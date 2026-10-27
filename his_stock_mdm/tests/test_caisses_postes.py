# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Les noms proposes a chaque caisse viennent des postes (MDM des roles, 2026-10-27).

Le PC du comptoir reste connecte ; la caissiere tape son nom. Jusqu'ici la
liste etait vide, et vide veut dire « tout le monde » pour pos_hr :
l'Administrateur comme le premier employe venu tenaient la Cafeteria, sans PIN.
"""

from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestCaissesPostes(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = cls.env.ref
        cls.cafeteria = ref("his_stock_mdm.pos_config_cafeteria")
        cls.restaurant = ref("his_stock_mdm.pos_config_restaurant")
        (cls.cafeteria | cls.restaurant).write({"module_pos_hr": True})
        cls.role = cls.env["his.role"].create(
            {"name": "Cafeteria Cashier", "pos_config_ids": [(6, 0, cls.cafeteria.ids)]}
        )
        cls.poste = cls.env["hr.job"].create({"name": "Caissier Cafeteria", "role_ids": [(6, 0, cls.role.ids)]})
        cls.autre_poste = cls.env["hr.job"].create({"name": "Magasinier"})
        cls.comptoir = new_test_user(cls.env, login="zz_comptoir_cafet", groups="his_stock_mdm.group_caisse_cafeteria")
        cls.chef = new_test_user(cls.env, login="zz_chef_pos", groups="point_of_sale.group_pos_manager")
        cls.chef_employe = cls.env["hr.employee"].create({"name": "Chef POS", "user_id": cls.chef.id, "pin": "9999"})

    def _caissiere(self, nom, pin="1234", poste=None):
        return self.env["hr.employee"].create(
            {"name": nom, "pin": pin, "job_id": (poste or self.poste).id, "company_id": self.cafeteria.company_id.id}
        )

    def _qui_peut_taper(self, config):
        # Comme a la caisse : le compte comptoir, sans droits RH, charge les employes.
        return self.env["hr.employee"].sudo().search(config.with_user(self.comptoir)._employee_domain(self.comptoir.id))

    def test_post_puts_cashier_on_its_till_only(self):
        rym = self._caissiere("Rym")
        self.assertIn(rym, self.cafeteria.advanced_employee_ids)
        self.assertNotIn(rym, self.restaurant.advanced_employee_ids)

    def test_cashier_without_pin_is_left_off_and_reported(self):
        sans_pin = self._caissiere("Sans Pin", pin=False)
        self.assertNotIn(sans_pin, self.cafeteria.advanced_employee_ids)
        self.assertIn("Sans Pin", self.cafeteria.his_till_issue)

    def test_losing_pin_or_post_removes_from_till(self):
        rym = self._caissiere("Rym")
        rym.pin = False
        self.assertNotIn(rym, self.cafeteria.advanced_employee_ids)

        rym.pin = "4321"
        self.assertIn(rym, self.cafeteria.advanced_employee_ids)
        rym.job_id = self.autre_poste
        self.assertNotIn(rym, self.cafeteria.advanced_employee_ids)

    def test_pos_managers_stay_on_every_till(self):
        self._caissiere("Rym")
        self.assertIn(self.chef_employe, self.cafeteria.advanced_employee_ids)

    def test_till_lists_restrict_who_can_tap_in(self):
        rym = self._caissiere("Rym")
        passant = self.env["hr.employee"].create({"name": "Passant", "company_id": self.cafeteria.company_id.id})

        peuvent = self._qui_peut_taper(self.cafeteria)

        self.assertIn(rym, peuvent)
        self.assertNotIn(passant, peuvent)

    def test_till_with_roles_but_no_eligible_cashier_is_closed(self):
        self._caissiere("Sans Pin", pin=False)
        passant = self.env["hr.employee"].create({"name": "Passant", "company_id": self.cafeteria.company_id.id})

        peuvent = self._qui_peut_taper(self.cafeteria)

        self.assertNotIn(passant, peuvent)
        self.assertIn(self.chef_employe, peuvent)
        self.assertIn("No cashier can open this till", self.cafeteria.his_till_issue)

    def test_removing_the_till_from_the_role_removes_its_cashiers(self):
        rym = self._caissiere("Rym")
        self.role.pos_config_ids = [(5, 0, 0)]
        self.assertNotIn(rym, self.cafeteria.advanced_employee_ids)

    def test_manager_without_pin_is_not_offered(self):
        """pos_hr met tout responsable POS sur la liste, PIN ou pas : sans PIN,
        n'importe qui taperait « Administrator » au comptoir."""
        self._caissiere("Rym")
        sans_pin = new_test_user(self.env, login="zz_chef_sans_pin", groups="point_of_sale.group_pos_manager")
        chef_sans_pin = self.env["hr.employee"].create({"name": "Chef sans PIN", "user_id": sans_pin.id})
        self._caissiere("Declencheur")

        self.assertNotIn(chef_sans_pin, self._qui_peut_taper(self.cafeteria))
        self.assertIn("Chef sans PIN", self.cafeteria.his_till_issue)

    def test_archiving_the_last_cashier_role_keeps_the_till_closed(self):
        self._caissiere("Rym")
        passant = self.env["hr.employee"].create({"name": "Passant", "company_id": self.cafeteria.company_id.id})

        self.role.active = False

        self.assertNotIn(passant, self._qui_peut_taper(self.cafeteria))

    def test_losing_pos_manager_removes_from_till(self):
        self._caissiere("Rym")
        self.assertIn(self.chef_employe, self.cafeteria.advanced_employee_ids)

        self.chef.write({"group_ids": [(3, self.env.ref("point_of_sale.group_pos_manager").id)]})

        self.assertNotIn(self.chef_employe, self.cafeteria.advanced_employee_ids)

    def test_a_role_created_with_its_till_and_post_fills_the_till(self):
        poste = self.env["hr.job"].create({"name": "Caissier Restaurant"})
        nour = self._caissiere("Nour", poste=poste)
        self.env["his.role"].create(
            {
                "name": "Restaurant Cashier",
                "pos_config_ids": [(6, 0, self.restaurant.ids)],
                "job_ids": [(6, 0, poste.ids)],
            }
        )
        self.assertIn(nour, self.restaurant.advanced_employee_ids)
