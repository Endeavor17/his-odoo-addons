   # University Maintenance — How It Works (Presentation Runbook)

   This is the click-by-click script for demoing the module. Read it top to bottom
   while you present: every step says **who is logged in**, **what they click**, and
   **what the audience should see**.

   The app is Odoo's own Maintenance app, extended for the university — not a
   lookalike sitting next to it. The menu is simply called **Maintenance**.

   ---

   ## 1. The three roles

   | Role | Sees | Can do |
   |------|------|--------|
   | **Reporter** | One screen: *Report a Problem* | Files a problem in a building. Sees only their own reports. Never sees the request pipeline. |
   | **Worker** | *My Work* (kanban of their own jobs) | Start / Pause / Resume / Complete their assigned jobs. Logs findings on an inspection tour. Sees **only** requests assigned to them. |
   | **Manager** (Maintenance Leader) | Everything | Creates requests, assigns workers, converts reports into work, reads the recap dashboard, manages buildings/categories/workers. |

   **The one rule that shapes the whole demo:** a Manager assigns and tracks work,
   but **cannot start or complete it**. The Start/Pause/Resume/Complete buttons are
   hidden from managers and blocked server-side. So you must log in as a worker for
   the middle of the demo. This is deliberate — say it out loud, it's a feature.

   ---

   ## 2. The flow at a glance

   ```mermaid
   flowchart TD
      R["Reporter: Report a Problem"] -->|Submit| F["Report sits in Findings and Reports"]
      F -->|"Manager: Convert to Request"| N
      M["Manager creates request directly"] --> N["New"]
      N -->|"Manager: pick workers, Assign"| A["Assigned"]
      A -->|"Worker: Start"| P["In Progress - clock running"]
      P -->|"Worker: Pause"| PA["Paused - clock stopped"]
      PA -->|"Worker: Resume"| P
      P -->|"Worker: Complete"| D["Done"]
      N -->|Cancel| C["Cancelled"]
      A -->|Cancel| C
      P -->|Cancel| C
   ```

   Inspection tours are the same pipeline with an extra loop:

   ```mermaid
   flowchart LR
      I["Inspection request"] --> W["Worker walks the building"]
      W --> FD["Logs Findings - one row per problem"]
      FD -->|Submit| MG["Manager reviews"]
      MG -->|"Convert to Request"| NR["New repair request"]
      W --> RP["Writes Report tab, Send Report to Leader"]
      RP --> CH["Lands in the chatter"]
   ```

   Every state change writes a **time segment**. The request's *Duration* is the
   real sum of those segments, not an estimate. That is what feeds the dashboard.

   ---

   ## 3. Pre-flight — do this 5 minutes before you present

   1. **Stack up:** http://localhost:8072 → database **`his`** → login `admin`.
   2. **Set the demo passwords.** Go to *Settings → Users & Companies → Users* and,
      for each account below, open it and set a password you'll remember, so you can
      log in live without hunting:

      | Purpose | Login |
      |---------|-------|
      | Manager | `a.chabouti@esi-sba.com` (Manitenance leader) |
      | Worker | `chabouti3abdo@gmail.com` (Worker) |
      | Reporter | `a.chabouti@dz` (Reporter) |

      `admin` is also a Manager if you'd rather use it.
   3. **Open three browser windows** — one normal (Manager), two incognito
      (Worker, Reporter). Switching accounts by logging out mid-demo wastes time
      and breaks your rhythm.
   4. **Check your data.** *Maintenance → Configuration → Buildings* should have at
      least one building, and *Categories* at least one non-inspection category plus
      one flagged **Is Inspection Category**.
      > Current state of `his`: one building (**CAF**), categories **inspection**
      > (the inspection one) and **hello**. The category named *normal* is archived
      > so it won't appear in the dropdown. Rename **hello** to something
      > presentable (e.g. *Plumbing*) before you start — 10 seconds, and it makes
      > the whole demo look intentional.
   5. **Have one request already Done** so the dashboard isn't empty. There are
      already three (`idk`, `wow`, `tisiti`).

   ---

   ## 4. Act 1 — The main loop: report → assign → do the work

   ### Step 1 — Reporter files a problem *(Reporter window)*

   1. Log in as `a.chabouti@dz`.
   2. Point out: **the whole app is one menu item for this person.**
      Click **Maintenance → Report a Problem**.
   3. Click **New**.
   4. Fill in: **Building** = CAF, **Category** = Plumbing, **Severity** = High,
      **Description** = "Water leaking from the ceiling in the cafeteria".
   5. Optionally drag a photo into the **Photos** box at the top.
   6. Click **Submit** (top-left).
      → The status bar moves **Draft → Submitted** and every field locks. Say why:
      *the manager is about to act on these exact values, so the reporter can't
      change them out from under a review already in progress.*

   > **Talking point:** there is nowhere else for this person to go. A Reporter
   > cannot see a single maintenance request in the whole university. That's
   > enforced by a record rule, not by hiding a menu.

   ### Step 2 — Manager turns the report into work *(Manager window)*

   1. Log in as `a.chabouti@esi-sba.com`.
   2. Click **Maintenance → Findings & Reports**.
   3. In the search panel, click the filter **Department Reports** — these are the
      ones filed by reporters (no inspection behind them). The leak you just filed
      is at the top, in blue (*Submitted*).
   4. Click **Convert to Request** on that row.
      → Odoo jumps straight to a **brand-new maintenance request**, pre-filled:
      building, category, description carried over, and **priority set from the
      severity** (High severity → High priority). Point at the *Originating
      Finding* field — the trail back to who reported it.
      → Back on the report, its status is now **Converted** with a link to the
      request it generated.

   ### Step 3 — Manager assigns it *(Manager window)*

   1. On that request form, in **Assigned Workers**, pick the worker **Worker**.
   2. Set **Scheduled For** to today, if you want to show it.
   3. Click **Assign**.
      → Status bar: **New → Assigned**, and *Assigned On* stamps itself.

   > **Show the guardrail:** before picking a worker, click **Assign** with the
   > field empty — Odoo refuses: *"Select at least one worker before assigning."*
   > A job can never leave New with nobody on it.

   > **Show the second guardrail:** as Manager, look at the header. There is **no
   > Start button.** Only Assign and Cancel. Say it: *the leader dispatches, the
   > worker executes.*

   ### Step 4 — Worker does the job *(Worker window)*

   1. Log in as `chabouti3abdo@gmail.com` (Worker).
   2. Click **Maintenance → My Work**. Two things are on this screen: the **work-day
      clock** across the top, and the job cards below.

      Press **Start working** first. The banner switches to *Working*, stamps the
      arrival time and starts counting. Say what it is: **presence, not task time**
      — it keeps running between jobs and through a break, which is exactly why it
      is a different number from the job timers below. Take a break and come back
      later in the demo to show *On break*; **End day** closes it.

      The new job is a card in the **Assigned** column.
   3. Click **Start** right on the card (no need to open it).
      → The card slides to **In Progress**. A time segment just opened.
   4. Open the card. Go to the **Time Log** tab — there's a row with a start time
      and no end time. *The clock is running.*
   5. Click **Pause**, then **Resume**, then **Complete**.
      → Watch the Time Log grow a row per segment, and **Duration** add up.
   6. Try to edit the **Description** as the worker → it's read-only. The worker
      updates their *progress*, never the *definition* of the job.

   > **Show the isolation:** in the search bar, clear all filters. The worker still
   > sees only their own jobs — the other requests in the university are invisible,
   > at the database level.

   ---

   ## 5. Act 2 — The inspection tour

   This is the part that makes it a maintenance *system* rather than a to-do list.

   ### Step 1 — Manager schedules a tour *(Manager window)*

   1. **Maintenance → Requests → New**.
   2. **Title**: "Monthly inspection — CAF". **Building**: CAF.
      **Category**: **inspection** (the one flagged as the inspection category).
      → The moment you pick it, two new tabs appear: **Findings** and **Report**.
      The kanban card will also carry an orange *Inspection tour* badge.
   3. **Assigned Workers**: **Worker**. Click **Assign**.

   ### Step 2 — Worker walks the building *(Worker window)*

   1. **My Work** → the inspection card → **Start**.
   2. Open the **Findings** tab. Click **Add a line** for each problem spotted:
      - Building (pre-filled with the inspected building), Category, Description,
      Severity.
      - Add two or three: e.g. *"Broken window, 2nd floor"* (High), *"Flickering
      light, corridor"* (Low).
   3. Click **Submit** on each finding row.
   4. Go to the **Report** tab, write a couple of lines about how the tour went,
      and click **Send Report to Leader**.
      → Scroll down to the chatter: the report is posted there as a message, so
      every follower is notified. It's a conversation, not a buried text field.
   5. Click **Complete**.

   > **Show the guardrail:** try setting a finding's category to **inspection** →
   > refused. Converting it would create *another inspection* instead of a repair.

   ### Step 3 — Manager converts findings into real work *(Manager window)*

   1. **Maintenance → Findings & Reports**, filter **Inspection Findings**.
   2. Both findings from the tour are there, *Submitted*.
   3. Click **Convert to Request** on the "Broken window" one.
      → New request, **priority High** (from the High severity). Assign it to a
      worker and you're back at Act 1.
   4. Open the inspection request again and point at the **Findings** stat button
      in the top-right corner — the count of everything that tour produced.

   > **The story to tell:** one inspection tour fans out into as many tracked
   > repair jobs as it found problems, each one carrying its origin. Nothing gets
   > lost between "someone noticed it" and "someone fixed it".

   ---

   ## 6. Act 3 — What the leader gets out of it *(Manager window)*

   ### Monthly Recap
   **Maintenance → Monthly Recap**

   - Totals across the top: **Requests Completed**, **Hours Logged**,
   **Findings Logged**.
   - **Worker Comparison** table: per worker — Hours Worked, Tasks Completed,
   Findings Logged, Critical/High Findings. Every number comes from the time
   segments the workers actually generated by clicking Start/Pause/Complete.
   Nobody typed a timesheet.
   - **By Category** and **By Building** breakdowns underneath — where the
   university's maintenance load actually falls.
   - Use the arrows to step to the previous month and back.

   > Managers are excluded from the worker comparison on purpose — a leader with an
   > employee record shouldn't pollute a worker-to-worker table.

   ### Worker Summary
   **Maintenance → Worker Summary** — the per-employee view, with the institutional
   ID (matricule) each person carries from the central `his_person_core`
   referential. Worth one sentence: **this module doesn't invent identities, it
   mirrors the university's.**

   ---

   ## 7. Configuration screens (show briefly at the end)

   **Maintenance → Configuration →**

   - **Buildings** — the university's building list. Name + code.
   - **Categories** — kinds of problem. Exactly one may be flagged **Is Inspection
   Category** at a time; the system enforces it.
   - **Create Workers** — batch-create worker accounts: type a name and a login,
   click Create, and each one gets a user account, an employee record, the Worker
   group and a generated password shown back to you.

   > **The best 20 seconds of the demo, if you have time:** in *Create Workers*,
   > type the name of somebody who already exists in the referential — e.g.
   > `Abderrahim Chabouti`. A **Possible Match** appears: *"Already registered as
   > <matricule> — pick them, or tick New Person."* Click Create anyway and it
   > **refuses**. Explain: this wizard used to mint a brand-new person and a
   > brand-new institutional ID on every run, which is how one human ended up with
   > three records. Now it either attaches to the existing person or makes you state
   > explicitly that this is a different human who happens to share the name.

   ---

   ## 8. Things that will bite you live — and what to say

   | What happens | Why | Say this |
   |---|---|---|
   | No **Start** button as Manager | Managers dispatch, workers execute — enforced server-side, not just hidden | "The leader can't quietly do the work and log it as someone else's." |
   | **Assign** refuses with no worker | A request can't leave New unassigned | "No orphan jobs." |
   | Worker can't edit description/building | Only progress fields are worker-writable | "The job definition belongs to the manager." |
   | Reporter sees zero requests | Deny-all record rule on the pipeline | "Access is by rule, not by hidden menus." |
   | Submitted report can't be edited | Locked once a manager is acting on it | "No changing the story mid-review." |
   | Clicking the status bubble does nothing | It's read-only by design | "The buttons are the only way through, so time always gets logged." |
   | A finding can't use the Inspection category | Would create another inspection instead of a repair | — |

   ---

   ## 9. If something goes wrong

   ```bash
   # Is it up?
   curl -I http://localhost:8072/web/login

   # Bring the stack up (Docker Desktop must be running first)
   cd /d/Mouhamed/his-odoo-addons && docker compose up -d

   # Python changed and the browser disagrees -> restart
   docker compose restart odoo

   # Views/XML changed -> upgrade the module
   docker compose run --rm odoo odoo -d his -u maintenance_university --stop-after-init
   docker compose restart odoo

   # Watch the log while you click
   docker compose logs -f odoo
   ```

   - **"Field is undefined" in the browser** → the long-running container is on old
   code. `docker compose restart odoo`.
   - **A view change didn't appear** → a restart alone never reloads XML. You need
   `-u maintenance_university`.
   - **Docker says it can't connect** → Docker Desktop itself is closed. Start it,
   wait for the whale, then `docker compose up -d`.
   - On Git Bash, prefix docker commands with `MSYS_NO_PATHCONV=1` if paths come out
   mangled.
