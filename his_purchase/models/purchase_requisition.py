# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Contrat-cadre annuel et commande mensuelle.

Le fournisseur mensuel du Restaurant livre au debut du mois, au magasin
principal (decisions du 2026-10-15). Le contrat-cadre fixe fournisseur et
prix pour l'annee ; chaque mois, `his_prepare_days` avant la livraison, un
brouillon de commande est cree avec les quantites habituelles et les besoins
ponctuels mis en attente, puis le responsable magasin l'ajuste et le confirme.
Il passe ensuite par l'approbation comme toute commande.
"""

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .hr_department import PURCHASE_DOMAINS
from .purchase_order import to_planned_datetime

RENEWAL_NOTICE_DAYS = 30
RENEWAL_DUE_DAYS = 20


class PurchaseRequisition(models.Model):
    _name = "purchase.requisition"
    _inherit = ["purchase.requisition", "his.purchase.followup.mixin"]

    his_purchase_domain = fields.Selection(
        PURCHASE_DOMAINS, string="Purchase Domain", default="pos", required=True, tracking=True
    )
    his_recurring = fields.Boolean(string="Monthly Order", tracking=True)
    his_delivery_day = fields.Integer(
        string="Delivery Day", default=1, tracking=True, help="Day of the month the supplier delivers."
    )
    his_prepare_days = fields.Integer(
        string="Prepare Days Before",
        default=7,
        tracking=True,
        help="The draft monthly order is created this many days before delivery.",
    )
    his_owner_id = fields.Many2one(
        "res.users",
        string="Monthly Order Owner",
        tracking=True,
        domain=[("share", "=", False)],
        help="Reviews and confirms each monthly order (the warehouse manager). Needs purchasing access.",
    )
    his_last_period = fields.Char(
        string="Last Monthly Order",
        readonly=True,
        copy=False,
        help="Month (YYYY-MM) of the last monthly order created.",
    )
    his_next_delivery = fields.Date(string="Next Delivery", compute="_compute_his_next_delivery")

    @api.constrains(
        "his_recurring", "his_delivery_day", "his_prepare_days", "his_owner_id", "requisition_type", "vendor_id"
    )
    def _check_his_recurring(self):
        for agreement in self.filtered("his_recurring"):
            if agreement.requisition_type != "blanket_order" or not agreement.vendor_id:
                raise ValidationError(_("A monthly order needs a blanket order with a vendor."))
            if not 1 <= agreement.his_delivery_day <= 28:
                raise ValidationError(_("The delivery day must be between 1 and 28."))
            if agreement.his_prepare_days < 1:
                raise ValidationError(_("Prepare at least one day before delivery."))
            if not agreement.his_owner_id:
                raise ValidationError(_("Set who owns the monthly order."))

    def _compute_his_next_delivery(self):
        today = fields.Date.context_today(self)
        for agreement in self:
            agreement.his_next_delivery = agreement._his_next_delivery(today) if agreement.his_recurring else False

    def _his_next_delivery(self, today):
        """Prochaine livraison a partir d'aujourd'hui (inclus)."""
        self.ensure_one()
        jour = date(today.year, today.month, self.his_delivery_day)
        if jour < today:
            jour = jour + relativedelta(months=1)
        return jour

    def _his_open_monthly_order(self):
        """Brouillon mensuel pas encore confirme, s'il y en a un."""
        self.ensure_one()
        return self.purchase_ids.filtered(lambda o: o.his_monthly and o.state in ("draft", "sent"))[:1]

    def _his_monthly_line_vals(self, product, qty, request_line=False):
        self.ensure_one()
        line = self.line_ids.filtered(lambda r: r.product_id == product)[:1]
        uom = line.product_uom_id or product.uom_id
        if request_line:
            # Le prix du contrat est dans son unite : on y convertit le besoin.
            qty = request_line.product_uom_id._compute_quantity(qty, uom)
        vals = {
            "product_id": product.id,
            "product_qty": qty,
            "product_uom_id": uom.id,
            "price_unit": line.price_unit,
        }
        if request_line:
            vals["his_request_line_id"] = request_line.id
        return vals

    def _his_queued_request_lines(self):
        self.ensure_one()
        return (
            self.env["his.purchase.request.line"]
            .search([("his_monthly_requisition_id", "=", self.id), ("request_id.state", "=", "sourcing")])
            .filtered(lambda line: line._his_remaining_qty() > 0)
        )

    def _his_add_to_monthly(self, request_lines):
        """Ajoute des besoins ponctuels au brouillon mensuel ouvert, sinon les met en attente."""
        self.ensure_one()
        request_lines.write({"his_monthly_requisition_id": self.id})
        order = self._his_open_monthly_order()
        if order:
            order.write(
                {
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                **self._his_monthly_line_vals(line.product_id, line._his_remaining_qty(), line),
                                "date_planned": order.date_planned,
                            },
                        )
                        for line in request_lines
                    ]
                }
            )
        return order

    def _his_create_monthly_order(self, delivery):
        self.ensure_one()
        planned = to_planned_datetime(delivery)
        lines = [
            (0, 0, {**self._his_monthly_line_vals(line.product_id, line.his_recurring_qty), "date_planned": planned})
            for line in self.line_ids
            if line.his_recurring_qty > 0
        ]
        lines += [
            (
                0,
                0,
                {
                    **self._his_monthly_line_vals(line.product_id, line._his_remaining_qty(), line),
                    "date_planned": planned,
                },
            )
            for line in self._his_queued_request_lines()
        ]
        if not lines:
            return self.env["purchase.order"]
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor_id.id,
                "company_id": self.company_id.id,
                "requisition_id": self.id,
                "user_id": self.his_owner_id.id,
                "currency_id": self.currency_id.id,
                "his_monthly": True,
                "his_purchase_domain": self.his_purchase_domain,
                "his_supplier_answer": "quoted",
                "origin": self.name,
                "date_planned": planned,
                "order_line": lines,
            }
        )
        self.his_last_period = delivery.strftime("%Y-%m")
        order.message_post(
            body=_(
                "Monthly order for the delivery of %(date)s, created from %(agreement)s.",
                date=delivery,
                agreement=self.name,
            )
        )
        return order

    @api.model
    def _cron_his_monthly_orders(self):
        today = fields.Date.context_today(self)
        orders = self.env["purchase.order"]
        for agreement in self.search([("his_recurring", "=", True), ("state", "=", "confirmed")]):
            delivery = agreement._his_next_delivery(today)
            if today < delivery - timedelta(days=agreement.his_prepare_days):
                continue
            if agreement.his_last_period == delivery.strftime("%Y-%m"):
                continue
            if agreement.date_end and delivery > agreement.date_end:
                continue
            if agreement.date_start and delivery < agreement.date_start:
                continue
            orders |= agreement._his_create_monthly_order(delivery)
        return orders

    # ------------------------------------------------------------------
    # Renouvellement
    # ------------------------------------------------------------------

    def _his_step(self):
        self.ensure_one()
        if self.state != "confirmed" or not self.date_end:
            return None
        if fields.Date.context_today(self) < self.date_end - timedelta(days=RENEWAL_NOTICE_DAYS):
            return None
        manager, director = self._his_company_people(self.company_id)
        owner = manager or director
        return {
            "key": "agreement_renew",
            "label": _("Renew agreement %(name)s (ends %(date)s)", name=self.name, date=self.date_end),
            "owner": owner,
            "due": self.date_end - timedelta(days=RENEWAL_DUE_DAYS),
            "chain": [(5, director - owner)],
        }

    @api.model
    def _cron_his_followup(self):
        self.search([("state", "=", "confirmed"), ("date_end", "!=", False)])._his_run_followup()


class PurchaseRequisitionLine(models.Model):
    _inherit = "purchase.requisition.line"

    his_recurring_qty = fields.Float(
        string="Monthly Quantity", digits="Product Unit", help="Usual quantity of the monthly order."
    )
