# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Une regle min/max sur un comptoir reapprovisionne depuis WH/Stock.

Sans la route « Réappro comptoirs », Odoo remonte au parent WH/Stock et cree une
reception fournisseur vers le comptoir : c'est ce que le premier test attrape.
Joue avec_user() comme test_stock_rbac.py, jamais en superutilisateur : un
superutilisateur ne prouve rien sur ce que le magasinier peut faire."""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestReapproComptoirs(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.boissons = cls.env.ref("his_stock_mdm.categ_cafe_boissons")
        cls.stock_location = cls.env.ref("stock.warehouse0").lot_stock_id
        cls.suppliers = cls.env.ref("stock.stock_location_suppliers")
        cls.comptoirs = [
            (cls.env.ref("his_stock_mdm.loc_" + nom), cls.env.ref("his_stock_mdm.picking_type_reappro_" + nom))
            for nom in ("cafeteria", "restaurant", "copy_center")
        ]
        cls.manager = cls._user("reappro-manager", "stock.group_stock_manager")
        cls.collaborateur = cls._user("reappro-collaborateur", "stock.group_stock_user")
        cls.counter = 0

    @classmethod
    def _user(cls, login, group_xmlid):
        return cls.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id, cls.env.ref(group_xmlid).id])],
            }
        )

    def _product(self, qty_magasin):
        type(self).counter += 1
        product = (
            self.env["product.template"]
            .create(
                {
                    "name": "Test Reappro %d" % self.counter,
                    "categ_id": self.boissons.id,
                    "type": "consu",
                    "is_storable": True,
                    "list_price": 100.0,
                }
            )
            .product_variant_id
        )
        if qty_magasin:
            self.env["stock.quant"]._update_available_quantity(product, self.stock_location, qty_magasin)
        return product

    def _orderpoint(self, product, location):
        return (
            self.env["stock.warehouse.orderpoint"]
            .with_user(self.manager)
            .create(
                {
                    "product_id": product.id,
                    "location_id": location.id,
                    "product_min_qty": 3,
                    "product_max_qty": 10,
                    "trigger": "manual",
                }
            )
        )

    def _moves_vers(self, product, location):
        return self.env["stock.move"].search([("product_id", "=", product.id), ("location_dest_id", "=", location.id)])

    def test_une_regle_sur_un_comptoir_tire_du_magasin(self):
        """Le cas qui echouait : une reception fournisseur au lieu d'un transfert."""
        for comptoir, type_reappro in self.comptoirs:
            with self.subTest(comptoir=comptoir.name):
                product = self._product(qty_magasin=100)
                self._orderpoint(product, comptoir).action_replenish()

                moves = self._moves_vers(product, comptoir)
                self.assertEqual(len(moves), 1)
                self.assertEqual(moves.location_id, self.stock_location)
                self.assertEqual(moves.picking_type_id, type_reappro)
                self.assertEqual(moves.product_uom_qty, 10)
                self.assertFalse(moves.filtered(lambda m: m.location_id == self.suppliers))

    def test_magasin_vide_le_transfert_attend_sans_achat(self):
        """Rupture au magasin : la demande existe quand meme, elle n'est pas disponible."""
        comptoir, type_reappro = self.comptoirs[0]
        product = self._product(qty_magasin=0)
        self._orderpoint(product, comptoir).action_replenish()

        moves = self._moves_vers(product, comptoir)
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.location_id, self.stock_location)
        self.assertEqual(moves.picking_type_id, type_reappro)
        self.assertNotEqual(moves.state, "assigned")

    def test_commander_deux_fois_ne_double_pas(self):
        """Le transfert en attente compte dans le previsionnel du comptoir."""
        comptoir = self.comptoirs[0][0]
        product = self._product(qty_magasin=100)
        orderpoint = self._orderpoint(product, comptoir)
        orderpoint.action_replenish()
        orderpoint.action_replenish()

        self.assertEqual(sum(self._moves_vers(product, comptoir).mapped("product_uom_qty")), 10)

    def test_le_collaborateur_ne_commande_pas(self):
        """Droits natifs : l'utilisateur Inventaire lit les regles sans pouvoir les executer.
        Commander est un geste de Manager, comme valider un ajustement."""
        comptoir = self.comptoirs[0][0]
        orderpoint = self._orderpoint(self._product(qty_magasin=100), comptoir)
        with self.assertRaises(AccessError):
            orderpoint.with_user(self.collaborateur).action_replenish()
