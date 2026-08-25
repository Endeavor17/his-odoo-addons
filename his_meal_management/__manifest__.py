{
    'name': 'HIS Meal Management',
    'version': '19.0.2.2.0',
    'summary': 'HIS person identity, meal cards, prepaid meal plans and credit consumption at the POS',
    'description': """
HIS Meal Management
===================
Prepaid meal credits, driven from two Point of Sale points: the IT centre sells
the plans, the restaurant consumes the credits.

* Identity belongs to his_person_core: the person record, the matricule
  institutionnel and its sequence are all its business, not this module's.
  Added here are only the academic attributes the meal service needs -
  rang_academique, specialite, and the many-to-many Person/Faculty referential.
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
  pricing, payment, invoicing and accounting stay stock Odoo.
* Credits move on the server when a POS order is saved, never in the browser:
  a cashier cannot grant, edit or invent credits.
* A negative balance is impossible at the database level, not merely refused in
  Python.
* Every grant and every meal writes an append-only ledger line naming the
  student, card, plan, cashier, session and the balance it left behind.
* The Restaurant point of sale is pointed at the student meal automatically
  when his_stock_mdm created it, without either module depending on the other.
""",
    'author': 'Abdo Chabouti',
    'category': 'Sales/Point of Sale',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'product',
        'point_of_sale',
        # Identity is not ours: his_person_core owns the person record and the
        # only sequence allowed to issue a matricule institutionnel.
        'his_person_core',
    ],

    'data': [
        'security/meal_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/his_faculty.xml',
        'data/barcode_rule.xml',
        'data/meal_plans.xml',
        'data/ir_cron.xml',
        'wizard/meal_adjust_wizard_views.xml',
        'views/meal_card_views.xml',
        'views/meal_subscription_views.xml',
        'views/meal_transaction_views.xml',
        'views/his_person_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/pos_config_views.xml',
        'report/meal_card_report.xml',
        'views/menus.xml',
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            'his_meal_management/static/src/app/**/*',
        ],
    },

    'post_init_hook': 'post_init_hook',

    'installable': True,
    'application': True,
}
