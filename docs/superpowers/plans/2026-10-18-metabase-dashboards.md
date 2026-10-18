# Metabase dashboards embedded in Odoo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each workflow manager opens their own Metabase dashboard inside their Odoo app (maintenance, helpdesk, POS, purchasing, inventory), on staging, with demo data, for the demo of Wednesday 2026-10-21.

**Architecture:** A new `his_metabase` module holds one `his.metabase.dashboard` record per dashboard (code, Metabase number, allowed groups), one generic client action that shows a server-signed static-embedding URL in an iframe, and a menu in each of the five apps. It replaces the maintenance screen written by a technician. The demo data and the five dashboards are built on the staging VPS by the Claude there, from a brief handed over in Task 1.

**Tech Stack:** Odoo 19 (Python, OWL), Metabase free edition (static embedding, HS256 JWT), PostgreSQL, Docker for local tests.

**Spec:** `docs/superpowers/specs/2026-10-18-metabase-dashboards-design.md`

## Global Constraints

- Settings reused as they are: system parameters `his_metabase.site_url` and `his_metabase.secret_key`; never committed (public repository).
- Token: HS256, claims `{"resource": {"dashboard": <int>}, "params": {}, "exp": now + 600}`; URL `<site>/embed/dashboard/<token>#bordered=false&titled=true`.
- Dashboard codes: `maintenance`, `helpdesk`, `pos`, `purchase`, `inventory`.
- Groups: `maintenance_university.group_maintenance_manager`, `helpdesk_mgmt.group_helpdesk_manager`, `point_of_sale.group_pos_manager`, `purchase.group_purchase_manager`, `stock.group_stock_manager`.
- Interface source in English, complete `i18n/fr.po` (CI test `his_access_base` `test_chaque_terme_a_sa_traduction_francaise`).
- Commits authored "Endeavor", no Co-Authored-By trailer.
- Lint before every push: `ruff check .`, `ruff format --check .`, `pylint --rcfile=.pylintrc <MODULES>`, `python tools/verifier_polices.py`, `npx eslint .` (Python at `C:\Users\Mohamed\AppData\Local\Programs\Python\Python312\python.exe`).

## Review Focus

- A user who is in the allowed group only through an implied group (e.g. the executive director, who implies purchase manager) must get the dashboard → test in Task 2.
- A dashboard record with no Metabase number yet, or missing site/key, must show a message in the page, not an error dialog → test in Task 2.
- An unknown or archived code (stale menu after an admin archives a dashboard) must give a clear message, not a traceback → test in Task 2.
- The secret key must never appear in what the browser receives → test in Task 2.
- After removal, the maintenance app must still load (no dangling menu/action/asset referring to the deleted screen) → test in Task 4.

---

### Task 1: Hand the staging Claude its brief (critical path: demo data must start tonight)

**Files:** none in the repo. The deliverable is the message below, given to Mohamed to paste into the Claude on the staging VPS (169.58.77.161). Nothing here depends on Tasks 2–5; Task 5 sets the five numbers it reports back.

- [ ] **Step 1: Give Mohamed this message verbatim**

