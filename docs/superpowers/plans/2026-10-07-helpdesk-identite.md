# Helpdesk on the Identity Register — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship OCA's helpdesk with every ticket linked to an existing `his.person`, usable by HIS staff in four teams.

**Architecture:** `helpdesk_mgmt` and `helpdesk_mgmt_crm` are vendored unmodified from OCA. One new module, `his_helpdesk_identity_bridge`, holds everything HIS-specific: the ticket ↔ person link, the S-6 re-open rule, teams, channel, French closing mail. `his_person_core` gains name-or-matricule search.

**Tech Stack:** Odoo 19.0 Community (stock `odoo:19.0` image), PostgreSQL 16, Docker Compose, Odoo `TransactionCase` tests.

**Spec:** `docs/superpowers/specs/2026-10-07-helpdesk-identite-design.md`

## Global Constraints

- Vendored source: `OCA/helpdesk` branch `19.0`, commit `5f7f54c167e3fb3b2bf6c19271ab9519643e75f0`, copied unmodified.
- The helpdesk never creates a `his.person`.
- The S-6 rule `his_person_core.rule_partner_student_candidate_private` is never modified; access is re-opened by a rule in the bridge.
- Re-open group: `helpdesk_mgmt.group_helpdesk_user_own`. No new group.
- Data files are `noupdate="1"`.
- Code comments in French, unaccented ASCII in Python; module text in French.
- Commits authored `Endeavor <mohamed.bounouaa@outlook.com>`, **no `Co-Authored-By` trailer** (Mohamed, 2026-09-27).
- Tests on Git Bash: prefix with `MSYS_NO_PATHCONV=1`, use `--without-demo=True`.

## Review Focus

1. Clearing the person on a ticket whose contact is a person's: the contact must clear too, or the link silently desyncs → test in Task 3.
2. A user with no helpdesk role still cannot read a student's contact after install (S-6 must hold) → test in Task 4.
3. A follower without a helpdesk role opening a ticket must not hit an AccessError on the person fields → fields carry `groups=` in the view, checked in Task 4.
4. Closing a ticket must not block the agent on SMTP → test in Task 6.
5. Ticket → lead without `his_crm_identity_bridge` installed must not crash → guarded in Task 5, test skips cleanly when absent.

---

## Test environment (used by every task)

```bash
cd C:/Users/Mohamed/his-odoo-addons
docker compose up -d db
# Base de travail, creee une fois (Task 1 Step 3), mise a jour ensuite par -u :
MSYS_NO_PATHCONV=1 docker compose run --rm odoo odoo -d hd_test --without-demo=True \
  -u <modules> --test-enable --test-tags /<module> --stop-after-init 2>&1 | tail -40
```

Pass criterion: no line matching `ERROR` or `FAIL` from `odoo.tests` and a final `0 failed, 0 error(s)` line.

---

### Task 1: Vendor OCA helpdesk

**Files:**
- Create: `helpdesk_mgmt/` (copy), `helpdesk_mgmt_crm/` (copy), `VENDOR.md` in each
- Modify: `pyproject.toml` (ruff `extend-exclude`), `.pre-commit-config.yaml` (`exclude`), `.github/workflows/ci.yml` (`MODULES`)

**Interfaces:** Produces the models `helpdesk.ticket`, `helpdesk.ticket.team`, `helpdesk.ticket.channel`, `helpdesk.ticket.create.lead` and groups `helpdesk_mgmt.group_helpdesk_user_own` / `group_helpdesk_user` / `group_helpdesk_manager`.

- [ ] **Step 1: Copy the two modules at the pinned commit**

```bash
SRC=<scratchpad>/oca/helpdesk   # git -C $SRC rev-parse HEAD == 5f7f54c...
cp -r $SRC/helpdesk_mgmt $SRC/helpdesk_mgmt_crm .
```

- [ ] **Step 2: Write `VENDOR.md` in each module**

