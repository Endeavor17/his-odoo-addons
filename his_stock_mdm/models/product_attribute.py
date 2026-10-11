# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    allowed_categ_ids = fields.Many2many(
        "product.category",
        string="Eligible Categories",
        help="If set, this attribute can only be used on products belonging to these "
        'categories. Leave empty for an unrestricted attribute (as with "Brand").',
    )
