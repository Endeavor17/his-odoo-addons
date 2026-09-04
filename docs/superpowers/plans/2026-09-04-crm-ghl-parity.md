# CRM GoHighLevel Parity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the admissions advisers a board where recording a call outcome is cheaper than skipping it, and give the Direction a cockpit whose numbers cannot be blank.

**Architecture:** Three phases layered onto the existing `his_crm_pipeline` / `his_admission` modules. Phase 1 adds a call loop (three fields, three buttons) to `crm.lead` and surfaces it on the existing kanban cards. Phase 2 merges GoHighLevel's real loss vocabulary into `crm.lost.reason` and makes a reason mandatory via a server-side `@api.constrains`, beside the two constraints already there. Phase 3 extends the existing `his.dashboard` indicator service with distribution donuts, a data-quality queue, and revenue derived from a new `his.tarif` reference table. No new architecture, no new dependencies beyond `phone_validation` (Odoo Community).

**Tech Stack:** Odoo 19 Community, Python 3, OWL 2, SCSS, XML views. No build step — the repo is volume-mounted into the stock `odoo:19.0` image, so a change is live after a container restart.

**Spec:** [`docs/superpowers/specs/2026-09-04-crm-ghl-parity-design.md`](../specs/2026-09-04-crm-ghl-parity-design.md)

## Global Constraints

- **Odoo 19.0 Community.** No Enterprise module may be referenced. `appointment`, `whatsapp`, `voip` and `crm_enterprise` do not exist in this image.
- **No new pip dependency.** Third-party addons are vendored into the repo with a `VENDOR.md`, never pip-installed, because deployment has no build step.
- **Code comments and docstrings: French, unaccented ASCII.** Match the surrounding files exactly — `his_crm_pipeline/models/crm_lead.py` is the reference. Markdown docs use accents; Python does not.
- **User-facing strings: French, with accents,** wrapped in `_()`.
- **Every server rule is a constraint or a capability guard, never a view attribute.** Views may hide a gesture; only the server may refuse it. Kanban drag, import and the API all bypass views.
- **A KPI is defined once,** in `his_crm_pipeline/models/his_dashboard.py`. Never recompute a metric in JavaScript.
- **Test command** (Git Bash on Windows — `MSYS_NO_PATHCONV=1` is mandatory or `--test-tags` is silently mangled into a Windows path and collects zero tests):

```bash
docker compose stop odoo
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' docker compose run --rm odoo odoo \
  -d his_test --without-demo=all -i his_crm_pipeline \
  --test-enable --test-tags /his_crm_pipeline --stop-after-init
```

- **A clean upgrade log is not verification.** Any task touching UI ends by rendering the view and reading a screenshot. Chrome is at `/c/Program Files/Google/Chrome/Application/chrome.exe`.
- **Commit after every task.** Message in French, `[ADD]` / `[FIX]` / `[IMP]` / `[DOC]` prefix, matching `git log`.

---

# Phase 1 — The adviser board

## Task 1: Phone normalisation and the WhatsApp link

The card needs a number WhatsApp will accept. Algerian input arrives as `0555…`, `+213555…` or `00213555…`; `wa.me` accepts only digits with no `+` and no leading zero.

**Files:**
- Modify: `his_crm_pipeline/__manifest__.py` (add `phone_validation` to `depends`, bump version)
- Modify: `his_crm_pipeline/models/crm_lead.py` (add fields at the end of the Admissions field block, around line 45)
- Test: `his_crm_pipeline/tests/test_pipeline.py` (append a new section)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `crm.lead.telephone_e164` (Char, computed, non-stored) and `crm.lead.whatsapp_url` (Char, computed, non-stored). Task 3 renders both.

- [ ] **Step 1: Verify the `phone_validation` API before writing against it**

Docker must be running. This confirms the helper exists and its signature, rather than assuming it:

```bash
docker compose run --rm odoo python3 -c \
  "from odoo.addons.phone_validation.tools import phone_validation as p; import inspect; print(inspect.signature(p.phone_format))"
```

Expected: a signature containing `number`, `country_code`, `country_phone_code`, `force_format`. If `force_format='E164'` is not an accepted value, use `'E164'`'s equivalent the signature reveals and adjust Step 3 accordingly — do not proceed on a guess.

- [ ] **Step 2: Write the failing test**

Append to `his_crm_pipeline/tests/test_pipeline.py`:

```python
    # --- Telephone et lien WhatsApp -----------------------------------------

    def test_le_numero_algerien_est_normalise_en_e164(self):
        """Les trois formes saisies par les candidats donnent le meme numero.

        C'est le lien WhatsApp qui en depend : wa.me refuse un zero initial et
        refuse le signe plus.
        """
        for saisi in ('0555123456', '+213555123456', '00213555123456'):
            lead = self.env['crm.lead'].create({
                'name': "Candidat %s" % saisi,
                'team_id': self.team_ventes.id,
                'phone': saisi,
            })
            self.assertEqual(
                lead.telephone_e164, '+213555123456',
                "« %s » n'a pas ete normalise" % saisi,
            )
            self.assertEqual(
                lead.whatsapp_url,
                'https://wa.me/213555123456',
                "Le lien WhatsApp doit porter les chiffres seuls",
            )

    def test_sans_telephone_il_n_y_a_pas_de_lien(self):
        """Un lien vide plutot qu'un lien casse : la carte le masque."""
        lead = self.env['crm.lead'].create({
            'name': "Sans telephone",
            'team_id': self.team_ventes.id,
        })
        self.assertFalse(lead.telephone_e164)
        self.assertFalse(lead.whatsapp_url)
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
docker compose stop odoo
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' docker compose run --rm odoo odoo \
  -d his_test --without-demo=all -i his_crm_pipeline \
  --test-enable --test-tags /his_crm_pipeline --stop-after-init
```

Expected: FAIL — `AttributeError` or `Invalid field 'telephone_e164' on model 'crm.lead'`.

- [ ] **Step 4: Add the dependency and bump the version**

In `his_crm_pipeline/__manifest__.py`:

```python
    'version': '19.0.3.2.0',
    ...
    'depends': [
        'crm',
        'mail',
        # Normalisation E.164 des numeros algeriens. Module Community, deja
        # present dans l'image : c'est celui qu'Odoo utilise lui-meme. Ecrire
        # l'expression reguliere a la main serait reimplementer une dependance
        # deja installee.
        'phone_validation',
    ],
```

- [ ] **Step 5: Write the implementation**

In `his_crm_pipeline/models/crm_lead.py`, add the import at the top beside the existing ones:

```python
from odoo.addons.phone_validation.tools import phone_validation
```

Then add, after `date_visite_campus` (around line 45):

```python
    # --- Joindre le candidat ------------------------------------------------

    # NON STOCKES. Ces deux champs ne sont qu'une mise en forme de `phone` :
    # les stocker creerait un second endroit ou vit le numero, et deux
    # versions du meme numero finissent toujours par diverger. Le cout est nul,
    # le calcul est une expression reguliere sur une chaine deja en memoire.
    telephone_e164 = fields.Char(
        string="Telephone (E.164)", compute='_compute_telephone_e164',
        help="Le numero au format international, seule forme que WhatsApp accepte.",
    )
    whatsapp_url = fields.Char(
        string="Lien WhatsApp", compute='_compute_telephone_e164',
    )

    @api.depends('phone', 'mobile', 'country_id')
    def _compute_telephone_e164(self):
        """Normalise le numero saisi, quelle que soit la forme.

        Les candidats saisissent « 0555... », « +213555... » ou
        « 00213555... ». wa.me refuse le zero initial ET le signe plus : sans
        normalisation, deux candidats sur trois donnent un lien mort.

        L'Algerie par defaut, et non le pays de la societe : ce pipeline
        recrute en Algerie. country_id reste prioritaire quand il est
        renseigne, pour le candidat etranger.
        """
        for lead in self:
            brut = lead.phone or getattr(lead, 'mobile', False)
            if not brut:
                lead.telephone_e164 = False
                lead.whatsapp_url = False
                continue
            pays = lead.country_id
            try:
                e164 = phone_validation.phone_format(
                    brut,
                    pays.code or 'DZ',
                    pays.phone_code or 213,
                    force_format='E164',
                    raise_exception=False,
                )
            except Exception:
                # Un numero illisible n'est pas une erreur bloquante : la
                # conseillere le corrigera. Perdre la fiche pour un numero mal
                # tape serait hors de proportion.
                e164 = False
            # phone_format rend la saisie telle quelle quand il echoue : sans
            # ce controle, « n'importe quoi » deviendrait une URL WhatsApp.
            if not e164 or not e164.startswith('+'):
                lead.telephone_e164 = False
                lead.whatsapp_url = False
                continue
            lead.telephone_e164 = e164
            lead.whatsapp_url = 'https://wa.me/%s' % e164[1:]
```

- [ ] **Step 6: Run the test to verify it passes**

Same command as Step 3. Expected: PASS, both tests.

- [ ] **Step 7: Commit**

