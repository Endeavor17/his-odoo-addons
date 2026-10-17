# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HisPurchaseRequestReject(models.TransientModel):
    _name = "his.purchase.request.reject"
    _description = "Reject Purchase Request"

    request_id = fields.Many2one("his.purchase.request", required=True)
    reason = fields.Text(string="Reason", required=True)

    def action_reject(self):
        self.request_id._his_reject(self.reason)
        return {"type": "ir.actions.act_window_close"}
