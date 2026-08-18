# -*- coding: utf-8 -*-
"""Ce module n'emet plus de matricule ; il se contente de l'afficher.

Ces tests ne verifient donc plus un cycle de vie possede ici, mais le
contraire : que le champ reste disponible pour les vues, et qu'il vient bien
de his_person_core via his_hr_base.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMatriculeIsMirrored(TransactionCase):

    def test_field_still_available_for_the_views(self):
        """hr_employee_views.xml reference le champ par ce nom : il doit exister."""
        field = self.env['hr.employee']._fields.get('matricule_institutionnel')
        self.assertIsNotNone(field, "champ retire : les vues de ce module casseraient")
        self.assertEqual(field.related, ('person_id', 'matricule_institutionnel'))
        self.assertTrue(field.store)
        self.assertTrue(field.readonly)

    def test_employee_gets_a_matricule_through_his_person(self):
        employee = self.env['hr.employee'].create({'name': "Test Mirroir"})
        self.assertTrue(employee.person_id, "aucune fiche his.person rattachee")
        self.assertRegex(employee.matricule_institutionnel, r'^HIS-\d{4}-\d{6}-[0-9X]$')
        self.assertEqual(
            employee.matricule_institutionnel,
            employee.person_id.matricule_institutionnel,
        )

    def test_this_module_owns_no_matricule_sequence(self):
        """La sequence locale a ete supprimee : une seule sequence dans le groupe."""
        self.assertFalse(
            self.env['ir.sequence'].sudo().search_count(
                [('code', '=', 'hr.employee.matricule.institutionnel')]
            ),
            "la sequence locale existe encore : deux compteurs = collision garantie",
        )

    def test_date_start_working_still_drives_the_year(self):
        employee = self.env['hr.employee'].create({
            'name': "Test Antidate", 'date_start_working': '2021-11-02',
        })
        self.assertTrue(
            employee.matricule_institutionnel.startswith('HIS-2021-'),
            employee.matricule_institutionnel,
        )
