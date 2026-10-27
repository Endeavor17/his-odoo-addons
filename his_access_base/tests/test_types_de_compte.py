# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Les comptes qui ne sont pas des personnes : comptoir d'une caisse, service (n8n).

Ils portent leurs roles directement, sans poste ni fiche employe. La revue
d'acces doit les traiter comme attendus, pas comme des derogations — et montrer
en revanche le compte d'employe sans fiche, ou desynchronise de son poste.
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTypesDeCompte(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.interne = cls.env.ref("base.group_user")
        cls.du_role = cls.env["res.groups"].create({"name": "ZZ groupe comptoir"})
        cls.role_comptoir = cls.env["his.role"].create(
            {"name": "Cafeteria Counter", "kind": "counter", "group_ids": [(6, 0, cls.du_role.ids)]}
        )

    def _compte(self, login, **vals):
        return self.env["res.users"].create(
            dict({"name": login, "login": login, "group_ids": [(6, 0, self.interne.ids)]}, **vals)
        )

    def _comptoir(self, login="zz_comptoir"):
        return self._compte(login, his_account_type="counter", his_role_ids=[(6, 0, self.role_comptoir.ids)])

    def test_counter_account_gets_its_role_groups(self):
        self.assertIn(self.du_role, self._comptoir().group_ids)

    def test_counter_account_loses_a_group_removed_from_its_role(self):
        comptoir = self._comptoir()
        self.role_comptoir.group_ids = [(5, 0, 0)]
        self.assertNotIn(self.du_role, comptoir.group_ids)

    def test_counter_and_service_accounts_are_not_drift(self):
        comptoir = self._comptoir()
        service = self._compte("zz_n8n", his_account_type="service")

        (comptoir | service)._his_controler_acces()

        self.assertFalse(comptoir.his_access_issue)
        self.assertFalse(service.his_access_issue)

    def test_employee_account_without_employee_is_flagged(self):
        seul = self._compte("zz_sans_fiche")
        seul._his_controler_acces()
        self.assertEqual(seul.his_access_issue, "no_employee")

    def test_counter_account_refuses_employee_role(self):
        role_employe = self.env["his.role"].create({"name": "Magasinier"})
        with self.assertRaises(ValidationError):
            self._compte("zz_mauvais", his_account_type="counter", his_role_ids=[(6, 0, role_employe.ids)])

    def test_employee_account_carries_no_direct_role(self):
        with self.assertRaises(ValidationError):
            self._compte("zz_direct", his_role_ids=[(6, 0, self.role_comptoir.ids)])

    def test_review_shows_issue(self):
        role = self.env["his.role"].create({"name": "Desync", "group_ids": [(6, 0, self.du_role.ids)]})
        poste = self.env["hr.job"].create({"name": "Poste desync", "role_ids": [(6, 0, role.ids)]})
        compte = self._compte("zz_desync")
        self.env["hr.employee"].create({"name": "Desync", "user_id": compte.id, "job_id": poste.id})
        # On desynchronise en ne passant pas par la reconciliation.
        compte.sudo().write({"role_ids_du_poste": [(5, 0, 0)]})

        signales = self.env["res.users"]._cron_controler_acces()

        self.assertIn("zz_desync", signales)
        self.assertEqual(compte.his_access_issue, "post_drift")
        self.assertFalse(compte.role_ids_du_poste, "le controle signale l'ecart, il ne le corrige pas")
