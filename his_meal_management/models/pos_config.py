from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    meal_product_id = fields.Many2one(
        'product.product', string="Student Meal Product",
        domain=[('available_in_pos', '=', True)],
        help="The meal a student pays for with credits. Set it on the restaurant "
             "point of sale; leave it empty on the one that sells the plans.",
    )

    # DO NOT add meal_product_id to _get_special_products().
    #
    # It looks like the right thing - pos_discount does exactly that for its
    # discount product - and it is a trap here. POS feeds that list into
    # `getExcludedProductIds()` (pos_store.js) and hides every special product
    # from the grid, because a tip or a discount is never meant to be clicked.
    # The Daily Meal *is*: someone with no credits pays the normal 600 for it.
    # Marking it special made it unsellable at the till.
    #
    # Nothing is needed in its place. POS loads every product with
    # available_in_pos = True and sale_ok = True with no row limit
    # (product_template._load_pos_data_domain), and the field's own domain
    # already restricts the choice to those. The one gap left is a config that
    # sets limit_categories and excludes the meal's category - then the button
    # reports "Not configured", which is a clear and fixable message.
