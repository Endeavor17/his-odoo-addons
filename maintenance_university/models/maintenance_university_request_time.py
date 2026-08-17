from odoo import api, fields, models


class MaintenanceUniversityRequestTime(models.Model):
    _name = 'maintenance.university.request.time'
    _description = 'Maintenance Request Time Log'
    _order = 'date_start desc'

    request_id = fields.Many2one(
        'maintenance.request',
        string="Request",
        required=True,
        ondelete='cascade',
        index=True,
    )
    employee_id = fields.Many2one('hr.employee', string="Worker", required=True)
    date_start = fields.Datetime(string="Start", required=True, default=fields.Datetime.now)
    date_end = fields.Datetime(string="End")
    duration = fields.Float(string="Duration (hours)", compute='_compute_duration', store=True)

    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        for rec in self:
            if rec.date_start and rec.date_end:
                rec.duration = (rec.date_end - rec.date_start).total_seconds() / 3600.0
            else:
                rec.duration = 0.0