```markdown
# Module tiers vendu (OCA)

- Source : https://github.com/OCA/helpdesk, branche `19.0`
- Commit : `5f7f54c167e3fb3b2bf6c19271ab9519643e75f0` (2026-10-06)
- Licence : AGPL-3
- Modifications locales : **aucune**. Tout le specifique HIS vit dans
  `his_helpdesk_identity_bridge`.

Pourquoi vendu : le deploiement n'a pas d'etape de build (image `odoo:19.0`
stock, depot monte) ; rien ne peut etre installe par pip.

Mettre a jour : recopier le dossier depuis le nouveau commit OCA, changer le
commit ci-dessus, relancer la suite `his_helpdesk_identity_bridge`.
```

- [ ] **Step 3: Exclude from lint, add to CI**

`pyproject.toml`: `extend-exclude = ["web_responsive", "helpdesk_mgmt", "helpdesk_mgmt_crm"]`.
`.pre-commit-config.yaml`: `exclude: '^(web_responsive|helpdesk_mgmt|helpdesk_mgmt_crm)/'`.
`ci.yml` `MODULES`: append `,helpdesk_mgmt,helpdesk_mgmt_crm,his_helpdesk_identity_bridge` (the bridge arrives in Task 3; CI is only run on push, after Task 7).

- [ ] **Step 4: Create the test base and run OCA's own tests**

```bash
MSYS_NO_PATHCONV=1 docker compose run --rm odoo odoo -d hd_test --without-demo=True \
  -i his_person_core,his_crm_identity_bridge,his_access_base,helpdesk_mgmt,helpdesk_mgmt_crm \
  --test-enable --test-tags /helpdesk_mgmt,/helpdesk_mgmt_crm,/his_access_base --stop-after-init
```
Expected: 0 failed. A `his_access_base` failure here means OCA opens something to every user — stop and report.

- [ ] **Step 5: Commit** — `[ADD] helpdesk_mgmt, helpdesk_mgmt_crm : modules OCA vendus tels quels`

---

### Task 2: Find a person by matricule

**Files:**
- Modify: `his_person_core/models/his_person.py` (class attributes), `his_person_core/__manifest__.py` (version bump)
- Test: `his_person_core/tests/test_recherche_matricule.py`, `his_person_core/tests/__init__.py`

**Interfaces:** Produces `his.person.name_search(<matricule fragment>)` returning the person.

- [ ] **Step 1: Failing test**

```python
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRechercheMatricule(TransactionCase):
    def test_une_personne_se_trouve_par_son_matricule(self):
        person = self.env["his.person"].create(
            {"name": "Lina Ouali", "type_personne": "etudiant", "source_system": "manual"}
        )
        self.assertTrue(person.matricule_institutionnel)
        found = self.env["his.person"].name_search(person.matricule_affiche)
        self.assertIn(person.id, [pid for pid, _name in found])

    def test_le_nom_reste_cherchable(self):
        person = self.env["his.person"].create(
            {"name": "Lina Ouali", "type_personne": "etudiant", "source_system": "manual"}
        )
        found = self.env["his.person"].name_search("Ouali")
        self.assertIn(person.id, [pid for pid, _name in found])
```

- [ ] **Step 2: Run** `-u his_person_core --test-tags /his_person_core:TestRechercheMatricule` → FAIL on the first test.

- [ ] **Step 3: Implement** — next to `_order` in `HisPerson`:

```python
    # Un agent tape le matricule affiche (sans cle) : ilike sur la forme
    # longue le contient. Sert a tous les selecteurs de personne du groupe.
    _rec_names_search = ["name", "matricule_institutionnel"]
```

- [ ] **Step 4: Run** → PASS, then the full `/his_person_core` suite → 0 failed.
- [ ] **Step 5: Commit** — `[IMP] his_person_core : une personne se trouve par son matricule`

---

### Task 3: Bridge module — ticket ↔ person link

**Files:**
- Create: `his_helpdesk_identity_bridge/__init__.py`, `__manifest__.py`, `models/__init__.py`, `models/helpdesk_ticket.py`, `tests/__init__.py`, `tests/test_lien_personne.py`

