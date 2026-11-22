# Part of Odoo. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, new_test_user, tagged

from .common import HisFinanceCase


@tagged("post_install", "-at_install")
class TestSupplierFile(HisFinanceCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Creer des contacts demande « Creation de contacts » (base), en plus d'Achats.
        cls.buyer = new_test_user(
            cls.env, login="his_buyer_pm", groups="purchase.group_purchase_user,base.group_partner_manager"
        )

    def test_new_supplier_is_waiting(self):
        partner = self.env["res.partner"].with_user(self.buyer).create({"name": "New Shop", "is_company": True})
        self.assertEqual(partner.his_supplier_status, "waiting")

    def test_only_finance_sets_status(self):
        partner = self.env["res.partner"].create({"name": "New Shop", "is_company": True})
        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            partner.with_user(self.buyer).his_supplier_status = "validated"
        with self.assertRaises(AccessError):
            self.env["res.partner"].with_user(self.buyer).create(
                {"name": "Sneaky SARL", "his_supplier_status": "validated"}
            )
        with Form(partner.with_user(self.finance)) as form:
            form.his_supplier_status = "validated"
        self.assertEqual(partner.his_supplier_status, "validated")
        # Ecrire la meme valeur (formulaire d'un acheteur) ne leve rien.
        partner.with_user(self.buyer).write({"his_supplier_status": "validated", "comment": "ok"})

    def test_buyer_and_finance_open_supplier_form(self):
        # Le formulaire contact lisait les cartes repas, reservees aux caissiers.
        for user in (self.officer, self.finance):
            self.env.invalidate_all()
            Form(self.supplier_a.with_user(user))

    def test_reason_required_for_reserve_and_refused(self):
        partner = self.env["res.partner"].create({"name": "New Shop", "is_company": True})
        for status in ("reserve", "refused"):
            with self.assertRaises(ValidationError):
                partner.with_user(self.finance).write({"his_supplier_status": status})
        partner.with_user(self.finance).write({"his_supplier_status": "reserve", "his_supplier_status_reason": "RIB missing"})
        self.assertEqual(partner.his_supplier_status, "reserve")

    def test_document_status(self):
        today = fields.Date.today()
        Doc = self.env["his.supplier.document"]
        base = {"partner_id": self.supplier_a.id, "doc_type": "rc"}
        self.assertEqual(Doc.create(base).status, "valid")
        self.assertEqual(Doc.create({**base, "expires_on": today - relativedelta(days=1)}).status, "expired")
        self.assertEqual(Doc.create({**base, "expires_on": today + relativedelta(days=10)}).status, "to_refresh")
        old_certificate = {**base, "doc_type": "tax_certificate", "received_on": today - relativedelta(months=7)}
        self.assertEqual(Doc.create(old_certificate).status, "to_refresh")
        self.assertEqual(Doc.create({**base, "non_compliant": True}).status, "non_compliant")

    def test_buyer_adds_documents_but_does_not_edit_them(self):
        doc = self.env["his.supplier.document"].with_user(self.officer).create(
            {"partner_id": self.supplier_a.id, "doc_type": "nif", "name": "000016001234567"}
        )
        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            doc.with_user(self.officer).non_compliant = False

    def test_blockers_read_on_commercial_partner(self):
        contact = self.env["res.partner"].create({"name": "Salesman", "parent_id": self.supplier_a.id})
        self.assertEqual(contact._his_supplier_blockers(), [])
        self.env["his.supplier.document"].create(
            {"partner_id": self.supplier_a.id, "doc_type": "rib", "expires_on": fields.Date.today() - relativedelta(days=1)}
        )
        self.assertEqual(len(contact._his_supplier_blockers()), 1)
        self.supplier_b.sudo().write({"his_supplier_status": "refused", "his_supplier_status_reason": "Fake RC"})
        self.assertIn("Refused", self.supplier_b._his_supplier_blockers()[0])

    def _supplier_payment(self, bank):
        journal = self.env["account.journal"].search([("type", "=", "bank"), ("company_id", "=", self.company.id)], limit=1)
        return self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.supplier_a.id,
                "amount": 1000,
                "journal_id": journal.id,
                "partner_bank_id": bank.id if bank else False,
            }
        )

    def test_payment_to_untrusted_bank_refused(self):
        bank = self.env["res.partner.bank"].create({"partner_id": self.supplier_a.id, "acc_number": "00799999000123456789"})
        self.assertFalse(bank.allow_out_payment)
        with self.assertRaises(UserError):
            self._supplier_payment(bank).action_post()
        bank.with_user(self.finance).allow_out_payment = True
        payment = self._supplier_payment(bank)
        payment.action_post()
        self.assertNotEqual(payment.state, "draft")
        cash = self._supplier_payment(False)
        cash.action_post()
        self.assertNotEqual(cash.state, "draft")
