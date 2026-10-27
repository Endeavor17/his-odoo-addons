# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Le role de caissier designe ses caisses : ses titulaires y tapent leur nom."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HisRole(models.Model):
    _inherit = "his.role"

    pos_config_ids = fields.Many2many(
        "pos.config",
        "his_role_pos_config_rel",
        "role_id",
        "config_id",
        string="Tills",
        help="Employees whose job post carries this role appear at these tills, once they have a PIN.",
    )

    @api.constrains("kind", "pos_config_ids")
    def _check_caisses_role_employe(self):
        if self.filtered(lambda r: r.kind != "employee" and r.pos_config_ids):
            raise ValidationError(_("Only an employee role names the tills where its holders tap in."))

    @api.model_create_multi
    def create(self, vals_list):
        roles = super().create(vals_list)
        if roles.filtered("pos_config_ids"):
            self.env["pos.config"]._his_sync_tills()
        return roles

    def write(self, vals):
        res = super().write(vals)
        if {"pos_config_ids", "job_ids", "active"} & vals.keys():
            self.env["pos.config"]._his_sync_tills()
        return res

    def unlink(self):
        res = super().unlink()
        self.env["pos.config"]._his_sync_tills()
        return res
