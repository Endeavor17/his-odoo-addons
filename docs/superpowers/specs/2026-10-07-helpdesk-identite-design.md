# Helpdesk on the Identity Register

Design for the first helpdesk of the Groupe HIS-HTC-IRA.

The governing idea, stated first:

> **A ticket is about a person, and the person lives in the register.** The
> helpdesk links a ticket to an existing `his.person`; it never creates one,
> never matches one by guesswork, and never stores identity data of its own.

---

## 1. Scope

| In version 1 | Out of version 1 (and why) |
|---|---|
| OCA `helpdesk_mgmt` vendored | Email intake: inbound mail for `his.edu.dz` goes to Mailgun, not Odoo |
| OCA `helpdesk_mgmt_crm` vendored (Admissions ticket → lead) | Student portal: students have no portal accounts |
| `his_helpdesk_identity_bridge`: ticket ↔ `his.person` | SLA, satisfaction rating, partner-response: need volume or email first |
| Four teams: Informatique, Scolarité, Admissions, Finance / Caisse | Building repairs: stay in `maintenance_university` |
| A « Guichet » channel for walk-in requests | Mass mailing: its own spec, next |

**Who opens tickets (decided by Mohamed, 2026-10-07):** staff only, from
Odoo. An agent opens a ticket for themselves, a colleague, or a student
standing at the counter.

## 2. Module architecture

Approach A (chosen): vendor OCA, put everything HIS-specific in one bridge.

```
helpdesk_mgmt                 OCA, vendored, untouched
    ^            ^
    |            |
helpdesk_mgmt_crm   his_person_core
    ^            ^
    |            |
his_helpdesk_identity_bridge  person link, access rule, teams, channel, French mail
```

- **Vendoring.** `helpdesk_mgmt` and `helpdesk_mgmt_crm` are copied from
  `OCA/helpdesk` branch `19.0`, commit `5f7f54c167e3fb3b2bf6c19271ab9519643e75f0`
  (2026-10-06), unmodified, with a `VENDOR.md` naming the commit and the
  procedure to refresh — the same route as `web_responsive`, for the same
  reason: deployment has no build step, so nothing can be pip-installed.
- **The bridge owns no matching logic** and emits no matricule, exactly like
  `his_crm_identity_bridge`. It depends on `helpdesk_mgmt_crm` (hence `crm`)
  and `his_person_core`. It does not depend on `his_crm_identity_bridge`; it
  writes `his_person_id` on the lead only if that field exists.

## 3. Ticket ↔ person

New field on `helpdesk.ticket`:

```
his_person_id   Many2one his.person, "Personne", stored, indexed
                compute  = partner_id.his_person_ids[:1]
                inverse  = partner_id := his_person_id.partner_id
```

- **The link is deterministic.** Every `his.person` delegates to exactly one
  `res.partner` (`_inherits`), so a partner either is a person's or is not.
  No score, no threshold, no confirmation step.
- **Picking a person** fills the contact. The person is searchable by name or
  matricule: `his_person_core` gains `_rec_names_search = ["name",
  "matricule_institutionnel"]` (today it searches by name only), a one-line
  change every person picker in the group benefits from.
- **Picking a contact** that belongs to a person fills the person. Both paths end in the same state.
- **A contact outside the register** (a supplier, a parent) is allowed; the
  person field stays empty.
- **The helpdesk never creates a person.** A student missing from the register
  is a register defect, fixed at its source (Google Sheets sync, admission),
  not papered over by a ticket.
- **Header of the ticket form:** matricule (`matricule_affiche`), person type,
  and the current engagement (latest `his.engagement` by `date_debut`).
  Read-only, related through `his_person_id`.
- **On the person form:** a « Tickets » smart button with a count, visible to
  helpdesk users only.

**Ticket → lead (Admissions).** `helpdesk_mgmt_crm`'s wizard builds the lead in
`_prepare_vals`. The bridge extends it to carry `his_person_id` when the lead
model has that field (`his_crm_identity_bridge` installed). The CRM bridge then
sees the person already set and does nothing — its existing guard.

## 4. Access

**Decided by Mohamed, 2026-10-07: every helpdesk agent may see students and
candidates.**

- Audit S-6 (`his_person_core.rule_partner_student_candidate_private`) hides
  students' and candidates' partners from `base.group_user`. Per its own rule,
  the bridge **re-opens** them with an `ir.rule` `(1, '=', 1)` on `res.partner`
  for `helpdesk_mgmt.group_helpdesk_user_own` (the lowest helpdesk role, which
  every agent holds). The S-6 rule itself is not touched.
