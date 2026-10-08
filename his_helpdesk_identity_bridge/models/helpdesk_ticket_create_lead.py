# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class HelpdeskTicketCreateLead(models.TransientModel):
    _inherit = "helpdesk.ticket.create.lead"

    def _prepare_vals(self):
        vals = super()._prepare_vals()
        # Sans dependance a his_crm_identity_bridge : on ne pose le champ que
        # s'il existe. Pose, il desarme le pont CRM (garde « deja rattache »).
        person = self.ticket_id.his_person_id
        if person and "his_person_id" in self.env["crm.lead"]._fields:
            vals["his_person_id"] = person.id
        return vals
