from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRechercheMatricule(TransactionCase):
    def _etudiant(self):
        return self.env["his.person"].create(
            {"name": "Lina Ouali", "type_personne": "etudiant", "source_system": "manual"}
        )

    def test_une_personne_se_trouve_par_son_matricule(self):
        person = self._etudiant()
        self.assertTrue(person.matricule_institutionnel)
        found = self.env["his.person"].name_search(person.matricule_affiche)
        self.assertIn(person.id, [pid for pid, _name in found])

    def test_le_nom_reste_cherchable(self):
        person = self._etudiant()
        found = self.env["his.person"].name_search("Ouali")
        self.assertIn(person.id, [pid for pid, _name in found])
