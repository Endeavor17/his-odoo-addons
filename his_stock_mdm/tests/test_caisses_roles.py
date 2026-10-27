"""Recette P-18 : n'importe quel utilisateur POS ouvrait n'importe quelle caisse.
Decision de Mohamed (2026-10-17) : un role par caisse, donne par le poste."""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestCaissesRoles(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = cls.env.ref
        cls.cafeteria = ref("his_stock_mdm.pos_config_cafeteria")
        cls.copy_center = ref("his_stock_mdm.pos_config_copy_center")
        cls.hana = new_test_user(cls.env, login="recette_hana", groups="his_stock_mdm.group_caisse_copy_center")
        cls.chef = new_test_user(cls.env, login="recette_chef_pos", groups="point_of_sale.group_pos_manager")

    def test_chaque_caisse_a_son_role(self):
        self.assertTrue(self.hana.has_group("point_of_sale.group_pos_user"), "le role de caisse donne le POS")
        for xmlid in ("pos_config_cafeteria", "pos_config_restaurant", "pos_config_copy_center"):
            self.assertTrue(self.env.ref(f"his_stock_mdm.{xmlid}").his_group_ids, xmlid)

    def test_la_caissiere_ne_voit_et_n_ouvre_que_sa_caisse(self):
        Config = self.env["pos.config"].with_user(self.hana)
        mes_caisses = Config.search([("his_is_my_till", "=", True)])
        self.assertIn(self.copy_center, mes_caisses)
        self.assertNotIn(self.cafeteria, mes_caisses)
        with self.assertRaises(AccessError):
            self.cafeteria.with_user(self.hana).open_ui()

    def test_le_responsable_pos_voit_tout(self):
        mes_caisses = self.env["pos.config"].with_user(self.chef).search([("his_is_my_till", "=", True)])
        self.assertIn(self.cafeteria, mes_caisses)
        self.assertIn(self.copy_center, mes_caisses)

    def test_le_restaurant_vend_les_boissons_de_son_stock(self):
        """2026-10-27 : le Restaurant vend les boissons, prises sur le stock unique des caisses."""
        restaurant = self.env.ref("his_stock_mdm.pos_config_restaurant")
        self.assertIn(self.env.ref("his_stock_mdm.pos_categ_boissons"), restaurant.iface_available_categ_ids)
        self.assertEqual(
            restaurant.picking_type_id.default_location_src_id,
            self.env.ref("his_stock_mdm.loc_cafeteria"),
            "les boissons vendues au Restaurant sortent du meme stock que la Cafeteria",
        )
