# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _his_is_supplier_payment(self):
        self.ensure_one()
        return self.payment_type == "outbound" and self.partner_type == "supplier"

    def action_post(self):
        # En Community, aucun moyen de paiement n'exige de compte approuve
        # (_get_method_codes_needing_bank_account vide) : on bloque nous-memes
        # tout virement fournisseur vers des coordonnees non validees.
        for payment in self:
            if payment._his_is_supplier_payment() and payment.partner_bank_id and not payment.partner_bank_id.allow_out_payment:
                raise UserError(
                    _(
                        "The bank account %(account)s of %(supplier)s has not been validated by Finance: "
                        "no payment can be sent to it.",
                        account=payment.partner_bank_id.display_name,
                        supplier=payment.partner_id.display_name,
                    )
                )
        return super().action_post()