```bash
git add his_crm_pipeline/__manifest__.py his_crm_pipeline/models/crm_lead.py his_crm_pipeline/tests/test_pipeline.py
git commit -m "[ADD] Le numero du candidat, sous la forme que WhatsApp accepte

Les candidats saisissent 0555, +213555 ou 00213555. wa.me refuse le zero
initial et refuse le plus : sans normalisation, deux liens sur trois sont
morts. phone_validation fait ce travail et Odoo s'en sert deja — l'ecrire
a la main serait reimplementer une dependance installee.

Non stockes : ce n'est qu'une mise en forme de phone. Les stocker donnerait
deux versions du meme numero.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: The call loop

**Files:**
- Modify: `his_crm_pipeline/models/crm_lead.py` (fields after Task 1's block; methods after `_compute_livrables_resume`)
- Test: `his_crm_pipeline/tests/test_pipeline.py`

**Interfaces:**
- Consumes: nothing from Task 1 (independent fields on the same model).
- Produces: `crm.lead.tentatives_appel` (Integer, stored), `crm.lead.derniere_tentative` (Datetime, stored), `crm.lead.action_appel_sans_reponse()` (returns `None`), `crm.lead.action_appel_joint()` (returns an `ir.actions.act_window` dict). Task 3 binds both methods to buttons; Task 6 reads `tentatives_appel`.

- [ ] **Step 1: Write the failing tests**

Append to `his_crm_pipeline/tests/test_pipeline.py`:

```python
    # --- Boucle d'appel ------------------------------------------------------

    def _lead_pris_en_charge(self):
        return self.env['crm.lead'].create({
            'name': "Candidat a rappeler",
            'team_id': self.team_ventes.id,
            'stage_id': self.stage_pris_en_charge.id,
            'phone': '0555123456',
        })

    def test_une_tentative_sans_reponse_incremente_et_replanifie(self):
        lead = self._lead_pris_en_charge()
        self.assertEqual(lead.tentatives_appel, 0)

        lead.action_appel_sans_reponse()

        self.assertEqual(lead.tentatives_appel, 1)
        self.assertTrue(lead.derniere_tentative)
        # L'etape ne bouge pas : une tentative n'est pas un contact.
        self.assertEqual(lead.stage_id, self.stage_pris_en_charge)
        # Un rappel est pose, et un seul.
        rappels = self.env['mail.activity'].search([
            ('res_model', '=', 'crm.lead'), ('res_id', '=', lead.id),
        ])
        self.assertEqual(len(rappels), 1)

    def test_trois_tentatives_ne_posent_qu_un_seul_rappel(self):
        """Sinon la conseillere recoit une activite par tentative et cesse de
        les lire — exactement le defaut que la relance SLA evite deja."""
        lead = self._lead_pris_en_charge()
        for _ in range(3):
            lead.action_appel_sans_reponse()

        self.assertEqual(lead.tentatives_appel, 3)
        rappels = self.env['mail.activity'].search([
            ('res_model', '=', 'crm.lead'), ('res_id', '=', lead.id),
        ])
        self.assertEqual(len(rappels), 1, "Un seul rappel, replanifie")

    def test_joint_avance_a_contact_etabli_et_efface_le_rappel(self):
        lead = self._lead_pris_en_charge()
        lead.action_appel_sans_reponse()

        action = lead.action_appel_joint()

        self.assertEqual(
            lead.stage_id,
            self.env.ref('his_crm_pipeline.stage_vente_contact_etabli'),
        )
        self.assertFalse(self.env['mail.activity'].search([
            ('res_model', '=', 'crm.lead'), ('res_id', '=', lead.id),
        ]), "Le rappel n'a plus d'objet une fois le candidat joint")
        self.assertEqual(action['res_id'], lead.id)
        self.assertEqual(action['res_model'], 'crm.lead')

    def test_chaque_tentative_laisse_une_trace_datee(self):
        """Le compteur dit combien ; le fil dit quand. Le second explique le
        premier a qui relit la fiche trois semaines plus tard."""
        lead = self._lead_pris_en_charge()
        avant = len(lead.message_ids)
        lead.action_appel_sans_reponse()
        self.assertGreater(len(lead.message_ids), avant)
```

- [ ] **Step 2: Run the tests to verify they fail**

Same command as Task 1 Step 3. Expected: FAIL — `Invalid field 'tentatives_appel'`.

- [ ] **Step 3: Write the implementation**

In `his_crm_pipeline/models/crm_lead.py`, add near the top beside `SLA_PREMIER_CONTACT_HEURES`:

```python
# Delai avant le rappel suivant, apres une tentative sans reponse.
JOURS_AVANT_RAPPEL = 1
# Au-dela, le candidat n'a jamais repondu : c'est une candidature fantome.
TENTATIVES_AVANT_FANTOME = 3
```

Add the fields after Task 1's block:

```python
    # --- La boucle d'appel ---------------------------------------------------

    # Le compteur est ce qui transforme « candidature fantome » d'un souvenir
    # en un fait porte par la fiche. Sans lui, la conseillere qui reprend un
    # lead ne sait pas si personne n'a essaye ou si six personnes ont echoue.
    tentatives_appel = fields.Integer(
        string="Tentatives d'appel", default=0, copy=False, readonly=True,
        help="Nombre d'appels restes sans reponse. Remis a zero par aucun "
             "geste : c'est un historique, pas un etat.",
    )
    derniere_tentative = fields.Datetime(
        string="Derniere tentative", copy=False, readonly=True,
    )
```

Add the methods after `_compute_livrables_resume`:

```python
    # --- La boucle d'appel ---------------------------------------------------

    def action_appel_sans_reponse(self):
        """Le candidat n'a pas repondu : on compte, on trace, on replanifie.

        Trois effets et pas un de plus. L'etape ne bouge PAS — une tentative
        n'est pas un contact, et faire avancer le lead sur un appel sans
        reponse gonflerait le pipeline avec des candidats que personne n'a
        jamais eus au telephone.

        Aucune perte automatique au-dela de N tentatives : une machine qui
        declare un candidat perdu est la meme automatisation que la Direction a
        refusee pour l'affectation. La fiche propose, la conseillere decide.
        """
        for lead in self:
            lead.sudo().write({
                'tentatives_appel': lead.tentatives_appel + 1,
                'derniere_tentative': fields.Datetime.now(),
            })
            lead.message_post(body=_(
                "Appel sans reponse (tentative n° %(n)s).",
                n=lead.tentatives_appel,
            ))
            lead._his_replanifier_rappel()

    def _his_replanifier_rappel(self):
        """Un seul rappel a la fois, repousse plutot que duplique.

        Poser une activite par tentative ferait exactement ce que la relance
        SLA evite deja : une pile d'activites que le destinataire cesse de
        lire. On deplace donc celle qui existe.
        """
        self.ensure_one()
        echeance = fields.Date.context_today(self) + timedelta(
            days=JOURS_AVANT_RAPPEL,
        )
        activite = self._his_rappel_existant()
        if activite:
            activite.date_deadline = echeance
            return
        self.activity_schedule(
            'mail.mail_activity_data_call',
            date_deadline=echeance,
            summary=_("Rappeler le candidat"),
            user_id=self.user_id.id or self.env.uid,
        )

    def _his_rappel_existant(self):
        """Le rappel pose par cette boucle, s'il y en a un."""
        self.ensure_one()
        return self.env['mail.activity'].search([
            ('res_model', '=', 'crm.lead'),
            ('res_id', '=', self.id),
            ('summary', '=', "Rappeler le candidat"),
        ], limit=1)

    def action_appel_joint(self):
        """Le candidat a repondu : on avance, on efface le rappel, on ouvre.

        Ouvrir la fiche est la moitie utile du geste. Le contact vient d'avoir
        lieu, c'est le seul moment ou la conseillere se souvient de ce qui a
        ete dit ; l'ecran doit etre devant elle sans qu'elle ait a le chercher.
        """
        self.ensure_one()
        etape = self.env.ref(
            'his_crm_pipeline.stage_vente_contact_etabli',
            raise_if_not_found=False,
        )
        if etape:
            self.stage_id = etape
        self._his_rappel_existant().unlink()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Candidat joint"),
            'res_model': 'crm.lead',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
```

> **Note on `sudo()` in `action_appel_sans_reponse`:** the counter is written by the system recording a fact, not by the user asserting one. Without `sudo()` the capability guard in `crm_capacites.py` — which refuses `user_id` writes from non-managers and stage writes from Acquisition — would be evaluated against a write the adviser is entitled to make. `tentatives_appel` is `readonly=True`, so this is the only path that sets it.

- [ ] **Step 4: Verify `mail.mail_activity_data_call` exists**

The plan assumes Odoo ships a "Call" activity type with this XML ID. Confirm rather than assume:

```bash
MSYS_NO_PATHCONV=1 docker compose run --rm odoo odoo shell -d his_test --stop-after-init <<'PY'
print(env.ref('mail.mail_activity_data_call', raise_if_not_found=False))
PY
```

Expected: a `mail.activity.type` record. If it returns `None`, substitute `mail.mail_activity_data_todo` (already used by the SLA cron in this same file) in `_his_replanifier_rappel` and note the substitution in the commit message.

- [ ] **Step 5: Run the tests to verify they pass**

Same command as Task 1 Step 3. Expected: PASS, four tests.

- [ ] **Step 6: Commit**

```bash
git add his_crm_pipeline/models/crm_lead.py his_crm_pipeline/tests/test_pipeline.py
git commit -m "[ADD] La boucle d'appel : compter, tracer, replanifier

626 pertes dans GoHighLevel, 193 motifs. Les deux tiers ne disent rien
parce que consigner coute six gestes et sauter n'en coute aucun.

Deux gestes d'un clic. « Sans reponse » compte, poste une note datee et
repousse le rappel — l'etape ne bouge pas, une tentative n'est pas un
contact. « Joint » avance a Contact etabli, efface le rappel et ouvre la
fiche, seul moment ou la conseillere se souvient de ce qui a ete dit.

Un seul rappel, repousse plutot que duplique : une activite par tentative
ferait la pile que la relance SLA evite deja.

Aucune perte automatique au-dela de trois tentatives. Une machine qui
declare un candidat perdu est l'automatisation refusee pour l'affectation.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: Surface the loop on the card and the form

**Files:**
- Modify: `his_crm_pipeline/views/crm_lead_views.xml` (the `view_crm_lead_kanban_admissions` record, and the `his_admissions` page of `view_crm_lead_form_his`)

**Interfaces:**
- Consumes: `telephone_e164`, `whatsapp_url` (Task 1); `tentatives_appel`, `action_appel_sans_reponse`, `action_appel_joint` (Task 2).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Declare the new fields on the kanban**

In `his_crm_pipeline/views/crm_lead_views.xml`, inside `view_crm_lead_kanban_admissions`, extend the existing `<xpath expr="//kanban" position="inside">` block:

```xml
            <xpath expr="//kanban" position="inside">
                <field name="visite_campus_effectuee"/>
                <field name="tentatives_appel"/>
                <field name="telephone_e164"/>
                <field name="whatsapp_url"/>
            </xpath>
```

- [ ] **Step 2: Add the attempt badge to the card meta**

Replace the `o_his_lead_kanban_meta` block in `view_crm_lead_kanban_admissions` with:

