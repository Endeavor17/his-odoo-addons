from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import CampusCommon


@tagged('post_install', '-at_install')
class TestVersioning(CampusCommon):
    """The historical guarantee: a published set cannot move under a candidate."""

    def test_publish_freezes_criteria(self):
        criteria = self._make_full_criteria_set()
        self.version.action_publish()
        self.assertEqual(self.version.state, 'published')

        with self.assertRaises(UserError, msg="editing a priority should be blocked"):
            criteria['C1'].priority = 9
        with self.assertRaises(UserError, msg="editing a source field should be blocked"):
            criteria['C1'].source_key = 'somethingElse'
        with self.assertRaises(UserError, msg="editing a scale score should be blocked"):
            criteria['C1'].scale_ids[0].score = 99
        with self.assertRaises(UserError, msg="adding a criterion should be blocked"):
            self._make_criterion('C13', 1, 'answered', 'foo')
        with self.assertRaises(UserError, msg="deleting a criterion should be blocked"):
            criteria['C2'].unlink()

    def test_publish_requires_criteria(self):
        with self.assertRaises(UserError):
            self.version.action_publish()

    def test_publish_requires_two_scale_lines(self):
        self._make_criterion('C1', 1, 'scale', 'rank', scale=[('prof', 6)])
        with self.assertRaises(UserError):
            self.version.action_publish()

    def test_new_version_creates_an_editable_copy(self):
        self._make_full_criteria_set()
        self.version.action_publish()

        action = self.version.action_new_version()
        copy = self.Version.browse(action['res_id'])

        self.assertEqual(copy.state, 'draft')
        self.assertEqual(copy.version, 2)
        self.assertEqual(copy.origin_id, self.version)
        self.assertEqual(len(copy.criterion_ids), 12, "criteria should be copied")
        self.assertEqual(
            len(copy.criterion_ids.filtered(lambda c: c.code == 'C1').scale_ids), 6,
            "scale lines should be copied with their criterion")

        # And the copy is editable again.
        copy.criterion_ids.filtered(lambda c: c.code == 'C1').priority = 9
        self.assertEqual(copy.criterion_ids.filtered(lambda c: c.code == 'C1').priority, 9)
        self.assertEqual(
            self.version.criterion_ids.filtered(lambda c: c.code == 'C1').priority, 3,
            "the published original must be untouched")

    def test_old_scores_survive_a_barème_change(self):
        """The point of the whole versioning design.

        Score a candidate, publish a new version with a different barème, and the
        original score line must still read the same.
        """
        self._make_full_criteria_set()
        self.version.action_publish()

        applicant = self._make_applicant('Historic Candidate', **{
            'campus_scientific_rank': 'mcb',      # scores 4 under v1
            'campus_years_exp': 10,
            'campus_taught_campus': 'no',
            'campus_taught_his': 'no',
            'campus_camera_confidence': '2',
            'campus_flipped_knowledge': '2',
            'campus_digital_tools': ['moodle'],
            'campus_teach_methods': ['onsite'],
        })
        applicant.action_campus_evaluate()

        c1_line = applicant.campus_score_ids.filtered(lambda l: l.code_snapshot == 'C1')
        self.assertEqual(c1_line.raw_score, 4.0)
        original_score = applicant.campus_final_score
        self.assertGreater(original_score, 0)

        # New version, MCB now worth 6 instead of 4.
        action = self.version.action_new_version()
        v2 = self.Version.browse(action['res_id'])
        v2.criterion_ids.filtered(lambda c: c.code == 'C1') \
            .scale_ids.filtered(lambda s: s.key == 'mcb').score = 6
        v2.action_publish()

        applicant.invalidate_recordset()
        self.assertEqual(
            applicant.campus_score_ids.filtered(lambda l: l.code_snapshot == 'C1').raw_score,
            4.0,
            "a published change in a NEW version must not rewrite an old score line")
        self.assertAlmostEqual(applicant.campus_final_score, original_score, places=6)

    def test_locked_application_is_skipped_by_bulk_evaluation(self):
        self._make_full_criteria_set()
        self.version.action_publish()
        applicant = self._make_applicant('Locked One', campus_scientific_rank='prof')
        applicant.action_campus_evaluate()
        score_before = applicant.campus_final_score

        applicant.action_campus_lock()
        self.assertEqual(applicant.campus_state, 'locked')

        # A second, unlocked application so the bulk action has work to do —
        # otherwise it correctly refuses and we never exercise the skip.
        other = self._make_applicant('Unlocked One', campus_scientific_rank='mcb')

        applicant.campus_scientific_rank = 'mab'
        self.version.action_evaluate_all()
        self.assertEqual(other.campus_state, 'evaluated',
                         "the unlocked application should have been scored")
        self.assertEqual(
            applicant.campus_final_score, score_before,
            "a locked application must not be re-scored in bulk")

    def test_version_with_applications_cannot_be_deleted(self):
        self._make_full_criteria_set()
        self.version.action_publish()
        self._make_applicant('Blocker')
        with self.assertRaises(UserError):
            self.version.unlink()
