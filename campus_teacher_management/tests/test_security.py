from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import CampusCommon


@tagged('post_install', '-at_install')
class TestSecurity(CampusCommon):

    def setUp(self):
        super().setUp()
        self.criteria = self._make_full_criteria_set()
        self.version.action_publish()

        self.recruiter = self.env['res.users'].create({
            'name': 'Campus Recruiter',
            'login': 'campus_recruiter_test',
            'email': 'recruiter@example.com',
            'group_ids': [(6, 0, [
                self.env.ref('campus_teacher_management.group_campus_recruiter').id,
            ])],
        })
        self.manager = self.env['res.users'].create({
            'name': 'Campus Manager',
            'login': 'campus_manager_test',
            'email': 'manager@example.com',
            'group_ids': [(6, 0, [
                self.env.ref('campus_teacher_management.group_campus_manager').id,
            ])],
        })

    def test_recruiter_can_read_configuration(self):
        version = self.version.with_user(self.recruiter)
        self.assertTrue(version.name)
        self.assertTrue(version.criterion_ids.with_user(self.recruiter).mapped('code'))

    def test_recruiter_cannot_edit_a_criterion(self):
        criterion = self.criteria['C1'].with_user(self.recruiter)
        with self.assertRaises(AccessError):
            criterion.write({'name': 'Renamed by a recruiter'})

    def test_recruiter_cannot_create_a_version(self):
        with self.assertRaises(AccessError):
            self.Version.with_user(self.recruiter).create({'name': 'Sneaky', 'version': 1})

    def test_manager_can_edit_a_draft_criterion(self):
        draft = self.Version.create({'name': 'Draft Set', 'version': 1})
        criterion = self._make_criterion('X1', 1, 'answered', 'flippedDef', version=draft)
        criterion.with_user(self.manager).write({'name': 'Renamed by a manager'})
        self.assertEqual(criterion.name, 'Renamed by a manager')

    def test_recruiter_cannot_read_raw_submissions(self):
        """Raw payloads carry personal data, so they are manager-only."""
        submission = self.env['campus.submission'].create({
            'reference': 'SUB/TEST/0001',
            'payload': {'email': 'someone@example.com'},
        })
        with self.assertRaises(AccessError):
            submission.with_user(self.recruiter).read(['payload'])
        self.assertTrue(submission.with_user(self.manager).read(['payload']))

    def test_recruiter_can_manage_subject_assignment(self):
        """Assigning accepted subjects is the recruiter's job, so it must be allowed."""
        applicant = self._make_applicant('Assignable')
        line = self.env['campus.application.subject'].with_user(self.recruiter).create({
            'applicant_id': applicant.id,
            'subject_id': self.math.id,
            'source': 'catalogue',
            'years_exp': 2,
        })
        line.with_user(self.recruiter).write({'is_accepted': True})
        self.assertTrue(line.is_accepted)

    def test_recruiter_can_read_score_lines_but_not_alter_them(self):
        applicant = self._make_applicant('Scored', campus_scientific_rank='prof')
        applicant.action_campus_evaluate()
        line = applicant.campus_score_ids[0].with_user(self.recruiter)
        self.assertTrue(line.code_snapshot)
        with self.assertRaises(AccessError):
            line.write({'raw_score': 999})
