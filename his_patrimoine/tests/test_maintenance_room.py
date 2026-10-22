# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""La salle sur les demandes et constats de maintenance.

Une seule liste de lieux : les salles sont les emplacements Patrimoine sous
chaque batiment. La maintenance les reference, elle n'en tient pas une autre.
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMaintenanceRoom(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Building = cls.env["maintenance.building"]
        Location = cls.env["stock.location"]
        cls.bloc_a = Building.create({"name": "Bloc A salles", "code": "XA"})
        cls.bloc_b = Building.create({"name": "Bloc B salles", "code": "XB"})
        cls.salle_a1 = Location.create({"name": "A1", "location_id": cls.bloc_a.his_location_id.id})
        cls.salle_b1 = Location.create({"name": "B1", "location_id": cls.bloc_b.his_location_id.id})
        cls.cat = cls.env["maintenance.category"].create({"name": "Plomberie salles"})

    def _request(self, **vals):
        return self.env["maintenance.request"].create(
            {
                "name": "Fuite",
                "building_id": self.bloc_a.id,
                "maintenance_category_id": self.cat.id,
                **vals,
            }
        )

    def test_la_salle_est_proposee_sous_le_batiment(self):
        req = self._request(his_room_id=self.salle_a1.id)
        self.assertEqual(req.his_room_id, self.salle_a1)
        self.assertEqual(req.his_building_location_id, self.bloc_a.his_location_id)

    def test_changer_de_batiment_vide_la_salle(self):
        req = self._request(his_room_id=self.salle_a1.id)
        req.building_id = self.bloc_b
        self.assertFalse(req.his_room_id)

    def test_une_salle_d_un_autre_batiment_est_refusee(self):
        with self.assertRaises(ValidationError):
            self._request(his_room_id=self.salle_b1.id)

    def test_le_batiment_lui_meme_n_est_pas_une_salle(self):
        with self.assertRaises(ValidationError):
            self._request(his_room_id=self.bloc_a.his_location_id.id)

    def test_la_conversion_garde_la_salle(self):
        finding = self.env["maintenance.university.finding"].create(
            {
                "building_id": self.bloc_a.id,
                "his_room_id": self.salle_a1.id,
                "category_id": self.cat.id,
                "description": "Vitre cassee",
            }
        )
        finding.action_submit()
        finding.action_convert_to_request()
        self.assertEqual(finding.created_request_id.his_room_id, self.salle_a1)
