"""Le pointage de l'equipe hygiene, sur la journee de maintenance_university.

La responsable pointe pour les salariees qui n'ont pas de compte ; la
maintenance garde sa regle stricte (personne ne pointe pour un autre).
"""

from datetime import timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import HygieneCase


@tagged("post_install", "-at_install")
class TestClock(HygieneCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.maint_manager = Users.create(
            {
                "name": "Chef maintenance",
                "login": "chef.maint.hyg@his.test",
                "group_ids": [(6, 0, [cls.env.ref("maintenance_university.group_maintenance_manager").id])],
            }
        )
        cls.maint_worker_user = Users.create(
            {
                "name": "Rachid",
                "login": "rachid.maint.hyg@his.test",
                "group_ids": [(6, 0, [cls.env.ref("maintenance_university.group_maintenance_worker").id])],
            }
        )
        cls.maint_worker = cls.env["hr.employee"].create({"name": "Rachid", "user_id": cls.maint_worker_user.id})
        cls.Workday = cls.env["maintenance.university.workday"]

    def _clock(self, user, employee, action):
        return self.Workday.with_user(user).his_hygiene_clock(employee.id, action)

    def _day(self, employee):
        return self.Workday.sudo().search([("employee_id", "=", employee.id)], limit=1)

    def test_le_responsable_pointe_une_salariee_sans_compte(self):
        for action in ("start", "pause", "resume", "end"):
            self._clock(self.manager_user, self.karima, action)
        day = self._day(self.karima)
        self.assertEqual(day.state, "done")
        self.assertEqual(day.his_team, "hygiene")
        self.assertEqual(len(day.segment_ids), 3)
        self.assertEqual(day.segment_ids.entered_by_id, self.manager_user)
        self.assertEqual(day.ended_by_id, self.manager_user)

    def test_la_salariee_pointe_elle_meme(self):
        payload = self._clock(self.fatima_user, self.fatima, "start")
        self.assertEqual(payload["state"], "working")
        self.assertEqual(self._day(self.fatima).segment_ids.entered_by_id, self.fatima_user)

    def test_le_bouton_de_my_work_range_aussi_dans_l_hygiene(self):
        self.Workday.with_user(self.fatima_user).action_start_day()
        self.assertEqual(self._day(self.fatima).his_team, "hygiene")

    def test_une_salariee_ne_pointe_pas_une_autre(self):
        with self.assertRaises(AccessError):
            self._clock(self.fatima_user, self.karima, "start")

    def test_le_responsable_ne_pointe_pas_hors_equipe(self):
        with self.assertRaises(AccessError):
            self._clock(self.manager_user, self.maint_worker, "start")

    def test_le_responsable_maintenance_ne_pointe_pas_l_hygiene(self):
        self._clock(self.manager_user, self.karima, "start")
        day = self._day(self.karima)
        with self.assertRaises(AccessError):
            self._clock(self.maint_manager, self.karima, "pause")
        with self.assertRaises(UserError):
            day.with_user(self.maint_manager).action_pause()

    def test_le_responsable_hygiene_ne_pointe_pas_la_maintenance(self):
        self.Workday.with_user(self.maint_worker_user).action_start_day()
        day = self._day(self.maint_worker)
        self.assertEqual(day.his_team, "maintenance")
        with self.assertRaises(UserError):
            day.with_user(self.manager_user).action_pause()

    def test_chaque_equipe_ne_voit_que_ses_journees(self):
        self._clock(self.manager_user, self.karima, "start")
        self.Workday.with_user(self.maint_worker_user).action_start_day()
        hyg_day, maint_day = self._day(self.karima), self._day(self.maint_worker)
        self.env.invalidate_all()
        seen_by_maint = self.Workday.with_user(self.maint_manager).search([])
        seen_by_hyg = self.Workday.with_user(self.manager_user).search([])
        self.assertIn(maint_day, seen_by_maint)
        self.assertNotIn(hyg_day, seen_by_maint)
        self.assertIn(hyg_day, seen_by_hyg)
        self.assertNotIn(maint_day, seen_by_hyg)

    def test_une_correction_garde_l_heure_d_origine(self):
        self._clock(self.manager_user, self.karima, "start")
        self._clock(self.manager_user, self.karima, "end")
        segment = self._day(self.karima).segment_ids
        start = segment.date_start
        segment.with_user(self.manager_user).write({"date_start": start - timedelta(hours=1)})
        segment.with_user(self.manager_user).write({"date_start": start - timedelta(hours=2)})
        self.assertEqual(segment.original_date_start, start)
        self.assertEqual(segment.corrected_by_id, self.manager_user)
        self.assertAlmostEqual(segment.duration, 2.0, delta=0.01)
