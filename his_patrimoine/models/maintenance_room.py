# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""La salle sur les demandes et constats de maintenance.

Les salles sont les emplacements Patrimoine sous le batiment (une seule liste
de lieux pour tout le groupe). Le champ vit ici et non dans
maintenance_university : la maintenance doit continuer a tourner sans stock.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


def _room_in_building(room, building):
    """Vrai si la salle est un descendant strict de l'emplacement du batiment."""
    parent = building.his_location_id
    return bool(parent) and room != parent and room.parent_path.startswith(parent.parent_path)


def _room_fields():
    return (
        fields.Many2one(related="building_id.his_location_id", string="Building Location"),
        fields.Many2one(
            "stock.location",
            string="Room",
            compute="_compute_his_room_id",
            store=True,
            readonly=False,
            precompute=True,
            index="btree_not_null",
            ondelete="restrict",
        ),
    )


def _clear_room_outside_building(records):
    # Changer de batiment vide une salle qui n'y est plus.
    for rec in records:
        if rec.his_room_id and not _room_in_building(rec.his_room_id, rec.building_id):
            rec.his_room_id = False


def _check_room_in_building(records):
    for rec in records:
        if rec.his_room_id and not _room_in_building(rec.his_room_id, rec.building_id):
            raise ValidationError(_("The room must be a place inside the selected building."))


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    his_building_location_id, his_room_id = _room_fields()

    @api.depends("building_id")
    def _compute_his_room_id(self):
        _clear_room_outside_building(self)

    @api.constrains("his_room_id", "building_id")
    def _his_check_room_in_building(self):
        _check_room_in_building(self)


class MaintenanceUniversityFinding(models.Model):
    _inherit = "maintenance.university.finding"

    his_building_location_id, his_room_id = _room_fields()

    @api.depends("building_id")
    def _compute_his_room_id(self):
        _clear_room_outside_building(self)

    @api.constrains("his_room_id", "building_id")
    def _his_check_room_in_building(self):
        _check_room_in_building(self)

    def action_convert_to_request(self):
        res = super().action_convert_to_request()
        if self.his_room_id:
            self.created_request_id.his_room_id = self.his_room_id
        return res
