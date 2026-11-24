# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_bill_check import TestBillCheck
from .test_service_done import TestServiceDone


@tagged("post_install", "-at_install")
class TestAnomaly(TestBillCheck):
    """Procedure 6.4 : declaree, solution de l'acheteur, validee puis close par la Finance."""

    # Les tests du rapprochement ne se rejouent pas ici : seuls ses outils servent.

    def _declare(self, order, user=None, kind="shortage", description="1 toner missing"):
        return self.env["his.purchase.anomaly"].with_user(user or self.officer)._his_declare(order, kind, description)

    def _todo(self, anomaly):
        return anomaly.sudo().activity_ids.user_id

    def test_circuit(self):
        order = self._confirmed()
        buyer = order.user_id
        self.assertTrue(buyer)
        anomaly = self._declare(order)
        self.assertEqual(anomaly.state, "declared")
        self.assertTrue(anomaly.name.startswith("ANO/"))
        self.assertIn(buyer, self._todo(anomaly))
        anomaly.with_user(self.officer).write(
            {"solution": "credit_note", "solution_note": "Supplier sends a credit note"}
        )
        anomaly.with_user(self.officer).action_propose()
        self.assertEqual(anomaly.state, "proposed")
        self.assertIn(self.finance, self._todo(anomaly))
        anomaly.with_user(self.finance).write({"finance_note": "No tax impact."})
        anomaly.with_user(self.finance).action_approve()
        self.assertEqual(anomaly.state, "approved")
        self.assertIn(buyer, self._todo(anomaly))
        anomaly.with_user(self.officer).action_execute()
        self.assertEqual(anomaly.state, "executed")
        self.assertIn(self.finance, self._todo(anomaly))
        anomaly.with_user(self.finance).action_close()
        self.assertEqual(anomaly.state, "closed")
        self.assertFalse(self._todo(anomaly))

    def test_wrong_roles(self):
        anomaly = self._declare(self._confirmed())
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            anomaly.with_user(self.officer).action_propose()  # pas de solution
        anomaly.with_user(self.officer).solution = "return"
        anomaly.with_user(self.officer).action_propose()
        with self.assertRaises(AccessError):
            anomaly.with_user(self.officer).action_approve()
        with self.assertRaises(UserError):
            anomaly.with_user(self.finance).action_close()  # pas encore executee

    def test_open_anomaly_holds_bill(self):
        order = self._received_order()
        bill = self._bill(order)
        self.assertEqual(bill.his_check_state, "validated")
        anomaly = self._declare(order, kind="damage", description="Box crushed")
        self.assertEqual(bill.his_check_state, "reserve")
        self.assertIn(anomaly.name, bill.his_check_reason)
        self.assertEqual(bill.payment_state, "blocked")
        anomaly.sudo().write({"state": "executed", "solution": "replacement"})
        anomaly.with_user(self.finance).action_close()
        self.assertEqual(bill.his_check_state, "validated")
        self.assertTrue(bill.his_first_check_clean)

    def test_cancel_needs_note_and_releases(self):
        order = self._received_order()
        bill = self._bill(order)
        anomaly = self._declare(order)
        with self.assertRaises(UserError):
            anomaly.with_user(self.finance).action_cancel()
        anomaly.with_user(self.finance).write({"finance_note": "Declared by mistake, the toner was there."})
        anomaly.with_user(self.finance).action_cancel()
        self.assertEqual(anomaly.state, "cancelled")
        self.assertEqual(bill.his_check_state, "validated")

    def test_outsider_cannot_declare(self):
        order = self._confirmed()
        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            self._declare(order, user=self.outsider)

    def test_smart_button_count(self):
        order = self._confirmed()
        self._declare(order)
        self._declare(order, kind="damage", description="Dented")
        self.assertEqual(order.his_anomaly_count, 2)


@tagged("post_install", "-at_install")
class TestAnomalyRequester(TestServiceDone):
    """Le demandeur ne lit pas les commandes : il declare depuis sa demande."""

    def test_requester_declares_from_request(self):
        order, request = self._service_order()
        action = request.with_user(self.requester).action_open_his_anomaly()
        wizard = (
            self.env["his.anomaly.declare"]
            .with_user(self.requester)
            .with_context(action["context"])
            .create({"kind": "damage", "description": "Screen cracked on delivery"})
        )
        self.assertEqual(wizard.order_ref, str(order.id))
        wizard.action_declare()
        anomaly = self.env["his.purchase.anomaly"].with_user(self.requester).search([])
        self.assertEqual(anomaly.order_id, order)
        self.assertEqual(anomaly.declared_by_id, self.requester)
        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            order.with_user(self.requester).read(["name"])

    def test_service_not_compliant(self):
        order, request = self._service_order()
        action = request.with_user(self.requester).action_open_service_done()
        wizard = (
            self.env["his.service.done"]
            .with_user(self.requester)
            .with_context(action["context"])
            .create({"period": "12 November 2026", "compliant": False, "note": "The printer still jams."})
        )
        wizard.action_confirm()
        self.assertFalse(order.his_service_done_on)
        anomaly = self.env["his.purchase.anomaly"].sudo().search([("order_id", "=", order.id)])
        self.assertEqual(anomaly.kind, "service")
        self.assertIn("still jams", anomaly.description)

    def test_not_compliant_needs_note(self):
        _order, request = self._service_order()
        action = request.with_user(self.requester).action_open_service_done()
        wizard = (
            self.env["his.service.done"]
            .with_user(self.requester)
            .with_context(action["context"])
            .create({"period": "12 November 2026", "compliant": False})
        )
        with self.assertRaises(UserError):
            wizard.action_confirm()
