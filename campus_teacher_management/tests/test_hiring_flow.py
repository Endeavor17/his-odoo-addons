from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import CampusCommon


@tagged('post_install', '-at_install')
class TestHiringFlow(CampusCommon):
    """The sequence from 'this one looks good' to an employee record."""

    def setUp(self):
        super().setUp()
        self._make_full_criteria_set()
        self.job = self.env['hr.job'].create({'name': 'Hiring Flow Post'})
        self.version.job_id = self.job.id
        self.version.action_publish()

        self.Slot = self.env['campus.interview.slot']
        self.applicant = self._make_applicant('Hire Me', campus_scientific_rank='prof')
        self.applicant.action_campus_evaluate()

    def _slot(self, days_ahead=1, hour=9, round_number='1'):
        start = fields.Datetime.now().replace(
            hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
        return self.Slot.create({
            'start_datetime': start,
            'duration': 0.5,
            'round': round_number,
            'interviewer_id': self.env.user.id,
        })

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def test_end_datetime_follows_duration(self):
        slot = self._slot()
        self.assertEqual(slot.end_datetime, slot.start_datetime + timedelta(minutes=30))

    def test_free_slots_excludes_booked_and_past(self):
        future = self._slot(days_ahead=2)
        past = self.Slot.create({
            'start_datetime': fields.Datetime.now() - timedelta(days=1),
            'duration': 0.5, 'round': '1', 'interviewer_id': self.env.user.id,
        })
        free = self.Slot._free_slots(1)
        self.assertIn(future, free)
        self.assertNotIn(past, free, "a slot in the past must not be offered")

        future._book(self.applicant)
        self.assertNotIn(future, self.Slot._free_slots(1),
                         "a booked slot must not be offered again")

    def test_booking_creates_a_meeting_linked_to_the_applicant(self):
        slot = self._slot()
        event = slot._book(self.applicant)
        self.assertEqual(slot.state, 'booked')
        self.assertEqual(slot.applicant_id, self.applicant)
        self.assertEqual(event.applicant_id, self.applicant)
        self.assertIn(event, self.applicant.meeting_ids)

    def test_candidate_is_not_invited_to_their_own_interview(self):
        """The recruiter confirms the time in their own reply, not Odoo.

        Odoo emails every attendee of a calendar event, so adding the candidate
        would send exactly the message the user asked us not to send.
        """
        self.applicant.partner_id = self.env['res.partner'].create({
            'name': 'Hire Me', 'email': 'hire.me@example.com'}).id
        slot = self._slot()
        event = slot._book(self.applicant)
        # attendee_ids is the real attendee list in Odoo 19; partner_ids reads
        # back empty once the attendees have been created from it.
        attendees = event.attendee_ids.partner_id
        self.assertNotIn(self.applicant.partner_id, attendees,
                         "the candidate must not be an attendee — Odoo emails attendees")
        self.assertIn(self.env.user.partner_id, attendees,
                      "the interviewer should be")

    def test_a_taken_slot_cannot_be_booked_twice(self):
        slot = self._slot()
        slot._book(self.applicant)
        other = self._make_applicant('Second Candidate')
        with self.assertRaises(UserError):
            slot._book(other)

    def test_releasing_a_slot_removes_the_meeting(self):
        slot = self._slot()
        event = slot._book(self.applicant)
        slot.action_release()
        self.assertEqual(slot.state, 'free')
        self.assertFalse(slot.applicant_id)
        self.assertFalse(event.exists(), "the calendar entry should go with the booking")

    def test_a_booked_slot_cannot_be_deleted(self):
        slot = self._slot()
        slot._book(self.applicant)
        with self.assertRaises(UserError):
            slot.unlink()

    # ------------------------------------------------------------------
    # Weekly generation
    # ------------------------------------------------------------------
    def test_weekly_generation_creates_the_expected_slots(self):
        monday = fields.Date.today() + timedelta(days=(7 - fields.Date.today().weekday()) % 7 or 7)
        wizard = self.env['campus.slot.generate'].create({
            'date_from': monday,
            'date_to': monday + timedelta(days=1),   # Monday + Tuesday
            'day_sun': False, 'day_mon': True, 'day_tue': True,
            'day_wed': False, 'day_thu': False, 'day_fri': False, 'day_sat': False,
            'time_from': 9.0, 'time_to': 11.0, 'duration': 0.5,
            'round': '1', 'interviewer_id': self.env.user.id,
        })
        before = self.Slot.search_count([])
        wizard.action_generate()
        # 2 days x 4 half-hour slots between 09:00 and 11:00
        self.assertEqual(self.Slot.search_count([]) - before, 8)

    def test_generating_twice_skips_what_already_exists(self):
        monday = fields.Date.today() + timedelta(days=(7 - fields.Date.today().weekday()) % 7 or 7)
        values = {
            'date_from': monday, 'date_to': monday,
            'day_sun': False, 'day_mon': True, 'day_tue': False, 'day_wed': False,
            'day_thu': False, 'day_fri': False, 'day_sat': False,
            'time_from': 9.0, 'time_to': 10.0, 'duration': 0.5,
            'round': '1', 'interviewer_id': self.env.user.id,
        }
        self.env['campus.slot.generate'].create(values).action_generate()
        after_first = self.Slot.search_count([])
        self.env['campus.slot.generate'].create(values).action_generate()
        self.assertEqual(self.Slot.search_count([]), after_first,
                         "running the wizard again must not duplicate slots")

    def test_generation_needs_at_least_one_day(self):
        wizard = self.env['campus.slot.generate'].create({
            'date_from': fields.Date.today(), 'date_to': fields.Date.today(),
            'day_sun': False, 'day_mon': False, 'day_tue': False, 'day_wed': False,
            'day_thu': False, 'day_fri': False, 'day_sat': False,
            'interviewer_id': self.env.user.id,
        })
        with self.assertRaises(UserError):
            wizard.action_generate()

    # ------------------------------------------------------------------
    # The funnel
    # ------------------------------------------------------------------
    def test_select_requires_a_slot_to_offer(self):
        """Inviting someone to pick from an empty list is worse than refusing."""
        self.assertFalse(self.Slot._free_slots(1))
        with self.assertRaises(UserError):
            self.applicant.action_campus_select()

    def test_full_sequence(self):
        self._slot(days_ahead=1, round_number='1')
        self._slot(days_ahead=8, round_number='2')

        self.applicant.action_campus_select()
        self.assertEqual(self.applicant.campus_hiring_state, 'invited')

        slot1 = self.Slot._free_slots(1)[0]
        self.env['campus.schedule.interview'].create({
            'applicant_id': self.applicant.id, 'round': '1', 'slot_id': slot1.id,
        }).action_confirm()
        self.assertEqual(self.applicant.campus_hiring_state, 'meeting_1')
        self.assertEqual(slot1.state, 'booked')

        self.applicant.write({
            'campus_cb_file': b'Y2I=', 'campus_cb_filename': 'cb.pdf',
            'campus_contract_file': b'Y3Q=', 'campus_contract_filename': 'contract.pdf',
        })
        self.applicant.action_campus_send_documents()
        self.assertEqual(self.applicant.campus_hiring_state, 'docs_sent')

        self.applicant.action_campus_record_acceptance()
        self.assertEqual(self.applicant.campus_hiring_state, 'docs_accepted')

        self.applicant.write({
            'campus_cb_final_file': b'ZmluYWw=', 'campus_cb_final_filename': 'final.pdf'})
        self.applicant.action_campus_send_final()
        self.assertEqual(self.applicant.campus_hiring_state, 'final_sent')

        slot2 = self.Slot._free_slots(2)[0]
        self.env['campus.schedule.interview'].create({
            'applicant_id': self.applicant.id, 'round': '2', 'slot_id': slot2.id,
        }).action_confirm()
        self.assertEqual(self.applicant.campus_hiring_state, 'meeting_2')

        self.applicant.action_campus_hire()
        self.assertEqual(self.applicant.campus_hiring_state, 'hired')
        self.assertTrue(self.applicant.campus_hiring_date)
        self.assertTrue(self.env['hr.employee'].search_count(
            [('name', '=', self.applicant.partner_name)]),
            "hiring should create the employee")

    def test_documents_cannot_be_sent_without_the_files(self):
        self._slot()
        self.applicant.action_campus_select()
        slot = self.Slot._free_slots(1)[0]
        self.env['campus.schedule.interview'].create({
            'applicant_id': self.applicant.id, 'round': '1', 'slot_id': slot.id,
        }).action_confirm()

        with self.assertRaises(UserError, msg="an empty contract must not be emailed"):
            self.applicant.action_campus_send_documents()

        # One of the two is still not enough.
        self.applicant.write({'campus_cb_file': b'Y2I=', 'campus_cb_filename': 'cb.pdf'})
        with self.assertRaises(UserError):
            self.applicant.action_campus_send_documents()

    def test_steps_cannot_be_taken_out_of_order(self):
        self._slot()
        with self.assertRaises(UserError, msg="cannot send documents before a meeting"):
            self.applicant.action_campus_send_documents()
        with self.assertRaises(UserError, msg="cannot record acceptance before sending"):
            self.applicant.action_campus_record_acceptance()
        with self.assertRaises(UserError, msg="cannot send the final breakdown first"):
            self.applicant.action_campus_send_final()
        with self.assertRaises(UserError, msg="cannot hire straight away"):
            self.applicant.action_campus_hire()

    def test_select_only_once(self):
        self._slot()
        self.applicant.action_campus_select()
        with self.assertRaises(UserError):
            self.applicant.action_campus_select()

    def test_emails_are_queued_for_each_send(self):
        self._slot(days_ahead=1, round_number='1')
        Mail = self.env['mail.mail']
        before = Mail.search_count([])
        self.applicant.action_campus_select()
        self.assertEqual(Mail.search_count([]) - before, 1,
                         "selecting should queue exactly one email")

    def test_reset_returns_to_the_start(self):
        self._slot()
        self.applicant.action_campus_select()
        self.applicant.action_campus_reset_hiring()
        self.assertEqual(self.applicant.campus_hiring_state, 'not_selected')
