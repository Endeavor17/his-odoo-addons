from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class CampusCriterion(models.Model):
    """One evaluation criterion (C1..C12) inside a version.

    A criterion knows three things: where its raw answer comes from
    (``source_key``), how that answer becomes a number (``value_type`` plus its
    scale lines), and how important it is (``priority``). The *weight* is never
    typed in — it is derived from the priorities of every criterion in the
    version by the CAR algorithm.
    """

    _name = 'campus.criterion'
    _description = 'Campus+ Evaluation Criterion'
    # Ordered by sequence then id, NOT by code. Two reasons: 'C10' sorts before
    # 'C2' as a string, and — more importantly — legacy_car's output depends on
    # the order criteria are fed to it, so the order has to be the stable,
    # author-controlled one rather than an alphabetical accident.
    _order = 'sequence, id'

    version_id = fields.Many2one(
        'campus.evaluation.version', "Evaluation Version",
        required=True, ondelete='cascade', index=True)
    version_state = fields.Selection(related='version_id.state', store=False)

    code = fields.Char("Code", required=True, help="Stable identifier such as C1. Used by the scoring engine.")
    name = fields.Char("Criterion", required=True, translate=True)
    description = fields.Text("Description", translate=True)
    sequence = fields.Integer("Sequence", default=10)
    active = fields.Boolean("Active", default=True)

    priority = fields.Integer(
        "Priority", default=1, required=True,
        help="Relative importance. Higher means more important. Weights are derived "
             "from these values by the CAR algorithm — do not enter a weight directly.")

    value_type = fields.Selection(
        selection='_selection_value_type', string="Value Type",
        default='scale', required=True,
        help="How the candidate's answer becomes a score.\n"
             "Scale: look the answer up in the scale lines below.\n"
             "Count: score is the number of options the candidate selected.\n"
             "Number: score is the numeric answer itself.\n"
             "Answered: score is the 'answered' value if the candidate wrote "
             "something, otherwise zero.")

    source_key = fields.Char(
        "Source Field", required=True,
        help="Key in the submitted payload that feeds this criterion, e.g. 'yearsExp'. "
             "Change this to re-point a criterion at a different question without "
             "touching any code.")

    max_score = fields.Float(
        "Maximum Score", compute='_compute_max_score', store=True, readonly=False,
        digits=(16, 4),
        help="Score treated as 100% for this criterion. Computed from the scale lines; "
             "set it by hand for count and number criteria.")
    answered_score = fields.Float(
        "Score When Answered", default=5.0, digits=(16, 4),
        help="Only used by 'Answered' criteria: the score given when the candidate "
             "provided any non-empty answer.")
    use_version_years_cap = fields.Boolean(
        "Use Version Years Cap",
        help="For number criteria: take the maximum from the version's years cap "
             "instead of the value above, so one setting drives every year-based "
             "criterion.")

    weight = fields.Float(
        "Weight", digits=(16, 10), readonly=True, copy=False,
        help="Derived from the priorities of all criteria in this version by the CAR "
             "algorithm. Weights across a version always sum to 1.")
    weight_percent = fields.Float(
        "Weight %", compute='_compute_weight_percent', digits=(16, 2))

    scale_ids = fields.One2many(
        'campus.criterion.scale', 'criterion_id', "Scale", copy=True)
    scale_count = fields.Integer("Scale Lines", compute='_compute_scale_count')

    _code_version_uniq = models.Constraint(
        'unique(code, version_id)',
        'Each criterion code must be unique inside an evaluation version.',
    )

    @api.model
    def _selection_value_type(self):
        """Overridable so a future module can add a value type by inheritance."""
        return [
            ('scale', 'Scale (barème)'),
            ('count', 'Count of selected options'),
            ('number', 'Numeric answer'),
            ('answered', 'Answered / not answered'),
        ]

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('scale_ids.score', 'value_type')
    def _compute_max_score(self):
        for criterion in self:
            if criterion.value_type == 'scale' and criterion.scale_ids:
                criterion.max_score = max(criterion.scale_ids.mapped('score'))
            elif criterion.value_type == 'answered':
                criterion.max_score = criterion.answered_score
            elif not criterion.max_score:
                # Count and number criteria have no scale to infer from; leave
                # whatever the administrator set, defaulting to 1 so a missing
                # value can never divide by zero during normalization.
                criterion.max_score = 1.0

    @api.depends('weight')
    def _compute_weight_percent(self):
        for criterion in self:
            criterion.weight_percent = criterion.weight * 100.0

    @api.depends('scale_ids')
    def _compute_scale_count(self):
        data = self.env['campus.criterion.scale']._read_group(
            [('criterion_id', 'in', self.ids)], ['criterion_id'], ['__count'])
        counts = {criterion.id: count for criterion, count in data}
        for criterion in self:
            criterion.scale_count = counts.get(criterion.id, 0)

    def _effective_max_score(self):
        """Maximum used by normalization, honouring the version's years cap."""
        self.ensure_one()
        if self.use_version_years_cap and self.version_id.years_cap:
            return float(self.version_id.years_cap)
        return self.max_score or 1.0

    # ------------------------------------------------------------------
    # CAR weighting
    # ------------------------------------------------------------------
    @api.model
    def _car_weights(self, priorities, method='car'):
        """Return {key: weight} from {key: priority}. Weights sum to 1.

        ``car`` walks the criteria from least to most important, adding the gap
        to the previous priority at each step. Equal priorities add nothing, so
        they always come out with equal weight.

        ``legacy_car`` reproduces the original implementation: it walks from most
        to least important building the same accumulator, then reverses that list
        *by index*. When a group of equally-prioritised criteria straddles a step
        in the accumulator the group gets split across two different weights, and
        which member lands where depends only on dict ordering. It is kept so
        rankings produced before this module can be reproduced exactly.
        """
        if not priorities:
            return {}

        if method == 'legacy_car':
            ordered = sorted(priorities.items(), key=lambda kv: kv[1], reverse=True)
            accumulator = [1.0]
            for index in range(1, len(ordered)):
                gap = ordered[index - 1][1] - ordered[index][1]
                accumulator.append(accumulator[-1] + gap)
            final = list(reversed(accumulator))
        else:
            ordered = sorted(priorities.items(), key=lambda kv: kv[1])
            accumulator = [1.0]
            for index in range(1, len(ordered)):
                gap = ordered[index][1] - ordered[index - 1][1]
                accumulator.append(accumulator[-1] + gap)
            final = accumulator

        total = sum(final)
        if not total:
            # Every criterion equally weighted rather than a division by zero.
            share = 1.0 / len(ordered)
            return {key: share for key, _priority in ordered}
        return {ordered[index][0]: final[index] / total for index in range(len(ordered))}

    def _recompute_weights(self):
        """Recompute stored weights for every version touched by ``self``.

        The search order matters: under ``legacy_car`` the weight a criterion
        receives inside a tie group depends on where it sits in the input, so
        criteria must always be fed in their stable sequence order.
        """
        for version in self.mapped('version_id'):
            criteria = self.search([('version_id', '=', version.id)], order='sequence, id')
            if not criteria:
                continue
            weights = self._car_weights(
                {criterion.id: criterion.priority for criterion in criteria},
                method=version.weighting_method,
            )
            for criterion in criteria:
                new_weight = weights.get(criterion.id, 0.0)
                # digits=(16, 10) on the field, so compare at the same precision
                # the value will be stored at or every pass writes needlessly.
                if float_compare(criterion.weight, new_weight, precision_digits=10) != 0:
                    # Bypass the draft guard: weights are derived data, not
                    # configuration, so recomputing them on a published version
                    # is legitimate and does not change any stored score.
                    super(CampusCriterion, criterion).write({'weight': new_weight})
        return True

    # ------------------------------------------------------------------
    # Immutability + validation
    # ------------------------------------------------------------------
    _SCORING_FIELDS = {
        'code', 'priority', 'value_type', 'source_key', 'max_score',
        'answered_score', 'use_version_years_cap', 'scale_ids', 'version_id', 'active',
    }

    @api.model_create_multi
    def create(self, vals_list):
        criteria = super().create(vals_list)
        criteria.mapped('version_id')._check_editable(_("Criteria"))
        criteria._recompute_weights()
        return criteria

    def write(self, vals):
        if self._SCORING_FIELDS.intersection(vals):
            self.mapped('version_id')._check_editable(_("Criteria"))
        result = super().write(vals)
        if {'priority', 'version_id'}.intersection(vals):
            self._recompute_weights()
        return result

    def unlink(self):
        versions = self.mapped('version_id')
        versions._check_editable(_("Criteria"))
        result = super().unlink()
        versions.criterion_ids._recompute_weights()
        return result

    def _validate_for_publish(self):
        """Structural checks that only make sense once the set is final."""
        for criterion in self:
            if criterion.value_type == 'scale' and len(criterion.scale_ids) < 2:
                raise UserError(_(
                    "Criterion %s needs at least two scale lines before the version "
                    "can be published.", criterion.code))
            if criterion.value_type in ('count', 'number') and not criterion._effective_max_score():
                raise UserError(_(
                    "Criterion %s needs a maximum score so its result can be normalized.",
                    criterion.code))
        return True

    @api.constrains('priority')
    def _check_priority(self):
        for criterion in self:
            if criterion.priority < 0:
                raise ValidationError(_("Criterion priorities cannot be negative."))

    @api.constrains('max_score', 'value_type')
    def _check_max_score(self):
        for criterion in self:
            if criterion.value_type != 'scale' and criterion.max_score <= 0 \
                    and not criterion.use_version_years_cap:
                raise ValidationError(_(
                    "Criterion %s must have a maximum score greater than zero.",
                    criterion.code))

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for criterion in self:
            criterion.display_name = f"{criterion.code} — {criterion.name}" if criterion.code else criterion.name
