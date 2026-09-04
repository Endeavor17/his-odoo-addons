# CRM — GoHighLevel parity, adviser board and director cockpit

Design for the Admissions CRM of the Groupe HIS-HTC-IRA, replacing the working
surface the team has in GoHighLevel.

The governing idea, stated first:

> **Parity means the team stops needing GHL, not that Odoo redraws GHL's
> screens.** Where GHL's screen answers a real question, reproduce the answer.
> Where GHL's screen is empty — and the Forecast tab largely is — reproduce the
> question and answer it from data Odoo already holds.

---

## 1. Scope and decomposition

Reproducing "the GHL experience" is not one project. It is three, and they share
no state:

| | Sub-project | Depends on | Status |
|---|---|---|---|
| A | Ingestion — n8n captures the web form + UTM into `crm.lead` | nothing | **parked**, workflow already drafted |
| B | Adviser board + director cockpit | nothing | **this spec** |
| C | Visual theming (colours, spacing) | real screenshots | later, its own pass |

Sub-project A exists as a working n8n workflow (`Admission Workflow.json`:
dedupe, UTM find-or-create, specialty matching, server-score re-read, audit
note). It is deliberately untouched here. Nothing in this spec requires it, and
nothing here breaks it — the fields it writes are the fields it already writes.

This spec covers B, in three phases, in this order:

| Phase | Deliverable |
|---|---|
| 1 | The adviser board — the call loop, card actions, WhatsApp and phone links |
| 2 | The loss taxonomy — real reasons, and a loss that cannot be silent |
| 3 | The director cockpit — distribution donuts, data-quality queue, derived revenue |

Phase 1 first because it is the surface three people use for eight hours a day,
and because phases 2 and 3 both measure what phase 1 records. A dashboard built
before the board would be charting an absence.

## 2. What already exists

`his_crm_pipeline` is not a starting point, it is most of the destination. It
already carries: two team-separated pipelines, two kanban boards inheriting the
native view in `mode="primary"`, tags, per-action saved filters, a tightened
record rule, an hourly first-contact SLA cron, transition capability guards
(`crm_capacites.py`), and an OWL cockpit driven by a single server-side
indicator service (`his_dashboard.py`) where every KPI is defined exactly once.

`his_admission` adds the academic reference data and computes `score_academique`
server-side from the Direction's barème, keeping the browser-computed
`score_client` beside it for tamper comparison.

**This spec adds to that architecture; it does not restructure it.** Every new
number goes through `his.dashboard`. Every new server rule sits beside the two
constraints already there. No new model is introduced except the tariff table in
phase 3, which carries data that genuinely has nowhere else to live.

## 3. The problem, measured

The GHL account supplies the numbers that justify each phase.

**Leads die on the phone, not in file review.** GHL's recorded loss reasons are
Ghost Application (48), No Answer (43), Not Suitable (17), Expensive (15),
Unknown (13), No answer (13), Wrong number (12), Old BAC (12). All but two are
call outcomes. The four admission reasons this module ships today — *Dossier non
retenu*, *Dossier incomplet*, *Paiement non confirmé*, *Hors quota commercial* —
describe a lead dying late, at file review. **The shipped taxonomy does not
describe how candidates are actually lost.**

**Two thirds of losses say nothing.** 626 opportunities lost; 193 carry a
reason. The other 433 are unexplained. This is not carelessness: in Odoo today,
recording an outcome costs six interactions (open the lead, find the chatter,
type, schedule an activity, open the lose wizard, choose) and skipping it costs
none. **The fix is to make recording cheaper than skipping**, which is a
workflow change on the board, not a chart.

**The forecast is 90% empty.** 505 open opportunities; 505 missing a close date;
454 missing a value. GHL's `DA19,151,350.50` expected revenue is extrapolated
from the 51 records that carry a number. Its own "at-risk" tiles read 0/0/0
because risk is computed from close-date slippage and no record has a close
date. Rebuilding this screen faithfully would rebuild a fiction.

## 4. Phase 1 — the adviser board

### 4.1 The call loop

