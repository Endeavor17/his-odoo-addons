# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    allowed_categ_ids = fields.Many2many(
        'product.category',
        string="Catégories éligibles",
        help="Si renseigné, cet attribut ne peut être utilisé que sur des produits "
             "appartenant à ces catégories. Laisser vide pour un attribut sans "
             "restriction (cas de « Marque »).")
