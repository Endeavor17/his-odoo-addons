# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_pack = fields.Boolean(string="Est un Pack")
    pack_line_ids = fields.One2many(
        'product.pack.line', 'pack_id', string="Composants du Pack")
