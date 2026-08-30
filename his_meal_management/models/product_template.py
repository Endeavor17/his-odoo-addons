from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    """A meal plan is an ordinary product carrying a credit count.

    Reusing the product means price, POS sellability, invoicing and accounting
    are stock Odoo. There is no separate 'plan' model to keep in sync.

    Two roles, two fields, and a product holds at most one of them:
      - `meal_credits > 0`     -> a plan. Selling it puts credits on the student.
      - `meal_credit_cost > 0` -> a meal. Serving it at zero price takes credits.

    The cost lives on the product and not on the point of sale, which is what
    lets one till serve several meals at different prices. It used to be a
    single `meal_product_id` per pos.config, so a shop could serve exactly one
    meal and a shop with the field empty could serve none at all.
    """

    _inherit = 'product.template'

    meal_credits = fields.Float(
        string="Meal Credits Granted", digits=(16, 2),
        help="Credits given to the student when this product is sold. "
             "Any product with credits above zero is a meal plan.",
    )
    meal_credit_cost = fields.Float(
        string="Meal Credit Cost", digits=(16, 2),
        help="Credits taken from the student when this product is served at "
             "zero price. Any product with a cost above zero is a meal. "
             "The 300 DA meal costs 0.5, the 600 DA meal costs 1.",
    )
    meal_validity_days = fields.Integer(
        string="Validity (days)",
        default=0,
        help="How long the credits stay usable, counted from the day of "
             "purchase. Zero means they never expire.",
    )

    @api.constrains('meal_credits', 'meal_credit_cost', 'meal_validity_days')
    def _check_meal_plan(self):
        for product in self:
            if product.meal_credits < 0:
                raise ValidationError(_("A meal plan cannot grant a negative number of credits."))
            if product.meal_credit_cost < 0:
                raise ValidationError(_("A meal cannot cost a negative number of credits."))
            # Being both would make selling it grant and spend at the same time.
            if product.meal_credits and product.meal_credit_cost:
                raise ValidationError(_(
                    "%s cannot be a meal plan and a meal at once: it either grants "
                    "credits or costs them.",
                    product.display_name,
                ))
            if product.meal_validity_days < 0:
                raise ValidationError(_(
                    "%s cannot have a negative validity. Use zero for credits that "
                    "never expire.",
                    product.display_name,
                ))


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def _load_pos_data_fields(self, *args, **kwargs):
        """The till needs the cost to tell the cashier what a meal will take.

        This has to be asked for on product.product specifically. The POS
        variant delegates to its template only for methods and getters (see
        enhanceProductTemplate in core's models/product_product.js) - a plain
        loaded field like this one does not fall through, so without this line
        the meal buttons cannot price a meal or check it against the balance.

        Only the cost: `meal_credits` belongs to selling a plan, which happens
        server-side in pos.order._apply_meal_credits, and nothing in the
        browser reads it.

        *args rather than the declared parameter: core has renamed this
        argument between POS versions (config_id / config), and this override
        does not care which it is - it only appends to whatever core returns.
        """
        return super()._load_pos_data_fields(*args, **kwargs) + ['meal_credit_cost']
