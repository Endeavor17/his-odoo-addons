from odoo import api, models


class ProductProduct(models.Model):
    """Make the copy dimensions readable at the till.

    Unlike `pos.config`, which POS reads with an empty field list and therefore
    hands over whole, `product.product` ships an explicit whitelist. A field
    missing from it does not error — it simply never arrives, and the builder
    then matches nothing while every product looks correctly configured in the
    backend. That failure is silent and expensive, so the test suite pins this
    list rather than trusting it.

    The four fields live on `product.template`; `product.product` _inherits it,
    so reading them off a variant is ordinary delegation.
    """

    _inherit = 'product.product'

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + [
            'copy_service', 'copy_format', 'copy_color', 'copy_sides',
        ]