```xml
            <xpath expr="//div[hasclass('o_kanban_card_crm_lead_revenue')]" position="replace">
                <div class="o_his_lead_kanban_meta d-flex align-items-center gap-1">
                    <span class="badge rounded-pill text-bg-light"
                          invisible="not score_academique"
                          title="Score academique">
                        <i class="fa fa-star-o me-1" role="img" aria-label="Score academique"/><field name="score_academique"/>
                    </span>
                    <!-- Le compteur ne s'affiche qu'a partir de la premiere
                         tentative : « 0 tentative » est le cas de tout lead
                         neuf et n'apprend rien. A partir de trois, il vire au
                         rouge — c'est le seuil de la candidature fantome. -->
                    <span class="badge rounded-pill"
                          invisible="not tentatives_appel"
                          t-att-class="record.tentatives_appel.raw_value >= 3 ? 'text-bg-danger' : 'text-bg-light'"
                          title="Appels restes sans reponse">
                        <i class="fa fa-phone me-1" role="img" aria-label="Tentatives d'appel"/><field name="tentatives_appel"/>
                    </span>
                    <i class="fa fa-calendar-check-o text-success"
                       role="img" aria-label="Visite du campus effectuee"
                       title="Visite du campus effectuee"
                       invisible="not visite_campus_effectuee"/>
                </div>
            </xpath>
```

- [ ] **Step 3: Add the action row to the card**

Immediately after the block from Step 2, still inside `view_crm_lead_kanban_admissions`:

```xml
            <!-- La rangee d'action : le geste de la conseillere, la ou elle
                 regarde deja. Des <button type="object"> natifs et non un
                 composant OWL maison — la carte stock les gere, et un widget
                 ecrit a la main casserait a la premiere refonte amont.

                 WhatsApp et tel: sont des LIENS PROFONDS, pas une integration.
                 Ils ouvrent l'application avec le numero pret. Aucun message
                 entrant, aucun accuse de reception, aucun fil dans Odoo :
                 Odoo 19 Community n'a ni telephonie, ni SMS gratuit, ni
                 WhatsApp. C'est une perte assumee face a GoHighLevel. -->
            <xpath expr="//div[hasclass('o_his_lead_kanban_meta')]" position="after">
                <div class="o_his_lead_actions d-flex align-items-center gap-1 mt-1">
                    <button type="object" name="action_appel_sans_reponse"
                            class="btn btn-sm btn-outline-secondary"
                            title="Appel sans reponse : compte, trace et replanifie">
                        <i class="fa fa-phone-square" role="img"/> Sans reponse
                    </button>
                    <button type="object" name="action_appel_joint"
                            class="btn btn-sm btn-outline-primary"
                            title="Candidat joint : passe en Contact etabli">
                        <i class="fa fa-check" role="img"/> Joint
                    </button>
                    <a t-if="record.whatsapp_url.raw_value"
                       t-att-href="record.whatsapp_url.raw_value"
                       target="_blank" rel="noopener"
                       class="btn btn-sm btn-outline-success"
                       title="Ouvrir WhatsApp avec ce numero"
                       aria-label="Ouvrir WhatsApp">
                        <i class="fa fa-whatsapp" role="img"/>
                    </a>
                    <a t-if="record.telephone_e164.raw_value"
                       t-attf-href="tel:{{ record.telephone_e164.raw_value }}"
                       class="btn btn-sm btn-outline-secondary"
                       title="Appeler (utile sur mobile)"
                       aria-label="Appeler">
                        <i class="fa fa-phone" role="img"/>
                    </a>
                </div>
            </xpath>
```

- [ ] **Step 4: Add the same actions to the form**

In `view_crm_lead_form_his`, inside the `his_admissions` page, replace the `<group string="Visite du campus">` group's sibling structure by adding a third group after it:

```xml
                        <group string="Joindre le candidat">
                            <field name="tentatives_appel"/>
                            <field name="derniere_tentative"
                                   invisible="not tentatives_appel"/>
                            <field name="telephone_e164"/>
                            <div class="d-flex gap-2 mt-2">
                                <button name="action_appel_sans_reponse"
                                        type="object" class="btn btn-secondary btn-sm"
                                        string="Sans reponse"/>
                                <button name="action_appel_joint"
                                        type="object" class="btn btn-primary btn-sm"
                                        string="Joint"/>
                                <widget name="url" invisible="not whatsapp_url"/>
                            </div>
                            <field name="whatsapp_url" widget="url"
                                   text="Ouvrir WhatsApp"
                                   invisible="not whatsapp_url"/>
                        </group>
```

Remove the stray `<widget name="url" .../>` line above if the `url` widget on the field below renders correctly — verify in Step 6 and delete whichever is redundant. Keep exactly one WhatsApp affordance on the form.

- [ ] **Step 5: Restart and confirm the module loads**

```bash
docker compose restart odoo
docker compose logs --tail=40 odoo
```

Expected: no `ParseError`, no `Field ... does not exist`. A view arch error fails loudly at load — this is the one class of defect compilation *does* catch.

- [ ] **Step 6: Render the board and read the screenshot**

This is not optional. Every real defect in this project has been invisible to a clean load — a `.bg-100` utility painting over the theme, a monospace face inherited onto a product name, a search field turned white-on-white.

Open the Admissions pipeline in a browser against the dev instance, with at least one lead carrying a phone number and `tentatives_appel >= 3`, then capture and **actually look at**:

```bash
"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless --disable-gpu --window-size=1600,1000 \
  --screenshot=/tmp/board.png "http://localhost:8069/odoo/crm"
```

Confirm, by eye: the buttons fit on the card without wrapping into an unreadable stack; the red badge appears at three attempts and not before; the WhatsApp and phone icons are distinguishable; the card is still legible at a narrow window width (the team is mostly desktop, sometimes mobile).

If the action row makes the card too tall to scan a column at a glance, collapse the two link icons into the card's existing dropdown menu (`//t[@t-name='menu']`, where *Programmer une visite* already lives) and keep only the two text buttons inline.

- [ ] **Step 7: Commit**

```bash
git add his_crm_pipeline/views/crm_lead_views.xml
git commit -m "[ADD] Les deux gestes de l'appel, sur la carte et sur la fiche

Des boutons natifs et non un composant maison : la carte stock les gere,
un widget ecrit a la main casserait a la premiere refonte amont.

Le compteur n'apparait qu'a la premiere tentative — « 0 tentative » est le
cas de tout lead neuf — et vire au rouge a trois, seuil de la candidature
fantome.

WhatsApp et tel: sont des liens profonds, pas une integration : ils
ouvrent l'application avec le numero pret. Aucun message entrant, aucun
fil dans Odoo. Community n'a ni telephonie, ni SMS gratuit, ni WhatsApp ;
c'est une perte assumee face a GoHighLevel.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

# Phase 2 — A loss that says something

## Task 4: The merged loss taxonomy

**Files:**
- Modify: `his_crm_pipeline/data/crm_lost_reason_data.xml`
- Test: `his_crm_pipeline/tests/test_pipeline.py`

**Interfaces:**
- Consumes: nothing.
- Produces: XML IDs `his_crm_pipeline.lost_reason_fantome`, `lost_reason_sans_reponse`, `lost_reason_numero_errone`, `lost_reason_bac_ancien`, `lost_reason_trop_cher`, `lost_reason_profil_inadapte`, `lost_reason_autre`. Task 5 references `lost_reason_autre`; Task 6 references `lost_reason_fantome`.

- [ ] **Step 1: Check whether `crm.lost.reason` has a `sequence` field**

The frequency ordering in Step 3 depends on it. Confirm rather than assume:

```bash
MSYS_NO_PATHCONV=1 docker compose run --rm odoo odoo shell -d his_test --stop-after-init <<'PY'
print('sequence' in env['crm.lost.reason']._fields)
PY
```

If `True`, use the `sequence` values written in Step 3. If `False`, delete every `<field name="sequence">` line from Step 3 and instead add the field in a new `his_crm_pipeline/models/crm_lost_reason.py`:

```python
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class CrmLostReason(models.Model):
    """Un ordre, parce que le motif le plus frequent doit etre le plus proche.

    Odoo trie les motifs par nom. Or trois motifs couvrent environ 70 % des
    pertes reelles : les laisser disperses dans un ordre alphabetique fait
    parcourir onze lignes a chaque cloture, et une cloture couteuse est une
    cloture qu'on saute — exactement ce que la contrainte de motif obligatoire
    cherche a eviter.
    """
    _inherit = 'crm.lost.reason'
    _order = 'sequence, name'

    sequence = fields.Integer(default=50)
```

Then register it in `his_crm_pipeline/models/__init__.py` (`from . import crm_lost_reason`).

- [ ] **Step 2: Write the failing test**

Append to `his_crm_pipeline/tests/test_pipeline.py`:

```python
    # --- Taxonomie des pertes ------------------------------------------------

    def test_les_motifs_d_issue_d_appel_existent(self):
        """Les leads meurent au telephone, pas en revue de dossier.

        Les quatre motifs d'origine decrivent tous une mort tardive. Les
        chiffres de GoHighLevel disent l'inverse : fantome, sans reponse et
        numero errone sont la majorite des pertes expliquees.
        """
        for xmlid in (
            'lost_reason_fantome', 'lost_reason_sans_reponse',
            'lost_reason_numero_errone', 'lost_reason_bac_ancien',
            'lost_reason_trop_cher', 'lost_reason_profil_inadapte',
            'lost_reason_autre',
        ):
            motif = self.env.ref(
                'his_crm_pipeline.%s' % xmlid, raise_if_not_found=False,
            )
            self.assertTrue(motif, "Motif manquant : %s" % xmlid)

    def test_les_motifs_d_origine_survivent(self):
        """noupdate et ondelete='restrict' : on ajoute, on ne remplace pas.

        Un motif supprime emporterait avec lui tous les leads qui le portaient.
        """
        for xmlid in (
            'lost_reason_hors_quota', 'lost_reason_dossier_non_retenu',
            'lost_reason_dossier_incomplet', 'lost_reason_paiement_non_confirme',
            'lost_reason_retour_production',
        ):
            self.assertTrue(self.env.ref(
                'his_crm_pipeline.%s' % xmlid, raise_if_not_found=False,
            ), "Motif d'origine perdu : %s" % xmlid)
