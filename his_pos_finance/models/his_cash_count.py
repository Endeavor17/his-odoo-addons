# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Comptage quotidien des caisses Finance et Direction (procedure §6.4, decision 6).

Meme logique que les caisses de point de vente, sans en faire des caisses :
leurs paiements fournisseurs sont des paiements comptables, qu'une session de
point de vente ne compterait pas. L'attendu est le solde du compte 530 de la
caisse au moment du comptage.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class HisCashCount(models.Model):
    _name = "his.cash.count"
    _description = "Cash Box Count"
    _order = "date desc, id desc"

    journal_id = fields.Many2one(
        "account.journal", string="Cash Box", required=True, domain="[('code', 'in', ('CFIN', 'CDIR'))]"
    )
    company_id = fields.Many2one(related="journal_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    kind = fields.Selection([("opening", "Opening"), ("closing", "Closing")], required=True, default="opening")
    date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    expected = fields.Monetary(compute="_compute_expected", store=True, readonly=True)
    counted = fields.Monetary(required=True)
    difference = fields.Monetary(compute="_compute_difference", store=True)
    note = fields.Text()
    his_discrepancy_ids = fields.One2many("his.cash.discrepancy", "count_id", string="Cash Discrepancies")

    @api.depends("journal_id")
    def _compute_expected(self):
        # Fige a la creation : ne depend pas des ecritures postees ensuite.
        for count in self:
            account = count.journal_id.default_account_id
            lines = (
                self.env["account.move.line"]
                .sudo()
                .search(
                    [
                        ("account_id", "=", account.id),
                        ("parent_state", "=", "posted"),
                        ("company_id", "=", count.company_id.id),
                    ]
                )
            )
            count.expected = sum(lines.mapped("balance")) if account else 0.0

    @api.depends("expected", "counted")
    def _compute_difference(self):
        for count in self:
            count.difference = count.counted - count.expected

    @api.constrains("difference", "note")
    def _check_note(self):
        for count in self:
            if not count.currency_id.is_zero(count.difference) and not (count.note or "").strip():
                raise ValidationError(_("Explain the cash difference."))

    @api.model
    def _his_may_count(self, journal):
        user = self.env.user
        if self.env.su or journal.his_holder_id == user:
            return True
        if journal.code == "CDIR":
            return user.has_group("his_purchase.group_purchase_director") or user.has_group(
                "his_pos_finance.group_finance_head"
            )
        return journal.code == "CFIN" and user.has_group("his_purchase_finance.group_finance")

    @api.model_create_multi
    def create(self, vals_list):
        journals = self.env["account.journal"].browse([vals.get("journal_id") for vals in vals_list])
        for journal in journals:
            if not self._his_may_count(journal):
                raise AccessError(_("You cannot count %(box)s.", box=journal.display_name))
        counts = super(HisCashCount, self.sudo()).create(vals_list)
        for count in counts:
            count._his_gap()
        return counts.sudo(False)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_("A cash count cannot be changed; count again."))
        return super().write(vals)

    def _his_gap(self):
        if self.currency_id.is_zero(self.difference):
            return
        box = self.journal_id
        ecart = self.env["account.account"].search(
            [("code", "=", "476000"), ("company_ids", "in", self.company_id.id)], limit=1
        )
        gap = self.difference
        move = self.env["account.move"].create(
            {
                "journal_id": box.id,
                "ref": _("Cash count %s", box.name),
                "line_ids": [
                    (0, 0, {"account_id": box.default_account_id.id, "debit": max(gap, 0), "credit": max(-gap, 0)}),
                    (0, 0, {"account_id": ecart.id, "debit": max(-gap, 0), "credit": max(gap, 0)}),
                ],
            }
        )
        move.action_post()
        self.env["his.cash.discrepancy"].his_open(
            "count",
            box,
            expected=self.expected,
            counted=self.counted,
            provisional_move=move,
            explanation=self.note or "",
            count_id=self.id,
            holder_id=(box.his_holder_id or self.user_id).id,
        )
