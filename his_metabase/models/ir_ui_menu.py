# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _load_menus_blacklist(self):
        # L'application « Tableaux de bord » (spreadsheet_dashboard, arrivee avec
        # le point de vente) ne porte aucun groupe : tout le monde la voit, vide
        # pour qui n'a aucun tableau. Elle ne s'affiche qu'a ceux qui en lisent
        # un, en pratique les responsables (recette 2026-10-28).
        res = super()._load_menus_blacklist()
        root = self.env.ref("spreadsheet_dashboard.spreadsheet_dashboard_menu_root", raise_if_not_found=False)
        if root and not self.env["spreadsheet.dashboard"].search_count([], limit=1):
            res.append(root.id)
        return res
