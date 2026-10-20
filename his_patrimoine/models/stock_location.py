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
                if "cyclic_inventory_frequency" in vals or not vals.get("location_id"):
                    continue
                parent = self.browse(vals["location_id"])
                if parent.parent_path.startswith(root.parent_path):
                    vals["cyclic_inventory_frequency"] = YEARLY
        return super().create(vals_list)
