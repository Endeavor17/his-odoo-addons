from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CampusScheduleInterview(models.TransientModel):
    """Record the time the candidate replied with.

    The candidate answers the invitation by email; the recruiter opens this and
    picks the slot they asked for. Booking it reserves the time, creates the
    meeting in the calendar and moves the candidate to the next step.
    """

    _name = 'campus.schedule.interview'
    _description = 'Campus+ Schedule Interview'

    applicant_id = fields.Many2one(
        'hr.applicant', "Candidate", required=True, readonly=True)
    round = fields.Selection([
        ('1', 'First Meeting'),
        ('2', 'Second Meeting'),
    ], string="Meeting", required=True, readonly=True)

    slot_id = fields.Many2one(
        'campus.interview.slot', "Chosen Time", required=True,
        domain="[('id', 'in', available_slot_ids)]")
    available_slot_ids = fields.Many2many(
        'campus.interview.slot', compute='_compute_available_slot_ids')

    slot_count = fields.Integer("Available", compute='_compute_available_slot_ids')
    interviewer_id = fields.Many2one(
        related='slot_id.interviewer_id', string="Interviewer", readonly=True)

    @api.depends('round')
    def _compute_available_slot_ids(self):
        Slot = self.env['campus.interview.slot']
        for wizard in self:
            slots = Slot._free_slots(wizard.round or '1', limit=200)
            wizard.available_slot_ids = slots
            wizard.slot_count = len(slots)

    def action_confirm(self):
        self.ensure_one()
        if not self.slot_id:
            raise UserError(_("Pick the time the candidate asked for."))

        # _book raises if the slot was taken between opening this wizard and
        # confirming it, which is the race two recruiters can actually hit.
        self.slot_id._book(self.applicant_id)

        self.applicant_id.campus_hiring_state = \
            'meeting_1' if self.round == '1' else 'meeting_2'
        self.applicant_id.message_post(body=_(
            "%(which)s scheduled for %(when)s with %(who)s.",
            which=_("First meeting") if self.round == '1' else _("Second meeting"),
            when=self.slot_id.display_name,
            who=self.slot_id.interviewer_id.name or _("the recruiter"),
        ))
        return {'type': 'ir.actions.act_window_close'}
