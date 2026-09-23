"""Sans la surcharge, ce test echoue : le coeur force l'envoi immediat du
courriel de facture (mail.mail.send / send_after_commit) dans la requete.
La surcharge le laisse en file pour le cron.
"""

from unittest.mock import patch

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestSendMailAsync(AccountTestInvoicingCommon):
    def test_invoice_mail_is_queued_not_force_sent(self):
        self.partner_a.email = "partner_a@example.com"
        move = self.init_invoice("out_invoice", partner=self.partner_a, amounts=[100], post=True)
        template = self.env.ref("account.email_template_edi_invoice")
        MailMail = type(self.env["mail.mail"])
        cron = self.env.ref("mail.ir_cron_mail_scheduler_action")
        Trigger = self.env["ir.cron.trigger"]
        triggers_before = Trigger.search_count([("cron_id", "=", cron.id)])

        with (
            patch.object(MailMail, "send", autospec=True) as send,
            patch.object(MailMail, "send_after_commit", autospec=True) as send_after_commit,
        ):
            self.env["account.move.send"]._send_mail(move, template, partner_ids=self.partner_a.ids)

        mail = self.env["mail.mail"].search([("res_id", "=", move.id), ("model", "=", "account.move")])
        self.assertEqual(mail.state, "outgoing", "le courriel doit etre en file")
        self.assertFalse(
            send.called or send_after_commit.called,
            "le courriel a ete envoye dans la requete au lieu d'etre depose en file",
        )
        self.assertGreater(
            Trigger.search_count([("cron_id", "=", cron.id)]),
            triggers_before,
            "le cron d'envoi doit etre reveille, sinon le courriel attend jusqu'a une heure",
        )


@tagged("post_install", "-at_install")
class TestPosInvoiceInBackground(AccountTestInvoicingCommon):
    """Une facture POS ne genere plus son PDF dans la requete de la caisse."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref("point_of_sale.group_pos_manager")
        cls.partner_a.write({"email": "partner_a@example.com", "invoice_sending_method": "email"})
        cls.product = cls.env["product.product"].create(
            {"name": "Repas", "available_in_pos": True, "list_price": 100, "taxes_id": False}
        )
        cls.cash = cls.env["pos.payment.method"].create(
            {
                "name": "Especes",
                "receivable_account_id": cls.company_data["default_account_receivable"].id,
                "journal_id": cls.company_data["default_journal_cash"].id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Caisse async",
                "payment_method_ids": [(6, 0, cls.cash.ids)],
                "invoice_journal_id": cls.company_data["default_journal_sale"].id,
            }
        )
        cls.config.open_ui()

    def test_invoice_pdf_and_mail_are_left_to_the_cron(self):
        cron = self.env.ref("account.ir_cron_account_move_send")
        Trigger = self.env["ir.cron.trigger"]
        triggers_before = Trigger.search_count([("cron_id", "=", cron.id)])
        order = self.env["pos.order"].create(
            {
                "session_id": self.config.current_session_id.id,
                "partner_id": self.partner_a.id,
                "lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "qty": 1,
                            "price_unit": 100,
                            "price_subtotal": 100,
                            "price_subtotal_incl": 100,
                        },
                    )
                ],
                "amount_total": 100,
                "amount_tax": 0,
                "amount_paid": 0,
                "amount_return": 0,
            }
        )
        self.env["pos.make.payment"].with_context(active_id=order.id).create(
            {"amount": 100, "payment_method_id": self.cash.id}
        ).check()

        with patch.object(type(self.env["account.move.send"]), "_generate_and_send_invoices", autospec=True) as gen:
            order.action_pos_order_invoice()
        invoice = order.account_move

        self.assertEqual(invoice.state, "posted")
        self.assertFalse(gen.called, "le PDF a ete genere dans la requete de la caisse")
        self.assertTrue(invoice.sending_data, "la facture n'a pas ete confiee au cron d'envoi")
        self.assertGreater(Trigger.search_count([("cron_id", "=", cron.id)]), triggers_before)

        # Ce que fait le cron (sans son commit) : PDF joint et courriel en file.
        self.env["account.move.send"]._generate_and_send_invoices(invoice, from_cron=True)
        self.assertTrue(invoice.invoice_pdf_report_id, "le cron n'a pas produit le PDF")
        self.assertFalse(invoice.sending_data)
        self.assertTrue(self.env["mail.mail"].search([("model", "=", "account.move"), ("res_id", "=", invoice.id)]))
