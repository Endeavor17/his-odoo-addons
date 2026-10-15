"""Rattachement des onglets du menu aux caisses, et TVA des plats.

Un hook et pas un enregistrement de donnees : les pos.config appartiennent a
his_stock_mdm, en noupdate, donc aucun fichier de ce module ne peut les ecrire
(meme raison que his_meal_management/hooks.py).
"""

from odoo import Command

ONGLETS = ("pos_categ_starters", "pos_categ_mains", "pos_categ_sides")
CAISSES = ("his_stock_mdm.pos_config_cafeteria", "his_stock_mdm.pos_config_restaurant")


def lier_onglets(env):
    onglets = env["pos.category"].browse([env.ref(f"his_pos_menu.{x}").id for x in ONGLETS])
    for xmlid in CAISSES:
        config = env.ref(xmlid, raise_if_not_found=False)
        if config and onglets - config.iface_available_categ_ids:
            config.write({"limit_categories": True, "iface_available_categ_ids": [Command.link(o.id) for o in onglets]})


def taxer_plats(env):
    """Les plats naissent sans taxe (menu_data.xml) : le prix du menu est le prix paye.

    La taxe par defaut d'une societe dz est « 19 % production » HORS taxe : la
    laisser poser aurait vendu un plat a 300 DA pour 357. On ne pose donc que
    une taxe COMPRISE dans le prix — celle que his_pos_tva met en defaut. Si
    his_pos_tva arrive apres, son propre hook taxe les plats restes sans taxe.
    """
    taxe = env.company.account_sale_tax_id
    if taxe and taxe.price_include:
        plats = env["product.template"].search([("categ_id", "=", env.ref("his_pos_menu.product_category_menu").id)])
        plats.filtered(lambda p: not p.taxes_id).write({"taxes_id": [Command.set(taxe.ids)]})


def post_init_hook(env):
    lier_onglets(env)
    taxer_plats(env)
