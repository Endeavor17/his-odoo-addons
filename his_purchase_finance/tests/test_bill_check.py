# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import HisFinanceCase

PROOF = base64.b64encode(b"virement 0042")


@tagged("post_install", "-at_install")
class TestBillCheck(HisFinanceCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.repair = cls.env["product.product"].create(
            {"name": "Printer repair", "type": "service", "purchase_ok": True}
        )

    # ------------------------------------------------------------------

    def _receive(self, order, qty=None):
        picking = order.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty if qty is None else qty
        res = picking.button_validate()
        if isinstance(res, dict) and res.get("res_model") == "stock.backorder.confirmation":
            self.env[res["res_model"]].with_context(res["context"]).create({}).process()

    def _bill(self, order, qty=None, price=None, uom=None, move_type="in_invoice", extra_line=False, post=True):
        pol = order.order_line[0]
        lines = [
            (
                0,
                0,
                {
                    "product_id": pol.product_id.id,
                    "quantity": pol.product_qty if qty is None else qty,
                    "price_unit": pol.price_unit if price is None else price,
                    "product_uom_id": (uom or pol.product_uom_id).id,
                    "tax_ids": [(6, 0, pol.tax_ids.ids)],
                    "purchase_line_id": pol.id,
                },
            )
        ]
        if extra_line:
            lines.append((0, 0, {"name": "Transport", "quantity": 1, "price_unit": 500, "tax_ids": [(5, 0, 0)]}))
        bill = (
            self.env["account.move"]
            .with_user(self.finance)
            .create(
                {
                    "move_type": move_type,
                    "partner_id": order.partner_id.id,
                    "invoice_date": fields.Date.today(),
                    "invoice_line_ids": lines,
                }
            )
        )
        if post:
            bill.action_post()
        return bill

    def _register(self, bill, proof=PROOF, **vals):
        vals.setdefault("his_bank_reference", "VIR 2026-0042")
        return (
            self.env["account.payment.register"]
            .with_user(self.finance)
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create({"his_proof": proof, "his_proof_name": "virement.pdf", **vals})
        )

    def _received_order(self):
        order = self._confirmed()
        self._receive(order)
        return order

    # ------------------------------------------------------------------

    def test_clean_bill_validated(self):
        bill = self._bill(self._received_order())
        self.assertEqual(bill.his_check_state, "validated")
        self.assertTrue(bill.his_first_check_clean)
        self.assertNotEqual(bill.payment_state, "blocked")

    def test_price_mismatch_held(self):
        bill = self._bill(self._received_order(), price=9100)
        self.assertEqual(bill.his_check_state, "reserve")
        self.assertIn("ordered at", bill.his_check_reason)
        self.assertEqual(bill.payment_state, "blocked")
        self.assertFalse(bill.his_first_check_clean)

    def test_tax_mismatch_held(self):
        order = self._received_order()
        bill = self._bill(order, post=False)
        other_tax = self.env["account.tax"].create({"name": "VAT 9 test", "amount": 9, "type_tax_use": "purchase"})
        bill.invoice_line_ids.tax_ids = other_tax
        bill.action_post()
        self.assertEqual(bill.his_check_state, "reserve")
        self.assertIn("taxes differ", bill.his_check_reason)

    def test_over_receipt_held(self):
        order = self._confirmed()
        bill = self._bill(order)  # rien recu
        self.assertEqual(bill.his_check_state, "reserve")
        self.assertIn("received", bill.his_check_reason)

    def test_unlinked_line_held(self):
        bill = self._bill(self._received_order(), extra_line=True)
        self.assertEqual(bill.his_check_state, "reserve")
        self.assertIn("not on the purchase order", bill.his_check_reason)

    def _bill_without_order(self, move_type="in_invoice", post=True):
        bill = (
            self.env["account.move"]
            .with_user(self.finance)
            .create(
                {
                    "move_type": move_type,
                    "partner_id": self.supplier_a.id,
                    "invoice_date": fields.Date.today(),
                    "invoice_line_ids": [(0, 0, {"name": "Rent", "quantity": 1, "price_unit": 1000})],
                }
            )
        )
        if post:
            bill.action_post()
        return bill

    def test_bill_without_order_on_hold(self):
        bill = self._bill_without_order()
        self.assertEqual(bill.his_check_state, "reserve")
        self.assertIn("No purchase order", bill.his_check_reason)
        self.assertEqual(bill.payment_state, "blocked")
        bill.with_user(self.finance)._his_decide("release", "Monthly rent, lease 2026")
        self.assertEqual(bill.his_check_state, "validated")
        self.assertNotEqual(bill.payment_state, "blocked")

    def test_refund_without_order_not_checked(self):
        refund = self._bill_without_order(move_type="in_refund")
        self.assertFalse(refund.his_check_state)

    def test_switch_off_bill_without_order_free(self):
        self.company.his_finance_confirms = False
        bill = self._bill_without_order()
        self.assertFalse(bill.his_check_state)

    def test_down_payment_on_hold(self):
        order = self._confirmed()
        pol = (
            self.env["purchase.order.line"]
            .sudo()
            .create(
                {
                    "order_id": order.id,
                    "name": "Down payment",
                    "is_downpayment": True,
                    "product_qty": 0,
                    "price_unit": 3000,
                }
            )
        )
        bill = (
            self.env["account.move"]
            .with_user(self.finance)
            .create(
                {
                    "move_type": "in_invoice",
                    "partner_id": order.partner_id.id,
                    "invoice_date": fields.Date.today(),
                    "invoice_line_ids": [
                        (0, 0, {"name": "Down payment", "quantity": 1, "price_unit": 3000, "purchase_line_id": pol.id})
                    ],
                }
            )
        )
        bill.action_post()
        self.assertEqual(bill.his_check_state, "reserve")
        self.assertIn("Down payment", bill.his_check_reason)
        self.assertNotIn("received", bill.his_check_reason)

    def test_bill_other_supplier(self):
        order = self._received_order()
        bill = self._bill(order, post=False)
        bill.partner_id = self.supplier_b
        bill.action_post()
        self.assertEqual(bill.his_check_state, "reserve")
        self.assertIn("Supplier B", bill.his_check_reason)

    def test_bill_other_payment_terms(self):
        order = self._offer()
        order.payment_term_id = self.env.ref("account.account_payment_term_30days")
        order = self._confirmed(order)
        self._receive(order)
        bill = self._bill(order, post=False)
        bill.invoice_payment_term_id = self.env.ref("account.account_payment_term_immediate")
        bill.action_post()
        self.assertEqual(bill.his_check_state, "reserve")
        self.assertIn("payment terms", bill.his_check_reason)
        same = self._bill(order, post=False, qty=0)
        same.invoice_payment_term_id = order.payment_term_id
        self.assertNotIn("payment terms", "\n".join(same._his_mismatches()))

    def test_held_bill_payment_refused(self):
        bill = self._bill(self._received_order(), price=9100)
        with self.assertRaises(UserError):
            self._register(bill)._create_payments()
        with self.assertRaises(UserError):
            bill.action_register_payment()

    def test_release_needs_reason_and_unblocks(self):
        bill = self._bill(self._received_order(), price=9100)
        with self.assertRaises(UserError):
            bill.with_user(self.officer)._his_decide("release", "x")
        action = bill.with_user(self.finance).action_open_release()
        self.env["his.bill.decision"].with_user(self.finance).with_context(action["context"]).create(
            {"reason": "Price increase agreed by phone."}
        ).action_apply()
        self.assertEqual(bill.his_check_state, "validated")
        self.assertNotEqual(bill.payment_state, "blocked")
        self.assertIn("Price increase agreed by phone.", bill.his_check_reason)
        self._register(bill)._create_payments()
        self.assertIn(bill.payment_state, ("paid", "in_payment"))

    def test_refuse_keeps_payment_blocked(self):
        bill = self._bill(self._received_order(), price=9100)
        bill.with_user(self.finance)._his_decide("refuse", "Duplicate of BILL/0012.")
        self.assertEqual(bill.his_check_state, "refused")
        self.assertEqual(bill.payment_state, "blocked")

    def test_check_again_after_receipt(self):
        order = self._confirmed()
        bill = self._bill(order)
        self.assertEqual(bill.his_check_state, "reserve")
        self._receive(order)
        bill.with_user(self.finance).action_his_check_again()
        self.assertEqual(bill.his_check_state, "validated")
        self.assertFalse(bill.his_first_check_clean, "le premier controle reste celui qui compte")

    def test_service_not_certified_held_then_rechecked(self):
        request = self._approved_request(
            "usual", lines=[{"product_id": self.repair.id, "product_qty": 1, "estimated_price_unit": 20000}]
        )
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 20000
        self._confirmed(order)
        bill = self._bill(order)
        self.assertEqual(bill.his_check_state, "reserve")
        self.assertIn("not been confirmed done", bill.his_check_reason)
        self.env["his.service.done"].with_user(self.requester).with_context(his_order_ids=order.ids).create(
            {"period": "November 2026"}
        ).action_confirm()
        self.assertEqual(bill.his_check_state, "validated", bill.his_check_reason)

    def test_uom_cartons(self):
        dozen = self.env.ref("uom.product_uom_dozen")
        dozen.active = True
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.supplier_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {"product_id": self.toner.id, "product_qty": 1, "product_uom_id": dozen.id, "price_unit": 1200},
                    )
                ],
            }
        )
        self._confirmed(order)
        self._receive(order)
        bill = self._bill(order, qty=12, price=100, uom=self.env.ref("uom.product_uom_unit"))
        self.assertEqual(bill.his_check_state, "validated", bill.his_check_reason)

    def test_partial_receipts_two_bills(self):
        order = self._confirmed()  # 2 toners
        self._receive(order, qty=1)
        first = self._bill(order, qty=1)
        self.assertEqual(first.his_check_state, "validated")
        second = self._bill(order, qty=1)
        self.assertEqual(second.his_check_state, "reserve", "1 recu, 2 factures")
        self._receive(order)
        second.with_user(self.finance).action_his_check_again()
        self.assertEqual(second.his_check_state, "validated")

    def test_refund_not_held_for_quantity(self):
        order = self._received_order()
        self._bill(order)
        refund = self._bill(order, qty=1, move_type="in_refund")
        self.assertEqual(refund.his_check_state, "validated")

    def test_reset_to_draft_waits(self):
        bill = self._bill(self._received_order(), price=9100)
        bill.button_draft()
        self.assertEqual(bill.his_check_state, "waiting")
        bill.invoice_line_ids.price_unit = 9000
        bill.action_post()
        self.assertEqual(bill.his_check_state, "validated")

    def test_proof_required_in_wizard(self):
        bill = self._bill(self._received_order())
        with self.assertRaises(UserError):
            self._register(bill, proof=False)._create_payments()
        payments = self._register(bill)._create_payments()
        attachment = self.env["ir.attachment"].search(
            [("res_model", "=", "account.payment"), ("res_id", "in", payments.ids)]
        )
        self.assertEqual(attachment.name, "virement.pdf")

    def test_manual_supplier_payment_needs_attachment(self):
        journal = self.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", self.company.id)], limit=1
        )
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.supplier_a.id,
                "amount": 1000,
                "journal_id": journal.id,
            }
        )
        with self.assertRaises(UserError):
            payment.action_post()
        self.env["ir.attachment"].create(
            {"name": "receipt.pdf", "datas": PROOF, "res_model": "account.payment", "res_id": payment.id}
        )
        payment.action_post()
        self.assertNotEqual(payment.state, "draft")
