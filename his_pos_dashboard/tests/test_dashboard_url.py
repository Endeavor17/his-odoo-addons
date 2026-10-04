import base64
import hashlib
import hmac
import json
import time

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

SITE = "https://metabase.example.test"
KEY = "test-only-signing-key"
PREFIX = SITE + "/embed/dashboard/"


def _decode(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


@tagged("post_install", "-at_install")
class TestDashboardUrl(TransactionCase):
    """The till gets a short-lived signed URL, never the key that signs it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.till_user = cls.env["res.users"].create(
            {
                "name": "Dashboard Till",
                "login": "his_dashboard_till",
                "group_ids": [(6, 0, [cls.env.ref("point_of_sale.group_pos_user").id])],
            }
        )

    def setUp(self):
        super().setUp()
        # Whatever the database holds, each test starts unconfigured.
        self._configure(False, False, False)

    def _configure(self, site_url, key, dashboard_id):
        set_param = self.env["ir.config_parameter"].sudo().set_param
        set_param("his_metabase.site_url", site_url)
        set_param("his_metabase.secret_key", key)
        set_param("his_pos_dashboard.metabase_dashboard_id", dashboard_id)
        self.env.invalidate_all()

    def test_menu_item_waits_for_all_three_parameters(self):
        config = self.env["pos.config"].create({"name": "Dashboard Till"})
        self._configure(SITE, KEY, False)
        self.assertFalse(config.his_dashboard_available, "Without a dashboard id the menu must stay stock.")
        self._configure(SITE, KEY, "5")
        fields = self.env["pos.config"]._load_pos_data_fields(config)
        loaded = config.read(fields, load=False)[0]
        self.assertTrue(
            loaded.get("his_dashboard_available"), "The flag must reach the browser with the till's config."
        )

    def test_url_carries_a_valid_short_lived_token(self):
        self._configure(SITE + "/", KEY, "5")
        url = self.env["pos.config"].with_user(self.till_user).his_dashboard_url()
        self.assertTrue(url.startswith(PREFIX), url)
        self.assertTrue(url.endswith("#bordered=true&titled=true"), url)
        header, payload, signature = url[len(PREFIX) :].split("#")[0].split(".")
        expected = hmac.new(KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        self.assertTrue(hmac.compare_digest(_decode(signature), expected), "Metabase would reject this signature.")
        self.assertEqual(json.loads(_decode(header))["alg"], "HS256")
        claims = json.loads(_decode(payload))
        self.assertEqual(claims["resource"], {"dashboard": 5})
        self.assertEqual(claims["params"], {})
        self.assertAlmostEqual(claims["exp"], time.time() + 600, delta=30)
        self.assertNotIn(KEY, url, "The key must never travel to the browser.")

    def test_only_a_configured_till_gets_a_url(self):
        with self.assertRaises(UserError):
            self.env["pos.config"].with_user(self.till_user).his_dashboard_url()
        self._configure(SITE, KEY, "5")
        outsider = self.env["res.users"].create(
            {
                "name": "Not a Till",
                "login": "his_dashboard_outsider",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            self.env["pos.config"].with_user(outsider).his_dashboard_url()
