from odoo import SUPERUSER_ID, api
from odoo.addons.his_pos_tva.hooks import post_init_hook


def migrate(cr, version):
    # Les plats des formules etaient restes a 19 % (recette P-09) : on rejoue le balayage.
    post_init_hook(api.Environment(cr, SUPERUSER_ID, {}))
