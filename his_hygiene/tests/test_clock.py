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

    # ------------------------------------------------------------------
    # Revue finale : fin oubliee et journees qu'on ne doit pas pouvoir forger
    # ------------------------------------------------------------------
    def _forgotten_day(self):
        self._clock(self.manager_user, self.karima, "start")
        day = self._day(self.karima)
        yesterday = day.date - timedelta(days=1)
        day.sudo().write({"date": yesterday, "date_start": day.date_start - timedelta(days=1)})
        day.segment_ids.sudo().write({"date_start": day.date_start})
        return day

    def test_la_responsable_termine_une_journee_oubliee(self):
        day = self._forgotten_day()
        end = day.date_start + timedelta(hours=7)
        day.with_user(self.manager_user).write({"date_end": end})
        self.assertEqual(day.state, "done")
        segment = day.segment_ids
        self.assertEqual(segment.date_end, end, "la tranche restee ouverte se ferme a la fin saisie")
        self.assertEqual(segment.corrected_by_id, self.manager_user)
        self.assertAlmostEqual(day.worked_hours, 7.0, delta=0.01)

    def test_corriger_le_debut_d_une_tranche_ouverte_garde_l_origine(self):
        self._clock(self.manager_user, self.karima, "start")
        segment = self._day(self.karima).segment_ids
        start = segment.date_start
        segment.with_user(self.manager_user).write({"date_start": start - timedelta(hours=1)})
        self.assertEqual(segment.original_date_start, start)
        self.assertEqual(segment.corrected_by_id, self.manager_user)

    def test_les_boutons_ne_sont_pas_des_corrections(self):
        for action in ("start", "pause", "resume", "end"):
            self._clock(self.manager_user, self.karima, action)
        self.assertFalse(self._day(self.karima).segment_ids.corrected_by_id)

    def test_la_responsable_ne_deplace_pas_une_journee(self):
        self._clock(self.manager_user, self.karima, "start")
        day = self._day(self.karima)
        with self.assertRaises(UserError):
            day.with_user(self.manager_user).write({"employee_id": self.maint_worker.id})
        with self.assertRaises(UserError):
            day.with_user(self.manager_user).write({"his_team": "maintenance"})
        other = self.Workday.sudo().create({"employee_id": self.fatima.id, "his_team": "hygiene"})
        with self.assertRaises(UserError):
            day.segment_ids.with_user(self.manager_user).write({"workday_id": other.id})

    def test_la_responsable_ne_corrige_pas_sa_propre_journee_de_maintenance(self):
        both = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Double casquette",
                    "login": "double.hyg@his.test",
                    "group_ids": [
                        (
                            6,
                            0,
                            [self.group_manager.id, self.env.ref("maintenance_university.group_maintenance_worker").id],
                        )
                    ],
                }
            )
        )
        self.env["hr.employee"].create({"name": "Double casquette", "user_id": both.id})
        self.Workday.with_user(both).action_start_day()
        day = self.Workday.sudo().search([("employee_id.user_id", "=", both.id)])
        self.assertEqual(day.his_team, "maintenance")
        with self.assertRaises(UserError):
            day.with_user(both).write({"date_start": day.date_start - timedelta(hours=2)})