```

- [ ] **Step 3: Run to verify it fails, then add the data**

Run the test command. Expected: FAIL on `lost_reason_fantome`.

Then add to `his_crm_pipeline/data/crm_lost_reason_data.xml`, inside the existing `<data noupdate="1">`, before the closing tag:

```xml
        <!-- ============ Issues d'appel ============

             Reprises de GoHighLevel, ou elles representent la majorite des
             pertes reellement expliquees : fantome 48, sans reponse 56,
             numero errone 12, BAC trop ancien 12, trop cher 15, profil
             inadapte 17.

             « Sans reponse » fusionne les deux entrees « No Answer » et
             « No answer » que GHL tenait separees. Les laisser scindees
             perpetuerait un compartiment coupe en deux dans tous les
             graphiques a venir, pour aucun gain.

             « Unknown » (13) n'est PAS repris : il n'enregistre rien. Sa place
             est tenue par « Autre », qui exige une precision — voir la
             contrainte dans models/crm_lead.py.

             sequence : l'ordre de frequence reelle, et non l'alphabet. Trois
             motifs couvrent environ 70 % des cas ; les mettre en tete est ce
             qui rend la cloture assez rapide pour ne pas etre sautee. -->

        <record id="lost_reason_sans_reponse" model="crm.lost.reason">
            <field name="name">Sans reponse</field>
            <field name="sequence">10</field>
        </record>

        <record id="lost_reason_fantome" model="crm.lost.reason">
            <field name="name">Candidature fantome</field>
            <field name="sequence">20</field>
        </record>

        <record id="lost_reason_profil_inadapte" model="crm.lost.reason">
            <field name="name">Profil non adapte</field>
            <field name="sequence">30</field>
        </record>

        <record id="lost_reason_trop_cher" model="crm.lost.reason">
            <field name="name">Frais trop eleves</field>
            <field name="sequence">40</field>
        </record>

        <record id="lost_reason_numero_errone" model="crm.lost.reason">
            <field name="name">Numero errone</field>
            <field name="sequence">50</field>
        </record>

        <record id="lost_reason_bac_ancien" model="crm.lost.reason">
            <field name="name">BAC trop ancien</field>
            <field name="sequence">60</field>
        </record>

        <!-- La soupape d'honnetete. Un motif obligatoire sans porte de sortie
             ne produit pas de meilleures donnees, il produit des mensonges
             confiants : la conseillere qui ne sait pas choisit ce qui est le
             plus proche du curseur, et ce motif-la est pire qu'un vide parce
             qu'il ne se distingue pas d'un vrai. Choisir « Autre » oblige a
             preciser — voir _check_perte_motivee. -->
        <record id="lost_reason_autre" model="crm.lost.reason">
            <field name="name">Autre - a preciser</field>
            <field name="sequence">99</field>
        </record>
```

- [ ] **Step 4: Upgrade and run the tests**

```bash
docker compose stop odoo
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' docker compose run --rm odoo odoo \
  -d his_test --without-demo=all -u his_crm_pipeline \
  --test-enable --test-tags /his_crm_pipeline --stop-after-init
```

Expected: PASS, both tests.

- [ ] **Step 5: Commit**

```bash
git add his_crm_pipeline/data/crm_lost_reason_data.xml his_crm_pipeline/models/ his_crm_pipeline/tests/test_pipeline.py
git commit -m "[ADD] Les motifs de perte qui decrivent vraiment comment on perd

Les quatre motifs livres decrivent une mort tardive, en revue de dossier.
Les chiffres de GoHighLevel disent l'inverse : fantome 48, sans reponse
56, numero errone 12 — les leads meurent au telephone.

« No Answer » et « No answer » etaient deux entrees dans GHL ; elles
fusionnent, sans quoi tout graphique a venir compterait un compartiment
coupe en deux. Une fois fusionnees, 104 des 193 pertes expliquees sont
« jamais joint ».

« Unknown » n'est pas repris : il n'enregistre rien. « Autre » le
remplace et exige une precision. Un motif obligatoire sans porte de
sortie ne produit pas de meilleures donnees, il produit des mensonges
confiants.

Rien n'est supprime : ondelete='restrict' et noupdate='1'.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: A loss cannot be silent

**Files:**
- Modify: `his_crm_pipeline/models/crm_lead.py` (constraint beside `_check_livrables_approuves`)
- Test: `his_crm_pipeline/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `his_crm_pipeline.lost_reason_autre` (Task 4).
- Produces: `crm.lead._check_perte_motivee()`. No later task consumes it.

- [ ] **Step 1: Write the failing tests**

```python
    # --- Une perte doit dire quelque chose -----------------------------------

    def test_perdre_sans_motif_est_refuse(self):
        """626 pertes, 193 motifs. Le vide n'est plus une option.

        Contrainte serveur et non regle de vue : le kanban, l'import et l'API
        contournent une vue. C'est la meme discipline que le verrou
        d'approbation et que « gagne seulement si encaisse ».
        """
        lead = self.env['crm.lead'].create({
            'name': "Candidat perdu",
            'team_id': self.team_ventes.id,
        })
        with self.assertRaises(ValidationError):
            lead.action_set_lost()

    def test_perdre_avec_un_motif_passe(self):
        lead = self.env['crm.lead'].create({
            'name': "Candidat injoignable",
            'team_id': self.team_ventes.id,
        })
        lead.action_set_lost(lost_reason_id=self.env.ref(
            'his_crm_pipeline.lost_reason_sans_reponse').id)
        self.assertFalse(lead.active)

    def test_autre_sans_precision_est_refuse(self):
        """La soupape d'honnetete a un prix : il faut ecrire la ligne.

        Sans cela « Autre » deviendrait le raccourci universel et on aurait
        remplace un vide par un mot qui ne dit pas davantage.
        """
        lead = self.env['crm.lead'].create({
            'name': "Candidat indetermine",
            'team_id': self.team_ventes.id,
        })
        with self.assertRaises(ValidationError):
            lead.action_set_lost(lost_reason_id=self.env.ref(
                'his_crm_pipeline.lost_reason_autre').id)

    def test_autre_avec_precision_passe(self):
        lead = self.env['crm.lead'].create({
            'name': "Candidat indetermine",
            'team_id': self.team_ventes.id,
            'perte_precision': "Parti a l'etranger, ne rappellera pas.",
        })
        lead.action_set_lost(lost_reason_id=self.env.ref(
            'his_crm_pipeline.lost_reason_autre').id)
        self.assertFalse(lead.active)
```

- [ ] **Step 2: Run to verify they fail**

Expected: the first test FAILS (no exception raised — `action_set_lost` succeeds today), and the last two ERROR on `Invalid field 'perte_precision'`.

- [ ] **Step 3: Write the implementation**

Add the field beside the call-loop fields in `his_crm_pipeline/models/crm_lead.py`:

```python
    perte_precision = fields.Char(
        string="Precision sur la perte", copy=False,
        help="Obligatoire avec le motif « Autre ». Ce que les motifs de la "
             "liste ne savent pas dire.",
    )
```

Add the constraint after `_check_livrables_approuves`:

```python
    @api.constrains('active', 'lost_reason_id', 'perte_precision')
    def _check_perte_motivee(self):
        """On ne perd pas un candidat sans dire pourquoi.

        Dans GoHighLevel, 626 opportunites perdues portent 193 motifs : les
        deux tiers ne disent rien. Ce n'est pas de la negligence — consigner
        coutait six gestes et sauter n'en coutait aucun. La contrainte rend le
        vide impossible ; la boucle d'appel et le pre-remplissage rendent le
        motif bon marche. Les deux sont necessaires : une contrainte seule
        pousserait a ne plus clore du tout, et le pipeline se remplirait de
        cadavres — une panne pire que celle qu'on repare.

        Contrainte serveur et non regle de vue, pour la meme raison que le
        verrou d'approbation : le glisser-deposer du kanban, l'import et l'API
        ne passent par aucune vue. Ils passent tous par write().

        Les deux pipelines, sans distinction d'equipe. Brancher par equipe
        serait du code de plus pour rien : la seule perte du pipeline Contenu
        est « Retour production necessaire », qu'il renseigne deja.
        """
        autre = self.env.ref(
            'his_crm_pipeline.lost_reason_autre', raise_if_not_found=False,
        )
        for lead in self:
            # active=False sans motif : c'est une perte, pas un archivage.
            # Odoo n'a pas d'autre marqueur — is_won vit sur l'etape, et une
            # fiche perdue est exactement une fiche desactivee.
            if lead.active:
                continue
            if not lead.lost_reason_id:
                raise ValidationError(_(
                    "« %(lead)s » ne peut pas etre perdu sans motif.\n\n"
                    "Le motif est ce qui permet de savoir ou l'on perd les "
                    "candidats. Si aucun de la liste ne convient, choisissez "
                    "« Autre - a preciser » et dites en une ligne ce qui s'est "
                    "passe.",
                    lead=lead.display_name,
                ))
            if autre and lead.lost_reason_id == autre \
                    and not (lead.perte_precision or '').strip():
                raise ValidationError(_(
                    "« %(lead)s » : le motif « Autre » demande une precision.\n\n"
                    "Sans elle, « Autre » deviendrait le raccourci universel et "
                    "n'apprendrait rien de plus qu'un motif vide.",
                    lead=lead.display_name,
                ))
```

- [ ] **Step 4: Expose the precision field on the form**

In `view_crm_lead_form_his`, inside the `his_admissions` page, add to the *Joindre le candidat* group from Task 3:

```xml
                            <field name="perte_precision"
                                   placeholder="Obligatoire avec le motif « Autre »"/>
```

- [ ] **Step 5: Run the tests to verify they pass**

Expected: PASS, four tests. If `action_set_lost` does not accept `lost_reason_id` as a keyword in this Odoo version, the tests will error — in that case set `lead.lost_reason_id` before calling `lead.action_set_lost()` and keep the assertions unchanged.

- [ ] **Step 6: Commit**

```bash
git add his_crm_pipeline/models/crm_lead.py his_crm_pipeline/views/crm_lead_views.xml his_crm_pipeline/tests/test_pipeline.py
git commit -m "[ADD] Une perte ne peut plus etre muette