**Interfaces:**
- Consumes: `res.partner.his_person_ids` (his_person_core), `helpdesk.ticket.partner_id`.
- Produces: `helpdesk.ticket.his_person_id` (Many2one `his.person`, stored). Invariant: `ticket.his_person_id == ticket.partner_id.his_person_ids[:1]`.

- [ ] **Step 1: Manifest**

```python
{
    "name": "Helpdesk - Referentiel Personnes (pont)",
    "version": "19.0.1.0.0",
    "category": "Services/Helpdesk",
    "summary": "Chaque ticket est rattache a une personne du referentiel",
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": ["helpdesk_mgmt_crm", "his_person_core"],
    "data": [],
    "installable": True,
}
```

- [ ] **Step 2: Failing tests** (`tests/test_lien_personne.py`)

```python
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLienPersonne(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.etudiant = cls.env["his.person"].create(
            {
                "name": "Amel Saidi",
                "type_personne": "etudiant",
                "source_system": "manual",
                "email": "amel.saidi@example.com",
            }
        )
        cls.fournisseur = cls.env["res.partner"].create({"name": "Papeterie Atlas"})

    def _ticket(self, **vals):
        return self.env["helpdesk.ticket"].create({"name": "Attestation", "description": "<p>Demande</p>", **vals})

    def test_choisir_la_personne_pose_le_contact(self):
        ticket = self._ticket(his_person_id=self.etudiant.id)
        self.assertEqual(ticket.partner_id, self.etudiant.partner_id)

    def test_choisir_le_contact_pose_la_personne(self):
        ticket = self._ticket(partner_id=self.etudiant.partner_id.id)
        self.assertEqual(ticket.his_person_id, self.etudiant)

    def test_contact_hors_referentiel(self):
        ticket = self._ticket(partner_id=self.fournisseur.id)
        self.assertFalse(ticket.his_person_id)

    def test_changer_de_contact_efface_la_personne(self):
        ticket = self._ticket(his_person_id=self.etudiant.id)
        ticket.partner_id = self.fournisseur
        self.assertFalse(ticket.his_person_id)

    def test_vider_la_personne_vide_son_contact(self):
        ticket = self._ticket(his_person_id=self.etudiant.id)
        ticket.his_person_id = False
        self.assertFalse(ticket.partner_id)

    def test_le_helpdesk_ne_cree_aucune_personne(self):
        avant = self.env["his.person"].search_count([])
        self._ticket(partner_id=self.fournisseur.id)
        self._ticket(partner_name="Inconnu", partner_email="inconnu@example.com")
        self.assertEqual(self.env["his.person"].search_count([]), avant)
```

- [ ] **Step 3: Run** `-i his_helpdesk_identity_bridge --test-tags /his_helpdesk_identity_bridge` → FAIL (field missing).

- [ ] **Step 4: Implement** `models/helpdesk_ticket.py`

```python
from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    # Le lien est deterministe : une his.person delegue a UN res.partner.
    # Calcule depuis le contact, donc impossible a desynchroniser ; l'inverse
    # pose le contact quand l'agent choisit la personne.
    his_person_id = fields.Many2one(
        "his.person",
        string="Personne",
        compute="_compute_his_person_id",
        inverse="_inverse_his_person_id",
        store=True,
        readonly=False,
        index=True,
    )

    @api.depends("partner_id")
    def _compute_his_person_id(self):
        for ticket in self:
            ticket.his_person_id = ticket.partner_id.his_person_ids[:1]

    def _inverse_his_person_id(self):
        for ticket in self:
            # Vider la personne d'un ticket dont le contact est une personne
            # vide aussi le contact : sinon le calcul la remettrait.
            if ticket.his_person_id or ticket.partner_id.his_person_ids:
                ticket.partner_id = ticket.his_person_id.partner_id

    @api.onchange("his_person_id")
    def _onchange_his_person_id(self):
        # L'inverse n'agit qu'a l'enregistrement : remplir le contact tout de
        # suite dans le formulaire (et, en cascade, nom et email du ticket).
        if self.his_person_id or self.partner_id.his_person_ids:
            self.partner_id = self.his_person_id.partner_id
```