```
Staging (miniodoo, database his_dev) — product demo to the workflow managers on
Wednesday 2026-10-21. Two jobs for you: demo data, then five Metabase dashboards.
Spec (read it first): his-odoo-addons main, docs/superpowers/specs/2026-10-18-metabase-dashboards-design.md
(on branch feature/metabase-dashboards until merged).

RULES
- Staging only. Never touch prod (197.140.11.218).
- Back up first: pg_dump of his_dev into /root/backups/demo-2026-10-18-<time>/.
- Fictional data only, consistent with the existing recette world in his_dev
  (company "HIS — Higher Institute (FICTIF)", students FIC-0001.., fictional suppliers).
- Create records through the Odoo ORM (odoo shell) so business rules hold; then
  back-date ONLY date columns with SQL (create_date, request_date, date_order,
  date_end, close dates...). Keep the scripts in /root/work/demo/ so they can be
  re-run; tag every created record so it can be found again (e.g. a "DEMO" prefix
  in a name/reference field where one exists).
- Report what you created, row counts per model, and any rule that blocked you.

PART 1 — DEMO DATA (about 3 months: 2026-07-20 to 2026-10-20)
Each KPI must have something to show:
- Maintenance (maintenance.request + maintenance_university models): ~120 requests
  over 6+ buildings and the categories; one building with repeated leaks (plumbing);
  10 still open, of which 3 older than 7 days; time logs and workdays for 4-5 workers
  so "booked vs present" differs; inspection findings incl. 2 critical ones with no
  repair request.
- Helpdesk (helpdesk.ticket, one team "Support"): ~150 tickets, every ticket on a
  his.person (students/staff), categories under the department parents; a Wi-Fi
  spike in the last 3 weeks; channels Front Desk / Email / Phone; ~15 open incl.
  some old ones; closed ones with realistic close dates.
- POS: daily sales on the cafeteria and restaurant tills for every working day
  (Sunday-Thursday), lunchtime peak 11:30-13:30, a smaller morning coffee peak;
  meals paid with credits and with cash; 20-30 products sold. Use real POS sessions
  (open, create paid orders, close) so accounting stays consistent; one session per
  till per day is fine.
- Purchasing (his.purchase.request + purchase.order): ~40 requests across 4-5
  departments in every state; 3 late ones (his_is_late); 2 approved requests with a
  free-text line waiting for a catalogue item (his_needs_product); confirmed orders
  with 2-3 quotes on some; 5+ suppliers with spend differences.
- Inventory: receipts from those orders; counter restocking moves; one counter item
  below its minimum (reordering rule); one slow mover (stock, no move for 60+ days).

PART 2 — FIVE METABASE DASHBOARDS (minimetabase.his.edu.dz, connection to his_dev)
- Admin settings: static embedding ON; its secret key must equal the Odoo system
  parameter his_metabase.secret_key in his_dev (check; if they differ, tell Mohamed,
  do not rotate on your own).
- One dashboard per area, names: "Maintenance", "Helpdesk", "Point of Sale",
  "Purchasing", "Inventory", in a collection "HIS — Dashboards".
- Questions in NATIVE SQL only (portable to prod later). Period filter on every
  dashboard (date range, default this month), wired to every question's date
  column. Hours in Africa/Algiers (Odoo stores UTC).
- KPIs (approved by Mohamed):
  Maintenance: open requests by age (<2 days, 2-7, >7); average time to fix
    (request_date to date_end) by maintenance_category_id; requests per building;
    worker hours booked (request time logs) vs present (workdays); critical
    findings with no repair request.
  Helpdesk: open tickets by stage; average time to close by category; tickets per
    category over time; tickets by channel; 10 oldest open tickets with requester
    and registration number.
  Point of Sale: sales per day per till (DA) with trend; meals paid with credits vs
    cash per day; top 10 products; sales by hour of day; average basket per till.
  Purchasing: requests by state; late requests (his_is_late) and who they wait on;
    spend per department (confirmed orders); average days request -> order per
    department; top suppliers by spend and quotes per order.
  Inventory: counter items below minimum (stock.warehouse.orderpoint); stock value
    by category; top items consumed; slow movers (stock, no move in 60 days);
    requests waiting for a catalogue item (his_needs_product).
- Enable embedding on each dashboard, period filter "Editable" (not locked).
- Report the five dashboard NUMBERS (ids). Mohamed will set them in Odoo
  (Settings > Technical > Metabase Dashboards) once his_metabase is installed.

LATER (Mohamed will send it): install his_metabase with
  odoo-upgrade --install his_metabase
after the PR is merged and deployed.
```

- [ ] **Step 2: Note in memory that the brief went out** (update `his-prod-staging-split.md` "where we are").

---

### Task 2: `his_metabase` — model, signed URL, access, admin screen

**Files:**
- Create: `his_metabase/__init__.py`, `his_metabase/__manifest__.py`
- Create: `his_metabase/models/__init__.py`, `his_metabase/models/his_metabase_dashboard.py`
- Create: `his_metabase/security/ir.model.access.csv`
- Create: `his_metabase/views/his_metabase_dashboard_views.xml`
- Create: `his_metabase/tests/__init__.py`, `his_metabase/tests/test_embed.py`

**Interfaces:**
- Produces: model `his.metabase.dashboard` with fields `name`, `code`, `metabase_id`, `group_ids`, `active`; method `his_embed(code) -> dict` returning `{"url": str}` or `{"error": str}`, raising `AccessError` when the user is in none of `group_ids`.

- [ ] **Step 1: Write the failing tests** — `his_metabase/tests/test_embed.py`

```python
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
```

`his_metabase/tests/__init__.py`:

