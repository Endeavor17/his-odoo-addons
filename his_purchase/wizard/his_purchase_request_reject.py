# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HisPurchaseRequestReject(models.TransientModel):
    _name = "his.purchase.request.reject"
    _description = "Reject Purchase Request"

    request_id = fields.Many2one("his.purchase.request", required=True)
    reason = fields.Text(string="Reason", required=True)
    mode = fields.Selection([("reject", "Reject"), ("hold", "Put on Hold")], default="reject", required=True)

    def action_reject(self):
        if self.mode == "hold":
            self.request_id._his_hold(self.reason)
        else:
            self.request_id._his_reject(self.reason)
        return {"type": "ir.actions.act_window_close"}
