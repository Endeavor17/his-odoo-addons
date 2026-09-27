# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    def action_send_receipt(self, email, ticket_image, basic_image):
        # Copie du coeur (point_of_sale/models/pos_order.py) a une difference
        # pres : force_send=False. Le coeur envoie le ticket par SMTP dans la
        # requete de la caisse, et le ticket part desormais apres CHAQUE vente a
        # un client qui a un email (his_meal_management, receipt_screen.js). En
        # file, et le cron mail reveille, comme pour les factures.
        self.ensure_one()
        self.email = email
        mail_template = self.env.ref("point_of_sale.email_template_pos_receipt", raise_if_not_found=False)
        if not mail_template:
            raise UserError(
                _("The mail template with xmlid %s has been deleted.", "point_of_sale.email_template_pos_receipt")
            )
        mail_template.send_mail(
            self.id,
            force_send=False,
            email_values={
                "email_to": email,
                "attachment_ids": self._get_mail_attachments(self.name, ticket_image, basic_image),
            },
        )
        self.env.ref("mail.ir_cron_mail_scheduler_action")._trigger()

    def _generate_pos_order_invoice(self):
        # Le coeur finit par invoice._generate_and_send() : PDF (wkhtmltopdf,
        # 2,5 a 4,5 s) puis courriel, dans la requete de la caisse. Le coeur
        # prevoit generate_pdf=False pour ne pas bloquer la caisse (voir
        # l10n_sa_edi_pos) ; on s'en sert, et on confie PDF + courriel au cron
        # « Send invoices automatically », exactement comme un envoi par lot.
        cron = self.env.ref("account.ir_cron_account_move_send", raise_if_not_found=False)
        if not self.env.context.get("generate_pdf", True) or not (cron and cron.sudo().active):
            return super()._generate_pos_order_invoice()

        to_invoice = self.filtered(lambda order: not order.account_move)
        res = super(PosOrder, self.with_context(generate_pdf=False))._generate_pos_order_invoice()
        invoices = to_invoice.account_move.filtered(lambda move: move.state == "posted")
        if invoices:
            invoices.sudo().sending_data = {
                "author_user_id": self.env.user.id,
                "author_partner_id": self.env.user.partner_id.id,
            }
            # Planifie une fois par jour : le reveiller, sinon rien ne part.
            cron._trigger()
        return res
