# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HisPerson(models.Model):
    _inherit = "his.person"

    his_helpdesk_ticket_count = fields.Integer(
        string="Tickets",
        compute="_compute_his_helpdesk_ticket_count",
    )

    def _compute_his_helpdesk_ticket_count(self):
        counts = dict(
            self.env["helpdesk.ticket"]._read_group(
                [("his_person_id", "in", self.ids)],
                ["his_person_id"],
                ["__count"],
            )
        )
        for person in self:
            person.his_helpdesk_ticket_count = counts.get(person, 0)

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
