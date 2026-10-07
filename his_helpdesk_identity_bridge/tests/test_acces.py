# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Audit S-6 : l'agent du helpdesk voit etudiants et candidats, personne d'autre."""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestAcces(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.etudiant = cls.env["his.person"].create(
            {
                "name": "Karim Djebbar",
                "type_personne": "etudiant",
                "source_system": "manual",
                "email": "karim.djebbar@example.com",
            }
        )
        # « prospect » et non « inscrit » : his_admission interdit d'inscrire
        # sans droits encaisses. L'en-tete ne fait que lire l'etat.
        cls.env["his.engagement"].create({"person_id": cls.etudiant.id, "etat": "prospect"})
        cls.agent = new_test_user(cls.env, login="agent_hd", groups="helpdesk_mgmt.group_helpdesk_user_own")
        cls.sans_role = new_test_user(cls.env, login="sans_role_hd", groups="base.group_user")

    def test_un_agent_voit_l_etudiant(self):
        self.assertEqual(self.etudiant.partner_id.with_user(self.agent).email, "karim.djebbar@example.com")
        self.assertEqual(self.etudiant.with_user(self.agent).matricule_affiche, self.etudiant.matricule_affiche)

    def test_sans_role_l_etudiant_reste_ferme(self):
        with self.assertRaises(AccessError):
            self.etudiant.partner_id.with_user(self.sans_role).read(["email"])

    def test_l_agent_ouvre_un_ticket_et_lit_l_en_tete(self):
        ticket = (
            self.env["helpdesk.ticket"]
            .with_user(self.agent)
            .create({"name": "Carte", "description": "<p>x</p>", "his_person_id": self.etudiant.id})
        )
        self.assertEqual(ticket.partner_id, self.etudiant.partner_id)
        self.assertEqual(ticket.his_matricule, self.etudiant.matricule_affiche)
        self.assertEqual(ticket.his_type_personne, "etudiant")
        # L etat, pas l engagement : un his.engagement s affiche sous le nom
        # de sa personne, ce qui ne dit rien a l agent.
        self.assertEqual(ticket.his_engagement_etat, "prospect")

    def test_l_agent_ne_modifie_pas_la_personne(self):
        with self.assertRaises(AccessError):
            self.etudiant.with_user(self.agent).write({"nom_arabe": "x"})
