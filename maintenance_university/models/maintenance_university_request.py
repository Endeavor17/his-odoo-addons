from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.mail import plaintext2html

CLOSED_STATES = ('done', 'cancelled')

# Fields a non-manager may still write directly: everything the state-machine
# buttons and the inspection report touch. Everything else defines the job
# itself (what/where/who/when) and is manager-only, even via direct API calls.
# close_date isn't something a worker sets themselves — it's core Maintenance's
# own side effect of stage_id reaching a done=True stage (see write() in
# odoo/addons/maintenance/models/maintenance.py), triggered as a nested write()
# from inside action_done/action_cancel.
WORKER_WRITABLE_FIELDS = {
    'stage_id', 'kanban_state', 'date_start', 'date_end', 'date_assigned',
    'inspection_report', 'finding_ids', 'close_date',
}

_STAGE_XMLIDS = {
    'new': 'maintenance_university.maintenance_stage_new',
    'assigned': 'maintenance_university.maintenance_stage_assigned',
    'in_progress': 'maintenance_university.maintenance_stage_in_progress',
    'done': 'maintenance_university.maintenance_stage_done',
    'cancelled': 'maintenance_university.maintenance_stage_cancelled',
}


class MaintenanceRequest(models.Model):
    # True inherit, not a new model: this IS Odoo's own maintenance.request,
    # extended — not a lookalike sitting next to it. Its technical name stays
    # 'maintenance.request' everywhere (views, other models, security).
    _inherit = 'maintenance.request'

    building_id = fields.Many2one('maintenance.building', string="Building", required=True, tracking=True)
    employee_ids = fields.Many2many('hr.employee', string="Assigned Workers", tracking=True)

    # Core's category_id is related='equipment_id.category_id' (an asset-type
    # taxonomy) — we have no equipment, only buildings, so it's always empty
    # left as-is. Redirected to our own category model instead of adding a
    # second, differently-named field for the same "what kind of problem"
    # concept the field slot already exists for.
    category_id = fields.Many2one(
        'maintenance.category', string="Category", required=True, tracking=True,
        related=None, compute=None, store=True, readonly=False,
    )

    # Core's request_date is a plain Date; the dashboard needs datetime
    # granularity for its month-window comparisons.
    request_date = fields.Datetime(string="Request Date", default=fields.Datetime.now, tracking=True)

    # Core's priority already has 4 levels with matching value keys (0-3) —
    # only the labels are relabeled to match what Managers/Workers already
    # know from this session, not a new scale.
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], string="Priority", default='1')

    scheduled_date = fields.Datetime(string="Scheduled For", tracking=True,
                                      help="When the worker is expected to do this.")
    date_assigned = fields.Datetime(string="Assigned On", readonly=True, copy=False)
    date_start = fields.Datetime(string="Started On", readonly=True, copy=False)
    date_end = fields.Datetime(string="Finished On", readonly=True, copy=False)

    time_log_ids = fields.One2many('maintenance.university.request.time', 'request_id', string="Time Log")
    # Overrides core's own duration (a static schedule_end - schedule_date
    # estimate) with the real sum of logged time segments — same field slot,
    # our own compute, rather than a second "actual_duration" field.
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

    # Our familiar new/assigned/in_progress/paused/done/cancelled vocabulary,
    # derived from the real stage_id + kanban_state core provides rather than
    # an independently-writable column. "Paused" isn't its own stage — it's
    # kanban_state='blocked' while the card stays in "In Progress", since a
    # pause isn't really a different pipeline step. Stored so every existing
    # domain/filter/search that reads state keeps working unchanged.
    state = fields.Selection([
        ('new', 'New'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('paused', 'Paused'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string="Status", compute='_compute_state', store=True, tracking=True)

    def _stage(self, key):
        return self.env.ref(_STAGE_XMLIDS[key])

    @api.model
    def _default_stage_id(self):
        return self._stage('new')

    @api.model
    def _default_maintenance_team_id(self):
        return self.env.ref('maintenance_university.maintenance_team_university')

    stage_id = fields.Many2one(default=_default_stage_id)
    maintenance_team_id = fields.Many2one(default=_default_maintenance_team_id)

    @api.depends('stage_id', 'kanban_state')
    def _compute_state(self):
        stage_done = self._stage('done')
        stage_cancelled = self._stage('cancelled')
        stage_in_progress = self._stage('in_progress')
        stage_assigned = self._stage('assigned')
        for rec in self:
            if rec.stage_id == stage_done:
                rec.state = 'done'
            elif rec.stage_id == stage_cancelled:
                rec.state = 'cancelled'
            elif rec.stage_id == stage_in_progress:
                rec.state = 'paused' if rec.kanban_state == 'blocked' else 'in_progress'
            elif rec.stage_id == stage_assigned:
                rec.state = 'assigned'
            else:
                rec.state = 'new'

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

    @api.model_create_multi
    def create(self, vals_list):
        # This model is core Odoo's own maintenance.request, so base.group_user
        # already grants every internal user create/unlink rights via its own
        # ACL — our tighter Manager-only rule has to be enforced here, not
        # left to ir.model.access (which only ever grants, never restricts,
        # across a user's groups).
        if not self.env.user.has_group('maintenance_university.group_maintenance_manager'):
            raise UserError(_("Only a manager can create a maintenance request."))
        return super().create(vals_list)

    def unlink(self):
        if not self.env.user.has_group('maintenance_university.group_maintenance_manager'):
            raise UserError(_("Only a manager can delete a maintenance request."))
        return super().unlink()

    def write(self, vals):
        # Core's own write() makes internal recursive calls on filtered (often
        # empty) subsets of self for its own housekeeping, e.g.
        # self.filtered(lambda m: m.stage_id.done).write({'close_date': ...})
        # — that still routes through this override even when the filtered
        # recordset is empty. Nothing to restrict if there's nothing to write.
        if self and not self.env.user.has_group('maintenance_university.group_maintenance_manager'):
            if set(vals) - WORKER_WRITABLE_FIELDS:
                raise UserError(_("You can only update your own progress on this request, not its details."))
        return super().write(vals)

    def action_assign(self):
        if not self.env.user.has_group('maintenance_university.group_maintenance_manager'):
            raise UserError(_("Only a manager can assign a maintenance request."))
        stage_assigned = self._stage('assigned')
        for rec in self:
            if rec.state in CLOSED_STATES:
                raise UserError(_("A closed request can no longer be assigned."))
            if not rec.employee_ids:
                raise UserError(_("Select at least one worker before assigning the request."))
            rec.write({
                'stage_id': stage_assigned.id,
                'date_assigned': fields.Datetime.now(),
            })

    def action_start(self):
        self._check_is_assigned_worker()
        stage_in_progress = self._stage('in_progress')
        for rec in self:
            if rec.state != 'assigned':
                raise UserError(_("Only an assigned request can be started."))
            rec._open_time_segment()
            vals = {'stage_id': stage_in_progress.id, 'kanban_state': 'normal'}
            if not rec.date_start:
                vals['date_start'] = fields.Datetime.now()
            rec.write(vals)

    def action_resume(self):
        self._check_is_assigned_worker()
        for rec in self:
            if rec.state != 'paused':
                raise UserError(_("Only a paused request can be resumed."))
            rec._open_time_segment()
            rec.kanban_state = 'normal'

    def action_pause(self):
        self._check_is_assigned_worker()
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_("Only a request in progress can be paused."))
            rec._close_open_time_segments()
            rec.kanban_state = 'blocked'

    def action_done(self):
        self._check_is_assigned_worker()
        stage_done = self._stage('done')
        for rec in self:
            if rec.state not in ('in_progress', 'paused'):
                raise UserError(_("Only a request in progress or paused can be completed."))
            rec._close_open_time_segments()
            rec.write({
                'stage_id': stage_done.id,
                'kanban_state': 'normal',
                'date_end': fields.Datetime.now(),
            })

    def action_cancel(self):
        self._check_can_operate()
        stage_cancelled = self._stage('cancelled')
        for rec in self:
            if rec.state in CLOSED_STATES:
                raise UserError(_("This request is already closed."))
            rec._close_open_time_segments()
            rec.write({'stage_id': stage_cancelled.id, 'kanban_state': 'normal'})

    def action_view_findings(self):
        self.ensure_one()
        # Explicit views: maintenance.university.finding now has a second
        # list/form pair (the Reporter's "Report a Problem" screen) sharing
        # the model, so default view resolution is no longer unambiguous —
        # same class of bug already hit twice this session on shared models.
        return {
            'type': 'ir.actions.act_window',
            'name': _("Findings"),
            'res_model': 'maintenance.university.finding',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('maintenance_university.view_maintenance_university_finding_list').id, 'list'),
                (self.env.ref('maintenance_university.view_maintenance_university_finding_form').id, 'form'),
            ],
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
