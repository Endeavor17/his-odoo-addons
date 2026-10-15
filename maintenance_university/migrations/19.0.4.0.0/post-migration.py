"""Rattache l'historique du chatter au nouveau champ.

Le suivi (tracking) des changements de categorie a ete enregistre sous
category_id, qui designait alors nos categories. Ce champ redevient celui du
coeur, sans suivi : ces lignes appartiennent desormais a maintenance_category_id.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE mail_tracking_value tv
           SET field_id = nouveau.id
          FROM ir_model_fields ancien, ir_model_fields nouveau
         WHERE tv.field_id = ancien.id
           AND ancien.model = 'maintenance.request'
           AND ancien.name = 'category_id'
           AND nouveau.model = 'maintenance.request'
           AND nouveau.name = 'maintenance_category_id'
        """
    )
    _logger.info("%s ligne(s) d'historique rattachee(s) a maintenance_category_id", cr.rowcount)
