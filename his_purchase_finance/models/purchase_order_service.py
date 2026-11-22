# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Attestation de service fait (procedure Finance, etape 6.2 ; decision 7).

Le departement beneficiaire (demandeur ou chef du departement de la demande)
atteste la prestation ; une commande sans demande, le responsable achats.
L'attestation est exigee avant paiement : le rapprochement de la facture la
verifie (account_move.py).
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    his_has_services = fields.Boolean(string="Has Services", compute="_compute_his_has_services")
    his_service_done_by_id = fields.Many2one("res.users", string="Service Done Confirmed By", readonly=True, copy=False)
    his_service_done_on = fields.Datetime(string="Service Done Confirmed On", readonly=True, copy=False)
    his_service_period = fields.Char(string="Service Period", readonly=True, copy=False)
    his_service_note = fields.Text(string="Service Reservations", readonly=True, copy=False)

    @api.depends("order_line.product_id.type")
    def _compute_his_has_services(self):
        for order in self:
            order.his_has_services = any(line.product_id.type == "service" for line in order.order_line)

    def _his_awaits_service(self):
        self.ensure_one()
        return self.state == "purchase" and self.his_has_services and not self.his_service_done_on

    def _his_may_certify_service(self, user):
        """Le departement beneficiaire ; sans demande, le responsable achats."""
        self.ensure_one()
        requests = self.sudo()._his_requests()
        if not requests:
            return user.has_group("purchase.group_purchase_manager")
        return any(user in (r.requester_user_id | r.department_id.manager_id.user_id) for r in requests)

    def _his_certify_service(self, period, note):
        """Atteste le service de la commande, au nom de l'utilisateur courant."""
        user = self.env.user
        for order in self.sudo():
            if not order._his_may_certify_service(user):
                raise AccessError(_("Only the requesting department can confirm the service on %s.", order.name))
            if not order._his_awaits_service():
                raise UserError(_("%s has no confirmed service waiting for confirmation.", order.name))
            order.write(
                {
                    "his_service_done_by_id": user.id,
                    "his_service_done_on": fields.Datetime.now(),
                    "his_service_period": period,
                    "his_service_note": note,
                }
            )
            for line in order.order_line.filtered(lambda line: line.product_id.type == "service"):
                line.qty_received = line.product_qty
            order.message_post(
                body=_(
                    "Service done confirmed by %(user)s (%(period)s). %(note)s",
                    user=user.name,
                    period=period,
                    note=note or "",
                )
            )
            order._his_recheck_bills()

    def action_open_service_done(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Confirm Service Done"),
            "res_model": "his.service.done",
            "view_mode": "form",
            "target": "new",
            "context": {"his_order_ids": self.ids},
        }


class HisPurchaseRequest(models.Model):
    _inherit = "his.purchase.request"

    his_service_pending = fields.Boolean(
        string="Service to Confirm", compute="_compute_his_service_pending", compute_sudo=True
    )

    def _compute_his_service_pending(self):
        for request in self:
            request.his_service_pending = any(o._his_awaits_service() for o in request.order_ids)

    def action_open_service_done(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Confirm Service Done"),
            "res_model": "his.service.done",
            "view_mode": "form",
            "target": "new",
            "context": {"his_order_ids": self.sudo().order_ids.ids},
        }
