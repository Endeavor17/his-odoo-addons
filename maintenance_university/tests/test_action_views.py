# -*- coding: utf-8 -*-
"""Toute action qui ouvre une maintenance.request doit nommer sa vue.

maintenance.request porte deux vues formulaire de meme priorite : celle du
coeur (maintenance.hr_equipment_request_view_form) et la notre. La resolution
par defaut retombe donc sur le plus petit id, c'est-a-dire celle du coeur - qui
n'a ni Batiment ni Categorie, tous deux obligatoires chez nous. Une demande
ouverte dans ce formulaire-la ne peut tout simplement pas etre enregistree.

Le module s'est fait prendre trois fois : le kanban des demandes, l'ecran des
constats, puis la conversion d'un constat en demande. Ce test ferme la porte
pour de bon.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestActionViewsAreExplicit(TransactionCase):

    def test_the_two_form_views_really_do_collide(self):
        """Si le coeur cessait d'en fournir une, ce test perdrait son sens."""
        forms = self.env['ir.ui.view'].search([
            ('model', '=', 'maintenance.request'),
            ('type', '=', 'form'),
            ('inherit_id', '=', False),
        ])
        self.assertGreater(
            len(forms), 1,
            "une seule vue formulaire : la resolution par defaut serait sans risque",
        )

    def test_converting_a_finding_opens_our_form(self):
        building = self.env['maintenance.building'].create({'name': "Test Bat"})
        category = self.env['maintenance.category'].create({'name': "Test Cat"})
        person = self.env['his.person'].create({
            'name': "Temoin Constat",
            'type_personne': 'etudiant',
            'source_system': 'manual',
        })
        employee = self.env['hr.employee'].create({
            'name': "Temoin Constat", 'person_id': person.id,
        })
        finding = self.env['maintenance.university.finding'].create({
            'building_id': building.id,
            'category_id': category.id,
            'description': "Vitre cassee",
            'severity': 'high',
            'employee_id': employee.id,
        })
        finding.action_submit()

        action = finding.action_convert_to_request()

        self.assertEqual(action['res_model'], 'maintenance.request')
        ours = self.env.ref('maintenance_university.view_maintenance_university_request_form')
        self.assertIn(
            (ours.id, 'form'), action.get('views') or [],
            "sans vue explicite, la conversion ouvre le formulaire generique du "
            "coeur, ou Batiment et Categorie n'existent pas",
        )
