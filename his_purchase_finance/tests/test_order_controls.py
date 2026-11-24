# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .test_bill_check import TestBillCheck


@tagged("post_install", "-at_install")
class TestOrderControls(TestBillCheck):
    """Devis joint, tableau comparatif, commande confirmee verrouillee, avoir du,
    cloture du dossier (procedure 3.1, 3.2, 5, 8.4.3, 9.3)."""

    # ------------------------------------------------------------------
    # Devis joint et tableau comparatif
    # ------------------------------------------------------------------

    def test_send_needs_quote_file(self):
        order = self._offer()
        with self.assertRaisesRegex(UserError, "quote"):
            self._send(order, quote=False)
        self._attach(order, "offre.pdf")
        self._send(order, quote=False)
        self.assertTrue(order.his_sent_to_finance_on)

    def test_rfq_report_not_a_quote(self):
        order = self._offer()
        self._attach(order, "Request for Quotation - %s.pdf" % order.name)
        with self.assertRaises(UserError):
            self._send(order, quote=False)

    def test_comparison_posted(self):
        order = self._offer(price=75000)
        self._alternative(order, self.supplier_b, 76000)
        self._alternative(order, self.supplier_c, 77000)
        self._send(order, criterion="lowest_price", note="")
        bodies = "".join(order.message_ids.mapped("body"))
        self.assertIn("<table", bodies)
        for name in ("Supplier A", "Supplier B", "Supplier C"):
            self.assertIn(name, bodies)

    # ------------------------------------------------------------------
    # Commande confirmee : seule la Finance la change
    # ------------------------------------------------------------------

    def test_buyer_cannot_change_confirmed(self):
        order = self._confirmed()
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            order.order_line.with_user(self.officer).product_qty = 5
        with self.assertRaises(UserError):
            order.with_user(self.officer).button_cancel()
        with self.assertRaises(UserError):
            order.with_user(self.officer).payment_term_id = self.env.ref("account.account_payment_term_30days")
        order.order_line.with_user(self.finance).product_qty = 3
        self.assertEqual(order.order_line.product_qty, 3)

    def test_receipt_and_service_after_lock(self):
        order = self._confirmed()
        storekeeper = new_test_user(self.env, login="his_storekeeper_lock", groups="stock.group_stock_user")
        picking = order.picking_ids.with_user(storekeeper)
        picking.move_ids.quantity = 2
        picking.button_validate()
        self.assertEqual(order.order_line.qty_received, 2)

    def test_down_payment_by_buyer(self):
        order = self._confirmed()
        bill = self.env["account.move"].with_user(self.finance).create(
            {
                "move_type": "in_invoice",
                "partner_id": order.partner_id.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [(0, 0, {"name": "Advance 30%", "quantity": 1, "price_unit": 5400})],
            }
        )
        line = bill.invoice_line_ids
        self.env.invalidate_all()
        wizard = (
            self.env["bill.to.po.wizard"]
            .with_user(self.officer)
            .with_context(active_ids=[-line.id])
            .create({"purchase_order_id": order.id})
        )
        wizard.action_add_downpayment()
        self.assertTrue(order.order_line.filtered("is_downpayment"))
        bill.action_post()
        self.assertEqual(bill.his_check_state, "reserve")
        self.assertIn("Down payment", bill.his_check_reason)

    # ------------------------------------------------------------------
    # Avoir du apres retour
    # ------------------------------------------------------------------

    def _return(self, order, qty):
        picking = order.picking_ids.filtered(lambda p: p.state == "done")
        wizard = (
            self.env["stock.return.picking"]
            .with_context(active_id=picking.id, active_ids=picking.ids, active_model="stock.picking")
            .create({})
        )
        wizard.product_return_moves.quantity = qty
        res = wizard.action_create_returns()
        back = self.env["stock.picking"].browse(res["res_id"])
        back.move_ids.quantity = qty
        back.button_validate()

    def test_credit_note_due(self):
        order = self._received_order()
        self._bill(order)
        self._return(order, 1)
        line = order.order_line
        self.assertEqual(line.qty_received, 1)
        self.assertEqual(line.his_qty_to_refund, 1)
        self.assertEqual(order.his_amount_to_refund, line.price_unit)
        due = self.env["purchase.order"].search([("his_amount_to_refund", ">", 0)])
        self.assertIn(order, due)

    # ------------------------------------------------------------------
    # Cloture du dossier
    # ------------------------------------------------------------------

    def _rate_both(self, order):
        Rating = self.env["his.supplier.rating"]
        Rating.with_user(self.officer).create(
            {
                "order_id": order.id,
                **{
                    f: 4
                    for f in (
                        "purchase_delay",
                        "purchase_quality",
                        "purchase_compliance",
                        "purchase_quantity",
                        "purchase_responsiveness",
                        "purchase_warranty",
                        "purchase_price",
                    )
                },
            }
        )
        Rating.with_user(self.finance).create(
            {
                "order_id": order.id,
                **{
                    f: 4
                    for f in (
                        "finance_admin",
                        "finance_invoicing",
                        "finance_bank",
                        "finance_payment_terms",
                        "finance_anomalies",
                    )
                },
            }
        )

    def test_close_file(self):
        order = self._received_order()
        bill = self._bill(order)
        with self.assertRaisesRegex(UserError, "paid"):
            order.with_user(self.finance).action_his_close_file()
        self._register(bill)._create_payments()
        self.assertIn(bill.payment_state, ("paid", "in_payment"))
        with self.assertRaisesRegex(UserError, "rat"):
            order.with_user(self.finance).action_his_close_file()
        self._rate_both(order)
        self.assertTrue(order.his_ready_to_close)
        self.assertIn(order, self.env["purchase.order"].search([("his_ready_to_close", "=", True)]))
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            order.with_user(self.officer).action_his_close_file()
        order.with_user(self.finance).action_his_close_file()
        self.assertTrue(order.his_closed_on)
        self.assertTrue(order.locked)

    def test_close_blocked_by_open_anomaly(self):
        order = self._received_order()
        self._register(self._bill(order))._create_payments()
        self._rate_both(order)
        self.env["his.purchase.anomaly"].with_user(self.officer)._his_declare(order, "damage", "Dented")
        with self.assertRaisesRegex(UserError, "ANO/"):
            order.with_user(self.finance).action_his_close_file()
