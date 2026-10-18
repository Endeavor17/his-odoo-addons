# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _his_appliquer_roles_du_poste(self):
        # Le meme moment que les droits : arrivee, changement de poste ou de
        # compte, reapplication manuelle, cron de rattrapage.
        touches = super()._his_appliquer_roles_du_poste()
        self._his_synchroniser_equipes()
        return touches

    def write(self, vals):
        res = super().write(vals)
        # Un depart archive l'employe sans toucher a son poste.
        if "active" in vals:
            self._his_synchroniser_equipes()
        return res

    def _his_synchroniser_equipes(self):
        self.env["helpdesk.ticket.team"].sudo().search([("his_job_id", "!=", False)])._his_synchroniser_membres()
