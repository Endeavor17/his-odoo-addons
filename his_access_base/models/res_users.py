# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Reconcilier les roles d'un compte avec ceux de son poste.

Toute la difficulte tient dans une distinction : un role vient soit DU POSTE,
soit d'une DEROGATION individuelle. Sans la garder, une resynchronisation
efface les exceptions — la conseillere a qui on avait ouvert la Production
Contenu le temps d'un remplacement perd son acces un matin, et personne ne
comprend pourquoi.

On memorise donc ce qui a ete accorde automatiquement. A la reconciliation on
retire (ancien automatique moins nouveau automatique), on ajoute le nouveau, et
on ne touche a rien d'autre.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    role_ids_du_poste = fields.Many2many(
        "res.groups",
        "his_user_group_poste_rel",
        "user_id",
        "group_id",
        string="Roles From Position",
        help="Technical: what the automatic assignment set. Used to tell a position "
        "role apart from an individual exception.",
    )

    # Les comptes qui ne sont pas des personnes : le PC d'un comptoir de caisse,
    # une integration (n8n). Ils portent leurs roles directement ; tout autre
    # compte tient les siens de son poste (decision de Mohamed, 2026-10-27).
    his_account_type = fields.Selection(
        [("employee", "Employee"), ("counter", "Counter"), ("service", "Service")],
        string="Account Type",
        default="employee",
        groups="base.group_erp_manager",
        help="Employee: rights come from the job post. Counter: the PC of a till. Service: an integration such as n8n.",
    )
    his_role_ids = fields.Many2many(
        "his.role",
        "his_user_role_rel",
        "user_id",
        "role_id",
        string="Account Roles",
        groups="base.group_erp_manager",
        help="Counter and service accounts only. Employees get their roles from their job post.",
    )
    his_access_issue = fields.Selection(
        [
            ("no_employee", "No employee record"),
            ("no_job", "No job post"),
            ("post_drift", "Out of sync with its job post"),
            ("role_drift", "Out of sync with its roles"),
        ],
        string="Access Issue",
        readonly=True,
        copy=False,
        groups="base.group_erp_manager",
    )

    @api.constrains("his_account_type", "his_role_ids")
    def _check_roles_du_compte(self):
        for user in self.sudo():
            kind = user.his_account_type or "employee"
            if kind == "employee" and user.his_role_ids:
                raise ValidationError(_("An employee account gets its roles from its job post, not directly."))
            if user.his_role_ids.filtered(lambda r, kind=kind: r.kind != kind):
                raise ValidationError(_("A counter or service account only carries roles of its own kind."))

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users.sudo().filtered("his_role_ids")._his_reconcilier_compte()
        return users

    def write(self, vals):
        res = super().write(vals)
        if {"his_account_type", "his_role_ids"} & vals.keys():
            self.sudo()._his_reconcilier_compte()
        return res

    def _his_groupes_attendus(self):
        """Ce que ce compte doit tenir automatiquement, groupes sensibles exclus."""
        self.ensure_one()
        user = self.sudo()
        if (user.his_account_type or "employee") == "employee":
            employe = user.employee_ids[:1]
            groupes = employe.job_id._his_groupes_du_poste() if employe.job_id else self.env["res.groups"]
        else:
            groupes = user.his_role_ids.group_ids
        return groupes - self.env["hr.job"]._his_groupes_sensibles()

    def _his_reconcilier_compte(self):
        for user in self:
            user._his_reconcilier_roles(user._his_groupes_attendus())
            user._his_controler_acces()

    def _his_controler_acces(self):
        """Note l'ecart d'acces de chaque compte, sans le corriger."""
        for user in self.sudo():
            issue = False
            # Desynchronise : ce qui est memorise differe de l'attendu, OU un
            # groupe attendu a ete retire a la main du compte.
            attendus = user._his_groupes_attendus()
            desynchronise = attendus != user.role_ids_du_poste or bool(attendus - user.group_ids)
            if not user.active:
                pass
            elif (user.his_account_type or "employee") == "employee":
                employe = user.employee_ids[:1]
                if not employe:
                    issue = "no_employee"
                elif not employe.job_id:
                    issue = "no_job"
                elif desynchronise:
                    issue = "post_drift"
            elif desynchronise:
                issue = "role_drift"
            if user.his_access_issue != issue:
                user.his_access_issue = issue

    @api.model
    def _cron_controler_acces(self):
        """Signale les ecarts sans les corriger en silence.

        Corriger sans rien dire masquerait une attribution faite a la main qui
        contredit le poste — or c'est precisement ce qu'une revue d'acces doit
        voir. Les ecarts s'affichent dans la revue d'acces (filtre « With
        issue »), plus seulement dans un journal que personne ne lit.
        """
        # Archives compris : leur ecart s'efface, la revue les affiche aussi.
        comptes = self.sudo().with_context(active_test=False).search([("share", "=", False)])
        comptes._his_controler_acces()
        signales = comptes.filtered("his_access_issue")  # que des actifs
        if signales:
            _logger.warning("Ecarts d'acces sur %s compte(s) : %s", len(signales), ", ".join(signales.mapped("login")))
        return signales.mapped("login")

    def _his_reconcilier_roles(self, groupes_du_poste):
        """Aligne ce compte sur les roles de son poste, sans toucher au reste."""
        self.ensure_one()
        # Defense en profondeur (faille S-1) : meme si un poste portait un role
        # d'administration (impossible via la contrainte de hr.job, mais une
        # base ancienne pourrait en avoir un), la reconciliation en sudo ne doit
        # jamais l'accorder. On l'ecarte avant tout calcul.
        interdits = self.env["hr.job"]._his_groupes_sensibles()
        groupes_du_poste = groupes_du_poste - interdits
        a_retirer = self.role_ids_du_poste - groupes_du_poste
        a_ajouter = groupes_du_poste - self.group_ids

        if not a_retirer and not a_ajouter and self.role_ids_du_poste == groupes_du_poste:
            return False

        self.sudo().write(
            {
                "group_ids": [(3, g.id) for g in a_retirer] + [(4, g.id) for g in a_ajouter],
                "role_ids_du_poste": [(6, 0, groupes_du_poste.ids)],
            }
        )
        return True


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _his_appliquer_roles_du_poste(self):
        """Applique les roles du poste aux comptes des employes vises.

        La majorite de l'organigramme n'a PAS d'utilisateur Odoo — les agents de
        cuisine, de securite, d'entretien ne se connectent pas. Un employe sans
        compte est donc le cas NORMAL, pas une anomalie : on le passe en
        silence.
        """
        touches = 0
        for employe in self:
            user = employe.user_id
            # Un compte comptoir ou service rattache par erreur a une fiche ne
            # prend pas les roles d'un poste.
            if not user or (user.sudo().his_account_type or "employee") != "employee":
                continue
            groupes = employe.job_id._his_groupes_du_poste() if employe.job_id else self.env["res.groups"]
            if user._his_reconcilier_roles(groupes):
                touches += 1
            user._his_controler_acces()
        return touches

    @api.model_create_multi
    def create(self, vals_list):
        employes = super().create(vals_list)
        # A la creation aussi, et pas seulement au changement : un employe
        # arrive avec son poste, ses roles doivent arriver avec lui. Sans cela
        # tout nouvel arrivant devrait etre repris a la main — exactement ce
        # que l'attribution par le poste sert a eviter.
        employes._his_appliquer_roles_du_poste()
        return employes

    def write(self, vals):
        res = super().write(vals)
        # Un changement de poste doit se traduire dans les droits. Le faire ici
        # et non par un cron : entre les deux, la personne aurait les acces de
        # son ancien poste.
        if "job_id" in vals or "user_id" in vals:
            self._his_appliquer_roles_du_poste()
        return res
