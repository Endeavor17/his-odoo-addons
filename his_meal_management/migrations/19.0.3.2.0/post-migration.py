"""Donne aux forfaits et aux repas leur onglet de caisse, sur les bases ou ils
existent deja.

Les produits sont crees en `noupdate="1"` : leur pos_categ_ids ajoute dans
meal_plans.xml ne s'applique donc qu'aux installations neuves. Sans onglet, un
produit disparait de toute caisse qui restreint ses categories — c'est-a-dire
les trois, depuis his_stock_mdm 19.0.1.1.0. La recharge de compte deviendrait
invendable.

Meme raison pour le rattachement de l'onglet aux caisses : les pos.config sont
en noupdate cote his_stock_mdm.
"""
from odoo import api, SUPERUSER_ID

# La ou l'etudiant recharge son compte, et la ou il mange.
CAISSES = ['his_stock_mdm.pos_config_copy_center', 'his_stock_mdm.pos_config_restaurant']


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    categ = env.ref('his_meal_management.pos_categ_repas', raise_if_not_found=False)
    if not categ:
        return

    # Les produits du module : forfaits prepayes et repas servis.
    produits = env['product.template'].search([
        '|', ('meal_credits', '>', 0), ('meal_credit_cost', '>', 0),
    ])
    a_taguer = produits.filtered(lambda p: categ not in p.pos_categ_ids)
    if a_taguer:
        a_taguer.write({
            'available_in_pos': True,
            'pos_categ_ids': [(4, categ.id)],
        })

    for xmlid in CAISSES:
        config = env.ref(xmlid, raise_if_not_found=False)
        if config and categ not in config.iface_available_categ_ids:
            config.write({'iface_available_categ_ids': [(4, categ.id)]})
