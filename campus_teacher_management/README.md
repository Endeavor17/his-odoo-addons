# Campus+ Teacher Management

Teacher recruitment, evaluation and ranking for Campus+, built on Odoo 19's
`hr.applicant`.

---

## What it does

```
Campus+ web form
      │  POST /api/campus/applications
      ▼
campus.submission        raw payload, stored before anything is parsed
      │
      ▼
hr.applicant             standard Odoo applicant + Campus+ answers
      │
      ├── campus.application.score      one row per criterion, snapshotted
      ├── campus.application.subject    requested + accepted subjects
      │
      ▼
campus.scoring.engine    raw → normalized → weighted → final
      │
      ▼
final score ──► rank (per campaign) ──► ranking list + dashboard
      │
      ▼
accept / refuse ──► assign accepted subjects
```

Nothing about recruitment is re-implemented. Stages, chatter, activities, the
UTM campaign, attachments and access rights all come from `hr_recruitment`.

---

## The hiring sequence

Everything after "this candidate looks good". Driven by `campus_hiring_state` on
`hr.applicant`, which is deliberately separate from `stage_id` (the pipeline a
recruiter drags cards through) and `campus_state` (the scoring lifecycle).

| Step | Button | Odoo sends |
|---|---|---|
| Not Selected | — | — |
| Invited | **Select & Invite** | acceptance + available 1st-meeting times |
| 1st Meeting Scheduled | **Schedule Meeting** | nothing |
| Documents Sent | **Send Course Breakdown & Contract** | both uploaded files |
| Documents Accepted | **Record Acceptance** | — |
| Final Breakdown Sent | **Send Final Breakdown** | final file + 2nd-meeting times |
| 2nd Meeting Scheduled | **Schedule Meeting** | nothing |
| Hired | **Hire** | — (creates the `hr.employee`) |

Only the one valid button is visible at a time, and the order is enforced in Python
as well — a server action or script cannot skip a step. Sending refuses to run while
a required document is missing, so an empty contract can never go out.

**The candidate is never an attendee of their own interview.** Odoo emails every
attendee of a `calendar.event`, and the decision was that the recruiter confirms the
time in their own reply. Only the interviewer is invited. There is a test for this.

**Documents are uploaded, not generated.** Attach the Course Breakdown, the contract
and the final Course Breakdown on the Hiring tab; Odoo emails exactly what is there.

**Slots.** Scheduling → Available Slots holds the times offered to candidates.
*Generate Week* creates a whole week from a pattern (days, hours, slot length) and
skips times already on file, so it is safe to run twice. Times are entered in your
timezone and stored as UTC. Releasing a booked slot also deletes its calendar entry.

### Email

Three templates under Configuration → Email Templates, editable without a developer.
Available times are rendered from the free slots at send time, so a candidate can
never be offered a slot the recruiter cannot then book.

**No outgoing mail server is configured yet.** Mails queue in *Settings → Technical →
Email → Emails* where you can read them. They start really sending the moment SMTP
credentials are added — no code change.

---

## Models

| Model | Purpose |
|---|---|
| `campus.evaluation.version` | A frozen campaign: criteria, barèmes, priorities, weighting method. Publishing makes it read-only. |
| `campus.criterion` | One criterion (C1–C12): where its answer comes from, how it becomes a number, how important it is. |
| `campus.criterion.scale` | One barème line: an answer code and the points it is worth. |
| `campus.subject` | The subject catalogue candidates choose from. |
| `campus.application.score` | One criterion's result for one application, with every input snapshotted. |
| `campus.application.subject` | A subject the candidate requested, and whether it was granted. |
| `campus.submission` | The raw request body, kept for audit and re-processing. |
| `campus.scoring.engine` | AbstractModel holding the pipeline. Swappable. |
| `campus.interview.slot` | A time offered to candidates; booking one creates the meeting. |
| `campus.slot.generate` | Wizard: create a week of slots from a pattern. |
| `campus.schedule.interview` | Wizard: record the time a candidate replied with. |
| `hr.applicant` | Extended, not replaced. |

---

## The CAR algorithm

Weights are **never typed in**. They are derived from criterion *priorities*
whenever a priority changes. Two methods are available per version:

| Criterion | Priority | `legacy_car` | `car` (default) |
|---|---|---|---|
| C1, C5 | 3 | 0.1290 | 0.1379 |
| C3, C8, C12 | 2 | 0.0968 | 0.1034 |
| C2, C4 | 1 | 0.0968 | 0.0690 |
| C7, C9, C11 | 1 | 0.0645 | 0.0690 |
| C6, C10 | 0 | 0.0323 | 0.0345 |

