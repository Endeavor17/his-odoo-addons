from . import models
from . import wizard

# There was a post_init_hook here that pointed the Restaurant till at the
# student meal, because a meal was a single product named on one pos.config.
# A meal is now any product carrying a meal_credit_cost, so every till serves
# every meal with nothing to configure - which is also what finally lets the
# Cafeteria serve one. Nothing left to wire at install, and no reference to
# his_stock_mdm anywhere in this module.
