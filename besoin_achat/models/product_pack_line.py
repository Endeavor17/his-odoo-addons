# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductPackLine(models.Model):
    _name = 'product.pack.line'
    _description = "Composant de Pack Produit"
    _order = 'sequence, id'

    pack_id = fields.Many2one(
        'product.template', string="Pack", required=True, ondelete='cascade')
    sequence = fields.Integer(string="Séquence", default=10)

    product_id = fields.Many2one('product.product', string="Produit", required=True)
    product_qty = fields.Float(string="Quantité", default=1.0, required=True)
    product_uom_id = fields.Many2one('uom.uom', string="Unité de mesure")
    discount = fields.Float(string="Sale discount (%)")
    price_unit = fields.Float(string="Prix")
    subtotal = fields.Float(string="Sous-total", compute='_compute_subtotal', store=True)

    @api.depends('product_qty', 'price_unit', 'discount')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.product_qty * line.price_unit * (1 - (line.discount or 0.0) / 100.0)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.product_uom_id = line.product_id.uom_id
                line.price_unit = line.product_id.list_price

    @api.constrains('product_id', 'pack_id')
    def _check_no_self_reference(self):
        for line in self:
            if line.product_id.product_tmpl_id.id == line.pack_id.id:
                raise ValidationError(_("Un pack ne peut pas se contenir lui-même comme composant."))
