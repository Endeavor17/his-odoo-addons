from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CampusEvaluationVersion(models.Model):
    """A frozen set of criteria, scales and priorities.

    Everything that decides a score lives under a version. Publishing one makes
    it read-only, so next year's barème changes cannot silently re-score last
    year's candidates. To change a published set you create a new version, which
    copies the criteria into a fresh draft.
    """

    _name = 'campus.evaluation.version'
    _description = 'Campus+ Evaluation Version'
    _inherit = ['mail.thread']
    _order = 'sequence, version desc, id desc'

    name = fields.Char("Name", required=True, tracking=True)
    sequence = fields.Integer("Sequence", default=10)
    version = fields.Integer("Version", default=1, required=True, tracking=True)
    origin_id = fields.Many2one(
        'campus.evaluation.version', "Original", copy=False, index='btree_not_null',
        help="First version of this chain. Versions sharing an origin are successive "
             "revisions of the same evaluation set.")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('closed', 'Closed'),
    ], string="Status", default='draft', required=True, tracking=True, copy=False)
    active = fields.Boolean("Active", default=True)

    description = fields.Html("Description")
    date_published = fields.Datetime("Published On", readonly=True, copy=False)
    date_closed = fields.Datetime("Closed On", readonly=True, copy=False)

    weighting_method = fields.Selection([
        ('car', 'CAR (corrected)'),
        ('legacy_car', 'CAR (legacy, index reversal)'),
    ], string="Weighting Method", default='car', required=True, tracking=True,
        help="How criterion weights are derived from priorities.\n\n"
             "CAR (corrected): priorities are accumulated in ascending order, so "
             "criteria with equal priority always receive equal weight.\n\n"
             "CAR (legacy): reproduces the original spreadsheet implementation, which "
             "reverses the accumulator by index. Criteria with equal priority can end "
             "up with different weights. Kept so historical rankings reproduce exactly.")
    normalize = fields.Boolean(
        "Normalize Scores", default=True,
        help="Divide each criterion's raw score by its maximum before weighting, so a "
             "weight of 0.13 really means 13% of the final score. Without this, "
             "unbounded criteria such as years of experience dominate the ranking.")
    years_cap = fields.Integer(
        "Years of Experience Cap", default=20,
        help="Years counted at full value before the criterion saturates. Only used by "
             "number-type criteria that declare this version's cap as their maximum.")

    job_id = fields.Many2one(
        'hr.job', "Job Position",
        help="Applied to every application that arrives through this campaign.\n\n"
             "Odoo only assigns a recruitment stage to an applicant that has a job "
             "position, so without this an incoming application lands with no stage "
             "and never appears in the recruitment pipeline.")

    criterion_ids = fields.One2many(
        'campus.criterion', 'version_id', "Criteria", copy=True)
    criterion_count = fields.Integer("Criteria Count", compute='_compute_counts')
    application_count = fields.Integer("Applications", compute='_compute_counts')
    total_weight = fields.Float("Total Weight", compute='_compute_total_weight', digits=(16, 6))

    _name_version_uniq = models.Constraint(
        'unique(name, version)',
        'An evaluation version with this name and version number already exists.',
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('criterion_ids')
    def _compute_counts(self):
        criterion_data = self.env['campus.criterion']._read_group(
            [('version_id', 'in', self.ids)], ['version_id'], ['__count'])
        criterion_map = {version.id: count for version, count in criterion_data}

        applicant_data = self.env['hr.applicant'].sudo()._read_group(
            [('campus_version_id', 'in', self.ids)], ['campus_version_id'], ['__count'])
        applicant_map = {version.id: count for version, count in applicant_data}

        for version in self:
            version.criterion_count = criterion_map.get(version.id, 0)
            version.application_count = applicant_map.get(version.id, 0)

    @api.depends('criterion_ids.weight')
    def _compute_total_weight(self):
        for version in self:
            version.total_weight = sum(version.criterion_ids.mapped('weight'))

    # ------------------------------------------------------------------
    # Immutability
    # ------------------------------------------------------------------
    def _check_editable(self, what=None):
        """Raise if any version in self is not a draft.

        Called from the criterion and scale models too, which is why the message
        names the offending record rather than assuming it is a version.
        """
        locked = self.filtered(lambda v: v.state != 'draft')
        if locked:
            raise UserError(_(
                "%(what)s cannot be changed because the evaluation version "
                "'%(version)s' is %(state)s.\n\n"
                "Use 'New Version' to create an editable copy. Changing a published "
                "set in place would silently re-score candidates who already applied "
                "under it.",
                what=what or _("This record"),
                version=locked[0].display_name,
                state=dict(self._fields['state'].selection).get(locked[0].state),
            ))

    def write(self, vals):
        # Fields that alter scoring are frozen once published; housekeeping
        # fields (sequence, description, active, state itself) stay editable.
        scoring_fields = {'weighting_method', 'normalize', 'years_cap', 'criterion_ids',
                          'version', 'origin_id'}
        if scoring_fields.intersection(vals):
            self._check_editable(_("Scoring settings"))
        return super().write(vals)

    def unlink(self):
        if any(version.state != 'draft' for version in self):
            raise UserError(_("Only draft evaluation versions can be deleted. "
                              "Archive or close the others instead."))
        if any(version.application_count for version in self):
            raise UserError(_("This evaluation version already has applications and "
                              "cannot be deleted."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_publish(self):
        for version in self:
            if version.state != 'draft':
                raise UserError(_("Only a draft version can be published."))
            if not version.criterion_ids:
                raise UserError(_("Add at least one criterion before publishing."))
            version.criterion_ids._validate_for_publish()
            version.write({'state': 'published', 'date_published': fields.Datetime.now()})
            version.message_post(body=_("Evaluation version published. Criteria and scales are now read-only."))
        # Weights are stored, so recompute once here rather than on every read.
        self.criterion_ids._recompute_weights()
        return True

    def action_close(self):
        for version in self:
            if version.state != 'published':
                raise UserError(_("Only a published version can be closed."))
        self.write({'state': 'closed', 'date_closed': fields.Datetime.now()})
        return True

    def action_new_version(self):
        self.ensure_one()
        chain_origin = self.origin_id or self
        latest = self.search([('origin_id', '=', chain_origin.id)], order='version desc', limit=1)
        next_version = max(latest.version if latest else 0, chain_origin.version) + 1
        copy = self.copy({
            'name': self.name,
            'version': next_version,
            'origin_id': chain_origin.id,
            'state': 'draft',
            'date_published': False,
            'date_closed': False,
        })
        copy.message_post(body=_("Created as a new version of %s v%s.", self.name, self.version))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'campus.evaluation.version',
            'res_id': copy.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_recompute_weights(self):
        self.criterion_ids._recompute_weights()
        return True

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------
    def _campus_recompute_ranks(self):
        """Renumber every evaluated application in these versions.

        Done as one window function per version rather than a stored compute.
        A compute would have to load and write every sibling each time a single
        score changed, which is O(n) writes per record and collapses well before
        the thousands of applications this is meant to hold. RANK() also gives
        the ranking semantics we want for free: tied scores share a rank and the
        next one skips (1, 2, 2, 4).
        """
        # Scores are written through the ORM, which batches and flushes lazily.
        # Raw SQL bypasses that cache, so without this the UPDATE reads the
        # pre-evaluation rows: every applicant still looks 'not_started', the
        # subquery matches nothing and every rank stays unset.
        self.env['hr.applicant'].flush_model([
            'campus_final_score', 'campus_state', 'campus_version_id',
            'campus_rank', 'active',
        ])
        for version in self:
            self.env.cr.execute("""
                UPDATE hr_applicant a
                   SET campus_rank = r.rnk
                  FROM (
                        SELECT id,
                               -- Order by score ALONE. Adding id as a tiebreaker
                               -- would make every row distinct to the window and
                               -- RANK() would never award a shared rank.
                               RANK() OVER (ORDER BY campus_final_score DESC NULLS LAST)
                          FROM hr_applicant
                         WHERE campus_version_id = %s
                           AND campus_state <> 'not_started'
                           AND active = TRUE
                       ) AS r(id, rnk)
                 WHERE a.id = r.id
                   AND a.campus_rank IS DISTINCT FROM r.rnk
            """, (version.id,))
        # The rows were changed behind the ORM's back; drop the stale cache.
        self.env['hr.applicant'].invalidate_model(['campus_rank'])
        return True

    def action_recompute_ranks(self):
        return self._campus_recompute_ranks()

    def action_evaluate_all(self):
        """Re-score every unlocked application in these versions."""
        applicants = self.env['hr.applicant'].search([
            ('campus_version_id', 'in', self.ids),
            ('campus_locked', '=', False),
        ])
        if not applicants:
            raise UserError(_("There are no unlocked applications to evaluate."))
        applicants.action_campus_evaluate()
        return True

    def action_view_applications(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Applications"),
            'res_model': 'hr.applicant',
            'view_mode': 'list,form',
            'domain': [('campus_version_id', '=', self.id)],
            'context': {'default_campus_version_id': self.id},
        }

    @api.constrains('years_cap')
    def _check_years_cap(self):
        for version in self:
            if version.years_cap <= 0:
                raise ValidationError(_("The years of experience cap must be greater than zero."))

    @api.depends('name', 'version')
    def _compute_display_name(self):
        for version in self:
            version.display_name = f"{version.name} (v{version.version})"