- ACL: read on `his.person` and `his.engagement` for the same group, so the
  person picker and the header work. No write, create or unlink.
- Roles reach users through the existing mechanism: `hr.job.group_ids`
  (`his_access_base`). Agents get « User: Team tickets », team leads
  « Helpdesk Manager ». No new group is created.
- OCA grants `base.group_user` read on tickets, limited by its own rule to
  tickets where the user is the contact or a follower. Kept: a staff member
  can follow their own request. The Helpdesk menu itself requires a helpdesk
  role, so `his_access_base`'s « socle » test stays green. Its ACL test only
  inspects `his_*` modules, and the bridge adds no `base.group_user` ACL.

## 5. Data

All `noupdate="1"`, so production edits survive upgrades.

- **Teams:** Informatique, Scolarité, Admissions, Finance / Caisse. No members
  seeded: the admin assigns them.
- **Channel:** « Guichet » (walk-in), alongside OCA's Web / Email / Phone / Other.
- **Stages:** OCA's six, French through the vendored `fr.po`.
- **Closing email:** OCA mails the requester when a ticket reaches Done,
  Cancelled or Rejected. The bridge replaces the template body with a French
  one that says not to reply: replies would land at Mailgun and never reach
  Odoo. Whether this mail blocks the agent's request is checked in the plan
  (§8).

## 6. Error handling

- Inverse writes `partner_id`; if the picked person is archived, Odoo's
  standard domain on the field (`active = True`) prevents the pick.
- Changing the contact to one with no person clears `his_person_id` — the
  compute owns it; no stale link can survive.
- The lead hook checks `"his_person_id" in self.env["crm.lead"]._fields`
  before writing, so the bridge works with or without the CRM bridge.

## 7. Testing

In `his_helpdesk_identity_bridge/tests/`, `TransactionCase`, French names:

1. Picking a person sets the contact; picking a person's contact sets the person.
2. A contact with no person: ticket saves, person empty.
3. Switching contact from a person to a non-person clears the person.
4. An agent with only « User: Personal tickets » reads a student's partner and
   `his.person`; a user with no role still cannot (S-6 holds).
5. Ticket → lead carries the person when `his_crm_identity_bridge` is installed.
6. The ticket count on the person.
7. A person is found by its matricule in the ticket's person picker.

CI: add `helpdesk_mgmt,helpdesk_mgmt_crm,his_helpdesk_identity_bridge` to
`MODULES` in `.github/workflows/ci.yml`, which also runs OCA's own tests and
`his_access_base`'s policy suite against the installed helpdesk. UI checked by
rendering the ticket form and the person form, not by a clean compile.

## 8. Deployment and open points

- Production: `-i helpdesk_mgmt,helpdesk_mgmt_crm,his_helpdesk_identity_bridge`,
  then container `stop` + `start` (a redeploy does not reload Python).
- **To verify during implementation:** whether the closing email is sent
  synchronously in the request (it would slow the agent's stage change like
  invoices did). If so, apply the `mail_notify_force_send=False` + cron
  `_trigger()` pattern from `his_mail_async`.
- **To verify:** that French is the active language for agents in production;
  otherwise the vendored `fr.po` has no visible effect.
- **Later specs:** email intake (IMAP polling or Mailgun route) — which also
  unlocks the partner-response and rating add-ons — then mass mailing.

## 9. Addendum (2026-10-07): email intake

Decided by Mohamed after verifying on production that mail reaches Odoo: the
IMAP server on `test-support@his.edu.dz` receives internal and external mail.
He is having `catchall@`, `bounce@` and `support@` forwarded into that mailbox;
until then, the routes below are in place but receive nothing.

- **Address:** OCA's `help@` alias is renamed `support@`. An email to it
  becomes a ticket with no team (OCA's "tickets without team" list), channel
  Email.
- **Person link:** the mail gateway already matches a known contact by its main
  email. Otherwise the bridge links the person whose `email_personnel` is
  exactly the sender's, when there is exactly one; zero or several means no
  link. Never a score, never a creation.
- **Replies** land on their ticket through `catchall@` (core routing by
  `In-Reply-To`). The closing email now invites a reply.
- **Closing email** is also copied to the address the student wrote from when
  it differs from the contact's, as a raw address: the mail composer would
  otherwise create a second contact for that person (`find_or_create`).
- **Not taken:** OCA `helpdesk_ticket_partner_response`. It compares the
  sender with the contact's main email, so a student writing from a personal
  address would never move the ticket; agents are notified of replies anyway.
