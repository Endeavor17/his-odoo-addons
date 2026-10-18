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
                self.assertFalse(dashboard.metabase_id, "Le numero se saisit par serveur, jamais livre.")
                self.assertEqual(dashboard.group_ids, self.env.ref(groupe))
                self.assertEqual(menu.parent_id, self.env.ref(racine))
                self.assertEqual(menu.group_ids, self.env.ref(groupe))
                self.assertEqual(menu.action.tag, "his_metabase_dashboard")
                self.assertEqual(menu.action.params, {"code": code})
