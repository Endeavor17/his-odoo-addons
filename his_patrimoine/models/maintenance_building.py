# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class MaintenanceBuilding(models.Model):
    _inherit = "maintenance.building"

    his_location_id = fields.Many2one(
        "stock.location", string="Patrimoine Location", readonly=True, copy=False, index="btree_not_null"
    )

    @api.model_create_multi
    def create(self, vals_list):
        buildings = super().create(vals_list)
        buildings._his_ensure_location()
        return buildings

    def write(self, vals):
        res = super().write(vals)
        if "name" in vals:
            for building in self.filtered("his_location_id"):
                building.his_location_id.sudo().name = building.name
        return res

    def unlink(self):
        locations = self.his_location_id
        res = super().unlink()
        # Archiver, pas supprimer : l'historique des biens y reste rattache.
        locations.sudo().active = False
        return res

    def _his_ensure_location(self):
        parent = self.env.ref("his_patrimoine.loc_patrimoine")
        for building in self.filtered(lambda b: not b.his_location_id):
            building.his_location_id = (
                self.env["stock.location"].sudo().create({"name": building.name, "location_id": parent.id})
            )