- [ ] **Step 5: Run** → PASS (6 tests).
- [ ] **Step 6: Commit** — `[ADD] his_helpdesk_identity_bridge : le ticket est rattache a une personne du referentiel`

---

### Task 4: Access and the ticket form

**Files:**
- Create: `his_helpdesk_identity_bridge/security/ir.model.access.csv`, `security/his_helpdesk_identity_bridge_security.xml`, `views/helpdesk_ticket_views.xml`, `tests/test_acces.py`
- Modify: `models/helpdesk_ticket.py` (header fields), `__manifest__.py` (`data`)

**Interfaces:** Produces `helpdesk.ticket.his_matricule` (Char), `his_type_personne` (Selection), `his_engagement_id` (Many2one `his.engagement`).

- [ ] **Step 1: Failing tests** (`tests/test_acces.py`)

```python
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestAcces(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.etudiant = cls.env["his.person"].create(
            {
                "name": "Karim Djebbar",
                "type_personne": "etudiant",
                "source_system": "manual",
                "email": "karim.djebbar@example.com",
            }
        )
        cls.env["his.engagement"].create({"person_id": cls.etudiant.id, "etat": "inscrit"})
        cls.agent = new_test_user(cls.env, login="agent_hd", groups="helpdesk_mgmt.group_helpdesk_user_own")
        cls.sans_role = new_test_user(cls.env, login="sans_role", groups="base.group_user")

    def test_un_agent_voit_l_etudiant(self):
        partner = self.etudiant.partner_id.with_user(self.agent)
        self.assertEqual(partner.email, "karim.djebbar@example.com")
        self.assertEqual(self.etudiant.with_user(self.agent).matricule_affiche, self.etudiant.matricule_affiche)

    def test_sans_role_l_etudiant_reste_ferme(self):
        with self.assertRaises(AccessError):
            self.etudiant.partner_id.with_user(self.sans_role).read(["email"])

    def test_l_agent_ouvre_un_ticket_et_lit_l_en_tete(self):
        ticket = (
            self.env["helpdesk.ticket"]
            .with_user(self.agent)
            .create({"name": "Carte", "description": "<p>x</p>", "his_person_id": self.etudiant.id})
        )
        self.assertEqual(ticket.his_matricule, self.etudiant.matricule_affiche)
        self.assertEqual(ticket.his_type_personne, "etudiant")
        self.assertEqual(ticket.his_engagement_id.etat, "inscrit")

    def test_l_agent_ne_modifie_pas_la_personne(self):
        with self.assertRaises(AccessError):
            self.etudiant.with_user(self.agent).write({"nom_arabe": "x"})
```

- [ ] **Step 2: Run** → FAIL (AccessError for the agent, missing fields).

- [ ] **Step 3: Implement**

`security/ir.model.access.csv`:
```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_his_person_helpdesk,his.person.helpdesk.lecture,his_person_core.model_his_person,helpdesk_mgmt.group_helpdesk_user_own,1,0,0,0
access_his_engagement_helpdesk,his.engagement.helpdesk.lecture,his_person_core.model_his_engagement,helpdesk_mgmt.group_helpdesk_user_own,1,0,0,0
```

`security/his_helpdesk_identity_bridge_security.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Audit S-6 : rouvre les etudiants et candidats que
         his_person_core.rule_partner_student_candidate_private ferme.
         Decision de Mohamed (2026-10-07) : tout agent du helpdesk les voit.
         group_helpdesk_user_own est le premier echelon : tous les agents
         l'ont, par implication. -->
    <record id="rule_partner_all_helpdesk" model="ir.rule">
        <field name="name">Contacts : tous (agents helpdesk)</field>
        <field name="model_id" ref="base.model_res_partner"/>
        <field name="groups" eval="[(4, ref('helpdesk_mgmt.group_helpdesk_user_own'))]"/>
        <field name="domain_force">[(1, '=', 1)]</field>
    </record>
</odoo>
```

