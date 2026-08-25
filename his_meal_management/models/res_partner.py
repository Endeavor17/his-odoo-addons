from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    """The meal wallet. Identity lives in `his.person`, not here.

    This module used to carry the Person of the HIS data model on res.partner
    itself — matricule, nom arabe, type de personne, statut, the two emails.
    All of that now belongs to `his_person_core`, which anchors a person on a
    `his.person` record delegating to `res.partner`. One identity for the whole
    group: employees, teachers, students, candidates.

    What stays here is the wallet, and it stays on res.partner deliberately:
    the card mirrors its code onto `res.partner.barcode`, Odoo's own 'client'
    barcode rule resolves a partner, and the POS sells to a partner. Since
    every `his.person` carries one, `person.meal_credits_remaining` resolves
    through delegation with nothing extra to define — while a walk-in customer
    with no identity still can't hold a balance, because a card and a
    subscription both refuse a partner with no `his.person` (see
    `_check_meal_holder_is_registered` on those models).

    Credits hang off the person, never off the card. Everything that moves a
    balance goes through `_grant_meal_credits` or `_consume_meal_credit`.
    """

    _inherit = 'res.partner'

    # --- Meal account ------------------------------------------------------
    meal_card_ids = fields.One2many('his.meal.card', 'partner_id', string="Meal Cards")
    meal_subscription_ids = fields.One2many('his.meal.subscription', 'partner_id')
    meal_transaction_ids = fields.One2many('his.meal.transaction', 'partner_id')
    # compute_sudo: a restaurant cashier is allowed to see a balance without
    # being granted read access to the subscription ledger itself.
    meal_credits_remaining = fields.Integer(
        string="Meal Credits", compute='_compute_meal_credits_remaining', compute_sudo=True,
    )
    meal_card_code = fields.Char(
        string="Card Code", compute='_compute_meal_card_code', compute_sudo=True,
        help="The code on the person's active card.",
    )
    meal_active_plan = fields.Char(
        string="Current Plan", compute='_compute_meal_credits_remaining', compute_sudo=True,
    )

    # The wallet's gate — a partner may only carry meal records if a
    # `his.person` anchors them — reads `his_person_ids`, which belongs to
    # his_person_core (models/res_partner.py) and is not redeclared here. It
    # was, briefly: a second declaration of the same field on the same model
    # adds nothing but a relabelling, and the socle owns the label. Its
    # unique(partner_id) is what makes this 0-or-1 and safe to read as [:1].

    # ------------------------------------------------------------------
    # Meal account
    # ------------------------------------------------------------------
    def _usable_subscriptions(self):
        """Subscriptions that may be eaten from today, soonest to expire first.

        Ordering by `date_end` means the credits about to be lost are spent
        before the ones that keep, which is what a person would choose.
        """
        self.ensure_one()
        today = fields.Date.context_today(self)
        return self.env['his.meal.subscription'].search(
            [
                ('partner_id', '=', self.id),
                ('state', '!=', 'cancelled'),
                ('credits_remaining', '>', 0),
                ('date_start', '<=', today),
                ('date_end', '>=', today),
            ],
            order='date_end asc, id asc',
        )

    @api.depends('meal_subscription_ids.credits_remaining', 'meal_subscription_ids.state')
    def _compute_meal_credits_remaining(self):
        for partner in self:
            subs = partner._usable_subscriptions() if partner.id else self.env['his.meal.subscription']
            partner.meal_credits_remaining = sum(subs.mapped('credits_remaining'))
            partner.meal_active_plan = subs[:1].product_id.display_name or ""

    @api.depends('meal_card_ids.state', 'meal_card_ids.code')
    def _compute_meal_card_code(self):
        for partner in self:
            active = partner.meal_card_ids.filtered(lambda c: c.state == 'active')
            partner.meal_card_code = active[:1].code or ""

    def _active_meal_card(self):
        self.ensure_one()
        return self.meal_card_ids.filtered(lambda c: c.state == 'active')[:1]

    def _add_meal_credits(self, credits, date_end, tx_type='purchase', product=None,
                          pos_order=None, note=None):
        """Put credits on the person as one new subscription, and log it."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        subscription = self.env['his.meal.subscription'].create({
            'partner_id': self.id,
            'product_id': product.id if product else False,
            'pos_order_id': pos_order.id if pos_order else False,
            'date_start': today,
            'date_end': date_end,
            'credits_total': credits,
        })
        self.invalidate_recordset(['meal_credits_remaining', 'meal_active_plan'])
        self._log_meal_transaction(
            tx_type=tx_type,
            credits=credits,
            subscription=subscription,
            product=product,
            pos_order=pos_order,
            note=note,
        )
        return subscription

    def _grant_meal_credits(self, product, pos_order=None, note=None):
        """Sell a plan: create the subscription and log the grant."""
        self.ensure_one()
        if product.meal_credits <= 0:
            raise UserError(_("%s is not a meal plan.", product.display_name))
        today = fields.Date.context_today(self)
        return self._add_meal_credits(
            credits=product.meal_credits,
            # -1 so a 7-day plan bought today is usable today through day 7,
            # not day 8.
            date_end=today + timedelta(days=product.meal_validity_days - 1),
            tx_type='purchase',
            product=product,
            pos_order=pos_order,
            note=note,
        )

    def _consume_meal_credit(self, qty=1, pos_order=None, tx_type='consume', note=None):
        """Eat `qty` meals. Raises if the person is short; never goes negative.

        Called from the POS order hook on the server, so the browser cannot
        decide whether a credit was really available.
        """
        self.ensure_one()
        if qty <= 0:
            return self.env['his.meal.transaction']

        # Lock this person's subscriptions for the length of the transaction.
        # Without it, two cashiers scanning the same card at the same instant
        # could both read "1 credit left" and both serve a meal.
        # Flush first so our own pending writes reach the rows we are locking,
        # then invalidate so the counters are re-read at their committed values.
        self.env['his.meal.subscription'].flush_model()
        self.env.cr.execute(
            "SELECT id FROM his_meal_subscription WHERE partner_id = %s FOR UPDATE",
            [self.id],
        )
        self.env['his.meal.subscription'].invalidate_model(
            ['credits_used', 'credits_remaining', 'state']
        )

        card = self._active_meal_card()
        transactions = self.env['his.meal.transaction']
        for _i in range(qty):
            subscription = self._usable_subscriptions()[:1]
            if not subscription:
                raise UserError(_(
                    "%(person)s has no meal credits available.",
                    person=self.display_name,
                ))
            subscription.credits_used += 1
            self.invalidate_recordset(['meal_credits_remaining', 'meal_active_plan'])
            transactions |= self._log_meal_transaction(
                tx_type=tx_type,
                credits=-1,
                subscription=subscription,
                product=pos_order.config_id.meal_product_id if pos_order else None,
                pos_order=pos_order,
                card=card,
                note=note,
            )
        return transactions

    def _log_meal_transaction(self, tx_type, credits, subscription=None, product=None,
                              pos_order=None, card=None, note=None):
        self.ensure_one()
        session = pos_order.session_id if pos_order else self.env['pos.session']
        return self.env['his.meal.transaction'].sudo().create({
            'partner_id': self.id,
            'card_id': (card or self._active_meal_card()).id or False,
            'subscription_id': subscription.id if subscription else False,
            'type': tx_type,
            'credits': credits,
            'balance_after': self.meal_credits_remaining,
            'product_id': product.id if product else False,
            'pos_order_id': pos_order.id if pos_order else False,
            'session_id': session.id or False,
            'config_id': session.config_id.id or False,
            'user_id': self.env.user.id,
            'note': note,
        })

    def get_meal_balance(self):
        """Read-only summary for the POS button. UX only — never authoritative.

        sudo because the cashier is shown a balance without being given read
        access to the subscriptions behind it.
        """
        self.ensure_one()
        subs = self.sudo()._usable_subscriptions()
        # The displayed matricule, not the stored one: his_person_core hides the
        # check digit on screen because a check digit only helps whoever copies
        # the number by hand, and nobody copies this one - it is read off a card.
        person = self.sudo().his_person_ids[:1]
        return {
            'partner_id': self.id,
            'name': self.display_name,
            'matricule': person.matricule_affiche or "",
            'credits': sum(subs.mapped('credits_remaining')),
            'plan': subs[:1].product_id.display_name or "",
            'expires': fields.Date.to_string(subs[:1].date_end) if subs else "",
        }

    def action_open_meal_transactions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Meal History"),
            'res_model': 'his.meal.transaction',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
