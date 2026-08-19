from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class PosOrder(models.Model):
    """Where credits actually move.

    Both directions run here, on the server, when a validated order is saved:
    selling a plan grants credits, ringing up the student meal spends them. The
    browser only ever asks for these things politely — it cannot perform them,
    so a cashier with the developer console open still cannot invent a credit.
    """

    _inherit = 'pos.order'

    def _process_saved_order(self, draft):
        res = super()._process_saved_order(draft)
        if not draft and self.state != 'cancel':
            self._apply_meal_credits()
        return res

    def _already_applied(self):
        """Orders can be re-synced. Credits must move exactly once."""
        self.ensure_one()
        return bool(self.env['his.meal.transaction'].sudo().search_count(
            [('pos_order_id', '=', self.id)], limit=1
        ))

    def _apply_meal_credits(self):
        self.ensure_one()
        if self._already_applied():
            return

        plan_lines = self.lines.filtered(lambda line: line.product_id.meal_credits > 0)
        meal_product = self.config_id.meal_product_id
        rounding = self.currency_id.rounding
        meal_lines = self.lines.filtered(
            lambda line: meal_product
            and line.product_id == meal_product
            # A student meal is the free one. The same product sold at its real
            # price is a paying customer and must not touch anyone's balance.
            and float_is_zero(line.price_unit, precision_rounding=rounding)
        )

        if not plan_lines and not meal_lines:
            return

        if not self.partner_id:
            raise UserError(_(
                "Scan the student's card before validating: this order carries a "
                "meal plan or a student meal but has no student on it."
            ))

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

        total_meals = int(sum(meal_lines.mapped('qty')))
        if total_meals > 0:
            partner._consume_meal_credit(qty=total_meals, pos_order=self)
