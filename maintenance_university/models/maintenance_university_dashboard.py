from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import format_date


class MaintenanceUniversityDashboard(models.AbstractModel):
    _name = 'maintenance.university.dashboard'
    _description = 'Monthly Recap Dashboard Data'

    @api.model
    def get_recap_data(self, month_offset=0):
        # Same defense-in-depth pattern as the rest of the module: the menu
        # is already Manager-only, but this method is reachable by RPC
        # regardless of what menu (if any) called it.
        if not self.env.user.has_group('maintenance_university.group_maintenance_manager'):
            raise AccessError(self.env._("Only a manager can view the monthly recap."))

        today = fields.Date.context_today(self)
        month_start = today.replace(day=1) + relativedelta(months=month_offset)
        start_dt = fields.Datetime.to_datetime(month_start)
        end_dt = start_dt + relativedelta(months=1)

        Employee = self.env['hr.employee']
        Request = self.env['maintenance.request']
        Time = self.env['maintenance.university.request.time']
        Finding = self.env['maintenance.university.finding']
        Workday = self.env['maintenance.university.workday']

        # Manager implies Worker, so without excluding it explicitly, a
        # Manager with their own hr.employee record would show up in this
        # worker-to-worker comparison too — confirmed live as a real bug,
        # not hypothetical.
        worker_group = self.env.ref('maintenance_university.group_maintenance_worker')
        manager_group = self.env.ref('maintenance_university.group_maintenance_manager')
        workers = Employee.search([
            ('user_id.group_ids', 'in', worker_group.id),
            ('user_id.group_ids', 'not in', manager_group.id),
        ])
        worker_rows = []
        for worker in workers:
            time_logs = Time.search([
                ('employee_id', '=', worker.id),
                ('date_start', '>=', start_dt), ('date_start', '<', end_dt),
            ])
            # Presence, from the My Work clock. Deliberately a different number
            # from `hours` above: that one counts time booked against requests,
            # this one counts time on site. The difference is travel and idle
            # time, which is the point of showing both.
            workdays = Workday.search([
                ('employee_id', '=', worker.id),
                ('date', '>=', month_start), ('date', '<', month_start + relativedelta(months=1)),
            ])
            worker_rows.append({
                'id': worker.id,
                'name': worker.name,
                'hours': sum(time_logs.mapped('duration')),
                'hours_present': sum(workdays.mapped('worked_hours')),
                'tasks_done': Request.search_count([
                    ('employee_ids', 'in', worker.id), ('state', '=', 'done'),
                    ('date_end', '>=', start_dt), ('date_end', '<', end_dt),
                ]),
                'findings_logged': Finding.search_count([
                    ('employee_id', '=', worker.id),
                    ('found_date', '>=', start_dt), ('found_date', '<', end_dt),
                ]),
                'findings_critical': Finding.search_count([
                    ('employee_id', '=', worker.id), ('severity', 'in', ('high', 'critical')),
                    ('found_date', '>=', start_dt), ('found_date', '<', end_dt),
                ]),
            })

        requests_this_month = Request.search([
            ('request_date', '>=', start_dt), ('request_date', '<', end_dt),
        ])
        category_breakdown = self._group_count(requests_this_month, 'category_id')
        building_breakdown = self._group_count(requests_this_month, 'building_id')

        return {
            'month_offset': month_offset,
            'month_label': format_date(self.env, month_start, date_format='MMMM y'),
            'workers': worker_rows,
            'category_breakdown': category_breakdown,
            'building_breakdown': building_breakdown,
            'totals': {
                'requests_done': sum(w['tasks_done'] for w in worker_rows),
                'hours': sum(w['hours'] for w in worker_rows),
                'hours_present': sum(w['hours_present'] for w in worker_rows),
                'findings_logged': sum(w['findings_logged'] for w in worker_rows),
            },
        }

    def _group_count(self, records, field_name):
        counts = {}
        for rec in records:
            key = rec[field_name]
            counts[key] = counts.get(key, 0) + 1
        return [{'name': key.display_name, 'count': count} for key, count in counts.items()]
