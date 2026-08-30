from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CampusCriterionScale(models.Model):
    """One line of a criterion's barème: an answer and the points it is worth.

    Scores live here as configuration data so administrators can change them
    between versions without a code change.
    """

    _name = 'campus.criterion.scale'
    _description = 'Campus+ Criterion Scale'
    _order = 'criterion_id, sequence, id'

    criterion_id = fields.Many2one(
        'campus.criterion', "Criterion", required=True, ondelete='cascade', index=True)
    version_id = fields.Many2one(
        related='criterion_id.version_id', store=True, index=True)

    key = fields.Char(
        "Answer Code", required=True,
        help="Stable code sent by the form, e.g. 'prof' or 'oui'. Matched "
             "case-insensitively. This is what the payload is looked up by — never "
             "the translated label, so renaming the label cannot change a score.")
    name = fields.Char("Label", required=True, translate=True)
    aliases = fields.Char(
        "Aliases",
        help="Comma-separated alternative spellings also accepted for this line, for "
             "payloads that send display text instead of the code (older submissions "
             "and spreadsheet imports).")
    score = fields.Float("Score", required=True, digits=(16, 4))
    sequence = fields.Integer("Sequence", default=10)
    active = fields.Boolean("Active", default=True)

    _key_criterion_uniq = models.Constraint(
        'unique(key, criterion_id)',
        'Each answer code must be unique inside a criterion.',
    )

    def _match_keys(self):
        """Every string that should resolve to this line, lower-cased."""
        self.ensure_one()
        keys = {(self.key or '').strip().lower(), (self.name or '').strip().lower()}
        for alias in (self.aliases or '').split(','):
            alias = alias.strip().lower()
            if alias:
                keys.add(alias)
        return {key for key in keys if key}

    # ------------------------------------------------------------------
    # Immutability: a published version's barème cannot move.
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.mapped('criterion_id.version_id')._check_editable(_("Scale lines"))
        return lines

    def write(self, vals):
        self.mapped('criterion_id.version_id')._check_editable(_("Scale lines"))
        return super().write(vals)

    def unlink(self):
        self.mapped('criterion_id.version_id')._check_editable(_("Scale lines"))
        return super().unlink()

    @api.constrains('score')
    def _check_score(self):
        for line in self:
            if line.score < 0:
                raise ValidationError(_(
                    "Scale scores cannot be negative (criterion %s, answer '%s').",
                    line.criterion_id.code, line.name))
