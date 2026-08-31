from . import models
from . import wizard
from . import controllers


def _campus_grant_manager_process_permissions(env):
    """Give every current Campus+ Manager full access to every process.

    Runs once at install so the very first upgrade doesn't lock the admin out
    of a module now gated by campus.process.permission — nothing here is
    user-specific, it's driven entirely by group membership at install time.
    Managers configure everyone else's matrix afterwards from Configuration >
    Process Permissions.
    """
    managers = env.ref('campus_teacher_management.group_campus_manager').user_ids
    processes = env['campus.process'].search([])
    if not managers or not processes:
        return
    Permission = env['campus.process.permission']
    existing = Permission.search([
        ('user_id', 'in', managers.ids), ('process_id', 'in', processes.ids),
    ])
    existing_pairs = {(perm.user_id.id, perm.process_id.id) for perm in existing}
    Permission.create([
        {
            'user_id': user.id,
            'process_id': process.id,
            'can_view': True,
            'can_execute': True,
            'can_validate': True,
        }
        for user in managers
        for process in processes
        if (user.id, process.id) not in existing_pairs
    ])
