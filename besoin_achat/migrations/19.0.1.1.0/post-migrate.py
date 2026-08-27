# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    sequence = env['ir.sequence'].search([('code', '=', 'university.besoin.achat')])
    if sequence and sequence.prefix != 'BO':
        sequence.write({'prefix': 'BO', 'padding': 4, 'number_next': 1})
        _logger.info(
            "besoin_achat: séquence 'university.besoin.achat' basculée sur "
            "le préfixe BO (padding 4, redémarrage à 1). Les références "
            "existantes ne sont pas modifiées.")
