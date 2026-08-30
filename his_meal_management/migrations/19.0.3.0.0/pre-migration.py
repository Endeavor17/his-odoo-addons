"""Clear the wallet before the credit columns change shape.

Credits become decimal in this version, and a credit stops meaning "one meal":
it now means "one 600 DA meal", with the 300 DA meal costing half of one. Every
balance standing in the database was counted under the old meaning, and there is
no honest way to reinterpret it - a student holding 12 credits could have been
sold either tier.

The decision taken was to start clean rather than convert. This runs before the
ORM widens the integer columns to numeric, so there is nothing left to convert
by the time it does.

Order matters: a transaction points at the subscription that produced it.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("SELECT COUNT(*) FROM his_meal_transaction")
    transactions = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM his_meal_subscription")
    subscriptions = cr.fetchone()[0]

    # DELETE, not TRUNCATE: pos.order and his.meal.card carry ON DELETE SET NULL
    # references into these tables, and TRUNCATE would refuse rather than honour
    # them.
    cr.execute("DELETE FROM his_meal_transaction")
    cr.execute("DELETE FROM his_meal_subscription")

    _logger.info(
        "his_meal_management 19.0.3.0.0: cleared %s ledger line(s) and %s "
        "subscription(s). Balances restart at zero under the new credit scale.",
        transactions, subscriptions,
    )
