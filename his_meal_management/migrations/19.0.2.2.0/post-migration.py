"""Wire the Restaurant till to the student meal on databases that already exist.

post_init_hook only runs when a module is INSTALLED. Every database that has
been running this module - the group's own included - upgrades instead, so the
hook never fires there and `pos.config.meal_product_id` stays empty: the
Student Meal button reports "Not configured" at a till that has been serving
meals for months.

The hook and this script are deliberately the same function, called twice from
two different events, rather than two copies of one rule.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api
    from odoo.addons.his_meal_management import post_init_hook

    env = api.Environment(cr, SUPERUSER_ID, {})
    config = env.ref('his_stock_mdm.pos_config_restaurant', raise_if_not_found=False)
    before = config.meal_product_id if config else None

    post_init_hook(env)

    if not config:
        _logger.info("his_stock_mdm absent: no Restaurant to wire, nothing to do.")
    elif before:
        _logger.info(
            "%s already serves %s: left as configured.",
            config.display_name, before.display_name,
        )
