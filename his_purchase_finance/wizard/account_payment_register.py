# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    his_proof = fields.Binary(string="Payment Proof", help="Bank transfer order, cheque copy or signed receipt.")
    his_proof_name = fields.Char(string="Payment Proof Name")
    his_proof_required = fields.Boolean(compute="_compute_his_proof_required")

    @api.depends("payment_type", "partner_type")
    def _compute_his_proof_required(self):
        for wizard in self:
            wizard.his_proof_required = wizard.payment_type == "outbound" and wizard.partner_type == "supplier"

    def _create_payments(self):
        # Le coeur ne refuse une facture bloquee que depuis la facture : ici on
        # couvre aussi le chemin des ecritures comptables.
        held = self.line_ids.move_id.filtered(lambda m: m.his_check_state and m.his_check_state != "validated")
        if held:
            raise UserError(
                _("%s is held by the purchase order check: Finance must validate or release it first.", held[0].name)
            )
        if self.his_proof_required and not self.his_proof:
            raise UserError(_("Attach the payment proof before paying a supplier."))
        wizard = self
        if self.his_proof:
            wizard = self.with_context(his_payment_proof=(self.his_proof_name or _("Payment proof"), self.his_proof))
        return super(AccountPaymentRegister, wizard)._create_payments()
