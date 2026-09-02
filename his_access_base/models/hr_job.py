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
from odoo import _, fields, models


class HrJob(models.Model):
    _inherit = 'hr.job'

    group_ids = fields.Many2many(
        'res.groups',
        'his_job_group_rel', 'job_id', 'group_id',
        string="Roles Odoo du poste",
        help="Roles accordes automatiquement a qui occupe ce poste. Les roles "
             "poses a la main sur un utilisateur ne sont jamais touches par "
             "cette liste.",
    )

    def action_appliquer_roles(self):
        """Reapplique les roles de ce poste a tous ceux qui l'occupent."""
        self.ensure_one()
        employes = self.env['hr.employee'].search([('job_id', '=', self.id)])
        touches = employes._his_appliquer_roles_du_poste()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if touches else 'warning',
                'message': _(
                    "%(n)s compte(s) mis a jour.", n=touches,
                ) if touches else _(
                    "Aucun compte a mettre a jour : les employes de ce poste "
                    "n'ont pas d'utilisateur Odoo."
                ),
                'sticky': False,
            },
        }