Add to `HelpdeskTicket`:
```python
his_matricule = fields.Char(related="his_person_id.matricule_affiche", string="Matricule")
his_type_personne = fields.Selection(related="his_person_id.type_personne", string="Type de personne")
his_engagement_id = fields.Many2one(
    "his.engagement",
    string="Engagement en cours",
    compute="_compute_his_engagement_id",
)


@api.depends("his_person_id")
def _compute_his_engagement_id(self):
    for ticket in self:
        # _order de his.engagement : date_debut desc, id desc.
        ticket.his_engagement_id = ticket.his_person_id.engagement_ids[:1]
```

`views/helpdesk_ticket_views.xml` — inherit `helpdesk_mgmt.ticket_view_form`, before `partner_id`:
```xml
<field name="partner_id" position="before">
    <field name="his_person_id" groups="helpdesk_mgmt.group_helpdesk_user_own"
           options="{'no_create': True}"/>
    <field name="his_matricule" groups="helpdesk_mgmt.group_helpdesk_user_own"
           invisible="not his_person_id"/>
    <field name="his_type_personne" groups="helpdesk_mgmt.group_helpdesk_user_own"
           invisible="not his_person_id"/>
    <field name="his_engagement_id" groups="helpdesk_mgmt.group_helpdesk_user_own"
           invisible="not his_engagement_id"/>
</field>
```
(`no_create`: the helpdesk never creates a person, including from the picker.) Also add `his_person_id` to the ticket search view (`helpdesk_mgmt.helpdesk_ticket_view_search`) after `partner_id`. Verify both view xmlids in `helpdesk_mgmt/views/helpdesk_ticket_views.xml` before writing.

Manifest `data`: security CSV, security XML, `views/helpdesk_ticket_views.xml`.

- [ ] **Step 4: Run** bridge suite + `/his_access_base` → 0 failed.
- [ ] **Step 5: Commit** — `[ADD] his_helpdesk_identity_bridge : les agents voient la personne du ticket (S-6 rouvert)`

---

### Task 5: Person smart button and ticket → lead

**Files:**
- Create: `models/his_person.py`, `models/helpdesk_ticket_create_lead.py`, `views/his_person_views.xml`, `tests/test_personne_et_lead.py`
- Modify: `models/__init__.py`, `__manifest__.py`

**Interfaces:** Produces `his.person.his_helpdesk_ticket_count` (Integer), `his.person.action_his_helpdesk_tickets()` (window action dict).

- [ ] **Step 1: Failing tests**

```python
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPersonneEtLead(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.candidat = cls.env["his.person"].create(
            {
                "name": "Nadia Ferhat",
                "type_personne": "candidat",
                "source_system": "manual",
                "email": "nadia.ferhat@example.com",
            }
        )

    def _ticket(self):
        return self.env["helpdesk.ticket"].create(
            {"name": "Question Master", "description": "<p>x</p>", "his_person_id": self.candidat.id}
        )

    def test_compteur_de_tickets_sur_la_personne(self):
        self._ticket()
        self._ticket()
        self.assertEqual(self.candidat.his_helpdesk_ticket_count, 2)
        action = self.candidat.action_his_helpdesk_tickets()
        self.assertEqual(action["domain"], [("his_person_id", "=", self.candidat.id)])

    def test_le_lead_reprend_la_personne(self):
        if "his_person_id" not in self.env["crm.lead"]._fields:
            self.skipTest("his_crm_identity_bridge non installe")
        ticket = self._ticket()
        wizard = self.env["helpdesk.ticket.create.lead"].with_context(active_id=ticket.id).create({})
        wizard.action_helpdesk_ticket_to_lead()
        self.assertEqual(ticket.lead_ids.his_person_id, self.candidat)
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

`models/his_person.py`:
```python
from odoo import fields, models


