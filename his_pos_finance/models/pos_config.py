# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    his_float_amount = fields.Monetary(
        string="Fixed Float", help="Cash left in the till after the evening hand over to Finance."
    )
