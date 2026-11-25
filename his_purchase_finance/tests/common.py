# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64

from odoo.addons.his_purchase.tests.common import HisPurchaseCase
from odoo.tests import new_test_user


class HisFinanceCase(HisPurchaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.finance = new_test_user(
            cls.env,
            login="his_finance",
            name="Meriem Finance",
            groups="his_purchase_finance.group_finance",
            email="finance@example.com",
        )
        cls.company.his_finance_confirms = True
        suppliers = cls.supplier_a | cls.supplier_b | cls.supplier_c | cls.supplier_ifu
        # Exemptes de pieces : les tests du dossier fournisseur les ajoutent eux-memes.
        suppliers.sudo().write({"his_documents_exempt": True, "his_supplier_status": "validated"})

    def _offer(self, supplier=None, price=9000, purchase_type="usual"):
        """Une demande approuvee et sa demande de prix chiffree (2 toners)."""
        request = self._approved_request(purchase_type)
        order = self._source_rfq(request, supplier or self.supplier_a)
        order.order_line.price_unit = price
        return order

    def _attach(self, record, name):
        return self.env["ir.attachment"].create(
            {"name": name, "datas": base64.b64encode(b"%PDF devis"), "res_model": record._name, "res_id": record.id}
        )

    def _send(self, order, criterion="quality", note="Original cartridges.", quote=True):
        if quote and not order._his_quote_files():
            # Le devis du fournisseur, exige a l'envoi (procedure 3.1).
            self._attach(order, "devis-fournisseur.pdf")
        action = order.with_user(self.officer).action_his_send_to_finance()
        wizard = (
            self.env["his.purchase.choice"]
            .with_user(self.officer)
            .with_context(action["context"])
            .create({"order_id": order.id, "criterion": criterion, "note": note})
        )
        return wizard.action_confirm()

    def _confirmed(self, order=None, **kwargs):
        """Commande envoyee, confirmee par la Finance et approuvee : en commande."""
        order = order or self._offer(**kwargs)
        self._send(order)
        order.with_user(self.finance).button_confirm()
        if order.state == "to approve":
            order.with_user(self.manager).button_approve()
        return order
