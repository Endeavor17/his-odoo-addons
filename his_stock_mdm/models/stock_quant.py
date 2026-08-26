# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.exceptions import AccessError


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    # --- Separation des taches : Collaborateur compte, Manager applique -----
    #
    # action_apply_inventory() est l'unique methode qui transforme un comptage
    # en mouvement de stock reel (verifie : le bouton "Appliquer" et
    # l'assistant "Tout appliquer" y convergent tous les deux). Un
    # Collaborateur (stock.group_stock_user) garde le droit de saisir
    # `inventory_quantity` (faire le comptage) ; seul un Manager peut
    # appliquer l'ecart aux livres. self.env.su bypasse le controle : une
    # consequence systeme n'est pas un geste humain a arbitrer.
    def action_apply_inventory(self, date=None):
        if not (self.env.su or self.env.user.has_group('stock.group_stock_manager')):
            raise AccessError(
                "Seul un Manager Stock peut appliquer un comptage. "
                "L'écart reste visible en attente d'application.")
        return super().action_apply_inventory(date=date)
