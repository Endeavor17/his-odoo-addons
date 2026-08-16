from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.mail import plaintext2html

CLOSED_STATES = ('done', 'cancelled')

# Fields a non-manager may still write directly: everything the state-machine
# buttons and the inspection report touch. Everything else defines the job
# itself (what/where/who/when) and is manager-only, even via direct API calls.
WORKER_WRITABLE_FIELDS = {
    'state', 'date_start', 'date_end', 'date_assigned', 'inspection_report', 'finding_ids',
}


class MaintenanceUniversityRequest(models.Model):
    _name = 'maintenance.university.request'
    _description = 'University Maintenance Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string="Subject", required=True, tracking=True)
    building_id = fields.Many2one('maintenance.building', string="Building", required=True, tracking=True)
    category_id = fields.Many2one('maintenance.category', string="Category", required=True, tracking=True)
    description = fields.Text(string="Description")
    employee_ids = fields.Many2many('hr.employee', string="Assigned Workers", tracking=True)
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], string="Priority", default='1')
    state = fields.Selection([
        ('new', 'New'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('paused', 'Paused'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string="Status", default='new', copy=False, tracking=True)

    request_date = fields.Datetime(string="Request Date", default=fields.Datetime.now)
    scheduled_date = fields.Datetime(string="Scheduled For", tracking=True,
                                      help="When the worker is expected to do this.")
    date_assigned = fields.Datetime(string="Assigned On", readonly=True, copy=False)
    date_start = fields.Datetime(string="Started On", readonly=True, copy=False)
    date_end = fields.Datetime(string="Finished On", readonly=True, copy=False)

    time_log_ids = fields.One2many('maintenance.university.request.time', 'request_id', string="Time Log")
    duration = fields.Float(string="Duration (hours)", compute='_compute_duration', store=True)

    is_inspection = fields.Boolean(related='category_id.is_inspection', store=True, string="Is Inspection")
    finding_ids = fields.One2many('maintenance.university.finding', 'request_id', string="Findings")
    finding_count = fields.Integer(string="Findings Count", compute='_compute_finding_count')

    origin_finding_id = fields.Many2one(
        'maintenance.university.finding',
        string="Originating Finding",
        readonly=True,
        copy=False,
    )

    inspection_report = fields.Text(string="Inspection Report")

    is_manager = fields.Boolean(compute='_compute_is_manager')

    @api.depends_context('uid')
    def _compute_is_manager(self):
        is_mgr = self.env.user.has_group('maintenance_university.group_maintenance_manager')
        for rec in self:
            rec.is_manager = is_mgr

    @api.depends('time_log_ids.duration')
    def _compute_duration(self):
        for rec in self:
            rec.duration = sum(rec.time_log_ids.mapped('duration'))

    @api.depends('finding_ids')
    def _compute_finding_count(self):
        for rec in self:
            rec.finding_count = len(rec.finding_ids)

    @api.constrains('employee_ids', 'state')
    def _check_employee_assigned(self):
        for rec in self:
            # 'cancelled' is reachable from 'new', where no worker is assigned yet.
            if rec.state not in ('new', 'cancelled') and not rec.employee_ids:
                raise ValidationError(_("At least one worker must be assigned before the request leaves the New state."))

    def _check_can_operate(self):
        # Manager or any of the assigned workers: used for management actions
        # like Cancel, which aren't "doing the work" itself.
        is_manager = self.env.user.has_group('maintenance_university.group_maintenance_manager')
        for rec in self:
            if not is_manager and self.env.user not in rec.sudo().employee_ids.user_id:
                raise UserError(_("You can only operate on your own assigned requests."))

    def _check_is_assigned_worker(self):
        # Strictly the assigned worker, no manager bypass: a Leader assigns
        # and tracks the work, but doesn't start/pause/resume/complete it
        # themselves — that would defeat the point of assigning it out.
        for rec in self:
            if self.env.user not in rec.sudo().employee_ids.user_id:
                raise UserError(_("Only an assigned worker can start, pause, resume or complete this request."))

    def write(self, vals):
        if not self.env.user.has_group('maintenance_university.group_maintenance_manager'):
            if set(vals) - WORKER_WRITABLE_FIELDS:
                raise UserError(_("You can only update your own progress on this request, not its details."))
        return super().write(vals)

    def action_assign(self):
        if not self.env.user.has_group('maintenance_university.group_maintenance_manager'):
            raise UserError(_("Only a manager can assign a maintenance request."))
        for rec in self:
            if rec.state in CLOSED_STATES:
                raise UserError(_("A closed request can no longer be assigned."))
            if not rec.employee_ids:
                raise UserError(_("Select at least one worker before assigning the request."))
            rec.write({
                'state': 'assigned',
                'date_assigned': fields.Datetime.now(),
            })

    def action_start(self):
        self._check_is_assigned_worker()
        for rec in self:
            if rec.state != 'assigned':
                raise UserError(_("Only an assigned request can be started."))
            rec._open_time_segment()
            vals = {'state': 'in_progress'}
            if not rec.date_start:
                vals['date_start'] = fields.Datetime.now()
            rec.write(vals)

    def action_resume(self):
        self._check_is_assigned_worker()
        for rec in self:
            if rec.state != 'paused':
                raise UserError(_("Only a paused request can be resumed."))
            rec._open_time_segment()
            rec.state = 'in_progress'

    def action_pause(self):
        self._check_is_assigned_worker()
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_("Only a request in progress can be paused."))
            rec._close_open_time_segments()
            rec.state = 'paused'

    def action_done(self):
        self._check_is_assigned_worker()
        for rec in self:
            if rec.state not in ('in_progress', 'paused'):
                raise UserError(_("Only a request in progress or paused can be completed."))
            rec._close_open_time_segments()
            rec.write({
                'state': 'done',
                'date_end': fields.Datetime.now(),
            })

    def action_cancel(self):
        self._check_can_operate()
        for rec in self:
            if rec.state in CLOSED_STATES:
                raise UserError(_("This request is already closed."))
            rec._close_open_time_segments()
            rec.state = 'cancelled'

    def action_view_findings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Findings"),
            'res_model': 'maintenance.university.finding',
            'view_mode': 'list,form',
            'domain': [('request_id', '=', self.id)],
            'context': {
                'default_request_id': self.id,
                'default_building_id': self.building_id.id,
            },
        }

    def action_submit_report(self):
        self._check_can_operate()
        for rec in self:
            if not rec.is_inspection:
                raise UserError(_("Only inspection requests take a report."))
            if not (rec.inspection_report or '').strip():
                raise UserError(_("Write something before sending the report."))
            rec.message_post(
                body=plaintext2html(rec.inspection_report),
                subject=_("Inspection report"),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

    def _open_time_segment(self):
        self.ensure_one()
        # Never leave two segments running at once: a stale open segment would
        # be closed later by an unrelated action and inflate the duration.
        self._close_open_time_segments()
        # Log the segment under whichever assigned worker actually clicked the
        # button, not just "the first one" — several people can share a job.
        actor = self.sudo().employee_ids.filtered(lambda e: e.user_id == self.env.user)
        self.env['maintenance.university.request.time'].create({
            'request_id': self.id,
            'employee_id': (actor[:1] or self.employee_ids[:1]).id,
            'date_start': fields.Datetime.now(),
        })

    def _close_open_time_segments(self):
        self.ensure_one()
        self.time_log_ids.filtered(lambda t: not t.date_end).write({'date_end': fields.Datetime.now()})
