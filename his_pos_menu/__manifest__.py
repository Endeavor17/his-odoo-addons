# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "POS - Restaurant Menu",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "summary": "The caterer's daily menu, sold for cash at the Cafeteria and the Restaurant",
    "description": """
Menu du traiteur recu le 2026-10-14 : 23 plats en trois onglets de caisse
(Starters, Main Courses, Sides), aux prix du menu, TVA comprise.

  - Cash seulement : aucun plat ne porte de cout en credits. Le repas
    d'abonnement reste le produit repas de his_meal_management.
  - Meme menu a la Cafeteria et au Restaurant : les trois onglets sont
    rattaches aux deux caisses par le hook d'installation.
  - Un plat se prepare sur place : produit non stocke, la vente ne decremente
    aucun stock (les ingredients se suivent par inventaire hebdomadaire).
  - Noms sources en anglais, francais et arabe dans i18n/ (regle du
    2026-10-08) ; « Pasta / Rice Salad » et consorts restent UNE touche.
  - noupdate : prix et libelles appartiennent a l'exploitant une fois crees.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": [
        "point_of_sale",
        "his_stock_mdm",
    ],
    "data": [
        "data/menu_data.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
