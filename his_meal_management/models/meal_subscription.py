from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

# Credits move in halves. Two decimals is one more than the scheme needs, which
# leaves room for a future third of a credit without touching the columns.
CREDIT_PRECISION = 2


class HisMealSubscription(models.Model):
    """One purchase of one meal plan by one student.

    The plan (product) is the offer; this is what the student actually bought,
    with its own validity window and its own counters.
    """

    _name = 'his.meal.subscription'
    _description = "Meal Subscription"
    _order = 'date_end, id'

    partner_id = fields.Many2one(
        'res.partner', string="Person", required=True, index=True, ondelete='restrict',
    )
    # Empty on a manual correction: those credits come from an officer's
    # decision, not from a plan the student bought.
    product_id = fields.Many2one(
        'product.product', string="Meal Plan", ondelete='restrict',
    )
    pos_order_id = fields.Many2one('pos.order', string="Purchase Order", readonly=True)
    date_start = fields.Date(required=True, default=fields.Date.context_today)
    # Not required: empty means the credits never expire, which is now the
    # normal case. A plan with meal_validity_days = 0 lands here as False.
    date_end = fields.Date(
        help="Leave empty for credits that never expire.",
    )

    # Decimal, because a 300 DA meal costs half a credit. Every amount this
    # module moves is a multiple of 0.5, and halves are exact in binary
    # floating point, so no sequence of grants and meals can drift.
    credits_total = fields.Float(required=True, readonly=True, digits=(16, 2))
    credits_used = fields.Float(default=0.0, readonly=True, digits=(16, 2))
    credits_remaining = fields.Float(
        compute='_compute_credits_remaining', store=True, readonly=True, digits=(16, 2),
    )
    state = fields.Selection(
        [
            ('active', "Active"),
            ('exhausted', "Exhausted"),
            ('expired', "Expired"),
            ('cancelled', "Cancelled"),
        ],
        compute='_compute_state', store=True, index=True, readonly=False,
    )
    transaction_ids = fields.One2many(
        'his.meal.transaction', 'subscription_id', readonly=True,
    )

    # The heart of the safety story: a negative balance is rejected by Postgres
    # itself, so no bug, race or manual write anywhere in Odoo can produce one.
    _credits_within_bounds = models.Constraint(
        'CHECK (credits_used >= 0 AND credits_used <= credits_total)',
        "A subscription cannot use fewer than zero or more credits than it was sold.",
    )
    _credits_total_positive = models.Constraint(
        'CHECK (credits_total > 0)',
        "A subscription must carry at least one credit.",
    )
    # NULL date_end makes this comparison NULL, which a CHECK accepts - so a
    # never-expiring subscription passes without needing its own clause.
    _dates_ordered = models.Constraint(
        'CHECK (date_end >= date_start)',
        "A subscription cannot end before it starts.",
    )

    @api.constrains('partner_id')
    def _check_meal_holder_is_registered(self):
        """Same gate as the card, from the other side.

        A card is not the only way into the wallet: selling a plan at the POS
        creates a subscription straight from the order's customer. Without this,
        a cashier picking any contact would open a balance on someone outside
        the referential - the hole the card constraint closes, reopened.
        """
        for sub in self:
            if not sub.partner_id.sudo().his_person_ids:
                raise ValidationError(_(
                    "%s has no person record, so no meal credits can be held.\n\n"
                    "Sell the plan to a registered person, or have them registered "
                    "in the Personnes referential first.",
                    sub.partner_id.display_name,
                ))

    @api.depends('credits_total', 'credits_used')
    def _compute_credits_remaining(self):
        for sub in self:
            sub.credits_remaining = sub.credits_total - sub.credits_used

    @api.depends('credits_remaining', 'date_start', 'date_end')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for sub in self:
            if sub.state == 'cancelled':
                continue
            if float_compare(sub.credits_remaining, 0.0, CREDIT_PRECISION) <= 0:
                sub.state = 'exhausted'
            elif sub.date_end and sub.date_end < today:
                sub.state = 'expired'
            else:
                sub.state = 'active'

    def _is_usable(self, on_date):
        self.ensure_one()
        return (
            self.state != 'cancelled'
            and float_compare(self.credits_remaining, 0.0, CREDIT_PRECISION) > 0
            and self.date_start <= on_date
            # No end date means it never stops being usable.
            and (not self.date_end or on_date <= self.date_end)
        )

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    @api.model
    def _cron_expire_subscriptions(self):
        """Refresh `state` so lists and filters show reality.

        Consumption does not rely on this: `_consume_meal_credit` checks the
        dates directly, so a missed cron run can never let an expired plan be
        eaten. This only keeps the displayed state honest.
        """
        stale = self.search([
            ('state', '=', 'active'),
            ('date_end', '<', fields.Date.context_today(self)),
        ])
        stale._compute_state()
