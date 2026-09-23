# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class PosOrder(models.Model):
    _inherit = "pos.order"

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
