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