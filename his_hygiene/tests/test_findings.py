"""Les constats : une panne part en maintenance, une salissure revient a la responsable."""

import base64

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import HygieneCase

# Un PNG d'un pixel.
PIXEL = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
    )
)


@tagged("post_install", "-at_install")
class TestFindings(HygieneCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Finding = cls.env["his.hygiene.finding"]

    def _report(self, user, area, kind, **vals):
        return self.Finding.with_user(user).create(
            {"area_id": area.id, "kind": kind, "description": "Robinet qui fuit", **vals}
        )

    def test_une_panne_part_en_maintenance(self):
        finding = self._report(self.fatima_user, self.area_amphi, "repair", image=PIXEL)
        maint = finding.sudo().maintenance_finding_id
        self.assertEqual(finding.state, "sent")
        self.assertEqual(maint.state, "submitted")
        self.assertEqual(maint.building_id, self.bloc)
        self.assertEqual(maint.his_room_id, self.loc_amphi)
        self.assertEqual(maint.category_id, self.env.ref("his_hygiene.category_reported_by_hygiene"))
        self.assertEqual(maint.employee_id, self.fatima)
        self.assertEqual(len(maint.image_ids), 1)

    def test_une_panne_sur_un_batiment_entier_n_a_pas_de_salle(self):
        area = self.env["his.hygiene.area"].create({"location_id": self.bloc.his_location_id.id})
        finding = self._report(self.manager_user, area, "repair", employee_id=self.karima.id)
        self.assertFalse(finding.sudo().maintenance_finding_id.his_room_id)
        self.assertEqual(finding.sudo().maintenance_finding_id.employee_id, self.karima)

    def test_une_salissure_revient_a_la_responsable(self):
        self.env["his.hygiene.assignment"].with_user(self.manager_user).set_cell(
            self.area_rdc.id, "2026-11-02", [self.karima.id]
        )
        finding = self._report(self.fatima_user, self.area_rdc, "cleaning", date="2026-11-02")
        self.assertEqual(finding.state, "new")
        self.assertFalse(finding.maintenance_finding_id)
        extra = finding.with_user(self.manager_user).action_dispatch()
        self.assertEqual(finding.state, "dispatched")
        self.assertTrue(extra.is_extra)
        self.assertEqual(extra.finding_id, finding)
        self.assertEqual(extra.employee_ids, self.karima, "par defaut, l'equipe deja sur la zone ce jour-la")
        matrix = self.env["his.hygiene.assignment"].with_user(self.manager_user).get_matrix(2026, 11)
        self.assertEqual(matrix["cells"][f"{self.area_rdc.id}|2026-11-02"]["extra"], 1)

    def test_une_salariee_ne_dispatche_pas(self):
        finding = self._report(self.fatima_user, self.area_rdc, "cleaning")
        with self.assertRaises(AccessError):
            finding.with_user(self.fatima_user).action_dispatch()

    def test_une_panne_ne_se_dispatche_pas(self):
        finding = self._report(self.fatima_user, self.area_rdc, "repair")
        with self.assertRaises(UserError):
            finding.with_user(self.manager_user).action_dispatch()

    def test_une_salariee_ne_signale_pas_au_nom_d_une_autre(self):
        with self.assertRaises(AccessError):
            self._report(self.fatima_user, self.area_rdc, "cleaning", employee_id=self.karima.id)

    def test_une_salariee_ne_voit_que_ses_constats(self):
        mine = self._report(self.fatima_user, self.area_rdc, "cleaning")
        other = self._report(self.manager_user, self.area_rdc, "cleaning", employee_id=self.karima.id)
        self.env.invalidate_all()
        seen = self.Finding.with_user(self.fatima_user).search([])
        self.assertIn(mine, seen)
        self.assertNotIn(other, seen)

    def test_la_salariee_ne_voit_pas_les_demandes_de_maintenance(self):
        self.env["maintenance.request"].create(
            {
                "name": "Demande interne",
                "building_id": self.bloc.id,
                "maintenance_category_id": self.env.ref("his_hygiene.category_reported_by_hygiene").id,
            }
        )
        self.env.invalidate_all()
        self.assertFalse(self.env["maintenance.request"].with_user(self.fatima_user).search([]))
