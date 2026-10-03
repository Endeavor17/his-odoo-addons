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
class TestMetabaseDashboard(TransactionCase):
    """A manager gets a short-lived signed URL, never the key that signs it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        def user(login, group):
            return cls.env["res.users"].create(
                {"name": login, "login": login, "group_ids": [(6, 0, [cls.env.ref(group).id])]}
            )

        cls.manager = user("mu_metabase_manager", "maintenance_university.group_maintenance_manager")
        cls.worker = user("mu_metabase_worker", "maintenance_university.group_maintenance_worker")

    def setUp(self):
        super().setUp()
        # Whatever the database holds, each test starts unconfigured.
        self._configure(False, False, False)

    def _configure(self, site_url, key, dashboard_id):
        set_param = self.env["ir.config_parameter"].sudo().set_param
        set_param("his_metabase.site_url", site_url)
        set_param("his_metabase.secret_key", key)
        set_param("maintenance_university.metabase_dashboard_id", dashboard_id)

    def test_manager_gets_a_valid_short_lived_token(self):
        self._configure(SITE + "/", KEY, "6")
        url = self.env["maintenance.university.dashboard"].with_user(self.manager).get_metabase_url()
        self.assertTrue(url.startswith(PREFIX), url)
        self.assertTrue(url.endswith("#bordered=true&titled=true"), url)
        header, payload, signature = url[len(PREFIX) :].split("#")[0].split(".")
        expected = hmac.new(KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        self.assertTrue(hmac.compare_digest(_decode(signature), expected), "Metabase would reject this signature.")
        claims = json.loads(_decode(payload))
        self.assertEqual(claims["resource"], {"dashboard": 6})
        self.assertEqual(claims["params"], {})
        self.assertAlmostEqual(claims["exp"], time.time() + 600, delta=30)
        self.assertNotIn(KEY, url, "The key must never travel to the browser.")

    def test_only_a_configured_manager_gets_a_url(self):
        Dashboard = self.env["maintenance.university.dashboard"]
        with self.assertRaises(UserError):
            Dashboard.with_user(self.manager).get_metabase_url()
        self._configure(SITE, KEY, "6")
        with self.assertRaises(AccessError):
            Dashboard.with_user(self.worker).get_metabase_url()
