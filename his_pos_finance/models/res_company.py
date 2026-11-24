# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Seuils internes de la procedure (§6.2), bornes incluses.
    his_gap_minor = fields.Float(string="Minor Gap Up To", default=5.0)
    his_gap_significant = fields.Float(string="Significant Gap Up To", default=2000.0)
    his_gap_important = fields.Float(string="Important Gap Up To", default=5000.0)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    his_gap_minor = fields.Float(related="company_id.his_gap_minor", readonly=False)
    his_gap_significant = fields.Float(related="company_id.his_gap_significant", readonly=False)
    his_gap_important = fields.Float(related="company_id.his_gap_important", readonly=False)
