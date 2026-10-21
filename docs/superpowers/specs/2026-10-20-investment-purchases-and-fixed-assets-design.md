# Usual vs investment purchases, and fixed assets in inventory

Date: 2026-10-20. Source: meeting between Mohamed and the CEO, then a design
conversation with Mohamed. Builds on `2026-10-15-purchasing-design.md`
(`his_purchase`), which this document amends.

## 1. Why

The executive director does not want to approve everyday purchases. The
purchasing officer already handles operational buying (POS and restaurant
stock, maintenance parts, small purchases) and should finish those alone.
The director only wants to see **investments**: new student tables, laptops,
printers, doors, Wi-Fi access points, cameras, desks, chairs, cars, kitchen
equipment and fit-out works.

The CEO also wants durable items (desks, screens, air conditioners, tables,
chairs...) to be in the inventory, each one traceable, and to go through the
annual inventory count.

## 2. Goals, non-goals, anti-goals

Goals
- Only "Responsable" positions can create purchase requests.
- The purchasing officer classifies every request as **Usual** or
  **Investment**. Usual: he finishes it alone. Investment: the director
  approves it up front.
- An investment order that ends up more than 20 % above what the director
  approved goes back to the director.
- Each durable item is a serial-numbered unit sitting in a room, with its move
  history, counted once a year room by room.

Non-goals (decided)
- **Réforme (written-off items): out of scope** until Mohamed finds out the
  real process (who decides, what document, where items go). Do not build a
  scrap/réforme flow, not even a placeholder.
- Depreciation / accounting asset values (Odoo Community has no asset module;
  stays with the accountant).
- A dedicated scanning app. Barcode vs QR is not decided; the design must work
  with either (see §5.4).

Anti-goals (would be a failure even if it works)
- The director receiving to-dos or approvals for usual purchases.
- A cheap estimate getting an expensive investment past the director.
- Patrimoine items mixing with the stock the POS and restaurant draw from
  (a laptop showing as "available" to a POS replenishment, chairs in a
  restaurant count).

## 3. Current state (main `2c88530`)

- `his.purchase.request`, `purchase.order` and `purchase.requisition` carry
  `his_purchase_domain` (`pos` / `general`). On requests it is computed from
  `hr.department.his_purchase_domain`, editable by the purchasing team only
  (`PROTECTED_FIELDS`).
- Request approval: `approver_id` = department head, or the company's
  `his_purchase_director_id` when the requester is the head
  (`_compute_approver_id`). States: draft → submitted → approved → sourcing →
  ordered → done.
- Order approval: `purchase_order._his_approver_group()` — `pos` →
  `purchase.group_purchase_manager`, `general` →
  `his_purchase.group_purchase_director`. Threshold
  `po_double_validation_amount` is set to **0** by `hooks.py`, so every order
  goes through approval (value on staging/prod not re-checked).
- Reminders/escalations: `_his_step()` on requests and orders, owner/chain
  depends on the domain.
- The buyer may relabel the domain and approve himself: **wanted by the
  directors, do not lock it** (decision 2026-10-19).
- Positions (`hr.job`, `his_access_base`) grant roles. The purchasing officer
  is the occupant of `his_purchase.job_purchasing_officer`
  (`res.company.his_purchase_officer_id`, computed).
- `maintenance_university` has `maintenance.building` (name, code). No rooms.
- No model or data tracks furniture or equipment today.

## 4. Purchases: Usual vs Investment