```python
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import test_embed
```

- [ ] **Step 2: Module skeleton so the tests can load, run them, see them fail**

`his_metabase/__init__.py`:

```python
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import models
```

`his_metabase/models/__init__.py`:

```python
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import his_metabase_dashboard
```

`his_metabase/__manifest__.py`:

```python
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "HIS - Metabase Dashboards",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "summary": "Each workflow manager opens their Metabase dashboard inside their Odoo app",
    "description": """
One record per dashboard (code, Metabase number, allowed groups), one page that
shows a server-signed static-embedding URL, one menu per app. The Metabase site
and key are the system parameters his_metabase.site_url and
his_metabase.secret_key, set per server and never committed.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": [
        "maintenance_university",
        "helpdesk_mgmt",
        "point_of_sale",
        "his_purchase",
        "stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/his_metabase_dashboard_views.xml",
    ],
    "installable": True,
}
```

`his_metabase/models/his_metabase_dashboard.py` (empty model first):

```python
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HisMetabaseDashboard(models.Model):
    _name = "his.metabase.dashboard"
    _description = "Metabase Dashboard"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    metabase_id = fields.Integer(string="Metabase Dashboard Number")
    group_ids = fields.Many2many("res.groups", string="Allowed Groups")
    active = fields.Boolean(default=True)
```

`his_metabase/security/ir.model.access.csv`:

```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_dashboard_system,his.metabase.dashboard system,model_his_metabase_dashboard,base.group_system,1,1,1,1
```

`his_metabase/views/his_metabase_dashboard_views.xml` (admin list, Settings ▸ Technical):

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="his_metabase_dashboard_view_list" model="ir.ui.view">
        <field name="name">his.metabase.dashboard.list</field>
        <field name="model">his.metabase.dashboard</field>
        <field name="arch" type="xml">
            <list editable="bottom">
                <field name="name"/>
                <field name="code"/>
                <field name="metabase_id"/>
                <field name="group_ids" widget="many2many_tags"/>
                <field name="active" column_invisible="1"/>
            </list>
        </field>
    </record>

    <record id="his_metabase_dashboard_action" model="ir.actions.act_window">
        <field name="name">Metabase Dashboards</field>
        <field name="res_model">his.metabase.dashboard</field>
        <field name="view_mode">list</field>
    </record>

    <menuitem id="his_metabase_dashboard_menu"
              name="Metabase Dashboards"
              parent="base.menu_custom"
              action="his_metabase_dashboard_action"
              sequence="100"
              groups="base.group_system"/>
</odoo>
```

Run (fresh local DB, see "Local test command" below):
`-d mb_test -i his_metabase --test-enable --test-tags /his_metabase`
Expected: FAIL — `AttributeError: 'his.metabase.dashboard' object has no attribute 'his_embed'`.

**Local test command** (Docker, from the worktree; DB container `his-odoo-addons-db-1` must be running):

```bash
MSYS_NO_PATHCONV=1 docker run --rm --network his-odoo-addons_default \
  -v C:/Users/Mohamed/his-metabase-wt:/mnt/extra-addons \
  -v C:/Users/Mohamed/his-odoo-addons/config/odoo.conf:/etc/odoo/odoo.conf:ro \
  odoo:19.0 odoo --stop-after-init --no-http <ARGS> 2>&1 | grep -E "FAIL:|ERROR:|tests when" -A8
```

First install of a new DB needs the prerequisites: `-d mb_test -i l10n_dz,point_of_sale` once.

- [ ] **Step 3: Implement `his_embed`** — replace the model file with:

```python
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import hashlib
import hmac
import json
import time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

# Le site et la cle de l'instance Metabase : poses par un administrateur sur
# chaque serveur, jamais dans le depot (il est public).
SITE_PARAM = "his_metabase.site_url"
KEY_PARAM = "his_metabase.secret_key"
# Comme l'exemple de Metabase : la page signe a chaque ouverture.
TOKEN_SECONDS = 600


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


def _b64_json(data):
    return _b64(json.dumps(data, separators=(",", ":")).encode())


