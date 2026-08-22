from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

class MaintenanceCategory(models.Model):
    _name = "maintenance.category"
    _description = "Maintenance Category"
    _order = "name"

    name = fields.Char(
        string="Category Name",
        required=True
    )

    description = fields.Text(
        string="Description"
    )

    active = fields.Boolean(
        default=True
    )

    # L'inverse que le coeur attend. maintenance.request.category_id est
    # redirige vers CE modele (cf. maintenance_university_request.py), alors
    # que le One2many qui le declare comme inverse vit sur
    # maintenance.equipment.category :
    #
    #   maintenance/models/maintenance.py:43
    #       maintenance_ids = fields.One2many('maintenance.request', 'category_id')
    #
    # L'ORM enregistre donc « l'inverse de category_id s'appelle
    # maintenance_ids » et va le chercher sur le comodele — ici. Sans ce champ,
    # _modified_triggers fait self['maintenance_ids'] et leve KeyError des
    # qu'un onchange declenche modified() sur une categorie : le formulaire
    # Categories devenait inouvrable.
    maintenance_ids = fields.One2many(
        'maintenance.request', 'category_id', string="Requests", copy=False,
    )

    is_inspection = fields.Boolean(
        string="Is Inspection Category",
        default=False,
        help="Requests using this category show the Findings tab and enable the inspection workflow.",
    )

    @api.constrains('is_inspection', 'active')
    def _check_single_inspection_category(self):
        for rec in self:
            if rec.is_inspection and rec.active:
                others = self.search_count([
                    ('is_inspection', '=', True),
                    ('active', '=', True),
                    ('id', '!=', rec.id),
                ])
                if others:
                    raise ValidationError(_("Only one active category can be marked as the Inspection category."))