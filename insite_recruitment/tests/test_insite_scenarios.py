import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import InsiteCommon

MATRICULE_RE = r'^HIS-\d{4}-\d{6}-[0-9X]$'


@tagged('post_install', '-at_install')
class TestInsiteScenarios(InsiteCommon):
    """Identity-matching scenarios, now against the group register (his.person)."""

    def _bridge(self, applicant):
        """Bring a Campus+ applicant into the register, as Select would."""
        applicant.with_context(campus_identity_force=True)._his_creer_ou_rapprocher_personne()
        return applicant.his_person_id

    def test_scenario_a_campus_only(self):
        applicant = self.env['hr.applicant'].create({
            'partner_name': 'Karim Campus Only', 'email_from': 'karim.campus.only@example.com',
        })
        self.assertFalse(applicant.his_person_id,
                         "no Person just because a Campus+ applicant exists")
        self.assertEqual(self.Candidature.search_count(
            [('person_id.campus_applicant_ids', '=', applicant.id)]), 0)

    def test_scenario_b_insite_only(self):
        match, applicants = self.Submission._insite_identity_matches(
            first_name='Nadia', last_name='Insite', email='nadia.insite@example.com')
        self.assertFalse(match['person'] or applicants)

        submission = self._make_submission('INS/TEST/0001', {
            'firstName': 'Nadia', 'lastName': 'Insite', 'email': 'nadia.insite@example.com',
            'matricule': 'HIS-2020-000001-9',
        })
        submission.with_user(self.manager).action_process()
        self.assertEqual(submission.state, 'processed')
        self.assertEqual(submission.match_method, 'new')

        person = submission.person_id
        self.assertEqual(person.type_personne, 'candidat')
        self.assertFalse(person.matricule_institutionnel,
                         "a submitted matricule is a lookup key, never written")
        self.assertEqual(submission.candidature_id.person_id, person)
        self.assertEqual(submission.candidature_id.state, 'prospect')
        self.assertEqual(self.Person.search_count(
            [('email_personnel', '=', 'nadia.insite@example.com')]), 1)
        self.assertEqual(person.insite_candidature_count, 1)

    def test_scenario_c_campus_teacher_enters_insite(self):
        applicant = self.env['hr.applicant'].create({
            'partner_name': 'Sami Existing', 'email_from': 'sami.existing@example.com',
            'partner_phone': '0555123456',
        })
        submission = self._make_submission('INS/TEST/0002', {
            'firstName': 'Sami', 'lastName': 'Existing', 'email': 'sami.existing@example.com',
        })
        submission.with_user(self.manager).action_process()
        self.assertEqual(submission.state, 'needs_matching')

        wizard = self.env['insite.identity.match.wizard'].create({
            'submission_id': submission.id, 'first_name': 'Sami', 'last_name': 'Existing',
            'email': 'sami.existing@example.com',
        })
        wizard.action_search()
        self.assertIn(applicant, wizard.possible_applicant_ids)
        wizard.selected_applicant_id = applicant
        wizard.with_user(self.manager).action_confirm_existing_applicant()

        self.assertEqual(submission.state, 'processed')
        self.assertEqual(submission.match_method, 'possible_match')
        self.assertEqual(submission.person_id, applicant.his_person_id,
                         "one Person, shared with Campus+")
        self.assertEqual(submission.person_id.insite_candidature_count, 1)

    def test_scenario_d_same_teacher_both_processes(self):
        applicant = self.env['hr.applicant'].create({
            'partner_name': 'Yacine Both', 'email_from': 'yacine.both@example.com',
            'campus_scientific_rank': 'MCA',
        })
        person = self._bridge(applicant)
        person.is_internal_teacher = 'external'
        candidature = self.Candidature.create({
            'person_id': person.id, 'motivation': 'InSite-only motivation text',
        })
        candidature.motivation = 'Changed on the InSite side only'
        self.assertEqual(applicant.campus_scientific_rank, 'MCA')
        applicant.campus_state = 'evaluated'
        self.assertEqual(candidature.state, 'prospect')

    def test_scenario_e_probabilistic_match_requires_confirmation(self):
        existing = self._person('Ahmed Ben Ali', email_personnel='ahmed.benali@example.com',
                                is_internal_teacher='external')
        submission = self._make_submission('INS/TEST/0003', {
            'firstName': '  AHMED  ', 'lastName': '  Ben   ALI ',
            'email': 'ahmed.benali@example.com',
        })
        submission.with_user(self.manager).action_process()
        self.assertEqual(submission.state, 'needs_matching')
        self.assertFalse(submission.person_id)

        wizard = self.env['insite.identity.match.wizard'].create({
            'submission_id': submission.id, 'first_name': 'Ahmed', 'last_name': 'Ben Ali',
            'email': 'ahmed.benali@example.com',
        })
        wizard.action_search()
        self.assertIn(existing, wizard.possible_person_ids)

        wizard.with_user(self.manager).action_confirm_new_person()
        self.assertEqual(submission.match_method, 'new')
        self.assertNotEqual(submission.person_id, existing)
        self.assertEqual(self.Person.search_count([('name', '=', 'Ahmed Ben Ali')]), 2,
                         "an explicit operator rejection is allowed to create a second Person")

    def test_a_mistyped_matricule_does_not_bypass_matching(self):
        self._person('Lina Hadj', email_personnel='lina.hadj@example.com',
                     is_internal_teacher='external')
        submission = self._make_submission('INS/TEST/0004', {
            'firstName': 'Lina', 'lastName': 'Hadj', 'email': 'lina.hadj@example.com',
            'matricule': 'HIS-2099-999999-0',
        })
        submission.with_user(self.manager).action_process()
        self.assertEqual(submission.state, 'needs_matching',
                         "an unknown matricule must not short-circuit into a new Person")

    def test_matricule_of_an_employee_is_reused(self):
        employee = self._person('Rachid Staff', type_personne='employe',
                                is_internal_teacher='internal')
        self.assertTrue(employee.matricule_institutionnel)
        submission = self._make_submission('INS/TEST/0005', {
            'firstName': 'Rachid', 'lastName': 'Staff',
            'matricule': employee.matricule_institutionnel,
        })
        submission.with_user(self.manager).action_process()
        self.assertEqual(submission.match_method, 'exact_matricule')
        self.assertEqual(submission.person_id, employee)

    def test_insite_reaches_the_person_of_a_selected_campus_applicant(self):
        applicant = self.env['hr.applicant'].create({
            'partner_name': 'Houda Selected', 'email_from': 'houda.selected@example.com',
        })
        person = self._bridge(applicant)
        person.is_internal_teacher = 'external'
        submission = self._make_submission('INS/TEST/0006', {
            'firstName': 'Houda', 'lastName': 'Selected', 'email': 'houda.selected@example.com',
        })
        submission.with_user(self.manager).action_process()
        self.assertEqual(submission.state, 'needs_matching')

        wizard = self.env['insite.identity.match.wizard'].with_context(
            default_submission_id=submission.id).create({})
        wizard.action_search()
        self.assertEqual(wizard.possible_person_ids, person)
        wizard.selected_person_id = person
        wizard.with_user(self.manager).action_confirm_existing_person()
        self.assertEqual(submission.person_id, person)

    def test_person_can_have_multiple_campus_applications(self):
        applicant_2025 = self.env['hr.applicant'].create({
            'partner_name': 'Yasmine Repeat', 'email_from': 'yasmine.repeat@example.com',
        })
        person = self._bridge(applicant_2025)
        applicant_2026 = self.env['hr.applicant'].create({
            'partner_name': 'Yasmine Repeat', 'email_from': 'yasmine.repeat@example.com',
        })
        self._bridge(applicant_2026)

        self.assertEqual(person.campus_applicant_ids, applicant_2025 | applicant_2026)
        match, _applicants = self.Submission._insite_identity_matches(
            first_name='Yasmine', last_name='Repeat', email='yasmine.repeat@example.com')
        self.assertEqual(match['person'], person)

    def test_matching_wizard_confirm_requires_execute_permission(self):
        limited = self._make_user('cp5_wizard_limited', 'group_campus_recruiter')
        permission = self._grant(limited, 'insite_candidatures', view=True)

        wizard = self.env['insite.identity.match.wizard'].create({
            'first_name': 'Wizard', 'last_name': 'Bypass', 'email': 'wizard.bypass@example.com',
        })
        with self.assertRaises(AccessError):
            wizard.with_user(limited).action_confirm_new_person()

        permission.write({'can_execute': True})
        wizard.with_user(limited).action_confirm_new_person()
        self.assertEqual(self.Person.search_count([('name', '=', 'Wizard Bypass')]), 1)

    def test_submission_action_open_matching_wizard(self):
        submission = self.env['insite.submission'].create({
            'reference': 'CP-BUGFIX-SUB-001',
            'payload': {'firstName': 'Regression', 'lastName': 'Target', 'email': 'regression.target@example.com'},
        })
        action = submission.action_open_matching_wizard()
        self.assertEqual(action['res_model'], 'insite.identity.match.wizard')
        self.assertEqual(action['context'], {'default_submission_id': submission.id})

        wizard = self.env['insite.identity.match.wizard'].with_context(
            **action['context']).create({})
        self.assertEqual(wizard.submission_id, submission)

        limited = self._make_user('bugfix_limited', 'group_campus_recruiter')
        self._grant(limited, 'insite_candidatures', view=True)
        with self.assertRaises(AccessError):
            wizard.with_user(limited).action_confirm_new_person()

    def test_candidature_latest_relation_states_track_current_row(self):
        person = self._person('Latest State', is_internal_teacher='external')
        need = self._make_need()
        candidature = self.Candidature.create({'person_id': person.id, 'need_id': need.id})
        self.assertFalse(candidature.latest_contract_state)
        self.assertFalse(candidature.latest_engagement_state)

        engagement = self.Engagement.create({
            'person_id': person.id, 'module_id': self.module.id,
            'academic_period_id': self.period.id, 'insite_candidature_id': candidature.id,
            'need_id': need.id,
        })
        contract = self.Contract.create({
            'person_id': person.id, 'candidature_id': candidature.id, 'need_id': need.id,
        })
        self.assertEqual(candidature.latest_contract_state, 'Draft')
        self.assertEqual(candidature.latest_engagement_state, 'Draft')

        contract.with_user(self.manager).action_prepare()
        self.assertEqual(candidature.latest_contract_state, 'Prepared')
        engagement.with_user(self.manager).action_confirm()
        self.assertEqual(candidature.latest_engagement_state, 'Confirmed')

    def test_candidature_blocked_for_unclassified_person(self):
        person = self._person('Unclassified Person')
        self.assertFalse(person.is_internal_teacher)
        with self.assertRaises(ValidationError):
            self.Candidature.create({'person_id': person.id})

        person.is_internal_teacher = 'internal'
        candidature = self.Candidature.create({'person_id': person.id})
        self.assertEqual(candidature.source, 'internal')

        person.is_internal_teacher = 'external'
        self.assertEqual(candidature.source, 'external')


