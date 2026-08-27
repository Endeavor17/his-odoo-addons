from odoo import api, fields, models


class CampusSubject(models.Model):
    """A teachable subject from the Campus+ catalogue.

    Mirrors the ``subjects`` array the web form renders, so the form can fetch
    the list from Odoo instead of hard-coding it and the ids on both sides stay
    in step.
    """

    _name = 'campus.subject'
    _description = 'Campus+ Subject'
    _order = 'sequence, code, id'

    name = fields.Char("Subject", required=True, translate=True)
    code = fields.Char(
        "External Code", index=True, copy=False,
        help="Identifier used by the web form. Kept stable so submissions keep "
             "resolving to the same subject even if the label is edited.")
    sequence = fields.Integer("Sequence", default=10)
    level = fields.Selection([
        ('L1', 'L1'), ('L2', 'L2'), ('L3', 'L3'),
        ('M1', 'M1'), ('M2', 'M2'),
    ], string="Level", index=True)
    track = fields.Char("Track / Speciality", translate=True)
    language = fields.Selection([
        ('AR', 'Arabic'),
        ('FR', 'French'),
        ('EN', 'English'),
        ('MIX', 'Mixed'),
    ], string="Language", default='AR', index=True)
    active = fields.Boolean("Active", default=True)

    application_count = fields.Integer("Applications", compute='_compute_application_count')

    _code_uniq = models.Constraint(
        'unique(code)',
        'Another subject already uses this external code.',
    )

    @api.depends('name')
    def _compute_application_count(self):
        data = self.env['campus.application.subject']._read_group(
            [('subject_id', 'in', self.ids)], ['subject_id'], ['__count'])
        counts = {subject.id: count for subject, count in data}
        for subject in self:
            subject.application_count = counts.get(subject.id, 0)

    @api.depends('name', 'level')
    def _compute_display_name(self):
        for subject in self:
            subject.display_name = f"[{subject.level}] {subject.name}" if subject.level else subject.name
