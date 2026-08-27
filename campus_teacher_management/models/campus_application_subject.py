from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CampusApplicationSubject(models.Model):
    """A subject the candidate asked to teach, and whether we granted it.

    Two roles in one model: ``is_wished`` records what the candidate selected on
    the form, ``is_accepted`` records what the recruiter assigned after
    acceptance. Keeping both on one row means you can always see the gap between
    what someone asked for and what they got.
    """

    _name = 'campus.application.subject'
    _description = 'Campus+ Application Subject'
    _order = 'applicant_id, source, sequence, id'

    applicant_id = fields.Many2one(
        'hr.applicant', "Application", required=True, ondelete='cascade', index=True)
    subject_id = fields.Many2one(
        'campus.subject', "Subject", ondelete='restrict', index='btree_not_null')
    subject_name = fields.Char(
        "Subject Name",
        help="Free text, used when the candidate typed a subject that is not in the "
             "catalogue (the 'subjects I want to teach at HIS' list).")
    display_subject = fields.Char("Subject Label", compute='_compute_display_subject', store=True)

    source = fields.Selection([
        ('catalogue', 'Selected from catalogue'),
        ('free', 'Proposed by candidate'),
    ], string="Source", default='catalogue', required=True, index=True)

    years_exp = fields.Float("Years of Experience", digits=(16, 1))
    sequence = fields.Integer("Sequence", default=10)

    is_wished = fields.Boolean(
        "Requested", default=True,
        help="The candidate asked to teach this subject.")
    is_accepted = fields.Boolean(
        "Accepted", default=False,
        help="Assigned to the candidate after acceptance.")
    selected_by = fields.Many2one(
        'res.users', "Selected By", readonly=True, copy=False,
        help="Who granted this subject. Stamped automatically when Accepted is ticked.")
    selected_date = fields.Datetime("Selected On", readonly=True, copy=False)

    def write(self, vals):
        # Stamp who/when a subject was granted, without requiring a separate
        # action — ticking the box on the applicant's Subjects tab is the act.
        if vals.get('is_accepted') and 'selected_by' not in vals:
            vals = dict(vals, selected_by=self.env.user.id, selected_date=fields.Datetime.now())
        elif vals.get('is_accepted') is False:
            vals = dict(vals, selected_by=False, selected_date=False)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_accepted') and not vals.get('selected_by'):
                vals['selected_by'] = self.env.user.id
                vals['selected_date'] = fields.Datetime.now()
        return super().create(vals_list)

    @api.depends('subject_id', 'subject_name')
    def _compute_display_subject(self):
        for line in self:
            line.display_subject = line.subject_id.display_name or line.subject_name or ''

    @api.constrains('subject_id', 'subject_name')
    def _check_subject(self):
        for line in self:
            if not line.subject_id and not (line.subject_name or '').strip():
                raise ValidationError(_(
                    "A subject line needs either a catalogue subject or a name."))

    @api.constrains('years_exp')
    def _check_years(self):
        for line in self:
            if line.years_exp < 0:
                raise ValidationError(_("Years of experience cannot be negative."))

    @api.depends('display_subject')
    def _compute_display_name(self):
        for line in self:
            line.display_name = line.display_subject
