# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Patrimoine : un bien = un numero de serie, range dans une salle, compte chaque annee."""

from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestPatrimoine(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mobilier = cls.env.ref("his_patrimoine.categ_mobilier")
        cls.sequence = cls.env.ref("his_patrimoine.seq_patrimoine")

    def _bien(self, name="Bureau 120 cm", **vals):
        return self.env["product.template"].create({"name": name, "categ_id": self.mobilier.id, **vals})

    def test_un_bien_est_suivi_par_numero_pat(self):
        bureau = self._bien()
        self.assertTrue(bureau.is_storable)
        self.assertEqual(bureau.tracking, "serial")
        self.assertEqual(bureau.lot_sequence_id, self.sequence)
        self.assertFalse(bureau.sale_ok)

    def test_un_bien_cree_comme_variante_est_suivi_aussi(self):
        # Ligne de commande « Creer » ou import : passe par product.product.
        portable = self.env["product.product"].create(
            {"name": "HP ProBook", "categ_id": self.env.ref("his_patrimoine.categ_informatique").id}
        )
        self.assertEqual(portable.tracking, "serial")
        self.assertEqual(portable.lot_sequence_id, self.sequence)

    def test_un_bien_reste_suivi_par_numero(self):
        bureau = self._bien()
        with self.assertRaises(ValidationError):
            bureau.tracking = "none"

    def _batiment(self, name="Bloc A"):
        return self.env["maintenance.building"].create({"name": name, "code": name[-1]})

    def test_un_batiment_cree_son_emplacement(self):
        batiment = self._batiment()
        location = batiment.his_location_id
        self.assertEqual(location.location_id, self.env.ref("his_patrimoine.loc_patrimoine"))
        self.assertEqual(location.name, "Bloc A")
        self.assertEqual(location.cyclic_inventory_frequency, 365)

    def test_renommer_le_batiment_renomme_l_emplacement(self):
        batiment = self._batiment()
        batiment.name = "Bloc B"
        self.assertEqual(batiment.his_location_id.name, "Bloc B")

    def test_une_salle_est_comptee_chaque_annee(self):
        # Revue RF5 : une salle creee a la main herite du rythme annuel.
        salle = self.env["stock.location"].create(
            {"name": "Salle 12", "location_id": self._batiment().his_location_id.id}
        )
        self.assertEqual(salle.cyclic_inventory_frequency, 365)
        autre = self.env["stock.location"].create(
            {"name": "Rayon", "location_id": self.env.ref("stock.warehouse0").lot_stock_id.id}
        )
        self.assertEqual(autre.cyclic_inventory_frequency, 0)

    def test_une_salle_creee_par_le_formulaire_est_comptee_chaque_annee(self):
        # Revue finale : le formulaire envoie la frequence par defaut (0).
        gestionnaire = new_test_user(
            self.env, login="his_stock_admin", groups="stock.group_stock_manager,stock.group_stock_multi_locations"
        )
        batiment = self._batiment()
        with Form(self.env["stock.location"].with_user(gestionnaire)) as form:
            form.name = "Salle 14"
            form.location_id = batiment.his_location_id
        self.assertEqual(form.record.cyclic_inventory_frequency, 365)

    def test_la_reception_range_les_biens_a_affecter(self):
        bureau = self._bien().product_variant_id
        warehouse = self.env.ref("stock.warehouse0")
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": warehouse.in_type_id.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": warehouse.lot_stock_id.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": bureau.id,
                            "product_uom_qty": 2,
                            "location_id": self.env.ref("stock.stock_location_suppliers").id,
                            "location_dest_id": warehouse.lot_stock_id.id,
                        },
                    )
                ],
            }
        )
        picking.action_confirm()
        for i, line in enumerate(picking.move_line_ids):
            line.lot_name = "PAT-TEST-%d" % i
        picking.move_ids.picked = True
        picking.button_validate()
        quants = self.env["stock.quant"].search([("product_id", "=", bureau.id), ("quantity", ">", 0)])
        self.assertEqual(len(quants), 2)
        self.assertEqual(quants.location_id, self.env.ref("his_patrimoine.loc_a_affecter"))

    def test_un_bien_en_salle_n_est_pas_du_stock(self):
        # Revue RF5 : rien de la salle n'apparait dans le stock des caisses.
        bureau = self._bien().product_variant_id
        salle = self.env["stock.location"].create(
            {"name": "Salle 3", "location_id": self._batiment().his_location_id.id}
        )
        lot = self.env["stock.lot"].create({"name": "PAT-TEST-9", "product_id": bureau.id})
        self.env["stock.quant"]._update_available_quantity(bureau, salle, 1, lot_id=lot)
        stock = self.env.ref("stock.warehouse0").lot_stock_id
        self.assertEqual(bureau.with_context(location=stock.id).qty_available, 0)
        self.assertEqual(bureau.with_context(location=salle.id).qty_available, 1)

    def test_import_des_biens_existants(self):
        rows = [
            {
                "building_code": "A",
                "room": "Salle 12",
                "category_xmlid": "his_patrimoine.categ_mobilier",
                "default_code": "PAT-BUR-120",
                "product_name": "Bureau 120 cm",
                "serial": "PAT-900001",
            },
            {
                "building_code": "A",
                "room": "Salle 12",
                "category_xmlid": "his_patrimoine.categ_mobilier",
                "default_code": "PAT-BUR-120",
                "product_name": "Bureau 120 cm",
                "serial": "PAT-900002",
            },
            {
                "building_code": "A",
                "room": "Salle 12",
                "category_xmlid": "his_stock_mdm.categ_cafe_boissons",
                "default_code": "X-1",
                "product_name": "Eau",
                "serial": "PAT-900003",
            },
        ]
        Lot = self.env["stock.lot"]
        created, rejected = Lot._his_import_patrimoine(rows)
        self.assertEqual(created, 2, rejected)
        self.assertEqual(len(rejected), 1)
        self.assertIn("row 3", rejected[0])
        en_salle = [("lot_id.name", "in", ["PAT-900001", "PAT-900002"]), ("location_id.usage", "=", "internal")]
        quants = self.env["stock.quant"].search(en_salle)
        self.assertEqual(len(quants), 2)
        self.assertEqual(quants.location_id.name, "Salle 12")
        self.assertEqual(quants.location_id.location_id.location_id, self.env.ref("his_patrimoine.loc_patrimoine"))
        created, rejected = Lot._his_import_patrimoine(rows[:2])
        self.assertEqual(created, 0, "relancer l'import ne cree pas de doublon")
        self.assertEqual(self.env["stock.quant"].search_count(en_salle), 2)

    def test_import_sans_numero_en_attribue_un(self):
        created, _rejected = self.env["stock.lot"]._his_import_patrimoine(
            [
                {
                    "building_code": "B",
                    "room": "Bureau 1",
                    "category_xmlid": "his_patrimoine.categ_informatique",
                    "default_code": "PAT-HP-450",
                    "product_name": "HP ProBook 450",
                    "serial": "",
                }
            ]
        )
        self.assertEqual(created, 1)
        lot = self.env["stock.lot"].search([("product_id.default_code", "=", "PAT-HP-450")])
        self.assertTrue(lot.name.startswith("PAT-"), lot.name)

    def test_relancer_un_import_sans_numeros_ne_double_pas(self):
        # Revue finale : le modele de fichier laisse les numeros vides.
        ligne = {
            "building_code": "C",
            "room": "Salle 1",
            "category_xmlid": "his_patrimoine.categ_mobilier",
            "default_code": "PAT-CHAISE",
            "product_name": "Chaise",
            "serial": "",
        }
        Lot = self.env["stock.lot"]
        self.assertEqual(Lot._his_import_patrimoine([ligne, ligne, ligne])[0], 3)
        self.assertEqual(Lot._his_import_patrimoine([ligne, ligne, ligne])[0], 0, "deja en salle : rien de plus")
        self.assertEqual(Lot._his_import_patrimoine([ligne] * 4)[0], 1, "une 4e chaise dans le fichier : une de plus")

    def test_les_autres_categories_ne_changent_pas(self):
        boisson = self.env["product.template"].create(
            {"name": "Eau 50 cl", "categ_id": self.env.ref("his_stock_mdm.categ_cafe_boissons").id}
        )
        self.assertNotEqual(boisson.lot_sequence_id, self.sequence, "Odoo 19 lui donne sa sequence par defaut")
        self.assertNotEqual(boisson.tracking, "serial")
