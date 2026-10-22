"""La journee, le mois d'une salariee et le recapitulatif de la responsable.

Un jour planifie et non marque absent compte comme travaille, pointe ou non
(decision de Mohamed) : les heures ne viennent que des jours pointes.
"""

from datetime import datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import HygieneCase


@tagged("post_install", "-at_install")
class TestRecap(HygieneCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Aucun jour off : les dates de test tombent n'importe quel jour.
        cls.env["ir.config_parameter"].sudo().set_param("his_hygiene.off_weekdays", "")
        cls.Plan = cls.env["his.hygiene.assignment"].with_user(cls.manager_user)
        cls.Recap = cls.env["his.hygiene.recap"]
        today = fields.Date.context_today(cls.env["his.hygiene.recap"])
        cls.d1 = today.replace(day=1) - relativedelta(months=1)
        cls.d2 = cls.d1 + timedelta(days=1)

    def _row(self, recap, employee):
        return next(w for w in recap["workers"] if w["employee_id"] == employee.id)

    def _recap(self):
        return self.Recap.with_user(self.manager_user).get_recap(-1)

    def test_un_jour_planifie_sans_pointage_compte(self):
        self.Plan.set_cell(self.area_rdc.id, str(self.d1), [self.karima.id])
        self.Plan.set_cell(self.area_amphi.id, str(self.d1), [self.karima.id])
        self.Plan.set_cell(self.area_rdc.id, str(self.d2), [self.karima.id])
        row = self._row(self._recap(), self.karima)
        self.assertEqual(row["days_worked"], 2)
        self.assertEqual(row["worked_hours"], 0)
        self.assertEqual(row["unclocked_days"], 2)
        self.assertEqual(row["areas_planned"], 3)
        self.assertEqual(row["areas_done"], 0)

    def test_un_jour_d_absence_ne_compte_pas(self):
        self.Plan.set_cell(self.area_rdc.id, str(self.d1), [self.karima.id])
        self.Plan.set_cell(self.area_rdc.id, str(self.d2), [self.karima.id])
        self.Plan.toggle_absence(self.karima.id, str(self.d2))
        recap = self._recap()
        row = self._row(recap, self.karima)
        self.assertEqual(row["days_worked"], 1)
        self.assertEqual(row["days_absent"], 1)
        area = next(a for a in recap["areas"] if a["id"] == self.area_rdc.id)
        self.assertEqual((area["planned"], area["done"], area["uncovered"]), (2, 0, 1))

    def test_les_heures_viennent_des_jours_pointes(self):
        self.Plan.set_cell(self.area_rdc.id, str(self.d1), [self.fatima.id])
        self.Plan.set_cell(self.area_rdc.id, str(self.d2), [self.fatima.id])
        start = datetime.combine(self.d1, time(7, 0))
        day = self.env["maintenance.university.workday"].sudo().create(
            {
                "employee_id": self.fatima.id,
                "date": self.d1,
                "date_start": start,
                "date_end": start + timedelta(hours=3),
                "his_team": "hygiene",
            }
        )
        Segment = self.env["maintenance.university.workday.segment"].sudo()
        Segment.create({"workday_id": day.id, "kind": "work", "date_start": start, "date_end": start + timedelta(hours=2)})
        Segment.create(
            {"workday_id": day.id, "kind": "pause", "date_start": start + timedelta(hours=2), "date_end": start + timedelta(hours=3)}
        )
        row = self._row(self._recap(), self.fatima)
        self.assertAlmostEqual(row["worked_hours"], 2.0, places=2)
        self.assertAlmostEqual(row["break_hours"], 1.0, places=2)
        self.assertEqual(row["unclocked_days"], 1)

    def test_l_equite_compte_les_jours_par_zone(self):
        self.Plan.set_cell(self.area_rdc.id, str(self.d1), [self.fatima.id])
        self.Plan.set_cell(self.area_rdc.id, str(self.d2), [self.fatima.id])
        self.Plan.set_cell(self.area_amphi.id, str(self.d1), [self.fatima.id])
        fairness = self._recap()["fairness"]
        self.assertEqual(fairness["areas"], [self.area_rdc.name, self.area_amphi.name])
        row = next(r for r in fairness["rows"] if r["name"] == self.fatima.name)
        self.assertEqual(row["counts"], [2, 1])

    def test_les_constats_comptent(self):
        self.env["his.hygiene.finding"].with_user(self.fatima_user).create(
            {"area_id": self.area_rdc.id, "kind": "cleaning", "description": "Eau", "date": self.d1}
        )
        self.assertEqual(self._row(self._recap(), self.fatima)["findings"], 1)

    def test_la_salariee_lit_son_mois(self):
        self.Plan.set_cell(self.area_rdc.id, str(self.d1), [self.fatima.id])
        month = self.Recap.with_user(self.fatima_user).get_month(False, -1)
        self.assertEqual(month["totals"]["days_worked"], 1)
        self.assertEqual(month["days"][0]["areas"], [self.area_rdc.name])

    def test_une_salariee_ne_lit_pas_le_mois_d_une_autre(self):
        with self.assertRaises(AccessError):
            self.Recap.with_user(self.fatima_user).get_month(self.karima.id, -1)
        with self.assertRaises(AccessError):
            self.Recap.with_user(self.fatima_user).get_today(self.karima.id)

    def test_seule_la_responsable_lit_le_recapitulatif(self):
        with self.assertRaises(AccessError):
            self.Recap.with_user(self.fatima_user).get_recap(0)

    def test_la_responsable_ouvre_la_journee_d_une_salariee(self):
        today = fields.Date.context_today(self.Recap)
        self.Plan.set_cell(self.area_rdc.id, str(today), [self.karima.id])
        payload = self.Recap.with_user(self.manager_user).get_today(self.karima.id)
        self.assertEqual(payload["employee"]["id"], self.karima.id)
        self.assertTrue(payload["is_manager"])
        self.assertEqual([a["area"] for a in payload["assignments"]], [self.area_rdc.name])
        self.assertFalse(payload["day"]["state"])
        self.assertEqual(len(payload["members"]), 2)

    def test_la_salariee_voit_sa_journee(self):
        payload = self.Recap.with_user(self.fatima_user).get_today()
        self.assertEqual(payload["employee"]["id"], self.fatima.id)
        self.assertFalse(payload["is_manager"])
        self.assertEqual(payload["members"], [])

    def test_la_journee_liste_les_zones_pour_signaler(self):
        payload = self.Recap.with_user(self.fatima_user).get_today()
        self.assertEqual({a["id"] for a in payload["areas"]}, {self.area_rdc.id, self.area_amphi.id})
