# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Fiche de declaration et de suivi des ecarts de caisse (procedure §6 et §8).

Un ecart est passe en 476 a titre provisoire des qu'il est constate (cloture,
ouverture, versement, comptage). La fiche suit le circuit caissier ->
responsable -> Finance (-> Direction pour un ecart majeur) ; la Finance la
clot en passant l'ecriture 476 -> compte definitif, lettree avec la
provisoire. Rien n'est regularise automatiquement (§6.5).
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

# Ce que l'utilisateur peut ecrire lui-meme ; tout le reste passe par les
# actions (sudo apres controle du groupe).
EDITABLE = {"explanation", "manager_note", "finance_note"}


class HisCashDiscrepancy(models.Model):
    _name = "his.cash.discrepancy"
    _description = "Cash Discrepancy"
    _inherit = ["mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(readonly=True, copy=False, default="/")
    date = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    kind = fields.Selection(
        [("opening", "Opening"), ("closing", "Closing"), ("handover", "Hand Over"), ("count", "Cash Count")],
        required=True,
        readonly=True,
    )
    journal_id = fields.Many2one("account.journal", string="Cash Box", required=True, readonly=True)
    company_id = fields.Many2one(related="journal_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    session_id = fields.Many2one("pos.session", readonly=True)
    holder_id = fields.Many2one("res.users", string="Holder", readonly=True)
    holder_employee_id = fields.Many2one("hr.employee", string="Cashier", readonly=True)
    expected = fields.Monetary(readonly=True)
    counted = fields.Monetary(readonly=True)
    amount = fields.Monetary(compute="_compute_amount", store=True, help="Counted minus expected.")
    nature = fields.Selection(
        [("shortage", "Shortage"), ("surplus", "Surplus")], compute="_compute_amount", store=True
    )
    tier = fields.Selection(
        [("minor", "Minor"), ("significant", "Significant"), ("important", "Important"), ("major", "Major")],
        compute="_compute_amount",
        store=True,
    )
    explanation = fields.Text(help="Written explanation of the holder.", tracking=True)
    manager_note = fields.Text(string="Reviewer Observations", tracking=True)
    finance_decision = fields.Selection(
        [("accepted", "Accepted"), ("refused", "Refused"), ("investigating", "Further Investigation")],
        readonly=True,
        tracking=True,
    )
    finance_note = fields.Text(tracking=True)
    his_account_id = fields.Many2one("account.account", string="Regularisation Account", readonly=True)
    provisional_move_id = fields.Many2one("account.move", readonly=True)
    regularisation_move_id = fields.Many2one("account.move", readonly=True)
    closed_date = fields.Date(readonly=True)
    state = fields.Selection(
        [("to_review", "To Review"), ("finance", "Finance"), ("direction", "Direction"), ("closed", "Closed")],
        default="to_review",
        required=True,
        readonly=True,
        tracking=True,
    )

    @api.depends("expected", "counted", "company_id")
    def _compute_amount(self):
        for form in self:
            company = form.company_id or self.env.company
            form.amount = amount = form.counted - form.expected
            form.nature = "surplus" if amount > 0 else "shortage"
            size = abs(amount)
            if size <= company.his_gap_minor:
                form.tier = "minor"
            elif size <= company.his_gap_significant:
                form.tier = "significant"
            elif size <= company.his_gap_important:
                form.tier = "important"
            else:
                form.tier = "major"

    @api.model
    def his_open(self, kind, journal, expected, counted, provisional_move, explanation="", **links):
        """Ouvre la fiche d'un ecart deja passe en 476 ; rien s'il n'y a pas d'ecart."""
        currency = journal.currency_id or journal.company_id.currency_id
        if currency.is_zero(counted - expected):
            return self.browse()
        return (
            self.sudo()
            .create(
                {
                    "name": self.env["ir.sequence"].sudo().next_by_code("his.cash.discrepancy") or "/",
                    "kind": kind,
                    "journal_id": journal.id,
                    "expected": expected,
                    "counted": counted,
                    "provisional_move_id": provisional_move.id,
                    "explanation": explanation or False,
                    **links,
                }
            )
            .sudo(False)
        )

    def write(self, vals):
        if not self.env.su and set(vals) - EDITABLE - {f for f in vals if f.startswith(("message_", "activity_"))}:
            raise AccessError(_("Cash discrepancies change only through their buttons."))
        return super().write(vals)

    # -- qui fait quoi -----------------------------------------------------

    def _his_reviewer_group(self):
        """Revue : la Direction pour la caisse Finance, le Responsable Finance pour la caisse Direction."""
        self.ensure_one()
        return {
            "CFIN": "his_purchase.group_purchase_director",
            "CDIR": "his_pos_finance.group_finance_head",
        }.get(self.journal_id.code, "point_of_sale.group_pos_manager")

    def _his_decider_group(self):
        self.ensure_one()
        if self.tier in ("minor", "significant"):
            return "his_purchase_finance.group_finance"
        return "his_pos_finance.group_finance_head"

    def _his_check(self, state, group):
        if self.state != state:
            raise UserError(_("%(name)s is no longer at this step.", name=self.name))
        if not (self.env.su or self.env.user.has_group(group)):
            raise AccessError(_("You are not allowed to act on %(name)s at this step.", name=self.name))

    # -- circuit -----------------------------------------------------------

    def action_send_to_finance(self):
        for form in self:
            form._his_check("to_review", form._his_reviewer_group())
            if not (form.explanation and form.manager_note):
                raise UserError(_("Fill in the holder's explanation and your observations first."))
            form.sudo().state = "finance"

    def action_decide(self, decision, account=None, note=""):
        self.ensure_one()
        self._his_check("finance", self._his_decider_group())
        form = self.sudo()
        vals = {"finance_decision": decision}
        if note:
            vals["finance_note"] = note
        if decision == "refused":
            vals["state"] = "to_review"
        elif decision == "accepted":
            default = "757000" if form.amount > 0 else "657000"
            vals["his_account_id"] = (account or form._his_account(default)).id
            if form.tier == "major":
                vals["state"] = "direction"
        form.write(vals)
        if note:
            form.message_post(body=note)
        if decision == "accepted" and form.tier != "major":
            form._his_regularise()

    def action_direction_approve(self):
        for form in self:
            form._his_check("direction", "his_purchase.group_purchase_director")
            form.sudo()._his_regularise()

    def action_send_back(self, note=""):
        for form in self:
            form._his_check("direction", "his_purchase.group_purchase_director")
            form.sudo().write({"state": "finance", "finance_decision": False})
            if note:
                form.message_post(body=note)

    def action_open_decide(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "his.cash.discrepancy.decide",
            "view_mode": "form",
            "target": "new",
            "context": {"default_discrepancy_id": self.id},
        }

    # -- comptabilite --------------------------------------------------------

    def _his_account(self, code):
        return self.env["account.account"].search(
            [("code", "=", code), ("company_ids", "in", self.company_id.id)], limit=1
        )

    def _his_regularise(self):
        """476 -> compte retenu par la Finance, lettre avec l'ecriture provisoire."""
        self.ensure_one()
        ecart = self._his_account("476000")
        journal = self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company_id.id)], limit=1
        )
        amount = self.amount
        move = self.env["account.move"].create(
            {
                "journal_id": journal.id,
                "ref": self.name,
                "line_ids": [
                    (0, 0, {"account_id": ecart.id, "name": self.name, "debit": max(amount, 0), "credit": max(-amount, 0)}),
                    (
                        0,
                        0,
                        {
                            "account_id": self.his_account_id.id,
                            "name": self.name,
                            "debit": max(-amount, 0),
                            "credit": max(amount, 0),
                        },
                    ),
                ],
            }
        )
        move.action_post()
        (self.provisional_move_id.line_ids | move.line_ids).filtered(
            lambda line: line.account_id == ecart and not line.reconciled
        ).reconcile()
        self.write({"regularisation_move_id": move.id, "state": "closed", "closed_date": fields.Date.today()})
