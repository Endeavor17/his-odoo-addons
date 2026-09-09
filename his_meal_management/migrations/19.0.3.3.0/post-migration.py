"""Applique aux bases existantes ce que post_init_hook fait a l'installation.

Reprend la separation Repas / Recharges : jusqu'ici les deux partageaient un
onglet unique, ce qui mettait les recharges sur la caisse du Restaurant et les
repas sur celle du Copy Center. Aucune des deux n'y a sa place.
"""
from odoo import api, SUPERUSER_ID

from odoo.addons.his_meal_management.hooks import lier_categories_pos, taguer_produits


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    lier_categories_pos(env)
    taguer_produits(env)

    # L'onglet fusionne « Repas & Recharges » n'a plus d'objet : ses produits
    # portent desormais l'un des deux nouveaux. On le retire des caisses sans
    # supprimer l'enregistrement, au cas ou l'exploitant y aurait mis autre chose.
    repas = env.ref('his_meal_management.pos_categ_repas', raise_if_not_found=False)
    if repas:
        if repas.name == 'Repas & Recharges':
            repas.name = 'Repas'
        # L'onglet fusionne avait mis les repas sur la caisse des recharges.
        copy_center = env.ref('his_stock_mdm.pos_config_copy_center', raise_if_not_found=False)
        if copy_center and repas in copy_center.iface_available_categ_ids:
            copy_center.write({'iface_available_categ_ids': [(3, repas.id)]})
