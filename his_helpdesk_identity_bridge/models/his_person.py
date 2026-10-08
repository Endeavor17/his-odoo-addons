# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class HisPerson(models.Model):
    _inherit = "his.person"

    # Le compteur vient du contact par delegation (helpdesk_ticket_count de
    # helpdesk_mgmt) ; pas les methodes : l'action est donc redeclaree ici.
    def action_his_helpdesk_tickets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Tickets"),
            "res_model": "helpdesk.ticket",
            "view_mode": "list,form",
            "domain": [("his_person_id", "=", self.id)],
            "context": {"default_his_person_id": self.id},
        }