Advisers dial from their own mobile handsets while looking at a desktop screen.
Click-to-call is therefore worthless here — there is no softphone to invoke. The
valuable action is entirely in what happens *after* the call.

Three fields on `crm.lead`:

```
tentatives_appel      Integer, default 0   how many times we have tried
derniere_tentative    Datetime             when we last tried
prochain_rappel       Datetime             the scheduled callback
```

Three buttons, on both the kanban card and the form header — the same methods
reached from two surfaces, because the queue-working pass and the inside-a-lead
pass are different moments:

| Button | Effect |
|---|---|
| **Sans réponse** | `tentatives_appel += 1`, dated note in the chatter, callback rescheduled +1 day. Stage unchanged. |
| **Joint** | Advances to *Contact établi*, clears the callback, opens the form to record what was said. |
| **Perdu** | Native `action_set_lost`, reason list ordered by real frequency, pre-filled where the record already knows the answer (see §5.4). |

The counter is what makes *Candidature fantôme* a fact rather than a
recollection. After three unanswered attempts the card shows a `3 tentatives`
badge and the lose action defaults to that reason.

**No automatic loss after N attempts.** A machine deciding a candidate is gone is
the same class of automation the Direction already rejected for lead assignment,
where `crm.ir_cron_crm_lead_assign` is deliberately left inactive. The record
proposes; the adviser decides.

### 4.2 Implementation constraint: no custom widget

Card buttons use Odoo 19's native `<button type="object">` support inside the
kanban card. A hand-rolled OWL widget would be more code and would break at the
first upstream card restructure. The two kanban views already inherit the native
view in `mode="primary"` and already extend `o_his_lead_kanban_meta`; the action
row is added the same way, at the same anchor.

### 4.3 Phone and WhatsApp

One computed field, `telephone_e164`, normalising Algerian input
(`0555…`, `+213555…`, `00213555…`) to E.164 via the **`phone_validation`**
module — Community, already available, and what Odoo itself uses. Writing a
regex for this would be reimplementing a dependency that is already installed.

From it, two links on the card:

- `tel:` — near-useless on desktop, correct on mobile, costs one attribute
- `wa.me/<number>?text=<greeting>` — the one they will actually press

**These are deep links, not an integration.** They open WhatsApp Web or the
desktop app with the number and a template message ready. There is no inbound
message, no thread in Odoo, no delivery status. This is a genuine loss against
GHL's Conversations tab. Odoo 19 Community offers no honest alternative:
telephony does not exist, SMS is a paid IAP service, WhatsApp is Enterprise. The
loss is stated here rather than discovered later.

### 4.4 Card content

Name, score badge, specialty, source, phone, tags, adviser avatar, attempt
count, action row. Nothing the native card already renders is redeclared —
tags, avatar, activities, priority and rotting stay as the stock card draws
them, per the rule the module's README already states.

Desktop-first, but every action reachable without hover and every tap target
usable: the team is mostly desktop, sometimes mobile, and `web_responsive` is
already vendored.

## 5. Phase 2 — a loss that says something

### 5.1 The merged taxonomy

Their vocabulary, cleaned. Six new call-outcome reasons:

| New reason | From GHL | Note |
|---|---|---|
| Candidature fantôme | Ghost Application (48) | submitted the form, never reachable |
| Sans réponse | No Answer (43) + No answer (13) | **the duplicate merges** — 56, the real leader |
| Numéro erroné | Wrong number (12) | |
| BAC trop ancien | Old BAC (12) | |
| Frais trop élevés | Expensive (15) | |
| Profil non adapté | Not suitable (17) | |

The five existing reasons are kept untouched. `crm.lost.reason` is
`ondelete='restrict'` and the data file is `noupdate="1"`: nothing is deleted,
nothing already in use can break, and a team that renames one keeps its change
across deliveries.

Once the duplicate merges, **104 of 193 explained losses are "never reached by
phone"** — over half. Phases 1 and 2 are the same problem seen twice.

### 5.2 Dropping "Unknown", and the honesty valve

*Unknown* (13) records nothing and is not carried over. But a mandatory field
with no honest escape does not produce better data — it produces confident lies.
An adviser who genuinely does not know will pick whatever is nearest the cursor,
and that reason is worse than a blank because it is indistinguishable from a
real one.

