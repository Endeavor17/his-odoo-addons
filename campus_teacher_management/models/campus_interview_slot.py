from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CampusInterviewSlot(models.Model):
    """One interview time the institute is offering.

    The admin creates a week of these; the offered times are listed in the email
    the candidate receives. The candidate replies by email with the one they
    want, and the admin books it here. There is deliberately no self-service
    booking page — that was the user's decision, and it keeps the whole flow
    inside Odoo where it can be audited.
    """

    _name = 'campus.interview.slot'
    _description = 'Campus+ Interview Slot'
    _order = 'start_datetime, id'

    start_datetime = fields.Datetime("Start", required=True, index=True)
    duration = fields.Float(
        "Duration", default=0.5, required=True,
        help="In hours. 0.5 is thirty minutes.")
    end_datetime = fields.Datetime(
        "End", compute='_compute_end_datetime', store=True)

    round = fields.Selection([
        ('1', 'First Meeting'),
        ('2', 'Second Meeting'),
        ('any', 'Either'),
    ], string="Meeting", default='1', required=True, index=True,
        help="Which meeting this time is offered for. 'Either' can be booked for both.")

    interviewer_id = fields.Many2one(
        'res.users', "Interviewer", default=lambda self: self.env.user,
        help="Invited to the meeting when the slot is booked.")

    state = fields.Selection([
        ('free', 'Available'),
        ('booked', 'Booked'),
        ('cancelled', 'Cancelled'),
    ], string="Status", default='free', required=True, index=True, copy=False)

    applicant_id = fields.Many2one(
        'hr.applicant', "Booked For", readonly=True, copy=False,
        ondelete='set null', index='btree_not_null')
    event_id = fields.Many2one(
        'calendar.event', "Calendar Entry", readonly=True, copy=False, ondelete='set null')
    active = fields.Boolean("Active", default=True)

    # The candidate confirms by replying to the invitation outside Odoo (same
    # deliberate no-self-service-page decision as booking itself); a recruiter
    # records that reply here. Independent of `state`: a slot can be booked and
    # still awaiting confirmation.
    teacher_confirmed = fields.Boolean("Confirmed by Teacher", default=False, copy=False)
    teacher_confirmed_date = fields.Datetime("Confirmed On", readonly=True, copy=False)

    _start_duration_uniq = models.Constraint(
        'unique(start_datetime, duration, interviewer_id, round)',
        'This interviewer already has a slot at that time for the same meeting.',
    )

    # 'any' slots aren't tied to one specific interview process, so they carry
    # no permission check of their own — only '1'/'2' map to interview1/interview2.
    _ROUND_TO_PROCESS_CODE = {'1': 'interview1', '2': 'interview2'}

    def _campus_check_round_access(self, level):
        for slot in self:
            code = self._ROUND_TO_PROCESS_CODE.get(slot.round)
            if code:
                self.env['campus.process.permission']._check_process_permission(code, level)

    # ------------------------------------------------------------------
    @api.depends('start_datetime', 'duration')
    def _compute_end_datetime(self):
        for slot in self:
            if slot.start_datetime and slot.duration:
                slot.end_datetime = slot.start_datetime + timedelta(hours=slot.duration)
            else:
                slot.end_datetime = slot.start_datetime

    @api.constrains('duration')
    def _check_duration(self):
        for slot in self:
            if slot.duration <= 0:
                raise ValidationError(_("A slot must last longer than zero."))

    @api.depends('start_datetime', 'duration', 'state')
    def _compute_display_name(self):
        for slot in self:
            if not slot.start_datetime:
                slot.display_name = _("New slot")
                continue
            start = fields.Datetime.context_timestamp(slot, slot.start_datetime)
            slot.display_name = start.strftime('%a %d %b · %H:%M')

    # ------------------------------------------------------------------
    # Booking
    # ------------------------------------------------------------------
    def _book(self, applicant):
        """Reserve this slot and create the meeting.

        The interviewer is the only attendee. Odoo emails every attendee
        automatically, and the decision was that the candidate is told their time
        in the recruiter's own email reply, not by Odoo.
        """
        self.ensure_one()
        self._campus_check_round_access('execute')
        if self.state != 'free':
            raise UserError(_(
                "That slot is no longer available — it was taken for %s.",
                self.applicant_id.display_name or _("another candidate")))

        event = self.env['calendar.event'].with_context(
            # Suppress Odoo's own invitation mail; the interviewer sees it in
            # their calendar and the candidate is handled by the recruiter.
            no_mail_to_attendees=True,
            mail_create_nolog=True,
        ).create({
            'name': _("Interview — %s", applicant.partner_name or applicant.display_name),
            'start': self.start_datetime,
            'stop': self.end_datetime,
            'duration': self.duration,
            'applicant_id': applicant.id,
            'res_model': 'hr.applicant',
            'res_id': applicant.id,
            'user_id': self.interviewer_id.id or self.env.user.id,
            'partner_ids': [(6, 0, self.interviewer_id.partner_id.ids)],
            'description': _("Campus+ recruitment interview."),
        })
        self.write({
            'state': 'booked',
            'applicant_id': applicant.id,
            'event_id': event.id,
        })
        return event

    def _reschedule(self, start_datetime, duration=None):
        """Move a booked slot to a new time, updating its calendar entry.

        Confirmation is reset: a "confirmed" flag left over from the old time
        would misrepresent whether the teacher agreed to the *new* one.
        """
        self.ensure_one()
        if self.state != 'booked':
            raise UserError(_("Only a booked slot can be rescheduled."))
        values = {
            'start_datetime': start_datetime,
            'duration': duration if duration is not None else self.duration,
            'teacher_confirmed': False,
            'teacher_confirmed_date': False,
        }
        self.write(values)
        if self.event_id:
            self.event_id.write({'start': self.start_datetime, 'stop': self.end_datetime})
        return True

    def action_confirm(self):
        """Record that the teacher confirmed they will attend."""
        self._campus_check_round_access('execute')
        for slot in self:
            if slot.state != 'booked':
                raise UserError(_("Only a booked slot can be confirmed."))
        self.write({'teacher_confirmed': True, 'teacher_confirmed_date': fields.Datetime.now()})
        return True

    def action_release(self):
        """Free a slot again, removing its meeting."""
        self._campus_check_round_access('execute')
        for slot in self:
            if slot.event_id:
                slot.event_id.unlink()
            slot.write({
                'state': 'free', 'applicant_id': False, 'event_id': False,
                'teacher_confirmed': False, 'teacher_confirmed_date': False,
            })
        return True

    def action_cancel(self):
        self._campus_check_round_access('execute')
        for slot in self:
            if slot.event_id:
                slot.event_id.unlink()
            slot.write({
                'state': 'cancelled', 'applicant_id': False, 'event_id': False,
                'teacher_confirmed': False, 'teacher_confirmed_date': False,
            })
        return True

    def unlink(self):
        if any(slot.state == 'booked' for slot in self):
            raise UserError(_(
                "A booked slot cannot be deleted — release it first, so the meeting "
                "in the calendar goes with it."))
        return super().unlink()

    # ------------------------------------------------------------------
    @api.model
    def _free_slots(self, round_number, limit=20):
        """Available slots for a round, soonest first.

        Used both by the scheduling wizard and by the email templates that list
        the offered times, so the candidate can never be offered a slot the
        recruiter cannot then book.
        """
        return self.search([
            ('state', '=', 'free'),
            ('start_datetime', '>=', fields.Datetime.now()),
            ('round', 'in', [str(round_number), 'any']),
        ], order='start_datetime', limit=limit)
