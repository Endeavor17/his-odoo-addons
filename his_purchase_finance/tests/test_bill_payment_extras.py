# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_bill_check import TestBillCheck


@tagged("post_install", "-at_install")
class TestBillPaymentExtras(TestBillCheck):
    """Original papier (7.3), TVA non deductible en especes (8.2), reference du paiement (8.3)."""

    def _journal(self, journal_type):
        return self.env["account.journal"].search(
            [("type", "=", journal_type), ("company_id", "=", self.company.id)], limit=1
        )

    def test_original_default_missing_and_filter(self):
        bill = self._bill(self._received_order())
        self.assertEqual(bill.his_original_state, "missing")
        missing = self.env["account.move"].search([("his_original_state", "=", "missing")])
        self.assertIn(bill, missing)
        bill.with_user(self.finance).write(
            {"his_original_state": "compliant", "his_original_holder_id": self.finance.id}
        )
        self.assertEqual(bill.his_original_state, "compliant")

    def test_cash_warning(self):
        order = self._offer(price=500000)  # 2 x 500 000 HT = 1 190 000 TTC
        self._confirmed(order)
        self._receive(order)
        bill = self._bill(order)
        self.assertGreater(abs(bill.amount_total_signed), 1_000_000)
        bank = self._register(bill, journal_id=self._journal("bank").id)
        self.assertFalse(bank.his_cash_vat_warning)
        cash = self._register(bill, journal_id=self._journal("cash").id, his_bank_reference=False)
        self.assertIn("not deductible", cash.his_cash_vat_warning)
        cash._create_payments()
        self.assertIn("not deductible", "".join(bill.message_ids.mapped("body")))

    def test_small_cash_payment_no_warning(self):
        bill = self._bill(self._received_order())  # 2 x 9 000 HT
        cash = self._register(bill, journal_id=self._journal("cash").id, his_bank_reference=False)
        self.assertFalse(cash.his_cash_vat_warning)

    def test_bank_reference_required(self):
        bill = self._bill(self._received_order())
        with self.assertRaisesRegex(UserError, "reference"):
            self._register(bill, journal_id=self._journal("bank").id, his_bank_reference=False)._create_payments()
        self._register(bill, journal_id=self._journal("bank").id, his_bank_reference="CHQ 004512")._create_payments()
        payment = self.env["account.payment"].search(
            [("partner_id", "=", bill.partner_id.id)], order="id desc", limit=1
        )
        self.assertEqual(payment.his_bank_reference, "CHQ 004512")
