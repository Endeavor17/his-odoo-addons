from collections import defaultdict

from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import format_date


class HisHygieneRecap(models.AbstractModel):
    """Ce que lisent les ecrans : la journee, le mois d'une salariee, le recap.

    Un jour travaille = un jour passe (ou aujourd'hui) ou la salariee a une
    zone, sans etre marquee absente - qu'elle ait pointe ou non (decision de
    Mohamed : le pointage reste facultatif pour celles sans compte). Les heures
    ne viennent que des jours pointes ; les jours non pointes sont comptes a
    part pour qu'un total d'heures bas ne soit pas mal lu.
    """

    _name = "his.hygiene.recap"
    _description = "Hygiene Screens Data"

    @api.model
    def _his_is_manager(self):
        return self.env.user.has_group("his_hygiene.group_hygiene_manager")

    @api.model
    def _his_employee(self, employee_id):
        """La salariee demandee, ou soi-meme ; une autre que soi = responsable seulement."""
        own = self.env["hr.employee"].sudo().search([("user_id", "=", self.env.uid)], limit=1)
        employee = self.env["hr.employee"].sudo().browse(employee_id).exists() if employee_id else own
        if employee != own and not self._his_is_manager():
            raise AccessError(_("Only the hygiene manager can open the day of another worker."))
        is_member = employee and self.env["his.hygiene.member"].sudo().search_count([("employee_id", "=", employee.id)])
        if employee_id and not is_member:
            raise AccessError(_("This person is not in the hygiene team."))
        return employee if is_member else self.env["hr.employee"]

    @api.model
    def _his_month(self, month_offset):
        first = fields.Date.context_today(self).replace(day=1) + relativedelta(months=month_offset)
        return first, first + relativedelta(months=1, days=-1)

    @api.model
    def _his_members(self):
        return [
            {"id": m.employee_id.id, "name": m.name, "initials": m.initials, "color": m.color}
            for m in self.env["his.hygiene.member"].sudo().search([])
        ]

    # ------------------------------------------------------------------
    # Aujourd'hui
    # ------------------------------------------------------------------
    @api.model
    def get_today(self, employee_id=False):
        employee = self._his_employee(employee_id)
        is_manager = self._his_is_manager()
        today = fields.Date.context_today(self)
        Workday = self.env["maintenance.university.workday"]
        res = {
            "employee": employee and {"id": employee.id, "name": employee.name},
            "is_manager": is_manager,
            "members": self._his_members() if is_manager else [],
            "today": format_date(self.env, today, date_format="EEEE d MMMM"),
            # Pour signaler un probleme ailleurs que dans ses zones du jour.
            "areas": [{"id": a.id, "name": a.name} for a in self.env["his.hygiene.area"].sudo().search([])],
            "day": {},
            "assignments": [],
            "absent": False,
        }
        if not employee:
            return res
        day = Workday.sudo().search([("employee_id", "=", employee.id), ("date", "=", today)], limit=1)
        assignments = (
            self.env["his.hygiene.assignment"]
            .sudo()
            .search([("date", "=", today), ("employee_ids", "in", employee.id)])
        )
        res.update(
            {
                "day": Workday._his_day_payload(day),
                "assignments": [
                    {
                        "id": a.id,
                        "area": a.area_id.name,
                        "area_id": a.area_id.id,
                        "done": a.is_done,
                        "extra": a.is_extra,
                    }
                    for a in assignments
                ],
                "absent": bool(
                    self.env["his.hygiene.absence"]
                    .sudo()
                    .search_count([("employee_id", "=", employee.id), ("date", "=", today)])
                ),
            }
        )
        return res

    # ------------------------------------------------------------------
    # Le mois d'une salariee
    # ------------------------------------------------------------------
    @api.model
    def _his_worker_month(self, employee, first, last):
        """Le detail jour par jour et les totaux, pour une salariee."""
        today = fields.Date.context_today(self)
        assignments = (
            self.env["his.hygiene.assignment"]
            .sudo()
            .search([("date", ">=", first), ("date", "<=", last), ("employee_ids", "in", employee.id)])
        )
        absent = set(
            self.env["his.hygiene.absence"]
            .sudo()
            .search([("employee_id", "=", employee.id), ("date", ">=", first), ("date", "<=", last)])
            .mapped("date")
        )
        workdays = {
            d.date: d
            for d in self.env["maintenance.university.workday"]
            .sudo()
            .search(
                [
                    ("employee_id", "=", employee.id),
                    ("his_team", "=", "hygiene"),
                    ("date", ">=", first),
                    ("date", "<=", last),
                ]
            )
        }
        by_date = defaultdict(lambda: self.env["his.hygiene.assignment"])
        for assignment in assignments:
            by_date[assignment.date] |= assignment
        worked = {d for d in by_date if d <= today and d not in absent}

        days = []
        for day in sorted(set(by_date) | absent):
            workday = workdays.get(day)
            days.append(
                {
                    "date": day.isoformat(),
                    "label": format_date(self.env, day, date_format="EEE d"),
                    "areas": by_date[day].area_id.mapped("name") if day in by_date else [],
                    "done": len(by_date[day].filtered("is_done")) if day in by_date else 0,
                    "absent": day in absent,
                    "worked_hours": workday.worked_hours if workday else None,
                }
            )
        totals = {
            "days_worked": len(worked),
            "days_absent": len(absent),
            "worked_hours": sum(d.worked_hours for d in workdays.values()),
            "break_hours": sum(d.paused_hours for d in workdays.values()),
            "unclocked_days": len(worked - set(workdays)),
            "areas_planned": len(assignments),
            "areas_done": len(assignments.filtered("is_done")),
        }
        return days, totals, assignments, absent

    @api.model
    def get_month(self, employee_id=False, month_offset=0):
        employee = self._his_employee(employee_id)
        first, last = self._his_month(month_offset)
        label = format_date(self.env, first, date_format="MMMM yyyy")
        if not employee:
            return {"label": label, "days": [], "totals": {}}
        days, totals, __, __ = self._his_worker_month(employee, first, last)
        return {"label": label, "employee": employee.name, "days": days, "totals": totals}

    # ------------------------------------------------------------------
    # Le recapitulatif de la responsable
    # ------------------------------------------------------------------
    @api.model
    def get_recap(self, month_offset=0):
        if not self._his_is_manager():
            raise AccessError(_("Only the hygiene manager can read the monthly recap."))
        first, last = self._his_month(month_offset)
        today = fields.Date.context_today(self)
        areas = self.env["his.hygiene.area"].search([])
        members = self.env["his.hygiene.member"].search([])
        Finding = self.env["his.hygiene.finding"]

        workers, fairness_rows = [], []
        for member in members:
            employee = member.employee_id
            __, totals, assignments, absent = self._his_worker_month(employee, first, last)
            totals.update(
                {
                    "employee_id": employee.id,
                    "name": member.name,
                    "findings": Finding.search_count(
                        [("employee_id", "=", employee.id), ("date", ">=", first), ("date", "<=", last)]
                    ),
                }
            )
            workers.append(totals)
            # Equite : jours passes dans chaque zone (absences exclues).
            present = assignments.filtered(lambda a, absent=absent: a.date not in absent)
            fairness_rows.append(
                {
                    "name": member.name,
                    "color": member.color,
                    "counts": [
                        len(set(present.filtered(lambda a, z=area: a.area_id == z).mapped("date"))) for area in areas
                    ],
                }
            )

        absent_by_date = self.env["his.hygiene.assignment"]._his_absent_by_date(first, last)
        planned = self.env["his.hygiene.assignment"].search(
            [("date", ">=", first), ("date", "<=", last), ("is_extra", "=", False)]
        )
        area_rows = []
        for area in areas:
            mine = planned.filtered(lambda a, z=area: a.area_id == z)
            uncovered = mine.filtered(
                lambda a: (
                    not a.is_done and a.date < today and all(e in absent_by_date[a.date] for e in a.employee_ids.ids)
                )
            )
            area_rows.append(
                {
                    "id": area.id,
                    "name": area.name,
                    "planned": len(mine),
                    "done": len(mine.filtered("is_done")),
                    "uncovered": len(uncovered),
                }
            )

        return {
            "label": format_date(self.env, first, date_format="MMMM yyyy"),
            "workers": workers,
            "areas": area_rows,
            "fairness": {"areas": areas.mapped("name"), "rows": fairness_rows},
        }
