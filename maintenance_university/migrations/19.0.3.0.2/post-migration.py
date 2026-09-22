"""Audit S-7 : oublie les mots de passe temporaires qui ont deja servi.

Desormais la premiere connexion les efface (res_users._update_last_login). Ceux
d'avant restent en clair : on efface ceux des ouvriers qui se sont deja
connectes au moins une fois. Les autres gardent le leur, sinon le responsable
ne pourrait plus le leur remettre.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE hr_employee e
           SET initial_password = NULL
         WHERE e.initial_password IS NOT NULL
           AND EXISTS (SELECT 1 FROM res_users_log l WHERE l.create_uid = e.user_id)
        """
    )
    _logger.info("S-7 : %s mot(s) de passe temporaire(s) deja utilise(s) efface(s)", cr.rowcount)