class HisPerson(models.Model):
    _inherit = "his.person"

    his_helpdesk_ticket_count = fields.Integer(
        string="Tickets",
        compute="_compute_his_helpdesk_ticket_count",
    )

    def _compute_his_helpdesk_ticket_count(self):
        counts = dict(
            self.env["helpdesk.ticket"]._read_group([("his_person_id", "in", self.ids)], ["his_person_id"], ["__count"])
        )
        for person in self:
            person.his_helpdesk_ticket_count = counts.get(person, 0)

    def action_his_helpdesk_tickets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Tickets"),
            "res_model": "helpdesk.ticket",
            "view_mode": "list,form",
            "domain": [("his_person_id", "=", self.id)],
            "context": {"default_his_person_id": self.id},
        }
```

`models/helpdesk_ticket_create_lead.py`:
```python
from odoo import models


class HelpdeskTicketCreateLead(models.TransientModel):
    _inherit = "helpdesk.ticket.create.lead"

    def _prepare_vals(self):
        vals = super()._prepare_vals()
        # Sans dependance a his_crm_identity_bridge : on ne pose le champ que
        # s'il existe. Pose, il desarme le pont CRM (garde « deja rattache »).
        person = self.ticket_id.his_person_id
        if person and "his_person_id" in self.env["crm.lead"]._fields:
            vals["his_person_id"] = person.id
        return vals
```

`views/his_person_views.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_his_person_form_helpdesk" model="ir.ui.view">
        <field name="name">his.person.form.helpdesk</field>
        <field name="model">his.person</field>
        <field name="inherit_id" ref="his_person_core.view_his_person_form"/>
        <field name="arch" type="xml">
            <xpath expr="//div[hasclass('oe_title')]" position="before">
                <div class="oe_button_box" name="button_box"
                     groups="helpdesk_mgmt.group_helpdesk_user_own">
                    <button name="action_his_helpdesk_tickets" type="object"
                            class="oe_stat_button" icon="fa-life-ring">
                        <field name="his_helpdesk_ticket_count" widget="statinfo" string="Tickets"/>
                    </button>
                </div>
            </xpath>
        </field>
    </record>
</odoo>
```

- [ ] **Step 4: Run** bridge suite (with `his_crm_identity_bridge` installed in `hd_test`, the lead test runs, not skips) → 0 failed.
- [ ] **Step 5: Commit** — `[ADD] his_helpdesk_identity_bridge : tickets sur la fiche personne, et le lead garde la personne`

---

### Task 6: Teams, channel, French closing mail, sent off-request

**Files:**
- Create: `data/helpdesk_data.xml`, `tests/test_cloture.py`
- Modify: `models/helpdesk_ticket.py`, `__manifest__.py`

- [ ] **Step 1: Failing tests**

```python
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCloture(TransactionCase):
    def test_les_quatre_equipes_et_le_guichet(self):
        for xmlid in ("team_informatique", "team_scolarite", "team_admissions", "team_finance", "channel_guichet"):
            self.assertTrue(self.env.ref("his_helpdesk_identity_bridge." + xmlid))

    def test_la_cloture_part_en_file_et_reveille_le_cron(self):
        person = self.env["his.person"].create(
            {
                "name": "Rym Bouzid",
                "type_personne": "etudiant",
                "source_system": "manual",
                "email": "rym.bouzid@example.com",
            }
        )
        ticket = self.env["helpdesk.ticket"].create(
            {"name": "Attestation", "description": "<p>x</p>", "his_person_id": person.id}
        )
        cron = self.env.ref("mail.ir_cron_mail_scheduler_action")
        MailMail = type(self.env["mail.mail"])
        with (
            patch.object(MailMail, "send", autospec=True) as send,
            patch.object(type(cron), "_trigger", autospec=True) as trigger,
        ):
            ticket.stage_id = self.env.ref("helpdesk_mgmt.helpdesk_ticket_stage_done")
            self.env.flush_all()
        send.assert_not_called()
        trigger.assert_called()
        mail = self.env["mail.mail"].search([("model", "=", "helpdesk.ticket"), ("res_id", "=", ticket.id)])
        self.assertTrue(mail)
        self.assertIn("ne pas répondre", mail.body_html)
