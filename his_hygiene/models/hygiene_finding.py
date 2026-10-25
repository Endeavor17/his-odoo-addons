from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class HisHygieneFinding(models.Model):
    """Ce qu'une salariee remarque dans une zone.

    Deux suites possibles : une panne part tout de suite en maintenance (un
    constat soumis, salle remplie, que le chef maintenance convertit comme les
    autres) ; une salissure revient a la responsable hygiene, qui en fait du
    travail en plus d'un clic.
    """

    _name = "his.hygiene.finding"
    _description = "Hygiene Finding"
    _order = "date desc, id desc"

    area_id = fields.Many2one("his.hygiene.area", string="Area", required=True, ondelete="restrict", index=True)
    date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Reported By",
        default=lambda self: self.env["hr.employee"].sudo().search([("user_id", "=", self.env.uid)], limit=1),
        index=True,
    )
    description = fields.Text(required=True)
    image = fields.Image(string="Photo", max_width=1920, max_height=1920)
    kind = fields.Selection([("repair", "Repair"), ("cleaning", "Cleaning")], required=True, default="cleaning")
    state = fields.Selection(
        [("new", "New"), ("sent", "Sent to maintenance"), ("dispatched", "Dispatched")],
        default="new",
        readonly=True,
        index=True,
    )
    maintenance_finding_id = fields.Many2one(
        "maintenance.university.finding", string="Maintenance Finding", readonly=True
    )
    assignment_ids = fields.One2many("his.hygiene.assignment", "finding_id", string="Extra Work")

    @api.model_create_multi
    def create(self, vals_list):
        is_manager = self.env.user.has_group("his_hygiene.group_hygiene_manager")
        findings = super().create(vals_list)
        if not is_manager:
            for finding in findings:
                if finding.sudo().employee_id.user_id != self.env.user:
                    raise AccessError(_("You can only report a finding in your own name."))
        findings.filtered(lambda f: f.kind == "repair")._his_send_to_maintenance()
        return findings

    def _his_send_to_maintenance(self):
        category = self.env.ref("his_hygiene.category_reported_by_hygiene")
        for finding in self.sudo():
            area = finding.area_id
            building = area.building_id
            room = area.location_id if area.location_id != building.his_location_id else False
            maint = finding.env["maintenance.university.finding"].create(
                {
                    "building_id": building.id,
                    "his_room_id": room and room.id,
                    "category_id": category.id,
                    "description": finding.description,
                    "severity": "medium",
                    "employee_id": finding.employee_id.id,
                    "found_date": fields.Datetime.now(),
                }
            )
            if finding.image:
                photo = finding.env["ir.attachment"].create(
                    {
                        "name": _("Photo - %s", area.name),
                        "datas": finding.image,
                        "res_model": maint._name,
                        "res_id": maint.id,
                    }
                )
                maint.image_ids = [(4, photo.id)]
            # Soumis apres la photo : un constat soumis est verrouille.
            maint.state = "submitted"
            finding.write({"state": "sent", "maintenance_finding_id": maint.id})

    def action_dispatch(self, date=None, employee_ids=None):
        """Fait d'une salissure du travail en plus, ce jour-la (aujourd'hui par defaut).

        Sans equipe precisee : celle deja planifiee sur la zone ce jour-la.
        """
        self.ensure_one()
        Assignment = self.env["his.hygiene.assignment"]
        Assignment._his_check_manager()
        if self.kind != "cleaning":
            raise UserError(_("Only a cleaning finding is dispatched to the team."))
        day = fields.Date.to_date(date) if date else self.date
        if employee_ids is None:
            planned = Assignment.search(
                [("area_id", "=", self.area_id.id), ("date", "=", day), ("is_extra", "=", False)], limit=1
            )
            employee_ids = planned.employee_ids.ids
        extra = Assignment.create(
            {
                "area_id": self.area_id.id,
                "date": day,
                "employee_ids": [(6, 0, employee_ids)],
                "is_extra": True,
                "finding_id": self.id,
            }
        )
        self.state = "dispatched"
        return extra


class HisHygieneAssignment(models.Model):
    _inherit = "his.hygiene.assignment"

    finding_id = fields.Many2one("his.hygiene.finding", string="Finding", ondelete="set null", index=True)
