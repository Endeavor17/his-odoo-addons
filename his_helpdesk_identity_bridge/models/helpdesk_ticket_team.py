# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command, api, fields, models


class HelpdeskTicketTeam(models.Model):
    _inherit = "helpdesk.ticket.team"

    # Un seul agent de support a HIS, et il change (Mohamed, 2026-10-18).
    # L'equipe suit donc un POSTE, comme les droits (his_access_base) :
    # changer l'occupant du poste change l'equipe, sans autre geste.
    his_job_id = fields.Many2one(
        "hr.job",
        string="Position",
        help="Whoever holds this position is a member of the team. Members follow the "
        "position: set it, and they are kept in sync.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        teams = super().create(vals_list)
        teams._his_synchroniser_membres()
        return teams

    def write(self, vals):
        res = super().write(vals)
        if "his_job_id" in vals:
            self._his_synchroniser_membres()
        return res

    def _his_synchroniser_membres(self):
        for team in self.filtered("his_job_id"):
            employes = (
                self.env["hr.employee"].sudo().search([("job_id", "=", team.his_job_id.id), ("user_id", "!=", False)])
            )
            if team.user_ids != employes.user_id:
                team.sudo().user_ids = [Command.set(employes.user_id.ids)]