626 pertes, 193 motifs : les deux tiers ne disaient rien. Pas par
negligence — consigner coutait six gestes, sauter n'en coutait aucun.

Contrainte serveur, aux cotes du verrou d'approbation et de « gagne
seulement si encaisse » : le kanban, l'import et l'API ne passent par
aucune vue, ils passent tous par write().

« Autre » exige une precision, sinon il devient le raccourci universel et
on aurait remplace un vide par un mot vide.

La contrainte seule serait nuisible : elle pousserait a ne plus clore et
le pipeline se remplirait de cadavres. C'est le pre-remplissage de la
tache suivante qui la rend supportable.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: Make the loss cheap — pre-fill from the record

**Files:**
- Modify: `his_crm_pipeline/models/crm_lead.py`
- Modify: `his_crm_pipeline/views/crm_lead_views.xml`
- Test: `his_crm_pipeline/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `tentatives_appel` (Task 2), `TENTATIVES_AVANT_FANTOME` (Task 2), `lost_reason_fantome` (Task 4).
- Produces: `crm.lead.action_perdre_rapide()` returning an `ir.actions.act_window` dict for `crm.lead.lost`.

- [ ] **Step 1: Write the failing test**

```python
    def test_apres_trois_tentatives_la_perte_propose_fantome(self):
        """La fiche sait deja. Elle ne demande pas.

        C'est ce qui rend le motif obligatoire supportable : trois clics sans
        reflexion plutot qu'un menu de onze lignes a lire.
        """
        lead = self._lead_pris_en_charge()
        for _ in range(3):
            lead.action_appel_sans_reponse()

        action = lead.action_perdre_rapide()

        self.assertEqual(
            action['context']['default_lost_reason_id'],
            self.env.ref('his_crm_pipeline.lost_reason_fantome').id,
        )

    def test_avant_trois_tentatives_aucun_motif_n_est_impose(self):
        """Deviner a la place de la conseillere serait pire que ne rien
        proposer : un motif faux ne se distingue pas d'un motif vrai."""
        lead = self._lead_pris_en_charge()
        lead.action_appel_sans_reponse()

        action = lead.action_perdre_rapide()

        self.assertFalse(action['context'].get('default_lost_reason_id'))
```

- [ ] **Step 2: Run to verify it fails**

Expected: FAIL — `'crm.lead' object has no attribute 'action_perdre_rapide'`.

- [ ] **Step 3: Write the implementation**

Add after `action_appel_joint` in `his_crm_pipeline/models/crm_lead.py`:

```python
    def action_perdre_rapide(self):
        """Ouvre l'assistant de perte, pre-rempli quand la fiche sait deja.

        Trois tentatives sans reponse SONT une candidature fantome : demander
        a la conseillere de le retrouver dans une liste de onze motifs revient
        a lui faire ressaisir ce que le compteur vient de mesurer.

        En dessous de trois, rien n'est propose. Deviner serait pire que se
        taire : un motif faux ne se distingue pas d'un motif vrai, et c'est
        precisement le defaut de « Unknown » qu'on vient de retirer.
        """
        self.ensure_one()
        contexte = dict(self.env.context, default_lead_ids=[self.id])
        if self.tentatives_appel >= TENTATIVES_AVANT_FANTOME:
            fantome = self.env.ref(
                'his_crm_pipeline.lost_reason_fantome',
                raise_if_not_found=False,
            )
            if fantome:
                contexte['default_lost_reason_id'] = fantome.id
        return {
            'type': 'ir.actions.act_window',
            'name': _("Perdre le candidat"),
            'res_model': 'crm.lead.lost',
            'view_mode': 'form',
            'target': 'new',
            'context': contexte,
        }
```

- [ ] **Step 4: Verify the lose wizard's model name and context key**

`crm.lead.lost` and `default_lead_ids` are assumptions about the stock wizard. Confirm both:

```bash
MSYS_NO_PATHCONV=1 docker compose run --rm odoo odoo shell -d his_test --stop-after-init <<'PY'
w = env['crm.lead.lost']
print(sorted(w._fields))
PY
```

Expected: a field list containing `lead_ids` and `lost_reason_id`. If the model is named differently or the leads field is `lead_id`, adjust the `default_` keys in Step 3 to match exactly. Do not guess — a wrong context key fails silently, opening an empty wizard.

- [ ] **Step 5: Wire the button on the card**

In `view_crm_lead_kanban_admissions`, add to the action row from Task 3, after the *Joint* button:

```xml
                    <button type="object" name="action_perdre_rapide"
                            class="btn btn-sm btn-outline-danger"
                            title="Perdre le candidat, motif pre-rempli si la fiche le sait">
                        <i class="fa fa-times" role="img"/> Perdu
                    </button>
```

- [ ] **Step 6: Run the tests to verify they pass**

Expected: PASS, both tests, and the whole `/his_crm_pipeline` suite still green.

- [ ] **Step 7: Render and read the screenshot**

Same procedure as Task 3 Step 6. Confirm the *Perdu* button does not push the row to two lines, and that clicking it opens the wizard with the reason already selected on a lead with three attempts.

- [ ] **Step 8: Commit**

```bash
git add his_crm_pipeline/models/crm_lead.py his_crm_pipeline/views/crm_lead_views.xml his_crm_pipeline/tests/test_pipeline.py
git commit -m "[IMP] La perte pre-remplie : la fiche sait deja, elle ne demande pas

Trois tentatives sans reponse SONT une candidature fantome. Faire
retrouver ce motif dans une liste de onze lignes revient a faire
ressaisir ce que le compteur vient de mesurer.

En dessous de trois, rien n'est propose. Deviner serait pire que se
taire : un motif faux ne se distingue pas d'un vrai — c'est exactement le
defaut de « Unknown » qu'on vient de retirer.

Sans cette tache, la contrainte de la precedente pousserait a ne plus
clore du tout.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

# Phase 3 — The director cockpit

## Task 7: Distribution donuts, server side

**Files:**
- Modify: `his_crm_pipeline/models/his_dashboard.py`
- Test: `his_crm_pipeline/tests/test_dashboard.py`

**Interfaces:**
- Consumes: `_action()`, `_entre()`, `_equipes_admissions()` (existing helpers in the same file).
- Produces: `his.dashboard._donut(label, model, domain, groupby)` returning `{'label', 'total', 'segments': [{'label', 'count', 'pourcentage', 'action'}]}`, and a `donuts` key in the dict returned by `get_admissions`. Task 8 renders it.

- [ ] **Step 1: Write the failing test**

Append to `his_crm_pipeline/tests/test_dashboard.py`:

```python
    def test_les_segments_d_un_donut_somment_a_son_total(self):
        """La regle du fichier : un indicateur est defini une seule fois.

        Si un donut et sa tuile comptent la meme population differemment, le
        directeur arbitre entre deux ecrans qui se contredisent.
        """
        spec = self.env['his.dashboard'].get_admissions('2020-01-01', '2100-01-01')
        self.assertIn('donuts', spec)
        for donut in spec['donuts']:
            somme = sum(s['count'] for s in donut['segments'])
            self.assertEqual(
                somme, donut['total'],
                "Le donut « %s » ne somme pas a son total" % donut['label'],
            )

    def test_chaque_segment_porte_son_action(self):
        """Un chiffre qu'on ne peut pas ouvrir doit etre cru sur parole, et
        c'est aussi ce qui rend une definition fausse indetectable."""
        spec = self.env['his.dashboard'].get_admissions('2020-01-01', '2100-01-01')
        for donut in spec['donuts']:
            for segment in donut['segments']:
                self.assertTrue(segment['action'])
                self.assertEqual(segment['action']['res_model'], 'crm.lead')
```

- [ ] **Step 2: Run to verify it fails**

Expected: FAIL — `KeyError: 'donuts'` or the `assertIn` fails.

- [ ] **Step 3: Write the `_donut` helper**

Add to `his_crm_pipeline/models/his_dashboard.py`, after `_a_traiter`:

```python
    def _donut(self, label, model, domain, groupby):
        """Une repartition : un tout, decoupe en parts qui le somment.

        Un seul _read_group sur une colonne deja stockee. Aucun SQL, aucune
        table d'agregat, comme partout dans ce fichier.

        Les parts sont triees par effectif decroissant : une legende dans
        l'ordre de la base fait chercher la plus grosse part a l'oeil.

        Chaque part porte son action, comme chaque tuile : cliquer une part
        doit ouvrir exactement les enregistrements qu'elle compte. C'est ce qui
        rend une definition fausse detectable au lieu de simplement fausse.
        """
        Model = self.env[model]
        groupes = Model._read_group(domain, groupby=[groupby], aggregates=['__count'])

        segments = []
        total = 0
        for valeur, compte in groupes:
            total += compte
            # _read_group rend un recordset pour un Many2one, la valeur brute
            # pour une Selection, et False pour un groupe vide. display_name
            # couvre le premier cas, le libelle du champ le second.
            if hasattr(valeur, 'display_name'):
                nom = valeur.display_name or "Non renseigne"
                critere = valeur.id
            else:
                nom = str(valeur) if valeur else "Non renseigne"
                critere = valeur
            segments.append({
                'label': nom,
                'count': compte,
                'action': self._action(
                    "%s : %s" % (label, nom), model,
                    domain + [(groupby, '=', critere)],
                ),
            })

        segments.sort(key=lambda s: s['count'], reverse=True)
        for segment in segments:
            segment['pourcentage'] = (
                round(segment['count'] / total * 100, 1) if total else 0
            )
        return {'label': label, 'total': total, 'segments': segments}
```

- [ ] **Step 4: Build the four donuts**

Add to the same file, after `_entonnoir`:

