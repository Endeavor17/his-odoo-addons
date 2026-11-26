# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import SUPERUSER_ID, api
from odoo.addons.his_pos_finance.hooks import carry_legacy_cash


def migrate(cr, version):
    # Bases installees en 19.0.1.0.0 : le fonds des caisses est reste sur
    # l'ancien compte de caisse (530001, la caisse Finance).
    env = api.Environment(cr, SUPERUSER_ID, {})
    for company in env["res.company"].search([]):
        if company.chart_template:
            carry_legacy_cash(env, company)
