# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Chaque tableau de bord a son menu, dans son application, pour son groupe."""

from odoo.tests import TransactionCase, tagged

ATTENDU = {
    "maintenance": ("maintenance_university.menu_maintenance_root", "maintenance_university.group_maintenance_manager"),
    "helpdesk": ("helpdesk_mgmt.helpdesk_ticket_main_menu", "helpdesk_mgmt.group_helpdesk_manager"),
    "pos": ("point_of_sale.menu_point_root", "point_of_sale.group_pos_manager"),
    "purchase": ("purchase.menu_purchase_root", "purchase.group_purchase_manager"),
    "inventory": ("stock.menu_stock_root", "stock.group_stock_manager"),
}


@tagged("post_install", "-at_install")
class TestMenus(TransactionCase):
    def test_un_menu_par_tableau_de_bord(self):
        for code, (racine, groupe) in ATTENDU.items():
            with self.subTest(code=code):
                dashboard = self.env.ref(f"his_metabase.dashboard_{code}")
                menu = self.env.ref(f"his_metabase.menu_dashboard_{code}")
                self.assertEqual(dashboard.code, code)
                self.assertEqual(dashboard.group_ids, self.env.ref(groupe))
                self.assertEqual(menu.parent_id, self.env.ref(racine))
                self.assertEqual(menu.group_ids, self.env.ref(groupe))
                self.assertEqual(menu.action.tag, "his_metabase_dashboard")
                self.assertEqual(menu.action.params, {"code": code})

    def test_l_ancien_ecran_maintenance_a_disparu(self):
        # Un seul chemin vers le tableau de bord maintenance : le notre.
        self.assertFalse(self.env.ref("maintenance_university.menu_maintenance_metabase", raise_if_not_found=False))
        self.assertFalse(
            self.env.ref("maintenance_university.action_maintenance_university_metabase", raise_if_not_found=False)
        )
        self.assertFalse(hasattr(self.env["maintenance.university.dashboard"], "get_metabase_url"))

    def test_pas_de_doublon_de_nom_dans_l_application(self):
        # Assistance et Point de vente ont deja un « Dashboard » : le notre ne
        # doit pas se confondre avec lui (revue finale, 2026-10-18).
        for code in ATTENDU:
            with self.subTest(code=code):
                menu = self.env.ref(f"his_metabase.menu_dashboard_{code}")
                freres = menu.parent_id.child_id - menu
                self.assertNotIn(menu.name, freres.mapped("name"))
