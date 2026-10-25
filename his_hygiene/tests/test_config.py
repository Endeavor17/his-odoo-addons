"""Equipe et zones : les personnes et les lieux viennent des referentiels."""

from odoo.exceptions import ValidationError
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
