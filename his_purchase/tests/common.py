# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo.tests import TransactionCase, new_test_user

# Lundi : les delais en jours ouvres (week-end vendredi-samedi) restent lisibles.
LUNDI = date(2026, 11, 2)


class HisPurchaseCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env["res.users"]
        cls.requester = new_test_user(
            cls.env,
            login="his_req",
            name="Amina Requester",
            groups="his_purchase.group_requester",
            email="req@example.com",
        )
        cls.head = new_test_user(
            cls.env,
            login="his_head",
            name="Karim Head",
            groups="his_purchase.group_requester",
            email="head@example.com",
        )
        cls.cook = new_test_user(
            cls.env,
            login="his_cook",
            name="Samir Cook",
            groups="his_purchase.group_requester",
            email="cook@example.com",
        )
        cls.officer = new_test_user(
            cls.env,
            login="his_officer",
            name="Nadia Officer",
            groups="purchase.group_purchase_user",
            email="officer@example.com",
        )
        cls.manager = new_test_user(
            cls.env,
            login="his_manager",
            name="Yacine Manager",
            groups="purchase.group_purchase_manager",
            email="manager@example.com",
        )
        cls.director = new_test_user(
            cls.env,
            login="his_director",
            name="Leila Director",
            groups="his_purchase.group_purchase_director",
            email="director@example.com",
        )
        cls.outsider = new_test_user(
            cls.env, login="his_outsider", name="Other Requester", groups="his_purchase.group_requester"
        )
        cls.company.write(
            {
                "his_purchase_manager_id": cls.manager.id,
                "his_purchase_director_id": cls.director.id,
            }
        )
        Employee = cls.env["hr.employee"]
        # L'acheteur est l'occupant du poste ; les roles du poste (administrateur
        # achats) changeraient les circuits testes ici, d'ou le poste sans role.
        cls.officer_job = cls.env.ref("his_purchase.job_purchasing_officer")
        cls.officer_job.group_ids = False
        Employee.create({"name": "Nadia Officer", "user_id": cls.officer.id, "job_id": cls.officer_job.id})
        cls.head_emp = Employee.create({"name": "Karim Head", "user_id": cls.head.id})
        cls.it = cls.env["hr.department"].create(
            {"name": "IT", "manager_id": cls.head_emp.id}
        )
        cls.head_emp.department_id = cls.it
        cls.restaurant = cls.env["hr.department"].create(
            {"name": "Restaurant", "manager_id": cls.head_emp.id}
        )
        cls.req_emp = Employee.create(
            {"name": "Amina Requester", "user_id": cls.requester.id, "department_id": cls.it.id}
        )
        cls.cook_emp = Employee.create(
            {"name": "Samir Cook", "user_id": cls.cook.id, "department_id": cls.restaurant.id}
        )
        cls.outsider_emp = Employee.create({"name": "Other Requester", "user_id": cls.outsider.id})
        Partner = cls.env["res.partner"]
        ids = {"is_company": True, "vat": "000016001234567", "his_rc": "16/00-1234567B21"}
        cls.supplier_a = Partner.create({"name": "Supplier A", **ids})
        cls.supplier_b = Partner.create({"name": "Supplier B", **ids})
        cls.supplier_c = Partner.create({"name": "Supplier C", **ids})
        cls.supplier_ifu = Partner.create({"name": "Small IFU Shop", "his_tax_regime": "ifu", **ids})
        cls.supplier_bare = Partner.create({"name": "No Papers SARL", "is_company": True})
        cls.toner = cls.env["product.product"].create({"name": "Toner HP 85A", "type": "consu", "purchase_ok": True})
        cls.tomatoes = cls.env["product.product"].create({"name": "Tomatoes", "type": "consu", "purchase_ok": True})
        cls.tva19 = cls.env["account.tax"].search(
            [("type_tax_use", "=", "purchase"), ("amount", "=", 19), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.toner.supplier_taxes_id = cls.tva19
        cls.company.write({"po_double_validation": "two_step", "po_double_validation_amount": 0})
        Users.flush_model()

    def _request(self, user=None, employee=None, lines=None, **vals):
        user = user or self.requester
        employee = employee or self.req_emp
        lines = lines or [{"product_id": self.toner.id, "product_qty": 2, "estimated_price_unit": 9000}]
        return (
            self.env["his.purchase.request"]
            .with_user(user)
            .create(
                {
                    "requester_id": employee.id,
                    "justification": "The printer of room 12 is empty.",
                    "date_required": date(2026, 11, 30),
                    "line_ids": [(0, 0, line) for line in lines],
                    **vals,
                }
            )
        )

    def _approved_request(self, purchase_type="investment", **kwargs):
        request = self._request(**kwargs)
        request.with_user(request.requester_user_id).action_submit()
        request.with_user(self.officer).his_purchase_type = purchase_type
        approver = self.director if purchase_type == "investment" else self.officer
        request.with_user(approver).action_approve()
        return request

    def _source_rfq(self, request, supplier):
        wizard = (
            self.env["his.purchase.request.source"]
            .with_user(self.officer)
            .create({"request_id": request.id, "mode": "rfq", "partner_id": supplier.id})
        )
        action = wizard.action_source()
        return self.env["purchase.order"].browse(action["res_id"])

    def _alternative(self, order, supplier, price):
        wizard = (
            self.env["purchase.requisition.create.alternative"]
            .with_user(self.officer)
            .create({"origin_po_id": order.id, "partner_ids": [(6, 0, supplier.ids)], "copy_products": True})
        )
        wizard.action_create_alternative()
        alt = order.alternative_po_ids.filtered(lambda o: o.partner_id == supplier)
        alt.order_line.price_unit = price
        return alt
