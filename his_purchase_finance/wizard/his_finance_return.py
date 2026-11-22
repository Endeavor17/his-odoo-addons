# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HisFinanceReturn(models.TransientModel):
    _name = "his.finance.return"
    _description = "Return Purchase Order to Buyer"

    order_id = fields.Many2one("purchase.order", required=True)
    reason = fields.Text(string="Reason", required=True)

    def action_return(self):
        self.order_id._his_return(self.reason)
        return {"type": "ir.actions.act_window_close"}
