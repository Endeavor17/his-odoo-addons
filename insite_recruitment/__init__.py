from odoo.addons.campus_teacher_management import _campus_grant_manager_process_permissions

from . import models
from . import wizard


def _insite_grant_manager_process_permissions(env):
    """Extend the Campus+ Manager permission grant over the InSite processes.

    campus_teacher_management runs the same grant in its own post_init_hook,
    but that fires when *it* finishes installing — at which point this module's
    six processes (data/insite_process_data.xml) do not exist yet. Since the
    permission matrix is opt-in (no row at all means denied, see
    campus.process.permission._has_process_permission), without this hook every
    InSite action raises AccessError for everyone except the uid-1 superuser —
    admin included, which locks the module the moment it is installed.

    The campus grant is idempotent (it skips user/process pairs that already
    have a row), so re-running it here only fills in the new processes.
    """
    _campus_grant_manager_process_permissions(env)
