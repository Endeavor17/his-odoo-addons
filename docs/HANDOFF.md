# Handoff — state, access and traps

Written so a session starting with **no prior context** (another machine, another
account) can pick this up. Newest section first.

---

# 2026-09-16

## 1. Where things stand

`main` is at **`2220f72`** (PR #24). GitHub Actions CI **green** (run #17).
Pre-prod is deployed, upgraded and verified.

Everything below was merged and deployed today:

| Work | Commits | State |
|---|---|---|
| Audit S-2/S-3 — public Campus+ API hardening | `16e6489` (PR #23) | merged, live |
| Adopt Abdo's POS branch `them_fixing` | `05297db` (PR #24) | merged, live |
| New module `his_pos_numbering` | `3631999`, `1c345c4` (PR #24) | merged, installed |

Earlier the same day: `chore/lint-ci` (PR #21) and `fix/s1-hr-job-escalation`
(PR #22) — lint tooling, CI, and the **S-1 critical** privilege-escalation fix.

### Verified on pre-prod after deployment

- 117 modules installed, **none stuck** in `to upgrade`
- `his_pos_numbering` installed, 19.0.1.0.0
- `https://odoo.his.edu.dz/api/campus/version` → 200
- `/web/login` → 200
- oversized POST to `/api/campus/applications` → **413**, nothing stored (S-3 cap live)
- the three `pos.config.order_seq_id` counters reset to **1**

## 2. The one thing NOT proven

**No screenshot exists of a POS order tab showing a plain number.** This is the
only open item from today's work.

- The logic is verified: 9 decision cases pass against the shipped code
  (`node` script, no browser needed — see §6).
- The patch demonstrably executes inside a real till (it returned the
  provisional marker before the fix).
- What is missing is a photograph of a tab reading `1` instead of `5001`.

Locally it could not be captured (see the CDP traps in §5). On pre-prod it needs
an **Odoo login for that server**, which this session never had. Easiest check:
open the Cafétéria till, create two orders, look at the top bar — they should
read `1` and `2`.

## 3. What `his_pos_numbering` does, and why

The POS top bar used to show `5001`, `4001`, `6003`. Decoded from Odoo source:

```
tracking_number = <device digit> + (order number % 1000), zero-padded to 3
```

The leading digit is **not the till**: it is `pos.config.device_seq_id`, a count
of *browsers* registered against that till. So the Restaurant (till 2) displayed
`6xxx`, and the digit changed whenever a till's browser data was cleared. With
`padding: 0` on that sequence, the 10th browser would have produced `10001`.

The module shows the order number taken from **`pos_reference`**
(`{YY}{device}-{config}-{number}`, e.g. `266-1-000003`) — third segment, parsed
the way Odoo's own `extractNumberFromReference` does it.

**`tracking_number` is untouched.** It still feeds refunds, receipts and
`pos_self_order`. No field, no view, no migration, no server call.

**Important correction discovered by rendering:** the first version displayed
`sequence_number`, which is **0 until an order syncs** — and a POS order only
syncs on validation. Every tab therefore read `…` during the whole time a
cashier is ringing up. `pos_reference` exists from creation and survives sync
unchanged, which is why it is the source. No test caught this; only opening a
real till did.

It is a **separate module** rather than part of `his_pos_ui` because that module
promises in its README to contain only CSS and one class, patching no component.

## 4. Access

- **Server**: `root@169.58.77.161` (Dokploy host). Private key is
  `Code's perso_private_id_rsa.txt` in `~/Downloads` on the Windows PC;
  fingerprint `SHA256:saL9W6eFPa5Zf3k0UVrJdyWkAD3vFukB4IlIguo7vlM`. Copy it
  somewhere with `chmod 600` before use.
  **A key created in Dokploy's "SSH Keys" section does not grant shell access** —
  that section only clones private git repos. The public key must be appended to
  `/root/.ssh/authorized_keys` from Dokploy's server terminal.
- **Containers**: `compose-copy-primary-monitor-vj69cc-odoo-1` and `-db-1`.
- **Database**: `his_dev` (yes — the production/pre-prod database has the same
  name as the local working one; `-d his_dev` on `169.58.77.161` means pre-prod).
- **Repo on the server**: `/etc/dokploy/compose/compose-copy-primary-monitor-vj69cc/code`
  (a real git clone; `git -C … log` tells you the deployed commit).
- **Dokploy API**: `http://169.58.77.161:3000`, header `x-api-key` (Mohamed has
  the key). It can read state and trigger deploys. It **cannot execute
  commands** — every exec-shaped route 404s — and it has no log route.
- Mohamed's position, recorded 2026-09-15: **this server is a pre-prod test
  box**; its data does not matter and destructive migrations are acceptable.

### Running anything on pre-prod

`docker exec` bypasses the image entrypoint, so the DB parameters must be passed
by hand:

```bash
C=compose-copy-primary-monitor-vj69cc
PW=$(docker exec ${C}-odoo-1 printenv PASSWORD)
docker exec ${C}-db-1 pg_dump -U odoo his_dev | gzip > /root/odoo-$(date +%F-%H%M).sql.gz
docker exec -u odoo ${C}-odoo-1 odoo -c /etc/odoo/odoo.conf -d his_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password="$PW" \
  -u <modules> --stop-after-init
docker restart ${C}-odoo-1
```

Keep `-u odoo` together as one token: `docker exec -u odoo <container>`.

## 5. Traps that cost real time — do not rediscover

### Deployment

1. **A Dokploy deploy does not restart the containers at all.** All three deploys
   on 2026-09-16 finished in ~3 seconds with container uptime unchanged, so the
   new Python was never loaded and S-1/S-2/S-3 sat dormant behind three green
   deploys. `-u` never happens by itself either.
2. **`compose.redeploy` in the API lies**: it answers
   `{"success":true,"message":"Redeployment queued"}` and does nothing — no
   restart, no deployment record. `compose.stop` then `compose.start` really do
   cycle the containers.
3. **The worst one: a running container can hold a stale bind-mount inode.**
   After a redeploy, `docker exec … ls /mnt/extra-addons` showed **0** of our 21
   modules while the host had all of them. A `-u` run in that state still
   reported "Modules loaded.", loaded 97 modules instead of 117, marked 16
   modules "not loaded", left three at `to upgrade`, and put
   `/api/campus/version` at **500** — while `/web/login` still answered 200, so
   one health probe is not enough.
   **Remedy — recreate, do not restart:**
   ```bash
   C=compose-copy-primary-monitor-vj69cc
   cd /etc/dokploy/compose/$C/code/deploy/odoo-dev && docker compose -p $C up -d --force-recreate
   docker exec ${C}-odoo-1 sh -c 'ls -1 /mnt/extra-addons | grep -cE "^(his_|campus_|insite_)"'
   ```
   That count must be ~19-21. **Zero is the signal.** Check it before any `-u`.
4. **Never `git checkout` `deploy/odoo-dev/docker-compose.yml` on the server.** It
   always shows as modified because Dokploy injects its Traefik labels and
   `dokploy-network` into it; reverting would drop the routing and take
   `odoo.his.edu.dz` offline.
5. **`-u all` cannot complete on that database.** Core `maintenance` upgrades
   before `maintenance_university`, so Odoo rebuilds core's FK
   (`category_id → maintenance_equipment_category`) on a column Abdo repurposed
   to his own `maintenance.category` model. It fails only when a
   `maintenance_request` row exists — pre-prod has exactly one ("Plumbing", valid
   data, `category_id` is NOT NULL). Use **targeted `-u`**. Do not "clean" that
   row. Code and DB agree at 19.0.3.0.0, so there is no mismatch to fix; it is an
   ordering problem and a question for Abdo.
6. Traefik **does** forward `X-Forwarded-Host`, so `proxy_mode` + ProxyFix work
   and `remote_addr` is the real client. Verified by the absence of the Campus+
   proxy warning in the log after a submission.

### POS / browser

7. Local container has **no `python3-websocket` and no Chrome**, so POS tours are
   **skipped** while the summary still says "0 failed" — a hollow green.
8. **Driving the POS over CDP**: a navigation detaches the session and the next
   command fails `-32000 "Not attached to an active page"`; re-enable `Page` and
   `Runtime` after every navigation. Several browser tabs on one till deadlock on
   `pos_config … FOR UPDATE NOWAIT` and the till hangs on its loading dots.
   The route is `/pos/ui?config_id=N` → entry screen → **"Opening Control"
   dialog** (a second "Open Register" button) → only then `.product-screen`.
   First load after clearing asset bundles takes 10-20s.
9. **Verify a pure function in plain Node**, not through the browser. Three runs
   were lost to nesting JS inside JS inside a bash heredoc.
10. Odoo 19 DOM facts: the order tab is `.floating-order-container button`.
    There is no `.order-tabs` and no `.list-container`. The single display
    chokepoint is the `floatingOrderName` getter on the client `pos.order`
    model — `getName()` calls it and appends "(Refund)".
11. A **double hyphen inside an XML comment** kills the entire POS template
    bundle; every till goes white and the browser shows nothing useful. The
    server log says "Double hyphen within comment".

### Local machine

12. Local `his_dev` has a **pre-existing inconsistency**: `his_academic_base` is
    uninstalled while `his_meal_management` and `insite_recruitment` depend on it,
    so those two never load there. Left alone deliberately — not this work's to
    fix. Use the **`ci`** database for local test runs instead; it has the full
    module set and mirrors CI's install order.
13. Under Git Bash, prefix container commands with `MSYS_NO_PATHCONV=1
    MSYS2_ARG_CONV_EXCL='*'` or absolute paths get rewritten to
    `C:/Program Files/Git/...` and `--test-tags /module` silently collects 0 tests.
14. The local server hosts several databases with no `dbfilter`, so a direct HTTP
    request answers 404 "No database is selected". Pass
    `-H "X-Odoo-Database: his_dev"`, or `?db=ci` in the browser.
15. `python` on this PC is the WindowsApps stub. Run tooling in containers
     (`python:3.12-slim`, `node:22-slim`). `node` itself is installed (v24).

## 6. Commands

```bash
# Tests for one module, on the local `ci` database (NOT his_dev — the running
# container serves it and two Odoo processes on one DB give "could not
# serialize access" and 0 tests).
MSYS_NO_PATHCONV=1 docker compose exec -T odoo odoo -d ci \
  -u <module> --test-enable --test-tags /<module> \
  --stop-after-init --http-port=8072 --log-level=test

# Lint exactly as CI does (the repo is 100% clean; keep it that way)
docker run --rm -v "$PWD:/w" -w /w python:3.12-slim \
  sh -c "pip -q install ruff==0.16.7 && ruff check . && ruff format --check ."
docker run --rm -v "$PWD:/w" -w /w node:22-slim sh -c "npx --yes eslint@9 ."
```

Read Odoo's own result line — `X failed, Y error(s) of Z tests`. **Never grep the
log for `ERROR`**: many tests deliberately raise, and Odoo logs ERROR while they
pass.

CI status without a token (the repo is public):
`https://api.github.com/repos/Endeavor17/his-odoo-addons/actions/runs?branch=<branch>`.
Query **by branch** — the `head_sha` filter needs the full 40-character SHA and
silently returns `total_count: 0` for a short one, which looks exactly like "CI
never triggered".

## 7. What is next

**Audit backlog** (full report on the local, unpushed branch
`chore/audit-securite-qualite`, at `docs/audit/2026-09-15-rapport.md`; the
ordered list is section 4). S-1, S-2, S-3 are done. Next:

- **S-4 / S-5 (High)** — meal wallet: a Meal Officer can write `credits_total`
  directly with no ledger line; a plan grants its credits whatever price the till
  actually charged. Needs `restrict_price_control` and a price check in
  `his_meal_management/models/pos_order.py`.
- **S-6 (Medium)** — record rule on `res.partner` so student/candidate personal
  data is not readable by every employee; group guard on `get_meal_balance`.
- **S-7 (Medium)** — temporary passwords stored in clear in
  `maintenance_university`.
- **S-8 (Medium)** — `workers` and `limit_*` absent from
  `deploy/odoo-dev/config/odoo.conf`.
- S-9/S-10/S-11 (Low) and the structural refactors.

**Outside the repo, Mohamed's to do:**

- **Branch protection on `main`**: require a PR and the `lint` + `tests` checks.
  Without it CI only warns — a push to `main` still auto-deploys.
- `gh` is **not installed** on the Windows PC, so PRs must be opened in the
  browser.

**Unreviewed team branches**: `origin/feature/besoin-achat`,
`origin/feature/campus-teacher-management`, `origin/feature/insite-recruitment`,
`origin/POS_and_maintenance`. Also `feature/meal-maintenance-rattrapage` (Abdo's
meal/maintenance catch-up, pushed, unmerged) and several local-only branches.

**Questions for Abdo**: why `them_fixing` was pushed when five of its six commits
say `LOCAL ONLY … Never push`; whether grid-only meal service is the final shape;
and the `maintenance` FK ordering above.

## 8. Conventions

- Commits are authored **`Endeavor <mohamed.bounouaa@outlook.com>`** (set at repo
  level, not globally) and end with a `Co-Authored-By:` trailer for the model.
- Commit bodies in **French**, explaining *why*, in the style of the `[SEC]`
  commits. Code comments follow the module they are in (Abdo's POS modules are in
  English; the identity/CRM modules are French).
- One branch per finding, **a failing test first**, then push and let CI judge.
- Mohamed verifies by **clicking through the real app**, and his bug reports are
  reliable even when the framing is imprecise. A clean compile or a green log is
  not verification — render it and look.
