"""Le menu du traiteur quitte la Cafeteria, qui recoit le sien (2026-10-17).

Le hook ne fait qu'ajouter : retirer les trois onglets du traiteur de la
Cafeteria se fait ici, une fois. Puis les onglets de la Cafeteria sont
rattaches et ses articles taxes comme ceux du traiteur.
"""

from odoo import SUPERUSER_ID, Command, api
from odoo.addons.his_pos_menu.hooks import ONGLETS, lier_onglets, taxer_plats


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cafeteria = env.ref("his_stock_mdm.pos_config_cafeteria", raise_if_not_found=False)
    if cafeteria:
        traiteur = [env.ref(f"his_pos_menu.{x}").id for x in ONGLETS["his_stock_mdm.pos_config_restaurant"]]
        cafeteria.write({"iface_available_categ_ids": [Command.unlink(i) for i in traiteur]})
    lier_onglets(env)
    taxer_plats(env)
