"""Le planning mensuel : zones x jours, saisi librement par la responsable."""

from datetime import date

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common import HygieneCase


@tagged("post_install", "-at_install")
class TestPlanning(HygieneCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Assignment = cls.env["his.hygiene.assignment"]
        cls.Plan = cls.Assignment.with_user(cls.manager_user)

    def _cell(self, area, day):
        matrix = self.Plan.get_matrix(day.year, day.month)
        return matrix["cells"].get(f"{area.id}|{day.isoformat()}", {})

    def test_une_case_peut_porter_deux_salariees(self):
        cell = self.Plan.set_cell(self.area_rdc.id, "2026-11-02", [self.fatima.id, self.karima.id])
        self.assertEqual(set(cell["employee_ids"]), {self.fatima.id, self.karima.id})
        self.assertEqual(
            set(self._cell(self.area_rdc, date(2026, 11, 2))["employee_ids"]), {self.fatima.id, self.karima.id}
        )

    def test_une_salariee_peut_avoir_plusieurs_zones_le_meme_jour(self):
        self.Plan.set_cell(self.area_rdc.id, "2026-11-02", [self.fatima.id])
        self.Plan.set_cell(self.area_amphi.id, "2026-11-02", [self.fatima.id])
        self.assertEqual(self.Assignment.search_count([("employee_ids", "in", self.fatima.id)]), 2)

    def test_vider_une_case_la_supprime(self):
        self.Plan.set_cell(self.area_rdc.id, "2026-11-02", [self.fatima.id])
        self.assertEqual(self.Plan.set_cell(self.area_rdc.id, "2026-11-02", []), {})
        self.assertFalse(self.Assignment.search([("area_id", "=", self.area_rdc.id)]))

    def test_une_absence_decouvre_la_zone(self):
        self.Plan.set_cell(self.area_rdc.id, "2026-11-02", [self.karima.id])
        self.assertTrue(self.Plan.toggle_absence(self.karima.id, "2026-11-02"))
        cell = self._cell(self.area_rdc, date(2026, 11, 2))
        self.assertTrue(cell["uncovered"])
        self.assertEqual(cell["absent_ids"], [self.karima.id])
        self.Plan.set_cell(self.area_rdc.id, "2026-11-02", [self.karima.id, self.fatima.id])
        self.assertFalse(self._cell(self.area_rdc, date(2026, 11, 2))["uncovered"])

    def test_l_absence_se_retire_d_un_second_clic(self):
        self.Plan.toggle_absence(self.karima.id, "2026-11-02")
        self.assertFalse(self.Plan.toggle_absence(self.karima.id, "2026-11-02"))
        self.assertFalse(self.env["his.hygiene.absence"].search([("employee_id", "=", self.karima.id)]))

    def test_les_jours_off_sont_signales(self):
        days = {d["day"]: d for d in self.Plan.get_matrix(2026, 11)["days"]}
        self.assertEqual(len(days), 30)
        self.assertTrue(days[6]["off"])  # vendredi
        self.assertTrue(days[7]["off"])  # samedi
        self.assertFalse(days[1]["off"])  # dimanche

    def test_remplir_une_ligne_saute_les_jours_off(self):
        count = self.Plan.fill_range(self.area_rdc.id, "2026-11-01", "2026-11-07", [self.fatima.id])
        self.assertEqual(count, 5)
        dates = self.Assignment.search([("area_id", "=", self.area_rdc.id)]).mapped("date")
        self.assertNotIn(date(2026, 11, 6), dates)
        self.assertNotIn(date(2026, 11, 7), dates)

    def test_copier_le_mois_precedent(self):
        self.Plan.set_cell(self.area_rdc.id, "2026-10-01", [self.fatima.id])  # -> dim. 1er nov.
        self.Plan.set_cell(self.area_rdc.id, "2026-10-06", [self.fatima.id])  # -> ven. 6 nov. : off
        self.Plan.set_cell(self.area_rdc.id, "2026-10-31", [self.fatima.id])  # -> pas de 31 nov.
        self.assertEqual(self.Plan.copy_previous_month(2026, 11), 1)
        nov = self.Assignment.search([("area_id", "=", self.area_rdc.id), ("date", ">=", "2026-11-01")])
        self.assertEqual(nov.mapped("date"), [date(2026, 11, 1)])

    def test_copier_ne_remplace_pas_une_case_deja_planifiee(self):
        self.Plan.set_cell(self.area_rdc.id, "2026-10-01", [self.fatima.id])
        self.Plan.set_cell(self.area_rdc.id, "2026-11-01", [self.karima.id])
        self.assertEqual(self.Plan.copy_previous_month(2026, 11), 0)

    def test_une_salariee_coche_sa_zone(self):
        cell = self.Plan.set_cell(self.area_rdc.id, "2026-11-02", [self.fatima.id])
        assignment = self.Assignment.browse(cell["id"])
        assignment.with_user(self.fatima_user).action_mark_done()
        self.assertTrue(assignment.is_done)
        self.assertEqual(assignment.done_by_id, self.fatima_user)

    def test_une_salariee_ne_coche_pas_la_zone_d_une_autre(self):
        cell = self.Plan.set_cell(self.area_rdc.id, "2026-11-02", [self.karima.id])
        with self.assertRaises(AccessError):
            self.Assignment.browse(cell["id"]).with_user(self.fatima_user).action_mark_done()

    def test_la_responsable_coche_pour_une_salariee_sans_compte(self):
        cell = self.Plan.set_cell(self.area_rdc.id, "2026-11-02", [self.karima.id])
        self.Assignment.browse(cell["id"]).with_user(self.manager_user).action_mark_done()
        self.assertTrue(self._cell(self.area_rdc, date(2026, 11, 2))["done"])

    def test_seule_la_responsable_planifie(self):
        with self.assertRaises(AccessError):
            self.Assignment.with_user(self.fatima_user).get_matrix(2026, 11)
        with self.assertRaises(AccessError):
            self.Assignment.with_user(self.fatima_user).set_cell(self.area_rdc.id, "2026-11-02", [self.fatima.id])

    def test_on_ne_planifie_que_l_equipe(self):
        stranger = self.env["hr.employee"].create({"name": "Hors equipe"})
        with self.assertRaises(ValidationError):
            self.Plan.set_cell(self.area_rdc.id, "2026-11-02", [stranger.id])
