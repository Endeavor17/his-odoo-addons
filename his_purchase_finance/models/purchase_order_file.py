# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Avoir du apres un retour (procedure 8.4.3) et cloture du dossier d'achat (9.3)."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .common import is_finance


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    his_qty_to_refund = fields.Float(
        string="Credit Note Due (Qty)",
        compute="_compute_his_qty_to_refund",
        store=True,
        digits="Product Unit",
        help="Invoiced but no longer received (goods returned): a credit note is expected.",
    )

    @api.depends("qty_invoiced", "qty_received", "product_id.type", "is_downpayment", "display_type")
    def _compute_his_qty_to_refund(self):
        for line in self:
            goods = not line.display_type and not line.is_downpayment and line.product_id.type != "service"
            line.his_qty_to_refund = max(0.0, line.qty_invoiced - line.qty_received) if goods else 0.0


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    his_amount_to_refund = fields.Monetary(
        string="Credit Note Due",
        compute="_compute_his_amount_to_refund",
        store=True,
        currency_field="company_currency_id",
    )
    company_currency_id = fields.Many2one(related="company_id.currency_id", string="Company Currency")
    his_closed_on = fields.Datetime(string="File Closed On", readonly=True, copy=False)
    his_closed_by_id = fields.Many2one("res.users", string="File Closed By", readonly=True, copy=False)
    his_ready_to_close = fields.Boolean(
        string="Ready to Close", compute="_compute_his_ready_to_close", search="_search_his_ready_to_close"
    )

    @api.depends("order_line.his_qty_to_refund", "order_line.price_unit", "order_line.discount", "currency_id")
    def _compute_his_amount_to_refund(self):
        for order in self:
            amount = sum(
                line.his_qty_to_refund * line.price_unit * (1 - (line.discount or 0.0) / 100)
                for line in order.order_line
            )
            order.his_amount_to_refund = order.currency_id._convert(
                amount, order.company_id.currency_id, order.company_id, order.date_order or fields.Date.today()
            )

    def _his_close_blockers(self):
        """Ce qui manque pour clore le dossier ; vide si complet."""
        self.ensure_one()
        order = self.sudo()
        blockers = []
        if order.state != "purchase":
            blockers.append(_("the order is not confirmed"))
        if order.picking_ids.filtered(lambda p: p.state not in ("done", "cancel")):
            blockers.append(_("a receipt is still open"))
        if order._his_awaits_service():
            blockers.append(_("the service is not confirmed done"))
        if order.invoice_status == "to invoice":
            blockers.append(_("something is still to be billed"))
        unpaid = order.invoice_ids.filtered(
            lambda m: m.state == "posted"
            and m.move_type == "in_invoice"
            and m.payment_state not in ("paid", "in_payment", "reversed")
        )
        if unpaid:
            blockers.append(_("bills not paid: %s", ", ".join(unpaid.mapped("name"))))
        if order.his_amount_to_refund:
            blockers.append(_("a credit note is still due"))
        anomalies = order._his_open_anomalies()
        if anomalies:
            blockers.append(_("open anomalies: %s", ", ".join(anomalies.mapped("name"))))
        sides = set(self.env["his.supplier.rating"].sudo().search([("order_id", "=", order.id)]).mapped("side"))
        if sides != {"purchase", "finance"}:
            blockers.append(_("the supplier is not rated by both Purchasing and Finance"))
        return blockers

    def _compute_his_ready_to_close(self):
        for order in self:
            order.his_ready_to_close = not order.his_closed_on and not order._his_close_blockers()

    def _search_his_ready_to_close(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise UserError(_("Unsupported search on Ready to Close."))
        candidates = self.search([("state", "=", "purchase"), ("his_closed_on", "=", False)])
        ready = candidates.filtered(lambda o: not o._his_close_blockers())
        positive = (operator == "=") == value
        return [("id", "in" if positive else "not in", ready.ids)]

    def action_his_close_file(self):
        if not is_finance(self.env):
            raise UserError(_("Only Finance closes a purchase file."))
        for order in self:
            blockers = order._his_close_blockers()
            if blockers:
                raise UserError(
                    _("%(order)s cannot be closed: %(reasons)s.", order=order.name, reasons="; ".join(blockers))
                )
            order.sudo().write({"his_closed_on": fields.Datetime.now(), "his_closed_by_id": self.env.user.id})
            order.button_lock()
            order.message_post(body=_("Purchase file closed by %s.", self.env.user.name))
        return True
