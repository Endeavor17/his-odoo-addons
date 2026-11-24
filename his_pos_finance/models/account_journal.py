# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    his_holder_id = fields.Many2one("res.users", string="Cash Box Holder", help="Person who holds this cash box.")
