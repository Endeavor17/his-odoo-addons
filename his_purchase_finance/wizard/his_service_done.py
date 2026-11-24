# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HisServiceDone(models.TransientModel):
    """Le demandeur n'a pas acces aux commandes : il choisit la sienne dans une
    liste calculee, sans lire purchase.order."""

    _name = "his.service.done"
    _description = "Confirm Service Done"

    order_ref = fields.Selection(selection="_selection_orders", string="Purchase Order", required=True)
    period = fields.Char(string="Period or Date of the Service", required=True)
    note = fields.Text(string="Reservations or Anomalies")
    compliant = fields.Boolean(
        string="Service Compliant",
        default=True,
        help="Untick if the service is not compliant: an anomaly is declared instead of the confirmation.",
    )

    @api.model
    def _his_orders(self):
        orders = self.env["purchase.order"].sudo().browse(self.env.context.get("his_order_ids") or [])
        return orders.filtered(lambda o: o._his_awaits_service())

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

    def action_confirm(self):
        self.ensure_one()
        order = self.env["purchase.order"].browse(int(self.order_ref))
        if not self.compliant:
            # Procedure 6.2 : en cas de non-conformite, l'anomalie part a l'acheteur.
            if not (self.note or "").strip():
                raise UserError(_("Describe what is not compliant."))
            self.env["his.purchase.anomaly"]._his_declare(
                order, "service", _("%(period)s: %(note)s", period=self.period, note=self.note)
            )
            return {"type": "ir.actions.act_window_close"}
        order._his_certify_service(self.period, self.note)
        return {"type": "ir.actions.act_window_close"}
