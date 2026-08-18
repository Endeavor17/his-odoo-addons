# -*- coding: utf-8 -*-

from . import models
from . import wizard


def post_init_hook(env):
    """Give every pre-existing employee an institutional ID.

    The field is added by this module, so employees created before the install
    have no value. The unique index tolerates NULLs, but leaving them empty
    would make the ID unreliable, so backfill them once at install time.
    """
    employees = env['hr.employee'].sudo().with_context(active_test=False).search(
        [('matricule_institutionnel', '=', False)]
    )
    sequence = env['ir.sequence'].sudo()
    for employee in employees:
        employee.matricule_institutionnel = sequence.next_by_code(
            'hr.employee.matricule.institutionnel'
        )

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
