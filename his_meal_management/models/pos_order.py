from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class PosOrder(models.Model):
    """Where credits actually move.

    Both directions run here, on the server, when a validated order is saved:
    selling a plan grants credits, ringing up the student meal spends them. The
    browser only ever asks for these things politely — it cannot perform them,
    so a cashier with the developer console open still cannot invent a credit.
    """

    _inherit = "pos.order"

    def _process_saved_order(self, draft):
        res = super()._process_saved_order(draft)
        if not draft and self.state != "cancel":
            self._apply_meal_credits()
        return res

    def _already_applied(self):
        """Orders can be re-synced. Credits must move exactly once."""
        self.ensure_one()
        return bool(self.env["his.meal.transaction"].sudo().search_count([("pos_order_id", "=", self.id)], limit=1))

    def _apply_meal_credits(self):
        self.ensure_one()
        if self._already_applied():
            return

        plan_lines = self.lines.filtered(lambda line: line.product_id.meal_credits > 0)
        meal_lines = self.lines.filtered(lambda line: line._his_is_credit_meal())

        if not plan_lines and not meal_lines:
            return

        if not self.partner_id:
            raise UserError(
                _(
                    "Scan the student's card before validating: this order carries a "
                    "meal plan or a student meal but has no student on it."
                )
            )

        # sudo() so a cashier who is not allowed to touch subscriptions still
        # gets the credit moved. It bypasses access rights without changing the
        # user, so the ledger still records who was at the till.
        partner = self.partner_id.sudo()

        # ponytail: refunds are a no-op on credits. A negative qty produces an
        # empty range and a non-positive meal count, so refunding a plan leaves
        # the subscription standing and refunding a meal gives no credit back -
        # an officer settles both with the correction wizard. Handle them here
        # only if refunds turn out to be common.
        for line in plan_lines:
            for _n in range(int(line.qty)):
                partner._grant_meal_credits(line.product_id, pos_order=self)

        # One call per meal served, not one per order line: the ledger has kept
        # a line per meal since it was written, and a cashier reading it back
        # wants to see two meals, not one line saying "2". What changes is that
        # each meal now costs what its own product says - 0.5 for a 300 DA
        # meal, 1 for a 600 DA one - instead of exactly one credit.
        #
        # The product is passed explicitly because the ledger used to read it
        # back off the till's config, which cannot tell two meals apart.
        #
        # A ticket short of credits raises partway through and the whole order
        # rolls back, so no meal is ever charged that the student did not get.
        #
        # This is the only caller that opts into the allowance. A student who
        # has bought a plan may take two meals on an empty card; the third is
        # refused here exactly as every meal was before. Nothing else in the
        # module passes allow_overdraft - least of all the correction wizard,
        # which uses the same method to take credits back.
        for line in meal_lines:
            cost = line.product_id.meal_credit_cost
            for _i in range(int(line.qty)):
                partner._consume_meal_credit(
                    amount=cost,
                    pos_order=self,
                    product=line.product_id,
                    allow_overdraft=True,
                )

    @api.model
    def _get_invoice_lines_values(self, line_values, pos_line, move_type):
        """Say on the invoice what a meal at 0 DA was really paid with.

        A meal served on credits is invoiced at zero, and rightly so: the money
        came in when the pack was sold, and invoicing the meal at its price
        would book the same revenue twice. But a line reading "Repas 600 -
        0,00" tells the student nothing, so the credits it took and what they
        are worth go into the line's label. The amounts are left alone.
        """
        values = super()._get_invoice_lines_values(line_values, pos_line, move_type)
        if values.get("display_type") or not pos_line._his_is_credit_meal():
            return values
        order = pos_line.order_id
        note = _(
            "Paid with %(credits)s meal credit(s), value %(value)s",
            credits=f"{pos_line.product_id.meal_credit_cost * pos_line.qty:g}",
            value=order.currency_id.format(pos_line.product_id.lst_price * pos_line.qty),
        )
        values["name"] = f"{values['name']}\n{note}" if values.get("name") else note
        return values


class PosOrderLine(models.Model):
    """One line, and the only question this module asks of it."""

    _inherit = "pos.order.line"

    def _his_meal_price_paid(self):
        """What the student hands over for one of these, discount included.

        A separate method rather than an expression inside the filter because
        this is the whole definition of "free meal" and it deserves a name a
        reader can grep for. Any other way of making a line cost nothing - a
        pricelist at zero, a future discount field - should land here too.
        """
        self.ensure_one()
        return self.price_unit * (1.0 - (self.discount or 0.0) / 100.0)

    def _his_is_credit_meal(self):
        """A meal the student eats on credits rather than pays for.

        A meal is any product carrying a credit cost - the mirror of how a plan
        is any product granting credits. It used to be the one product named on
        the till's pos.config, which meant a shop served exactly one meal and a
        shop with the field empty served none.

        The credit meal is the free one. The same product sold at its real price
        is a paying customer and must not touch anyone's balance.

        What counts is what the student actually pays, not the price printed on
        the line: this read `price_unit` alone until a test walked a meal out of
        the restaurant on a 100% discount. The discount button is on every till,
        needs no developer console, and left the meal ledger empty - so the food
        was gone and nothing anywhere counted it.

        The till's `isServedOnMealCredits` (static/src/app/pos_order.js) asks
        the same question to decide which screen to show; this one decides what
        the credits do.
        """
        self.ensure_one()
        return self.product_id.meal_credit_cost > 0 and float_is_zero(
            self._his_meal_price_paid(), precision_rounding=self.order_id.currency_id.rounding
        )
