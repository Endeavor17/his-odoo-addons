from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import CampusCommon


@tagged('post_install', '-at_install')
class TestContractStageGate(CampusCommon):
    """Mark Contract Signed / Not Signed must not be usable before the
    candidate has actually reached the Contrat stage — even though
    campus_contract_state is already 'sent' from the 2nd Interview step,
    well before Course Breakdown is approved."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.process_contract = cls.env.ref('campus_teacher_management.process_contract')
        cls.stage_course_breakdown = cls.env.ref('campus_teacher_management.stage_course_breakdown')
        cls.stage_contract = cls.env.ref('campus_teacher_management.stage_contract')

    def setUp(self):
        super().setUp()
        self.manager = self.env['res.users'].create({
            'name': 'Contract Gate Manager',
            'login': 'contract_gate_manager',
            'email': 'contract_gate_manager@example.com',
            'group_ids': [(6, 0, [
                self.env.ref('campus_teacher_management.group_campus_manager').id])],
        })
        self.env['campus.process.permission'].create({
            'process_id': self.process_contract.id, 'user_id': self.manager.id,
            'can_view': True, 'can_execute': True, 'can_validate': True,
        })
        # campus_contract_state = 'sent' on purpose: this is already true by
        # the time a real candidate reaches Course Breakdown (set at the 2nd
        # Interview scheduling step), so the gate must not rely on it.
        self.applicant = self._make_applicant(
            'Contract Gate Candidate', stage_id=self.stage_course_breakdown.id,
            campus_contract_state='sent',
            campus_contract_file=b'Y29udHJhY3Q=', campus_contract_filename='contract.pdf')

    def test_in_contract_stage_flag_follows_the_stage(self):
        self.assertFalse(self.applicant.campus_in_contract_stage)
        self.applicant.stage_id = self.stage_contract
        self.assertTrue(self.applicant.campus_in_contract_stage)

    def test_signed_is_blocked_while_at_course_breakdown(self):
        with self.assertRaises(UserError):
            self.applicant.with_user(self.manager).action_campus_mark_contract_signed()
        self.assertEqual(self.applicant.campus_contract_state, 'sent',
                         "a blocked action must not change the contract status")

    def test_not_signed_is_blocked_while_at_course_breakdown(self):
        with self.assertRaises(UserError):
            self.applicant.with_user(self.manager).action_campus_mark_contract_not_signed()
        self.assertEqual(self.applicant.campus_contract_state, 'sent')

    def test_signed_is_allowed_once_at_contract_stage(self):
        self.applicant.stage_id = self.stage_contract
        self.applicant.with_user(self.manager).action_campus_mark_contract_signed()
        self.assertEqual(self.applicant.campus_contract_state, 'signed')

    def test_not_signed_is_allowed_once_at_contract_stage(self):
        self.applicant.stage_id = self.stage_contract
        self.applicant.with_user(self.manager).action_campus_mark_contract_not_signed()
        self.assertEqual(self.applicant.campus_contract_state, 'not_signed')
