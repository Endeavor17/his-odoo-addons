from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MaintenanceUniversityWorkday(models.Model):
    """One worker's presence on one day: arrival, breaks, departure.

    Deliberately not core's hr.attendance. Attendance knows only check-in and
    check-out, so a break there is a check-out followed by a check-in and the
    pause itself is never stored - only inferable as the gap between two rows.
    A break is exactly what this has to record, so it gets its own segment kind
    and its own total.

    This is the worker's *presence*, and it is independent of the time logged
    against individual requests (maintenance.university.request.time). The two
    are meant to differ: the gap between hours present and hours on jobs is
    travel and idle time, which is the interesting number for a leader.
    """

    _name = 'maintenance.university.workday'
    _description = 'Maintenance Work Day'
    _order = 'date desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee', string="Worker", required=True, index=True, ondelete='restrict',
    )
    date = fields.Date(string="Day", required=True, index=True, default=fields.Date.context_today)
    date_start = fields.Datetime(string="Started At", required=True, default=fields.Datetime.now)
    date_end = fields.Datetime(
        string="Ended At", help="Empty while the day is still running.",
    )
    segment_ids = fields.One2many(
        'maintenance.university.workday.segment', 'workday_id', string="Segments",
    )
    worked_hours = fields.Float(
        string="Worked Hours", compute='_compute_hours', store=True,
        help="Time actually worked, breaks excluded.",
    )
    paused_hours = fields.Float(
        string="Break Hours", compute='_compute_hours', store=True,
    )
    # Derived from the segments rather than stored as something writable, the
    # same way maintenance.request.state is derived from its stage: the buttons
    # are the only way through, so the state can never disagree with the log.
    state = fields.Selection(
        [
            ('working', "Working"),
            ('paused', "On Break"),
            ('done', "Finished"),
        ],
        string="Status", compute='_compute_state', store=True, index=True,
    )

    _employee_day_unique = models.Constraint(
        'UNIQUE(employee_id, date)',
        "A worker already has a work day recorded for that date.",
    )
    _dates_ordered = models.Constraint(
        'CHECK (date_end IS NULL OR date_end >= date_start)',
        "A work day cannot end before it starts.",
    )

    @api.depends('segment_ids.duration', 'segment_ids.kind')
    def _compute_hours(self):
        for day in self:
            worked = day.segment_ids.filtered(lambda s: s.kind == 'work')
            paused = day.segment_ids.filtered(lambda s: s.kind == 'pause')
            day.worked_hours = sum(worked.mapped('duration'))
            day.paused_hours = sum(paused.mapped('duration'))

    @api.depends('date_end', 'segment_ids.kind', 'segment_ids.date_end')
    def _compute_state(self):
        for day in self:
            if day.date_end:
                day.state = 'done'
                continue
            open_segment = day.segment_ids.filtered(lambda s: not s.date_end)[:1]
            day.state = 'paused' if open_segment.kind == 'pause' else 'working'

    @api.depends('employee_id', 'date')
    def _compute_display_name(self):
        for day in self:
            day.display_name = f"{day.employee_id.name} - {day.date}" if day.employee_id else _("Work Day")

    # ------------------------------------------------------------------
    # Whose day is it
    # ------------------------------------------------------------------
    @api.model
    def _my_employee(self):
        """The employee record behind the current user.

        sudo() on the search only: a worker is not granted read access to the
        employee directory, but still has to be able to find themselves in it.
        """
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.user.id)], limit=1,
        )
        if not employee:
            raise UserError(_(
                "Your user account is not linked to an employee record, so no "
                "work day can be recorded. Ask a maintenance manager to set one up."
            ))
        return employee

    def _check_is_owner(self):
        """Strictly the worker themselves - no manager bypass.

        Same reasoning as _check_is_assigned_worker on the request: a leader who
        can clock someone in has defeated the point of a presence record.
        """
        for day in self:
            if day.sudo().employee_id.user_id != self.env.user:
                raise UserError(_("You can only clock your own work day."))

    # ------------------------------------------------------------------
    # The four buttons
    #
    # A Worker holds read access and nothing more (see ir.model.access.csv), so
    # every write below runs sudo(). That is the point: a presence record is
    # only worth keeping if the person it measures cannot rewrite it. Left
    # writable, a worker could move date_start back an hour through the API and
    # invent a morning - the record rule scopes them to their own day, which is
    # exactly the day they would want to change.
    #
    # sudo() here does not widen anything: _my_employee() and _check_is_owner()
    # have already established that this is the caller's own day, and each
    # method refuses an illegal transition. Same shape as the meal module's
    # _log_meal_transaction, which sudo()s a create the cashier is allowed to
    # cause but not to perform.
    # ------------------------------------------------------------------
    @api.model
    def action_start_day(self):
        employee = self._my_employee()
        today = fields.Date.context_today(self)
        existing = self.sudo().search(
            [('employee_id', '=', employee.id), ('date', '=', today)], limit=1,
        )
        if existing:
            raise UserError(_(
                "You already started your day at %s.",
                fields.Datetime.to_string(existing.date_start),
            ))
        day = self.sudo().create({
            'employee_id': employee.id,
            'date': today,
            'date_start': fields.Datetime.now(),
        })
        day._open_segment('work')
        return day.get_my_day()

    def action_pause(self):
        self.ensure_one()
        self._check_is_owner()
        if self.state != 'working':
            raise UserError(_("Only a running day can be paused."))
        day = self.sudo()
        day._close_open_segments()
        day._open_segment('pause')
        return self.get_my_day()

    def action_resume(self):
        self.ensure_one()
        self._check_is_owner()
        if self.state != 'paused':
            raise UserError(_("Only a paused day can be resumed."))
        day = self.sudo()
        day._close_open_segments()
        day._open_segment('work')
        return self.get_my_day()

    def action_end_day(self):
        self.ensure_one()
        self._check_is_owner()
        if self.state == 'done':
            raise UserError(_("This day is already finished."))
        day = self.sudo()
        day._close_open_segments()
        day.date_end = fields.Datetime.now()
        return self.get_my_day()

    def _open_segment(self, kind):
        self.ensure_one()
        # Never two open at once: a stale one would be closed later by an
        # unrelated click and inflate the total. Same guard as the request's
        # own _open_time_segment.
        self._close_open_segments()
        return self.env['maintenance.university.workday.segment'].sudo().create({
            'workday_id': self.id,
            'kind': kind,
            'date_start': fields.Datetime.now(),
        })

    def _close_open_segments(self):
        self.ensure_one()
        self.sudo().segment_ids.filtered(lambda s: not s.date_end).write({
            'date_end': fields.Datetime.now(),
        })

    # ------------------------------------------------------------------
    # What the banner reads
    # ------------------------------------------------------------------
    @api.model
    def get_my_day(self):
        """Today's state for the current user, for the My Work banner.

        Seconds rather than hours so the browser can tick a counter locally
        instead of polling the server, and the open segment's own elapsed time
        is included live - a stored duration is only written when a segment
        closes.
        """
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.user.id)], limit=1,
        )
        if not employee:
            return {'has_employee': False}

        today = fields.Date.context_today(self)
        day = self.search(
            [('employee_id', '=', employee.id), ('date', '=', today)], limit=1,
        )
        if not day:
            return {'has_employee': True, 'id': False, 'state': False}

        now = fields.Datetime.now()
        worked = day.worked_hours * 3600.0
        paused = day.paused_hours * 3600.0
        open_segment = day.segment_ids.filtered(lambda s: not s.date_end)[:1]
        if open_segment:
            live = (now - open_segment.date_start).total_seconds()
            if open_segment.kind == 'pause':
                paused += live
            else:
                worked += live

        return {
            'has_employee': True,
            'id': day.id,
            'state': day.state,
            'date_start': fields.Datetime.to_string(day.date_start),
            'date_end': fields.Datetime.to_string(day.date_end) if day.date_end else False,
            'worked_seconds': worked,
            'paused_seconds': paused,
        }


class MaintenanceUniversityWorkdaySegment(models.Model):
    """A stretch of one work day: either working or on a break.

    Same shape as maintenance.university.request.time, down to the duration
    compute - one open-ended row per stretch, closed when the next button is
    pressed.
    """

    _name = 'maintenance.university.workday.segment'
    _description = 'Maintenance Work Day Segment'
    _order = 'date_start'

    workday_id = fields.Many2one(
        'maintenance.university.workday', string="Work Day",
        required=True, ondelete='cascade', index=True,
    )
    employee_id = fields.Many2one(
        related='workday_id.employee_id', string="Worker", store=True, index=True,
    )
    kind = fields.Selection(
        [('work', "Working"), ('pause', "Break")],
        string="Kind", required=True, default='work',
    )
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
