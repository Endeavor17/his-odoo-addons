# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Le lien ticket <-> personne : un test par regle."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLienPersonne(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.etudiant = cls.env["his.person"].create(
            {
                "name": "Amel Saidi",
                "type_personne": "etudiant",
                "source_system": "manual",
                "email": "amel.saidi@example.com",
            }
        )
        cls.fournisseur = cls.env["res.partner"].create({"name": "Papeterie Atlas"})

    def _ticket(self, **vals):
        return self.env["helpdesk.ticket"].create({"name": "Attestation", "description": "<p>Demande</p>", **vals})

    def test_choisir_la_personne_pose_le_contact(self):
        ticket = self._ticket(his_person_id=self.etudiant.id)
        self.assertEqual(ticket.partner_id, self.etudiant.partner_id)

    def test_choisir_le_contact_pose_la_personne(self):
        ticket = self._ticket(partner_id=self.etudiant.partner_id.id)
        self.assertEqual(ticket.his_person_id, self.etudiant)

    def test_contact_hors_referentiel(self):
        ticket = self._ticket(partner_id=self.fournisseur.id)
        self.assertFalse(ticket.his_person_id)

    def test_changer_de_contact_efface_la_personne(self):
        ticket = self._ticket(his_person_id=self.etudiant.id)
        ticket.partner_id = self.fournisseur
        self.assertFalse(ticket.his_person_id)

    def test_vider_la_personne_vide_son_contact(self):
        ticket = self._ticket(his_person_id=self.etudiant.id)
        ticket.his_person_id = False
        self.assertFalse(ticket.partner_id)

    def test_le_helpdesk_ne_cree_aucune_personne(self):
        avant = self.env["his.person"].search_count([])
        self._ticket(partner_id=self.fournisseur.id)
        self._ticket(partner_name="Inconnu", partner_email="inconnu@example.com")
        self.assertEqual(self.env["his.person"].search_count([]), avant)

    def test_le_type_de_personne_n_encombre_pas_le_suivi(self):
        # Un champ related herite du tracking de sa source : le type de la
        # personne ecrirait dans le fil de chaque ticket a chaque changement.
        self.assertNotIn("his_type_personne", self.env["helpdesk.ticket"]._track_get_fields())
