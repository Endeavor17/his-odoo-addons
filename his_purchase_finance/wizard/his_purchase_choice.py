# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_amount

from ..models.purchase_order import QUOTE_THRESHOLD, QUOTES_REQUIRED


class HisPurchaseChoice(models.TransientModel):
    """Envoi a la Finance : le motif du choix, et la derogation aux 3 devis."""

    _inherit = "his.purchase.choice"

    quote_count = fields.Integer(string="Quotes", compute="_compute_quote_rule")
    needs_exception = fields.Boolean(string="Exception Needed", compute="_compute_quote_rule")

    @api.depends("order_id")
    def _compute_quote_rule(self):
        for wizard in self:
            wizard.quote_count = wizard.order_id._his_quote_count()
            wizard.needs_exception = wizard.order_id._his_needs_quote_exception()

    def action_confirm(self):
        if not self.env.context.get("his_send_to_finance"):
            return super().action_confirm()
        self.ensure_one()
        order = self.order_id
        self._his_check()
        exception = order._his_needs_quote_exception()
        if exception and not (self.note or "").strip():
            raise UserError(
                _(
                    "%(order)s is %(amount)s excl. tax with %(count)s quote(s): from %(threshold)s, %(required)s quotes "
                    "are required. Explain the exception in the note.",
                    order=order.name,
                    amount=format_amount(self.env, order._his_amount_company(), order.company_id.currency_id),
                    count=order._his_quote_count(),
                    threshold=format_amount(self.env, QUOTE_THRESHOLD, order.company_id.currency_id),
                    required=QUOTES_REQUIRED,
                )
            )
        self._his_record()
        if exception:
            order.message_post(
                body=_(
                    "Exception to the 3-quote rule (%(count)s quote(s)): %(note)s",
                    count=order._his_quote_count(),
                    note=self.note,
                )
            )
        order._his_mark_sent()
        return {"type": "ir.actions.act_window_close"}
