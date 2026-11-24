# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HisCashTransferReceive(models.TransientModel):
    _name = "his.cash.transfer.receive"
    _description = "Receive a Cash Transfer"

    transfer_id = fields.Many2one("his.cash.transfer", required=True)
    currency_id = fields.Many2one(related="transfer_id.currency_id")
    amount_sent = fields.Monetary(related="transfer_id.amount_sent")
    amount = fields.Monetary(string="Amount Counted", required=True)

    def action_confirm(self):
        self.ensure_one()
        self.transfer_id.action_receive(self.amount)