**`legacy_car`** reproduces the original spreadsheet implementation exactly. It
builds an accumulator from most to least important, then reverses it *by index*.
When a group of equally-prioritised criteria straddles a step in that array the
group is split: C2, C4, C7, C9 and C11 all have priority 1 but come out with two
different weights, decided only by dict ordering — and C2/C4 end up tied with the
higher-priority C3/C8/C12. Keep this method to reproduce pre-Odoo rankings.

**`car`** sorts ascending and accumulates the gap to the previous priority, so
equal priorities always get equal weight and higher priority always means higher
weight. Both sum to 1.

Priority 0 still yields a non-zero weight in both methods. If 0 should mean
*excluded*, archive the criterion instead — or change `_car_weights`.

### Normalization

Each criterion's raw score is divided by its own maximum before weighting, so a
weight of 0.1379 really is 13.79% of the final score. The final score is on
**0–100**.

Without this, C3 (years of experience) dominates: it is unbounded while every
other criterion caps at 6, so all eleven others at maximum sum to 4.59 while C3
alone reaches that at ~45 years. `years_cap` on the version (default 20) is the
point at which experience saturates.

Turning `normalize` off gives a plain weighted sum of raw scores with no ×100
rescale — the pre-Odoo behaviour, for reproducing old numbers.

---

## Historical safety

Two independent mechanisms, because either alone leaves a gap:

1. **Version immutability.** Publishing a version makes its criteria, scales and
   priorities read-only. Editing requires **New Version**, which copies
   everything into a fresh draft. The published original never moves.
2. **Score snapshots.** Every `campus.application.score` row copies the criterion
   code, the matched answer, the raw score, the maximum and the weight that
   produced it. Even if a criterion were deleted, the row still explains how that
   candidate was ranked.

Changing a barème in a new version therefore cannot alter a score computed under
the old one. There is a test for exactly this.

---

## Criteria → form mapping

| # | Criterion | Source field | Type |
|---|---|---|---|
| C1 | Scientific rank | `rank` | scale (6 → 1) |
| C2 | Previous Campus+ participation | `taughtCampus` | scale (5 / 0) |
| C3 | Years of experience | `yearsExp` | number, capped |
| C4 | Confidence on camera | `camConfidence` | scale (5,4,3,1,0) |
| C5 | Already taught selected subjects | `taughtSelectedSubjects` | **derived** |
| C6 | Already taught at HIS | `taughtHIS` | scale (5 / 0) |
| C7 | Digital tools used | `digitalTools` | count, max 6 |
| C8 | Flipped classroom knowledge | `flippedKnowledge` | scale (4 → 0) |
| C9 | Experience per subject provided | `subjectExperienceProvided` | **derived** |
| C10 | Pedagogical means used | `teachMethods` | count, max 5 |
| C11 | Explanation of digital tool use | `concernsHandled` | **needs confirmation** |
| C12 | Flipped classroom in own words | `flippedDef` | answered |

### ⚠ Confirm before publishing

The web form has **no question** matching C5, C9 or C11. The shipped values are a
best reading:

- **C5** — derived: true when any selected catalogue subject has years > 0.
- **C9** — derived: true when the candidate entered years against any subject.
- **C11** — points at *"how did you address your concerns"*. The alternative is
  `redesignDetail`.

`source_key` is an ordinary editable field, so re-pointing a criterion is a UI
change, not a code change. After changing it, use **Re-process** on the stored
submissions to rebuild affected applications.

### Two form quirks encoded here

- **C1** — the form offers 7 ranks; the barème names 6. `vacataire` and
  `doctorant` both map to *Autre* = 1.
- **C4** — the barème is 0, 1, 3, 4, 5. It **skips 2** on purpose. The form's
  five levels map onto those in order.

Answers are matched on the stable code first, then the label, then any alias, so
renaming a label can never change how a past answer scored. The alias lists carry
the Arabic display text the current form sends, so submissions score correctly
whether or not the form has been patched.

---

## API

Base URL in development: `http://localhost:8070`.

### `POST /api/campus/applications`

```json
{
  "external_ref": "web-8f21...",
  "nameAr": "...", "nameLat": "...", "email": "...", "phone": "0770000000",
  "yearsExp": 8,
  "rank": "mca",
  "taughtHIS": "yes", "taughtCampus": "no",
  "camConfidence": "3", "flippedKnowledge": "3",
  "flippedDef": "...", "concernsHandled": "...",
  "digitalTools": ["moodle", "zoom"],
  "teachMethods": ["onsite"],
  "selectedSubjects": [{"id": "12", "name": "...", "exp": 3}],
  "hisSubjects": [{"id": "", "name": "...", "exp": 2}]
}
```

