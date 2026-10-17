"""Recette P-26 : une base neuve naissait aux Etats-Unis, sans le francais."""

from odoo.tests import TransactionCase, tagged

from .. import defauts_algeriens


@tagged("post_install", "-at_install")
class TestBaseNeuve(TransactionCase):
    def test_societe_en_algerie_et_francais_charge(self):
        company = self.env.ref("base.main_company")
        company.country_id = self.env.ref("base.us")
        defauts_algeriens(self.env)
        self.assertEqual(company.country_id, self.env.ref("base.dz"))
        self.assertTrue(self.env["res.lang"]._lang_get("fr_FR").active)
