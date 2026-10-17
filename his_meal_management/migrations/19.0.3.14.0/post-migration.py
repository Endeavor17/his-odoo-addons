"""Les formules du traiteur remplacent « Meal 300 » et « Meal 600 » (2026-10-15).

Les produits sont en noupdate : le fichier de donnees n'archive les deux repas
generiques que sur une base neuve, d'ou cette migration. On ecrit `active`
directement et non par action_archive : celle-ci refuse tant qu'une caisse est
ouverte, et une caisse ouverte se contente de les garder jusqu'a son
rechargement.

L'onglet « Meals » quitte la Cafeteria : il est desormais celui du Restaurant,
la Cafeteria a « Meal Packs ». Le hook n'enleve jamais un onglet, d'ou le
retrait ici.
"""

from odoo import SUPERUSER_ID, api
from odoo.addons.his_meal_management.hooks import lier_categories_pos, taguer_produits


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in ("product_meal_300", "product_daily_meal"):
        produit = env.ref(f"his_meal_management.{xmlid}", raise_if_not_found=False)
        if produit:
            produit.write({"active": False})

    repas = env.ref("his_meal_management.pos_categ_repas", raise_if_not_found=False)
    cafeteria = env.ref("his_stock_mdm.pos_config_cafeteria", raise_if_not_found=False)
    if repas and cafeteria and repas in cafeteria.iface_available_categ_ids:
        cafeteria.write({"iface_available_categ_ids": [(3, repas.id)]})

    lier_categories_pos(env)
    taguer_produits(env)
