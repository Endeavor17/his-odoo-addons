# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Un tableau de bord Metabase s'ouvre signe par le serveur, pour son groupe seulement."""

import base64
import hashlib
import hmac
import json
import time

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

SITE = "https://metabase.example.test"
KEY = "test-only-signing-key"
PREFIX = SITE + "/embed/dashboard/"


def _decode(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


@tagged("post_install", "-at_install")
class TestEmbed(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dashboard = cls.env["his.metabase.dashboard"]
        cls.achats = cls.Dashboard.create(
            {
                "name": "Test Purchasing",
                "code": "test_purchase",
                "metabase_id": 7,
                "group_ids": [(6, 0, cls.env.ref("purchase.group_purchase_manager").ids)],
            }
        )
        cls.acheteur = new_test_user(cls.env, login="mb_manager", groups="purchase.group_purchase_manager")
        cls.directeur = new_test_user(cls.env, login="mb_director", groups="his_purchase.group_purchase_director")
        cls.magasinier = new_test_user(cls.env, login="mb_stock", groups="stock.group_stock_manager")

    def setUp(self):
        super().setUp()
        self._configure(SITE + "/", KEY)

    def _configure(self, site_url, key):
        set_param = self.env["ir.config_parameter"].sudo().set_param
        set_param("his_metabase.site_url", site_url)
        set_param("his_metabase.secret_key", key)

    def _embed(self, user, code="test_purchase"):
        return self.Dashboard.with_user(user).his_embed(code)

    def test_un_jeton_valide_et_court(self):
        url = self._embed(self.acheteur)["url"]
        self.assertTrue(url.startswith(PREFIX), url)
        self.assertTrue(url.endswith("#bordered=false&titled=true"), url)
        header, payload, signature = url[len(PREFIX) :].split("#")[0].split(".")
        attendu = hmac.new(KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        self.assertTrue(hmac.compare_digest(_decode(signature), attendu))
        claims = json.loads(_decode(payload))
        self.assertEqual(claims["resource"], {"dashboard": 7})
        self.assertEqual(claims["params"], {})
        self.assertAlmostEqual(claims["exp"], time.time() + 600, delta=30)

    def test_la_cle_ne_part_jamais_au_navigateur(self):
        self.assertNotIn(KEY, json.dumps(self._embed(self.acheteur)))

    def test_un_groupe_implique_suffit(self):
        # Le directeur executif implique le responsable achats.
        self.assertIn("url", self._embed(self.directeur))

    def test_hors_groupe_refuse(self):
        with self.assertRaises(AccessError):
            self._embed(self.magasinier)

    def test_non_configure_un_message_pas_une_erreur(self):
        self._configure(False, False)
        self.assertIn("his_metabase.site_url", self._embed(self.acheteur)["error"])

    def test_numero_absent_un_message(self):
        self.achats.metabase_id = 0
        self.assertIn("error", self._embed(self.acheteur))

    def test_code_inconnu_ou_archive_un_message(self):
        self.assertIn("error", self._embed(self.acheteur, code="nope"))
        self.achats.active = False
        self.assertIn("error", self._embed(self.acheteur))
