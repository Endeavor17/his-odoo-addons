# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _his_is_supplier_payment(self):
        self.ensure_one()
        return self.payment_type == "outbound" and self.partner_type == "supplier"

    def action_post(self):
        proof = self.env.context.get("his_payment_proof")
        Attachment = self.env["ir.attachment"]
        for payment in self.filtered(lambda p: p._his_is_supplier_payment()):
            # En Community, aucun moyen de paiement n'exige de compte approuve
            # (_get_method_codes_needing_bank_account vide) : on bloque nous-memes
            # tout virement fournisseur vers des coordonnees non validees.
            if payment.partner_bank_id and not payment.partner_bank_id.allow_out_payment:
                raise UserError(
                    _(
                        "The bank account %(account)s of %(supplier)s has not been validated by Finance: "
                        "no payment can be sent to it.",
                        account=payment.partner_bank_id.display_name,
                        supplier=payment.partner_id.display_name,
                    )
                )
            # « Paye » seulement avec la preuve jointe (procedure Finance, 8.3).
            if proof:
                Attachment.create(
                    {"name": proof[0], "datas": proof[1], "res_model": "account.payment", "res_id": payment.id}
                )
            if not Attachment.search_count([("res_model", "=", "account.payment"), ("res_id", "=", payment.id)]):
                raise UserError(_("Attach the payment proof to %s before posting it.", payment.display_name))
        return super().action_post()
