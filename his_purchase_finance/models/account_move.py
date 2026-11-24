# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Rapprochement commande / reception / facture (decision 6 du 2026-11-22).

Community n'a pas de rapprochement a 3 : on compare chaque ligne de facture a
sa ligne de commande, sans tolerance. Non conforme -> « En reserve », avec
la liste des ecarts, et le paiement bloque (payment_state « blocked » du
coeur, que l'enregistrement d'un paiement refuse). La Finance relance la
verification, libere avec un motif ecrit, ou refuse.
Une facture sans commande est mise en reserve : la Finance la libere avec un
motif (loyer, electricite...). Un acompte aussi : la liberation vaut
autorisation (complement du 2026-11-24).
"""

from markupsafe import Markup
from odoo import _, fields, models
from odoo.exceptions import UserError

from .common import is_finance

CHECK_FIELDS = {"his_check_state", "his_check_reason", "his_first_check_done", "his_first_check_clean"}
HELD = ("waiting", "reserve", "refused")
CHECK_STATES = [
    ("waiting", "Waiting"),
    ("reserve", "On Hold"),
    ("validated", "Validated"),
    ("refused", "Refused"),
]


class AccountMove(models.Model):
    _inherit = "account.move"

    his_check_state = fields.Selection(
        CHECK_STATES, string="Finance Check", readonly=True, copy=False, tracking=True, index="btree_not_null"
    )
    his_check_reason = fields.Text(string="Finance Check Reason", readonly=True, copy=False)
    his_first_check_done = fields.Boolean(readonly=True, copy=False)
    # Procedure 7.3 : l'original papier, son detenteur et sa conformite au scan.
    his_original_state = fields.Selection(
        [
            ("missing", "Not Received"),
            ("compliant", "Received, Matches the Scan"),
            ("not_compliant", "Received, Differs"),
        ],
        string="Paper Original",
        default="missing",
        tracking=True,
        copy=False,
    )
    his_original_received_on = fields.Date(string="Original Received On", copy=False)
    his_original_holder_id = fields.Many2one("res.users", string="Original Held By", copy=False)
    his_original_note = fields.Char(string="Original Note", copy=False)
    his_first_check_clean = fields.Boolean(
        string="Compliant at First Check", readonly=True, copy=False, help="For the monthly indicator."
    )

    def _his_is_checked_bill(self):
        self.ensure_one()
        if self.move_type == "in_invoice" and self.company_id.his_finance_confirms:
            return True
        return self.move_type in ("in_invoice", "in_refund") and bool(self.invoice_line_ids.purchase_line_id)

    def _his_header_mismatches(self, order):
        """Fournisseur et conditions de paiement de la facture contre la commande."""
        issues = []
        supplier = order.partner_id.commercial_partner_id
        if self.commercial_partner_id != supplier:
            issues.append(
                _(
                    "%(order)s was placed with %(supplier)s, but this bill is from %(billed)s.",
                    order=order.name,
                    supplier=supplier.name,
                    billed=self.commercial_partner_id.name,
                )
            )
        if order.payment_term_id and self.invoice_payment_term_id != order.payment_term_id:
            issues.append(
                _(
                    "%(order)s: payment terms %(ordered)s, billed %(billed)s.",
                    order=order.name,
                    ordered=order.payment_term_id.name,
                    billed=self.invoice_payment_term_id.name or _("none"),
                )
            )
        return issues

    def _his_order_mismatches(self, order):
        """Ecarts propres a une commande liee (les anomalies ouvertes s'y ajoutent)."""
        return []

    def _his_mismatches(self):
        """Les ecarts de la facture avec ses commandes et receptions ; vide si conforme."""
        self.ensure_one()
        issues = []
        product_lines = self.invoice_line_ids.filtered(lambda line: line.display_type == "product")
        if not product_lines.purchase_line_id:
            return [_("No purchase order: Finance must release this bill with a reason.")]
        for line in product_lines:
            pol = line.purchase_line_id
            label = line.product_id.display_name or line.name
            if not pol:
                issues.append(_("%s is not on the purchase order.", label))
                continue
            order = pol.order_id
            if pol.is_downpayment:
                # La deduction de l'acompte sur la facture finale (quantite
                # negative) a deja ete autorisee : seul l'acompte lui-meme l'est.
                if self.move_type == "in_invoice" and line.quantity > 0:
                    issues.append(_("Down payment on %s: needs Finance's authorisation.", order.name))
                continue
            if line.currency_id != order.currency_id:
                issues.append(
                    _(
                        "%(line)s: invoiced in %(currency)s, ordered in another currency.",
                        line=label,
                        currency=line.currency_id.name,
                    )
                )
                continue
            # Prix net dans l'unite de la commande : 12 unites a 100 = 1 carton a 1 200.
            billed = line.product_uom_id._compute_price(
                line.price_unit * (1 - (line.discount or 0.0) / 100), pol.product_uom_id
            )
            ordered = pol.price_unit * (1 - (pol.discount or 0.0) / 100)
            if order.currency_id.compare_amounts(billed, ordered):
                issues.append(
                    _(
                        "%(line)s: invoiced at %(billed)s, ordered at %(ordered)s.",
                        line=label,
                        billed=order.currency_id.format(billed),
                        ordered=order.currency_id.format(ordered),
                    )
                )
            if line.tax_ids != pol.tax_ids:
                issues.append(_("%s: taxes differ from the purchase order.", label))
            if self.move_type != "in_invoice":
                continue
            if pol.product_id.type == "service" and not order.his_service_done_on:
                issues.append(
                    _("%(line)s: the service on %(order)s has not been confirmed done.", line=label, order=order.name)
                )
            elif pol.product_uom_id.compare(pol.qty_invoiced, pol.qty_received) > 0:
                issues.append(
                    _(
                        "%(line)s: %(invoiced)s %(uom)s invoiced so far, %(received)s received.",
                        line=label,
                        invoiced=pol.qty_invoiced,
                        received=pol.qty_received,
                        uom=pol.product_uom_id.name,
                    )
                )
        for order in product_lines.purchase_line_id.order_id:
            if self.move_type != "in_refund":
                # L'argent qui revient ne se bloque pas ; l'assistant d'avoir
                # vide d'ailleurs les conditions de paiement.
                issues.extend(self._his_header_mismatches(order))
            issues.extend(self._his_order_mismatches(order))
        return issues

    def _his_run_check(self):
        for move in self.filtered(lambda m: m.state == "posted" and m._his_is_checked_bill()):
            issues = move._his_mismatches()
            vals = {
                "his_check_state": "reserve" if issues else "validated",
                "his_check_reason": "\n".join(issues) or False,
            }
            if not move.his_first_check_done:
                vals.update(his_first_check_done=True, his_first_check_clean=not issues)
            move.sudo().write(vals)
            move._his_sync_payment_block()
            if issues:
                move.message_post(
                    body=Markup("%s<ul>%s</ul>")
                    % (
                        _("Put on hold by the purchase order check:"),
                        Markup("").join(Markup("<li>%s</li>") % i for i in issues),
                    )
                )

    def _his_sync_payment_block(self):
        for move in self.sudo():
            if move.his_check_state == "validated":
                if move.payment_state == "blocked":
                    move.payment_state = "not_paid"
                    self.env.add_to_compute(move._fields["payment_state"], move)
            elif move.payment_state not in ("paid", "in_payment", "reversed", "blocked"):
                move.payment_state = "blocked"

    def _post(self, soft=True):
        posted = super()._post(soft)
        posted._his_run_check()
        return posted

    def button_draft(self):
        res = super().button_draft()
        self.filtered("his_check_state").sudo().write({"his_check_state": "waiting", "his_check_reason": False})
        return res

    def write(self, vals):
        # « readonly » n'arrete pas un appel RPC : seul le code (en sudo) decide.
        if CHECK_FIELDS & set(vals) and not self.env.su:
            raise UserError(_("The purchase order check is set by Finance decisions only."))
        return super().write(vals)

    def action_toggle_block_payment(self):
        # Le deblocage du coeur rendrait payable une facture en reserve sans
        # motif ecrit : la Finance passe par « Liberer ».
        if self.filtered(lambda m: m.his_check_state in HELD):
            raise UserError(_("This bill is held by the purchase order check: Finance releases it with a reason."))
        return super().action_toggle_block_payment()

    # ------------------------------------------------------------------
    # Decisions de la Finance
    # ------------------------------------------------------------------

    def _his_check_finance(self):
        if not is_finance(self.env):
            raise UserError(_("Only Finance can decide on a vendor bill check."))

    def action_his_check_again(self):
        self._his_check_finance()
        self._his_run_check()
        return True

    def _his_action_decision(self, decision):
        self.ensure_one()
        self._his_check_finance()
        return {
            "type": "ir.actions.act_window",
            "name": _("Release Bill") if decision == "release" else _("Refuse Bill"),
            "res_model": "his.bill.decision",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id, "default_decision": decision},
        }

    def action_open_release(self):
        return self._his_action_decision("release")

    def action_open_refuse(self):
        return self._his_action_decision("refuse")

    def _his_decide(self, decision, reason):
        self._his_check_finance()
        for move in self:
            if move.state != "posted" or not move.his_check_state:
                raise UserError(_("%s is not a checked vendor bill.", move.name))
            if decision == "release":
                body = _("Released by %(user)s despite the check: %(reason)s", user=self.env.user.name, reason=reason)
                move.sudo().write({"his_check_state": "validated", "his_check_reason": body})
            else:
                body = _("Refused by %(user)s: %(reason)s", user=self.env.user.name, reason=reason)
                move.sudo().write({"his_check_state": "refused", "his_check_reason": body})
            move._his_sync_payment_block()
            move.message_post(body=body)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def reconcile(self):
        # Le lettrage (widget « Ajouter », assistant des ecritures) paie une
        # facture sans passer par l'enregistrement du paiement : une facture en
        # reserve ne se lettre qu'avec une autre facture ou un avoir.
        held = self.move_id.filtered(lambda m: m.his_check_state in HELD)
        if held and (self.move_id - held).filtered(lambda m: m.move_type not in ("in_invoice", "in_refund")):
            raise UserError(
                _("%s is held by the purchase order check: Finance must validate or release it first.", held[0].name)
            )
        return super().reconcile()


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _his_recheck_bills(self):
        self.env["account.move"].search(
            [("invoice_line_ids.purchase_line_id.order_id", "in", self.ids), ("his_check_state", "=", "reserve")]
        )._his_run_check()
