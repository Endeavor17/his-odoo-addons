# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Tout ce qui change qui tape son nom a une caisse resynchronise les caisses."""

from odoo import api, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model_create_multi
    def create(self, vals_list):
        employes = super().create(vals_list)
        self.env["pos.config"]._his_sync_tills()
        return employes

    def write(self, vals):
        res = super().write(vals)
        if {"job_id", "pin", "active", "company_id", "user_id"} & vals.keys():
            self.env["pos.config"]._his_sync_tills()
        return res


class HrJob(models.Model):
    _inherit = "hr.job"

    def write(self, vals):
        res = super().write(vals)
        if "role_ids" in vals:
            self.env["pos.config"]._his_sync_tills()
        return res


class ResUsers(models.Model):
    _inherit = "res.users"

    def write(self, vals):
        res = super().write(vals)
        # Devenir ou cesser d'etre responsable POS change qui tape son nom.
        if "group_ids" in vals:
            self.env["pos.config"]._his_sync_tills()
        return res