```python
    def _admissions_donuts(self, equipes, date_from, date_to):
        """Les quatre repartitions du cockpit GoHighLevel.

        Elles repondent a quatre questions distinctes : quelle qualite de
        candidats arrive, ou en est le portefeuille, ou l'on perd, et d'ou
        vient l'acquisition. Une cinquieme ferait double emploi.

        `active_test: False` sur les deux dernieres : une candidature perdue
        EST une fiche desactivee. Sans cela, le donut des motifs de perte
        serait vide, ce qui est la seule chose plus inutile qu'un motif faux.
        """
        base = [('team_id', 'in', equipes.ids)] + self._entre(date_from, date_to)
        perdus = self.with_context(active_test=False)

        return [
            self._donut(
                "Candidats par score", 'crm.lead', base, 'score_academique',
            ),
            self._donut(
                "Etat du portefeuille", 'crm.lead', base, 'stage_id',
            ),
            perdus._donut(
                "Motifs de perte", 'crm.lead',
                base + [('active', '=', False), ('lost_reason_id', '!=', False)],
                'lost_reason_id',
            ),
            perdus._donut(
                "Acquisition par source", 'crm.lead', base, 'source_id',
            ),
        ]
```

Then add the key to `get_admissions`'s return dict, beside `funnel`:

```python
            'donuts': self._admissions_donuts(equipes, date_from, date_to),
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
docker compose stop odoo
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' docker compose run --rm odoo odoo \
  -d his_test --without-demo=all -u his_crm_pipeline \
  --test-enable --test-tags /his_crm_pipeline --stop-after-init
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add his_crm_pipeline/models/his_dashboard.py his_crm_pipeline/tests/test_dashboard.py
git commit -m "[ADD] Quatre repartitions, definies la ou vivent les indicateurs

Score, portefeuille, motifs de perte, acquisition. Un _read_group chacune,
sur des colonnes deja stockees : ni SQL ni table d'agregat, comme le reste
du fichier.

Chaque part porte son action. Une part qu'on ne peut pas ouvrir doit etre
crue sur parole, et c'est aussi ce qui rend une definition fausse
indetectable — un test verifie que les parts somment a leur total.

active_test=False sur les pertes : une candidature perdue EST une fiche
desactivee. Sans cela le donut des motifs serait vide.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 8: Draw the donuts

**Files:**
- Modify: `his_crm_pipeline/static/src/dashboard/dashboard.xml`
- Modify: `his_crm_pipeline/static/src/dashboard/dashboard.js`
- Modify: `his_crm_pipeline/static/src/dashboard/dashboard.scss`

**Interfaces:**
- Consumes: the `donuts` key from Task 7.
- Produces: `HisDashboard.gradientDonut(donut)` returning a CSS `conic-gradient(...)` string.

- [ ] **Step 1: Add the gradient builder to the component**

In `his_crm_pipeline/static/src/dashboard/dashboard.js`, add near the other helpers, after `largeurMarche`:

```javascript
    /**
     * Le donut, en une declaration CSS.
     *
     * conic-gradient plutot qu'une bibliotheque de graphiques : ces quatre
     * donuts sont des INSTANTANES, pas des series temporelles. Le README du
     * module a deja tranche contre Chart.js pour cette raison, et une
     * dependance pour dessiner quatre camemberts statiques serait une facon
     * couteuse de perdre un argument deja gagne. Le jour ou une courbe dans le
     * temps est demandee, une bibliotheque devient justifiee.
     *
     * La palette suit l'index de couleur d'Odoo, comme les etiquettes : le
     * theme decide du rendu, rien n'est fixe en dur ici. C'est ce qui permet a
     * la passe visuelle a venir de ne toucher qu'aux jetons.
     */
    gradientDonut(donut) {
        if (!donut.total) {
            return "conic-gradient(var(--his-donut-vide, #e9ecef) 0 100%)";
        }
        const parts = [];
        let angle = 0;
        donut.segments.forEach((segment, index) => {
            const fin = angle + (segment.count / donut.total) * 100;
            parts.push(`var(--his-donut-${index % 8}) ${angle}% ${fin}%`);
            angle = fin;
        });
        return `conic-gradient(${parts.join(", ")})`;
    }

    /** La couleur d'une part, pour sa pastille de legende. */
    couleurSegment(index) {
        return `var(--his-donut-${index % 8})`;
    }
```

- [ ] **Step 2: Add the template block**

In `his_crm_pipeline/static/src/dashboard/dashboard.xml`, insert after the *Entonnoir* block and before the *A traiter* block:

```xml
                <!-- =========================== Repartitions ========================
                     Des instantanes, pas des series : un conic-gradient suffit,
                     et evite d'ajouter une bibliotheque pour quatre camemberts
                     statiques. Chaque part est cliquable, comme chaque tuile. -->
                <div t-if="state.spec.donuts and state.spec.donuts.length" class="his_bloc">
                    <h3 class="his_titre">Repartitions</h3>
                    <div class="his_donuts">
                        <div t-foreach="state.spec.donuts" t-as="donut"
                             t-key="donut.label" class="his_donut">
                            <div class="his_donut_titre" t-esc="donut.label"/>
                            <div t-if="!donut.total" class="his_donut_vide text-muted small">
                                Aucune donnee sur la periode
                            </div>
                            <div t-else="" class="his_donut_corps">
                                <div class="his_donut_disque"
                                     t-attf-style="background: {{ gradientDonut(donut) }}">
                                    <div class="his_donut_trou">
                                        <span t-esc="donut.total"/>
                                    </div>
                                </div>
                                <ul class="his_donut_legende">
                                    <li t-foreach="donut.segments" t-as="segment"
                                        t-key="segment.label"
                                        class="his_cliquable"
                                        t-on-click="() => this.ouvrir(segment.action)">
                                        <span class="his_pastille"
                                              t-attf-style="background: {{ couleurSegment(segment_index) }}"/>
                                        <span class="his_legende_nom" t-esc="segment.label"/>
                                        <span class="his_legende_compte" t-esc="segment.count"/>
                                        <span class="his_legende_part">
                                            <t t-esc="segment.pourcentage"/>%
                                        </span>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
```

- [ ] **Step 3: Add the styles**

Append to `his_crm_pipeline/static/src/dashboard/dashboard.scss`:

```scss
// ============================== Repartitions ==============================
// Huit couleurs, definies en variables et non en dur : la passe visuelle a
// venir ne doit toucher qu'ici. Les valeurs de depart sont la palette d'Odoo,
// pour que le cockpit ne detonne pas avant meme d'etre theme.
.o_his_dashboard {
    --his-donut-0: #2b7cd3;
    --his-donut-1: #00acc0;
    --his-donut-2: #7c5dc7;
    --his-donut-3: #4aa8e0;
    --his-donut-4: #17a2b8;
    --his-donut-5: #6f42c1;
    --his-donut-6: #5bc0de;
    --his-donut-7: #9b8ad4;
    --his-donut-vide: #e9ecef;
}

.his_donuts {
    display: grid;
    // Deux par ligne sur un ecran de bureau, une seule sur mobile, sans
    // media query : l'equipe est majoritairement au bureau, parfois sur
    // telephone.
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 1rem;
}

