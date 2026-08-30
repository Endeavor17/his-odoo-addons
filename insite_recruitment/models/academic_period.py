from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AcademicPeriod(models.Model):
    """Shared academic reference data: the period an Engagement runs in."""

    _name = 'academic.period'
    _description = 'Academic Period'
    _order = 'date_start desc, id desc'

    name = fields.Char(required=True)
    date_start = fields.Date("Start Date", required=True)
    date_end = fields.Date("End Date", required=True)
    active = fields.Boolean(default=True)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for period in self:
            if period.date_start and period.date_end and period.date_start > period.date_end:
                raise ValidationError(_("The start date must be before the end date."))