```

- [ ] **Step 2: Run** → FAIL (missing xmlids; `send` called synchronously).

- [ ] **Step 3: Implement**

`data/helpdesk_data.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <record id="team_informatique" model="helpdesk.ticket.team">
            <field name="name">Informatique</field>
        </record>
        <record id="team_scolarite" model="helpdesk.ticket.team">
            <field name="name">Scolarité</field>
        </record>
        <record id="team_admissions" model="helpdesk.ticket.team">
            <field name="name">Admissions</field>
        </record>
        <record id="team_finance" model="helpdesk.ticket.team">
            <field name="name">Finance / Caisse</field>
        </record>
        <record id="channel_guichet" model="helpdesk.ticket.channel">
            <field name="name">Guichet</field>
        </record>
        <!-- Les reponses partiraient chez Mailgun (MX de his.edu.dz) et
             n'atteindraient jamais Odoo : le courriel le dit. -->
        <record id="helpdesk_mgmt.closed_ticket_template" model="mail.template">
            <field name="subject">Votre demande {{object.number}} est clôturée</field>
            <field name="body_html" type="html">
                <p>Bonjour <t t-out="object.partner_id.name or object.partner_name or ''"/>,</p>
                <p>Votre demande <strong><t t-out="object.number"/></strong>
                   (« <t t-out="object.name"/> ») est clôturée.</p>
                <p>Ce message est envoyé automatiquement : merci de ne pas répondre.
                   Pour toute question, présentez-vous au guichet.</p>
            </field>
        </record>
    </data>
</odoo>
```

Add to `HelpdeskTicket` (same pattern as `his_mail_async`):
```python
    def _message_track_post_template(self, changes):
        # Le courriel de cloture passe par le suivi (_track_template) : envoye
        # dans la requete, il ferait attendre l'agent sur le SMTP. En file, et
        # le cron mail reveille (il ne tourne que toutes les heures).
        res = super(HelpdeskTicket, self.with_context(mail_notify_force_send=False))._message_track_post_template(changes)
        self.env.ref("mail.ir_cron_mail_scheduler_action")._trigger()
        return res
```
Verify the method name and signature in `odoo/addons/mail/models/mail_thread.py` (19.0) inside the container before writing; if the template is sent through `message_post_with_source` with `force_send` in kwargs instead of the context, override `_track_template` to set the option there.

Manifest `data`: add `data/helpdesk_data.xml`.

- [ ] **Step 4: Run** bridge suite → 0 failed.
- [ ] **Step 5: Commit** — `[ADD] his_helpdesk_identity_bridge : quatre equipes, le guichet, et la cloture en francais sans bloquer l'agent`

---

### Task 7: Full verification, render, push

- [ ] **Step 1:** Run every touched suite together on `hd_test`: `/his_person_core,/his_helpdesk_identity_bridge,/his_access_base,/his_crm_identity_bridge,/helpdesk_mgmt,/helpdesk_mgmt_crm` → 0 failed.
- [ ] **Step 2:** Lint as CI does: `ruff check . && ruff format --check .` (pinned ruff 0.16.7) on the bridge and `his_person_core`.
- [ ] **Step 3: Render.** Start `docker compose up -d odoo` on `hd_test`, log in as an agent, create a ticket from the person picker by matricule, screenshot the ticket form and the person form (smart button). Look at them.
- [ ] **Step 4:** Drop `hd_test` only if it was created for this branch (it was).
- [ ] **Step 5:** Push `feature/helpdesk-identite`; record the deploy command in the PR text: `-i helpdesk_mgmt,helpdesk_mgmt_crm,his_helpdesk_identity_bridge -u his_person_core`, then container `stop` + `start`.
