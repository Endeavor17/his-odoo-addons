# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""La commande : l'acheteur la prepare et l'envoie, seule la Finance la confirme.

- Envoyer a la Finance demande toujours le motif du choix (meme une seule
  offre) et applique la regle des devis : a partir de 100 000 DA HT, 3 devis,
  sinon une derogation ecrite (decision 3 du 2026-11-22).
- Une commande envoyee ne change plus que par la Finance, qui la confirme ou
  la renvoie a l'acheteur avec un motif.
- Confirmer exige un fournisseur valide, sans piece expiree ni non conforme
  (decision 4). L'approbation routee de his_purchase suit, inchangee.
"""

from odoo import _, api, fields, models
from odoo.addons.his_purchase.models.his_purchase_followup import add_working_days
from odoo.exceptions import UserError

from .common import is_finance

QUOTE_THRESHOLD = 100_000
QUOTES_REQUIRED = 3
DAYS_TO_CONFIRM = 2
LOCKED_WHEN_SENT = {"partner_id", "currency_id", "order_line"}


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    his_sent_to_finance_on = fields.Datetime(string="Sent to Finance On", readonly=True, copy=False, tracking=True)
    his_sent_to_finance_by_id = fields.Many2one("res.users", string="Sent to Finance By", readonly=True, copy=False)
    his_finance_confirms = fields.Boolean(related="company_id.his_finance_confirms")
    his_can_confirm = fields.Boolean(compute="_compute_his_can_confirm")

    @api.depends("company_id.his_finance_confirms", "his_sent_to_finance_on")
    @api.depends_context("uid")
    def _compute_his_can_confirm(self):
        finance = is_finance(self.env)
        for order in self:
            order.his_can_confirm = not order.his_finance_confirms or (finance and bool(order.his_sent_to_finance_on))

    # ------------------------------------------------------------------
    # Regle des devis
    # ------------------------------------------------------------------

    def _his_amount_company(self):
        """Montant HT dans la devise de la societe : le seuil est en dinars."""
        self.ensure_one()
        return self.currency_id._convert(
            self.amount_untaxed, self.company_id.currency_id, self.company_id, self.date_order or fields.Date.today()
        )

    def _his_quote_count(self):
        self.ensure_one()
        return 1 + len(self._his_competitors())

    def _his_needs_quote_exception(self):
        self.ensure_one()
        currency = self.company_id.currency_id
        return (
            currency.compare_amounts(self._his_amount_company(), QUOTE_THRESHOLD) >= 0
            and self._his_quote_count() < QUOTES_REQUIRED
        )

    # ------------------------------------------------------------------
    # Envoi a la Finance, retour a l'acheteur
    # ------------------------------------------------------------------

    def _his_check_sendable(self):
        for order in self:
            if order.state not in ("draft", "sent"):
                raise UserError(_("%s is not a request for quotation any more.", order.name))
            if order.his_sent_to_finance_on:
                raise UserError(_("%s is already with Finance.", order.name))

    def action_his_send_to_finance(self):
        self.ensure_one()
        self._his_check_sendable()
        self._his_confirm_checks()
        if self.requisition_id:
            # Le contrat-cadre a ete mis en concurrence : il tient lieu de choix.
            self.with_context(his_choice_write=True).write(
                {
                    "his_choice_criterion": "usual_supplier",
                    "his_choice_note": _("Framework contract %s", self.requisition_id.name),
                    "his_chosen_by_id": self.env.user.id,
                    "his_chosen_on": fields.Datetime.now(),
                }
            )
            return self._his_mark_sent()
        action = self._his_action_choice()
        action["name"] = _("Send to Finance")
        action["context"]["his_send_to_finance"] = True
        if not self._his_competitors():
            # Une seule offre : « Meilleur prix » ne veut rien dire, l'acheteur choisit.
            action["context"]["default_criterion"] = False
        return action

    def _his_mark_sent(self):
        self._his_check_sendable()
        for order in self:
            vals = {"his_sent_to_finance_on": fields.Datetime.now(), "his_sent_to_finance_by_id": self.env.user.id}
            if order.his_supplier_answer == "pending":
                # Plus de relance au fournisseur : son offre est retenue.
                vals["his_supplier_answer"] = "quoted"
            order.write(vals)
            order.message_post(body=_("Sent to Finance for confirmation by %s.", self.env.user.name))
        self._his_sync_step()
        return True

    def action_open_his_return(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Return to Buyer"),
            "res_model": "his.finance.return",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_id": self.id},
        }

    def _his_return(self, reason):
        if not is_finance(self.env):
            raise UserError(_("Only Finance can return an order to the buyer."))
        for order in self:
            if not order.his_sent_to_finance_on or order.state not in ("draft", "sent"):
                raise UserError(_("%s is not waiting for Finance.", order.name))
            buyer = order.his_sent_to_finance_by_id or order.user_id
            order.with_context(his_choice_write=True).write(
                {
                    "his_sent_to_finance_on": False,
                    "his_sent_to_finance_by_id": False,
                    "his_choice_criterion": False,
                    "his_choice_note": False,
                    "his_chosen_by_id": False,
                    "his_chosen_on": False,
                }
            )
            order._his_notify(buyer, lambda r, name=self.env.user.name: r._his_text_returned(name, reason))
        self._his_sync_step()

    def _his_text_returned(self, user_name, reason):
        return _("Returned to the buyer by %(user)s: %(reason)s", user=user_name, reason=reason)

    # ------------------------------------------------------------------
    # ORM : une commande envoyee ne change plus que par la Finance
    # ------------------------------------------------------------------

    def _his_check_not_with_finance(self):
        if is_finance(self.env):
            return
        sent = self.filtered(lambda o: o.his_sent_to_finance_on and o.state in ("draft", "sent"))
        if sent:
            raise UserError(_("%s is with Finance: ask Finance to return it before changing it.", sent[0].name))

    def write(self, vals):
        if LOCKED_WHEN_SENT & set(vals):
            self._his_check_not_with_finance()
        return super().write(vals)

    # ------------------------------------------------------------------
    # Confirmation par la Finance
    # ------------------------------------------------------------------

    def button_confirm(self):
        to_check = self.filtered(lambda o: o.state in ("draft", "sent") and o.company_id.his_finance_confirms)
        if to_check and not is_finance(self.env):
            raise UserError(_("Only Finance confirms purchase orders: use “Send to Finance”."))
        for order in to_check:
            if not order.his_sent_to_finance_on:
                raise UserError(_("%s has not been sent to Finance yet.", order.name))
            blockers = order.partner_id._his_supplier_blockers()
            if blockers:
                raise UserError(
                    _("%(order)s cannot be confirmed: %(reasons)s.", order=order.name, reasons="; ".join(blockers))
                )
        return super().button_confirm()

    # ------------------------------------------------------------------
    # Suivi : l'a-faire de la Finance
    # ------------------------------------------------------------------

    @api.model
    def _his_finance_users(self):
        users = self.env.ref("his_purchase_finance.group_finance").all_user_ids.filtered(
            lambda u: u.active and not u.share
        )
        # Les comptes d'administration ont tout : l'a-faire va aux vrais comptables.
        staff = users.filtered(lambda u: not u.has_group("base.group_system"))
        return staff or users

    def _his_step(self):
        self.ensure_one()
        if self.state in ("draft", "sent") and self.his_sent_to_finance_on:
            since = self.his_step_since or fields.Date.context_today(self)
            return {
                "key": "finance_confirm",
                "label": _("Confirm purchase order %s", self.name),
                "owner": self._his_finance_users(),
                "due": add_working_days(since, DAYS_TO_CONFIRM),
                "chain": [],
            }
        return super()._his_step()


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.order_id._his_check_not_with_finance()
        return lines

    def write(self, vals):
        self.order_id._his_check_not_with_finance()
        return super().write(vals)

    def unlink(self):
        self.order_id._his_check_not_with_finance()
        return super().unlink()
