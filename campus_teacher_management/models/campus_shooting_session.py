from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CampusShootingSession(models.Model):
    """One recording session scheduled with a hired teacher.

    Unlike an interview, a candidate can have any number of these, each with
    its own title and description of what to record — so this is a dedicated
    model rather than a third value on ``campus.interview.slot.round``, which
    would force irrelevant fields (title, description, recorded) onto ordinary
    interview bookings.
    """

    _name = 'campus.shooting.session'
    _description = 'Campus+ Shooting Session'
    _order = 'applicant_id, start_datetime, id'

    applicant_id = fields.Many2one(
        'hr.applicant', "Application", required=True, ondelete='cascade', index=True)
    program_id = fields.Many2one(
        'campus.shooting.program', "Shooting Program", required=True, ondelete='cascade',
        index=True, help="The teacher's own container for their recording sessions. "
        "Filled in automatically from the Application if not set explicitly.")

    title = fields.Char("Recording Title", required=True)
    description = fields.Text(
        "Description", required=True,
        help="What the teacher needs to record during this session. Sent to them by email.")

    start_datetime = fields.Datetime("Start", required=True, index=True)
    duration = fields.Float("Duration", default=1.0, required=True, help="In hours.")
    end_datetime = fields.Datetime("End", compute='_compute_end_datetime', store=True)

    confirmed = fields.Boolean("Confirmed", default=False, copy=False)
    confirmed_date = fields.Datetime("Confirmed On", readonly=True, copy=False)
    recorded = fields.Boolean("Recorded", default=False, copy=False)
    recorded_date = fields.Datetime("Recorded On", readonly=True, copy=False)

    event_id = fields.Many2one(
        'calendar.event', "Calendar Entry", readonly=True, copy=False, ondelete='set null')
    sequence = fields.Integer("Sequence", default=10)

    campus_can_execute_process = fields.Boolean(compute='_compute_campus_process_access')
    campus_can_validate_process = fields.Boolean(compute='_compute_campus_process_access')

    def _compute_campus_process_access(self):
        Permission = self.env['campus.process.permission']
        can_execute = Permission._has_process_permission('shooting', 'execute')
        can_validate = Permission._has_process_permission('shooting', 'validate')
        for session in self:
            session.campus_can_execute_process = can_execute
            session.campus_can_validate_process = can_validate

    # Fields that, if changed, mean the teacher needs a fresh email — a rename
    # of internal notes elsewhere on the record must not spam them.
    _EMAIL_RELEVANT_FIELDS = ('title', 'description', 'start_datetime', 'duration')

    # ------------------------------------------------------------------
    @api.depends('start_datetime', 'duration')
    def _compute_end_datetime(self):
        for session in self:
            if session.start_datetime and session.duration:
                session.end_datetime = session.start_datetime + timedelta(hours=session.duration)
            else:
                session.end_datetime = session.start_datetime

    @api.constrains('duration')
    def _check_duration(self):
        for session in self:
            if session.duration <= 0:
                raise ValidationError(_("A session must last longer than zero."))

    @api.depends('title', 'start_datetime')
    def _compute_display_name(self):
        for session in self:
            if not session.start_datetime:
                session.display_name = session.title or _("New session")
                continue
            start = fields.Datetime.context_timestamp(session, session.start_datetime)
            session.display_name = f"{session.title} · {start.strftime('%a %d %b · %H:%M')}"

    # ------------------------------------------------------------------
    # Calendar + email
    # ------------------------------------------------------------------
    def _sync_calendar_event(self):
        """Create or update the calendar entry so the session shows on a
        real calendar, the same way a booked interview slot does."""
        for session in self:
            values = {
                'name': _("Shooting — %s", session.title),
                'start': session.start_datetime,
                'stop': session.end_datetime,
                'duration': session.duration,
                'applicant_id': session.applicant_id.id,
                'res_model': 'hr.applicant',
                'res_id': session.applicant_id.id,
                'description': session.description,
            }
            if session.event_id:
                session.event_id.write(values)
            else:
                event = self.env['calendar.event'].with_context(
                    no_mail_to_attendees=True, mail_create_nolog=True,
                ).create(values)
                session.event_id = event.id

    def _campus_send_own_template(self, xmlid):
        """Render a template against THIS session, not the applicant.

        An applicant can have several sessions, so "which one was just created
        or changed" only means something if the email is rendered against this
        specific row — routing through hr.applicant._campus_send_template would
        leave the template unable to tell which session it is describing.
        Mirrors that method's own checks.
        """
        self.ensure_one()
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            raise UserError(_("The email template %s is missing. Reinstall the module.", xmlid))
        if not self.applicant_id.email_from:
            raise UserError(_("%s has no email address to write to.", self.applicant_id.display_name))
        template.send_mail(self.id, force_send=False)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        self.env['campus.process.permission']._check_process_permission('shooting', 'execute')
        Program = self.env['campus.shooting.program']
        Applicant = self.env['hr.applicant']
        for vals in vals_list:
            if not vals.get('program_id') and vals.get('applicant_id'):
                vals['program_id'] = Program._get_or_create_for_applicant(
                    Applicant.browse(vals['applicant_id'])).id
        sessions = super().create(vals_list)
        sessions._sync_calendar_event()
        for session in sessions:
            session._campus_send_own_template(
                'campus_teacher_management.mail_template_campus_shooting_created')
            session.applicant_id.message_post(body=_(
                "Shooting session '%s' scheduled for %s.",
                session.title, session.display_name))
        return sessions

    def write(self, vals):
        watched = set(self._EMAIL_RELEVANT_FIELDS) & set(vals)
        old_values = {s.id: {f: s[f] for f in watched} for s in self} if watched else {}

        result = super().write(vals)

        if watched:
            self._sync_calendar_event()
            for session in self:
                if any(old_values[session.id][f] != session[f] for f in watched):
                    session._campus_send_own_template(
                        'campus_teacher_management.mail_template_campus_shooting_modified')
                    session.applicant_id.message_post(body=_(
                        "Shooting session '%s' updated.", session.title))
        return result

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def action_confirm(self):
        self.env['campus.process.permission']._check_process_permission('shooting', 'execute')
        self.write({'confirmed': True, 'confirmed_date': fields.Datetime.now()})
        return True

    def action_mark_recorded(self):
        self.env['campus.process.permission']._check_process_permission('shooting', 'validate')
        self.write({'recorded': True, 'recorded_date': fields.Datetime.now()})
        return True
