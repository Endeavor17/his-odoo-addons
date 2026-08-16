from dateutil.relativedelta import relativedelta

from odoo import api, models, fields


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # Not `required=True`: the value is generated in create(), so a NOT NULL
    # constraint would only break the web client (a readonly field is empty in
    # the form until the record is saved) and log a schema warning for the rows
    # that existed before this module was installed.
    matricule_institutionnel = fields.Char(
        string="Institutional ID",
        copy=False,
        readonly=True,
        index=True,
    )
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
        'maintenance.university.request', string="Maintenance Requests",
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

    _matricule_institutionnel_unique = models.Constraint(
        'unique(matricule_institutionnel)',
        "This institutional ID is already assigned to another employee.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            if not vals.get('matricule_institutionnel'):
                start_date = fields.Date.to_date(vals.get('date_start_working')) \
                    or fields.Date.context_today(self)
                vals['matricule_institutionnel'] = sequence.next_by_code(
                    'hr.employee.matricule.institutionnel',
                    sequence_date=start_date,
                )
        employees = super().create(vals_list)
        # An employee created outside the Create Workers wizard (e.g. the
        # standard Employees form) gets a user account with no maintenance
        # group at all — invisible to our menu security, so they'd log in to
        # a completely blank home screen. Default any such account to Worker,
        # the least-privileged role, rather than leaving it with no access.
        # Skipped if they already have a group (e.g. deliberately made a
        # Manager) — Manager already implies Worker, so this never downgrades.
        worker_group = self.env.ref('maintenance_university.group_maintenance_worker')
        for employee in employees:
            user = employee.sudo().user_id
            if user and not user.has_group('maintenance_university.group_maintenance_worker'):
                user.sudo().write({'group_ids': [(4, worker_group.id)]})
        return employees

    @api.depends()
    def _compute_maintenance_request_ids(self):
        Request = self.env['maintenance.university.request']
        for employee in self:
            employee.maintenance_request_ids = Request.search([('employee_ids', 'in', employee.id)])

    @api.depends()
    def _compute_maintenance_monthly_stats(self):
        # Not stored: "this month" is a moving window, so it's always
        # recomputed fresh from the source records rather than kept in sync.
        month_start = fields.Date.context_today(self).replace(day=1)
        month_start_dt = fields.Datetime.to_datetime(month_start)
        next_month_dt = month_start_dt + relativedelta(months=1)
        Request = self.env['maintenance.university.request']
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
