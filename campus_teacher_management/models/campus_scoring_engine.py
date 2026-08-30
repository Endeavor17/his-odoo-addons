import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class CampusScoringEngine(models.AbstractModel):
    """The scoring pipeline, isolated from models, views and the API.

    An AbstractModel rather than a plain class so another module can replace any
    single step with ``_inherit`` and full ORM access, without this module
    knowing it exists. Which engine runs is data, not code: the config parameter
    ``campus_teacher.scoring_engine`` names the model to instantiate.

        raw answer -> raw score -> normalized -> weighted -> final

    Each arrow is one overridable method. A different algorithm replaces the
    step it disagrees with and inherits the rest.
    """

    _name = 'campus.scoring.engine'
    _description = 'Campus+ Scoring Engine'

    ENGINE_VERSION = 'car-v1'

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def compute_scores(self, applicants):
        """Score a recordset in one pass.

        Returns ``{applicant_id: {'final_score': float, 'lines': [line dicts]}}``.
        Nothing is written here — persisting is the caller's job, which keeps the
        engine usable for previews and "what if" comparisons.
        """
        data = self._collect(applicants)
        data = self._raw_scores(data)
        data = self._normalize(data)
        data = self._apply_weights(data)
        return self._aggregate(data)

    # ------------------------------------------------------------------
    # 1. Collect
    # ------------------------------------------------------------------
    def _collect(self, applicants):
        """Gather each applicant's criteria and answers.

        Criteria are read once per version rather than once per applicant, so
        scoring a thousand candidates stays a handful of queries.
        """
        versions = applicants.mapped('campus_version_id')
        criteria_by_version = {}
        for version in versions:
            criteria = version.criterion_ids.filtered('active').sorted(
                lambda c: (c.sequence, c.code or ''))
            criteria_by_version[version.id] = criteria
            # Weights are stored; make sure they reflect the current priorities
            # before they are read into snapshots.
            criteria._recompute_weights()

        collected = []
        for applicant in applicants:
            version = applicant.campus_version_id
            if not version:
                continue
            payload = applicant._campus_answer_payload()
            collected.append({
                'applicant': applicant,
                'version': version,
                'criteria': criteria_by_version.get(version.id, self.env['campus.criterion']),
                'payload': payload,
                'lines': [],
            })
        return collected

    # ------------------------------------------------------------------
    # 2. Raw scores
    # ------------------------------------------------------------------
    def _raw_scores(self, data):
        for entry in data:
            payload = entry['payload']
            for criterion in entry['criteria']:
                value = payload.get(criterion.source_key)
                raw_score, display = self._criterion_raw_score(criterion, value)
                entry['lines'].append({
                    'criterion': criterion,
                    'raw_value': display,
                    'raw_score': raw_score,
                    'max_score': criterion._effective_max_score(),
                    'normalized_score': 0.0,
                    'weight': criterion.weight,
                    'weighted_score': 0.0,
                })
        return data

    def _criterion_raw_score(self, criterion, value):
        """Turn one raw answer into (score, human-readable value)."""
        handler = getattr(self, f'_score_{criterion.value_type}', None)
        if handler is None:
            _logger.warning(
                "No handler for criterion value type %r (criterion %s); scoring 0.",
                criterion.value_type, criterion.code)
            return 0.0, self._display(value)
        return handler(criterion, value)

    def _score_scale(self, criterion, value):
        """Look the answer up in the barème.

        Matching is on the stable answer code, falling back to the label and any
        aliases, so payloads that send display text (older submissions, imported
        spreadsheet rows) still resolve.
        """
        if value is None or value == '':
            return 0.0, ''
        needle = str(value).strip().lower()
        for line in criterion.scale_ids:
            if needle in line._match_keys():
                return line.score, line.name
        _logger.info(
            "Criterion %s: answer %r matched no scale line; scoring 0.",
            criterion.code, value)
        return 0.0, self._display(value)

    def _score_count(self, criterion, value):
        """Score is how many options the candidate selected."""
        items = self._as_list(value)
        return float(len(items)), ', '.join(str(item) for item in items)

    def _score_number(self, criterion, value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0, self._display(value)
        # Negatives would drag a weighted sum below zero; treat them as absent.
        number = max(number, 0.0)
        return number, self._display(value)

    def _score_answered(self, criterion, value):
        """Presence-only criteria: did the candidate write anything at all."""
        if value is None:
            return 0.0, ''
        if isinstance(value, bool):
            return (criterion.answered_score if value else 0.0), self._display(value)
        if isinstance(value, (list, tuple, set)):
            answered = bool(value)
        else:
            answered = bool(str(value).strip()) and str(value).strip() not in ('—', '-')
        return (criterion.answered_score if answered else 0.0), self._display(value)

    # ------------------------------------------------------------------
    # 3. Normalize
    # ------------------------------------------------------------------
    def _normalize(self, data):
        """Rescale every criterion onto 0..1 so weights mean what they say.

        Without this, an unbounded criterion such as years of experience
        outweighs every bounded one put together regardless of its weight.
        Disabled per version for reproducing pre-Odoo rankings.
        """
        for entry in data:
            normalize = entry['version'].normalize
            for line in entry['lines']:
                if not normalize:
                    line['normalized_score'] = line['raw_score']
                    continue
                maximum = line['max_score'] or 1.0
                line['normalized_score'] = min(max(line['raw_score'] / maximum, 0.0), 1.0)
        return data

    # ------------------------------------------------------------------
    # 4. Weight
    # ------------------------------------------------------------------
    def _apply_weights(self, data):
        for entry in data:
            for line in entry['lines']:
                line['weighted_score'] = line['normalized_score'] * line['weight']
        return data

    # ------------------------------------------------------------------
    # 5. Aggregate
    # ------------------------------------------------------------------
    def _aggregate(self, data):
        results = {}
        for entry in data:
            total = sum(line['weighted_score'] for line in entry['lines'])
            # Normalized weights sum to 1, so the total is a 0..1 fraction —
            # present it as a percentage. Un-normalized totals are left on their
            # own scale so legacy numbers stay comparable to the spreadsheet.
            if entry['version'].normalize:
                total *= 100.0
            results[entry['applicant'].id] = {
                'final_score': total,
                'engine_version': self.ENGINE_VERSION,
                'weighting_method': entry['version'].weighting_method,
                'lines': entry['lines'],
            }
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _as_list(self, value):
        """Accept a real list, or the joined strings older payloads send."""
        if value is None or value == '':
            return []
        if isinstance(value, (list, tuple, set)):
            return [item for item in value if str(item).strip()]
        text = str(value).strip()
        if text in ('—', '-'):
            return []
        # Pipe first: it is the separator this module writes, and it never
        # appears inside a label. The Arabic comma is what the original web form
        # joined with, and some labels contain it, so it must not be tried first.
        for separator in ('|', '،', ','):
            if separator in text:
                return [part.strip() for part in text.split(separator) if part.strip()]
        return [text]

    @api.model
    def _display(self, value):
        if value is None:
            return ''
        if isinstance(value, (list, tuple, set)):
            return ', '.join(str(item) for item in value)
        return str(value)
