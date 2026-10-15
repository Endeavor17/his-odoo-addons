"""La categorie d'une demande vit dans son propre champ, pas dans celui du coeur.

maintenance_university detournait maintenance.request.category_id vers
maintenance.category. Le coeur le declare vers maintenance.equipment.category :
toute mise a jour de `maintenance` recreait sa cle etrangere sur nos valeurs et
echouait. Nos categories vivent desormais dans maintenance_category_id.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCategoryField(TransactionCase):
    def setUp(self):
        super().setUp()
        self.category = self.env["maintenance.category"].create({"name": "Test Plomberie"})
        self.building = self.env["maintenance.building"].create({"name": "Test Batiment"})

    def test_le_category_id_du_coeur_est_intact(self):
        field = self.env["maintenance.request"]._fields["category_id"]
        self.assertEqual(field.comodel_name, "maintenance.equipment.category")
        self.assertEqual(field.related, "equipment_id.category_id")

    def test_la_categorie_universite_a_son_propre_champ(self):
        field = self.env["maintenance.request"]._fields["maintenance_category_id"]
        self.assertEqual(field.comodel_name, "maintenance.category")
        self.assertTrue(field.required)

    def test_une_categorie_liste_ses_demandes(self):
        request = self.env["maintenance.request"].create(
            {
                "name": "Test Demande",
                "maintenance_category_id": self.category.id,
                "building_id": self.building.id,
            }
        )
        self.assertIn(request, self.category.maintenance_ids)
        self.assertFalse(request.category_id)

    def test_un_onchange_sur_une_categorie_ne_leve_pas(self):
        """modified() sur tous les champs, comme au premier onchange d'un formulaire."""
        self.category.modified(list(self.category._fields))

    def test_is_inspection_suit_la_categorie(self):
        inspection = self.env["maintenance.category"].search([("is_inspection", "=", True)], limit=1)
        if not inspection:
            inspection = self.env["maintenance.category"].create({"name": "Test Inspection", "is_inspection": True})
        self.assertTrue(
            self.env["maintenance.request"]
            .create(
                {
                    "name": "Test Tournee",
                    "maintenance_category_id": inspection.id,
                    "building_id": self.building.id,
                }
            )
            .is_inspection
        )
