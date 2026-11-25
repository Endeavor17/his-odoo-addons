# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Loi de finances 2023, art. 23 (art. 30 CTCA) : au-dela, la TVA d'une facture
# reglee en especes n'est pas deductible.
CASH_VAT_LIMIT = 1_000_000


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    his_proof = fields.Binary(string="Payment Proof", help="Bank transfer order, cheque copy or signed receipt.")
    his_proof_name = fields.Char(string="Payment Proof Name")
    his_proof_required = fields.Boolean(compute="_compute_his_proof_required")
    his_bank_reference = fields.Char(string="Cheque or Bank Reference")
    his_reference_required = fields.Boolean(string="Reference Required", compute="_compute_his_proof_required")
    his_cash_vat_warning = fields.Char(string="Cash VAT Warning", compute="_compute_his_cash_vat_warning")

    def _his_big_bills(self):
        self.ensure_one()
        return self.line_ids.move_id.filtered(
            lambda m: (
                m.move_type == "in_invoice"
                and m.company_id.currency_id.compare_amounts(abs(m.amount_total_signed), CASH_VAT_LIMIT) > 0
            )
        )

    @api.depends("journal_id", "line_ids")
    def _compute_his_cash_vat_warning(self):
        for wizard in self:
            big = wizard.journal_id.type == "cash" and wizard._his_big_bills()
            wizard.his_cash_vat_warning = (
                _(
                    "VAT on %s is not deductible if paid in cash above 1,000,000 DA incl. tax "
                    "(Finance Act 2023, art. 23).",
                    ", ".join(big.mapped("name")),
                )
                if big
                else False
            )

    @api.depends("payment_type", "partner_type", "journal_id")
    def _compute_his_proof_required(self):
        for wizard in self:
            wizard.his_proof_required = wizard.payment_type == "outbound" and wizard.partner_type == "supplier"
            wizard.his_reference_required = wizard.his_proof_required and wizard.journal_id.type == "bank"

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
        if self.his_reference_required and not (self.his_bank_reference or "").strip():
            raise UserError(_("Give the cheque number or the bank transfer reference."))
        wizard = self
        if self.his_proof:
            wizard = self.with_context(his_payment_proof=(self.his_proof_name or _("Payment proof"), self.his_proof))
        payments = super(AccountPaymentRegister, wizard)._create_payments()
        if self.his_cash_vat_warning:
            for bill in self._his_big_bills():
                bill.message_post(body=self.his_cash_vat_warning)
        return payments

    def _create_payment_vals_from_wizard(self, batch_result):
        vals = super()._create_payment_vals_from_wizard(batch_result)
        vals["his_bank_reference"] = self.his_bank_reference
        return vals

    def _create_payment_vals_from_batch(self, batch_result):
        vals = super()._create_payment_vals_from_batch(batch_result)
        vals["his_bank_reference"] = self.his_bank_reference
        return vals
