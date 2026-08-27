from odoo.tests import tagged

from .common import CampusCommon
from .test_car_weights import CAR_EXPECTED


@tagged('post_install', '-at_install')
class TestScoring(CampusCommon):

    def setUp(self):
        super().setUp()
        self.criteria = self._make_full_criteria_set()
        self.version.action_publish()

    # ------------------------------------------------------------------
    # Value types
    # ------------------------------------------------------------------
    def test_scale_lookup_by_code_label_and_alias(self):
        criterion = self.criteria['C1']
        engine = self.env['campus.scoring.engine']
        self.assertEqual(engine._score_scale(criterion, 'prof')[0], 6.0)
        self.assertEqual(engine._score_scale(criterion, 'PROF')[0], 6.0, "matching is case-insensitive")
        self.assertEqual(engine._score_scale(criterion, 'Mcb')[0], 4.0)
        self.assertEqual(engine._score_scale(criterion, 'Prof')[0], 6.0, "the label also matches")
        self.assertEqual(engine._score_scale(criterion, 'nonsense')[0], 0.0,
                         "an unmatched answer scores zero rather than raising")
        self.assertEqual(engine._score_scale(criterion, None)[0], 0.0)

    def test_count_accepts_lists_and_joined_strings(self):
        engine = self.env['campus.scoring.engine']
        criterion = self.criteria['C7']
        self.assertEqual(engine._score_count(criterion, ['a', 'b', 'c'])[0], 3.0)
        self.assertEqual(engine._score_count(criterion, 'a | b')[0], 2.0)
        self.assertEqual(engine._score_count(criterion, 'a، b، c')[0], 3.0,
                         "the original form joined with an Arabic comma")
        self.assertEqual(engine._score_count(criterion, '')[0], 0.0)
        self.assertEqual(engine._score_count(criterion, '—')[0], 0.0)

    def test_count_does_not_split_a_label_containing_a_comma(self):
        """A pipe-joined list wins over an Arabic comma inside one label."""
        engine = self.env['campus.scoring.engine']
        value = 'Zoom، Teams | Moodle'
        self.assertEqual(engine._score_count(self.criteria['C7'], value)[0], 2.0)

    def test_answered_is_presence_only(self):
        engine = self.env['campus.scoring.engine']
        criterion = self.criteria['C12']
        self.assertEqual(engine._score_answered(criterion, 'a real answer')[0], 5.0)
        self.assertEqual(engine._score_answered(criterion, '   ')[0], 0.0)
        self.assertEqual(engine._score_answered(criterion, '—')[0], 0.0)
        self.assertEqual(engine._score_answered(criterion, None)[0], 0.0)

    def test_number_clamps_negatives(self):
        engine = self.env['campus.scoring.engine']
        self.assertEqual(engine._score_number(self.criteria['C3'], -5)[0], 0.0)
        self.assertEqual(engine._score_number(self.criteria['C3'], 'abc')[0], 0.0)
        self.assertEqual(engine._score_number(self.criteria['C3'], '7.5')[0], 7.5)

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------
    def test_years_saturate_at_the_cap(self):
        """The fix for the criterion that used to dominate the ranking."""
        capped = self._make_applicant('Capped', campus_years_exp=60)
        exactly = self._make_applicant('Exactly', campus_years_exp=20)
        (capped | exactly).action_campus_evaluate()

        def c3(applicant):
            return applicant.campus_score_ids.filtered(lambda l: l.code_snapshot == 'C3')

        self.assertEqual(c3(capped).raw_score, 60.0, "the raw answer is preserved")
        self.assertEqual(c3(capped).normalized_score, 1.0, "but it normalizes to the cap")
        self.assertEqual(c3(exactly).normalized_score, 1.0)
        self.assertEqual(capped.campus_final_score, exactly.campus_final_score,
                         "40 extra years beyond the cap must not buy any advantage")

    def test_normalized_score_is_bounded_zero_to_one(self):
        applicant = self._make_applicant('Bounded', campus_years_exp=999)
        applicant.action_campus_evaluate()
        for line in applicant.campus_score_ids:
            self.assertGreaterEqual(line.normalized_score, 0.0)
            self.assertLessEqual(line.normalized_score, 1.0)

    def test_perfect_candidate_scores_one_hundred(self):
        """Every criterion at maximum must total exactly 100."""
        applicant = self._make_applicant('Perfect', **{
            'campus_scientific_rank': 'prof',       # 6/6
            'campus_years_exp': 20,                 # capped 20/20
            'campus_taught_campus': 'yes',          # 5/5
            'campus_camera_confidence': '4',        # 5/5
            'campus_taught_his': 'yes',             # 5/5
            'campus_flipped_knowledge': '4',        # 4/4
            'campus_digital_tools': ['a', 'b', 'c', 'd', 'e', 'f'],   # 6/6
            'campus_teach_methods': ['a', 'b', 'c', 'd', 'e'],        # 5/5
            'campus_concerns_handled': 'yes I did',  # 5/5
            'campus_flipped_def': 'my definition',   # 5/5
        })
        # C5 and C9 are derived from subject experience.
        self.env['campus.application.subject'].create({
            'applicant_id': applicant.id,
            'subject_id': self.math.id,
            'source': 'catalogue',
            'years_exp': 4,
        })
        applicant.action_campus_evaluate()
        self.assertAlmostEqual(applicant.campus_final_score, 100.0, places=6)

    def test_empty_candidate_scores_zero(self):
        applicant = self._make_applicant('Empty')
        applicant.action_campus_evaluate()
        self.assertAlmostEqual(applicant.campus_final_score, 0.0, places=6)

    def test_final_score_equals_sum_of_line_contributions(self):
        applicant = self._make_applicant('Consistent', **{
            'campus_scientific_rank': 'mca',
            'campus_years_exp': 8,
            'campus_flipped_def': 'something',
            'campus_digital_tools': ['a', 'b'],
        })
        applicant.action_campus_evaluate()
        total = sum(applicant.campus_score_ids.mapped('weighted_score')) * 100.0
        self.assertAlmostEqual(applicant.campus_final_score, total, places=6)

    def test_hand_computed_score(self):
        """One candidate worked through by hand, criterion by criterion."""
        applicant = self._make_applicant('Worked Example', **{
            'campus_scientific_rank': 'mcb',        # 4/6
            'campus_years_exp': 10,                 # 10/20
            'campus_taught_campus': 'no',           # 0/5
            'campus_camera_confidence': '3',        # 4/5
            'campus_taught_his': 'yes',             # 5/5
            'campus_flipped_knowledge': '2',        # 2/4
            'campus_digital_tools': ['a', 'b', 'c'],   # 3/6
            'campus_teach_methods': ['a'],             # 1/5
            'campus_concerns_handled': 'handled',      # 5/5
            'campus_flipped_def': 'defined',           # 5/5
        })
        # No subject experience, so both derived criteria are "non" -> 0.
        applicant.action_campus_evaluate()

        expected = 100.0 * sum([
            (4 / 6) * CAR_EXPECTED['C1'],
            (0 / 5) * CAR_EXPECTED['C2'],
            (10 / 20) * CAR_EXPECTED['C3'],
            (4 / 5) * CAR_EXPECTED['C4'],
            (0 / 5) * CAR_EXPECTED['C5'],
            (5 / 5) * CAR_EXPECTED['C6'],
            (3 / 6) * CAR_EXPECTED['C7'],
            (2 / 4) * CAR_EXPECTED['C8'],
            (0 / 5) * CAR_EXPECTED['C9'],
            (1 / 5) * CAR_EXPECTED['C10'],
            (5 / 5) * CAR_EXPECTED['C11'],
            (5 / 5) * CAR_EXPECTED['C12'],
        ])
        # campus_final_score is stored with digits=(16, 4), so compare at a
        # precision the field can actually represent.
        self.assertAlmostEqual(applicant.campus_final_score, expected, places=3)

    def test_unnormalized_reproduces_a_raw_weighted_sum(self):
        """With normalization off the engine is a plain weighted sum of raw scores."""
        version = self.Version.create({
            'name': 'Legacy Mode', 'version': 1,
            'weighting_method': 'legacy_car', 'normalize': False, 'years_cap': 20,
        })
        self._make_full_criteria_set(version=version)
        version.action_publish()

        applicant = self._make_applicant('Legacy', version=version, **{
            'campus_scientific_rank': 'prof',
            'campus_years_exp': 30,
        })
        applicant.action_campus_evaluate()

        lines = {l.code_snapshot: l for l in applicant.campus_score_ids}
        self.assertEqual(lines['C3'].raw_score, 30.0)
        self.assertEqual(lines['C3'].normalized_score, 30.0,
                         "un-normalized keeps the raw value, cap and all")
        expected = sum(l.raw_score * l.weight_snapshot for l in applicant.campus_score_ids)
        self.assertAlmostEqual(applicant.campus_final_score, expected, places=3,
                               msg="no x100 rescale when normalization is off")

    # ------------------------------------------------------------------
    # Snapshots and bookkeeping
    # ------------------------------------------------------------------
    def test_score_lines_snapshot_their_inputs(self):
        applicant = self._make_applicant('Snapshotted', campus_scientific_rank='mca')
        applicant.action_campus_evaluate()
        line = applicant.campus_score_ids.filtered(lambda l: l.code_snapshot == 'C1')
        self.assertEqual(line.name_snapshot, 'Criterion C1')
        self.assertEqual(line.max_score_snapshot, 6.0)
        self.assertAlmostEqual(line.weight_snapshot, CAR_EXPECTED['C1'], places=8)
        self.assertEqual(line.raw_value, 'Mca', "the matched label is stored, not the code")

    def test_evaluation_sets_state_and_metadata(self):
        applicant = self._make_applicant('Metadata')
        self.assertEqual(applicant.campus_state, 'not_started')
        applicant.action_campus_evaluate()
        self.assertEqual(applicant.campus_state, 'evaluated')
        self.assertTrue(applicant.campus_evaluation_date)
        self.assertEqual(applicant.campus_engine_version, 'car-v1')
        self.assertEqual(applicant.campus_weighting_method, 'car')

    def test_re_evaluating_replaces_rather_than_duplicates_lines(self):
        applicant = self._make_applicant('Repeat')
        applicant.action_campus_evaluate()
        applicant.action_campus_evaluate()
        self.assertEqual(len(applicant.campus_score_ids), 12)

    def test_engine_is_selected_by_config_parameter(self):
        """The swap seam: point the parameter elsewhere and that engine runs."""
        self.env['ir.config_parameter'].sudo().set_param(
            'campus_teacher.scoring_engine', 'campus.scoring.engine')
        self.assertEqual(
            self.Applicant._campus_scoring_engine()._name, 'campus.scoring.engine')

        # An unknown model must fall back rather than crash the evaluation.
        self.env['ir.config_parameter'].sudo().set_param(
            'campus_teacher.scoring_engine', 'does.not.exist')
        self.assertEqual(
            self.Applicant._campus_scoring_engine()._name, 'campus.scoring.engine')