### 4.1 The field
- Replace `his_purchase_domain` with **Purchase Type**
  (`his_purchase_type`, selection `usual` / `investment`, labels "Usual
  purchase" / "Investment") on requests, orders and agreements.
- It is **no longer derived from the department**: remove
  `hr.department.his_purchase_domain` and its view.
- On a request it is **empty until the officer sets it**. It stays in
  `PROTECTED_FIELDS` (the requester never sets it; the officer may change it
  freely **until the director approves**). Once the director has approved an
  investment request, the type is **locked to Investment** for everyone but
  the director, on the request and on the orders/agreements that come from it
  (Mohamed, 2026-10-20). This narrows the 2026-10-19 "do not lock the
  relabelling" decision to before the escalation.
- Migration: `pos` → `usual`, `general` → `investment` on every existing
  record. Open requests in `submitted` keep their current approver until
  acted on (builder's call how; staging is a dev zone, prod data is test data).
  My call: requests already approved as `general` get `his_approved_amount`
  backfilled from `estimated_amount`, so their open orders follow the 20 %
  rule instead of all landing on the director.

### 4.2 Who can request
- Only the **Requester** role (`his_purchase.group_requester`) creates
  requests, and it is granted **by position** to Responsable positions only,
  not to all employees. No code beyond what exists; it is position data.
  Mohamed sets which positions after deployment (§7).
- The department-head approval step disappears: the requester *is* the head.
  Update the group's comment and the README accordingly.

### 4.3 Request flow
1. Responsable creates and submits (same checks as today: justification,
   required date, lines).
2. On submit the request goes to the **purchasing officer**
   (`approver_id` = officer). He is subscribed and gets the to-do.
3. The officer sets the Purchase Type. **Approve is refused while the type is
   empty.**
   - **Usual** → the officer approves. Then sourcing as today.
   - **Investment** → `approver_id` becomes the executive director. Only the
     director (`group_purchase_director`) can approve. Setting the type to
     Investment *is* the escalation; no extra button is required (builder may
     add one if it reads better).
4. When the director approves, store **`his_approved_amount`** = the request's
   `estimated_amount` at that moment (readonly, tracked). This is what he said
   yes to. My call: estimates are **excluding tax** (label the request line
   price "Estimated Unit Price (excl. tax)"), compared with the order's untaxed
   total, so tax never eats the 20 % margin.
5. Reject works as today, by whoever is the current approver.

My call: no new state. "Waiting for the officer" vs "waiting for the
director" is read from `approver_id`; add a filter "To approve by me".

### 4.4 Order approval
Keep the 3 quotes, recorded choice, reminders and monthly framework orders
unchanged. Who approves an order in `to approve`:

| Order | Approver |
|---|---|
| Usual | purchase manager group (the officer), or the director |
| Investment, from a director-approved request, untaxed total ≤ 120 % of the approved amount of the request lines it covers | purchase manager group (the officer), or the director |
| Investment, above 120 % | director only |
| Investment, no approved request behind it (officer created the order or agreement directly) or approved amount = 0 | director only |

- "Approved amount of the lines it covers": prorate `his_approved_amount` on
  the request lines the order's lines come from (`_his_requests()` already
  links them). If an order covers several requests, sum. Exact formula is the
  builder's, but it must not let splitting one request into several orders
  bypass the 20 % (compare cumulative confirmed orders of a request against its
  approved amount).
- The 20 % is a constant in code (like the delays), not a setting.
- The refusal message names the reason ("more than 20 % above the amount the
  director approved: X DA approved, Y DA ordered").
- Keep the threshold at 0.

### 4.5 Reminders
Adapt `_his_step()`: request waiting for the officer → owner officer, escalate
to the purchase manager setting; waiting for the director → owner director, no
chain. Orders: usual → officer; investment needing the director → director.
**The director must never get a to-do for a usual purchase.**

## 5. Fixed assets ("Patrimoine")

New module `his_patrimoine` (depends on `stock`, `his_stock_mdm`,
`maintenance_university`, `his_purchase`). Name is my call.

### 5.1 Items
- Product category tree **Patrimoine** with subcategories (my starting list:
  Mobilier, Informatique, Réseau & sécurité, Climatisation, Véhicules,
  Équipement cuisine). Categories set to storable, **tracking by serial
  number**, not for sale, and not a source of automatic accounting entries on
  moves.
  Vendor bills keep the **default expense account**; the accountant
  reclassifies them to fixed assets by hand (Mohamed, 2026-10-20). No class 2
  accounts are configured.
- A product is a model ("Desk 120 cm", "HP ProBook 450"); each physical unit is
  a serial (`stock.lot`). The serial is what the label carries.
- Serial naming: a company sequence, e.g. `PAT-000123`, offered when serials
  are generated at receipt (builder's call on the exact mechanism).
- Fit-out works ("aménagement") are investments on the purchase side but are
  services, not inventory items.

### 5.2 Rooms
- A dedicated internal location tree **Patrimoine / <Building> / <Room>**,
  **outside WH/Stock** so no POS/restaurant route or availability ever sees
  these items.
- One building location per `maintenance.building`, created and renamed
  automatically (including existing buildings at install). Rooms are created
  by hand under them (no room model exists).
- A location "Patrimoine / À affecter" for received items not yet placed.

### 5.3 Receiving and moving
- What makes an item Patrimoine is its **product category**, not the order's
  type: a chair bought on a usual order is still Patrimoine, toner on an
  investment order is not. My call: a putaway rule on the Patrimoine category
  sends received units to "À affecter"; receipts ask for one serial per unit
  (standard serial tracking).
- The magasinier moves each unit to its room with an internal transfer. Later
  moves (room to room, out for repair) are internal transfers too, so each
  serial keeps its full history (standard lot traceability).
- From a room or a serial, one can see what is where (standard quant views
  filtered on the Patrimoine tree; add a menu "Patrimoine" under Inventory).

### 5.4 Labels
- Print labels from serials with the standard lot/serial label report; the
  encoded content is the serial name so barcode or QR both work. If the
  standard report only offers one symbology, that is acceptable for now.
- Scanning = a scanner or phone typing into the serial field like a keyboard.

### 5.5 Annual inventory
- Standard physical inventory (`stock.quant`, inventory mode), filtered by
  room. Each serial is a quant of 1: found → counted 1; missing → 0; found in
  another room → recorded in the room where it is found, the old one counted 0.
- Set the annual count frequency on the Patrimoine locations
  (`cyclic_inventory_frequency` = 365) so the next count date shows.
- Counting: Inventory User (magasinier). Applying differences: Inventory
  Administrator (the stock manager / purchasing officer).

### 5.6 Initial load
Existing items must be tagged once. Provide a CSV template + import script
(same pattern as `tools/import_seed_catalogue.py`: one savepoint per row,
creates product if missing, serial, quant in the room). Collecting the data is
HIS's job.

## 6. Rules carried over
- English source strings + `i18n/fr.po` for every module touched.
- Roles go to positions, not users.
- Tests through `Form` under the real role for anything a user saves
  (lesson of 2026-10-19), plus: usual request never reaches the director;
  investment request needs the director; the officer cannot relabel a
  director-approved investment as usual; order at +20 % passes the officer,
  at +21 % is refused to him; split orders cannot bypass; patrimoine items
  never appear in WH/Stock availability.

## 7. After deployment (Mohamed)
- Give the Requester role to the Responsable positions, remove it elsewhere.
- Create rooms under each building.
- Decide barcode vs QR if the standard label is not enough.
- Find out the réforme process → separate design.
