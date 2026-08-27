from odoo import api, fields, models


class CampusApplicationScore(models.Model):
    """One criterion's result for one application, with its inputs snapshotted.

    Every number that produced the score is copied here at evaluation time: the
    criterion code, the scale value, the maximum and the weight. A later version
    can change all of those and this row still explains exactly how the candidate
    was ranked at the time — which is what makes re-scoring safe.
    """

    _name = 'campus.application.score'
    _description = 'Campus+ Application Score Line'
    _order = 'applicant_id, sequence, code_snapshot, id'
    _rec_name = 'code_snapshot'

    applicant_id = fields.Many2one(
        'hr.applicant', "Application", required=True, ondelete='cascade', index=True)
    criterion_id = fields.Many2one(
        'campus.criterion', "Criterion", required=True, ondelete='restrict', index=True,
        help="Restricted on purpose: deleting a criterion must not erase the history "
             "of how past candidates were scored.")
    version_id = fields.Many2one(
        'campus.evaluation.version', "Evaluation Version", index=True, ondelete='restrict')
    sequence = fields.Integer("Sequence", default=10)

    # --- snapshot: written at evaluation, never recomputed -------------
    code_snapshot = fields.Char("Code", readonly=True)
    name_snapshot = fields.Char("Criterion Name", readonly=True)
    raw_value = fields.Char("Answer", readonly=True)
    raw_score = fields.Float("Raw Score", readonly=True, digits=(16, 4))
    max_score_snapshot = fields.Float("Maximum", readonly=True, digits=(16, 4))
    normalized_score = fields.Float("Normalized", readonly=True, digits=(16, 6))
    weight_snapshot = fields.Float("Weight", readonly=True, digits=(16, 10))
    weighted_score = fields.Float("Weighted", readonly=True, digits=(16, 6))
    contribution_percent = fields.Float(
        "Contribution %", compute='_compute_contribution_percent', digits=(16, 2),
        help="Share of this application's final score contributed by this criterion.")

    _applicant_criterion_uniq = models.Constraint(
        'unique(applicant_id, criterion_id)',
        'A criterion can only be scored once per application.',
    )

    @api.depends('weighted_score', 'applicant_id.campus_final_score')
    def _compute_contribution_percent(self):
        for line in self:
            total = line.applicant_id.campus_final_score
            if not total:
                line.contribution_percent = 0.0
            else:
                # weighted_score is a 0..1 fraction while the stored final score
                # is already a percentage, so scale before dividing.
                line.contribution_percent = (line.weighted_score * 100.0) / total * 100.0

    @api.depends('code_snapshot', 'name_snapshot')
    def _compute_display_name(self):
        for line in self:
            line.display_name = f"{line.code_snapshot} — {line.name_snapshot}"