.his_donut_corps {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.his_donut_disque {
    position: relative;
    flex: 0 0 auto;
    width: 120px;
    height: 120px;
    border-radius: 50%;
}

.his_donut_trou {
    position: absolute;
    inset: 22%;
    border-radius: 50%;
    background: var(--his-donut-fond, #fff);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
}

.his_donut_legende {
    list-style: none;
    margin: 0;
    padding: 0;
    flex: 1 1 auto;
    font-size: 0.85rem;

    li {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.1rem 0;
    }
}

.his_pastille {
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 2px;
    flex: 0 0 auto;
}

.his_legende_nom {
    flex: 1 1 auto;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.his_legende_compte { font-weight: 600; }
.his_legende_part { opacity: 0.6; min-width: 3.2em; text-align: right; }
```

> **Do not write `min()` or `max()` with mixed units in this file.** SCSS evaluates them at compile time and refuses mixed units; `min(62vmin, 620px)` once collapsed the entire backend bundle from 1,092,975 bytes to 29,941 with a clean upgrade log. If one is ever needed, wrap it as `#{"min(62vmin, 620px)"}`.

- [ ] **Step 4: Restart and confirm the bundle did not collapse**

```bash
docker compose restart odoo
docker compose logs --tail=40 odoo
```

Then confirm the asset bundle is a plausible size rather than a stub — a silently broken SCSS rule produces a valid but nearly empty bundle:

```bash
curl -s -o /dev/null -w "%{size_download}\n" \
  "http://localhost:8069/web/assets/any/web.assets_backend.css"
```

Expected: a size in the hundreds of kilobytes or more. A five-figure number means the bundle collapsed — find the offending rule before continuing.

- [ ] **Step 5: Render the cockpit and read the screenshot**

```bash
"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless --disable-gpu --window-size=1600,1200 \
  --screenshot=/tmp/cockpit.png "http://localhost:8069/odoo/action-his_crm_pipeline.action_dashboard_admissions"
```

**Look at the image.** Confirm: four donuts render as rings and not as solid discs (the hole must be visible); adjacent segments are distinguishable in colour; long lost-reason labels truncate with an ellipsis rather than breaking the layout; the centre total is legible against the hole's background; and a donut with no data shows the empty message rather than a black circle.

If two adjacent segments are hard to tell apart, reorder the palette variables so neighbouring indices contrast — do not add more colours.

- [ ] **Step 6: Commit**

```bash
git add his_crm_pipeline/static/src/dashboard/
git commit -m "[ADD] Les repartitions se lisent en camembert, sans bibliotheque

conic-gradient : ces quatre donuts sont des instantanes, pas des series
temporelles. Le README avait deja tranche contre Chart.js pour cette
raison ; une dependance pour dessiner quatre camemberts statiques serait
une facon couteuse de perdre un argument deja gagne.

Huit couleurs en variables et non en dur : la passe visuelle a venir ne
touchera qu'a ces jetons.

Chaque part de legende est cliquable et ouvre exactement ce qu'elle
compte.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 9: The data-quality queue

GoHighLevel's best idea, and the mechanism already exists here.

**Files:**
- Modify: `his_crm_pipeline/models/his_dashboard.py`
- Test: `his_crm_pipeline/tests/test_dashboard.py`

**Interfaces:**
- Consumes: `_a_traiter()` (existing).
- Produces: a `qualite` key in `get_admissions`'s return dict. Task 10 appends one entry to it.

- [ ] **Step 1: Write the failing test**

```python
    def test_la_file_qualite_signale_ce_qui_manque(self):
        """Le panneau « Fix your forecast data » de GHL, avec la mecanique
        qui existe deja : _a_traiter rend un libelle, un compte, un apercu et
        une action. C'est le meme objet."""
        lead = self.env['crm.lead'].create({
            'name': "Candidat sans rien",
            'team_id': self.env.ref('his_crm_pipeline.crm_team_ventes').id,
        })
        spec = self.env['his.dashboard'].get_admissions('2020-01-01', '2100-01-01')

        self.assertIn('qualite', spec)
        libelles = [f['label'] for f in spec['qualite']]
        self.assertIn("Sans telephone ni email", libelles)

        sans_contact = next(
            f for f in spec['qualite'] if f['label'] == "Sans telephone ni email"
        )
        self.assertGreaterEqual(sans_contact['count'], 1)
        self.assertIn(lead.id, [l['id'] for l in sans_contact['apercu']])
```

- [ ] **Step 2: Run to verify it fails**

Expected: FAIL — `KeyError: 'qualite'`.

- [ ] **Step 3: Write the implementation**

Add to `his_crm_pipeline/models/his_dashboard.py`, after `_admissions_donuts`:

```python
    def _admissions_qualite(self, equipes):
        """Ce qui manque, et qu'on peut aller corriger.

        C'est la meilleure idee du cockpit GoHighLevel — son panneau « Fix your
        forecast data » — et la mecanique existe deja ici : _a_traiter rend un
        libelle, un compte, un apercu de cinq lignes et une action. C'est
        exactement le meme objet, donc trois appels et rien de plus.

        C'est aussi ce qui rend les autres chiffres de l'ecran dignes de
        confiance : un tableau de bord qui ne dit pas ce qu'il ignore laisse
        croire qu'il sait tout.

        Pas de « date de cloture manquante » ici, contrairement a GHL, ou les
        505 opportunites ouvertes en manquent toutes : signaler un champ que
        personne ne remplit et que rien n'utilise ne serait pas de la qualite
        de donnee, seulement du bruit.
        """
        base = [('team_id', 'in', equipes.ids)]
        files = [
            self._a_traiter(
                "Sans telephone ni email", 'crm.lead',
                base + [('phone', '=', False), ('email_from', '=', False)],
            ),
            self._a_traiter(
                "Sans specialite visee", 'crm.lead',
                base + [('specialite_id', '=', False)],
            ) if 'specialite_id' in self.env['crm.lead']._fields else None,
            self._a_traiter(
                "Sans source d'acquisition", 'crm.lead',
                base + [('source_id', '=', False)],
            ),
        ]
        # specialite_id vient de his_admission, qui est en aval : le pipeline
        # doit rester installable seul.
        return [file for file in files if file]
```

Add the key to `get_admissions`'s return dict:

```python
            'qualite': self._admissions_qualite(equipes),
```

- [ ] **Step 4: Render the block in the template**

In `dashboard.xml`, after the *Repartitions* block:

```xml
                <!-- ========================= Qualite des donnees ====================
                     Ce qui manque, et qu'on peut aller corriger. C'est ce qui
                     rend les autres chiffres de l'ecran dignes de confiance :
                     un tableau de bord qui ne dit pas ce qu'il ignore laisse
                     croire qu'il sait tout. Meme mecanique que « A traiter ». -->
                <div t-if="state.spec.qualite and state.spec.qualite.length" class="his_bloc">
                    <h3 class="his_titre">Qualite des donnees</h3>
                    <div class="his_files">
                        <div t-foreach="state.spec.qualite" t-as="file"
                             t-key="file.label" class="his_file">
                            <div class="his_file_entete his_cliquable"
                                 t-on-click="() => this.ouvrir(file.action)">
                                <span t-esc="file.label"/>
                                <span class="his_badge"
                                      t-att-class="{ 'his_badge_vide': !file.count }"
                                      t-esc="file.count"/>
                            </div>
                            <ul class="his_file_apercu">
                                <li t-foreach="file.apercu" t-as="ligne"
                                    t-key="ligne.id" t-esc="ligne.nom"/>
                            </ul>
                        </div>
                    </div>
                </div>
```

- [ ] **Step 5: Run the tests, restart, render, read the screenshot**

Run the test command (expected: PASS), then `docker compose restart odoo`, then screenshot the cockpit as in Task 8 Step 5 and confirm the new block sits below the donuts and reuses the existing `his_file` styling without a visual seam.

- [ ] **Step 6: Commit**

```bash
git add his_crm_pipeline/models/his_dashboard.py his_crm_pipeline/static/src/dashboard/dashboard.xml his_crm_pipeline/tests/test_dashboard.py
git commit -m "[ADD] Qualite des donnees : ce que le cockpit ignore, il le dit

La meilleure idee du tableau de bord GoHighLevel, et la mecanique
existait deja : _a_traiter rend un libelle, un compte, un apercu et une
action. Trois appels, rien de plus.

C'est ce qui rend les autres chiffres dignes de confiance. Un tableau de
bord qui ne dit pas ce qu'il ignore laisse croire qu'il sait tout.

Pas de « date de cloture manquante » comme chez GHL, ou les 505
opportunites ouvertes en manquent toutes : signaler un champ que personne
ne remplit et que rien n'utilise n'est pas de la qualite, c'est du bruit.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 10: Revenue, derived from a tariff

**Files:**
- Create: `his_admission/models/his_tarif.py`
- Create: `his_admission/views/his_tarif_views.xml`
- Modify: `his_admission/models/__init__.py`, `his_admission/__manifest__.py`, `his_admission/security/ir.model.access.csv`
- Modify: `his_admission/models/his_dashboard.py`
- Test: `his_admission/tests/test_admission.py`

**Interfaces:**
- Consumes: `his.specialite` (`cycle`, existing), `_tuile()` (existing).
- Produces: model `his.tarif` with fields `specialite_id`, `frais_inscription`, `frais_scolarite`, `active`; and `his.tarif._montant_pour(specialite)` returning a float.

> **This task ships with blank amounts and is not complete until Finance supplies the fee schedule.** The GHL cards show a uniform DA400,000, but whether that is the registration fee alone or the total, and whether Master differs from Licence, is unknown. The revenue block stays hidden while every tariff is zero — nothing ships pretending to know a price it does not.

- [ ] **Step 1: Write the failing test**

Append to `his_admission/tests/test_admission.py`:

```python
    def test_sans_tarif_le_cockpit_ne_montre_aucun_montant(self):
        """Un chiffre d'affaires invente est pire qu'un chiffre absent : il se
        cite en reunion. Tant que la grille est vide, le bloc n'existe pas."""
        self.env['his.tarif'].search([]).unlink()
        spec = self.env['his.dashboard'].get_dossiers('2020-01-01', '2100-01-01')
        cles = [t['cle'] for t in spec['tiles']]
        self.assertNotIn('revenu_attendu', cles)

    def test_avec_un_tarif_le_revenu_se_deduit(self):
        """Deduit, jamais saisi. C'est la difference avec GoHighLevel, ou 454
        opportunites sur 505 n'ont aucun montant parce qu'il fallait le taper."""
        specialite = self.env.ref('his_admission.spec_info_systemes')
        self.env['his.tarif'].create({
            'specialite_id': specialite.id,
            'frais_inscription': 400000.0,
        })
        self.env['crm.lead'].create({
            'name': "Candidat chiffrable",
            'team_id': self.env.ref('his_crm_pipeline.crm_team_ventes').id,
            'specialite_id': specialite.id,
        })

        spec = self.env['his.dashboard'].get_dossiers('2020-01-01', '2100-01-01')
        tuile = next(t for t in spec['tiles'] if t['cle'] == 'revenu_attendu')
        self.assertEqual(tuile['valeur'], 400000.0)

    def test_un_seul_tarif_actif_par_specialite(self):
        """Deux tarifs actifs pour la meme specialite donneraient deux revenus
        possibles, et le cockpit choisirait au hasard."""
        specialite = self.env.ref('his_admission.spec_info_systemes')
        self.env['his.tarif'].create({
            'specialite_id': specialite.id, 'frais_inscription': 400000.0,
        })
        with self.assertRaises(ValidationError):
            self.env['his.tarif'].create({
                'specialite_id': specialite.id, 'frais_inscription': 450000.0,
            })
```

- [ ] **Step 2: Run to verify it fails**

Expected: FAIL — `KeyError: 'his.tarif'`.

- [ ] **Step 3: Create the model**

`his_admission/models/his_tarif.py`:

```python
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""La grille tarifaire, pour le REPORTING et rien d'autre.

Ce modele ne facture pas, ne comptabilise pas et ne touche aucun modele
`account`. Il existe pour qu'un chiffre d'affaires attendu puisse etre DEDUIT
au lieu d'etre saisi.

C'est la lecon des donnees de GoHighLevel : 454 opportunites ouvertes sur 505
n'y portent aucun montant, parce qu'il fallait le taper a la main sur chaque
fiche. Un tarif se lit dans une grille — l'etablissement en a une — et un
chiffre deduit ne peut pas etre vide.

his_engagement garde ses booleens paye / non paye. Le jour ou les montants
comptent vraiment, c'est un chantier `account` ; ce fichier ne l'ouvre pas.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HisTarif(models.Model):
    _name = 'his.tarif'
    _description = "Tarif par specialite"
    _order = 'specialite_id'

    specialite_id = fields.Many2one(
        'his.specialite', string="Specialite", required=True,
        ondelete='cascade',
    )
    # Related et non recopie : le cycle vit sur la specialite, qui le porte
    # deja en champ requis. Le dupliquer donnerait deux verites.
    cycle = fields.Selection(
        related='specialite_id.cycle', string="Cycle", store=True, readonly=True,
    )
    frais_inscription = fields.Float(
        string="Frais d'inscription", digits=(12, 2),
        help="Les frais non remboursables. C'est leur encaissement qui gagne "
             "le lead.",
    )
    frais_scolarite = fields.Float(
        string="Frais de scolarite", digits=(12, 2),
    )
    active = fields.Boolean(default=True)

    @api.constrains('specialite_id', 'active')
    def _check_un_seul_tarif_actif(self):
        """Deux tarifs actifs pour la meme specialite donneraient deux revenus
        possibles, et le cockpit en choisirait un au hasard. Desactiver
        l'ancien plutot que le supprimer garde l'historique lisible."""
        for tarif in self:
            if not tarif.active:
                continue
            if self.search_count([
                ('specialite_id', '=', tarif.specialite_id.id),
                ('active', '=', True),
                ('id', '!=', tarif.id),
            ]):
                raise ValidationError(_(
                    "Un tarif actif existe deja pour « %(spec)s ». "
                    "Desactivez-le avant d'en creer un nouveau.",
                    spec=tarif.specialite_id.display_name,
                ))

    @api.model
    def _montant_pour(self, specialite):
        """Les frais d'inscription de cette specialite, ou 0.

        Zero et non une exception : une specialite non tarifee est une lacune
        de la grille, signalee par la file « Qualite des donnees ». Elle ne doit
        pas faire tomber le cockpit du directeur.
        """
        if not specialite:
            return 0.0
        tarif = self.search([('specialite_id', '=', specialite.id)], limit=1)
        return tarif.frais_inscription or 0.0
```

Register it in `his_admission/models/__init__.py`:

```python
from . import his_tarif
```

- [ ] **Step 4: Add access rights and the view**

Append to `his_admission/security/ir.model.access.csv` — read for everyone who opens a cockpit, write reserved to Direction, matching the module's existing pattern:

```csv
access_his_tarif_read,his.tarif read,model_his_tarif,base.group_user,1,0,0,0
access_his_tarif_admin,his.tarif admin,model_his_tarif,sales_team.group_sale_manager,1,1,1,1
```

Create `his_admission/views/his_tarif_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="view_his_tarif_list" model="ir.ui.view">
        <field name="name">his.tarif.list</field>
        <field name="model">his.tarif</field>
        <field name="arch" type="xml">
            <list string="Tarifs" editable="bottom">
                <field name="specialite_id"/>
                <field name="cycle"/>
                <field name="frais_inscription"/>
                <field name="frais_scolarite"/>
                <field name="active" column_invisible="1"/>
            </list>
        </field>
    </record>

    <record id="action_his_tarif" model="ir.actions.act_window">
        <field name="name">Tarifs</field>
        <field name="res_model">his.tarif</field>
        <field name="view_mode">list</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">Aucun tarif enregistre.</p>
            <p>Tant que cette grille est vide, le cockpit n'affiche aucun chiffre
               d'affaires : un montant invente se cite en reunion.</p>
        </field>
    </record>

</odoo>
```

Add both to `his_admission/__manifest__.py` `'data'` (after the existing config views) and bump `'version'` to `19.0.1.5.0`.

- [ ] **Step 5: Add the derived tile**

In `his_admission/models/his_dashboard.py`, inside `get_dossiers`, after the existing tiles are built:

```python
        # Le revenu attendu, DEDUIT et jamais saisi.
        #
        # Chez GoHighLevel, 454 opportunites ouvertes sur 505 n'ont aucun
        # montant : c'est la consequence directe d'avoir demande a un humain de
        # taper un nombre qu'une grille connait deja. Ici il se calcule, donc
        # il ne peut pas etre vide.
        #
        # La tuile n'apparait PAS tant qu'aucun tarif n'est saisi. Un chiffre
        # d'affaires invente est pire qu'un chiffre absent : il se cite en
        # reunion.
        Tarif = self.env['his.tarif']
        if Tarif.sudo().search_count([('frais_inscription', '>', 0)]):
            equipes = self._equipes_admissions()
            ouverts = self.env['crm.lead'].search([
                ('team_id', 'in', equipes.ids),
                ('active', '=', True),
                ('specialite_id', '!=', False),
            ])
            attendu = sum(
                Tarif.sudo()._montant_pour(lead.specialite_id)
                for lead in ouverts
            )
            tuiles.append(self._tuile(
                'revenu_attendu', "Revenu attendu", attendu, unite="DA",
                action=self._action(
                    "Candidatures ouvertes chiffrables", 'crm.lead',
                    [('team_id', 'in', equipes.ids),
                     ('active', '=', True),
                     ('specialite_id', '!=', False)],
                ),
            ))
```

- [ ] **Step 6: Add the untariffed-specialty entry to the quality queue**

In `his_crm_pipeline/models/his_dashboard.py`'s `_admissions_qualite`, this belongs downstream — add it instead in `his_admission/models/his_dashboard.py` by overriding:

```python
    def _admissions_qualite(self, equipes):
        """Ajoute la lacune que seul ce module peut voir : une specialite sans
        tarif rend une candidature non chiffrable, donc absente du revenu
        attendu sans que rien ne le dise."""
        files = super()._admissions_qualite(equipes)
        sans_tarif = self.env['his.specialite'].search([]).filtered(
            lambda s: not self.env['his.tarif'].sudo().search_count([
                ('specialite_id', '=', s.id), ('frais_inscription', '>', 0),
            ])
        )
        if sans_tarif:
            files.append(self._a_traiter(
                "Specialites sans tarif", 'his.specialite',
                [('id', 'in', sans_tarif.ids)],
            ))
        return files
```

- [ ] **Step 7: Run the tests**

```bash
docker compose stop odoo
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' docker compose run --rm odoo odoo \
  -d his_test --without-demo=all -u his_admission \
  --test-enable --test-tags /his_admission --stop-after-init
```

Expected: PASS, three tests. Then re-run the `/his_crm_pipeline` suite to confirm nothing upstream regressed.

- [ ] **Step 8: Render the cockpit and read the screenshot**

Confirm by eye: with an empty tariff grid the revenue tile is absent and *Spécialités sans tarif* appears in the quality queue; with one tariff filled, the tile appears and its amount matches the count of chargeable open leads times the fee.

- [ ] **Step 9: Commit**

```bash
git add his_admission/
git commit -m "[ADD] Le revenu attendu se deduit d'une grille, il ne se saisit pas

454 opportunites ouvertes sur 505 n'ont aucun montant dans GoHighLevel.
C'est la consequence directe d'avoir demande a un humain de taper un
nombre qu'une grille tarifaire connait deja. Deduit, le chiffre ne peut
pas etre vide.

his.tarif est une reference de REPORTING : il ne facture rien, ne
comptabilise rien et ne touche aucun modele account. his.engagement garde
ses booleens paye / non paye.

La tuile n'apparait pas tant que la grille est vide, et les specialites
sans tarif remontent dans la file « Qualite des donnees ». Un chiffre
d'affaires invente est pire qu'un chiffre absent : il se cite en reunion.

MONTANTS A OBTENIR DE LA FINANCE avant mise en service.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 11: Documentation

**Files:**
- Modify: `his_crm_pipeline/README.md`
- Modify: `his_admission/README.md`
- Modify: `README.md` (root, the module table)

**Interfaces:** consumes everything; produces nothing.

- [ ] **Step 1: Update `his_crm_pipeline/README.md`**

Three edits, each replacing a claim the code has now outgrown:

1. Add a section **"La boucle d'appel"** after *Relance SLA premier contact*, covering the three fields, the two buttons, the single-reschedule rule, and the explicit refusal to auto-lose after N attempts.
2. Add a section **"Les motifs de perte"** covering the merge of GHL's vocabulary, the dropped *Unknown*, the *Autre* valve, and the server constraint.
3. In **"Hors périmètre (assumé)"**, replace the Chart.js bullet — the donuts now exist and are drawn with `conic-gradient`; the reasoning (snapshots, not time series) still holds and should be restated, not deleted. Also update the *Capture UTM* bullet to note that the n8n workflow now fills `source_id` / `medium_id` / `campaign_id`.

- [ ] **Step 2: Update `his_admission/README.md`**

Add a section on `his.tarif`: reporting only, no `account` coupling, one active tariff per specialty, and the standing dependency on Finance for the real amounts.

- [ ] **Step 3: Update the root `README.md` module table**

Bump the test counts in the `his_crm_pipeline` and `his_admission` rows to the numbers the suites actually report — read them from the test output, do not estimate.

- [ ] **Step 4: Commit**

```bash
git add README.md his_crm_pipeline/README.md his_admission/README.md
git commit -m "[DOC] La boucle d'appel, les motifs de perte et la grille tarifaire

Chaque module documente ses regles et ses ecarts assumes. Trois
paragraphes du README du pipeline avaient ete rendus faux par le code :
Chart.js reste ecarte mais les repartitions existent desormais, dessinees
en conic-gradient pour la raison deja donnee — ce sont des instantanes.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Self-review

**Spec coverage.** §4.1 call loop → Task 2. §4.2 no custom widget → Task 3 Step 3. §4.3 phone and WhatsApp → Task 1. §4.4 card content → Task 3. §5.1 taxonomy → Task 4. §5.2 honesty valve → Tasks 4 and 5. §5.3 the lock → Task 5. §5.4 speed → Task 6, and the two verification steps for the wizard's API live in Tasks 4 Step 1 and 6 Step 4. §6.1 donuts → Tasks 7 and 8. §6.2 data-quality queue → Task 9. §6.3 at-risk deliberately not built → no task, by design, restated in Task 9's docstring. §6.4 derived revenue → Task 10. §7 findings → recorded in the spec, no code. §9 testing → every task ends with a run, and every UI task with a rendered screenshot.

**Type consistency.** `tentatives_appel` (Integer) is defined in Task 2 and read in Tasks 3 and 6. `telephone_e164` / `whatsapp_url` (Char) defined in Task 1, rendered in Task 3. `_donut()` returns `{'label', 'total', 'segments'}` in Task 7 and is consumed under exactly those keys in Task 8. `_admissions_qualite(equipes)` is defined in Task 9 and overridden with the same signature in Task 10 Step 6. `_montant_pour(specialite)` defined and called in Task 10 only.

**Known unverified assumptions**, each with its own in-plan verification step rather than a guess: `phone_validation.phone_format`'s signature (Task 1 Step 1), the existence of `mail.mail_activity_data_call` (Task 2 Step 4), whether `crm.lost.reason` has `sequence` (Task 4 Step 1), and the lose wizard's model name and context keys (Task 6 Step 4). Docker was unavailable when this plan was written; none of these change the design's shape, only the exact identifiers.
