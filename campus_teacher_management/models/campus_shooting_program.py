from odoo import api, fields, models


class CampusShootingProgram(models.Model):
    """One teacher's own container for their recording sessions.

    Created automatically the moment a candidate's contract is marked signed
    (see hr.applicant.action_campus_mark_contract_signed) — never by hand —
    so every teacher who reaches Shooting has exactly one of these holding
    all of their campus.shooting.session rows.
    """

    _name = 'campus.shooting.program'
    _description = 'Campus+ Shooting Program'
    _order = 'id'

    applicant_id = fields.Many2one(
        'hr.applicant', "Teacher", required=True, ondelete='cascade', index=True)
    session_ids = fields.One2many(
        'campus.shooting.session', 'program_id', "Shooting Sessions")
    session_count = fields.Integer("Sessions", compute='_compute_counts', store=True)
    recorded_count = fields.Integer("Recorded", compute='_compute_counts', store=True)

    _applicant_uniq = models.Constraint(
        'unique(applicant_id)',
        'This teacher already has a Shooting Program.',
    )

    @api.depends('session_ids.recorded')
    def _compute_counts(self):
        for program in self:
            program.session_count = len(program.session_ids)
            program.recorded_count = len(program.session_ids.filtered('recorded'))

    @api.depends('applicant_id')
    def _compute_display_name(self):
        for program in self:
            program.display_name = f"{program.applicant_id.display_name} — Shooting Program"

    @api.model
    def _get_or_create_for_applicant(self, applicant):
        program = self.search([('applicant_id', '=', applicant.id)], limit=1)
        if not program:
            program = self.create({'applicant_id': applicant.id})
        return program
