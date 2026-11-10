"""Equipe et zones : les personnes et les lieux viennent des referentiels."""

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger
from psycopg2 import IntegrityError

from .common import HygieneCase


@tagged("post_install", "-at_install")
class TestConfig(HygieneCase):
    def test_une_zone_hors_batiment_est_refusee(self):
        with self.assertRaises(ValidationError):
            self.env["his.hygiene.area"].create({"location_id": self.env.ref("stock.stock_location_stock").id})

    def test_le_nom_de_zone_porte_le_batiment(self):
        self.assertEqual(self.area_rdc.name, "Bloc H / RDC")
        self.assertEqual(self.area_rdc.building_id, self.bloc)

    def test_le_batiment_entier_peut_etre_une_zone(self):
        area = self.env["his.hygiene.area"].create({"location_id": self.bloc.his_location_id.id})
        self.assertEqual(area.name, "Bloc H")

    def test_une_sous_salle_garde_tout_son_chemin(self):
        salle = self.env["stock.location"].create({"name": "Salle 3", "location_id": self.loc_rdc.id})
        area = self.env["his.hygiene.area"].create({"location_id": salle.id})
        self.assertEqual(area.name, "Bloc H / RDC / Salle 3")

    def test_un_salarie_n_est_membre_qu_une_fois(self):
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self.env["his.hygiene.member"].create({"employee_id": self.fatima.id})

    def test_initiales(self):
        self.assertEqual(self.m_fatima.initials, "FZ")
        self.assertEqual(self.m_karima.initials, "KS")

    def test_chaque_membre_a_sa_couleur(self):
        self.assertNotEqual(self.m_fatima.color, self.m_karima.color)


@tagged("post_install", "-at_install")
class TestConfigDroits(HygieneCase):
    """L'equipe vient des RH, les zones de l'Inventaire (2026-11-10)."""

    def _user(self, login, *groups):
        return (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create({"name": login, "login": login, "group_ids": [(6, 0, [self.env.ref(g).id for g in groups])]})
        )

    def test_la_responsable_n_ajoute_ni_salariee_ni_zone(self):
        other = self.env["hr.employee"].create({"name": "Nadia"})
        with self.assertRaises(AccessError):
            self.env["his.hygiene.member"].with_user(self.manager_user).create({"employee_id": other.id})
        with self.assertRaises(AccessError):
            self.env["his.hygiene.area"].with_user(self.manager_user).create({"location_id": self.loc_rdc.id})
        with self.assertRaises(AccessError):
            self.area_rdc.with_user(self.manager_user).unlink()

    def test_la_responsable_colore_son_equipe(self):
        self.m_fatima.with_user(self.manager_user).color = 7
        self.assertEqual(self.m_fatima.color, 7)

    def test_personne_ne_change_la_salariee_d_une_fiche(self):
        other = self.env["hr.employee"].create({"name": "Nadia"})
        with self.assertRaises(UserError):
            self.m_fatima.employee_id = other

    def test_les_rh_ajoutent_une_salariee(self):
        hr_user = self._user("rh.hyg@his.test", "hr.group_hr_user")
        other = self.env["hr.employee"].create({"name": "Nadia"})
        member = self.env["his.hygiene.member"].with_user(hr_user).create({"employee_id": other.id})
        self.assertEqual(member.employee_id, other)

    def test_l_inventaire_ajoute_une_zone(self):
        stock_user = self._user("stock.hyg@his.test", "stock.group_stock_user")
        salle = self.env["stock.location"].create({"name": "Salle 9", "location_id": self.loc_rdc.id})
        area = self.env["his.hygiene.area"].with_user(stock_user).create({"location_id": salle.id})
        self.assertEqual(area.name, "Bloc H / RDC / Salle 9")
