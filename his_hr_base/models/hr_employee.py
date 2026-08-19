# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import ValidationError


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
        # super() D'ABORD, contrairement a la version precedente de ce fichier.
        # hr.employee.create() ne cree le work_contact_id qu'a sa DERNIERE
        # ligne (`employees.filtered(...)._create_work_contacts()`), donc avant
        # super() ce partenaire n'existe pas encore. Creer la fiche personne
        # avant, c'est garantir un SECOND partenaire pour le meme humain —
        # exactement le probleme que la delegation existe pour eviter.
        employees = super().create(vals_list)
        for employee in employees:
            if not employee.person_id:
                employee.person_id = employee._create_his_person()
        return employees

    def _create_his_person(self):
        """Cree la fiche personne d'un employe, en reutilisant son partenaire."""
        self.ensure_one()
        partner = self.sudo().work_contact_id

        if partner:
            # res.partner.employee_ids est un One2many : un meme contact
            # professionnel peut servir plusieurs employes, et le coeur d'Odoo
            # le prevoit (`if len(...employee_ids) <= 1`). Un ancrage
            # d'identite, lui, doit rester un-par-humain : on signale, on ne
            # partage pas en silence.
            others = partner.sudo().employee_ids - self
            if others:
                raise ValidationError(
                    "Le contact « %s » sert deja %s autre(s) employe(s) (%s). Un "
                    "matricule identifie une seule personne : rattachez d'abord "
                    "chaque employe a son propre contact." % (
                        partner.display_name, len(others),
                        ", ".join(others.mapped('name')),
                    )
                )
            existing = self.env['his.person'].sudo().with_context(
                active_test=False,
            ).search([('partner_id', '=', partner.id)], limit=1)
            if existing:
                raise ValidationError(
                    "Le contact « %s » porte deja la fiche personne %s. Deux "
                    "fiches sur un meme contact rendraient le matricule "
                    "ambigu." % (partner.display_name, existing.matricule_institutionnel)
                )

        # L'annee du matricule vient de la date d'entree, pas de la date de
        # creation de la fiche : une embauche saisie en retard ou signee pour
        # la rentree doit porter son annee reelle. Comportement repris a
        # l'identique du code de maintenance_university remplace ici.
        # date_start_working appartient a maintenance_university : absent si ce
        # module n'est pas installe.
        vals = {
            'type_personne': 'employe',
            'source_system': 'odoo_hr',
            'match_method': 'new',
            'matricule_sequence_date': self.date_start_working
            if 'date_start_working' in self._fields else False,
        }
        if partner:
            # Reutilisation : la delegation se rattache au partenaire existant
            # au lieu d'en creer un second.
            vals['partner_id'] = partner.id
        else:
            # Aucun partenaire (contexte salary_simulation, ou cas limite) :
            # la delegation en cree un, ce qui est correct ici. Le cas a eviter
            # est d'en creer un second quand il en existe deja un.
            vals['name'] = self.name or "Employe"
        return self.env['his.person'].sudo().create(vals)
