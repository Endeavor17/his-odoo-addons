# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import HisFinanceCase


@tagged("post_install", "-at_install")
class TestServiceDone(HisFinanceCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.repair = cls.env["product.product"].create(
            {"name": "Printer repair", "type": "service", "purchase_ok": True}
        )

    def _service_order(self):
        request = self._approved_request(
            "usual", lines=[{"product_id": self.repair.id, "product_qty": 1, "estimated_price_unit": 20000}]
        )
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 20000
        return self._confirmed(order), request

    def _certify(self, user, order_ids, period="12 November 2026", note=""):
        wizard = (
            self.env["his.service.done"]
            .with_user(user)
            .with_context(his_order_ids=order_ids)
            .create({"period": period, "note": note})
        )
        return wizard.action_confirm()

    def test_requester_certifies_service(self):
        order, request = self._service_order()
        self.assertTrue(request.with_user(self.requester).his_service_pending)
        action = request.with_user(self.requester).action_open_service_done()
        self._certify(self.requester, action["context"]["his_order_ids"], note="Toner smudge remains.")
        self.assertEqual(order.his_service_done_by_id, self.requester)
        self.assertEqual(order.order_line.qty_received, 1)
        self.assertEqual(order.his_service_note, "Toner smudge remains.")
        request.invalidate_recordset()
        self.assertFalse(request.his_service_pending)

    def test_outsider_cannot_certify(self):
        order, _request = self._service_order()
        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            self._certify(self.outsider, order.ids)
        with self.assertRaises(AccessError):
            self._certify(self.manager, order.ids)

    def test_manager_certifies_order_without_request(self):
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.supplier_a.id,
                "order_line": [(0, 0, {"product_id": self.repair.id, "product_qty": 1, "price_unit": 5000})],
            }
        )
        self._confirmed(order)
        self._certify(self.manager, order.ids)
        self.assertEqual(order.his_service_done_by_id, self.manager)
