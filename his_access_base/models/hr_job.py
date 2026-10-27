# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Le poste porte les roles Odoo qu'il donne.

L'organigramme du groupe croise sept grades et une quinzaine de departements.
Ce croisement ne se modelise PAS en groupes : un « mas'ul » de la restauration
et un « mas'ul » des admissions n'ont aucun droit commun, et sept grades fois
quinze departements font une centaine de groupes vides de sens.

Le grade et le departement restent donc de la donnee descriptive, ici, dans hr.
Ce qui est traduit en droits, c'est le POSTE — et la traduction est de la
configuration, pas du code : les RH ajustent un poste sans livraison.
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

    group_ids = fields.Many2many(
        "res.groups",
        "his_job_group_rel",
        "job_id",
        "group_id",
        string="Position Odoo Roles",
        help="Roles granted automatically to whoever holds this position. Roles set "
        "by hand on a user are never touched by this list.",
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

    @api.constrains("group_ids")
    def _check_pas_de_role_administration(self):
        """Un poste ne peut pas conferer l'administration (faille S-1 de l'audit).

        La vue masque deja `group_ids` aux non-managers RH, mais ce n'est que de
        l'affichage : un ecrit direct (RPC) passerait outre. Le verrou est ici.
        """
        interdits = self._his_groupes_sensibles()
        for job in self:
            fautifs = job.group_ids & interdits
            if fautifs:
                raise ValidationError(
                    _(
                        "A position cannot grant an administration role (%(roles)s). These "
                        "accesses are still assigned by hand by an administrator, in Settings ▸ "
                        "Users.",
                        roles=", ".join(fautifs.mapped("name")),
                    )
                )

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
