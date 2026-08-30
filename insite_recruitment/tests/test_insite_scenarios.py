import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import InsiteCommon


@tagged('post_install', '-at_install')
class TestInsiteScenarios(InsiteCommon):
    """Identity-matching scenarios — unaffected by the Need-pipeline rebuild,
    since academic.person.insite_find_matches()/insite.submission.action_process()
    don't depend on the candidature/contract state machines at all."""

    def test_scenario_a_campus_only(self):
        applicant = self.env['hr.applicant'].create({
            'partner_name': 'Karim Campus Only', 'email_from': 'karim.campus.only@example.com',
        })
        self.assertFalse(
            self.Person.search([('campus_applicant_id', '=', applicant.id)]),
            "no InSite Person should be created just because a Campus+ applicant exists")
        self.assertEqual(self.Candidature.search_count([('person_id.campus_applicant_id', '=', applicant.id)]), 0)

    def test_scenario_b_insite_only(self):
        matches = self.Person.insite_find_matches(
            first_name='Nadia', last_name='Insite', email='nadia.insite@example.com')
        self.assertFalse(matches['exact'] or matches['possible_persons'] or matches['possible_applicants'])

        submission = self._make_submission('INS/TEST/0001', {
            'firstName': 'Nadia', 'lastName': 'Insite', 'email': 'nadia.insite@example.com',
        })
        submission.with_user(self.manager).action_process()
        self.assertEqual(submission.state, 'processed')
        self.assertEqual(submission.match_method, 'new')

        person = submission.person_id
        self.assertTrue(person)
        candidature = submission.candidature_id
        self.assertEqual(candidature.person_id, person)
        self.assertEqual(candidature.state, 'prospect',
                          "a submission-created candidature starts as prospect — a human "
                          "links it to a Need and selects it explicitly, nothing auto-advances")
        self.assertEqual(self.Person.search_count([('email_institutional', '=', 'nadia.insite@example.com')]), 1)
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
        self.assertEqual(submission.state, 'needs_matching',
                          "a name/email match against an hr.applicant is probabilistic, not automatic")

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
        person = submission.person_id
        self.assertIn(applicant, person.campus_applicant_id)
        self.assertEqual(
            self.Person.search_count([('campus_applicant_id', '=', applicant.id)]), 1,
            "one Person, not a duplicate, for a teacher already known through Campus+")
        self.assertTrue(submission.candidature_id)
        self.assertEqual(person.insite_candidature_count, 1)

    def test_scenario_d_same_teacher_both_processes(self):
        """Same teacher in both processes: separate answers, separate state,
        no cross-contamination either direction."""
        applicant = self.env['hr.applicant'].create({
            'partner_name': 'Yacine Both', 'email_from': 'yacine.both@example.com',
            'campus_scientific_rank': 'MCA',
        })
        person = self.Person.insite_create_from_applicant(applicant)
        candidature = self.Candidature.create({
            'person_id': person.id,
            'motivation': 'InSite-only motivation text',
            'availability': 'Evenings',
        })

        self.assertNotEqual(getattr(applicant, 'campus_scientific_rank', None), candidature.motivation)
        candidature.motivation = 'Changed on the InSite side only'
        self.assertEqual(applicant.campus_scientific_rank, 'MCA',
                          "editing the InSite candidature must never touch the Campus+ applicant")

        applicant.campus_state = 'evaluated'
        self.assertEqual(candidature.state, 'prospect',
                          "Campus+'s own state field must not move InSite's")

    def test_scenario_e_probabilistic_match_requires_confirmation(self):
        existing = self.Person.create({
            'first_name': 'Ahmed', 'last_name': 'Ben Ali',
            'email_institutional': 'ahmed.benali@example.com', 'is_internal_teacher': 'external',
        })
        submission = self._make_submission('INS/TEST/0003', {
            'firstName': '  AHMED  ', 'lastName': '  Ben   ALI ',
            'email': 'a.benali.other@example.com',
        })
        submission.with_user(self.manager).action_process()
        self.assertEqual(submission.state, 'needs_matching')
        self.assertFalse(submission.person_id, "must not auto-resolve on a probabilistic-only match")

        wizard = self.env['insite.identity.match.wizard'].create({
            'submission_id': submission.id, 'first_name': 'Ahmed', 'last_name': 'Ben Ali',
            'email': 'a.benali.other@example.com',
        })
        wizard.action_search()
        self.assertIn(existing, wizard.possible_person_ids)

        wizard.with_user(self.manager).action_confirm_new_person()
        self.assertEqual(submission.state, 'processed')
        self.assertEqual(submission.match_method, 'new')
        self.assertNotEqual(submission.person_id, existing)
        self.assertEqual(
            self.Person.search_count([('last_name', '=', 'Ben Ali')]), 2,
            "an explicit operator rejection is allowed to create a second Person")

    def test_person_can_have_multiple_campus_applications(self):
        applicant_2025 = self.env['hr.applicant'].create({
            'partner_name': 'Yasmine Repeat', 'email_from': 'yasmine.repeat@example.com',
        })
        person = self.Person.insite_create_from_applicant(applicant_2025)
        self.assertEqual(len(person.campus_applicant_id), 1)

        applicant_2026 = self.env['hr.applicant'].create({
            'partner_name': 'Yasmine Repeat', 'email_from': 'yasmine.repeat.2026@example.com',
        })
        person.insite_link_campus_applicant(applicant_2026)

        self.assertEqual(len(person.campus_applicant_id), 2)
        self.assertIn(applicant_2025, person.campus_applicant_id)
        self.assertIn(applicant_2026, person.campus_applicant_id)

        matches = self.Person.insite_find_matches(email='yasmine.repeat.2026@example.com')
        self.assertIn(person, matches['possible_persons'])

    def test_person_campus_plus_insite_together(self):
        applicant = self.env['hr.applicant'].create({
            'partner_name': 'Omar Both', 'email_from': 'omar.both@example.com',
        })
        person = self.Person.insite_create_from_applicant(applicant)
        self.Candidature.create({'person_id': person.id})

        self.assertEqual(self.Person.search_count([('id', '=', person.id)]), 1)
        self.assertEqual(len(person.campus_applicant_id), 1)
        self.assertEqual(person.insite_candidature_count, 1)

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
        self.assertEqual(
            self.Person.search_count([('first_name', '=', 'Wizard'), ('last_name', '=', 'Bypass')]), 1)

    def test_submission_action_open_matching_wizard(self):
        submission = self.env['insite.submission'].create({
            'reference': 'CP-BUGFIX-SUB-001',
            'payload': {'firstName': 'Regression', 'lastName': 'Target', 'email': 'regression.target@example.com'},
        })
        action = submission.action_open_matching_wizard()
        self.assertEqual(action['res_model'], 'insite.identity.match.wizard')
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['context'], {'default_submission_id': submission.id})

        wizard = self.env['insite.identity.match.wizard'].with_context(
            **action['context']).create({})
        self.assertEqual(wizard.submission_id, submission)

        limited = self._make_user('bugfix_limited', 'group_campus_recruiter')
        self._grant(limited, 'insite_candidatures', view=True)
        with self.assertRaises(AccessError):
            wizard.with_user(limited).action_confirm_new_person()

    def test_candidature_latest_relation_states_track_current_row(self):
        person = self.Person.create({'first_name': 'Latest', 'last_name': 'State', 'is_internal_teacher': 'external'})
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

    # ------------------------------------------------------------------
    # A Candidature can never be created for an unclassified Person — the
    # server-side gate, not just a UI hint. source is fully computed and
    # tracks whatever the Person is classified as, never manually settable.
    # ------------------------------------------------------------------
    def test_candidature_blocked_for_unclassified_person(self):
        person = self.Person.create({'first_name': 'Unclassified', 'last_name': 'Person'})
        self.assertFalse(person.is_internal_teacher)
        with self.assertRaises(ValidationError):
            self.Candidature.create({'person_id': person.id})

        person.is_internal_teacher = 'internal'
        candidature = self.Candidature.create({'person_id': person.id})
        self.assertEqual(candidature.source, 'internal')

        person.is_internal_teacher = 'external'
        self.assertEqual(candidature.source, 'external',
                          "source stays computed/live — it's never a one-time snapshot")


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

    # ------------------------------------------------------------------
    # Internal path: Need -> internal teacher found -> selected -> accepted
    # -> contract -> signed -> module -> validation -> publication.
    # ------------------------------------------------------------------
    def test_internal_teacher_path(self):
        teacher = self.Person.create({
            'first_name': 'Internal', 'last_name': 'Teacher', 'is_internal_teacher': 'internal',
        })
        need = self._make_need()
        need.with_user(self.manager).action_search_internal()
        self.assertEqual(need.state, 'searching_internal')

        candidates = need._internal_teacher_candidates()
        self.assertIn(teacher, candidates)

        candidature = self.Candidature.create({'person_id': teacher.id, 'need_id': need.id})
        self.assertEqual(candidature.source, 'internal',
                          "source is snapshotted from is_internal_teacher at creation, not inferred later")
        candidature.with_user(self.manager).action_select_this_candidate()
        self.assertEqual(need.state, 'candidate_selected')
        self.assertEqual(need.selected_candidature_id, candidature)

        need.with_user(self.manager).action_select_candidate(candidature)
        need.with_user(self.manager).action_contact_candidate()
        candidature.with_user(self.manager).action_mark_accepted()
        self.assertEqual(need.state, 'accepted')

        self._schedule_meeting(candidature, location='Room 101')
        self.assertTrue(candidature.meeting_event_id, "Schedule Meeting must create and link a real calendar.event")
        self.assertEqual(candidature.meeting_event_id.location, 'Room 101')
        self.assertEqual(need.state, 'meeting_scheduled')

        need.with_user(self.manager).action_mark_meeting_completed()
        self.assertEqual(need.state, 'meeting_completed')

        contract = need.with_user(self.manager).action_start_contract()
        self.assertEqual(need.state, 'contract')
        self._sign_contract(contract)
        self.assertEqual(need.state, 'integration_pending',
                          "no real Google Workspace integration exists — must land here, "
                          "never silently claim success")
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
        self.assertEqual(need.state, 'publication_pending',
                          "no student-platform API exists — must land here, never claim published")
        self.assertTrue(need.publication_pending)

        need.with_user(self.manager).action_mark_publication_done()
        self.assertEqual(need.state, 'published')
        self.assertEqual(sheet.state, 'published')

    # ------------------------------------------------------------------
    # External path: no internal teacher -> external candidates -> explicit,
    # explainable ranking -> best candidate selected.
    # ------------------------------------------------------------------
    def test_external_candidate_ranking_path(self):
        need = self._make_need(specialty='Networking')
        need.with_user(self.manager).action_search_internal()
        need.with_user(self.manager).action_no_internal_teacher_found()
        self.assertEqual(need.state, 'searching_external')

        weak = self.Person.create({
            'first_name': 'Weak', 'last_name': 'Candidate', 'is_internal_teacher': 'external'})
        strong = self.Person.create({
            'first_name': 'Strong', 'last_name': 'Candidate', 'specialty': 'Networking',
            'is_internal_teacher': 'external',
        })
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

    # ------------------------------------------------------------------
    # Decline: candidate A declines -> candidate B becomes available for
    # MANUAL selection — nothing auto-picks B.
    # ------------------------------------------------------------------
    def test_candidate_decline_requires_manual_next_selection(self):
        need = self._make_need()
        need.with_user(self.manager).action_search_internal()
        need.with_user(self.manager).action_no_internal_teacher_found()

        person_a = self.Person.create({
            'first_name': 'Candidate', 'last_name': 'A', 'is_internal_teacher': 'external'})
        person_b = self.Person.create({
            'first_name': 'Candidate', 'last_name': 'B', 'is_internal_teacher': 'external'})
        cand_a = self.Candidature.create({'person_id': person_a.id, 'need_id': need.id})
        cand_b = self.Candidature.create({'person_id': person_b.id, 'need_id': need.id})

        need.with_user(self.manager).action_select_candidate(cand_a)
        need.with_user(self.manager).action_contact_candidate()
        cand_a.with_user(self.manager).action_mark_declined()

        self.assertEqual(cand_a.state, 'declined')
        self.assertFalse(need.selected_candidature_id, "declining must clear the selection, not skip to B")
        self.assertEqual(need.state, 'searching_external',
                          "must revert to searching, not auto-advance")
        self.assertEqual(cand_b.state, 'prospect',
                          "candidate B is available, not automatically selected")

        # Manual selection of B works.
        cand_b.with_user(self.manager).action_select_this_candidate()
        self.assertEqual(need.selected_candidature_id, cand_b)

    # ------------------------------------------------------------------
    # 48h reminder — mandatory: reminds Pédagogie, never changes state,
    # never auto-selects a next candidate.
    # ------------------------------------------------------------------
    def test_48h_reminder_never_auto_advances(self):
        need = self._make_need()
        person_a = self.Person.create({
            'first_name': 'Reminder', 'last_name': 'A', 'is_internal_teacher': 'external'})
        person_b = self.Person.create({
            'first_name': 'Reminder', 'last_name': 'B', 'is_internal_teacher': 'external'})
        cand_a = self.Candidature.create({'person_id': person_a.id, 'need_id': need.id})
        cand_b = self.Candidature.create({'person_id': person_b.id, 'need_id': need.id})

        need.with_user(self.manager).action_select_candidate(cand_a)
        need.with_user(self.manager).action_contact_candidate()
        # Simulate 49h having passed since contact.
        cand_a.contacted_date = cand_a.contacted_date - timedelta(hours=49)

        self.Candidature._cron_insite_reminder_check()
        cand_a.invalidate_recordset()

        self.assertTrue(cand_a.reminder_sent)
        self.assertEqual(cand_a.state, 'contacted', "the cron must never change state")
        self.assertEqual(need.state, 'awaiting_response', "the cron must never change the Need's state")
        self.assertEqual(cand_b.state, 'prospect', "candidate B must never be auto-selected")
        self.assertTrue(cand_a.activity_ids, "an activity reminding Pédagogie must have been created")

        # No duplicate reminder on a second run.
        activity_count = len(cand_a.activity_ids)
        self.Candidature._cron_insite_reminder_check()
        self.assertEqual(len(cand_a.activity_ids), activity_count, "must not send a duplicate reminder")

    # ------------------------------------------------------------------
    # Contract rejection -> recruitment does not continue to integration.
    # ------------------------------------------------------------------
    def test_contract_rejection_stops_recruitment(self):
        need = self._make_need()
        person = self.Person.create({
            'first_name': 'Reject', 'last_name': 'Contract', 'is_internal_teacher': 'external'})
        candidature = self.Candidature.create({'person_id': person.id, 'need_id': need.id})
        self._accept_candidate(need, candidature)
        contract = need.with_user(self.manager).action_start_contract()

        contract.with_user(self.manager).action_prepare()
        contract.with_user(self.manager).action_send()
        contract.with_user(self.manager).action_candidate_reject()

        self.assertEqual(contract.state, 'rejected')
        self.assertEqual(need.state, 'cancelled')
        self.assertFalse(self.Engagement.search([('need_id', '=', need.id)]))
        self.assertFalse(self.ModuleSheet.search([('engagement_id.need_id', '=', need.id)]))

    # ------------------------------------------------------------------
    # Module validation: submitted -> modification requested -> resubmitted
    # -> approved -> publication triggered.
    # ------------------------------------------------------------------
    def test_module_validation_and_publication_flow(self):
        engagement = self.Engagement.create({
            'person_id': self.Person.create({'first_name': 'Module', 'last_name': 'Flow'}).id,
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

        # Publication triggering (Need -> integration -> module -> publication)
        # is exercised end-to-end in test_internal_teacher_path; here we only
        # confirm validate() is rejected once already validated.
        with self.assertRaises(UserError):
            sheet.with_user(self.manager).action_validate()

    # ------------------------------------------------------------------
    # Meeting scheduling: no self-service booking, no hardcoded datetime,
    # never a second orphaned calendar.event — Schedule/Reschedule are
    # deliberately separate, guarded entry points.
    # ------------------------------------------------------------------
    def test_meeting_schedule_guard_and_reschedule(self):
        need = self._make_need()
        person = self.Person.create({
            'first_name': 'Meeting', 'last_name': 'Flow', 'is_internal_teacher': 'external'})
        candidature = self.Candidature.create({'person_id': person.id, 'need_id': need.id})
        need.with_user(self.manager).action_select_candidate(candidature)
        need.with_user(self.manager).action_contact_candidate()
        candidature.with_user(self.manager).action_mark_accepted()

        # Scheduling before any meeting exists must succeed and open no
        # public/self-service surface — just a real, linked calendar.event.
        first_start = fields.Datetime.now() + timedelta(days=5)
        self._schedule_meeting(candidature, start=first_start, location='Room A')
        event = candidature.meeting_event_id
        self.assertTrue(event)
        self.assertEqual(event.start, first_start)
        self.assertEqual(event.location, 'Room A')
        self.assertEqual(need.state, 'meeting_scheduled')

        # Scheduling again (not rescheduling) must be blocked, not silently
        # create a second event.
        with self.assertRaises(UserError):
            candidature.with_user(self.manager).action_schedule_meeting()
        with self.assertRaises(UserError):
            self._schedule_meeting(candidature, start=fields.Datetime.now() + timedelta(days=6))
        self.assertEqual(
            self.env['calendar.event'].search_count([('id', '=', event.id)]), 1,
            "must never end up with a second event")

        # Reschedule must edit the SAME event, not create a new one.
        new_start = fields.Datetime.now() + timedelta(days=7)
        self._schedule_meeting(candidature, reschedule=True, start=new_start, location='Room B')
        self.assertEqual(candidature.meeting_event_id, event, "reschedule must reuse the same record")
        self.assertEqual(event.start, new_start)
        self.assertEqual(event.location, 'Room B')

        # Rescheduling before any meeting exists must be blocked.
        candidature2 = self.Candidature.create({'person_id': person.id, 'need_id': need.id})
        with self.assertRaises(UserError):
            candidature2.with_user(self.manager).action_reschedule_meeting()

        # Contract gate: cannot start before the meeting is marked completed.
        with self.assertRaises(UserError):
            need.with_user(self.manager).action_start_contract()
        need.with_user(self.manager).action_mark_meeting_completed()
        self.assertEqual(need.state, 'meeting_completed')
        need.with_user(self.manager).action_start_contract()
        self.assertEqual(need.state, 'contract')
