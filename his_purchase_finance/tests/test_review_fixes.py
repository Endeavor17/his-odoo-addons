# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Revue finale du 2026-11-22 : contournements par RPC et paiement d'une facture en reserve."""

import base64
from datetime import date

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import HisFinanceCase
from .test_bill_check import TestBillCheck


@tagged("post_install", "-at_install")
class TestReviewFixes(HisFinanceCase):
    # Critique 1 : confirmer sans la Finance par button_approve(force=True) ou write(state)
    def test_buyer_cannot_approve_or_write_state_on_rfq(self):
        order = self._offer()
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            order.with_user(self.officer).button_approve(force=True)
        with self.assertRaises(UserError):
            order.with_user(self.officer).with_context(his_confirming=True).button_approve()
        with self.assertRaises(UserError):
            order.with_user(self.officer).write({"state": "purchase"})
        self.assertEqual(order.state, "draft")

    # Critique 2 : champs « readonly » ecrits par RPC
    def test_protected_fields_not_writable_by_rpc(self):
        order = self._offer()
        self.env.invalidate_all()
        for vals in (
            {"his_sent_to_finance_on": fields.Datetime.now()},
            {"his_service_done_on": fields.Datetime.now()},
        ):
            with self.assertRaises(UserError):
                order.with_user(self.officer).write(vals)
        self._send(order)
        with self.assertRaises(UserError):
            order.with_user(self.officer).write({"his_sent_to_finance_on": False})
        with self.assertRaises(UserError):
            order.with_user(self.officer).with_context(his_choice_write=True).write({"his_choice_note": "changed"})

    def test_check_state_not_writable_by_rpc(self):
        clerk = self.env["res.users"].create(
            {
                "name": "Clerk",
                "login": "his_clerk",
                "group_ids": [(6, 0, self.env.ref("account.group_account_invoice").ids)],
            }
        )
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.supplier_a.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [(0, 0, {"name": "x", "quantity": 1, "price_unit": 10})],
            }
        )
        with self.assertRaises(UserError):
            bill.with_user(clerk).write({"his_check_state": "validated"})

    # Important 4 : complement autorise par le responsable achats
    def test_finance_confirms_authorised_top_up(self):
        request = self._approved_request("usual")
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.write({"price_unit": 9000})
        order.order_line.with_user(self.manager).product_qty = 3  # 2 demandes
        action = order.with_user(self.manager).action_his_send_to_finance()
        self.env["his.purchase.choice"].with_user(self.manager).with_context(action["context"]).create(
            {"order_id": order.id, "criterion": "quality", "note": "Spare toner."}
        ).action_confirm()
        order.with_user(self.finance).button_confirm()
        self.assertIn(order.state, ("to approve", "purchase"))

    # Important 5 : verrou pendant l'approbation
    def test_buyer_cannot_edit_order_waiting_approval(self):
        order = self._offer()
        self._send(order)
        order.with_user(self.finance).button_confirm()
        self.assertEqual(order.state, "to approve")
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            order.order_line.with_user(self.officer).price_unit = 1

    # Important 6 : contrat-cadre qui ne couvre pas la commande
    def test_unrelated_contract_does_not_skip_choice(self):
        agreement = self.env["purchase.requisition"].create(
            {
                "requisition_type": "blanket_order",
                "vendor_id": self.supplier_b.id,
                "date_start": date(2026, 9, 1),
                "date_end": date(2027, 8, 31),
                "line_ids": [(0, 0, {"product_id": self.tomatoes.id, "product_qty": 1200, "price_unit": 120})],
            }
        )
        agreement.action_confirm()
        order = self._offer()
        order.with_user(self.officer).requisition_id = agreement
        action = order.with_user(self.officer).action_his_send_to_finance()
        self.assertIsInstance(action, dict, "le contrat d'un autre fournisseur ne dispense pas du motif")
        self.assertFalse(order.his_sent_to_finance_on)


@tagged("post_install", "-at_install")
class TestHeldBillPaymentRoutes(TestBillCheck):
    # Critique 3 : payer une facture en reserve par un autre ecran
    def test_toggle_block_refused_on_held_bill(self):
        bill = self._bill(self._received_order(), price=9100)
        with self.assertRaises(UserError):
            bill.with_user(self.finance).action_toggle_block_payment()
        self.assertEqual(bill.payment_state, "blocked")

    def test_reconcile_held_bill_with_payment_refused(self):
        bill = self._bill(self._received_order(), price=9100)
        journal = self.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", self.company.id)], limit=1
        )
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.supplier_a.id,
                "amount": bill.amount_total,
                "journal_id": journal.id,
            }
        )
        self.env["ir.attachment"].create(
            {"name": "p.pdf", "datas": base64.b64encode(b"x"), "res_model": "account.payment", "res_id": payment.id}
        )
        payment.action_post()
        lines = (bill.line_ids | payment.move_id.line_ids).filtered(
            lambda line: line.account_id.account_type == "liability_payable" and not line.reconciled
        )
        with self.assertRaises(UserError):
            lines.reconcile()

    def test_credit_note_still_reconciles_with_held_bill(self):
        bill = self._bill(self._received_order(), price=9100)
        reversal = bill._reverse_moves([{"invoice_date": fields.Date.today()}], cancel=True)
        self.assertTrue(reversal)
        self.assertTrue(bill.currency_id.is_zero(bill.amount_residual), "l'avoir solde la facture en reserve")
