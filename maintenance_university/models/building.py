from odoo import fields, models


class Building(models.Model):
    _name = "maintenance.building"
    _description = "University Building"

    name = fields.Char(string="Building Name", required=True)
    code = fields.Char(string="Code")
    description = fields.Text(string="Description")