**"Autre — à préciser"** therefore stays, and choosing it requires typing a line.
A reason nobody can dodge needs a door marked *I don't know*, or they climb out
the window.

### 5.3 The lock

One `@api.constrains` on `crm.lead`: a lead being lost must carry
`lost_reason_id`. Server-side, not a view rule — the kanban, an import and the
API all route through `write()`, so one guard covers every caller instead of one
guard per button. It sits beside `_check_livrables_approuves` and
`_check_gagne_seulement_si_encaisse` as `_check_perte_motivee`, following a
pattern the module has already applied twice.

Applied to **both** pipelines. Branching by team would be more code for no
benefit: the content pipeline's only loss is *Retour production nécessaire*,
which it already records.

**No backfill required.** The README is explicit that GHL history is not
imported (*"départ à neuf, aucun historique repris"*), so no reason-less lost
lead exists in Odoo for the constraint to trip over. Should that ever change,
the migration must stamp the old records first, or editing an imported lead
becomes impossible.

### 5.4 Speed, or the constraint backfires

A mandatory reason adds a step. If that step is expensive, advisers stop losing
leads at all and the pipeline fills with corpses — a worse failure than the one
being fixed. Two mitigations:

- the lose action pre-selects *Candidature fantôme* when `tentatives_appel >= 3`;
  the record already knows, so it does not ask
- reasons are ordered by observed frequency, not alphabetically, so the top three
  cover roughly 70% of cases

**To verify before implementing** (Docker was unavailable at design time, so
these are reasoned from knowledge of Odoo rather than read from source):
whether the stock lose wizard already requires a reason (believed **not** —
`lost_reason_id` is an ordinary optional `Many2one`), and whether
`crm.lost.reason` carries a `sequence` field for ordering (believed **not**; if
absent it is three lines to add). Neither changes the design's shape.

## 6. Phase 3 — the director cockpit

### 6.1 Distribution donuts

Four: lead-score distribution, opportunity status, lost reasons, source and
channel. Each is one `_read_group` on a column that already exists and is
already indexed. They join `his.dashboard`'s response as a `donuts` key beside
`tiles` and `funnel`; the OWL component grows one block. **No new mechanism, no
new model, and no second definition of any KPI** — the one-definition rule in
`his_dashboard.py` is the reason four cockpits share one component, and it holds
here.

Drawn with **CSS `conic-gradient`**, not a charting library. The README parked
Chart.js on the grounds that these are snapshots rather than time series, and
that is still true: a donut is one `background` declaration and a legend is a
`<ul>`. Adding a dependency to draw four static pies would be an expensive way
to lose an argument the module already settled. A real time series is when a
library earns its place.

Every segment is clickable, via the `_action()` helper that already exists — the
cockpit's existing rule is that a number one cannot open must be believed on
faith.

### 6.2 The data-quality queue

GHL's "Fix your forecast data" panel is its best idea, and Odoo already has the
mechanism. `_a_traiter()` returns a label, a count, a five-row preview and an
action — structurally identical. The panel is three additional calls to a helper
that exists.

This is the cheapest item in the spec and probably the most valuable: it is what
makes every other number on the screen trustworthy.

### 6.3 "At-risk opportunities" — deliberately not built

GHL ranks deals by how many times their close date has slipped. Nothing in this
system has a close date; GHL's own panel reports all 505 open opportunities
missing one, and its three risk tiles read 0/0/0. It is an empty widget.

Rebuilding it would mean inventing a close-date discipline for advisers purely to
feed a chart. The honest substitute already ships: **`is_rotting`**, native to
Odoo 19 via `mail.tracking.duration.mixin`, already wired into
`_admissions_a_traiter()` as *Candidatures en sommeil*. Same question — which of
these is dying? — answered from data the server maintains itself, with nothing
for anyone to key in.

### 6.4 Revenue, derived not typed

`his_engagement.py:133` states the current position plainly:

> *Payé / non payé seulement, comme le classeur. Aucun montant, aucun raccord
> comptable. Le jour où les montants comptent, c'est un chantier account.*

