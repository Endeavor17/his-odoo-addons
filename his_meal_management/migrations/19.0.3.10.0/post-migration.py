"""Des noms que le caissier comprend sans explication.

« Meal 600 » ne disait pas qu'un meme produit se sert sur credits OU se vend
en especes, et « Pack 600 - Weekly » ne disait pas que c'est l'abonnement
qu'on recharge. Les produits sont en noupdate : le fichier de donnees ne
renomme que les bases neuves, d'ou cette migration.

Un produit deja renomme a la main garde son nom : on ne remplace que l'ancien
nom par defaut.
"""

from odoo import SUPERUSER_ID, api

NOMS = {
    "product_meal_300": ("Meal 300", "Meal 300 (credits or cash)"),
    "product_daily_meal": ("Meal 600", "Meal 600 (credits or cash)"),
    "product_plan_300_weekly": ("Pack 300 - Weekly (6 meals)", "Meal subscription 300 - 6 meals (weekly)"),
    "product_plan_300_monthly": ("Pack 300 - Monthly (25 meals)", "Meal subscription 300 - 25 meals (monthly)"),
    "product_plan_300_semester": ("Pack 300 - Semesterly (80 meals)", "Meal subscription 300 - 80 meals (semester)"),
    "product_plan_weekly": ("Pack 600 - Weekly (6 meals)", "Meal subscription 600 - 6 meals (weekly)"),
    "product_plan_monthly": ("Pack 600 - Monthly (25 meals)", "Meal subscription 600 - 25 meals (monthly)"),
    "product_plan_semester": ("Pack 600 - Semesterly (80 meals)", "Meal subscription 600 - 80 meals (semester)"),
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {"lang": "en_US"})
    for xmlid, (ancien, nouveau) in NOMS.items():
        produit = env.ref(f"his_meal_management.{xmlid}", raise_if_not_found=False)
        if produit and produit.name == ancien:
            produit.name = nouveau
