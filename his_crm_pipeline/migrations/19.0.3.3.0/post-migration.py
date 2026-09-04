# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Referme les motifs de perte anglais sur une base deja installee.

Le post_init_hook ne joue qu'a l'installation. Sur une base existante, c'est ce
script qui applique la meme decision — et la meme fonction, pour que les deux
chemins ne puissent pas diverger. Voir hooks.py pour le pourquoi du code
imperatif.
"""
from odoo import SUPERUSER_ID, api

from odoo.addons.his_crm_pipeline.hooks import desactiver_motifs_natifs


def migrate(cr, version):
    if not version:
        return
    desactiver_motifs_natifs(api.Environment(cr, SUPERUSER_ID, {}))
