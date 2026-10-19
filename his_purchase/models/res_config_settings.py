# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    his_purchase_officer_id = fields.Many2one(related="company_id.his_purchase_officer_id")
    his_purchase_manager_id = fields.Many2one(related="company_id.his_purchase_manager_id", readonly=False)
    his_purchase_director_id = fields.Many2one(related="company_id.his_purchase_director_id", readonly=False)
