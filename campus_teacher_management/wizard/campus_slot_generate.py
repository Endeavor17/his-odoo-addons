from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Monday is 0 in Python. The working week here runs Sunday to Thursday, so the
# defaults below reflect that rather than a Monday-to-Friday assumption.
WEEKDAY_FIELDS = [
    ('day_sun', 6, 'Sunday'),
    ('day_mon', 0, 'Monday'),
    ('day_tue', 1, 'Tuesday'),
    ('day_wed', 2, 'Wednesday'),
    ('day_thu', 3, 'Thursday'),
    ('day_fri', 4, 'Friday'),
    ('day_sat', 5, 'Saturday'),
]


class CampusSlotGenerate(models.TransientModel):
    """Create a week of interview slots in one screen.

    The admin sets availability weekly, so generating from a pattern beats
    entering twenty rows by hand. Times already on file are skipped, which makes
    the wizard safe to run twice — useful when you add an afternoon after the
    fact.
    """

    _name = 'campus.slot.generate'
    _description = 'Campus+ Generate Interview Slots'

    date_from = fields.Date(
        "Week Starting", required=True,
        default=lambda self: fields.Date.context_today(self))
    date_to = fields.Date(
        "Until", required=True,
        default=lambda self: fields.Date.context_today(self) + timedelta(days=6))

    day_sun = fields.Boolean("Sunday", default=True)
    day_mon = fields.Boolean("Monday", default=True)
    day_tue = fields.Boolean("Tuesday", default=True)
    day_wed = fields.Boolean("Wednesday", default=True)
    day_thu = fields.Boolean("Thursday", default=True)
    day_fri = fields.Boolean("Friday")
    day_sat = fields.Boolean("Saturday")

    time_from = fields.Float("From", default=9.0, required=True, help="09:00 is 9.0, 09:30 is 9.5.")
    time_to = fields.Float("To", default=12.0, required=True)
    duration = fields.Float("Slot Length", default=0.5, required=True, help="In hours.")

    round = fields.Selection([
        ('1', 'First Meeting'),
        ('2', 'Second Meeting'),
        ('any', 'Either'),
    ], string="Meeting", default='1', required=True)
    interviewer_id = fields.Many2one(
        'res.users', "Interviewer", required=True,
        default=lambda self: self.env.user)

    preview = fields.Char("Preview", compute='_compute_preview')

    # ------------------------------------------------------------------
    @api.depends('date_from', 'date_to', 'time_from', 'time_to', 'duration',
                 'day_sun', 'day_mon', 'day_tue', 'day_wed', 'day_thu', 'day_fri', 'day_sat')
    def _compute_preview(self):
        for wizard in self:
            try:
                count = len(wizard._planned_starts())
            except (UserError, ValidationError):
                count = 0
            wizard.preview = _("%s slots will be created", count) if count \
                else _("Nothing to create with these settings")

    @api.constrains('time_from', 'time_to', 'duration')
    def _check_times(self):
        for wizard in self:
            if not 0 <= wizard.time_from < 24 or not 0 < wizard.time_to <= 24:
                raise ValidationError(_("Times must fall inside a single day."))
            if wizard.time_to <= wizard.time_from:
                raise ValidationError(_("The end time must be after the start time."))
            if wizard.duration <= 0:
                raise ValidationError(_("Slot length must be greater than zero."))
            if wizard.duration > (wizard.time_to - wizard.time_from):
                raise ValidationError(_(
                    "A %(len)s hour slot does not fit between %(from)s and %(to)s.",
                    len=wizard.duration, **{'from': wizard.time_from, 'to': wizard.time_to}))

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_to < wizard.date_from:
                raise ValidationError(_("The end date is before the start date."))

    # ------------------------------------------------------------------
    def _selected_weekdays(self):
        return {weekday for fname, weekday, _label in WEEKDAY_FIELDS if self[fname]}

    def _planned_starts(self):
        """Every slot start this wizard would create, as naive UTC datetimes.

        Times are entered in the user's timezone, so they are converted here
        rather than stored as typed — otherwise a 09:00 slot lands at 09:00 UTC
        and shows up at the wrong hour on the calendar.
        """
        self.ensure_one()
        weekdays = self._selected_weekdays()
        if not weekdays:
            return []

        starts = []
        day = self.date_from
        while day <= self.date_to:
            if day.weekday() in weekdays:
                cursor = self.time_from
                while cursor + self.duration <= self.time_to + 1e-9:
                    hour = int(cursor)
                    minute = int(round((cursor - hour) * 60))
                    local = datetime.combine(day, time(hour=hour, minute=minute))
                    starts.append(fields.Datetime.to_string(self._to_utc(local)))
                    cursor += self.duration
            day += timedelta(days=1)
        return starts

    def _to_utc(self, naive_local):
        """Interpret a naive datetime as the user's local time and return UTC.

        Odoo stores datetimes in UTC. Without this, a slot typed as 09:00 would be
        saved as 09:00 UTC and show on the calendar at the wrong hour.
        """
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        return tz.localize(naive_local).astimezone(pytz.UTC).replace(tzinfo=None)

    # ------------------------------------------------------------------
    def action_generate(self):
        self.ensure_one()
        if not self._selected_weekdays():
            raise UserError(_("Pick at least one day of the week."))

        Slot = self.env['campus.interview.slot']
        starts = self._planned_starts()
        if not starts:
            raise UserError(_("These settings produce no slots. Check the dates and times."))

        existing = set(Slot.search([
            ('start_datetime', 'in', starts),
            ('interviewer_id', '=', self.interviewer_id.id),
            ('round', '=', self.round),
        ]).mapped(lambda s: fields.Datetime.to_string(s.start_datetime)))

        to_create = [{
            'start_datetime': start,
            'duration': self.duration,
            'round': self.round,
            'interviewer_id': self.interviewer_id.id,
        } for start in starts if start not in existing]

        created = Slot.create(to_create) if to_create else Slot.browse()

        return {
            'type': 'ir.actions.act_window',
            'name': _("Available Slots"),
            'res_model': 'campus.interview.slot',
            'view_mode': 'list,calendar,form',
            'domain': [('id', 'in', created.ids)] if created else [],
            'context': {
                'default_round': self.round,
                'skipped': len(starts) - len(to_create),
            },
        }
