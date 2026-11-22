# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger
from psycopg2 import IntegrityError

from .common import HisFinanceCase

PURCHASE_FOURS = dict.fromkeys(
    [
        "purchase_delay",
        "purchase_quality",
        "purchase_compliance",
        "purchase_quantity",
        "purchase_responsiveness",
        "purchase_warranty",
        "purchase_price",
    ],
    4,
)
FINANCE_TWOS = dict.fromkeys(
    ["finance_admin", "finance_invoicing", "finance_bank", "finance_payment_terms", "finance_anomalies"], 2
)


@tagged("post_install", "-at_install")
class TestRating(HisFinanceCase):
    def _rate(self, user, order, marks):
        return self.env["his.supplier.rating"].with_user(user).create({"order_id": order.id, **marks})

    def test_score_average_and_label(self):
        first = self._confirmed()
        rating = self._rate(self.officer, first, PURCHASE_FOURS)
        self.assertEqual(rating.side, "purchase")
        self.assertEqual(rating.score, 4.0)
        self.assertEqual(self.supplier_a.his_rating_label, "satisfactory")
        second = self._confirmed()
        self._rate(self.finance, second, FINANCE_TWOS)
        self.supplier_a.invalidate_recordset()
        self.assertEqual(self.supplier_a.his_rating_score, 3.0)
        self.assertEqual(self.supplier_a.his_rating_label, "watch")

    def test_one_rating_per_side(self):
        order = self._confirmed()
        self._rate(self.officer, order, PURCHASE_FOURS)
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.cr.savepoint():
            self._rate(self.officer, order, PURCHASE_FOURS)

    def test_criteria_bounds(self):
        order = self._confirmed()
        with self.assertRaises(ValidationError):
            self._rate(self.officer, order, {**PURCHASE_FOURS, "purchase_price": 6})
        with self.assertRaises(ValidationError):
            self._rate(self.officer, order, {**PURCHASE_FOURS, "purchase_price": 0})

    def test_only_finance_rates_finance_side(self):
        order = self._confirmed()
        with self.assertRaises(AccessError):
            self._rate(self.officer, order, {"side": "finance", **FINANCE_TWOS})
