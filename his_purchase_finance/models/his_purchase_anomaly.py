# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Anomalies d'achat (procedure Finance, etape 6.4).

Declaree par le receptionnaire, le departement, l'acheteur ou la Finance ;
l'acheteur propose la solution avec le fournisseur ; la Finance la valide ;
l'acheteur l'execute ; la Finance clot apres les justificatifs. Tant qu'une
anomalie est ouverte, les factures de la commande restent en reserve.
"""

from odoo import _, api, fields, models
from odoo.addons.his_purchase.models.his_purchase_followup import add_working_days
from odoo.exceptions import AccessError, UserError

from .common import is_finance

KINDS = [
    ("shortage", "Shortage"),
    ("damage", "Damage"),
    ("non_compliance", "Non-Compliance"),
    ("invoice", "Invoice or Price Discrepancy"),
    ("service", "Service Not Compliant"),
    ("other", "Other"),
]
SOLUTIONS = [
    ("replacement", "Replacement"),
    ("return", "Return"),
    ("complement", "Complementary Delivery"),
    ("correction", "Correction"),
    ("credit_note", "Credit Note"),
    ("other", "Other"),
]
STATES = [
    ("declared", "Declared"),
    ("proposed", "Solution Proposed"),
    ("approved", "Approved by Finance"),
    ("executed", "Carried Out"),
    ("closed", "Closed"),
    ("cancelled", "Cancelled"),
]
OPEN_STATES = ("declared", "proposed", "approved", "executed")
DAYS_TO_ACT = 2
DAYS_TO_EXECUTE = 5
# Ecrits seulement par le circuit (en sudo).
WORKFLOW_FIELDS = {"state", "order_id", "declared_by_id", "declared_on", "picking_id", "move_id", "company_id"}


class HisPurchaseAnomaly(models.Model):
    _name = "his.purchase.anomaly"
    _description = "Purchase Anomaly"
    _inherit = ["mail.thread", "mail.activity.mixin", "his.purchase.followup.mixin"]
    _order = "id desc"

    name = fields.Char(string="Reference", readonly=True, copy=False, default=lambda self: _("New"))
    order_id = fields.Many2one("purchase.order", string="Purchase Order", required=True, readonly=True, index=True)
    picking_id = fields.Many2one("stock.picking", string="Receipt", readonly=True)
    move_id = fields.Many2one("account.move", string="Vendor Bill", readonly=True)
    partner_id = fields.Many2one(related="order_id.partner_id", store=True, string="Supplier")
    company_id = fields.Many2one(related="order_id.company_id", store=True)
    kind = fields.Selection(KINDS, string="Type", required=True, tracking=True)
    description = fields.Text(string="Description", required=True)
    declared_by_id = fields.Many2one("res.users", string="Declared By", readonly=True)
    declared_on = fields.Datetime(string="Declared On", readonly=True)
    solution = fields.Selection(SOLUTIONS, string="Solution", tracking=True)
    solution_note = fields.Text(string="Solution Details")
    finance_note = fields.Text(string="Finance Assessment", help="Financial, accounting and tax impact.")
    state = fields.Selection(STATES, string="Status", default="declared", required=True, tracking=True, readonly=True)

    # ------------------------------------------------------------------
    # Declaration
    # ------------------------------------------------------------------

    @api.model
    def _his_may_declare(self, order, user):
        return (
            user.has_group("purchase.group_purchase_user")
            or user.has_group("stock.group_stock_user")
            or order._his_may_certify_service(user)
        )

    @api.model
    def _his_declare(self, order, kind, description, picking=None, bill=None):
        user = self.env.user
        if not self.env.su and not self._his_may_declare(order.sudo(), user):
            raise AccessError(_("You cannot declare an anomaly on %s.", order.sudo().name))
        order = order.sudo()
        anomaly = self.sudo().create(
            {
                "name": self.env["ir.sequence"].sudo().next_by_code("his.purchase.anomaly") or _("New"),
                "order_id": order.id,
                "picking_id": picking.id if picking else False,
                "move_id": bill.id if bill else False,
                "kind": kind,
                "description": description,
                "declared_by_id": user.id,
                "declared_on": fields.Datetime.now(),
            }
        )
        anomaly.message_subscribe(partner_ids=user.partner_id.ids)
        order.message_post(body=_("Anomaly %(name)s declared by %(user)s.", name=anomaly.name, user=user.name))
        anomaly._his_sync_step()
        order._his_recheck_open_bills()
        return anomaly.with_env(self.env)

    # ------------------------------------------------------------------
    # Circuit
    # ------------------------------------------------------------------

    def write(self, vals):
        if WORKFLOW_FIELDS & set(vals) and not self.env.su:
            raise UserError(_("The status of an anomaly changes through its buttons only."))
        if "finance_note" in vals and not is_finance(self.env):
            raise AccessError(_("Only Finance writes its assessment."))
        if {"solution", "solution_note"} & set(vals) and not self._his_is_buyer():
            raise AccessError(_("Only the purchasing team proposes the solution."))
        return super().write(vals)

    def _his_is_buyer(self):
        return self.env.su or self.env.user.has_group("purchase.group_purchase_user")

    def _his_move(self, from_states, to_state, allowed, message):
        if not allowed:
            raise AccessError(_("You cannot do this on an anomaly."))
        for anomaly in self:
            if anomaly.state not in from_states:
                raise UserError(_("%(name)s is %(state)s.", name=anomaly.name, state=anomaly._his_state_label()))
        self.sudo().write({"state": to_state})
        for anomaly in self:
            anomaly.message_post(body=message)
        self._his_sync_step()

    def _his_state_label(self):
        return dict(self._fields["state"]._description_selection(self.env))[self.state]

    def action_propose(self):
        for anomaly in self:
            if not anomaly.solution:
                raise UserError(_("Choose the solution agreed with the supplier for %s.", anomaly.name))
        self._his_move(("declared",), "proposed", self._his_is_buyer(), _("Solution proposed to Finance."))

    def action_approve(self):
        self._his_move(("proposed",), "approved", is_finance(self.env), _("Solution approved by Finance."))

    def action_execute(self):
        self._his_move(("approved",), "executed", self._his_is_buyer(), _("Solution carried out with the supplier."))

    def action_close(self):
        self._his_move(("executed",), "closed", is_finance(self.env), _("Closed by Finance."))
        self.order_id._his_recheck_bills()

    def action_cancel(self):
        for anomaly in self:
            if not (anomaly.finance_note or "").strip():
                raise UserError(_("Explain in the Finance assessment why %s is cancelled.", anomaly.name))
        self._his_move(OPEN_STATES, "cancelled", is_finance(self.env), _("Cancelled by Finance."))
        self.order_id._his_recheck_bills()

    # ------------------------------------------------------------------
    # Suivi
    # ------------------------------------------------------------------

    def _his_step(self):
        self.ensure_one()
        order = self.order_id.sudo()
        buyer = order.user_id or order.company_id.his_purchase_manager_id
        finance = order._his_finance_users()
        since = self.his_step_since or fields.Date.context_today(self)
        steps = {
            "declared": (_("Propose a solution for anomaly %s", self.name), buyer, DAYS_TO_ACT),
            "proposed": (_("Approve the solution of anomaly %s", self.name), finance, DAYS_TO_ACT),
            "approved": (_("Carry out the solution of anomaly %s", self.name), buyer, DAYS_TO_EXECUTE),
            "executed": (_("Close anomaly %s", self.name), finance, DAYS_TO_ACT),
        }
        if self.state not in steps:
            return None
        label, owner, days = steps[self.state]
        return {
            "key": "anomaly_" + self.state,
            "label": label,
            "owner": owner,
            "due": add_working_days(since, days),
            "chain": [],
        }


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    his_anomaly_ids = fields.One2many("his.purchase.anomaly", "order_id", string="Anomalies")
    his_anomaly_count = fields.Integer(string="Anomaly Count", compute="_compute_his_anomaly_count", compute_sudo=True)

    @api.depends("his_anomaly_ids")
    def _compute_his_anomaly_count(self):
        for order in self:
            order.his_anomaly_count = len(order.his_anomaly_ids)

    def _his_open_anomalies(self):
        return self.sudo().his_anomaly_ids.filtered(lambda a: a.state in OPEN_STATES)

    def _his_recheck_open_bills(self):
        """Une anomalie declaree remet en reserve les factures validees non payees."""
        self.env["account.move"].sudo().search(
            [
                ("invoice_line_ids.purchase_line_id.order_id", "in", self.ids),
                ("state", "=", "posted"),
                ("his_check_state", "in", ("validated", "reserve")),
                ("payment_state", "not in", ("paid", "in_payment", "reversed")),
            ]
        )._his_run_check()

    def action_his_declare_anomaly(self):
        self.ensure_one()
        return self.env["his.anomaly.declare"]._his_action(self.ids)

    def action_view_his_anomalies(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Anomalies"),
            "res_model": "his.purchase.anomaly",
            "view_mode": "list,form",
            "domain": [("order_id", "=", self.id)],
        }


class AccountMove(models.Model):
    _inherit = "account.move"

    def _his_order_mismatches(self, order):
        issues = super()._his_order_mismatches(order)
        for anomaly in order._his_open_anomalies():
            issues.append(_("Anomaly %(name)s is open on %(order)s.", name=anomaly.name, order=order.name))
        return issues

    def action_his_declare_anomaly(self):
        self.ensure_one()
        orders = self.invoice_line_ids.purchase_line_id.order_id
        if not orders:
            raise UserError(_("This bill is not linked to a purchase order."))
        return self.env["his.anomaly.declare"]._his_action(orders.ids, bill=self)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_his_declare_anomaly(self):
        self.ensure_one()
        if not self.purchase_id:
            raise UserError(_("This receipt is not linked to a purchase order."))
        return self.env["his.anomaly.declare"]._his_action(self.purchase_id.ids, picking=self)


class HisPurchaseRequest(models.Model):
    _inherit = "his.purchase.request"

    def action_open_his_anomaly(self):
        self.ensure_one()
        orders = self.sudo().order_ids.filtered(lambda o: o.state in ("purchase", "done"))
        return self.env["his.anomaly.declare"]._his_action(orders.ids)

    @api.model
    def _cron_his_followup(self):
        res = super()._cron_his_followup()
        self.env["his.purchase.anomaly"].search([("state", "in", OPEN_STATES)])._his_run_followup()
        return res
