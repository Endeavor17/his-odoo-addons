from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common import CampusCommon


@tagged('post_install', '-at_install')
class TestProcessPermissions(CampusCommon):
    """The campus.process.permission matrix, per section 22 of the spec.

    Each test creates its own throwaway user (mirrors tests/test_security.py)
    and its own permission row(s), so the scenarios are self-contained and
    don't depend on any seeded data.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Permission = cls.env['campus.process.permission']
        cls.interview1 = cls.env.ref('campus_teacher_management.process_interview1')
        cls.stage_interview1 = cls.env.ref('campus_teacher_management.stage_interview1')

    def _make_recruiter(self, login):
        return self.env['res.users'].create({
            'name': login,
            'login': login,
            'email': f'{login}@example.com',
            'group_ids': [(6, 0, [
                self.env.ref('campus_teacher_management.group_campus_recruiter').id,
            ])],
        })

    def _make_manager(self, login):
        return self.env['res.users'].create({
            'name': login,
            'login': login,
            'email': f'{login}@example.com',
            'group_ids': [(6, 0, [
                self.env.ref('campus_teacher_management.group_campus_manager').id,
            ])],
        })

    def _grant(self, user, process, view=False, execute=False, validate=False):
        return self.Permission.create({
            'process_id': process.id,
            'user_id': user.id,
            'can_view': view,
            'can_execute': execute,
            'can_validate': validate,
        })

    def _interview1_applicant(self, name='Interview1 Candidate'):
        return self._make_applicant(name=name, stage_id=self.stage_interview1.id)

    # ------------------------------------------------------------------
    # Test 1: view only
    # ------------------------------------------------------------------
    def test_view_only_can_open_but_not_execute_or_validate(self):
        user = self._make_recruiter('view_only')
        self._grant(user, self.interview1, view=True)
        applicant = self._interview1_applicant()

        applicant.with_user(user).read(['partner_name'])  # can open

        with self.assertRaises(AccessError):
            applicant.with_user(user).action_campus_open_schedule_interview1()
        with self.assertRaises(AccessError):
            applicant.with_user(user).action_campus_mark_interview1_completed()

    # ------------------------------------------------------------------
    # Test 2: view + execute
    # ------------------------------------------------------------------
    def test_view_and_execute_can_act_but_not_validate(self):
        user = self._make_recruiter('view_execute')
        self._grant(user, self.interview1, view=True, execute=True)
        applicant = self._interview1_applicant()

        applicant.with_user(user).read(['partner_name'])
        applicant.with_user(user).action_campus_open_schedule_interview1()  # no error

        with self.assertRaises(AccessError):
            applicant.with_user(user).action_campus_mark_interview1_completed()

    # ------------------------------------------------------------------
    # Test 3: full access
    # ------------------------------------------------------------------
    def test_full_access_can_view_execute_and_validate(self):
        user = self._make_recruiter('full_access')
        self._grant(user, self.interview1, view=True, execute=True, validate=True)
        applicant = self._interview1_applicant()
        applicant.campus_hiring_state = 'meeting_1'

        applicant.with_user(user).read(['partner_name'])
        applicant.with_user(user).action_campus_open_schedule_interview1()
        applicant.with_user(user).action_campus_mark_interview1_completed()
        self.assertEqual(applicant.campus_hiring_state, 'interview1_completed')

    # ------------------------------------------------------------------
    # Test 4: no access — filtered from lists, denied on direct access/RPC
    # ------------------------------------------------------------------
    def test_no_access_is_filtered_and_denied(self):
        user = self._make_recruiter('no_access')
        applicant = self._interview1_applicant()

        found = self.Applicant.with_user(user).search([('id', '=', applicant.id)])
        self.assertFalse(found, "an applicant on a process the user cannot view must not appear in search")

        with self.assertRaises(AccessError):
            applicant.with_user(user).read(['partner_name'])
        with self.assertRaises(AccessError):
            applicant.with_user(user).action_campus_mark_interview1_completed()

    # ------------------------------------------------------------------
    # Test 5: bypass attempts (direct action-method call) are denied
    # ------------------------------------------------------------------
    def test_bypass_via_direct_action_call_is_denied(self):
        user = self._make_recruiter('bypass_attempt')
        self._grant(user, self.interview1, view=True)  # no execute/validate
        applicant = self._interview1_applicant()

        with self.assertRaises(AccessError):
            self.env['campus.process.permission']._check_process_permission(
                'interview1', 'validate', for_user=user)

    # ------------------------------------------------------------------
    # Test 6: a normal user cannot modify the permission matrix
    # ------------------------------------------------------------------
    def test_normal_user_cannot_edit_permissions(self):
        user = self._make_recruiter('cannot_edit')
        with self.assertRaises(AccessError):
            self.Permission.with_user(user).create({
                'process_id': self.interview1.id,
                'user_id': user.id,
                'can_view': True, 'can_execute': True, 'can_validate': True,
            })

        existing = self._grant(self._make_recruiter('someone_else'), self.interview1, view=True)
        with self.assertRaises(AccessError):
            existing.with_user(user).write({'can_view': False})

    # ------------------------------------------------------------------
    # Test 7: a manager's edit takes effect immediately, no code change
    # ------------------------------------------------------------------
    def test_manager_edit_applies_immediately(self):
        manager = self._make_manager('editor_manager')
        user = self._make_recruiter('flips')
        permission = self._grant(user, self.interview1, view=True)
        applicant = self._interview1_applicant()

        with self.assertRaises(AccessError):
            applicant.with_user(user).action_campus_open_schedule_interview1()

        permission.with_user(manager).write({'can_execute': True})

        applicant.with_user(user).action_campus_open_schedule_interview1()  # now allowed

    # ------------------------------------------------------------------
    # Hierarchy: Validate needs Execute, Execute needs View (section 10)
    # ------------------------------------------------------------------
    def test_hierarchy_is_enforced(self):
        user = self._make_recruiter('bad_hierarchy')
        with self.assertRaises(ValidationError):
            self.Permission.create({
                'process_id': self.interview1.id,
                'user_id': user.id,
                'can_view': False, 'can_execute': True, 'can_validate': False,
            })

    def test_duplicate_permission_is_rejected(self):
        user = self._make_recruiter('dup_user')
        self._grant(user, self.interview1, view=True)
        with self.assertRaises(Exception):
            self._grant(user, self.interview1, view=True)
