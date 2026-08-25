# -*- coding: utf-8 -*-
"""Le formulaire Categories doit s'ouvrir.

maintenance.request.category_id est redirige vers maintenance.category, mais le
One2many qui le declare comme inverse vit sur maintenance.equipment.category
(maintenance/models/maintenance.py:43). L'ORM cherche donc « maintenance_ids »
sur notre modele. Quand il n'y etait pas, tout onchange sur une categorie
levait KeyError: 'maintenance_ids' et l'ecran renvoyait un RPC_ERROR.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCategoryInverse(TransactionCase):

    def test_the_inverse_the_core_expects_exists(self):
        field = self.env['maintenance.category']._fields.get('maintenance_ids')
        self.assertIsNotNone(
            field, "sans ce champ, le formulaire Categories est inouvrable",
        )
        self.assertEqual(field.comodel_name, 'maintenance.request')
        self.assertEqual(field.inverse_name, 'category_id')

    def test_an_onchange_on_a_category_does_not_raise(self):
        """Reproduit exactement l'appel qui echouait : onchange -> modified()."""
        category = self.env['maintenance.category'].create({'name': "Test Onchange"})
        # modified() sur TOUS les champs, ce que fait web/models/models.py au
        # premier onchange d'un formulaire.
        category.modified(list(category._fields))

    def test_a_category_lists_its_own_requests(self):
        category = self.env['maintenance.category'].create({'name': "Test Inverse"})
        building = self.env['maintenance.building'].create({'name': "Test Batiment"})
        request = self.env['maintenance.request'].create({
            'name': "Test Demande",
            'category_id': category.id,
            'building_id': building.id,
        })
        self.assertIn(request, category.maintenance_ids)
