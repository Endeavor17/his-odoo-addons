from odoo.tests import tagged

from .common import CampusCommon


@tagged('post_install', '-at_install')
class TestRanking(CampusCommon):

    def setUp(self):
        super().setUp()
        self._make_full_criteria_set()
        self.version.action_publish()

    def _candidate(self, name, rank_code):
        return self._make_applicant(name, campus_scientific_rank=rank_code)

    def test_ranks_are_assigned_in_descending_score_order(self):
        top = self._candidate('Top', 'prof')       # 6
        middle = self._candidate('Middle', 'mcb')  # 4
        bottom = self._candidate('Bottom', 'mab')  # 2
        (top | middle | bottom).action_campus_evaluate()

        self.assertEqual(top.campus_rank, 1)
        self.assertEqual(middle.campus_rank, 2)
        self.assertEqual(bottom.campus_rank, 3)
        self.assertGreater(top.campus_final_score, middle.campus_final_score)
        self.assertGreater(middle.campus_final_score, bottom.campus_final_score)

    def test_ties_share_a_rank_and_the_next_one_skips(self):
        """Standard competition ranking: 1, 2, 2, 4."""
        first = self._candidate('First', 'prof')
        tie_a = self._candidate('Tie A', 'mcb')
        tie_b = self._candidate('Tie B', 'mcb')
        last = self._candidate('Last', 'mab')
        (first | tie_a | tie_b | last).action_campus_evaluate()

        self.assertEqual(first.campus_rank, 1)
        self.assertEqual(tie_a.campus_rank, 2)
        self.assertEqual(tie_b.campus_rank, 2, "equal scores must share a rank")
        self.assertEqual(last.campus_rank, 4, "the rank after a two-way tie is 4, not 3")

    def test_ranking_is_scoped_to_the_version(self):
        """Two campaigns each get their own 1..N."""
        other = self.Version.create({
            'name': 'Other Campaign', 'version': 1,
            'weighting_method': 'car', 'normalize': True, 'years_cap': 20,
        })
        self._make_full_criteria_set(version=other)
        other.action_publish()

        a1 = self._candidate('A1', 'prof')
        a2 = self._candidate('A2', 'mab')
        b1 = self._make_applicant('B1', version=other, campus_scientific_rank='mcb')
        (a1 | a2 | b1).action_campus_evaluate()

        self.assertEqual(a1.campus_rank, 1)
        self.assertEqual(a2.campus_rank, 2)
        self.assertEqual(b1.campus_rank, 1, "a separate campaign restarts at 1")

    def test_unevaluated_applications_are_not_ranked(self):
        scored = self._candidate('Scored', 'prof')
        unscored = self._make_applicant('Unscored')
        scored.action_campus_evaluate()

        self.assertEqual(scored.campus_rank, 1)
        self.assertEqual(unscored.campus_rank, 0,
                         "an application that was never evaluated stays unranked")

    def test_archived_applications_are_excluded(self):
        keep = self._candidate('Keep', 'mcb')
        refused = self._candidate('Refused', 'prof')
        (keep | refused).action_campus_evaluate()
        self.assertEqual(keep.campus_rank, 2)

        refused.active = False
        self.version.action_recompute_ranks()
        keep.invalidate_recordset(['campus_rank'])
        self.assertEqual(keep.campus_rank, 1,
                         "archiving the leader should promote everyone below")

    def test_ranks_refresh_when_a_score_changes(self):
        leader = self._candidate('Leader', 'prof')
        follower = self._candidate('Follower', 'mab')
        (leader | follower).action_campus_evaluate()
        self.assertEqual(leader.campus_rank, 1)

        # The follower gains a lot of experience and overtakes.
        follower.campus_years_exp = 20
        follower.campus_taught_his = 'yes'
        follower.campus_taught_campus = 'yes'
        follower.campus_flipped_def = 'a definition'
        follower.campus_concerns_handled = 'handled'
        (leader | follower).action_campus_evaluate()

        leader.invalidate_recordset(['campus_rank'])
        follower.invalidate_recordset(['campus_rank'])
        self.assertEqual(follower.campus_rank, 1)
        self.assertEqual(leader.campus_rank, 2)
