# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Interrupteur de mise en service : sans lui, les tests de his_purchase
    # (post_install) et un demarrage sans Finance bloqueraient toute commande.
    his_finance_confirms = fields.Boolean(
        string="Finance Confirms Purchase Orders",
        default=True,
        help="Buyers send orders to Finance, which alone confirms them, once the supplier file is validated.",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    his_finance_confirms = fields.Boolean(related="company_id.his_finance_confirms", readonly=False)
