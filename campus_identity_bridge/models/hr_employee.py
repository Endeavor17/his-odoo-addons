# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _create_his_person(self):
        """L'embauche Campus+ reprend la fiche du candidat au lieu d'en refuser une.

        create_employee_from_applicant pose work_contact_id = le contact de la
        candidature. Une fois le pont passe, ce contact porte deja une fiche, et
        his_hr_base leve « Le contact ... porte deja la fiche personne ». Ici la
        fiche existante EST la bonne : c'est la meme personne qui passe de
        candidat a enseignant.

        « enseignant » et non « employe » : his_meal_management n'autorise un
        rang academique que sur un enseignant.
        """
        self.ensure_one()
        person = self.sudo().applicant_ids.his_person_id[:1] \
            or self.sudo().work_contact_id.his_person_ids[:1]
        if not person:
            return super()._create_his_person()
        person.write({'type_personne': 'enseignant'})
        person._his_attribuer_matricule(
            sequence_date=self.date_start_working if 'date_start_working' in self._fields else None,
        )
        return person
