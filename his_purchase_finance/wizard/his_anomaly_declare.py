# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.his_purchase_anomaly import KINDS


class HisAnomalyDeclare(models.TransientModel):
    """Declarer une anomalie. Le demandeur ne lit pas les commandes : la liste
    est calculee en sudo, comme pour le service fait."""

    _name = "his.anomaly.declare"
    _description = "Declare a Purchase Anomaly"

    order_ref = fields.Selection(selection="_selection_orders", string="Purchase Order", required=True)
    kind = fields.Selection(KINDS, string="Type", required=True)
    description = fields.Text(string="Description", required=True)

    @api.model
    def _his_action(self, order_ids, picking=None, bill=None):
        if not order_ids:
            raise UserError(_("There is no confirmed purchase order to declare an anomaly on."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Declare Anomaly"),
            "res_model": "his.anomaly.declare",
            "view_mode": "form",
            "target": "new",
            "context": {
                "his_order_ids": list(order_ids),
                "his_picking_id": picking.id if picking else False,
                "his_bill_id": bill.id if bill else False,
            },
        }

    @api.model
    def _his_orders(self):
        return self.env["purchase.order"].sudo().browse(self.env.context.get("his_order_ids") or []).exists()

    @api.model
    def _selection_orders(self):
        return [(str(order.id), order.name) for order in self._his_orders()]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        orders = self._his_orders()
        if len(orders) == 1 and "order_ref" in fields_list:
            res["order_ref"] = str(orders.id)
        return res

    def action_declare(self):
        self.ensure_one()
        ctx = self.env.context
        order = self._his_orders().filtered(lambda o: str(o.id) == self.order_ref)
        if not order:
            raise UserError(_("Choose one of the listed purchase orders."))
        picking = self.env["stock.picking"].sudo().browse(ctx.get("his_picking_id") or [])
        bill = self.env["account.move"].sudo().browse(ctx.get("his_bill_id") or [])
        self.env["his.purchase.anomaly"]._his_declare(
            order,
            self.kind,
            self.description,
            picking=picking.filtered(lambda p: p.purchase_id == order) or None,
            bill=bill.filtered(lambda b: order in b.invoice_line_ids.purchase_line_id.order_id) or None,
        )
        return {"type": "ir.actions.act_window_close"}