@tagged('post_install', '-at_install')
class TestInsiteNeedPipeline(InsiteCommon):
    """The full Need -> ... -> Published pipeline (see plan §18)."""

    def _accept_candidate(self, need, candidature):
        need.with_user(self.manager).action_select_candidate(candidature)
        need.with_user(self.manager).action_contact_candidate()
        candidature.with_user(self.manager).action_mark_accepted()
        self._schedule_meeting(candidature)
        need.with_user(self.manager).action_mark_meeting_completed()

    def _schedule_meeting(self, candidature, reschedule=False, start=None, location='Room 101'):
        start = start or (fields.Datetime.now() + timedelta(days=2))
        wizard = self.env['insite.meeting.schedule.wizard'].with_user(self.manager).with_context(
            default_candidature_id=candidature.id, reschedule=reschedule).create({
                'meeting_start': start, 'meeting_end': start + timedelta(hours=1), 'location': location,
            })
        wizard.action_confirm()
        return wizard

    def _sign_contract(self, contract):
        contract.with_user(self.manager).action_prepare()
        contract.with_user(self.manager).action_send()
        contract.with_user(self.manager).action_candidate_accept()
        contract.with_user(self.manager).write({
            'document': base64.b64encode(b'contract-pdf-bytes'), 'filename': 'c.pdf'})
        contract.with_user(self.manager).action_sign()

    def test_internal_teacher_path(self):
        teacher = self._person('Internal Teacher', is_internal_teacher='internal')
        self.assertFalse(teacher.matricule_institutionnel)
        need = self._make_need()
        need.with_user(self.manager).action_search_internal()
        self.assertEqual(need.state, 'searching_internal')
        self.assertIn(teacher, need._internal_teacher_candidates())

        candidature = self.Candidature.create({'person_id': teacher.id, 'need_id': need.id})
        self.assertEqual(candidature.source, 'internal')
        candidature.with_user(self.manager).action_select_this_candidate()
        self.assertEqual(need.state, 'candidate_selected')
        self.assertEqual(need.selected_candidature_id, candidature)

        need.with_user(self.manager).action_select_candidate(candidature)
        need.with_user(self.manager).action_contact_candidate()
        candidature.with_user(self.manager).action_mark_accepted()
        self.assertEqual(need.state, 'accepted')

        self._schedule_meeting(candidature, location='Room 101')
        self.assertEqual(candidature.meeting_event_id.location, 'Room 101')
        self.assertEqual(need.state, 'meeting_scheduled')

        need.with_user(self.manager).action_mark_meeting_completed()
        contract = need.with_user(self.manager).action_start_contract()
        self.assertEqual(need.state, 'contract')
        self._sign_contract(contract)
        self.assertEqual(teacher.type_personne, 'enseignant',
                         "signing the contract makes the person a teacher")
        self.assertRegex(teacher.matricule_institutionnel, MATRICULE_RE)
        self.assertEqual(need.state, 'integration_pending')
        self.assertTrue(need.integration_pending)

        need.with_user(self.manager).action_mark_integration_done()
        self.assertEqual(need.state, 'module_assigned')

        engagement = need.with_user(self.manager).action_assign_module()
        self.assertEqual(need.state, 'module_preparation')
        sheet = self.ModuleSheet.search([('engagement_id', '=', engagement.id)])
        self.assertTrue(sheet)

        sheet.with_user(self.manager).action_submit()
        sheet.with_user(self.manager).action_validate()
        self.assertEqual(sheet.state, 'validated')
        self.assertEqual(need.state, 'publication_pending')
        self.assertTrue(need.publication_pending)

        need.with_user(self.manager).action_mark_publication_done()
        self.assertEqual(need.state, 'published')
        self.assertEqual(sheet.state, 'published')

    def test_external_candidate_ranking_path(self):
        need = self._make_need(specialty='Networking')
        need.with_user(self.manager).action_search_internal()
        need.with_user(self.manager).action_no_internal_teacher_found()
        self.assertEqual(need.state, 'searching_external')

        weak = self._person('Weak Candidate', is_internal_teacher='external')
        strong = self._person('Strong Candidate', specialite='Networking',
                              is_internal_teacher='external')
        self.Engagement.create({
            'person_id': strong.id, 'module_id': self.module.id, 'academic_period_id': self.period.id,
        })

        c_weak = self.Candidature.create({'person_id': weak.id, 'need_id': need.id})
        c_strong = self.Candidature.create({
            'person_id': strong.id, 'need_id': need.id, 'teaching_experience': '5 years',
        })
        self.assertEqual(c_weak.source, 'external')

        need.with_user(self.manager).action_rank_external_candidates()
        self.assertEqual(c_strong.insite_rank, 1)
        self.assertEqual(c_weak.insite_rank, 2)
        self.assertIn('Specialty match: Yes', c_strong.rank_explanation)
        self.assertIn('Experience with this exact module: Yes', c_strong.rank_explanation)
        self.assertIn('Specialty match: No', c_weak.rank_explanation)

        c_strong.with_user(self.manager).action_select_this_candidate()
        self.assertEqual(need.selected_candidature_id, c_strong)

    def test_candidate_decline_requires_manual_next_selection(self):
        need = self._make_need()
        need.with_user(self.manager).action_search_internal()
        need.with_user(self.manager).action_no_internal_teacher_found()

        person_a = self._person('Candidate A', is_internal_teacher='external')
        person_b = self._person('Candidate B', is_internal_teacher='external')
        cand_a = self.Candidature.create({'person_id': person_a.id, 'need_id': need.id})
        cand_b = self.Candidature.create({'person_id': person_b.id, 'need_id': need.id})

        need.with_user(self.manager).action_select_candidate(cand_a)
        need.with_user(self.manager).action_contact_candidate()
        cand_a.with_user(self.manager).action_mark_declined()

        self.assertEqual(cand_a.state, 'declined')
        self.assertFalse(need.selected_candidature_id)
        self.assertEqual(need.state, 'searching_external')
        self.assertEqual(cand_b.state, 'prospect')

        cand_b.with_user(self.manager).action_select_this_candidate()
        self.assertEqual(need.selected_candidature_id, cand_b)

    def test_48h_reminder_never_auto_advances(self):
        need = self._make_need()
        person_a = self._person('Reminder A', is_internal_teacher='external')
        person_b = self._person('Reminder B', is_internal_teacher='external')
        cand_a = self.Candidature.create({'person_id': person_a.id, 'need_id': need.id})
        cand_b = self.Candidature.create({'person_id': person_b.id, 'need_id': need.id})

        need.with_user(self.manager).action_select_candidate(cand_a)
        need.with_user(self.manager).action_contact_candidate()
        cand_a.contacted_date = cand_a.contacted_date - timedelta(hours=49)

        self.Candidature._cron_insite_reminder_check()
        cand_a.invalidate_recordset()

        self.assertTrue(cand_a.reminder_sent)
        self.assertEqual(cand_a.state, 'contacted')
        self.assertEqual(need.state, 'awaiting_response')
        self.assertEqual(cand_b.state, 'prospect')
        self.assertTrue(cand_a.activity_ids)

        activity_count = len(cand_a.activity_ids)
        self.Candidature._cron_insite_reminder_check()
        self.assertEqual(len(cand_a.activity_ids), activity_count)

    def test_contract_rejection_stops_recruitment(self):
        need = self._make_need()
        person = self._person('Reject Contract', is_internal_teacher='external')
        candidature = self.Candidature.create({'person_id': person.id, 'need_id': need.id})
        self._accept_candidate(need, candidature)
        contract = need.with_user(self.manager).action_start_contract()

        contract.with_user(self.manager).action_prepare()
        contract.with_user(self.manager).action_send()
        contract.with_user(self.manager).action_candidate_reject()

        self.assertEqual(contract.state, 'rejected')
        self.assertEqual(need.state, 'cancelled')
        self.assertEqual(person.type_personne, 'candidat', "no matricule without a signature")
        self.assertFalse(self.Engagement.search([('need_id', '=', need.id)]))

    def test_module_validation_and_publication_flow(self):
        engagement = self.Engagement.create({
            'person_id': self._person('Module Flow').id,
            'module_id': self.module.id, 'academic_period_id': self.period.id,
        })
        sheet = self.ModuleSheet.create({'engagement_id': engagement.id})

        sheet.with_user(self.manager).action_submit()
        sheet.review_notes = 'Add more detail to chapter 2.'
        sheet.with_user(self.manager).action_request_modification()
        self.assertEqual(sheet.state, 'draft')

        sheet.with_user(self.manager).action_submit()
        self.assertEqual(sheet.state, 'submitted')
        sheet.with_user(self.manager).action_validate()
        self.assertEqual(sheet.state, 'validated')

        with self.assertRaises(UserError):
            sheet.with_user(self.manager).action_validate()

    def test_meeting_schedule_guard_and_reschedule(self):
        need = self._make_need()
        person = self._person('Meeting Flow', is_internal_teacher='external')
        candidature = self.Candidature.create({'person_id': person.id, 'need_id': need.id})
        need.with_user(self.manager).action_select_candidate(candidature)
        need.with_user(self.manager).action_contact_candidate()
        candidature.with_user(self.manager).action_mark_accepted()

        first_start = fields.Datetime.now() + timedelta(days=5)
        self._schedule_meeting(candidature, start=first_start, location='Room A')
        event = candidature.meeting_event_id
        self.assertTrue(event)
        self.assertEqual(event.start, first_start)
        self.assertEqual(need.state, 'meeting_scheduled')

        with self.assertRaises(UserError):
            candidature.with_user(self.manager).action_schedule_meeting()
        with self.assertRaises(UserError):
            self._schedule_meeting(candidature, start=fields.Datetime.now() + timedelta(days=6))

        new_start = fields.Datetime.now() + timedelta(days=7)
        self._schedule_meeting(candidature, reschedule=True, start=new_start, location='Room B')
        self.assertEqual(candidature.meeting_event_id, event)
        self.assertEqual(event.start, new_start)
        self.assertEqual(event.location, 'Room B')

        candidature2 = self.Candidature.create({'person_id': person.id, 'need_id': need.id})
        with self.assertRaises(UserError):
            candidature2.with_user(self.manager).action_reschedule_meeting()

        with self.assertRaises(UserError):
            need.with_user(self.manager).action_start_contract()
        need.with_user(self.manager).action_mark_meeting_completed()
        need.with_user(self.manager).action_start_contract()
        self.assertEqual(need.state, 'contract')
