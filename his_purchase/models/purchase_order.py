# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Commande fournisseur : reponse du fournisseur, choix trace, approbation routee.

- Un fournisseur qui refuse ou ne repond pas n'est jamais une offre a 0 DA :
  sa demande de prix ne se confirme pas et sort de la comparaison.
- Le choix du fournisseur (critere, note, qui, quand) est enregistre a la
  confirmation et fige ensuite. Pas de minimum de devis (decision du
  2026-10-15) : le petit assistant n'apparait que s'il y a vraiment eu
  concurrence.
- Toute commande est approuvee : directeur executif pour les achats generaux,
  responsable achats ou directeur pour les points de vente.
"""

from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .his_purchase_followup import add_working_days
from .hr_department import PURCHASE_DOMAINS

ANSWERS = [
    ("pending", "Pending"),
    ("quoted", "Quoted"),
    ("declined", "Declined"),
    ("no_answer", "No Answer"),
]
CRITERIA = [
    ("lowest_price", "Lowest price"),
    ("earliest_delivery", "Earliest delivery"),
    ("quality", "Quality"),
    ("only_supplier", "Only supplier"),
    ("other", "Other"),
]
CHOICE_FIELDS = {"his_choice_criterion", "his_choice_note", "his_chosen_by_id", "his_chosen_on"}
DAYS_TO_REPLY = 5
DAYS_TO_APPROVE = 2
DAYS_TO_REVIEW_MONTHLY = 2
SUPPLIER_REMINDER_EVERY = 3
SUPPLIER_REMINDER_MAX = 2


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "his.purchase.followup.mixin"]

    his_request_id = fields.Many2one(
        "his.purchase.request", string="Purchase Request", copy=True, index="btree_not_null", readonly=True
    )
    his_purchase_domain = fields.Selection(
        PURCHASE_DOMAINS,
        string="Purchase Domain",
        compute="_compute_his_purchase_domain",
        store=True,
        readonly=False,
        precompute=True,
        tracking=True,
        help="Decides who approves: the executive director for General, the purchase manager or the "
        "director for Points of Sale.",
    )
    his_monthly = fields.Boolean(string="Monthly Order", readonly=True, copy=False)
    his_supplier_answer = fields.Selection(
        ANSWERS, string="Supplier Answer", default="pending", tracking=True, copy=False
    )
    his_quote_ref = fields.Char(string="Pro Forma Number", copy=False)
    his_quote_date = fields.Date(string="Pro Forma Date", copy=False)
    his_quote_valid_until = fields.Date(string="Pro Forma Valid Until", copy=False)
    his_answer_note = fields.Text(string="Supplier Observations", copy=False)
    his_reply_by = fields.Date(
        string="Reply By", copy=False, help="Date by which the supplier should send its pro forma."
    )
    his_supplier_reminder_count = fields.Integer(string="Supplier Reminders", readonly=True, copy=False)
    his_supplier_reminded_on = fields.Date(string="Supplier Reminded On", readonly=True, copy=False)
    his_choice_criterion = fields.Selection(
        CRITERIA, string="Choice Criterion", readonly=True, copy=False, tracking=True
    )
    his_choice_note = fields.Text(string="Choice Note", readonly=True, copy=False)
    his_chosen_by_id = fields.Many2one("res.users", string="Chosen By", readonly=True, copy=False)
    his_chosen_on = fields.Datetime(string="Chosen On", readonly=True, copy=False)
    his_approved_by_id = fields.Many2one("res.users", string="Approved By", readonly=True, copy=False)

    @api.depends("his_request_id", "requisition_id")
    def _compute_his_purchase_domain(self):
        for order in self:
            source = order.his_request_id or order.requisition_id
            order.his_purchase_domain = (
                source.his_purchase_domain if source else (order.his_purchase_domain or "general")
            )

    # ------------------------------------------------------------------
    # Offres concurrentes
    # ------------------------------------------------------------------

    def _his_is_competing_offer(self):
        """Offre reelle : ni refusee, ni sans reponse, ni annulee, et chiffree."""
        self.ensure_one()
        return (
            self.state != "cancel"
            and self.his_supplier_answer not in ("declined", "no_answer")
            and self.amount_total > 0
        )

    def _his_competitors(self):
        self.ensure_one()
        return (self.alternative_po_ids - self).filtered(lambda o: o._his_is_competing_offer())

    def _his_is_cheapest(self):
        self.ensure_one()
        prices = [
            o.currency_id._convert(o.amount_total, self.company_id.currency_id, self.company_id, fields.Date.today())
            for o in self._his_competitors()
        ]
        mine = self.currency_id._convert(
            self.amount_total, self.company_id.currency_id, self.company_id, fields.Date.today()
        )
        return all(mine <= price for price in prices)

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------

    def write(self, vals):
        if CHOICE_FIELDS & set(vals) and not self.env.context.get("his_choice_write"):
            raise UserError(_("The supplier choice is recorded at confirmation and cannot be changed afterwards."))
        if vals.get("his_supplier_answer") in ("declined", "no_answer"):
            # Hors comparaison : Odoo ignore les lignes a total nul. Les quantites
            # sont gardees de cote, pour revenir si la reponse etait une erreur.
            for line in self.order_line.filtered(lambda line: not line.display_type and line.product_qty):
                line.write({"his_qty_before_answer": line.product_qty, "product_qty": 0})
        elif "his_supplier_answer" in vals:
            for line in self.order_line.filtered("his_qty_before_answer"):
                line.write({"product_qty": line.his_qty_before_answer, "his_qty_before_answer": 0})
        res = super().write(vals)
        if vals.get("his_supplier_answer") == "quoted":
            self._his_check_quoted()
        if {"state", "his_supplier_answer", "his_reply_by"} & set(vals):
            self._his_sync_step()
        if "state" in vals:
            self._his_requests()._his_update_progress()
        return res

    def _his_requests(self):
        """Les demandes servies : une commande mensuelle ou un appel en sert
        plusieurs, par ses lignes, sans `his_request_id`."""
        return self.his_request_id | self.order_line.his_request_line_id.request_id

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders.filtered(
            lambda o: o.his_request_id and not o.his_reply_by and o.state in ("draft", "sent")
        )._his_set_reply_by()
        orders._his_sync_step()
        return orders

    def _his_set_reply_by(self):
        today = fields.Date.context_today(self)
        for order in self:
            order.his_reply_by = add_working_days(today, DAYS_TO_REPLY)

    def _his_check_quoted(self):
        for order in self:
            sans_prix = order.order_line.filtered(lambda line: not line.display_type and line.price_unit <= 0)
            if sans_prix:
                raise UserError(
                    _(
                        "%(order)s is marked as quoted but has lines without a price: %(lines)s.",
                        order=order.name,
                        lines=", ".join(sans_prix.mapped("name")),
                    )
                )

    # ------------------------------------------------------------------
    # Confirmation
    # ------------------------------------------------------------------

    def _his_confirm_checks(self):
        for order in self:
            if order.his_supplier_answer in ("declined", "no_answer"):
                raise UserError(
                    _(
                        "%(order)s cannot be confirmed: the supplier answer is “%(answer)s”.",
                        order=order.name,
                        answer=dict(ANSWERS)[order.his_supplier_answer],
                    )
                )
            missing = order.partner_id.his_missing_identifiers()
            if missing:
                raise UserError(
                    _(
                        "%(supplier)s is missing %(fields)s: complete the supplier before confirming %(order)s.",
                        supplier=order.partner_id.commercial_partner_id.name,
                        fields=", ".join(missing),
                        order=order.name,
                    )
                )
            order._his_check_quoted()
            order._his_check_request_quantities()

    def _his_check_request_quantities(self):
        """Pas plus que demande, sauf un responsable achats (trace au fil)."""
        self.ensure_one()
        depassements = []
        for line in self.order_line.filtered("his_request_line_id"):
            request_line = line.his_request_line_id
            autres = (request_line.purchase_line_ids - line).filtered(
                lambda p: p.order_id.state in ("to approve", "purchase")
            )
            total = sum(p._his_qty_in_request_uom() for p in autres) + line._his_qty_in_request_uom()
            if request_line.product_uom_id.compare(total, request_line.product_qty) > 0:
                depassements.append((request_line, total))
        if not depassements:
            return
        if not self.env.user.has_group("purchase.group_purchase_manager"):
            raise UserError(
                _(
                    "%(order)s orders more than requested on %(request)s. Only a purchase manager can authorise a top-up.",
                    order=self.name,
                    request=depassements[0][0].request_id.name,
                )
            )
        for request_line, total in depassements:
            self.message_post(
                body=_(
                    "Quantity top-up authorised by %(user)s: %(total)s ordered for %(requested)s requested (%(line)s).",
                    user=self.env.user.name,
                    total=total,
                    requested=request_line.product_qty,
                    line=request_line.product_id.display_name or request_line.description,
                )
            )

    def _his_needs_choice(self):
        self.ensure_one()
        return not self.his_choice_criterion and bool(self._his_competitors())

    def button_confirm(self):
        to_check = self.filtered(lambda o: o.state in ("draft", "sent"))
        to_check._his_confirm_checks()
        if not self.env.context.get("his_choice_done"):
            pending = to_check.filtered(lambda o: o._his_needs_choice())
            if pending:
                if len(self) > 1:
                    raise UserError(
                        _("%s has competing offers: confirm it on its own to record the choice.", pending[0].name)
                    )
                return pending._his_action_choice()
        for order in to_check:
            vals = {}
            if not order.his_chosen_by_id:
                vals.update({"his_chosen_by_id": self.env.user.id, "his_chosen_on": fields.Datetime.now()})
            if not order.his_choice_criterion:
                vals["his_choice_criterion"] = "only_supplier"
            if order.his_supplier_answer == "pending":
                vals["his_supplier_answer"] = "quoted"
            if vals:
                order.with_context(his_choice_write=True).write(vals)
            if order.partner_id.his_is_vat_free():
                order.order_line.write({"tax_ids": [(5, 0, 0)]})
        return super().button_confirm()

    def _his_action_choice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Record the Supplier Choice"),
            "res_model": "his.purchase.choice",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_order_id": self.id,
                "default_criterion": "lowest_price" if self._his_is_cheapest() else False,
            },
        }

    # ------------------------------------------------------------------
    # Approbation routee
    # ------------------------------------------------------------------

    def _his_approver_group(self):
        self.ensure_one()
        if self.his_purchase_domain == "pos":
            return "purchase.group_purchase_manager"
        return "his_purchase.group_purchase_director"

    def _approval_allowed(self):
        self.ensure_one()
        company = self.company_id
        if company.po_double_validation == "one_step":
            return True
        seuil = self.env.company.currency_id._convert(
            company.po_double_validation_amount, self.currency_id, company, self.date_order or fields.Date.today()
        )
        if self.amount_total < seuil:
            return True
        return self.env.user.has_group(self._his_approver_group())

    def button_approve(self, force=False):
        # Le coeur filtre en silence ce que l'utilisateur ne peut pas approuver :
        # un clic sans effet. On le dit.
        if not force and not self.env.su:
            refused = self.filtered(lambda o: o.state == "to approve" and not o._approval_allowed())
            if refused:
                role = (
                    _("the executive director")
                    if refused[0].his_purchase_domain == "general"
                    else _("a purchase manager or the executive director")
                )
                raise UserError(_("%(order)s can only be approved by %(role)s.", order=refused[0].name, role=role))
        res = super().button_approve(force=force)
        self.filtered(lambda o: o.state == "purchase" and not o.his_approved_by_id).with_context(
            his_choice_write=True
        ).write({"his_approved_by_id": self.env.user.id})
        return res

    # ------------------------------------------------------------------
    # Relances
    # ------------------------------------------------------------------

    def _his_step(self):
        self.ensure_one()
        company = self.company_id
        manager, director = self._his_company_people(company)
        since = self.his_step_since or fields.Date.context_today(self)
        officer = self.user_id or company.his_purchase_officer_id or manager
        if self.state in ("draft", "sent") and self.his_monthly:
            owner = self.requisition_id.his_owner_id or officer
            return {
                "key": "monthly_review",
                "label": _("Review monthly order %s", self.name),
                "owner": owner,
                "due": add_working_days(since, DAYS_TO_REVIEW_MONTHLY),
                "chain": [(1, manager - owner)],
            }
        if self.state in ("draft", "sent") and self.his_supplier_answer == "pending" and self.his_reply_by:
            return {
                "key": "supplier_reply",
                "label": _("Chase supplier %(supplier)s for %(order)s", supplier=self.partner_id.name, order=self.name),
                "owner": officer,
                "due": self.his_reply_by,
                "chain": [(3, manager - officer)],
            }
        if self.state == "to approve":
            if self.his_purchase_domain == "pos":
                owner, chain = manager or director, [(2, director - manager)]
            else:
                owner, chain = director, []
            return {
                "key": "order_approve",
                "label": _("Approve purchase order %s", self.name),
                "owner": owner,
                "due": add_working_days(since, DAYS_TO_APPROVE),
                "chain": chain,
            }
        if self.state == "purchase" and self.receipt_status in ("pending", "partial") and self.date_planned:
            return {
                "key": "late_delivery",
                "label": _("Late delivery on %s", self.name),
                "owner": officer,
                "due": self.date_planned.date(),
                "chain": [(3, manager - officer)],
            }
        return None

    def _his_remind_suppliers(self):
        """Relance automatique du fournisseur (decision du 2026-10-15) : a la
        date de reponse, puis tous les 3 jours, deux fois au plus."""
        today = fields.Date.context_today(self)
        template = self.env.ref("his_purchase.mail_template_supplier_reminder", raise_if_not_found=False)
        if not template:
            return
        for order in self:
            if order.his_supplier_reminder_count >= SUPPLIER_REMINDER_MAX or today < order.his_reply_by:
                continue
            last = order.his_supplier_reminded_on
            if last and today < last + timedelta(days=SUPPLIER_REMINDER_EVERY):
                continue
            template.send_mail(order.id)
            order.message_post(body=_("Reminder sent to %s for the pro forma.", order.partner_id.name))
            order.write(
                {
                    "his_supplier_reminder_count": order.his_supplier_reminder_count + 1,
                    "his_supplier_reminded_on": today,
                }
            )

    @api.model
    def _cron_his_followup(self):
        today = fields.Date.context_today(self)
        followed = self.search(
            [
                "|",
                "|",
                ("state", "in", ("draft", "sent", "to approve")),
                ("his_step", "!=", False),
                "&",
                ("state", "=", "purchase"),
                ("receipt_status", "in", ("pending", "partial")),
            ]
        )
        followed._his_run_followup()
        self.search(
            [
                ("state", "in", ("draft", "sent")),
                ("his_supplier_answer", "=", "pending"),
                ("his_reply_by", "<=", today),
                ("his_monthly", "=", False),
                ("requisition_id", "=", False),
            ]
        )._his_remind_suppliers()


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    his_request_line_id = fields.Many2one(
        "his.purchase.request.line", string="Request Line", index="btree_not_null", copy=True, readonly=True
    )
    his_qty_before_answer = fields.Float(
        string="Quantity Before Refusal",
        digits="Product Unit",
        readonly=True,
        copy=False,
        help="Quantity set aside while the supplier answer is Declined or No Answer.",
    )

    def _his_qty_in_request_uom(self):
        """La quantite commandee dans l'unite de la demande : 10 cartons de 12
        couvrent 120 unites, pas 10."""
        self.ensure_one()
        return self.product_uom_id._compute_quantity(
            self.product_qty, self.his_request_line_id.product_uom_id, round=False
        )

    def _compute_tax_id(self):
        res = super()._compute_tax_id()
        # Fournisseur a l'IFU ou auto-entrepreneur : pas de TVA facturee.
        for line in self:
            if line.order_id.partner_id and line.order_id.partner_id.his_is_vat_free():
                line.tax_ids = False
        return res


def to_planned_datetime(day):
    """Une date de livraison en datetime a midi : aucun fuseau ne la fait changer de jour."""
    return datetime.combine(day, datetime.min.time()).replace(hour=12)


class PurchaseOrderReportHelpers(models.Model):
    _inherit = "purchase.order"

    def _his_delivery_partner(self):
        """Adresse de livraison imprimee : l'entrepot de reception, sinon la societe."""
        self.ensure_one()
        return self.dest_address_id or self.picking_type_id.warehouse_id.partner_id or self.company_id.partner_id

    def _his_vat_breakdown(self):
        """[(libelle, base HT, TVA)] par taux, pour le Bon de commande."""
        self.ensure_one()
        groups = {}
        for line in self.order_line.filtered(lambda ol: not ol.display_type):
            label = ", ".join(line.tax_ids.mapped("name")) or _("No VAT")
            base, tax = groups.get(label, (0.0, 0.0))
            groups[label] = (base + line.price_subtotal, tax + line.price_tax)
        return [(label, base, tax) for label, (base, tax) in sorted(groups.items())]

    def _his_offers(self):
        """Toutes les offres de la meme demande (fiche de choix), la moins chere d'abord."""
        self.ensure_one()
        offers = self | self.alternative_po_ids
        return offers.sorted(lambda o: (o.his_supplier_answer in ("declined", "no_answer"), o.amount_total))

    def _his_amount_in_words(self):
        self.ensure_one()
        return self.currency_id.amount_to_text(self.amount_total)
