{
    "name": "HIS Meal Management",
    "version": "19.0.3.9.0",
    "summary": "HIS person identity, meal cards, prepaid meal plans and credit consumption at the POS",
    "description": """
HIS Meal Management
===================
Prepaid meal credits: the IT centre sells the plans, and any food point of sale
serves meals against the balance.

Two meals at two prices share one wallet. A 300 DA meal costs half a credit and
a 600 DA meal costs one, so the six packages - 1 500 / 6 000 / 18 000 DA in the
300 tier and 3 000 / 12 000 / 36 000 DA in the 600 tier - all buy from the same
balance at the same rate for a given duration: 500, 480 or 450 DA per credit.
Credits do not expire; they keep until they are eaten.

* Identity belongs to his_person_core: the person record, the matricule
  institutionnel and its sequence are all its business, not this module's.
  The academic attributes (rang_academique, specialite, the Person/Faculty
  referential) come from his_academic_base; the six faculties are seeded here.
* The wallet stays on res.partner, because that is what the card's barcode
  resolves to and what the POS sells to. Every his.person carries one, so a
  balance reads straight off a person record through delegation.
* No wallet without an identity: a card and a subscription both refuse a
  partner carrying no his.person, so a plain contact cannot hold credits.
* At the till a person is identified by the card they tap, so anyone holding a
  card can eat, whatever their role. The matricule gates nothing.
* The card carries only an identifier. Credits and history live in Odoo, so a
  lost card is replaced without losing a single credit.
* A meal plan is an ordinary product carrying a credit count and a validity, so
  pricing, payment, invoicing and accounting stay stock Odoo. A meal is the
  mirror of it: an ordinary product carrying the credits it costs to serve.
* What a meal COSTS is a property of the meal and not of the shop, so one till
  can serve several meals at different prices and none of them needs a per-shop
  field. WHERE a meal may be served is configured, however, since his_stock_mdm
  19.0.1.2.0 gave each till a category scope: the Copy Center sells the plans
  and nothing edible, while the Cafeteria and the Restaurant both serve meals.
  The scope says where; the product still says how much.
* Credits move on the server when a POS order is saved, never in the browser:
  a cashier cannot grant, edit or invent credits.
* A negative balance is impossible at the database level, not merely refused in
  Python.
* Every grant and every meal writes an append-only ledger line naming the
  student, card, plan, cashier, session and the balance it left behind.
""",
    "author": "Abdo Chabouti",
    "category": "Sales/Point of Sale",
    "license": "LGPL-3",
    "post_init_hook": "post_init_hook",
    "depends": [
        "base",
        "product",
        "point_of_sale",
        # Identity is not ours: his_person_core owns the person record and the
        # only sequence allowed to issue a matricule institutionnel.
        "his_person_core",
        # his.faculty and the academic fields moved there (19.0.3.5.0).
        "his_academic_base",
        # The plans are sold at the tills his_stock_mdm defines, and their POS
        # tab has to sit alongside its retail ones. The coupling already
        # existed through available_in_pos; declaring it makes the load order
        # explicit instead of accidental.
        "his_stock_mdm",
    ],
    "data": [
        "security/meal_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/his_faculty.xml",
        "data/barcode_rule.xml",
        "data/meal_plans.xml",
        "data/ir_cron.xml",
        "wizard/meal_adjust_wizard_views.xml",
        "views/meal_card_views.xml",
        "views/meal_subscription_views.xml",
        "views/meal_transaction_views.xml",
        "views/his_person_views.xml",
        "views/res_partner_views.xml",
        "views/product_template_views.xml",
        "report/meal_card_report.xml",
        "views/menus.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "his_meal_management/static/src/app/**/*",
        ],
        "web.assets_backend": [
            "his_meal_management/static/src/backend/**/*",
        ],
        "web.assets_tests": [
            "his_meal_management/static/tests/tours/**/*",
        ],
    },
    "installable": True,
    "application": True,
}
