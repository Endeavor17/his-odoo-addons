from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


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
        rounding = self.currency_id.rounding
        # A meal is any product carrying a credit cost - the mirror of how a
        # plan is any product granting credits. It used to be the one product
        # named on this till's pos.config, which meant a shop served exactly
        # one meal and a shop with the field empty served none.
        meal_lines = self.lines.filtered(
            lambda line: (
                line.product_id.meal_credit_cost > 0
                # A student meal is the free one. The same product sold at its real
                # price is a paying customer and must not touch anyone's balance.
                and float_is_zero(line.price_unit, precision_rounding=rounding)
            )
        )

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
            # Audit S-5: credits are only as good as the money taken for them.
            # A plan at 0, or at its price with the discount button pressed,
            # used to hand over every credit as an ordinary purchase.
            paid = line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)
            if line.qty > 0 and float_compare(paid, line.product_id.lst_price, precision_rounding=rounding) < 0:
                raise UserError(
                    _(
                        "%(plan)s must be sold at its price, %(price)s. Meal credits are "
                        "not granted on a discounted or zero-priced plan.",
                        plan=line.product_id.display_name,
                        price=self.currency_id.format(line.product_id.lst_price),
                    )
                )
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
