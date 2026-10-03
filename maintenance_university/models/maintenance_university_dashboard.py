import base64
import hashlib
import hmac
import json
import time

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import format_date

# The Metabase instance's site and key are shared with his_pos_dashboard (one
# place to rotate the key); the dashboard number is this app's. Set by an
# administrator, never committed: the repository is public.
METABASE_PARAMS = (
    "his_metabase.site_url",
    "his_metabase.secret_key",
    "maintenance_university.metabase_dashboard_id",
)


# ponytail: the same HS256 signing as his_pos_dashboard, copied rather than
# shared. Depending on a new module would need an upgrade at deploy to install
# it, and deploys here run none. Extract a shared module at a third dashboard.
def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


def _b64_json(data):
    return _b64(json.dumps(data, separators=(",", ":")).encode())


class MaintenanceUniversityDashboard(models.AbstractModel):
    _name = "maintenance.university.dashboard"
    _description = "Monthly Recap Dashboard Data"

    @api.model
    def get_metabase_url(self):
        """Signed embed URL for the Metabase dashboard, asked for on each opening.

        The key is read in sudo and never leaves the server: the browser gets a
        10-minute token. Manager-only like get_recap_data, and checked here for
        the same reason: the method is reachable by RPC whatever the menu says.
        """
        if not self.env.user.has_group("maintenance_university.group_maintenance_manager"):
            raise AccessError(self.env._("Only a manager can view the maintenance dashboard."))
        get_param = self.env["ir.config_parameter"].sudo().get_param
        site_url, key, dashboard_id = (get_param(name) for name in METABASE_PARAMS)
        if not (site_url and key and dashboard_id):
            raise UserError(
                self.env._(
                    "The maintenance dashboard is not configured: set the his_metabase.site_url, "
                    "his_metabase.secret_key and maintenance_university.metabase_dashboard_id system parameters."
                )
            )
        signing_input = (
            _b64_json({"alg": "HS256", "typ": "JWT"})
            + b"."
            + _b64_json({"resource": {"dashboard": int(dashboard_id)}, "params": {}, "exp": int(time.time()) + 600})
        )
        signature = _b64(hmac.new(key.encode(), signing_input, hashlib.sha256).digest())
        token = (signing_input + b"." + signature).decode()
        return f"{site_url.rstrip('/')}/embed/dashboard/{token}#bordered=true&titled=true"

    @api.model
    def get_recap_data(self, month_offset=0):
        # Same defense-in-depth pattern as the rest of the module: the menu
        # is already Manager-only, but this method is reachable by RPC
        # regardless of what menu (if any) called it.
        if not self.env.user.has_group("maintenance_university.group_maintenance_manager"):
            raise AccessError(self.env._("Only a manager can view the monthly recap."))

        today = fields.Date.context_today(self)
        month_start = today.replace(day=1) + relativedelta(months=month_offset)
        start_dt = fields.Datetime.to_datetime(month_start)
        end_dt = start_dt + relativedelta(months=1)

        Employee = self.env["hr.employee"]
        Request = self.env["maintenance.request"]
        Time = self.env["maintenance.university.request.time"]
        Finding = self.env["maintenance.university.finding"]
        Workday = self.env["maintenance.university.workday"]

        # Manager implies Worker, so without excluding it explicitly, a
        # Manager with their own hr.employee record would show up in this
        # worker-to-worker comparison too — confirmed live as a real bug,
        # not hypothetical.
        worker_group = self.env.ref("maintenance_university.group_maintenance_worker")
        manager_group = self.env.ref("maintenance_university.group_maintenance_manager")
        workers = Employee.search(
            [
                ("user_id.group_ids", "in", worker_group.id),
                ("user_id.group_ids", "not in", manager_group.id),
            ]
        )
        worker_rows = []
        for worker in workers:
            time_logs = Time.search(
                [
                    ("employee_id", "=", worker.id),
                    ("date_start", ">=", start_dt),
                    ("date_start", "<", end_dt),
                ]
            )
            # Presence, from the My Work clock. Deliberately a different number
            # from `hours` above: that one counts time booked against requests,
            # this one counts time on site. The difference is travel and idle
            # time, which is the point of showing both.
            workdays = Workday.search(
                [
                    ("employee_id", "=", worker.id),
                    ("date", ">=", month_start),
                    ("date", "<", month_start + relativedelta(months=1)),
                ]
            )
            worker_rows.append(
                {
                    "id": worker.id,
                    "name": worker.name,
                    "hours": sum(time_logs.mapped("duration")),
                    "hours_present": sum(workdays.mapped("worked_hours")),
                    "tasks_done": Request.search_count(
                        [
                            ("employee_ids", "in", worker.id),
                            ("state", "=", "done"),
                            ("date_end", ">=", start_dt),
                            ("date_end", "<", end_dt),
                        ]
                    ),
                    "findings_logged": Finding.search_count(
                        [
                            ("employee_id", "=", worker.id),
                            ("found_date", ">=", start_dt),
                            ("found_date", "<", end_dt),
                        ]
                    ),
                    "findings_critical": Finding.search_count(
                        [
                            ("employee_id", "=", worker.id),
                            ("severity", "in", ("high", "critical")),
                            ("found_date", ">=", start_dt),
                            ("found_date", "<", end_dt),
                        ]
                    ),
                }
            )

        requests_this_month = Request.search(
            [
                ("request_date", ">=", start_dt),
                ("request_date", "<", end_dt),
            ]
        )
        category_breakdown = self._group_count(requests_this_month, "category_id")
        building_breakdown = self._group_count(requests_this_month, "building_id")

        return {
            "month_offset": month_offset,
            "month_label": format_date(self.env, month_start, date_format="MMMM y"),
            "workers": worker_rows,
            "category_breakdown": category_breakdown,
            "building_breakdown": building_breakdown,
            "totals": {
                "requests_done": sum(w["tasks_done"] for w in worker_rows),
                "hours": sum(w["hours"] for w in worker_rows),
                "hours_present": sum(w["hours_present"] for w in worker_rows),
                "findings_logged": sum(w["findings_logged"] for w in worker_rows),
            },
        }

    def _group_count(self, records, field_name):
        counts = {}
        for rec in records:
            key = rec[field_name]
            counts[key] = counts.get(key, 0) + 1
        return [{"name": key.display_name, "count": count} for key, count in counts.items()]
