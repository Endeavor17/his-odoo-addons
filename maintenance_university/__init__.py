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
