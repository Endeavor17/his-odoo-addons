# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    person_id = fields.Many2one(
        'his.person',
        string="Fiche personne",
        # restrict : supprimer une fiche personne encore rattachee a un employe
        # detacherait un matricule deja distribue de son porteur.
        ondelete='restrict',
        copy=False,
        index=True,
    )
    # Miroir, pas source. Le nom du champ est conserve a l'identique : la vue
    # hr_employee_views.xml de maintenance_university le reference par ce nom
    # et continue de fonctionner sans modification.
    matricule_institutionnel = fields.Char(
        string="Matricule institutionnel",
        related='person_id.matricule_institutionnel',
        store=True,
        readonly=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        Person = self.env['his.person'].sudo()
        for vals in vals_list:
            if vals.get('person_id'):
                continue
            # L'annee du matricule vient de la date d'entree, pas de la date de
            # creation de la fiche : une embauche saisie en retard ou signee
            # pour la rentree doit porter son annee reelle. Comportement repris
            # a l'identique du code de maintenance_university remplace ici.
            person = Person.create({
                'nom_latin': vals.get('name') or "Employe",
                'type_personne': 'employe',
                'source_system': 'odoo_hr',
                'match_method': 'new',
                'matricule_sequence_date': vals.get('date_start_working'),
            })
            vals['person_id'] = person.id
        return super().create(vals_list)
