# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Rapprochement commande / reception / facture (decision 6 du 2026-11-22).

Community n'a pas de rapprochement a 3 : on compare chaque ligne de facture a
sa ligne de commande, sans tolerance. Non conforme -> « En reserve », avec
la liste des ecarts, et le paiement bloque (payment_state « blocked » du
coeur, que l'enregistrement d'un paiement refuse). La Finance relance la
verification, libere avec un motif ecrit, ou refuse.
Une facture sans ligne de commande n'est pas verifiee (cas 5, encore ouvert).
"""

from markupsafe import Markup

from odoo import _, fields, models
from odoo.exceptions import UserError

from .common import is_finance

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
    his_first_check_clean = fields.Boolean(
        string="Compliant at First Check", readonly=True, copy=False, help="For the monthly indicator."
    )

    def _his_is_checked_bill(self):
        self.ensure_one()
        return self.move_type in ("in_invoice", "in_refund") and bool(self.invoice_line_ids.purchase_line_id)

    def _his_mismatches(self):
        """Les ecarts de la facture avec ses commandes et receptions ; vide si conforme."""
        self.ensure_one()
        issues = []
        for line in self.invoice_line_ids.filtered(lambda line: line.display_type == "product"):
            pol = line.purchase_line_id
            label = line.product_id.display_name or line.name
            if not pol:
                issues.append(_("%s is not on the purchase order.", label))
                continue
            order = pol.order_id
            if line.currency_id != order.currency_id:
                issues.append(_("%(line)s: invoiced in %(currency)s, ordered in another currency.", line=label, currency=line.currency_id.name))
                continue
            # Prix net dans l'unite de la commande : 12 unites a 100 = 1 carton a 1 200.
            billed = line.product_uom_id._compute_price(line.price_unit * (1 - (line.discount or 0.0) / 100), pol.product_uom_id)
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
                issues.append(_("%(line)s: the service on %(order)s has not been confirmed done.", line=label, order=order.name))
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
        return issues

    def _his_run_check(self):
        for move in self.filtered(lambda m: m.state == "posted" and m._his_is_checked_bill()):
            issues = move._his_mismatches()
            vals = {"his_check_state": "reserve" if issues else "validated", "his_check_reason": "\n".join(issues) or False}
            if not move.his_first_check_done:
                vals.update(his_first_check_done=True, his_first_check_clean=not issues)
            move.write(vals)
            move._his_sync_payment_block()
            if issues:
                move.message_post(
                    body=Markup("%s<ul>%s</ul>")
                    % (_("Put on hold by the purchase order check:"), Markup("").join(Markup("<li>%s</li>") % i for i in issues))
                )

    def _his_sync_payment_block(self):
        for move in self:
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
        self.filtered("his_check_state").write({"his_check_state": "waiting", "his_check_reason": False})
        return res

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
                move.write({"his_check_state": "validated", "his_check_reason": body})
            else:
                body = _("Refused by %(user)s: %(reason)s", user=self.env.user.name, reason=reason)
                move.write({"his_check_state": "refused", "his_check_reason": body})
            move._his_sync_payment_block()
            move.message_post(body=body)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _his_recheck_bills(self):
        self.env["account.move"].search(
            [("invoice_line_ids.purchase_line_id.order_id", "in", self.ids), ("his_check_state", "=", "reserve")]
        )._his_run_check()
