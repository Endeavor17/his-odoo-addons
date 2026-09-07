from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round

from .meal_subscription import ALLOWANCE_MEALS, CREDIT_PRECISION


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
    meal_credits_remaining = fields.Float(
        string="Meal Credits", digits=(16, 2),
        compute='_compute_meal_credits_remaining', compute_sudo=True,
    )
    meal_card_code = fields.Char(
        string="Card Code", compute='_compute_meal_card_code', compute_sudo=True,
        help="The code on the person's active card.",
    )
    meal_active_plan = fields.Char(
        string="Current Plan", compute='_compute_meal_credits_remaining', compute_sudo=True,
    )
    # The safety net: meals still available on an empty card, and what has
    # already been eaten on it. compute_sudo for the same reason as the balance
    # above - a cashier is shown both without being handed the ledger.
    meal_allowance_left = fields.Integer(
        string="Allowance Meals Left", compute='_compute_meal_allowance', compute_sudo=True,
        help="Meals this person may still take on an empty card. Reset by the "
             "next top-up, which also settles what is owed.",
    )
    meal_allowance_debt = fields.Float(
        string="Owed From Allowance", digits=(16, 2),
        compute='_compute_meal_allowance', compute_sudo=True,
        help="Credits eaten on an empty card. Taken off the next top-up.",
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
        Postgres sorts NULLs last on an ASC order, so subscriptions that never
        expire naturally come after every dated one - exactly the right
        priority now that never-expiring is the normal case.
        """
        self.ensure_one()
        today = fields.Date.context_today(self)
        return self.env['his.meal.subscription'].search(
            [
                ('partner_id', '=', self.id),
                ('state', '!=', 'cancelled'),
                ('credits_remaining', '>', 0),
                ('date_start', '<=', today),
                '|', ('date_end', '=', False), ('date_end', '>=', today),
            ],
            order='date_end asc, id asc',
        )

    @api.depends('meal_subscription_ids.credits_remaining', 'meal_subscription_ids.state')
    def _compute_meal_credits_remaining(self):
        for partner in self:
            subs = partner._usable_subscriptions() if partner.id else self.env['his.meal.subscription']
            partner.meal_credits_remaining = sum(subs.mapped('credits_remaining'))
            partner.meal_active_plan = subs[:1].product_id.display_name or ""

    # ------------------------------------------------------------------
    # The allowance
    # ------------------------------------------------------------------
    # Two meals on an empty card, for anyone who has bought a plan, settled out
    # of the next top-up. It is deliberately NOT a negative balance: the CHECK
    # constraint on his.meal.subscription is the module's whole safety story and
    # it stays untouched. What an allowance meal leaves behind is a ledger line
    # and nothing else.
    #
    # Both numbers below are derived from that ledger rather than stored in a
    # counter. The ledger is already append-only (write and unlink both raise),
    # so it cannot disagree with itself, there is no field to reset and no
    # migration to write for the students who already exist.
    def _allowance_boundary(self):
        """The last time credits landed on this account.

        Everything after it is the current cycle. A top-up is therefore its own
        reset: nothing has to remember to zero a counter.
        """
        self.ensure_one()
        return self.env['his.meal.transaction'].sudo().search(
            [
                ('partner_id', '=', self.id),
                ('type', 'in', ('purchase', 'adjust')),
                ('credits', '>', 0),
            ],
            order='id desc', limit=1,
        )

    def _meal_allowance_state(self):
        """(meals taken on an empty card this cycle, credits owed for them)."""
        self.ensure_one()
        domain = [('partner_id', '=', self.id), ('type', '=', 'allowance')]
        boundary = self._allowance_boundary()
        if boundary:
            # id, not date: a top-up and the repayment it pays for are written
            # in the same transaction and share a timestamp to the second.
            domain.append(('id', '>', boundary.id))
        lines = self.env['his.meal.transaction'].sudo().search(domain)
        debt = float_round(
            -sum(lines.mapped('credits')), precision_digits=CREDIT_PRECISION,
        )
        return len(lines), debt

    @api.depends('meal_transaction_ids.type', 'meal_transaction_ids.credits')
    def _compute_meal_allowance(self):
        for partner in self:
            if not partner.id or not partner._qualifies_for_allowance():
                partner.meal_allowance_left = 0
                partner.meal_allowance_debt = 0.0
                continue
            used, debt = partner._meal_allowance_state()
            partner.meal_allowance_left = max(0, ALLOWANCE_MEALS - used)
            partner.meal_allowance_debt = debt

    def _qualifies_for_allowance(self):
        """Only someone who has actually bought a plan eats on credit.

        A subscription with no product came from the correction wizard, so a
        hand-granted credit never by itself buys the right to run a card empty.
        """
        self.ensure_one()
        return bool(self.sudo().meal_subscription_ids.filtered('product_id'))

    def _can_take_allowance_meal(self):
        """Read straight off the ledger, not off the computed field.

        This is called mid-transaction, between two writes to that very ledger,
        which is exactly when a cached compute is worth nothing.
        """
        self.ensure_one()
        if not self._qualifies_for_allowance():
            return False
        self.env['his.meal.transaction'].flush_model()
        used, _debt = self._meal_allowance_state()
        return used < ALLOWANCE_MEALS

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
        # Read the debt BEFORE anything is written. The cycle boundary is the
        # last top-up, so the purchase line below becomes the boundary the
        # moment it exists and every allowance meal falls behind it — asking
        # afterwards would always answer "nothing owed".
        self.env['his.meal.transaction'].flush_model()
        _used, debt = self._meal_allowance_state()
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
        self._settle_meal_allowance(debt, pos_order=pos_order)
        return subscription

    def _settle_meal_allowance(self, debt, pos_order=None):
        """Pay back what was eaten on an empty card, out of the credits just added.

        Here rather than in `_grant_meal_credits` because this is the one funnel
        every credit arrives through - a plan sold at the till and a correction
        typed by an officer both land in `_add_meal_credits` - so the debt is
        settled once, in one place, whichever way the top-up came.

        The repayment goes through the ordinary guarded path, so it can no more
        push a subscription past its total than a meal can, and it leaves a
        normal ledger line: the student's history reads +3.0 purchase, -2.0
        repayment, and the subscription shows 3.0 total / 2.0 used / 1.0 left.
        """
        self.ensure_one()
        if float_compare(debt, 0.0, CREDIT_PRECISION) <= 0:
            return self.env['his.meal.transaction']

        self.invalidate_recordset(['meal_credits_remaining', 'meal_active_plan'])
        available = self.meal_credits_remaining
        # ponytail: a top-up smaller than the debt repays what it can and the
        # rest is written off - the new purchase line becomes the cycle
        # boundary, so the unpaid remainder falls behind it. Unreachable from
        # the till (the smallest plan is 3.0 credits and the largest possible
        # debt is 2.0); only a hand correction under 2 credits can do it. If
        # that ever matters, give repayments their own ledger type and make the
        # debt a running total instead of a per-cycle one.
        repay = min(debt, available)
        if float_compare(repay, 0.0, CREDIT_PRECISION) <= 0:
            return self.env['his.meal.transaction']
        return self._consume_meal_credit(
            amount=repay,
            pos_order=pos_order,
            note=_("Repaid %(credits)s credit(s) eaten on an empty card", credits=repay),
        )

    def _grant_meal_credits(self, product, pos_order=None, note=None):
        """Sell a plan: create the subscription and log the grant."""
        self.ensure_one()
        if float_compare(product.meal_credits, 0.0, CREDIT_PRECISION) <= 0:
            raise UserError(_("%s is not a meal plan.", product.display_name))
        today = fields.Date.context_today(self)
        # Zero validity means the credits keep until they are eaten. Otherwise
        # -1 so a 7-day plan bought today is usable today through day 7, not
        # day 8.
        date_end = False
        if product.meal_validity_days > 0:
            date_end = today + timedelta(days=product.meal_validity_days - 1)
        return self._add_meal_credits(
            credits=product.meal_credits,
            date_end=date_end,
            tx_type='purchase',
            product=product,
            pos_order=pos_order,
            note=note,
        )

    def _consume_meal_credit(self, amount=1.0, pos_order=None, tx_type='consume',
                             note=None, product=None, allow_overdraft=False):
        """Spend `amount` credits. Raises if short; never goes negative.

        `amount` is decimal because meals are not all worth the same: a 300 DA
        meal takes 0.5 and a 600 DA one takes 1. It is a total, not a meal
        count - the caller multiplies quantity by the product's cost.

        The amount is drawn across subscriptions in expiry order, so a meal
        costing 1 credit can take 0.5 from a plan about to run out and 0.5 from
        the next. Each subscription touched gets its own ledger line, which is
        what makes a split visible afterwards.

        `allow_overdraft` lets what the subscriptions cannot cover fall through
        to the allowance - two meals on an empty card for anyone who has bought
        a plan. It defaults to False, and that default is load-bearing: the
        correction wizard's negative branch calls this same method to take
        credits back, and taking credits back must never open an overdraft.
        Only the meal loop in pos_order.py passes True.

        Called from the POS order hook on the server, so the browser cannot
        decide whether a credit was really available.
        """
        self.ensure_one()
        if float_compare(amount, 0.0, CREDIT_PRECISION) <= 0:
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
        left_to_spend = float_round(amount, precision_digits=CREDIT_PRECISION)

        while float_compare(left_to_spend, 0.0, CREDIT_PRECISION) > 0:
            subscription = self._usable_subscriptions()[:1]
            if not subscription:
                # Out of credits. Either the allowance covers the rest of this
                # meal, or nobody eats.
                if allow_overdraft and self._can_take_allowance_meal():
                    # One line for whatever is left of this meal, whether that
                    # is the whole of it or the half a subscription could not
                    # cover. One call to this method is one meal, so one line
                    # here is one meal against the two-meal cap.
                    #
                    # Invalidate first so balance_after is read at its committed
                    # value: it is 0 by definition here, and saying so plainly
                    # is what makes the ledger legible afterwards.
                    self.invalidate_recordset(['meal_credits_remaining', 'meal_active_plan'])
                    transactions |= self._log_meal_transaction(
                        tx_type='allowance',
                        credits=-left_to_spend,
                        product=product,
                        pos_order=pos_order,
                        card=card,
                        note=note or _("Served on an empty card"),
                    )
                    break
                # Raising rolls the whole transaction back, so the credits
                # already taken from earlier subscriptions in this loop are
                # never left spent against a meal that was not served.
                raise UserError(_(
                    "%(person)s has no meal credits available.",
                    person=self.display_name,
                ))
            take = min(subscription.credits_remaining, left_to_spend)
            subscription.credits_used += take
            left_to_spend = float_round(
                left_to_spend - take, precision_digits=CREDIT_PRECISION,
            )
            self.invalidate_recordset(['meal_credits_remaining', 'meal_active_plan'])
            transactions |= self._log_meal_transaction(
                tx_type=tx_type,
                credits=-take,
                subscription=subscription,
                product=product,
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
            # Empty when the credits never expire, which the till reads as
            # "don't mention a date" rather than "no date known".
            'expires': fields.Date.to_string(subs[:1].date_end) if subs[:1].date_end else "",
            # What the cashier needs to see when the card comes up empty. Read
            # sudo like everything else here: showing a cashier that a card is
            # empty must not require handing them the ledger.
            'allowance_left': self.sudo().meal_allowance_left,
            'allowance_debt': self.sudo().meal_allowance_debt,
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
