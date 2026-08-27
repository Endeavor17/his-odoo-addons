# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    besoin_achat_id = fields.Many2one(
        'university.besoin.achat', string="Besoin d'Achat",
        readonly=True, copy=False, index=True)
