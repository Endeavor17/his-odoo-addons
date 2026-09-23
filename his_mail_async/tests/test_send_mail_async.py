"""Sans la surcharge, ce test echoue : le coeur force l'envoi immediat et le
courriel passe de 'outgoing' a 'sent' (ou 'exception') avant que le test ne
lise son etat. La surcharge le laisse en file pour le cron.
"""
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestSendMailAsync(AccountTestInvoicingCommon):
    def test_invoice_mail_is_queued_not_force_sent(self):
        move = self.init_invoice("out_invoice", partner=self.partner_a, amounts=[100], post=True)
        template = self.env.ref("account.email_template_edi_invoice")

        self.env["account.move.send"]._send_mail(move, template)

        mail = self.env["mail.mail"].search(
            [("res_id", "=", move.id), ("model", "=", "account.move")],
            order="id desc",
            limit=1,
        )
        self.assertTrue(mail, "le message_post aurait du creer un mail.mail")
        self.assertEqual(
            mail.state,
            "outgoing",
            "le courriel a ete envoye tout de suite au lieu d'etre depose en file",
        )
