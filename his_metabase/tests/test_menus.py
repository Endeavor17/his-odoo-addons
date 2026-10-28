# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Chaque tableau de bord a son menu, dans son application, pour son groupe."""

from odoo.tests import TransactionCase, new_test_user, tagged

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

    def test_l_agent_ouvre_l_assistance_sur_ses_tickets(self):
        # Recette 2026-10-28 : le tableau de bord est au responsable.
        agent = new_test_user(self.env, login="agent_hd", groups="base.group_user,helpdesk_mgmt.group_helpdesk_user")
        responsable = new_test_user(
            self.env, login="resp_hd", groups="base.group_user,helpdesk_mgmt.group_helpdesk_manager"
        )
        dashboard = self.env.ref("helpdesk_mgmt.helpdesk_ticket_dashboard_menu")
        self.assertNotIn(dashboard.id, self.env["ir.ui.menu"].with_user(agent)._visible_menu_ids())
        self.assertIn(dashboard.id, self.env["ir.ui.menu"].with_user(responsable)._visible_menu_ids())
        menus = self.env["ir.ui.menu"].with_user(agent).load_menus(False)
        racine = self.env.ref("helpdesk_mgmt.helpdesk_ticket_main_menu")
        premier = menus[menus[racine.id]["children"][0]]
        self.assertEqual(premier["xmlid"], "helpdesk_mgmt.helpdesk_ticket_menu")

    def test_tableaux_de_bord_caches_a_qui_n_en_a_aucun(self):
        racine = self.env.ref("spreadsheet_dashboard.spreadsheet_dashboard_menu_root", raise_if_not_found=False)
        if not racine:
            self.skipTest("spreadsheet_dashboard absent")
        simple = new_test_user(self.env, login="simple_tdb", groups="base.group_user")
        self.assertIn(racine.id, self.env["ir.ui.menu"].with_user(simple)._visible_menu_ids())
        self.assertNotIn(racine.id, self.env["ir.ui.menu"].with_user(simple).load_menus(False))
        groupe = self.env["res.groups"].create({"name": "Lecteurs TDB"})
        self.env["spreadsheet.dashboard"].create(
            {
                "name": "Test",
                "dashboard_group_id": self.env["spreadsheet.dashboard.group"].create({"name": "G"}).id,
                "group_ids": [(6, 0, groupe.ids)],
            }
        )
        simple.group_ids = [(4, groupe.id)]
        self.assertIn(racine.id, self.env["ir.ui.menu"].with_user(simple).load_menus(False))
