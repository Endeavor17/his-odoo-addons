# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Lus et ecrits sur le partenaire de la societe, comme `vat` (le NIF).
    his_rc = fields.Char(related="partner_id.his_rc", readonly=False)
    his_nis = fields.Char(related="partner_id.his_nis", readonly=False)
    his_ai = fields.Char(related="partner_id.his_ai", readonly=False)
