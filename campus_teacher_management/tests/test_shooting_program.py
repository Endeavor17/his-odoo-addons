from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import CampusCommon


@tagged('post_install', '-at_install')
class TestShootingProgram(CampusCommon):
    """Contract Signed — and only Contract Signed — creates the teacher's
    own Shooting Program and moves them to the Shooting stage."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.process_contract = cls.env.ref('campus_teacher_management.process_contract')
        cls.process_shooting = cls.env.ref('campus_teacher_management.process_shooting')
        cls.stage_contract = cls.env.ref('campus_teacher_management.stage_contract')
        cls.stage_shooting = cls.env.ref('campus_teacher_management.stage_shooting')
        cls.Program = cls.env['campus.shooting.program']
        cls.Session = cls.env['campus.shooting.session']

    def setUp(self):
        super().setUp()
        self.manager = self.env['res.users'].create({
            'name': 'Shooting Manager',
            'login': 'shooting_manager',
            'email': 'shooting_manager@example.com',
            'group_ids': [(6, 0, [
                self.env.ref('campus_teacher_management.group_campus_manager').id])],
        })
        Permission = self.env['campus.process.permission']
        for process in (self.process_contract, self.process_shooting):
            Permission.create({
                'process_id': process.id, 'user_id': self.manager.id,
                'can_view': True, 'can_execute': True, 'can_validate': True,
            })
        self.applicant = self._make_applicant(
            'Shooting Candidate', stage_id=self.stage_contract.id,
            campus_contract_file=b'Y29udHJhY3Q=', campus_contract_filename='contract.pdf',
            campus_contract_state='sent')

    def test_sent_and_awaiting_do_not_create_a_program_or_move_the_stage(self):
        self.applicant.with_user(self.manager).action_campus_mark_contract_sent()
        self.assertEqual(self.applicant.stage_id, self.stage_contract)
        self.assertFalse(self.Program.search([('applicant_id', '=', self.applicant.id)]))

        self.applicant.with_user(self.manager).action_campus_mark_contract_awaiting_signature()
        self.assertEqual(self.applicant.stage_id, self.stage_contract)
        self.assertFalse(self.Program.search([('applicant_id', '=', self.applicant.id)]))

    def test_signed_creates_exactly_one_program_and_moves_to_shooting(self):
        self.applicant.with_user(self.manager).action_campus_mark_contract_signed()
        self.assertEqual(self.applicant.stage_id, self.stage_shooting)
        programs = self.Program.search([('applicant_id', '=', self.applicant.id)])
        self.assertEqual(len(programs), 1)
        self.assertEqual(self.applicant.campus_shooting_program_id, programs)

    def test_get_or_create_for_applicant_is_idempotent(self):
        first = self.Program._get_or_create_for_applicant(self.applicant)
        second = self.Program._get_or_create_for_applicant(self.applicant)
        self.assertEqual(first, second, "one program per teacher, even if requested twice")

    def test_signing_again_once_in_shooting_is_blocked(self):
        """Once Contract Signed has already moved the candidate to Shooting,
        the Course-Breakdown-stage gate (below) also blocks signing it again
        — there is no path back into 'currently in Contrat'."""
        self.applicant.with_user(self.manager).action_campus_mark_contract_signed()
        self.applicant.campus_contract_state = 'awaiting_signature'  # simulate a re-entry
        with self.assertRaises(UserError):
            self.applicant.with_user(self.manager).action_campus_mark_contract_signed()

    def test_session_created_from_the_applicant_attaches_to_the_program(self):
        self.applicant.with_user(self.manager).action_campus_mark_contract_signed()
        program = self.applicant.campus_shooting_program_id

        session = self.Session.with_user(self.manager).create({
            'applicant_id': self.applicant.id,
            'title': 'Intro segment',
            'description': 'Record the module introduction.',
            'start_datetime': fields.Datetime.now(),
        })
        self.assertEqual(session.program_id, program)
        self.assertIn(session, program.session_ids)

    def test_program_is_created_on_the_fly_if_a_session_arrives_first(self):
        """Defensive: a session created before the contract-signed step ran
        (e.g. from a script) still gets a program instead of being orphaned."""
        self.applicant.campus_contract_state = 'signed'  # bypass the action on purpose
        self.assertFalse(self.Program.search([('applicant_id', '=', self.applicant.id)]))

        session = self.Session.with_user(self.manager).create({
            'applicant_id': self.applicant.id,
            'title': 'Intro segment',
            'description': 'Record the module introduction.',
            'start_datetime': fields.Datetime.now(),
        })
        self.assertTrue(session.program_id)
        self.assertEqual(session.program_id.applicant_id, self.applicant)
