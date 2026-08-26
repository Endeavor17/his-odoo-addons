# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Separation des taches Collaborateur/Manager sur les ajustements de stock,
et cycle de vie de l'inventaire physique annuel.

Comme dans his_crm_pipeline/tests/test_roles.py : tout est joue en
`with_user()`, jamais en superutilisateur, sinon le test ne prouve rien sur ce
qu'un role peut ou ne peut pas faire."""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStockRbac(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.boissons = cls.env.ref('his_stock_mdm.categ_cafe_boissons')
        cls.stock_location = cls.env.ref('stock.stock_location_stock')
        cls.collaborateur = cls._user('collaborateur-test', 'stock.group_stock_user')
        cls.manager = cls._user('manager-test', 'stock.group_stock_manager')
        cls.counter = 0

    @classmethod
    def _user(cls, login, group_xmlid):
        return cls.env['res.users'].create({
            'name': login,
            'login': login,
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref(group_xmlid).id,
            ])],
        })

    def _product(self, **vals):
        type(self).counter += 1
        return self.env['product.template'].create({
            'name': 'Test RBAC %d' % self.counter,
            'categ_id': self.boissons.id,
            'type': 'consu',
            'is_storable': True,
            'list_price': 100.0,
            **vals,
        })

    def _scrap(self):
        product = self._product()
        return self.env['stock.scrap'].create({
            'product_id': product.product_variant_id.id,
            'location_id': self.stock_location.id,
            'scrap_qty': 1.0,
            'scrap_reason_tag_ids': [(6, 0, self.env.ref('his_stock_mdm.scrap_reason_autre').ids)],
            'scrap_note': "Test RBAC",
        })

    def _quant_a_appliquer(self):
        product = self._product()
        return self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.product_variant_id.id,
            'location_id': self.stock_location.id,
            'inventory_quantity': 10,
        })

    # --- Pertes : Collaborateur propose, Manager valide ----------------------

    def test_collaborateur_can_create_scrap_but_not_validate(self):
        scrap = self._scrap()
        scrap.with_user(self.collaborateur).scrap_note = "Ajusté par le collaborateur"
        with self.assertRaises(AccessError):
            scrap.with_user(self.collaborateur).do_scrap()

    def test_manager_can_validate_scrap(self):
        scrap = self._scrap()
        scrap.with_user(self.manager).do_scrap()
        self.assertEqual(scrap.state, 'done')

    # --- Comptages : Collaborateur compte, Manager applique ------------------

    def test_collaborateur_can_count_but_not_apply(self):
        quant = self._quant_a_appliquer()
        self.assertTrue(quant.inventory_quantity_set)
        with self.assertRaises(AccessError):
            quant.with_user(self.collaborateur).action_apply_inventory()

    def test_manager_can_apply_inventory(self):
        quant = self._quant_a_appliquer()
        quant.with_user(self.manager).action_apply_inventory()
        self.assertFalse(quant.inventory_quantity_set)

    # --- Inventaire annuel : ouverture, cloture, verrou ----------------------

    def test_annual_inventory_open_and_close_by_manager(self):
        inventaire = self.env['his.inventaire.annuel'].with_user(self.manager).create({
            'name': "Test 2026"})
        inventaire.with_user(self.manager).action_cloturer()
        self.assertEqual(inventaire.state, 'cloture')
        self.assertEqual(inventaire.cloture_par_id, self.manager)

    def test_annual_inventory_close_blocked_for_collaborateur(self):
        inventaire = self.env['his.inventaire.annuel'].create({'name': "Test 2027"})
        with self.assertRaises(AccessError):
            inventaire.with_user(self.collaborateur).action_cloturer()

    def test_annual_inventory_close_blocked_by_pending_count(self):
        self._quant_a_appliquer()  # comptage saisi, jamais applique
        inventaire = self.env['his.inventaire.annuel'].create({'name': "Test 2028"})
        with self.assertRaises(ValidationError):
            inventaire.with_user(self.manager).action_cloturer()

    def test_annual_inventory_constraint_fires_on_direct_write(self):
        """Le verrou de reconciliation vit dans @api.constrains, pas seulement
        dans action_cloturer() : une ecriture directe doit aussi echouer."""
        self._quant_a_appliquer()
        inventaire = self.env['his.inventaire.annuel'].create({'name': "Test 2029"})
        with self.assertRaises(ValidationError):
            inventaire.write({'state': 'cloture'})

    def test_annual_inventory_locked_after_closure(self):
        """Cloture verrouillee meme pour le Manager qui l'a prononcee : ce
        n'est pas un document de travail. with_user() est indispensable ici
        (cf. docstring du module) : self.env tourne en superutilisateur et
        contournerait le verrou en silence."""
        inventaire = self.env['his.inventaire.annuel'].create({'name': "Test 2030"})
        inventaire.with_user(self.manager).action_cloturer()
        with self.assertRaises(AccessError):
            inventaire.with_user(self.manager).write({'note': "Tentative de modification"})
        with self.assertRaises(AccessError):
            inventaire.with_user(self.manager).unlink()
