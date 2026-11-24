# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HisCashDiscrepancyDecide(models.TransientModel):
    _name = "his.cash.discrepancy.decide"
    _description = "Finance Decision on a Cash Discrepancy"

    discrepancy_id = fields.Many2one("his.cash.discrepancy", required=True)
    decision = fields.Selection(
        [("accepted", "Accepted"), ("refused", "Refused"), ("investigating", "Further Investigation")],
        required=True,
        default="accepted",
    )
    account_id = fields.Many2one(
        "account.account",
        string="Regularisation Account",
        domain="[('account_type', 'not in', ('asset_receivable', 'liability_payable'))]",
        help="Empty: 657000 for a shortage, 757000 for a surplus.",
    )
    note = fields.Text()

    def action_confirm(self):
        self.ensure_one()
        self.discrepancy_id.action_decide(self.decision, account=self.account_id or None, note=self.note or "")
