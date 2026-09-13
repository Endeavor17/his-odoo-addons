"""Met en vente les articles de caisse deja prices (MDM regle 3 bis).

Avant la 1.4.0, saisir un prix sur un article importe en sale_ok=False ne le
rendait pas vendable : il restait invisible en caisse. La regle est desormais
appliquee par write() ; cette passe rattrape les prix saisis avant elle
(INV-001670 au 2026-09-13).

Par l'ORM et non en SQL : write_date doit bouger, c'est ce qui signale le
changement aux caisses.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    a_vendre = env['product.template'].search([
        ('available_in_pos', '=', True),
        ('sale_ok', '=', False),
        ('list_price', '>', 0),
    ])
    if a_vendre:
        a_vendre.write({'sale_ok': True})
    _logger.info("MDM regle 3 bis : %d article(s) de caisse mis en vente %s",
                 len(a_vendre), a_vendre.mapped('default_code'))