class HisMetabaseDashboard(models.Model):
    """Un tableau de bord Metabase, ouvert depuis le menu de son application.

    Le numero Metabase differe d'un serveur a l'autre : il est saisi par un
    administrateur, jamais livre dans les donnees.
    """

    _name = "his.metabase.dashboard"
    _description = "Metabase Dashboard"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, help="Stable key used by the app menus.")
    metabase_id = fields.Integer(
        string="Metabase Dashboard Number", help="The dashboard's number on this server's Metabase."
    )
    group_ids = fields.Many2many("res.groups", string="Allowed Groups")
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("UNIQUE(code)", "Each dashboard code must be unique.")

    @api.model
    def his_embed(self, code):
        """URL signee pour la page, ou le message a afficher a sa place.

        Les droits sont verifies ici : la methode est joignable par RPC quel
        que soit le menu. La cle reste sur le serveur ; le navigateur ne recoit
        qu'un jeton de 10 minutes.
        """
        dashboard = self.sudo().search([("code", "=", code)], limit=1)
        if not dashboard:
            return {"error": _("This dashboard does not exist or has been archived.")}
        if not dashboard.group_ids & self.env.user.all_group_ids:
            raise AccessError(_("You are not allowed to open the %s dashboard.", dashboard.name))
        get_param = self.env["ir.config_parameter"].sudo().get_param
        site_url, key = get_param(SITE_PARAM), get_param(KEY_PARAM)
        if not (site_url and key):
            return {
                "error": _(
                    "Metabase is not configured: set the %(site)s and %(key)s system parameters.",
                    site=SITE_PARAM,
                    key=KEY_PARAM,
                )
            }
        if not dashboard.metabase_id:
            return {
                "error": _(
                    "The %s dashboard has no Metabase number yet: set it in Settings > Technical > "
                    "Metabase Dashboards.",
                    dashboard.name,
                )
            }
        signing_input = (
            _b64_json({"alg": "HS256", "typ": "JWT"})
            + b"."
            + _b64_json(
                {
                    "resource": {"dashboard": dashboard.metabase_id},
                    "params": {},
                    "exp": int(time.time()) + TOKEN_SECONDS,
                }
            )
        )
        signature = _b64(hmac.new(key.encode(), signing_input, hashlib.sha256).digest())
        token = (signing_input + b"." + signature).decode()
        return {"url": f"{site_url.rstrip('/')}/embed/dashboard/{token}#bordered=false&titled=true"}
