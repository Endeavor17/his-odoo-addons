"""Le Restaurant vend aussi les boissons (Mohamed, 2026-10-27).

Stock unique : les boissons sont livrees aux caisses (emplacement Cafeteria)
et le personnel en porte au congelateur du Restaurant sans transfert. La caisse
du Restaurant gagne l'onglet Boissons et ses ventes sortent du meme stock ; le
Restaurant ne vend rien d'autre en stock (repas et plats ne sont pas stockes).
Caisse et type d'operation sont en noupdate : poses ici.
"""

from odoo import SUPERUSER_ID, Command, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    restaurant = env.ref("his_stock_mdm.pos_config_restaurant", raise_if_not_found=False)
    boissons = env.ref("his_stock_mdm.pos_categ_boissons", raise_if_not_found=False)
    if restaurant and boissons and boissons not in restaurant.iface_available_categ_ids:
        restaurant.write({"limit_categories": True, "iface_available_categ_ids": [Command.link(boissons.id)]})
    ventes = env.ref("his_stock_mdm.picking_type_pos_restaurant", raise_if_not_found=False)
    if ventes:
        ventes.default_location_src_id = env.ref("his_stock_mdm.loc_cafeteria")
