# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models

# Les biens se comptent une fois par an (inventaire annuel, his_stock_mdm).
YEARLY = 365


class StockLocation(models.Model):
    _inherit = "stock.location"

    @api.model_create_multi
    def create(self, vals_list):
        root = self.env.ref("his_patrimoine.loc_patrimoine", raise_if_not_found=False)
        if root:
            for vals in vals_list:
                # Le formulaire envoie 0 par defaut : seule une valeur saisie compte.
                if vals.get("cyclic_inventory_frequency") or not vals.get("location_id"):
                    continue
                # sudo : seul le chemin est lu. Un utilisateur peut creer un
                # emplacement sans lire son parent (cas du socle de tests POS).
                parent = self.browse(vals["location_id"]).sudo()
                if parent.parent_path.startswith(root.sudo().parent_path):
                    vals["cyclic_inventory_frequency"] = YEARLY
        return super().create(vals_list)
