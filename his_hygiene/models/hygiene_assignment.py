from collections import defaultdict
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class HisHygieneAssignment(models.Model):
    """Une zone, un jour, une ou plusieurs salariees : une case de la matrice.

    La responsable remplit librement : aucune regle de rotation, son jugement
    est la regle. Une seule case planifiee par (jour, zone) ; le travail en
    plus (une salissure signalee) est une ligne a part, marquee is_extra.
    """

    _name = "his.hygiene.assignment"
    _description = "Hygiene Assignment"
    _order = "date, area_id, id"

    date = fields.Date(required=True, index=True)
    area_id = fields.Many2one("his.hygiene.area", string="Area", required=True, ondelete="restrict", index=True)
    employee_ids = fields.Many2many(
        "hr.employee", "his_hygiene_assignment_employee_rel", "assignment_id", "employee_id", string="Workers"
    )
    is_extra = fields.Boolean(string="Extra Work", help="Added on top of the plan, e.g. after a cleaning finding.")
    is_done = fields.Boolean(string="Done", readonly=True)
    done_by_id = fields.Many2one("res.users", string="Done By", readonly=True)
    done_at = fields.Datetime(string="Done At", readonly=True)

    _planned_unique = models.UniqueIndex(
        "(date, area_id) WHERE is_extra IS NOT TRUE", "This area is already planned on that day."
    )

    @api.constrains("employee_ids")
    def _check_members(self):
        for assignment in self:
            self._his_check_members(assignment.employee_ids.ids)

    # ------------------------------------------------------------------
    # Qui a le droit
    # ------------------------------------------------------------------
    @api.model
    def _his_is_manager(self):
        return self.env.user.has_group("his_hygiene.group_hygiene_manager")

    @api.model
    def _his_check_manager(self):
        if not self._his_is_manager():
            raise AccessError(_("Only the hygiene manager can plan the team."))

    @api.model
    def _his_check_members(self, employee_ids):
        members = set(self.env["his.hygiene.member"].sudo().search([]).employee_id.ids)
        if set(employee_ids) - members:
            raise ValidationError(_("Only members of the hygiene team can be assigned."))

    @api.model
    def _hygiene_off_weekdays(self):
        raw = self.env["ir.config_parameter"].sudo().get_param("his_hygiene.off_weekdays", "4,5")
        return {int(x) for x in raw.split(",") if x.strip().isdigit()}

    # ------------------------------------------------------------------
    # Zone faite
    # ------------------------------------------------------------------
    def _his_check_can_tick(self):
        if self._his_is_manager():
            return
        for assignment in self.sudo():
            if self.env.user not in assignment.employee_ids.user_id:
                raise AccessError(_("Only the workers of this area, or the manager, can tick it."))

    def action_mark_done(self):
        self._his_check_can_tick()
        self.sudo().write({"is_done": True, "done_by_id": self.env.uid, "done_at": fields.Datetime.now()})
        return True

    def action_mark_undone(self):
        self._his_check_can_tick()
        self.sudo().write({"is_done": False, "done_by_id": False, "done_at": False})
        return True

    # ------------------------------------------------------------------
    # La matrice
    # ------------------------------------------------------------------
    @api.model
    def _his_absent_by_date(self, first, last):
        absent = defaultdict(set)
        for absence in self.env["his.hygiene.absence"].sudo().search([("date", ">=", first), ("date", "<=", last)]):
            absent[absence.date].add(absence.employee_id.id)
        return absent

    def _his_cell(self, absent_by_date, off):
        """La case telle que la matrice la dessine."""
        self.ensure_one()
        workers = self.employee_ids.ids
        absent_ids = [e for e in workers if e in absent_by_date[self.date]]
        return {
            "id": self.id,
            "employee_ids": workers,
            "done": self.is_done,
            "extra": 0,
            "absent_ids": absent_ids,
            # Decouverte : un jour travaille, pas faite, et personne de present.
            "uncovered": not self.is_done
            and self.date.weekday() not in off
            and (not workers or len(absent_ids) == len(workers)),
        }

    @api.model
    def get_matrix(self, year, month):
        self._his_check_manager()
        first = date(year, month, 1)
        last = first + relativedelta(months=1, days=-1)
        off = self._hygiene_off_weekdays()
        today = fields.Date.context_today(self)
        absent = self._his_absent_by_date(first, last)

        cells = {}
        assignments = self.search([("date", ">=", first), ("date", "<=", last)])
        for assignment in assignments.filtered(lambda a: not a.is_extra):
            cells[f"{assignment.area_id.id}|{assignment.date.isoformat()}"] = assignment._his_cell(absent, off)
        for assignment in assignments.filtered("is_extra"):
            key = f"{assignment.area_id.id}|{assignment.date.isoformat()}"
            cell = cells.setdefault(
                key,
                {"id": False, "employee_ids": [], "done": False, "extra": 0, "absent_ids": [], "uncovered": False},
            )
            cell["extra"] += 1

        days = []
        current = first
        while current <= last:
            days.append(
                {
                    "date": current.isoformat(),
                    "day": current.day,
                    "weekday": current.weekday(),
                    "off": current.weekday() in off,
                    "today": current == today,
                }
            )
            current += timedelta(days=1)

        return {
            "year": year,
            "month": month,
            "days": days,
            "areas": [
                {"id": a.id, "name": a.name, "building": a.building_id.name}
                for a in self.env["his.hygiene.area"].search([])
            ],
            "members": [
                {"id": m.employee_id.id, "name": m.name, "initials": m.initials, "color": m.color}
                for m in self.env["his.hygiene.member"].search([])
            ],
            "cells": cells,
            "absences": {
                f"{a.employee_id.id}|{a.date.isoformat()}": a.reason or ""
                for a in self.env["his.hygiene.absence"].search([("date", ">=", first), ("date", "<=", last)])
            },
        }

    @api.model
    def _his_set(self, area_id, day, employee_ids):
        cell = self.search([("area_id", "=", area_id), ("date", "=", day), ("is_extra", "=", False)], limit=1)
        if not employee_ids and cell and not cell.is_done:
            cell.unlink()
            return self.browse()
        if cell:
            cell.employee_ids = [(6, 0, employee_ids)]
        elif employee_ids:
            cell = self.create({"area_id": area_id, "date": day, "employee_ids": [(6, 0, employee_ids)]})
        return cell

    @api.model
    def set_cell(self, area_id, date_str, employee_ids):
        self._his_check_manager()
        self._his_check_members(employee_ids)
        day = fields.Date.to_date(date_str)
        cell = self._his_set(area_id, day, employee_ids)
        if not cell:
            return {}
        return cell._his_cell(self._his_absent_by_date(day, day), self._hygiene_off_weekdays())

    @api.model
    def fill_range(self, area_id, date_from, date_to, employee_ids):
        """Meme equipe sur chaque jour travaille de la periode (bornes incluses)."""
        self._his_check_manager()
        self._his_check_members(employee_ids)
        off = self._hygiene_off_weekdays()
        current, last = sorted([fields.Date.to_date(date_from), fields.Date.to_date(date_to)])
        count = 0
        while current <= last:
            if current.weekday() not in off:
                self._his_set(area_id, current, employee_ids)
                count += 1
            current += timedelta(days=1)
        return count

    @api.model
    def copy_previous_month(self, year, month):
        """Le jour N du mois precedent devient le jour N de ce mois.

        Saute un jour qui n'existe pas (31), un jour off, une case deja
        planifiee, une zone archivee, et les salariees sorties de l'equipe.
        """
        self._his_check_manager()
        first = date(year, month, 1)
        prev_first = first - relativedelta(months=1)
        off = self._hygiene_off_weekdays()
        members = set(self.env["his.hygiene.member"].search([]).employee_id.ids)
        planned = {
            (a.area_id.id, a.date)
            for a in self.search(
                [("date", ">=", first), ("date", "<", first + relativedelta(months=1)), ("is_extra", "=", False)]
            )
        }
        sources = self.search(
            [
                ("date", ">=", prev_first),
                ("date", "<", first),
                ("is_extra", "=", False),
                ("area_id.active", "=", True),
            ]
        )
        count = 0
        for source in sources:
            try:
                target = source.date.replace(year=year, month=month)
            except ValueError:
                continue
            workers = [e for e in source.employee_ids.ids if e in members]
            if target.weekday() in off or (source.area_id.id, target) in planned or not workers:
                continue
            self.create({"area_id": source.area_id.id, "date": target, "employee_ids": [(6, 0, workers)]})
            planned.add((source.area_id.id, target))
            count += 1
        return count

    @api.model
    def toggle_absence(self, employee_id, date_str):
        """Absente / presente ce jour-la ; renvoie le nouvel etat (True = absente)."""
        self._his_check_manager()
        self._his_check_members([employee_id])
        Absence = self.env["his.hygiene.absence"]
        absence = Absence.search([("employee_id", "=", employee_id), ("date", "=", date_str)])
        if absence:
            absence.unlink()
            return False
        Absence.create({"employee_id": employee_id, "date": date_str})
        return True
