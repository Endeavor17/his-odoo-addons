# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models
from odoo.exceptions import UserError

from .common import CASH_VAT_LIMIT


class AccountPayment(models.Model):
    _inherit = "account.payment"

    his_bank_reference = fields.Char(string="Cheque or Bank Reference", copy=False)

    def _his_is_supplier_payment(self):
        self.ensure_one()
        return self.payment_type == "outbound" and self.partner_type == "supplier"

    def action_post(self):
        proof = self.env.context.get("his_payment_proof")
        Attachment = self.env["ir.attachment"]
        for payment in self.filtered(lambda p: p._his_is_supplier_payment()):
            # Procedure 8.1 : on ne paie qu'un fournisseur au dossier valide.
            supplier = payment.partner_id.commercial_partner_id
            # decret 15-153 : un paiement saisi hors de la facture n'y echappe pas
            company_amount = payment.currency_id._convert(
                payment.amount, payment.company_currency_id, payment.company_id, payment.date or fields.Date.today()
            )
            if (
                payment.journal_id.type == "cash"
                and payment.company_currency_id.compare_amounts(company_amount, CASH_VAT_LIMIT) >= 0
            ):
                raise UserError(
                    _(
                        "A supplier payment of 1,000,000 DA or more goes by cheque or bank transfer, "
                        "not in cash (executive decree 15-153)."
                    )
                )
            if payment.company_id.his_finance_confirms and supplier and supplier.his_supplier_status != "validated":
                raise UserError(
                    _(
                        "The supplier file of %(supplier)s is not validated by Finance: it cannot be paid.",
                        supplier=supplier.name,
                    )
                )
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
