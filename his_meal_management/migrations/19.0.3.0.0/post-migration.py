"""Bring the four pre-existing products onto the new scheme, and drop the field
that used to tie a meal to a single till.

data/meal_plans.xml is noupdate="1", so the three plans and the meal that
already exist keep whatever they were loaded with - the new prices, names and
the meal's credit cost never reach a database that upgrades rather than
installs. That is the right default for records a manager may have edited, and
the wrong one here, so this writes them explicitly.

The three plans were the 600 DA tier all along under shorter names, and their
credit counts (6 / 25 / 80) were already correct. What changes is the name, the
category, and the loss of their expiry.
"""
import logging

_logger = logging.getLogger(__name__)

# xml id -> what it must now say. Credits are left alone where they were
# already right; validity goes to zero everywhere because credits no longer
# expire.
PLANS = {
    'product_plan_weekly': ("Pack 600 - Weekly (6 meals)", 6.0),
    'product_plan_monthly': ("Pack 600 - Monthly (25 meals)", 25.0),
    'product_plan_semester': ("Pack 600 - Semesterly (80 meals)", 80.0),
}


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    category = env.ref(
        'his_meal_management.product_category_meal_plans', raise_if_not_found=False,
    )

    for xml_id, (name, credits) in PLANS.items():
        plan = env.ref(f'his_meal_management.{xml_id}', raise_if_not_found=False)
        if not plan:
            continue
        vals = {'name': name, 'meal_credits': credits, 'meal_validity_days': 0}
        if category:
            vals['categ_id'] = category.id
        plan.write(vals)
        _logger.info("his_meal_management: %s is now %s, %s credits, no expiry.",
                     xml_id, name, credits)

    # The Daily Meal becomes Meal 600 and gains the cost that makes it a meal.
    # Without this it stays a product nothing recognises: the till identifies a
    # meal by meal_credit_cost now, not by a field on pos.config.
    meal = env.ref('his_meal_management.product_daily_meal', raise_if_not_found=False)
    if meal:
        # meal_validity_days back to 0 as well: it carried the old default of
        # 30, which is meaningless on a meal (only a plan's validity is ever
        # read, in _grant_meal_credits) and reads as a contradiction next to
        # Meal 300. A fresh install gets 0 from the field default.
        meal.write({
            'name': "Meal 600",
            'meal_credit_cost': 1.0,
            'meal_validity_days': 0,
        })
        _logger.info("his_meal_management: Daily Meal is now Meal 600 at 1 credit.")

    # A meal is no longer configured per point of sale, so every till serves
    # every meal - which is what finally lets the Cafeteria serve one at all.
    cr.execute("ALTER TABLE pos_config DROP COLUMN IF EXISTS meal_product_id")
    cr.execute(
        """
        DELETE FROM ir_model_fields
         WHERE name = 'meal_product_id'
           AND model = 'pos.config'
        """
    )
    _logger.info("his_meal_management: pos_config.meal_product_id dropped.")
