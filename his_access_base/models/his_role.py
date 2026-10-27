# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Le role metier : ce que l'administrateur choisit, a la place des groupes Odoo.

Un poste ne liste plus des groupes bruts. Pour installer une caissiere il
fallait savoir qu'elle a besoin de trois groupes, et le poste « Caissier
repas » en oubliait un. Le role est defini une fois, ici, dans les mots de
HIS (« Caissier Cafeteria », « Magasinier ») ; les groupes Odoo n'en sont que
l'application.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HisRole(models.Model):
    _name = "his.role"
    _description = "Business Role"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    kind = fields.Selection(
        [("employee", "Employee"), ("counter", "Counter"), ("service", "Service")],
        required=True,
        default="employee",
        help="Which accounts may carry this role: an employee through their job post, a till's "
        "counter account, or a service account such as n8n.",
    )
    group_ids = fields.Many2many(
        "res.groups",
        "his_role_group_rel",
        "role_id",
        "group_id",
        string="Odoo Groups",
    )
    granted_group_ids = fields.Many2many(
        "res.groups",
        string="Everything This Role Grants",
        compute="_compute_granted_group_ids",
        help="The groups above plus every group they bring along.",
    )
    job_ids = fields.Many2many(
        "hr.job",
        "his_job_role_rel",
        "role_id",
        "job_id",
        string="Job Positions",
    )
    user_ids = fields.Many2many(
        "res.users",
        "his_user_role_rel",
        "role_id",
        "user_id",
        string="Accounts",
        help="Counter and service accounts carrying this role directly.",
    )
    active = fields.Boolean(default=True)

    @api.depends("group_ids", "group_ids.all_implied_ids")
    def _compute_granted_group_ids(self):
        for role in self:
            role.granted_group_ids = role.group_ids | role.group_ids.all_implied_ids

    @api.constrains("group_ids")
    def _check_no_sensitive_group(self):
        interdits = self.env["hr.job"]._his_groupes_sensibles()
        for role in self:
            fautifs = role.group_ids & interdits
            if fautifs:
                raise ValidationError(
                    _(
                        "A business role cannot grant a sensitive group (%(groups)s). These are "
                        "still assigned by hand by an administrator, in Settings ▸ Users.",
                        groups=", ".join(fautifs.mapped("name")),
                    )
                )

    @api.constrains("kind", "user_ids", "job_ids")
    def _check_comptes_et_postes(self):
        """La regle de type, vue du cote du role : sinon on rattacherait un
        compte comptoir a un role d'employe en passant par le role."""
        self.sudo().user_ids._check_roles_du_compte()
        # Pas de job_ids._check_roles_d_employe() : hr.job.role_ids filtre par
        # son domaine (kind = employee) a la lecture et ne verrait pas ce role.
        if self.sudo().filtered(lambda r: r.kind != "employee" and r.job_ids):
            raise ValidationError(_("A position only carries employee roles, not counter or service roles."))

    def write(self, vals):
        # Les postes d'AVANT comptent aussi : un poste retire du role doit perdre
        # ses groupes.
        tous = self.with_context(active_test=False)
        postes, comptes = tous.job_ids, tous.user_ids
        res = super().write(vals)
        if {"group_ids", "job_ids", "user_ids", "active"} & vals.keys():
            self._his_reapply(postes, comptes)
        return res

    def unlink(self):
        tous = self.with_context(active_test=False)
        postes, comptes = tous.job_ids, tous.user_ids
        res = super().unlink()
        self.browse()._his_reapply(postes, comptes)
        return res

    def _his_reapply(self, postes=None, comptes=None):
        """Re-applique ces roles a tous ceux qui les portent."""
        tous = self.with_context(active_test=False)
        postes = (postes or self.env["hr.job"]) | tous.job_ids
        comptes = (comptes or self.env["res.users"]) | tous.user_ids
        self.env["hr.employee"].sudo().search([("job_id", "in", postes.ids)])._his_appliquer_roles_du_poste()
        comptes.sudo()._his_reconcilier_compte()
