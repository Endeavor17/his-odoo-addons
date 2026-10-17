# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Demande d'achat interne : le besoin d'un employe, avant tout fournisseur.

Brouillon -> Soumise (chef de departement) -> Approuvee (acheteur) -> En cours
d'achat -> Commandee -> Terminee. Un refus renvoie en brouillon, motif au
fil de discussion. Une fois soumise, seule l'equipe achats la modifie.
"""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import format_date

from .his_purchase_followup import WEEKEND, add_working_days
from .hr_department import PURCHASE_DOMAINS

STATES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("approved", "Approved"),
    ("sourcing", "Sourcing"),
    ("ordered", "Ordered"),
    ("done", "Done"),
    ("cancel", "Cancelled"),
]
OPEN_STATES = ("submitted", "approved", "sourcing")
# Delais en jours ouvres, valides par Mohamed le 2026-10-15.
DAYS_TO_APPROVE = 2
DAYS_TO_SOURCE = 2
DAYS_TO_ESCALATE = 2
URGENT_DAYS = 5
NUDGE_HOURS = 24
# Champs que le suivi ecrit lui-meme, quel que soit l'etat.
FOLLOWUP_FIELDS = {"his_step", "his_step_since", "his_step_level", "his_reminder_count", "his_is_late"}
# Ecrits par les boutons (sudo) ou l'equipe achats, jamais par le demandeur :
# sinon il approuve son propre brouillon, ou choisit qui approuvera ses commandes.
PROTECTED_FIELDS = {
    "state",
    "approver_id",
    "approved_by_id",
    "approved_on",
    "his_purchase_domain",
    "his_last_nudge",
    "his_urgent_alert_sent",
}


class HisPurchaseRequest(models.Model):
    _name = "his.purchase.request"
    _description = "Purchase Request"
    _inherit = ["mail.thread", "mail.activity.mixin", "his.purchase.followup.mixin"]
    _order = "id desc"

    name = fields.Char(string="Reference", default=lambda self: _("New"), readonly=True, copy=False, required=True)
    company_id = fields.Many2one(
        "res.company", string="Company", required=True, default=lambda self: self.env.company, tracking=True
    )
    requester_id = fields.Many2one(
        "hr.employee",
        string="Requester",
        required=True,
        tracking=True,
        default=lambda self: self.env.user.employee_id,
        check_company=True,
    )
    requester_user_id = fields.Many2one(
        "res.users", related="requester_id.user_id", store=True, string="Requester User"
    )
    department_id = fields.Many2one(
        "hr.department",
        string="Department",
        compute="_compute_department_id",
        store=True,
        precompute=True,
        readonly=False,
        tracking=True,
        check_company=True,
    )
    approver_id = fields.Many2one(
        "res.users",
        string="Approver",
        compute="_compute_approver_id",
        store=True,
        precompute=True,
        help="Head of the department; the executive director when the requester is the head.",
    )
    his_purchase_domain = fields.Selection(
        PURCHASE_DOMAINS,
        string="Purchase Domain",
        compute="_compute_his_purchase_domain",
        store=True,
        precompute=True,
        readonly=False,
        required=True,
        tracking=True,
    )
    date_required = fields.Date(string="Required By", tracking=True)
    justification = fields.Text(string="Justification")
    line_ids = fields.One2many("his.purchase.request.line", "request_id", string="Lines", copy=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    estimated_amount = fields.Monetary(string="Estimated Amount", compute="_compute_estimated_amount", store=True)
    state = fields.Selection(STATES, string="Status", default="draft", required=True, tracking=True, copy=False)
    user_id = fields.Many2one(
        "res.users", string="Purchasing Officer", tracking=True, copy=False, domain=[("share", "=", False)]
    )
    approved_by_id = fields.Many2one("res.users", string="Approved By", readonly=True, copy=False)
    approved_on = fields.Datetime(string="Approved On", readonly=True, copy=False)
    order_ids = fields.Many2many(
        "purchase.order", string="Purchase Orders", compute="_compute_order_ids", compute_sudo=True
    )
    order_count = fields.Integer(compute="_compute_order_ids", compute_sudo=True)
    his_last_nudge = fields.Datetime(string="Last Reminder by Requester", readonly=True, copy=False)
    his_urgent_alert_sent = fields.Boolean(string="Urgent Alert Sent", readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Calculs
    # ------------------------------------------------------------------

    @api.depends("requester_id")
    def _compute_department_id(self):
        for request in self:
            request.department_id = request.requester_id.department_id

    @api.depends(
        "department_id",
        "department_id.manager_id.user_id",
        "requester_user_id",
        "company_id",
        "company_id.his_purchase_director_id",
    )
    def _compute_approver_id(self):
        for request in self:
            head = request.department_id.manager_id.user_id
            if not head or head == request.requester_user_id:
                head = request.company_id.his_purchase_director_id
            request.approver_id = head

    @api.depends("department_id")
    def _compute_his_purchase_domain(self):
        for request in self:
            request.his_purchase_domain = request.department_id.his_purchase_domain or "general"

    @api.depends("line_ids.estimated_subtotal")
    def _compute_estimated_amount(self):
        for request in self:
            request.estimated_amount = sum(request.line_ids.mapped("estimated_subtotal"))

    def _compute_order_ids(self):
        for request in self:
            orders = request.line_ids.purchase_line_ids.order_id
            request.order_ids = orders
            request.order_count = len(orders)

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._his_check_protected(vals)
            self._his_check_department(vals, self.env["hr.employee"].browse(vals.get("requester_id")))
            if vals.get("name", _("New")) == _("New"):
                company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
                vals["name"] = self.env["ir.sequence"].with_company(company).next_by_code("his.purchase.request") or _(
                    "New"
                )
        return super().create(vals_list)

    def write(self, vals):
        self._his_check_protected(vals)
        for request in self:
            request._his_check_department(vals, request.requester_id)
        # Le fil de discussion (pieces jointes, activites) reste ouvert a tous.
        business = {f for f in vals if f not in FOLLOWUP_FIELDS and not f.startswith(("message_", "activity_"))}
        if business and not self._his_is_purchasing():
            locked = self.filtered(lambda r: r.state != "draft")
            if locked:
                raise UserError(_("%s has been submitted: only the purchasing team can change it now.", locked[0].name))
        res = super().write(vals)
        if "state" in vals:
            self._his_sync_step()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        if any(request.state not in ("draft", "cancel") for request in self):
            raise UserError(_("Only draft or cancelled purchase requests can be deleted."))

    # ------------------------------------------------------------------
    # Droits
    # ------------------------------------------------------------------

    def _his_is_purchasing(self):
        return self.env.su or self.env.user.has_group("purchase.group_purchase_user")

    def _his_check_protected(self, vals):
        protected = PROTECTED_FIELDS & set(vals)
        if protected and not self._his_is_purchasing():
            raise AccessError(_("Only the purchasing team can set: %s.", ", ".join(sorted(protected))))

    def _his_check_department(self, vals, requester):
        """Le departement decide de l'approbateur et du domaine (recette P-07) :
        hors equipe achats, c'est celui du demandeur."""
        if "department_id" not in vals or self._his_is_purchasing():
            return
        if "requester_id" in vals:
            requester = self.env["hr.employee"].browse(vals["requester_id"])
        if (vals["department_id"] or False) != (requester.sudo().department_id.id or False):
            raise AccessError(_("Only the purchasing team can file a request for another department."))

    def _his_check_requester(self):
        for request in self:
            if request.requester_user_id != self.env.user and not self._his_is_purchasing():
                raise AccessError(_("Only the requester or the purchasing team can do this on %s.", request.name))

    def _his_check_approver(self):
        user = self.env.user
        for request in self:
            allowed = (
                self.env.su
                or user == request.approver_id
                or user == request.department_id.manager_id.user_id
                or user.has_group("his_purchase.group_purchase_director")
            )
            if not allowed:
                raise AccessError(
                    _(
                        "%(request)s can only be approved by %(approver)s.",
                        request=request.name,
                        approver=request.approver_id.name or _("the head of department"),
                    )
                )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_submit(self):
        self._his_check_requester()
        for request in self:
            if request.state != "draft":
                raise UserError(_("%s is not a draft.", request.name))
            missing = []
            if not request.justification:
                missing.append(_("Justification"))
            if not request.date_required:
                missing.append(_("Required By"))
            if not request.line_ids:
                missing.append(_("at least one line"))
            if missing:
                raise ValidationError(
                    _("To submit %(request)s, fill in: %(fields)s.", request=request.name, fields=", ".join(missing))
                )
            if request.date_required < fields.Date.context_today(request):
                raise ValidationError(_("The required date of %s is in the past.", request.name))
            if not request.approver_id:
                raise UserError(
                    _(
                        "%s has no approver: set a head on the department, or an executive director in the Purchase settings.",
                        request.name,
                    )
                )
        self.sudo().write({"state": "submitted"})
        for request in self:
            request.sudo().message_subscribe(partner_ids=request.approver_id.partner_id.ids)
        return True

    def action_approve(self):
        self._his_check_approver()
        for request in self:
            if request.state != "submitted":
                raise UserError(_("%s is not waiting for approval.", request.name))
            officer = request.user_id or request.company_id.his_purchase_officer_id
            request.sudo().write(
                {
                    "state": "approved",
                    "approved_by_id": self.env.user.id,
                    "approved_on": fields.Datetime.now(),
                    "user_id": officer.id,
                }
            )
            if officer:
                request.sudo().message_subscribe(partner_ids=officer.partner_id.ids)
        return True

    def action_open_reject(self):
        self._his_check_approver()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reject Purchase Request"),
            "res_model": "his.purchase.request.reject",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def _his_reject(self, reason):
        self._his_check_approver()
        for request in self:
            if request.state != "submitted":
                raise UserError(_("%s is not waiting for approval.", request.name))
            request.sudo().write({"state": "draft"})
            request.sudo()._his_notify(
                request.requester_user_id, lambda r, name=self.env.user.name: r._his_text_rejected(name, reason)
            )

    def _his_text_rejected(self, user_name, reason):
        return _("Rejected by %(user)s: %(reason)s", user=user_name, reason=reason)

    def action_cancel(self):
        self._his_check_requester()
        for request in self:
            if request.state in ("ordered", "done"):
                raise UserError(_("%s is already ordered: cancel its purchase orders first.", request.name))
            if request.state not in ("draft", "submitted") and not self._his_is_purchasing():
                raise UserError(_("Ask the purchasing team to cancel %s.", request.name))
        self.sudo().write({"state": "cancel"})
        return True

    def action_draft(self):
        self._his_check_requester()
        if any(request.state != "cancel" for request in self):
            raise UserError(_("Only a cancelled request can be reset to draft."))
        self.sudo().write({"state": "draft"})
        return True

    def action_open_source(self):
        self.ensure_one()
        if not self._his_is_purchasing():
            raise AccessError(_("Only the purchasing team can source a request."))
        if self.state not in ("approved", "sourcing"):
            raise UserError(_("Only an approved request can be sourced."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Source Purchase Request"),
            "res_model": "his.purchase.request.source",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def action_remind(self):
        """Le demandeur relance celui qui tient sa demande, une fois par 24 h."""
        self.ensure_one()
        self._his_check_requester()
        if self.state not in OPEN_STATES:
            raise UserError(_("Only an open request can be reminded."))
        now = fields.Datetime.now()
        if self.his_last_nudge and now - self.his_last_nudge < timedelta(hours=NUDGE_HOURS):
            raise UserError(_("You already sent a reminder in the last 24 hours."))
        step = self._his_step()
        owner = step["owner"] if step else self.user_id or self.company_id.his_purchase_officer_id
        if not owner:
            raise UserError(_("Nobody holds this request yet: contact the purchasing team."))
        self.sudo().his_last_nudge = now
        user_name = self.env.user.name
        self.sudo()._his_notify(owner, lambda r: r._his_text_nudge(user_name))
        return True

    def _his_text_nudge(self, user_name):
        return _("%(user)s is waiting on %(request)s.", user=user_name, request=self.name)

    def _his_text_urgent(self):
        return _(
            "%(request)s is needed by %(date)s and nothing is ordered yet.",
            request=self.name,
            date=format_date(self.env, self.date_required),
        )

    def _his_text_urgent_label(self):
        return _("Urgent: %s needed soon", self.name)

    def action_view_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("purchase.purchase_rfq")
        action["domain"] = [("id", "in", self.order_ids.ids)]
        action["context"] = {"create": False}
        return action

    # ------------------------------------------------------------------
    # Avancement d'apres les commandes
    # ------------------------------------------------------------------

    def _his_update_progress(self):
        for request in self.filtered(lambda r: r.state in ("sourcing", "ordered", "done")):
            covered = all(line.qty_ordered >= line.product_qty for line in request.line_ids)
            if not covered:
                state = "sourcing"
            else:
                # Terminee quand tout le materiel est recu ; un service n'a rien a recevoir.
                lines = request.line_ids.purchase_line_ids.filtered(
                    lambda p: p.order_id.state == "purchase" and p.product_id.type != "service"
                )
                received = all(p.qty_received >= p.product_qty for p in lines)
                state = "done" if received else "ordered"
            if state != request.state:
                request.sudo().state = state

    # ------------------------------------------------------------------
    # Suivi
    # ------------------------------------------------------------------

    def _his_step(self):
        self.ensure_one()
        manager, director = self._his_company_people(self.company_id)
        since = self.his_step_since or fields.Date.context_today(self)
        if self.state == "submitted":
            owner = self.approver_id
            return {
                "key": "request_approve",
                "label": _("Approve purchase request %s", self.name),
                "owner": owner,
                "due": add_working_days(since, DAYS_TO_APPROVE),
                "chain": [(DAYS_TO_ESCALATE, manager - owner), (DAYS_TO_ESCALATE, director - owner)],
            }
        if self.state == "approved":
            owner = self.user_id or manager
            return {
                "key": "request_source",
                "label": _("Source purchase request %s", self.name),
                "owner": owner,
                "due": add_working_days(since, DAYS_TO_SOURCE),
                "chain": [(DAYS_TO_ESCALATE, manager - owner), (DAYS_TO_ESCALATE, director - owner)],
            }
        return None

    def _his_alert_urgent(self):
        """Besoin dans moins de 5 jours et rien de commande : alerte, quel que soit l'etat."""
        today = fields.Date.context_today(self)
        for request in self:
            if request.his_urgent_alert_sent or not request.date_required:
                continue
            if request.date_required - today > timedelta(days=URGENT_DAYS):
                continue
            manager, _director = self._his_company_people(request.company_id)
            users = (request.user_id or request.company_id.his_purchase_officer_id) | manager
            if users:
                request._his_notify(users, lambda r: r._his_text_urgent())
                request._his_schedule(users, lambda r: r._his_text_urgent_label(), today)
            request.his_urgent_alert_sent = True

    @api.model
    def _cron_his_followup(self):
        self.search([("state", "in", ("sourcing", "ordered"))])._his_update_progress()
        if fields.Date.context_today(self).weekday() in WEEKEND:
            # Ni rappel ni escalade vendredi et samedi (recette P-06) : dimanche rattrape.
            return
        requests = self.search([("state", "in", list(OPEN_STATES))])
        requests._his_run_followup()
        requests._his_alert_urgent()
        self.env["purchase.order"]._cron_his_followup()
        self.env["purchase.requisition"]._cron_his_followup()

    @api.model
    def _cron_his_weekly_digest(self):
        """Lundi : toutes les demandes ouvertes, la plus ancienne d'abord."""
        for company in self.env["res.company"].search([]):
            manager, director = self._his_company_people(company)
            recipients = (manager | director).partner_id.filtered("email")
            if not recipients:
                continue
            requests = self.search(
                [("company_id", "=", company.id), ("state", "in", list(OPEN_STATES))], order="create_date asc"
            )
            body = self.env["ir.qweb"]._render(
                "his_purchase.weekly_digest_body",
                {"requests": requests, "company": company, "today": fields.Date.context_today(self)},
            )
            self.env["mail.mail"].sudo().create(
                {
                    "subject": _("Open purchase requests: %s", len(requests)),
                    "body_html": body,
                    "email_from": company.email_formatted or self.env.user.email_formatted,
                    "recipient_ids": [(6, 0, recipients.ids)],
                    "auto_delete": True,
                }
            )


class HisPurchaseRequestLine(models.Model):
    _name = "his.purchase.request.line"
    _description = "Purchase Request Line"
    _order = "request_id, sequence, id"

    sequence = fields.Integer(default=10)
    request_id = fields.Many2one("his.purchase.request", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="request_id.company_id", store=True)
    state = fields.Selection(related="request_id.state")
    product_id = fields.Many2one(
        "product.product", string="Product", domain=[("purchase_ok", "=", True)], check_company=True
    )
    description = fields.Char(string="Description")
    product_qty = fields.Float(string="Quantity", digits="Product Unit", default=1.0, required=True)
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Unit",
        compute="_compute_product_uom_id",
        store=True,
        readonly=False,
        required=True,
        precompute=True,
    )
    currency_id = fields.Many2one(related="request_id.currency_id")
    estimated_price_unit = fields.Monetary(string="Estimated Unit Price")
    estimated_subtotal = fields.Monetary(
        string="Estimated Subtotal", compute="_compute_estimated_subtotal", store=True, precompute=True
    )
    purchase_line_ids = fields.One2many("purchase.order.line", "his_request_line_id", string="Order Lines")
    qty_ordered = fields.Float(
        string="Ordered", compute="_compute_qty_ordered", compute_sudo=True, digits="Product Unit"
    )
    qty_in_progress = fields.Float(
        string="Quantity Being Sourced", compute="_compute_qty_ordered", compute_sudo=True, digits="Product Unit"
    )
    his_monthly_requisition_id = fields.Many2one(
        "purchase.requisition",
        string="Next Monthly Order",
        readonly=True,
        copy=False,
        help="Waiting to be added to the next monthly order of this blanket order.",
    )

    _check_qty = models.Constraint("CHECK(product_qty > 0)", "The quantity must be greater than zero.")

    @api.depends("product_id")
    def _compute_product_uom_id(self):
        for line in self:
            if line.product_id:
                line.product_uom_id = line.product_id.uom_id
            elif not line.product_uom_id:
                line.product_uom_id = self.env.ref("uom.product_uom_unit")

    @api.depends("product_qty", "estimated_price_unit")
    def _compute_estimated_subtotal(self):
        for line in self:
            line.estimated_subtotal = line.product_qty * line.estimated_price_unit

    @api.depends(
        "product_uom_id", "purchase_line_ids.product_qty", "purchase_line_ids.product_uom_id", "purchase_line_ids.state"
    )
    def _compute_qty_ordered(self):
        for line in self:
            confirmed = line.purchase_line_ids.filtered(lambda p: p.state in ("to approve", "purchase"))
            drafts = line.purchase_line_ids.filtered(lambda p: p.state in ("draft", "sent"))
            line.qty_ordered = sum(
                p._his_qty_in_request_uom() for p in confirmed.filtered(lambda p: p.state == "purchase")
            )
            # Ce qui reste a sourcer : les demandes de prix concurrentes visent le
            # meme besoin, elles comptent une fois (la plus grosse), pas en somme.
            line.qty_in_progress = sum(p._his_qty_in_request_uom() for p in confirmed) + max(
                [p._his_qty_in_request_uom() for p in drafts] or [0.0]
            )

    @api.constrains("product_id", "description", "product_qty")
    def _check_product_or_description(self):
        for line in self:
            if not line.product_id and not line.description:
                raise ValidationError(_("Each line needs a product or a description."))

    @api.constrains("estimated_price_unit")
    def _check_estimate(self):
        if any(line.estimated_price_unit < 0 for line in self):
            raise ValidationError(_("The estimated price cannot be negative."))

    def _his_check_editable(self):
        if self.env.su or self.env.user.has_group("purchase.group_purchase_user"):
            return
        if any(line.request_id.state != "draft" for line in self):
            raise UserError(_("A submitted request can only be changed by the purchasing team."))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._his_check_editable()
        return lines

    def write(self, vals):
        self._his_check_editable()
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_editable(self):
        self._his_check_editable()

    def _his_remaining_qty(self):
        self.ensure_one()
        return max(self.product_qty - self.qty_in_progress, 0.0)
