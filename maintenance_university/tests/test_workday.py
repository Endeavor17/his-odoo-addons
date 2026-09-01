# -*- coding: utf-8 -*-
"""La journee de travail : arrivee, pauses, depart.

C'est la presence, pas le temps passe sur les demandes. Les deux comptent des
choses differentes et doivent diverger : l'ecart entre les heures presentes et
les heures imputees aux demandes, c'est le trajet et l'attente.

Le calcul qui compte vraiment est celui de la pause : si worked_hours
l'incluait, on paierait le dejeuner de tout le monde sans que rien ne le
signale.
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWorkday(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.worker_group = cls.env.ref('maintenance_university.group_maintenance_worker')
        cls.user = cls.env['res.users'].create({
            'name': "Rayan",
            'login': "rayan.workday@his.test",
            'group_ids': [(6, 0, [cls.worker_group.id])],
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': "Rayan", 'user_id': cls.user.id,
        })
        cls.Workday = cls.env['maintenance.university.workday'].with_user(cls.user)

    def _day(self):
        return self.env['maintenance.university.workday'].search(
            [('employee_id', '=', self.employee.id)], limit=1,
        )

    # ------------------------------------------------------------------
    # The four buttons
    # ------------------------------------------------------------------
    def test_starting_the_day_opens_one_working_segment(self):
        self.Workday.action_start_day()
        day = self._day()

        self.assertEqual(day.state, 'working')
        self.assertEqual(day.date, fields.Date.context_today(day))
        self.assertFalse(day.date_end, "the day is still running")
        self.assertEqual(len(day.segment_ids), 1)
        self.assertEqual(day.segment_ids.kind, 'work')
        self.assertFalse(day.segment_ids.date_end, "the segment is still open")

    def test_pause_closes_the_work_and_opens_a_break(self):
        self.Workday.action_start_day()
        day = self._day()
        day.with_user(self.user).action_pause()

        self.assertEqual(day.state, 'paused')
        self.assertEqual(len(day.segment_ids), 2)
        work, pause = day.segment_ids.sorted('date_start')
        self.assertTrue(work.date_end, "the working stretch is closed")
        self.assertEqual(pause.kind, 'pause')
        self.assertFalse(pause.date_end, "the break is running")

    def test_resume_closes_the_break_and_opens_work_again(self):
        self.Workday.action_start_day()
        day = self._day()
        day.with_user(self.user).action_pause()
        day.with_user(self.user).action_resume()

        self.assertEqual(day.state, 'working')
        self.assertEqual(len(day.segment_ids), 3)
        last = day.segment_ids.sorted('date_start')[-1]
        self.assertEqual(last.kind, 'work')
        self.assertFalse(last.date_end, "the new working stretch is open")
        pause = day.segment_ids.filtered(lambda s: s.kind == 'pause')
        self.assertTrue(pause.date_end, "the break was closed on resume")

    def test_ending_the_day_closes_everything(self):
        self.Workday.action_start_day()
        day = self._day()
        day.with_user(self.user).action_end_day()

        self.assertEqual(day.state, 'done')
        self.assertTrue(day.date_end)
        self.assertFalse(
            day.segment_ids.filtered(lambda s: not s.date_end),
            "no segment may be left running once the day is over",
        )

    # ------------------------------------------------------------------
    # The arithmetic
    # ------------------------------------------------------------------
    def test_worked_hours_exclude_the_break(self):
        """08:30-12:00 worked, 12:00-12:45 break, 12:45-16:00 worked."""
        self.Workday.action_start_day()
        day = self._day()
        day.with_user(self.user).action_pause()
        day.with_user(self.user).action_resume()
        day.with_user(self.user).action_end_day()

        # Rewrite the stamps to a realistic day; the buttons above produced the
        # right *shape*, this fixes the clock so the totals are checkable.
        base = fields.Datetime.now().replace(hour=8, minute=30, second=0, microsecond=0)
        work_1, pause, work_2 = day.segment_ids.sorted('date_start')
        work_1.write({'date_start': base, 'date_end': base + timedelta(hours=3, minutes=30)})
        pause.write({
            'date_start': base + timedelta(hours=3, minutes=30),
            'date_end': base + timedelta(hours=4, minutes=15),
        })
        work_2.write({
            'date_start': base + timedelta(hours=4, minutes=15),
            'date_end': base + timedelta(hours=7, minutes=30),
        })

        self.assertAlmostEqual(day.worked_hours, 6.75, places=5)
        self.assertAlmostEqual(day.paused_hours, 0.75, places=5)

    # ------------------------------------------------------------------
    # Illegal moves
    # ------------------------------------------------------------------
    def test_a_day_cannot_be_started_twice(self):
        self.Workday.action_start_day()
        with self.assertRaises(UserError):
            self.Workday.action_start_day()

    def test_a_running_day_cannot_be_resumed(self):
        self.Workday.action_start_day()
        with self.assertRaises(UserError):
            self._day().with_user(self.user).action_resume()

    def test_a_paused_day_cannot_be_paused_again(self):
        self.Workday.action_start_day()
        day = self._day()
        day.with_user(self.user).action_pause()
        with self.assertRaises(UserError):
            day.with_user(self.user).action_pause()

    def test_a_finished_day_cannot_be_ended_again(self):
        self.Workday.action_start_day()
        day = self._day()
        day.with_user(self.user).action_end_day()
        with self.assertRaises(UserError):
            day.with_user(self.user).action_end_day()

    def test_nobody_can_clock_someone_elses_day(self):
        """Not even a manager: a leader who can clock you in has defeated the
        point of a presence record."""
        self.Workday.action_start_day()
        day = self._day()

        other_user = self.env['res.users'].create({
            'name': "Autre", 'login': "autre.workday@his.test",
            'group_ids': [(6, 0, [
                self.worker_group.id,
                self.env.ref('maintenance_university.group_maintenance_manager').id,
            ])],
        })
        self.env['hr.employee'].create({'name': "Autre", 'user_id': other_user.id})

        with self.assertRaises(UserError):
            day.with_user(other_user).action_pause()

    def test_a_user_without_an_employee_is_told_so(self):
        stranger = self.env['res.users'].create({
            'name': "Sans Fiche", 'login': "sans.fiche@his.test",
            'group_ids': [(6, 0, [self.worker_group.id])],
        })
        with self.assertRaises(UserError):
            self.env['maintenance.university.workday'].with_user(stranger).action_start_day()

    # ------------------------------------------------------------------
    # What the banner reads
    # ------------------------------------------------------------------
    def test_the_banner_reads_nothing_before_the_day_starts(self):
        day = self.Workday.get_my_day()
        self.assertTrue(day['has_employee'])
        self.assertFalse(day['state'], "no record yet reads the same as not started")

    def test_the_banner_counts_the_open_segment_live(self):
        """A stored duration is only written when a segment closes, so the
        running stretch has to be added on the way out or the counter sits at
        zero all morning."""
        self.Workday.action_start_day()
        day = self._day()
        day.segment_ids.date_start = fields.Datetime.now() - timedelta(hours=2)

        reading = self.Workday.get_my_day()
        self.assertEqual(reading['state'], 'working')
        self.assertGreater(reading['worked_seconds'], 7000, "roughly two hours, live")

    # ------------------------------------------------------------------
    # A presence record the worker cannot rewrite
    # ------------------------------------------------------------------
    def test_a_worker_cannot_rewrite_their_own_clock(self):
        """Otherwise the record measures nothing.

        The record rule scopes a worker to their own day - which is exactly the
        day they would want to move. Read is theirs; write is not.
        """
        self.Workday.action_start_day()
        day = self._day()

        with self.assertRaises(AccessError):
            day.with_user(self.user).write({'date_start': '2026-01-01 04:00:00'})

    def test_a_worker_cannot_rewrite_a_segment(self):
        self.Workday.action_start_day()
        day = self._day()
        segment = day.segment_ids[0]

        with self.assertRaises(AccessError):
            segment.with_user(self.user).write({'date_end': '2026-01-01 23:00:00'})

    def test_a_worker_cannot_invent_a_day_out_of_nothing(self):
        with self.assertRaises(AccessError):
            self.env['maintenance.university.workday'].with_user(self.user).create({
                'employee_id': self.employee.id,
                'date': fields.Date.context_today(self.env.user),
                'date_start': '2026-01-01 04:00:00',
            })

    def test_the_buttons_still_work_with_the_worker_read_only(self):
        """The whole point: locked down, and still usable."""
        self.Workday.action_start_day()
        day = self._day()
        day.with_user(self.user).action_pause()
        day.with_user(self.user).action_resume()
        day.with_user(self.user).action_end_day()

        self.assertEqual(day.state, 'done')
        self.assertEqual(len(day.segment_ids), 3)
        self.assertFalse(day.segment_ids.filtered(lambda s: not s.date_end))

    def test_a_manager_can_still_correct_a_forgotten_day(self):
        """The agreed recovery path, so read-only must not close it."""
        self.Workday.action_start_day()
        day = self._day()
        manager = self.env['res.users'].create({
            'name': "Chef", 'login': "chef.workday@his.test",
            'group_ids': [(6, 0, [
                self.worker_group.id,
                self.env.ref('maintenance_university.group_maintenance_manager').id,
            ])],
        })
        day.with_user(manager).write({'date_end': fields.Datetime.now()})
        self.assertEqual(day.state, 'done')

    # ------------------------------------------------------------------
    # What the leader sees
    # ------------------------------------------------------------------
    def test_the_employee_shows_todays_state_to_a_leader(self):
        """The field the whole Worker Summary column hangs off."""
        self.assertEqual(self.employee.maintenance_workday_state, 'not_started')

        self.Workday.action_start_day()
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.maintenance_workday_state, 'working')
        self.assertTrue(self.employee.maintenance_workday_started_at)

        day = self._day()
        day.with_user(self.user).action_pause()
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.maintenance_workday_state, 'paused')

        day.with_user(self.user).action_end_day()
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.maintenance_workday_state, 'done')

    def test_yesterdays_day_does_not_count_as_today(self):
        """Otherwise a leader sees a worker still 'Working' from last week."""
        self.Workday.action_start_day()
        day = self._day()
        day.with_user(self.user).action_end_day()
        day.date = fields.Date.context_today(day) - timedelta(days=1)

        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.maintenance_workday_state, 'not_started')
        self.assertFalse(self.employee.maintenance_workday_started_at)

    def test_the_banner_survives_a_user_with_no_employee(self):
        stranger = self.env['res.users'].create({
            'name': "Sans Fiche 2", 'login': "sans.fiche2@his.test",
            'group_ids': [(6, 0, [self.worker_group.id])],
        })
        reading = self.env['maintenance.university.workday'].with_user(stranger).get_my_day()
        self.assertFalse(reading['has_employee'], "a quiet message, not a traceback")
