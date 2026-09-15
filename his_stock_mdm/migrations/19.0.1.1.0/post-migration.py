"""Applique le perimetre de caisse aux bases ou les pos.config existent deja.

Les trois pos.config sont crees en `noupdate="1"` : le drapeau est stocke sur
ir.model.data, donc une fois l'enregistrement cree, AUCUN fichier de donnees ne
peut plus le modifier — pas meme un bloc sans noupdate. C'est voulu : la
configuration d'une caisse (journaux, moyens de paiement) appartient a
l'exploitant une fois posee.

Le perimetre de categories, lui, doit exister pour que les caisses soient
utilisables. Les installations neuves le recoivent par pos_config_data.xml ;
les bases deja installees passent par ici, une seule fois.

Volontairement non destructif : on ajoute les onglets manquants sans retirer
ceux que l'exploitant aurait ajoutes, et on ne touche pas a une caisse qui
restreint deja ses categories de son propre chef.
"""

from odoo import SUPERUSER_ID, api

PERIMETRES = {
    "his_stock_mdm.pos_config_cafeteria": [
        "pos_categ_boissons",
        "pos_categ_snacks",
        "pos_categ_chocolat",
        "pos_categ_biscuits",
        "pos_categ_bonbons",
        "pos_categ_divers",
    ],
    "his_stock_mdm.pos_config_restaurant": [
        "pos_categ_boissons",
        "pos_categ_biscuits",
        "pos_categ_divers",
    ],
    "his_stock_mdm.pos_config_copy_center": [
        "pos_categ_fournitures",
        "pos_categ_boissons",
    ],
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for config_xmlid, categories in PERIMETRES.items():
        config = env.ref(config_xmlid, raise_if_not_found=False)
        if not config:
            continue
        manquantes = env["pos.category"]
        for name in categories:
            categ = env.ref("his_stock_mdm." + name, raise_if_not_found=False)
            if categ and categ not in config.iface_available_categ_ids:
                manquantes |= categ
        if manquantes:
            config.write(
                {
                    "limit_categories": True,
                    "iface_available_categ_ids": [(4, c.id) for c in manquantes],
                }
            )
