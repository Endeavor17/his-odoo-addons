# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models
from odoo.exceptions import UserError


class PosSession(models.Model):
    _inherit = "pos.session"

    his_discrepancy_ids = fields.One2many("his.cash.discrepancy", "session_id", string="Cash Discrepancies")

    def try_cash_in_out(self, _type, amount, reason, partner_id, extras):
        # Procedure §4.1 : une caisse ne paie ni achat ni fournisseur ; les
        # especes n'en sortent que par un versement a la Finance.
        raise UserError(_("Cash only leaves a till by a hand over to Finance."))

    def _his_cash_gap(self):
        return self.config_id.cash_control and not self.currency_id.is_zero(self.cash_register_difference)

    def close_session_from_ui(self, bank_payment_method_diff_pairs=None):
        # Decision 1 : le caissier ferme lui-meme, mais explique tout ecart. Pas
        # dans _cannot_close_session : Odoo l'appelle aussi avant d'enregistrer
        # le comptage et la note (post_closing_cash_details).
        self.ensure_one()
        if self._his_cash_gap() and not (self.closing_notes or "").strip():
            return {"successful": False, "message": _("Explain the cash difference before closing."), "redirect": False}
        return super().close_session_from_ui(bank_payment_method_diff_pairs)

    def _post_statement_difference(self, amount):
        avant = self.statement_line_ids
        res = super()._post_statement_difference(amount)
        nouvelle = self.statement_line_ids - avant
        if nouvelle:
            # Odoo vient de passer l'ecart sur le compte d'ecart du journal
            # (476000, his_pos_finance.hooks) : c'est l'ecriture provisoire.
            self.env["his.cash.discrepancy"].his_open(
                "closing",
                self.cash_journal_id,
                # le solde attendu recalcule inclurait deja la ligne d'ecart
                expected=self.cash_register_balance_end_real - amount,
                counted=self.cash_register_balance_end_real,
                provisional_move=nouvelle.move_id,
                explanation=self.closing_notes or "",
                **self._his_links(),
            )
        return res

    def _set_opening_control_data(self, cashbox_value, notes):
        attendu = self.cash_register_balance_start
        res = super()._set_opening_control_data(cashbox_value, notes)
        ecart = cashbox_value - attendu
        if self.cash_journal_id and not self.currency_id.is_zero(ecart):
            # Odoo ne passe rien pour un ecart d'ouverture : il disparaitrait des
            # livres. On garde le report de la veille et la ligne porte l'ecart ;
            # sinon il serait compte deux fois dans le solde attendu.
            self.cash_register_balance_start = attendu
            journal = self.cash_journal_id
            ligne = (
                self.env["account.bank.statement.line"]
                .sudo()
                .with_context(no_retrieve_partner=True)
                .create(
                    {
                        "journal_id": journal.id,
                        "amount": ecart,
                        "date": fields.Date.context_today(self),
                        "pos_session_id": self.id,
                        "payment_ref": _("Opening difference (%s)", self.config_id.name),
                        "counterpart_account_id": (
                            journal.loss_account_id if ecart < 0 else journal.profit_account_id
                        ).id,
                    }
                )
            )
            self.env["his.cash.discrepancy"].his_open(
                "opening",
                journal,
                expected=attendu,
                counted=cashbox_value,
                provisional_move=ligne.move_id,
                explanation=notes or "",
                **self._his_links(),
            )
        return res

    def _his_links(self):
        return {
            "session_id": self.id,
            "holder_id": self.user_id.id,
            "holder_employee_id": self.employee_id.id,
        }
