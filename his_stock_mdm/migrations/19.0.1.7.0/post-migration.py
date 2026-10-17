"""Des especes au Restaurant et au Copy Center (recette P-15), un role par
caisse (recette P-18).

Les caisses sont en noupdate : leur role est pose ici. Pour ne fermer la caisse
a personne le jour du deploiement, chaque utilisateur POS d'aujourd'hui recoit
les trois roles ; on les retire ensuite poste par poste.
"""

import logging

from odoo import SUPERUSER_ID, Command, api
from odoo.addons.his_stock_mdm import CAISSES, donner_especes

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    donner_especes(env)
    roles = env["res.groups"]
    for xmlid in CAISSES:
        caisse = env.ref(f"his_stock_mdm.{xmlid}", raise_if_not_found=False)
        role = env.ref(f"his_stock_mdm.group_{xmlid.replace('pos_config_', 'caisse_')}")
        roles |= role
        if caisse and not caisse.his_group_ids:
            caisse.his_group_ids = [Command.set(role.ids)]
    caissiers = env.ref("point_of_sale.group_pos_user").all_user_ids.filtered(
        lambda u: not u.share and not u.has_group("point_of_sale.group_pos_manager")
    )
    caissiers.write({"group_ids": [Command.link(role.id) for role in roles]})
    _logger.info(
        "Roles de caisse donnes a %d utilisateur(s) POS existant(s) : %s", len(caissiers), caissiers.mapped("login")
    )
