# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Le poste porte les roles metier qu'il donne.

L'organigramme du groupe croise sept grades et une quinzaine de departements.
Ce croisement ne se modelise PAS en groupes : un « mas'ul » de la restauration
et un « mas'ul » des admissions n'ont aucun droit commun, et sept grades fois
quinze departements font une centaine de groupes vides de sens.

Le grade et le departement restent donc de la donnee descriptive, ici, dans hr.
Ce qui est traduit en droits, c'est le POSTE — et la traduction est de la
configuration, pas du code. Le poste pointe des roles metier (his.role), jamais
des groupes Odoo bruts ; seul l'administrateur des droits les choisit (decision
de Mohamed, 2026-10-27). Les RH affectent les gens aux postes.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Roles sensibles : jamais par un poste ni par un role metier. L'administration
# d'abord — qui la detient controle tout Odoo (utilisateurs, regles, actions
# serveur qui executent du Python) ; sinon quiconque edite un poste s'octroie
# l'administration en se le rattachant. Puis ce qui contourne une protection
# ou fait sortir les donnees : HTML non assaini, modeles d'e-mail (rendu de
# code), comptabilite en administrateur, export, documentation de l'API.
# Ils restent attribues a la main par un administrateur, dans Reglages, et la
# revue d'acces les montre comme des derogations.
SENSITIVE_GROUP_XMLIDS = (
    "base.group_system",
    "base.group_erp_manager",
    "base.group_sanitize_override",
    "mail.group_mail_template_editor",
    "account.group_account_manager",
    "base.group_allow_export",
    "api_doc.group_allow_doc",
)


class HrJob(models.Model):
    _inherit = "hr.job"

    role_ids = fields.Many2many(
        "his.role",
        "his_job_role_rel",
        "job_id",
        "role_id",
        string="Business Roles",
        domain=[("kind", "=", "employee")],
        groups="base.group_erp_manager",
        help="Business roles granted automatically to whoever holds this position. Groups "
        "set by hand on a user are never touched.",
    )

    @api.model
    def _his_groupes_sensibles(self):
        """Les groupes sensibles, eux-memes et tout ce qui les implique."""
        dangereux = self.env["res.groups"]
        for xmlid in SENSITIVE_GROUP_XMLIDS:
            groupe = self.env.ref(xmlid, raise_if_not_found=False)
            if groupe:
                dangereux |= groupe
        if not dangereux:
            return dangereux
        # Un groupe qui IMPLIQUE l'administration la donne tout autant.
        return self.env["res.groups"].search([]).filtered(lambda g: (g | g.all_implied_ids) & dangereux)

    @api.constrains("role_ids")
    def _check_roles_d_employe(self):
        for job in self:
            if job.role_ids.filtered(lambda r: r.kind != "employee"):
                raise ValidationError(_("A position only carries employee roles, not counter or service roles."))

    def _his_groupes_du_poste(self):
        """Les groupes que donne ce poste.

        En sudo : `role_ids` est reserve a l'administrateur des droits, alors que
        la reconciliation part aussi d'un RH qui change quelqu'un de poste.
        """
        return self.sudo().role_ids.group_ids

    def write(self, vals):
        res = super().write(vals)
        if "role_ids" in vals:
            self.env["hr.employee"].sudo().search([("job_id", "in", self.ids)])._his_appliquer_roles_du_poste()
        return res

    def action_appliquer_roles(self):
        """Reapplique les roles de ce poste a tous ceux qui l'occupent."""
        self.ensure_one()
        employes = self.env["hr.employee"].search([("job_id", "=", self.id)])
        touches = employes._his_appliquer_roles_du_poste()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success" if touches else "warning",
                "message": _(
                    "%(n)s account(s) updated.",
                    n=touches,
                )
                if touches
                else _("No account to update: the employees in this position have no Odoo user."),
                "sticky": False,
            },
        }
