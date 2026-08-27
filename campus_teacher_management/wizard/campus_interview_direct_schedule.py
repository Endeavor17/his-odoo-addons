from odoo import api, fields, models


class CampusInterviewDirectSchedule(models.TransientModel):
    """Book, or reschedule, a specific date/time for one applicant's 1st or
    2nd interview directly — the counterpart to campus.schedule.interview,
    which picks from a pre-generated pool of offered times. All of the actual
    work is delegated to hr.applicant._campus_book_direct_interview, already
    built and tested; this wizard only collects the date/time/interviewer.
    """

    _name = 'campus.interview.direct.schedule'
    _description = 'Campus+ Schedule Interview Directly'

    applicant_id = fields.Many2one('hr.applicant', "Candidate", required=True, readonly=True)
    round = fields.Selection([
        ('1', 'First Interview'),
        ('2', 'Second Interview'),
    ], string="Interview", required=True, readonly=True)

    existing_slot_id = fields.Many2one(
        'campus.interview.slot', "Current Booking", compute='_compute_existing_slot')

    start_datetime = fields.Datetime("Date & Time", required=True)
    duration = fields.Float("Duration", default=0.5, required=True, help="In hours.")
    interviewer_id = fields.Many2one(
        'res.users', "Interviewer", default=lambda self: self.env.user)

    @api.depends('applicant_id', 'round')
    def _compute_existing_slot(self):
        for wizard in self:
            wizard.existing_slot_id = wizard.applicant_id.campus_slot_ids.filtered(
                lambda s: s.round == wizard.round and s.state == 'booked')[:1]

    def action_confirm(self):
        self.ensure_one()
        self.applicant_id._campus_book_direct_interview(
            self.round, self.start_datetime, self.duration, self.interviewer_id)
        return {'type': 'ir.actions.act_window_close'}
