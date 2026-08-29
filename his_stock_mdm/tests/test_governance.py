# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Un seul test par regle du MDM. Il echoue si une regle saute."""
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGovernance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.boissons = cls.env.ref('his_stock_mdm.categ_cafe_boissons')
        cls.viandes = cls.env.ref('his_stock_mdm.categ_resto_viandes')
        # Book a gagne une sous-arborescence reelle (16 rayons) : ce n'est plus
        # une categorie terminale, donc plus utilisable comme second exemple de
        # feuille pour ces tests. Articles Bureautique reste une feuille et
        # n'est eligible ni Format ni Variante.
        cls.other_leaf = cls.env.ref('his_stock_mdm.categ_copy_bureautique')
        cls.cafe = cls.env.ref('his_stock_mdm.categ_cafe')  # noeud intermediaire

        cls.counter = 0

    def _product(self, **vals):
        type(self).counter += 1
        return self.env['product.template'].create({
            'name': 'Test MDM %d' % self.counter,
            'default_code': 'TEST-MDM-%d' % self.counter,
            'categ_id': self.boissons.id,
            'type': 'consu',
            'is_storable': True,
            'list_price': 100.0,
            **vals,
        })

    # --- Regle 1 : reference interne obligatoire et unique -------------------

    def test_default_code_required_on_write(self):
        """La reference est auto-attribuee a la creation ; la vider est refuse."""
        product = self._product()
        with self.assertRaises(ValidationError):
            product.default_code = False

    def test_default_code_unique(self):
        self._product(default_code='MDM-UNIQ-1')
        with self.assertRaises(ValidationError):
            self._product(default_code='MDM-UNIQ-1')

    # --- Regle 1 bis : reference opaque sequentielle INV-NNNNNN --------------

    def test_reference_auto_assigned_and_sequential(self):
        first = self._product(default_code=False)
        second = self._product(default_code=False)
        self.assertRegex(first.default_code, r'^INV-\d{6}$')
        self.assertRegex(second.default_code, r'^INV-\d{6}$')
        self.assertEqual(
            int(second.default_code[4:]), int(first.default_code[4:]) + 1,
            "compteur unique et sequentiel")

    def test_reference_counter_is_global_across_categories(self):
        """Un seul compteur : pas de sequence par categorie ni par type."""
        a = self._product(default_code=False, categ_id=self.boissons.id)
        b = self._product(default_code=False, categ_id=self.other_leaf.id)
        c = self._product(default_code=False, type='service', is_storable=False)
        numbers = [int(p.default_code[4:]) for p in (a, b, c)]
        self.assertEqual(numbers, sorted(numbers))
        self.assertEqual(numbers[2] - numbers[0], 2, "aucun compteur separe")

    def test_explicit_reference_is_respected(self):
        product = self._product(default_code='MDM-MANUEL-1')
        self.assertEqual(product.default_code, 'MDM-MANUEL-1')

    def test_semantic_prefix_rejected(self):
        for bad in ('CAF-BOI-001', 'cop-imp-002', 'RES - 003', 'NET-01', 'SAN-9'):
            with self.assertRaises(ValidationError, msg=bad):
                self._product(default_code=bad)

    def test_reference_is_permanent(self):
        """Changer categorie/type/attributs ne regenere jamais la reference."""
        product = self._product(default_code=False, categ_id=self.boissons.id)
        reference = product.default_code
        product.write({'categ_id': self.other_leaf.id, 'sale_ok': False})
        self.assertEqual(product.default_code, reference)
        product.write({'type': 'service', 'is_storable': False})
        self.assertEqual(product.default_code, reference)

    def test_legacy_reference_untouched_on_unrelated_write(self):
        """Une fiche historique en CAF- reste modifiable sur les autres champs."""
        product = self._product(default_code='INV-LEGACY-PROBE')
        # SQL brut assume et limite au test : c'est le seul moyen de fabriquer
        # l'etat « fiche historique » que la contrainte interdit precisement de
        # creer par l'ORM. Aucun SQL brut dans le code du module.
        # default_code est stocke sur la variante ET sur le template (miroir
        # calcule stocke) : les deux lignes doivent etre mises a jour.
        # flush_all() d'abord, sinon les valeurs encore en cache seraient
        # reecrites par-dessus l'UPDATE au prochain flush.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE product_product SET default_code = 'CAF-BOI-001' WHERE id = %s",
            [product.product_variant_id.id])
        self.env.cr.execute(
            "UPDATE product_template SET default_code = 'CAF-BOI-001' WHERE id = %s",
            [product.id])
        product.product_variant_id.invalidate_recordset(['default_code'])
        product.invalidate_recordset(['default_code'])
        product.write({'name': 'Renommé sans toucher à la référence'})
        self.assertEqual(product.default_code, 'CAF-BOI-001')

    # --- Regle 2 : categorie feuille ----------------------------------------

    def test_category_must_be_leaf(self):
        self.assertTrue(self.cafe.child_id, "Café doit rester un noeud intermediaire")
        with self.assertRaises(ValidationError):
            self._product(categ_id=self.cafe.id)

    # --- Regle 3 : prix de vente obligatoire si stockable et vendable -------

    def test_sale_price_required(self):
        with self.assertRaises(ValidationError):
            self._product(list_price=0.0, sale_ok=True)

    def test_sale_price_not_required_if_not_sellable(self):
        self._product(list_price=0.0, sale_ok=False)  # ne doit pas lever

    def test_sale_price_not_required_for_service(self):
        self._product(list_price=0.0, type='service', is_storable=False)

    # --- Regle 6 : eligibilite des attributs par categorie ------------------

    def _add_attribute_line(self, template, attribute, value):
        return self.env['product.template.attribute.line'].create({
            'product_tmpl_id': template.id,
            'attribute_id': attribute.id,
            'value_ids': [(6, 0, value.ids)],
        })

    def test_format_rejected_on_ineligible_category(self):
        template = self._product(categ_id=self.other_leaf.id)
        fmt = self.env.ref('his_stock_mdm.attribute_format')
        with self.assertRaises(ValidationError):
            self._add_attribute_line(template, fmt, self.env.ref('his_stock_mdm.format_33cl'))

    def test_format_accepted_on_eligible_category(self):
        template = self._product(categ_id=self.boissons.id)
        fmt = self.env.ref('his_stock_mdm.attribute_format')
        self._add_attribute_line(template, fmt, self.env.ref('his_stock_mdm.format_33cl'))

    def test_unrestricted_attribute_accepted_anywhere(self):
        """allowed_categ_ids vide = pas de restriction (cas « Marque »)."""
        attribute = self.env['product.attribute'].create({'name': 'Marque Test MDM'})
        value = self.env['product.attribute.value'].create({
            'name': 'Ghadir', 'attribute_id': attribute.id})
        self._add_attribute_line(self._product(categ_id=self.other_leaf.id), attribute, value)

    # --- Phase 5 : tracabilite heritee de la categorie ----------------------

    def test_tracking_inherited_from_category(self):
        meat = self._product(categ_id=self.viandes.id)
        self.assertEqual(meat.tracking, 'lot')
        self.assertTrue(meat.use_expiration_date)

        drink = self._product(categ_id=self.boissons.id)
        self.assertEqual(drink.tracking, 'none')
        self.assertFalse(drink.use_expiration_date)

    # --- Phase 6 : valorisation par categorie -------------------------------

    def test_costing_method_per_category(self):
        self.assertEqual(self.viandes.property_cost_method, 'fifo')
        self.assertEqual(self.boissons.property_cost_method, 'average')
        self.assertEqual(self.viandes.property_valuation, 'real_time')

    # --- Phase 7 : motif de perte -------------------------------------------

    def _scrap(self, **vals):
        product = self._product(categ_id=self.boissons.id)
        return self.env['stock.scrap'].create({
            'product_id': product.product_variant_id.id,
            'scrap_qty': 1.0,
            **vals,
        })

    def test_scrap_reason_required(self):
        with self.assertRaises(ValidationError):
            self._scrap()

    def test_scrap_autre_requires_note(self):
        autre = self.env.ref('his_stock_mdm.scrap_reason_autre')
        with self.assertRaises(ValidationError):
            self._scrap(scrap_reason_tag_ids=[(6, 0, autre.ids)])
        self._scrap(scrap_reason_tag_ids=[(6, 0, autre.ids)], scrap_note='Inondation')

    # --- Phase 3 / 8 : chaque caisse tire de son propre emplacement ---------

    def test_pos_sources_own_location(self):
        for pos_xmlid, loc_xmlid in [
            ('pos_config_cafeteria', 'loc_cafeteria'),
            ('pos_config_restaurant', 'loc_restaurant'),
            ('pos_config_copy_center', 'loc_copy_center'),
        ]:
            config = self.env.ref('his_stock_mdm.%s' % pos_xmlid)
            location = self.env.ref('his_stock_mdm.%s' % loc_xmlid)
            self.assertEqual(config.picking_type_id.default_location_src_id, location)
            self.assertEqual(location.location_id,
                             self.env.ref('stock.warehouse0').lot_stock_id)
