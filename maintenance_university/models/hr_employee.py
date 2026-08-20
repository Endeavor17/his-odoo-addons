from dateutil.relativedelta import relativedelta

from odoo import api, models, fields


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # HR/the Administrator sets this — it may be backdated (a hire entered
    # late) or in the future (hired now, starting later). It's what the
    # institutional ID's year is generated from, not the record's create date.
    date_start_working = fields.Date(
        string="Start Date",
        default=fields.Date.context_today,
        help="When this employee starts working — determines the year in their institutional ID.",
    )

    # Computed rather than a plain inverse Many2many field: a request's
    # employee_ids is a Many2many, so there's no single "the" inverse field
    # name to pair against — this just searches for it directly instead.
    maintenance_request_ids = fields.Many2many(
        'maintenance.request', string="Maintenance Requests",
        compute='_compute_maintenance_request_ids',
    )
    maintenance_hours_this_month = fields.Float(
        string="Hours This Month", compute='_compute_maintenance_monthly_stats'
    )
    maintenance_requests_done_this_month = fields.Integer(
        string="Tasks Done This Month", compute='_compute_maintenance_monthly_stats'
    )
    maintenance_findings_logged_this_month = fields.Integer(
        string="Findings Logged This Month", compute='_compute_maintenance_monthly_stats'
    )
    maintenance_findings_critical_this_month = fields.Integer(
        string="Critical/High Findings This Month", compute='_compute_maintenance_monthly_stats'
    )

    # `groups=` is an ORM-level restriction, not just a view one: a Worker
    # user can't read this field at all, even via a direct API call.
    initial_password = fields.Char(
        string="Temporary Password", copy=False,
        groups="maintenance_university.group_maintenance_manager",
    )
    login = fields.Char(related='user_id.login', string="Login", store=False)

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        # An employee created outside the Create Workers wizard (e.g. the
        # standard Employees form) gets a user account with no maintenance
        # group at all — invisible to our menu security, so they'd log in to
        # a completely blank home screen. Default any such account to Worker,
        # the least-privileged role, rather than leaving it with no access.
        # Skipped if they already have a group (e.g. deliberately made a
        # Manager) — Manager already implies Worker, so this never downgrades.
        # Also skipped for a Reporter: that's a sibling role, not a lesser
        # one — without this check, giving someone an hr.employee record
        # after setting them up as a Reporter would silently also make them
        # a Worker (assignable to real maintenance work), which they aren't.
        worker_group = self.env.ref('maintenance_university.group_maintenance_worker')
        for employee in employees:
            user = employee.sudo().user_id
            if user and not (
                user.has_group('maintenance_university.group_maintenance_worker')
                or user.has_group('maintenance_university.group_maintenance_reporter')
            ):
                user.sudo().write({'group_ids': [(4, worker_group.id)]})
        return employees

    @api.depends()
    def _compute_maintenance_request_ids(self):
        Request = self.env['maintenance.request']
        for employee in self:
            employee.maintenance_request_ids = Request.search([('employee_ids', 'in', employee.id)])

    @api.depends()
    def _compute_maintenance_monthly_stats(self):
        # Not stored: "this month" is a moving window, so it's always
        # recomputed fresh from the source records rather than kept in sync.
        month_start = fields.Date.context_today(self).replace(day=1)
        month_start_dt = fields.Datetime.to_datetime(month_start)
        next_month_dt = month_start_dt + relativedelta(months=1)
        Request = self.env['maintenance.request']
        Time = self.env['maintenance.university.request.time']
        Finding = self.env['maintenance.university.finding']
        for employee in self:
            employee.maintenance_requests_done_this_month = Request.search_count([
                ('employee_ids', 'in', employee.id),
                ('state', '=', 'done'),
                ('date_end', '>=', month_start_dt),
                ('date_end', '<', next_month_dt),
            ])
            time_logs = Time.search([
                ('employee_id', '=', employee.id),
                ('date_start', '>=', month_start_dt),
                ('date_start', '<', next_month_dt),
            ])
            employee.maintenance_hours_this_month = sum(time_logs.mapped('duration'))
            employee.maintenance_findings_logged_this_month = Finding.search_count([
                ('employee_id', '=', employee.id),
                ('found_date', '>=', month_start_dt),
                ('found_date', '<', next_month_dt),
            ])
            employee.maintenance_findings_critical_this_month = Finding.search_count([
                ('employee_id', '=', employee.id),
                ('severity', 'in', ('high', 'critical')),
                ('found_date', '>=', month_start_dt),
                ('found_date', '<', next_month_dt),
            ])
