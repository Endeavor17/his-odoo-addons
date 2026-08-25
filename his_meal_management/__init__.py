import logging

from . import models
from . import wizard

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Point the Restaurant till at the student meal, when there is a Restaurant.

    his_stock_mdm creates the group's three POS configs and knows nothing about
    meals; this module knows nothing about stock. Neither depends on the other
    and neither should, so the one field that joins them is set here at install
    rather than by a <record>, which would force a hard dependency for it.

    Two guards, both load-bearing:
      - his_stock_mdm absent is a normal install, not an error. The button then
        reports "Not configured", which pos_config.py already documents.
      - only an empty field is filled. Re-running the hook after a failed
        deployment must never overwrite what a manager chose at the till.
    """
    config = env.ref('his_stock_mdm.pos_config_restaurant', raise_if_not_found=False)
    if not config or config.meal_product_id:
        return
    meal = env.ref('his_meal_management.product_daily_meal', raise_if_not_found=False)
    if not meal:
        return
    # The data record is a product.template; the field holds a product.product.
    config.meal_product_id = meal.product_variant_id
    _logger.info(
        "his_meal_management: %s set as the student meal on %s.",
        meal.display_name, config.display_name,
    )
