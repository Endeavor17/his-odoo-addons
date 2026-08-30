from odoo import fields, models


class AcademicFaculty(models.Model):
    """Shared academic reference data: which faculty a Module belongs to."""

    _name = 'academic.faculty'
    _description = 'Faculty'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char(index=True)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        'unique(code)',
        'Another faculty already uses this code.',
    )
