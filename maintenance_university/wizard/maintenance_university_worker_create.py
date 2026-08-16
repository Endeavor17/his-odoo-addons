import secrets
import string

from odoo import fields, models, _
from odoo.exceptions import UserError

# Excludes visually ambiguous characters (0/O, 1/l/I) since these get
# hand-copied or read aloud when handing a worker their login.
_PASSWORD_ALPHABET = ''.join(c for c in string.ascii_letters + string.digits if c not in '0OoIl1')


def _generate_password(length=12):
    return ''.join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


class MaintenanceUniversityWorkerCreate(models.TransientModel):
    _name = 'maintenance.university.worker.create'
    _description = 'Create Workers'

    line_ids = fields.One2many(
        'maintenance.university.worker.create.line', 'wizard_id', string="Workers"
    )

    def action_create_workers(self):
        self.ensure_one()
        if not self.env.user.has_group('maintenance_university.group_maintenance_manager'):
            raise UserError(_("Only a manager can create workers."))
        if not self.line_ids:
            raise UserError(_("Add at least one worker before creating."))

        worker_group = self.env.ref('maintenance_university.group_maintenance_worker')
        # Creating user accounts and employee records both need elevated
        # rights our Manager group deliberately doesn't have (that's core
        # Odoo's own protection, not something to weaken) — the has_group()
        # check above is the real gate; sudo() here only unlocks the specific
        # privileged calls it just authorized.
        Employee = self.env['hr.employee'].sudo()
        Users = self.env['res.users'].sudo()

        for line in self.line_ids:
            if line.employee_id:
                continue  # already processed (wizard reopened after a partial run)
            # The Manager/Administrator can type their own password for this
            # worker; leaving it blank keeps the old auto-generate behavior.
            password = line.password or _generate_password()
            user = Users.create({
                'name': line.name,
                'login': line.login,
                'password': password,
                'group_ids': [(6, 0, [worker_group.id])],
                # Explicit, not inherited from context: a new user's default
                # language falls back to whatever's on the session context,
                # which isn't reliably the creating Manager's own language
                # for a button-triggered server action.
                # ar_DZ, not ar_001: Odoo's web client hardcodes Arabic-Indic
                # digits specifically for ar-sa/ar-sy/ar-001 (see
                # localization_service.js NUMBERING_SYSTEMS) — ar_DZ isn't
                # in that list, so dates render with plain 0-9 digits.
                'lang': 'ar_DZ',
            })
            employee = Employee.create({
                'name': line.name,
                'user_id': user.id,
                'initial_password': password,
                'date_start_working': line.date_start_working,
            })
            line.write({
                'employee_id': employee.id,
                'password': password,
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class MaintenanceUniversityWorkerCreateLine(models.TransientModel):
    _name = 'maintenance.university.worker.create.line'
    _description = 'Create Workers - Line'

    wizard_id = fields.Many2one(
        'maintenance.university.worker.create', required=True, ondelete='cascade'
    )
    name = fields.Char(string="Name", required=True)
    login = fields.Char(string="Login", required=True)
    date_start_working = fields.Date(string="Start Date", default=fields.Date.context_today)
    employee_id = fields.Many2one('hr.employee', string="Employee", readonly=True, copy=False)
    password = fields.Char(string="Password", copy=False)
