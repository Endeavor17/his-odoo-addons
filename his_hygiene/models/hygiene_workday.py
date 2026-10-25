from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

CLOCK_ACTIONS = {"pause": "action_pause", "resume": "action_resume", "end": "action_end_day"}

# Ce qu'une correction a la main peut changer sur une journee d'hygiene : les
# heures, rien d'autre. Changer la salariee, l'equipe ou deplacer une tranche
# reviendrait a inventer une presence.
TIME_FIELDS = {"date_start", "date_end"}


class MaintenanceUniversityWorkday(models.Model):
    """La journee de maintenance_university, partagee avec l'equipe hygiene.

    Une seule horloge pour les deux equipes. La difference est ici : pour une
    journee d'hygiene, la responsable peut pointer a la place de la salariee
    (la plupart n'ont pas de compte). La maintenance garde sa regle : personne
    ne pointe pour un autre.
    """

    _inherit = "maintenance.university.workday"

    his_team = fields.Selection(selection_add=[("hygiene", "Hygiene")], ondelete={"hygiene": "cascade"})
    ended_by_id = fields.Many2one("res.users", string="Ended By", readonly=True)

    @api.model
    def _his_team_for(self, employee):
        if self.env["his.hygiene.member"].sudo().search_count([("employee_id", "=", employee.id)]):
            return "hygiene"
        return super()._his_team_for(employee)

    def _check_is_owner(self):
        # La responsable hygiene passe pour les journees de son equipe ; tout le
        # reste suit la regle de la maintenance.
        rest = self
        if self.env.user.has_group("his_hygiene.group_hygiene_manager"):
            rest = self.filtered(lambda d: d.sudo().his_team != "hygiene")
        return super(MaintenanceUniversityWorkday, rest)._check_is_owner()

    def _his_check_manual_write(self, vals):
        """Une ecriture hors des boutons (formulaire, RPC) : qui corrige quoi.

        Journee d'hygiene : la responsable hygiene seule, et seulement les heures.
        Journee de maintenance : la regle de maintenance_university (son
        responsable corrige), jamais quelqu'un qui n'y a que sa propre journee.
        Personne ne change une journee d'equipe.
        """
        if self.env.su:
            return
        if "his_team" in vals:
            raise AccessError(_("The team of a work day cannot be changed."))
        user = self.env.user
        for day in self.sudo():
            if day.his_team == "hygiene":
                allowed = (
                    user.has_group("his_hygiene.group_hygiene_manager")
                    and day.employee_id.user_id != user
                    and not set(vals) - TIME_FIELDS
                )
            else:
                allowed = user.has_group("maintenance_university.group_maintenance_manager")
            if not allowed:
                raise AccessError(_("Only the team manager can correct the times of this work day."))

    def write(self, vals):
        self._his_check_manual_write(vals)
        res = super().write(vals)
        if vals.get("date_end") and not self.env.su:
            # Fin oubliee saisie a la main : la tranche restee ouverte se ferme
            # a cette heure-la (et la correction est tracee sur elle).
            self.sudo().segment_ids.filtered(lambda s: not s.date_end).write({"date_end": vals["date_end"]})
        return res

    def _close_open_segments(self):
        # Les boutons ferment la tranche en cours : ce n'est pas une correction.
        return super(MaintenanceUniversityWorkday, self.with_context(his_clock=True))._close_open_segments()

    def action_end_day(self):
        res = super().action_end_day()
        self.sudo().ended_by_id = self.env.user
        return res

    @api.model
    def _his_hygiene_check_access(self, employee):
        """Membre de l'equipe, et l'appelant est la responsable ou elle-meme."""
        if not employee or not self.env["his.hygiene.member"].sudo().search_count([("employee_id", "=", employee.id)]):
            raise AccessError(_("This person is not in the hygiene team."))
        if not self.env.user.has_group("his_hygiene.group_hygiene_manager") and employee.user_id != self.env.user:
            raise AccessError(_("Only the hygiene manager can enter the day of another worker."))

    @api.model
    def his_hygiene_clock(self, employee_id, action):
        """Debut / pause / reprise / fin de la journee d'une salariee de l'hygiene."""
        employee = self.env["hr.employee"].sudo().browse(employee_id).exists()
        self._his_hygiene_check_access(employee)
        if action == "start":
            day = self._start_day_for(employee)
        elif action in CLOCK_ACTIONS:
            day = self.sudo().search(
                [("employee_id", "=", employee.id), ("date", "=", fields.Date.context_today(self))],
                limit=1,
            )
            if not day:
                raise UserError(_("This day has not started yet."))
            # Sous l'identite de l'appelant : _check_is_owner fait son travail.
            getattr(day.with_env(self.env), CLOCK_ACTIONS[action])()
        else:
            raise UserError(_("Unknown clock action."))
        return self._his_day_payload(day.sudo())


class MaintenanceUniversityWorkdaySegment(models.Model):
    _inherit = "maintenance.university.workday.segment"

    # sudo() garde l'utilisateur : c'est bien la personne qui a appuye.
    entered_by_id = fields.Many2one("res.users", string="Entered By", default=lambda self: self.env.user, readonly=True)
    corrected_by_id = fields.Many2one("res.users", string="Corrected By", readonly=True)
    original_date_start = fields.Datetime(string="Original Start", readonly=True)
    original_date_end = fields.Datetime(string="Original End", readonly=True)

    def write(self, vals):
        if not self.env.su:
            if set(vals) - TIME_FIELDS:
                raise AccessError(_("Only the times of a work day segment can be corrected."))
            self.workday_id._his_check_manual_write(vals)
        # Une correction d'heure garde la toute premiere valeur. Fermer la
        # tranche en cours par un bouton (contexte his_clock) n'en est pas une.
        corrected = self.browse()
        if TIME_FIELDS & set(vals) and not self.env.context.get("his_clock"):
            corrected = self
            for segment in corrected.filtered(lambda s: not s.corrected_by_id):
                super(MaintenanceUniversityWorkdaySegment, segment).write(
                    {"original_date_start": segment.date_start, "original_date_end": segment.date_end}
                )
        res = super().write(vals)
        if corrected:
            super(MaintenanceUniversityWorkdaySegment, corrected).write({"corrected_by_id": self.env.uid})
        return res
