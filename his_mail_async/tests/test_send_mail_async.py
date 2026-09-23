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
