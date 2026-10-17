"""Recette du 2026-10-17 : doublons (P-12) et matricules brules (P-23)."""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models.his_person import MATRICULE_SEQUENCE_CODE


@tagged("post_install", "-at_install")
class TestRecetteIdentite(TransactionCase):
    def _person(self, **vals):
        return self.env["his.person"].create(
            {"name": "Etudiant Doublon", "type_personne": "etudiant", "email": "doublon@example.com", **vals}
        )

    def test_un_doublon_saisi_a_la_main_est_signale(self):
        first = self._person()
        with self.assertRaisesRegex(UserError, first.matricule_institutionnel):
            self._person()
        # Un homonyme reel : confirme, il est cree et la confirmation est tracee.
        second = self._person(his_confirmed_new=True)
        self.assertNotEqual(second.matricule_institutionnel, first.matricule_institutionnel)

    def test_fusionner_deux_personnes_est_refuse(self):
        first = self._person()
        second = self._person(name="Autre Etudiant", email="autre@example.com")
        wizard = self.env["base.partner.merge.automatic.wizard"].create(
            {"partner_ids": [(6, 0, (first.partner_id | second.partner_id).ids)], "dst_partner_id": first.partner_id.id}
        )
        with self.assertRaises(UserError):
            wizard.action_merge()
        self.assertTrue(second.exists(), "la fusion a supprime une identite et son matricule")

    def test_sans_source_et_sans_matricule_brule(self):
        person = self.env["his.person"].create({"name": "Sans Source", "type_personne": "etudiant"})
        self.assertEqual(person.source_system, "manual")
        sequence = self.env["ir.sequence"].search([("code", "=", MATRICULE_SEQUENCE_CODE)])
        before = sequence.date_range_ids.mapped("number_next_actual")
        with self.assertRaises(RuntimeError), self.env.cr.savepoint():
            self.env["his.person"].create({"name": "Echec", "type_personne": "etudiant"})
            raise RuntimeError("echec apres l'attribution du matricule")
        sequence.invalidate_recordset()
        sequence.date_range_ids.invalidate_recordset()
        self.assertEqual(sequence.date_range_ids.mapped("number_next_actual"), before, "un echec a brule un matricule")