That day has come for reporting, and only for reporting. The decision taken is
to **derive revenue from a tariff reference, never to type it per lead.**

A small model, `his.tarif`, keyed on specialty and cycle, carrying the
registration fee and the tuition fee. Expected revenue on the cockpit is then
open leads multiplied by their tariff — computed, and **structurally incapable of
being blank.** This is not merely parity with GHL, it is strictly better: GHL's
454-of-505 empty values are the direct consequence of asking a human to type a
number that a price list already knows.

Boundaries, so this does not become an accounting project:

- `his.tarif` is a **reference for reporting**. It posts nothing, invoices
  nothing, and touches no `account` model. `frais_inscription_payes` stays the
  boolean it is, and it remains what wins the lead.
- No `expected_revenue` is written onto `crm.lead`. One derived figure on the
  cockpit, not a money field advisers can edit into disagreeing with the price
  list.

**Open dependency: the fee schedule is not yet known.** The GHL cards show a
uniform DA400,000, but whether that is the registration fee or the total, and
whether Licence and Master differ, requires Finance. The model ships with its
seed values **blank and marked**, and the cockpit shows the revenue block only
once tariffs exist. Nothing ships pretending to know a price it does not.

## 7. Findings to report, not to fix

Recorded here because the ingestion brief lists them as open, and two are now
answered:

1. **How Odoo distinguishes Licence from Master — answered.**
   `his.specialite.cycle` is a required `Selection('licence','master')` and the
   seed data sets it per specialty. No new mechanism is needed. **But** the
   Master web form submits free-text `master_field` rather than a specialty, so
   the n8n Master branch has nothing to match against. That is a phase-A problem.
2. **Whether the academic score accepts null — answered, and the answer is not
   the one the brief expects.** `score_academique` is redefined by
   `his_admission` as a **stored computed** field, read-only, derived from
   `bac_moyenne`. It is not writable at all, so the null-versus-zero choice does
   not arise as posed: a Master lead with no BAC data computes to `0`, with
   `score_detail` reading *"Moyenne du BAC non renseignée."* The distinction
   between "unscored" and "scored zero" is therefore carried by `score_detail`,
   not by the integer. **Sorting the assignment queue by score will still sink
   every Master applicant to the bottom.** This needs a decision and is out of
   scope here.
3. **The Master form's consent checkbox** carries no `name` attribute and is not
   a real GHL field, so consent is likely not recorded in GHL at all. Reported,
   not fixed, per the brief.
4. **Duplicate lost reasons in GHL** (*No Answer* / *No answer*, plus *Unknown*)
   are resolved on the way over rather than carried across — see §5.1.

## 8. Out of scope

- **Sub-project A (n8n ingestion)** — parked, drafted, untouched by this spec.
- **Sub-project C (visual theme)** — colours and spacing await a separate pass.
- **Inbound WhatsApp, SMS, telephony** — impossible in Community without paid
  services; §4.3 states what is delivered instead.
- **Social Planner and Email Marketing** — GHL's marketing suite; no part of the
  CRM working surface.
- **Any `account` integration** — §6.4 draws the boundary.
- **`his.person` / `his.engagement` creation from this flow** — Assumption A1 is
  unresolved and stays that way.
- **Automatic loss after N call attempts** — §4.1.
- **Master-applicant scoring** — finding 2 above; a business decision, not a
  build.

## 9. Testing

Extending the existing files, no new test module.

| Phase | Checks |
|---|---|
| 1 | attempt counter increments and reschedules; *Joint* lands in the right stage; E.164 conversion handles the three Algerian formats; card renders (screenshot, read) |
| 2 | losing without a reason raises; with one passes; three-attempt pre-fill selects the right reason; *Autre* without a note raises |
| 3 | each donut's segments sum to the tile reporting the same population; revenue block absent while tariffs are blank; cockpit renders (screenshot, read) |

**A clean upgrade log is not verification.** Every real defect in this project so
far has been invisible to compilation. UI work is confirmed by rendering it and
reading the image, per the repository's standing practice.
