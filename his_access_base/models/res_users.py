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

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    role_ids_du_poste = fields.Many2many(
        'res.groups',
        'his_user_group_poste_rel', 'user_id', 'group_id',
        string="Roles issus du poste",
        help="Technique : ce que l'attribution automatique a pose. Sert a "
             "distinguer un role du poste d'une derogation individuelle.",
    )

    def _his_reconcilier_roles(self, groupes_du_poste):
        """Aligne ce compte sur les roles de son poste, sans toucher au reste."""
        self.ensure_one()
        a_retirer = self.role_ids_du_poste - groupes_du_poste
        a_ajouter = groupes_du_poste - self.group_ids

        if not a_retirer and not a_ajouter and self.role_ids_du_poste == groupes_du_poste:
            return False

        self.sudo().write({
            'group_ids': [(3, g.id) for g in a_retirer] + [(4, g.id) for g in a_ajouter],
            'role_ids_du_poste': [(6, 0, groupes_du_poste.ids)],
        })
        return True


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

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
            if not user:
                continue
            groupes = employe.job_id.group_ids if employe.job_id else self.env['res.groups']
            if user._his_reconcilier_roles(groupes):
                touches += 1
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
        if 'job_id' in vals or 'user_id' in vals:
            self._his_appliquer_roles_du_poste()
        return res

    @api.model
    def _cron_reconcilier_roles(self):
        """Signale les ecarts sans les corriger en silence.

        Corriger sans rien dire masquerait une attribution faite a la main qui
        contredit le poste — or c'est precisement ce qu'une revue d'acces doit
        voir.
        """
        ecarts = []
        for employe in self.search([('user_id', '!=', False), ('job_id', '!=', False)]):
            attendu = employe.job_id.group_ids
            pose = employe.user_id.role_ids_du_poste
            if attendu != pose:
                ecarts.append("%s (poste %s)" % (employe.name, employe.job_id.name))
        if ecarts:
            _logger.warning(
                "Roles du poste desynchronises pour %s compte(s) : %s",
                len(ecarts), ", ".join(ecarts),
            )
        return ecarts
