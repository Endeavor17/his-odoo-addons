# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    his_holder_id = fields.Many2one("res.users", string="Cash Box Holder", help="Person who holds this cash box.")
    his_count_state = fields.Selection(
        [("none", "Not Opened"), ("opened", "Opened"), ("closed", "Closed")],
        string="Today",
        compute="_compute_his_count_state",
    )

    def _compute_his_count_state(self):
        debut = fields.Datetime.to_datetime(fields.Date.context_today(self))
        for journal in self:
            last = self.env["his.cash.count"].sudo().search(
                [("journal_id", "=", journal.id), ("date", ">=", debut)], order="date desc, id desc", limit=1
            )
            journal.his_count_state = {"opening": "opened", "closing": "closed"}.get(last.kind, "none")

    def action_his_count(self, kind=None):
        self.ensure_one()
        kind = kind or self.env.context.get("his_count_kind", "opening")
        return {
            "type": "ir.actions.act_window",
            "res_model": "his.cash.count",
            "view_mode": "form",
            "target": "new",
            "context": {"default_journal_id": self.id, "default_kind": kind},
        }
