# -*- coding: utf-8 -*-

from . import models
from . import wizard


def post_init_hook(env):
    """Neutralise les regles de visibilite natives de Maintenance.

    Le backfill des matricules institutionnels a ete retire d'ici : ce module
    ne possede plus le champ ni sa sequence. L'emission et la reprise sont
    assurees par les hooks d'installation de his_hr_base, qui rattachent chaque
    employe a sa fiche his.person (source unique : his_person_core).
    """
    # Core Maintenance's own default rules (follower/owner/technician can see)
    # leak visibility beyond our own Worker rule — verified live: a Worker who
    # merely follows a request they're not assigned to could see it, since
    # ir.rule domains across a user's groups combine with OR. Both rules are
    # noupdate="1" in maintenance's own data, so an XML override from this
    # module would be silently ignored — only a direct ORM write gets past
    # that.
    rule_xmlids = ['maintenance.equipment_request_rule_user', 'maintenance.equipment_rule_user']
    for xmlid in rule_xmlids:
        rule = env.ref(xmlid, raise_if_not_found=False)
        if rule:
            rule.sudo().active = False
