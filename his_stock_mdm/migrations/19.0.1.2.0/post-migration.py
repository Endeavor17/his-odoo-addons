"""Resserre le perimetre des caisses sur les regles metier reelles.

La version 19.0.1.1.0 avait ouvert le Restaurant aux boissons, biscuits et
divers, et le Copy Center aux boissons. C'etait une supposition, et elle etait
fausse : le Restaurant ne sert QUE des repas, et rien de comestible ne se vend
au Copy Center, qui ne propose que des fournitures d'etude et encaisse les
recharges de compte.

On ne retire que les categories que ce module avait lui-meme posees a tort. Un
onglet ajoute par un autre module -- Repas, Recharges -- ou par l'exploitant
n'est pas touche.
"""

from odoo import SUPERUSER_ID, api

A_RETIRER = {
    "his_stock_mdm.pos_config_restaurant": [
        "pos_categ_boissons",
        "pos_categ_biscuits",
        "pos_categ_divers",
    ],
    "his_stock_mdm.pos_config_copy_center": [
        "pos_categ_boissons",
    ],
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for config_xmlid, categories in A_RETIRER.items():
        config = env.ref(config_xmlid, raise_if_not_found=False)
        if not config:
            continue
        for name in categories:
            categ = env.ref("his_stock_mdm." + name, raise_if_not_found=False)
            if categ and categ in config.iface_available_categ_ids:
                config.write({"iface_available_categ_ids": [(3, categ.id)]})