| Status | Meaning |
|---|---|
| `201` | Created and scored |
| `200` + `duplicate: true` | This `external_ref` was already received; the original is returned |
| `400` `invalid_json` | Body is not a JSON object |
| `403` `origin_not_allowed` | Origin is not in the allowlist |
| `409` `duplicate_application` | This email already applied to this campaign |
| `422` | `missing_field`, `invalid_email`, `invalid_years`, `too_many_subjects`, `unknown_subject`, `no_published_version` |
| `429` `rate_limited` | Too many submissions from this IP or email |

### `GET /api/campus/subjects`
The catalogue, so the form need not hard-code it.

### `GET /api/campus/version`
The open campaign. **Never returns scores, weights or priorities** — publishing
the barème would tell candidates how to game it.

### Security

The form is a static page, so the browser posts directly and cannot hold a
secret. CORS is *not* the security boundary — it only makes the legitimate
browser call work, and `curl` ignores it. The actual defenses are:

- **Origin allowlist** — `campus_teacher.allowed_origins`, comma-separated.
  Empty means "not configured yet" and allows everything so a fresh install is
  testable. **Set this before going live.**
- **Rate limiting** — `campus_teacher.rate_limit_ip` (default 20) and
  `campus_teacher.rate_limit_email` (default 3) per
  `campus_teacher.rate_limit_window_minutes` (default 60).
- **Honeypot** — `campus_teacher.honeypot_field` (default `website`). A filled
  honeypot is answered `201` so a bot learns nothing, but nothing is created.
- **Duplicate detection** by email per campaign, and `external_ref` idempotency.
- **Full payload validation** before any record is created.

If abuse becomes real, a CAPTCHA is the next step. Rate limiting at the reverse
proxy is complementary and recommended.

Every request is written to `campus.submission` **before** parsing, so a mapping
bug can be corrected and re-processed instead of losing an application.

---

## Configuring

**Set a Job Position on every campaign.** Odoo only assigns a recruitment stage
to an applicant that has a job position (`hr.applicant._compute_stage` returns
early without one). Leave it empty and incoming applications are created with no
stage, so they never appear in the recruitment pipeline and cannot be moved
through accept/refuse. The field is on the evaluation version form.

**Add a question to the evaluation** — no code required:
1. Configuration → Evaluation Versions → **New Version** (if published).
2. Add a criterion: code, name, priority, value type, source field.
3. For a scale criterion, add its answer lines with their scores.
4. **Publish**. Weights recompute automatically.

**Change a score or a weight**: change the barème line, or change the priority.
Weights are derived — never enter one by hand.

**Re-point a criterion at a different question**: edit `source_key` in a draft
version. Valid keys are whatever `hr.applicant._campus_answer_payload()` returns.

---

## Replacing the scoring algorithm

`campus.scoring.engine` is an AbstractModel with one overridable method per step:

```python
def compute_scores(self, applicants):
    data = self._collect(applicants)
    data = self._raw_scores(data)
    data = self._normalize(data)      # ← divide by max, clamp
    data = self._apply_weights(data)  # ← multiply by CAR weight
    return self._aggregate(data)      # ← sum, ×100
```

Either edit those in place, or — better — ship a separate module:

```python
class WeightedEngine(models.AbstractModel):
    _name = 'campus.scoring.engine.mine'
    _inherit = 'campus.scoring.engine'
    ENGINE_VERSION = 'mine-v1'

    def _normalize(self, data):
        ...
```

then point the config parameter at it:

```
campus_teacher.scoring_engine = campus.scoring.engine.mine
```

No model, view, API route or dashboard changes. `ENGINE_VERSION` is stamped onto
every application, so you can always tell which algorithm produced a score.

The CAR weight derivation itself lives in `campus.criterion._car_weights`.

---

## Security groups

- **Recruiter** (implies `hr_recruitment.group_hr_recruitment_user`) — reads the
  configuration, manages applications, accepts/refuses, assigns subjects.
- **Manager** — the above, plus criteria, barèmes, priorities, publishing,
  recalculation and raw submissions.

Raw submissions contain personal data and are manager-only via a record rule.
This module does not modify any other app's menus.

---

## Tests

```bash
docker exec teacher_odoo odoo -d campus_recruitment \
  -u campus_teacher_management --test-enable \
  --test-tags /campus_teacher_management --stop-after-init --log-level=test
```

The most important file is `tests/test_car_weights.py`: it pins both weight
tables to the exact values above. If a refactor changes a ranking, that is where
you will find out.

---

## Known gaps

- **Arabic subject labels** in `data/campus_subjects.xml` were reconstructed from
  a lossy PDF render of `form.html`. The `code` is what scoring uses, so a wrong
  label is cosmetic — but verify them against the real file.
- **Wilaya, commune and secondary phone** are in the specification but not in the
  form. The fields exist and stay empty until the form collects them.
- **Language levels** are collected by the patched form but no criterion scores
  them yet; add one when you decide how they should count.
