from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HisHygieneArea(models.Model):
    """Une zone que l'equipe nettoie : un emplacement Patrimoine sous un batiment.

    Le lieu lui-meme reste dans le referentiel (stock.location sous
    WH/Patrimoine/<batiment>). Ce modele ne dit que « l'hygiene le couvre », et
    dans quel ordre il apparait dans la matrice.
    """

    _name = "his.hygiene.area"
    _description = "Hygiene Area"
    _order = "building_id, sequence, id"

    location_id = fields.Many2one("stock.location", string="Place", required=True, ondelete="restrict", index=True)
    building_id = fields.Many2one(
        "maintenance.building", string="Building", compute="_compute_place", store=True, index=True
    )
    name = fields.Char(compute="_compute_place", store=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _location_unique = models.Constraint("UNIQUE(location_id)", "This place is already an area.")

    @api.depends("location_id.parent_path", "location_id.complete_name")
    def _compute_place(self):
        buildings = self.env["maintenance.building"].sudo().search([("his_location_id", "!=", False)])
        by_location = {b.his_location_id.id: b for b in buildings}
        for area in self:
            loc = area.location_id
            ancestor_ids = [int(i) for i in (loc.parent_path or "").split("/") if i]
            building = next((by_location[i] for i in reversed(ancestor_ids) if i in by_location), False)
            area.building_id = building
            if not building:
                area.name = loc.name
                continue
            # Le chemin sous le batiment : « Bloc A / RDC / Salle 3 ».
            depth = len(building.his_location_id.complete_name.split("/"))
            area.name = " / ".join([building.name, *loc.complete_name.split("/")[depth:]])

    @api.constrains("location_id")
    def _check_under_building(self):
        for area in self:
            if not area.building_id:
                raise ValidationError(_("An area must be a place under a building in Patrimoine."))
