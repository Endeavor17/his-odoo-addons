# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged

from .common import HisPurchaseCase


@tagged("post_install", "-at_install")
class TestRequestEstimate(HisPurchaseCase):
    """Etape 1 de la procedure Finance : priorite, taxes estimees et TTC."""

    def test_tax_estimate_from_product_taxes(self):
        request = self._request(lines=[{"product_id": self.toner.id, "product_qty": 2, "estimated_price_unit": 1000}])
        self.assertEqual(request.line_ids.estimated_tax, 380)
        self.assertEqual(request.estimated_amount, 2000)
        self.assertEqual(request.estimated_tax, 380)
        self.assertEqual(request.estimated_amount_total, 2380)

    def test_no_product_no_tax(self):
        request = self._request(
            lines=[{"description": "Shelf for the archives", "product_qty": 1, "estimated_price_unit": 500}]
        )
        self.assertEqual(request.line_ids.estimated_tax, 0)
        self.assertEqual(request.estimated_amount_total, 500)

    def test_priority_default_and_tracked(self):
        request = self._request()
        self.assertEqual(request.priority, "0")
        request.with_user(self.requester).priority = "1"
        self.assertEqual(request.priority, "1")
        # Le suivi est ecrit au precommit, que la transaction de test ne joue pas.
        self.assertTrue(request._fields["priority"].tracking)
