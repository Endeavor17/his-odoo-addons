from odoo.tests import tagged

from .common import CampusCommon


@tagged('post_install', '-at_install')
class TestDashboardQueries(CampusCommon):
    """Runs exactly the reads the OWL dashboard issues.

    The dashboard is client-side, so a bad query does not fail any Python test —
    it fails silently in the browser and the whole component refuses to mount.
    That is how a group-by on the non-stored ``application_status`` shipped
    unnoticed. These tests execute the same calls server-side so a broken one is
    caught here instead of by whoever opens the app.
    """

    def setUp(self):
        super().setUp()
        self._make_full_criteria_set()
        self.version.action_publish()
        self.applicant = self._make_applicant('Dashboard Candidate', **{
            'campus_scientific_rank': 'prof',
            'campus_years_exp': 10,
        })
        self.applicant.action_campus_evaluate()
        self.domain = [('campus_version_id', '=', self.version.id)]
        self.evaluated = self.domain + [('campus_state', 'in', ['evaluated', 'locked'])]

    def test_version_selector_read(self):
        versions = self.Version.search_read([], ['id', 'display_name', 'state'],
                                            order='version desc, id desc')
        self.assertTrue(versions)

    def test_status_counts_group_by(self):
        groups = self.Applicant.formatted_read_group(
            self.domain, ['campus_state'], ['__count'])
        counts = {g['campus_state']: g['__count'] for g in groups}
        self.assertEqual(counts.get('evaluated'), 1)

    def test_score_aggregates(self):
        agg = self.Applicant.formatted_read_group(
            self.evaluated, [], ['campus_final_score:avg', 'campus_final_score:max'])
        self.assertTrue(agg)
        self.assertGreater(agg[0]['campus_final_score:max'], 0)

    def test_accepted_and_refused_are_counted_not_grouped(self):
        """application_status is computed and NOT stored.

        It carries a search method so a domain works, but grouping on it compiles
        to SQL over a column that does not exist. This asserts both halves so the
        dashboard can never regress back to a group-by.
        """
        # Filtering works...
        self.assertIsInstance(
            self.Applicant.search_count(
                self.domain + [('application_status', '=', 'hired')]), int)
        self.assertIsInstance(
            self.Applicant.search_count(
                self.domain + [('application_status', '=', 'refused')]), int)

        # ...grouping does not, and must never be reintroduced.
        self.assertFalse(
            self.Applicant._fields['application_status'].store,
            "application_status became stored; the dashboard could now group on it, "
            "but check every other non-stored field it reads before relying on that")
        with self.assertRaises(ValueError):
            self.Applicant.formatted_read_group(
                self.domain, ['application_status'], ['__count'])

    def test_ranking_table_read(self):
        rows = self.Applicant.search_read(
            self.evaluated,
            ['id', 'campus_rank', 'partner_name', 'email_from', 'campus_final_score',
             'campus_scientific_rank', 'stage_id'],
            limit=25, order='campus_final_score desc, id asc')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['campus_rank'], 1)

    def test_every_field_the_ranking_reads_is_stored_or_readable(self):
        """A non-stored field in the order clause would break the ranking table."""
        for name in ('campus_rank', 'campus_final_score', 'campus_state', 'campus_version_id'):
            self.assertTrue(
                self.Applicant._fields[name].store,
                f"{name} must stay stored: the dashboard sorts and filters on it")
