from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    """A meal plan is an ordinary product carrying a credit count.

    Reusing the product means price, POS sellability, invoicing and accounting
    are stock Odoo. There is no separate 'plan' model to keep in sync.
    """

    _inherit = 'product.template'

    meal_credits = fields.Integer(
        string="Meal Credits",
        help="Credits granted to the student when this product is sold. "
             "Any product with credits above zero is a meal plan.",
    )
    meal_validity_days = fields.Integer(
        string="Validity (days)",
        default=30,
        help="How long the credits stay usable, counted from the day of purchase.",
    )

    @api.constrains('meal_credits', 'meal_validity_days')
    def _check_meal_plan(self):
        for product in self:
            if product.meal_credits < 0:
                raise ValidationError(_("A meal plan cannot grant a negative number of credits."))
            if product.meal_credits and product.meal_validity_days <= 0:
                raise ValidationError(_(
                    "%s grants credits, so it needs a validity of at least one day.",
                    product.display_name,
                ))
