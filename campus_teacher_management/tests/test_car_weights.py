from odoo.tests import tagged

from .common import PRIORITIES, CampusCommon

# The two weight tables, as exact fractions of their denominators. These are the
# reference values for the whole module: if either changes, rankings change.
LEGACY_EXPECTED = {
    'C1': 4 / 31, 'C5': 4 / 31,
    'C3': 3 / 31, 'C8': 3 / 31, 'C12': 3 / 31,
    'C2': 3 / 31, 'C4': 3 / 31,
    'C7': 2 / 31, 'C9': 2 / 31, 'C11': 2 / 31,
    'C6': 1 / 31, 'C10': 1 / 31,
}
CAR_EXPECTED = {
    'C1': 4 / 29, 'C5': 4 / 29,
    'C3': 3 / 29, 'C8': 3 / 29, 'C12': 3 / 29,
    'C2': 2 / 29, 'C4': 2 / 29, 'C7': 2 / 29, 'C9': 2 / 29, 'C11': 2 / 29,
    'C6': 1 / 29, 'C10': 1 / 29,
}


@tagged('post_install', '-at_install')
class TestCarWeights(CampusCommon):

    def _weights(self, method):
        return self.env['campus.criterion']._car_weights(PRIORITIES, method=method)

    def test_legacy_matches_reference_table(self):
        """legacy_car reproduces the pre-Odoo spreadsheet weights exactly."""
        weights = self._weights('legacy_car')
        for code, expected in LEGACY_EXPECTED.items():
            self.assertAlmostEqual(
                weights[code], expected, places=10,
                msg=f"legacy_car weight for {code} drifted from the reference table")

    def test_car_matches_reference_table(self):
        """The corrected method produces the documented weights."""
        weights = self._weights('car')
        for code, expected in CAR_EXPECTED.items():
            self.assertAlmostEqual(
                weights[code], expected, places=10,
                msg=f"car weight for {code} drifted from the reference table")

    def test_both_methods_sum_to_one(self):
        for method in ('car', 'legacy_car'):
            self.assertAlmostEqual(
                sum(self._weights(method).values()), 1.0, places=10,
                msg=f"{method} weights must sum to 1")

    def test_car_gives_equal_priorities_equal_weight(self):
        """The defect legacy_car has and car does not.

        C2, C4, C7, C9 and C11 all have priority 1. Under legacy_car they split
        into two different weights depending only on dict ordering.
        """
        weights = self._weights('car')
        for priority in set(PRIORITIES.values()):
            group = [code for code, value in PRIORITIES.items() if value == priority]
            distinct = {round(weights[code], 10) for code in group}
            self.assertEqual(
                len(distinct), 1,
                f"criteria with priority {priority} got different weights: "
                f"{ {code: weights[code] for code in group} }")

    def test_legacy_splits_a_tie_group(self):
        """Pin the legacy defect so nobody 'fixes' it and silently changes history."""
        weights = self._weights('legacy_car')
        priority_one = [code for code, value in PRIORITIES.items() if value == 1]
        distinct = {round(weights[code], 10) for code in priority_one}
        self.assertEqual(
            len(distinct), 2,
            "legacy_car is expected to split the priority-1 group in two; if this "
            "changed, historical rankings can no longer be reproduced")

    def test_car_is_monotone_in_priority(self):
        """Higher priority never earns a lower weight."""
        weights = self._weights('car')
        ordered = sorted(PRIORITIES.items(), key=lambda kv: kv[1], reverse=True)
        for (code, priority), (next_code, next_priority) in zip(ordered, ordered[1:]):
            if priority > next_priority:
                self.assertGreater(
                    weights[code], weights[next_code],
                    f"{code} (priority {priority}) should outweigh "
                    f"{next_code} (priority {next_priority})")

    def test_weights_are_stored_on_criteria(self):
        """Creating criteria populates the stored weight without an explicit call."""
        self._make_full_criteria_set()
        criteria = {c.code: c for c in self.version.criterion_ids}
        for code, expected in CAR_EXPECTED.items():
            self.assertAlmostEqual(criteria[code].weight, expected, places=8)
        self.assertAlmostEqual(self.version.total_weight, 1.0, places=8)

    def test_changing_method_changes_stored_weights(self):
        self._make_full_criteria_set()
        self.version.weighting_method = 'legacy_car'
        self.version.action_recompute_weights()
        criteria = {c.code: c for c in self.version.criterion_ids}
        for code, expected in LEGACY_EXPECTED.items():
            self.assertAlmostEqual(criteria[code].weight, expected, places=8)

    def test_changing_a_priority_reweights_the_set(self):
        criteria = self._make_full_criteria_set()
        before = criteria['C6'].weight
        criteria['C6'].priority = 5
        criteria['C6'].invalidate_recordset(['weight'])
        self.assertGreater(
            criteria['C6'].weight, before,
            "raising a criterion's priority must raise its weight")
        self.assertAlmostEqual(self.version.total_weight, 1.0, places=8)

    def test_empty_and_all_zero_priorities(self):
        """Degenerate inputs must not raise or divide by zero."""
        self.assertEqual(self._weights_for({}), {})
        weights = self._weights_for({'A': 0, 'B': 0, 'C': 0})
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=10)
        self.assertEqual(len(set(round(w, 10) for w in weights.values())), 1)

    def _weights_for(self, priorities, method='car'):
        return self.env['campus.criterion']._car_weights(priorities, method=method)