```

- [ ] **Step 4: Run the tests, expect PASS**

`-d mb_test -u his_metabase --test-enable --test-tags /his_metabase` → `0 failed, 0 error(s) of 7 tests`.

- [ ] **Step 5: Commit**

```bash
git add his_metabase
git commit -m "his_metabase : tableau de bord Metabase signe par le serveur, ouvert a son groupe"
```

---

### Task 3: The page, the five dashboards and their menus

**Files:**
- Create: `his_metabase/static/src/dashboard.js`, `his_metabase/static/src/dashboard.xml`
- Create: `his_metabase/data/his_metabase_dashboard_data.xml`
- Create: `his_metabase/views/menus.xml`
- Modify: `his_metabase/__manifest__.py` (data + assets)
- Test: `his_metabase/tests/test_menus.py`, `his_metabase/tests/__init__.py`

**Interfaces:**
- Consumes: `his.metabase.dashboard.his_embed(code)` from Task 2.
- Produces: client action tag `his_metabase_dashboard` reading `action.params.code`; records `his_metabase.dashboard_<code>` and menus `his_metabase.menu_dashboard_<code>` for the five codes.

- [ ] **Step 1: Failing test** — `his_metabase/tests/test_menus.py`

```python
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Chaque tableau de bord a son menu, dans son application, pour son groupe."""

from odoo.tests import TransactionCase, tagged

ATTENDU = {
    "maintenance": ("maintenance_university.menu_maintenance_root", "maintenance_university.group_maintenance_manager"),
    "helpdesk": ("helpdesk_mgmt.helpdesk_ticket_main_menu", "helpdesk_mgmt.group_helpdesk_manager"),
    "pos": ("point_of_sale.menu_point_root", "point_of_sale.group_pos_manager"),
    "purchase": ("purchase.menu_purchase_root", "purchase.group_purchase_manager"),
    "inventory": ("stock.menu_stock_root", "stock.group_stock_manager"),
}


@tagged("post_install", "-at_install")
class TestMenus(TransactionCase):
    def test_un_menu_par_tableau_de_bord(self):
        for code, (racine, groupe) in ATTENDU.items():
            with self.subTest(code=code):
                dashboard = self.env.ref(f"his_metabase.dashboard_{code}")
                menu = self.env.ref(f"his_metabase.menu_dashboard_{code}")
                self.assertEqual(dashboard.code, code)
                self.assertFalse(dashboard.metabase_id, "Le numero se saisit par serveur, jamais livre.")
                self.assertEqual(dashboard.group_ids, self.env.ref(groupe))
                self.assertEqual(menu.parent_id, self.env.ref(racine))
                self.assertEqual(menu.group_ids, self.env.ref(groupe))
                self.assertEqual(menu.action.tag, "his_metabase_dashboard")
                self.assertEqual(menu.action.params, {"code": code})
```

Add `test_menus` to `his_metabase/tests/__init__.py`:

```python
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import test_embed, test_menus
```

Run `-u his_metabase --test-tags /his_metabase` → FAIL: `ValueError: External ID not found in the system: his_metabase.dashboard_maintenance`.

- [ ] **Step 2: Data** — `his_metabase/data/his_metabase_dashboard_data.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Sans numero Metabase : il differe d'un serveur a l'autre et se saisit
         dans Reglages > Technique > Tableaux de bord Metabase. -->
    <data noupdate="1">
        <record id="dashboard_maintenance" model="his.metabase.dashboard">
            <field name="name">Maintenance</field>
            <field name="code">maintenance</field>
            <field name="group_ids" eval="[Command.set([ref('maintenance_university.group_maintenance_manager')])]"/>
        </record>
        <record id="dashboard_helpdesk" model="his.metabase.dashboard">
            <field name="name">Helpdesk</field>
            <field name="code">helpdesk</field>
            <field name="group_ids" eval="[Command.set([ref('helpdesk_mgmt.group_helpdesk_manager')])]"/>
        </record>
        <record id="dashboard_pos" model="his.metabase.dashboard">
            <field name="name">Point of Sale</field>
            <field name="code">pos</field>
            <field name="group_ids" eval="[Command.set([ref('point_of_sale.group_pos_manager')])]"/>
        </record>
        <record id="dashboard_purchase" model="his.metabase.dashboard">
            <field name="name">Purchasing</field>
            <field name="code">purchase</field>
            <field name="group_ids" eval="[Command.set([ref('purchase.group_purchase_manager')])]"/>
        </record>
        <record id="dashboard_inventory" model="his.metabase.dashboard">
            <field name="name">Inventory</field>
            <field name="code">inventory</field>
            <field name="group_ids" eval="[Command.set([ref('stock.group_stock_manager')])]"/>
        </record>
    </data>
</odoo>
```

- [ ] **Step 3: Menus** — `his_metabase/views/menus.xml` (one client action per code; the page asks the server again, the menu groups only hide)

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="action_dashboard_maintenance" model="ir.actions.client">
        <field name="name">Dashboard</field>
        <field name="tag">his_metabase_dashboard</field>
        <field name="params" eval="{'code': 'maintenance'}"/>
    </record>
    <record id="action_dashboard_helpdesk" model="ir.actions.client">
        <field name="name">Dashboard</field>
        <field name="tag">his_metabase_dashboard</field>
        <field name="params" eval="{'code': 'helpdesk'}"/>
    </record>
    <record id="action_dashboard_pos" model="ir.actions.client">
        <field name="name">Dashboard</field>
        <field name="tag">his_metabase_dashboard</field>
        <field name="params" eval="{'code': 'pos'}"/>
    </record>
    <record id="action_dashboard_purchase" model="ir.actions.client">
        <field name="name">Dashboard</field>
        <field name="tag">his_metabase_dashboard</field>
        <field name="params" eval="{'code': 'purchase'}"/>
    </record>
    <record id="action_dashboard_inventory" model="ir.actions.client">
        <field name="name">Dashboard</field>
        <field name="tag">his_metabase_dashboard</field>
        <field name="params" eval="{'code': 'inventory'}"/>
    </record>

    <menuitem id="menu_dashboard_maintenance" name="Dashboard" parent="maintenance_university.menu_maintenance_root"
              action="action_dashboard_maintenance" sequence="8"
              groups="maintenance_university.group_maintenance_manager"/>
    <menuitem id="menu_dashboard_helpdesk" name="Dashboard" parent="helpdesk_mgmt.helpdesk_ticket_main_menu"
              action="action_dashboard_helpdesk" sequence="1"
              groups="helpdesk_mgmt.group_helpdesk_manager"/>
    <menuitem id="menu_dashboard_pos" name="Dashboard" parent="point_of_sale.menu_point_root"
              action="action_dashboard_pos" sequence="1"
              groups="point_of_sale.group_pos_manager"/>
    <menuitem id="menu_dashboard_purchase" name="Dashboard" parent="purchase.menu_purchase_root"
              action="action_dashboard_purchase" sequence="1"
              groups="purchase.group_purchase_manager"/>
    <menuitem id="menu_dashboard_inventory" name="Dashboard" parent="stock.menu_stock_root"
              action="action_dashboard_inventory" sequence="1"
              groups="stock.group_stock_manager"/>
</odoo>
```

- [ ] **Step 4: The page** — `his_metabase/static/src/dashboard.js`

```javascript
import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Le tableau de bord Metabase d'une application, en pleine page. Le serveur
// signe l'URL a chaque ouverture (his_embed) : la cle ne vient jamais ici. Un
// reglage manquant revient en message, affiche a la place du tableau.
export class HisMetabaseDashboard extends Component {
    static template = "his_metabase.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        onWillStart(async () => {
            const code = this.props.action.params?.code;
            const result = await this.orm.call("his.metabase.dashboard", "his_embed", [code]);
            this.url = result.url;
            this.error = result.error;
        });
    }
}

registry.category("actions").add("his_metabase_dashboard", HisMetabaseDashboard);
```

`his_metabase/static/src/dashboard.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<templates xml:space="preserve">
    <t t-name="his_metabase.Dashboard">
        <div class="o_content h-100 d-flex align-items-center justify-content-center">
            <iframe t-if="url" t-att-src="url" class="w-100 h-100 border-0" title="Dashboard"/>
            <p t-else="" class="m-0 p-4 fs-4 text-muted text-center" t-esc="error"/>
        </div>
    </t>
</templates>
```

- [ ] **Step 5: Manifest** — `data` and `assets` become:

```python
    "data": [
        "security/ir.model.access.csv",
        "data/his_metabase_dashboard_data.xml",
        "views/his_metabase_dashboard_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "his_metabase/static/src/**/*",
        ],
    },
```

- [ ] **Step 6: Run tests, expect PASS** — `-u his_metabase --test-tags /his_metabase` → `0 failed, 0 error(s) of 8 tests`.

- [ ] **Step 7: Commit**

```bash
git add his_metabase
git commit -m "his_metabase : la page et les cinq tableaux de bord, un menu par application"
```

---

### Task 4: Retire the technician's maintenance screen

**Files:**
- Delete: `maintenance_university/static/src/metabase/metabase_dashboard.js`, `maintenance_university/static/src/metabase/metabase_dashboard.xml`, `maintenance_university/tests/test_metabase_dashboard.py`
- Modify: `maintenance_university/models/maintenance_university_dashboard.py` (remove `METABASE_PARAMS`, `_b64`, `_b64_json`, `get_metabase_url`, and the imports `base64 hashlib hmac json time` if unused afterwards; `UserError` too if unused)
- Modify: `maintenance_university/views/maintenance_university_dashboard_actions.xml` (remove `action_maintenance_university_metabase`)
- Modify: `maintenance_university/views/menus.xml` (remove `menu_maintenance_metabase` and its comment)
- Modify: `maintenance_university/__manifest__.py` (remove the `"maintenance_university/static/src/metabase/**/*"` asset line; version `19.0.4.0.2` → `19.0.4.0.3`)
- Modify: `maintenance_university/tests/__init__.py` (remove `test_metabase_dashboard`)
- Test: `his_metabase/tests/test_menus.py` (one test added)

- [ ] **Step 1: Failing test** — append to `TestMenus` in `his_metabase/tests/test_menus.py`:

```python
    def test_l_ancien_ecran_maintenance_a_disparu(self):
        # Un seul chemin vers le tableau de bord maintenance : le notre.
        self.assertFalse(self.env.ref("maintenance_university.menu_maintenance_metabase", raise_if_not_found=False))
        self.assertFalse(
            self.env.ref("maintenance_university.action_maintenance_university_metabase", raise_if_not_found=False)
        )
        self.assertFalse(hasattr(self.env["maintenance.university.dashboard"], "get_metabase_url"))
```

Run `-u his_metabase --test-tags /his_metabase` → FAIL on this test.

- [ ] **Step 2: Remove the files and code listed above.** In `maintenance_university_dashboard.py`, keep `get_recap_data` and `_group_count` untouched; the remaining imports are:

```python
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import format_date
```

- [ ] **Step 3: Run both modules' tests** — `-u maintenance_university,his_metabase --test-enable --test-tags /maintenance_university,/his_metabase` → `0 failed`. The Odoo update deletes the removed menu and action (their XML ids are no longer in the data).

- [ ] **Step 4: Commit**

```bash
git add -A maintenance_university his_metabase
git commit -m "maintenance_university : l'ecran Metabase du technicien laisse la place a his_metabase"
```

---

### Task 5: French, CI, full replay, browser check, push

**Files:**
- Create: `his_metabase/i18n/fr.po`
- Modify: `.github/workflows/ci.yml` (`MODULES`: add `his_metabase`)
- Modify: `maintenance_university/i18n/fr.po` (drop entries the export no longer lists; optional)

- [ ] **Step 1: Export the terms and translate** — on the local DB with French loaded:

```bash
MSYS_NO_PATHCONV=1 docker run --rm --network his-odoo-addons_default \
  -v C:/Users/Mohamed/his-metabase-wt:/mnt/extra-addons \
  -v C:/Users/Mohamed/his-odoo-addons/config/odoo.conf:/etc/odoo/odoo.conf:ro \
  odoo:19.0 odoo i18n export -c /etc/odoo/odoo.conf -d mb_test -l fr_FR -o /mnt/extra-addons/his_metabase/i18n/fr.po his_metabase
```

(Load French first with `--load-language=fr_FR` on that DB.) Fill every `msgstr`; the main ones:
"Metabase Dashboard" → "Tableau de bord Metabase"; "Metabase Dashboards" → "Tableaux de bord Metabase"; "Dashboard" → "Tableau de bord"; "Metabase Dashboard Number" → "Numéro du tableau de bord Metabase"; "Allowed Groups" → "Groupes autorisés"; "Point of Sale" → "Point de vente"; "Purchasing" → "Achats"; "Inventory" → "Inventaire"; "Helpdesk" → "Assistance"; "Maintenance" → "Maintenance"; the four messages of `his_embed` and the two help texts translated faithfully, keeping `%s`, `%(site)s`, `%(key)s`.

- [ ] **Step 2: CI module list** — in `.github/workflows/ci.yml`, append `,his_metabase` to the `MODULES:` line.

- [ ] **Step 3: Lint** (Global Constraints commands). Expected: all pass.

- [ ] **Step 4: Full CI replay locally** (the job that failed on the helpdesk branch for a missing translation):

pinned image `odoo:19.0@sha256:dd9013e669caaa23d26765dc55814655eaeecca7cfc2c265dbabae913bce22fd`, `--user root`, fresh DB; `-i l10n_dz,point_of_sale,his_person_core,his_academic_base`; then `tools/charger_plan_comptable_dz.py` and `tools/seed_categories.py` through `odoo shell`; then `-i "$MODULES,$VENDORED" --test-enable --test-tags <each module prefixed with />`. Expected: `0 failed, 0 error(s)` of ≥ 790 tests.

- [ ] **Step 5: Browser check** (local preview on port 8099, French admin, a test Metabase site and key set as system parameters): each of the five menus opens its page; with no Metabase number the page shows the message; a stock-manager-only test user sees only the Inventory dashboard menu, and calling `his_embed('purchase')` as that user from the browser console is refused.

- [ ] **Step 6: Commit and push**

```bash
git add his_metabase/i18n .github/workflows/ci.yml maintenance_university/i18n
git commit -m "his_metabase : traductions francaises et CI"
git push -u origin feature/metabase-dashboards
```

- [ ] **Step 7: Install message for the staging Claude** (to give Mohamed after the PR is merged and deployed):

```
his-odoo-addons main now carries his_metabase (PR "feature/metabase-dashboards").
1. Check the deploy picked up the merge commit; maintenance_university updated by the
   startup auto-upgrade to 19.0.4.0.3 (its old Metabase menu is gone).
2. odoo-upgrade --install his_metabase
3. Settings > Technical > Metabase Dashboards: set the five numbers you reported
   (Maintenance, Helpdesk, Point of Sale, Purchasing, Inventory).
4. Check as admin that each app's "Tableau de bord" menu shows its dashboard, and
   report any message shown instead.
```
