# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HisBillDecision(models.TransientModel):
    _name = "his.bill.decision"
    _description = "Finance Decision on a Vendor Bill"

    move_id = fields.Many2one("account.move", required=True)
    decision = fields.Selection([("release", "Release"), ("refuse", "Refuse")], required=True)
    reason = fields.Text(string="Reason", required=True)

    def action_apply(self):
        self.move_id._his_decide(self.decision, self.reason)
        return {"type": "ir.actions.act_window_close"}
