# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Le role metier : ce que l'administrateur choisit a la place des groupes Odoo.

Deux proprietes comptent. Le role montre TOUT ce qu'il donne, groupes
impliques compris, pour que l'administrateur voie « Responsable POS → Inventaire
utilisateur » avant d'enregistrer. Et il ne peut jamais porter un groupe
sensible, ni directement ni par implication.
"""

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.his_access_base.models.hr_job import SENSITIVE_GROUP_XMLIDS


@tagged("post_install", "-at_install")
class TestHisRole(TransactionCase):
    def _user(self, login, xmlids):
        groups = [self.env.ref("base.group_user").id] + [self.env.ref(x).id for x in xmlids]
        return self.env["res.users"].create({"name": login, "login": login, "group_ids": [(6, 0, groups)]})

    def test_role_shows_everything_it_grants(self):
        # Un groupe cree ici, sur une dependance declaree (hr) : le test ne doit
        # pas supposer le Point de vente installe.
        brings_along = self.env["res.groups"].create(
            {"name": "Brings HR along", "implied_ids": [(4, self.env.ref("hr.group_hr_user").id)]}
        )
        role = self.env["his.role"].create({"name": "HR helper", "group_ids": [(6, 0, [brings_along.id])]})
        self.assertIn(self.env.ref("hr.group_hr_user"), role.granted_group_ids)

    def test_role_refuses_sensitive_group(self):
        checked = 0
        for xmlid in SENSITIVE_GROUP_XMLIDS:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if not group:
                continue
            checked += 1
            with self.assertRaises(ValidationError, msg=xmlid):
                self.env["his.role"].create({"name": "Trap %s" % xmlid, "group_ids": [(6, 0, [group.id])]})
        self.assertGreaterEqual(checked, 4)

    def test_role_refuses_group_implying_sensitive(self):
        trap = self.env["res.groups"].create(
            {"name": "Harmless looking", "implied_ids": [(4, self.env.ref("base.group_allow_export").id)]}
        )
        with self.assertRaises(ValidationError):
            self.env["his.role"].create({"name": "Trap", "group_ids": [(6, 0, [trap.id])]})

    def test_only_access_admin_writes_roles(self):
        hr_manager = self._user("zz_role_hr", ["hr.group_hr_manager"])
        with self.assertRaises(AccessError):
            self.env["his.role"].with_user(hr_manager).create({"name": "Nope"})

        access_admin = self._user("zz_role_admin", ["base.group_erp_manager"])
        role = self.env["his.role"].with_user(access_admin).create({"name": "Fine"})
        self.assertEqual(role.kind, "employee")
