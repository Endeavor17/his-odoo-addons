# Metabase dashboards embedded in Odoo — design

Date: 2026-10-18. Decided with Mohamed. Deadline: product demo to the workflow
managers on **Wednesday 2026-10-21**, on the staging server (`his_dev`).

## 1. Goal

Metabase (free edition) is the reporting tool for the whole ERP. Each workflow
manager opens **their own dashboard inside their own Odoo app**: maintenance,
helpdesk, point of sale, purchasing, inventory. Five KPIs per dashboard, agreed
below. The demo runs on staging with about three months of believable demo
data.

Out of scope: locked per-user filters (managers see their whole area), the
in-till dashboard of `his_pos_dashboard` (not installed on staging; to review
later), moving dashboards to prod (later, see §7).

## 2. Who does what

| Part | Owner |
|---|---|
| `his_metabase` Odoo module, menus, tests, removal of the old maintenance screen | Claude (this repo) |
| Demo data in `his_dev` | Claude on the staging VPS |
| The five Metabase dashboards | Claude on the staging VPS |
| KPI sign-off, dry run Tuesday evening | Mohamed |

## 3. The `his_metabase` module

Replaces the two embeddings a technician wrote (maintenance and till), which
each copied the token signing. One module, one way.

**Model `his.metabase.dashboard`** — one record per dashboard:

| Field | Meaning |
|---|---|
| `name` | Shown to the manager (translatable) |
| `code` | Stable key: `maintenance`, `helpdesk`, `pos`, `purchase`, `inventory` (unique) |
| `metabase_id` | Metabase dashboard number. Per server: set by an administrator, never shipped in data |
| `group_ids` | Odoo groups allowed to open it |
| `active` | Standard |

The five records ship as `noupdate` data with no `metabase_id`.

**Settings reused as they are** (already set on staging): system parameters
`his_metabase.site_url` and `his_metabase.secret_key`. The repository is
public, so neither is ever committed.

**Opening a dashboard**: each app gets a "Dashboard" menu that opens one client
action, given the dashboard `code`. The browser asks the server for a URL; the
server checks the user is in one of `group_ids` (an `AccessError` otherwise,
whatever the menu shows), signs a Metabase static-embedding token (HS256,
`{"resource": {"dashboard": id}, "params": {}, "exp": now + 600}`) and returns
`<site>/embed/dashboard/<token>#bordered=false&titled=true`. The page shows it
full-screen in an iframe. The key never leaves the server.

**Not configured**: if the site, the key or the dashboard number is missing,
the page shows a plain message naming what to set, not an error dialog.

**Menus and groups**:

| Dashboard | Under | Group |
|---|---|---|
| Maintenance | `maintenance_university.menu_maintenance_root` (replaces `menu_maintenance_metabase`) | `maintenance_university.group_maintenance_manager` |
| Helpdesk | `helpdesk_mgmt.helpdesk_ticket_main_menu` | `helpdesk_mgmt.group_helpdesk_manager` |
| Point of sale | `point_of_sale.menu_point_root` | `point_of_sale.group_pos_manager` |
| Purchasing | `purchase.menu_purchase_root` | `purchase.group_purchase_manager` (the executive director implies it) |
| Inventory | `stock.menu_stock_root` | `stock.group_stock_manager` |

The module depends on those five apps; all are installed on staging and will be
on prod. Administration (Settings ▸ Technical ▸ Metabase dashboards, system
group only) sets the numbers.

**Removed from `maintenance_university`**: the Metabase client action, its menu,
`get_metabase_url`, its JS/XML and its test. The monthly recap screen stays.

**Interface language**: English source, complete `i18n/fr.po` (CI rule).

## 4. KPIs (approved by Mohamed, 2026-10-18)

Every dashboard has a **period filter**, default this month, with the previous
month for comparison.

**Maintenance** — open requests by age (< 2 days, 2–7, > 7); average time to
fix, request to finished, by category; requests per building; worker hours
booked on requests vs present on site; critical inspection findings with no
repair request yet.

**Helpdesk** — open tickets now by stage (new / in progress / waiting); average
time to close by category; tickets per category over time; tickets by channel;
the ten oldest open tickets with requester and registration number.

**Point of sale** — sales per day per till (DA) with trend; meals served paid
with credits vs cash per day; top ten products; sales by hour of day; average
basket per till.

**Purchasing** — requests by step (draft → done); late requests (the follow-up
`his_is_late` flag) and who they wait on; spend per department from confirmed
orders; average time from request to order per department; top suppliers by
spend and number of quotes per order.

**Inventory** — counter items below their minimum (reordering rules); stock
value by category; top items consumed; slow movers (stock, no move in 60 days);
items waiting to be created from purchase requests (`his_needs_product`).

## 5. Demo data (staging `his_dev`)

- **Backup first** (dump in `/root/backups/`).
- About **three months of history**, created through the Odoo models (so
  business rules hold), then back-dated in SQL on the date fields only.
- Each KPI has something to show: a building with repeated leaks and one late
  repair; a Wi-Fi spike in tickets; a late purchase request and an item waiting
  to be created; one counter item below its minimum and one slow mover; daily
  till sales with lunchtime peaks, credits and cash.
- Fictional people and suppliers only, consistent with the existing recette
  world in `his_dev`.

## 6. Dashboards (staging Metabase)

- Built through the Metabase API: one dashboard per area, the five KPIs and the
  period filter.
- Questions in **native SQL**, against the `his_dev` database connection: they
  carry only the database reference, which makes a later move to prod a
  matter of remapping one id.
- Static embedding enabled on each dashboard, the period filter left
  **editable** (not locked).
- The five dashboard numbers are reported back and set in Odoo.

## 7. Later, not now

- Prod: copy the Metabase application database to prod once, before prod has
  real data, then author on prod (decided 2026-10-18). Dashboards-as-code only
  if they change often.
- Locked filters per user (one till, one department) when a dashboard is shown
  below manager level.
- Review or retire `his_pos_dashboard`.

## 8. Testing

- Module tests: token signature and expiry decode correctly with the key; a
  user outside `group_ids` gets `AccessError`; a missing setting returns the
  "not configured" answer; every dashboard record's groups and menu exist.
- Browser check on staging: each manager role opens its dashboard and is
  refused the others; French labels.
- Dry run with Mohamed on Tuesday evening.
