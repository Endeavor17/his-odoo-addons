# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Les tickets se voient depuis la personne, et la personne suit le ticket au lead."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPersonneEtLead(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.candidat = cls.env["his.person"].create(
            {
                "name": "Nadia Ferhat",
                "type_personne": "candidat",
                "source_system": "manual",
                "email": "nadia.ferhat@example.com",
            }
        )

    def _ticket(self):
        return self.env["helpdesk.ticket"].create(
            {"name": "Question Master", "description": "<p>x</p>", "his_person_id": self.candidat.id}
        )

    def test_compteur_de_tickets_sur_la_personne(self):
        self._ticket()
        self._ticket()
        self.assertEqual(self.candidat.his_helpdesk_ticket_count, 2)
        action = self.candidat.action_his_helpdesk_tickets()
        self.assertEqual(action["domain"], [("his_person_id", "=", self.candidat.id)])

    def test_le_lead_reprend_la_personne(self):
        if "his_person_id" not in self.env["crm.lead"]._fields:
            self.skipTest("his_crm_identity_bridge non installe")
        ticket = self._ticket()
        wizard = self.env["helpdesk.ticket.create.lead"].with_context(active_id=ticket.id).create({})
        wizard.action_helpdesk_ticket_to_lead()
        self.assertEqual(ticket.lead_ids.his_person_id, self.candidat)
