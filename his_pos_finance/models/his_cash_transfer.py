# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Versements entre caisses (procedure §4.4), par le compte de liaison 581000.

Remise : 581000 / caisse qui remet. Reception : caisse qui recoit / 581000,
pour le montant compte. Un ecart entre remis et recu passe de 581000 en
476000 et ouvre une fiche d'ecart sur la caisse qui recoit. Cote caisse de
point de vente, le mouvement est une ligne d'especes de la session ouverte,
pour que le solde attendu a la cloture reste juste.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain

EDITABLE_DRAFT = {"from_journal_id", "to_journal_id", "amount_sent", "note"}


class HisCashTransfer(models.Model):
    _name = "his.cash.transfer"
    _description = "Cash Transfer"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(readonly=True, copy=False, default="/")
    from_journal_id = fields.Many2one(
        "account.journal", string="From", required=True, domain="[('type', '=', 'cash')]", tracking=True
    )
    to_journal_id = fields.Many2one(
        "account.journal", string="To", required=True, domain="[('type', '=', 'cash')]", tracking=True
    )
    company_id = fields.Many2one(related="from_journal_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    from_session_id = fields.Many2one("pos.session", readonly=True)
    to_session_id = fields.Many2one("pos.session", readonly=True)
    amount_sent = fields.Monetary(required=True, tracking=True)
    amount_received = fields.Monetary(readonly=True, tracking=True)
    sent_by = fields.Many2one("res.users", readonly=True)
    received_by = fields.Many2one("res.users", readonly=True)
    # a la caisse, le compte est partage par le comptoir : la personne est
    # l'employe qui a tape son nom et son PIN
    sent_employee_id = fields.Many2one("hr.employee", string="Handed Over by", readonly=True)
    received_employee_id = fields.Many2one("hr.employee", string="Counted by", readonly=True)
    sent_at = fields.Datetime(readonly=True)
    received_at = fields.Datetime(readonly=True)
    note = fields.Text()
    send_move_id = fields.Many2one("account.move", readonly=True)
    receive_move_id = fields.Many2one("account.move", readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("sent", "Sent"), ("received", "Received")],
        default="draft",
        required=True,
        readonly=True,
        tracking=True,
    )
    his_discrepancy_ids = fields.One2many("his.cash.discrepancy", "transfer_id", string="Cash Discrepancies")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].sudo().next_by_code("his.cash.transfer") or "/"
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            libres = {f for f in vals if f.startswith(("message_", "activity_"))}
            if set(vals) - libres - EDITABLE_DRAFT or any(t.state != "draft" for t in self):
                raise AccessError(_("Cash transfers change only through their buttons."))
        return super().write(vals)

    # -- comptes et caisses --------------------------------------------------

    def _his_link_account(self):
        account = self.company_id.transfer_account_id
        if not account:
            raise UserError(_("Set the internal transfer account (581000) on the company first."))
        return account

    @api.model
    def _his_open_session(self, journal):
        """La session ouverte de la caisse dont les especes vont dans `journal`."""
        return (
            self.env["pos.session"]
            .sudo()
            .search([("state", "=", "opened"), ("cash_journal_id", "=", journal.id)], limit=1)
        )

    def _his_is_till(self, journal):
        return bool(
            self.env["pos.payment.method"]
            .sudo()
            .search_count([("journal_id", "=", journal.id), ("is_cash_count", "=", True)])
        )

    def _his_move(self, journal, debit_account, credit_account, amount):
        move = (
            self.env["account.move"]
            .sudo()
            .create(
                {
                    "journal_id": journal.id,
                    "ref": self.name,
                    "line_ids": [
                        (0, 0, {"account_id": debit_account.id, "name": self.name, "debit": amount, "credit": 0}),
                        (0, 0, {"account_id": credit_account.id, "name": self.name, "debit": 0, "credit": amount}),
                    ],
                }
            )
        )
        move.action_post()
        return move

    def _his_till_line(self, session, amount, employee=None):
        """Mouvement d'especes de la session, contrepartie 581000.

        pos_hr regroupe les mouvements du popup de cloture par `employee_id` et
        affiche son nom (« false » sans employe), puis le partenaire comme
        caissier de chaque ligne.
        """
        employee = (employee or self.env["hr.employee"]).sudo()
        line = (
            self.env["account.bank.statement.line"]
            .sudo()
            .with_context(no_retrieve_partner=True)
            .create(
                {
                    "journal_id": session.cash_journal_id.id,
                    "amount": amount,
                    "date": fields.Date.context_today(self),
                    "pos_session_id": session.id,
                    "payment_ref": self.name,
                    "employee_id": employee.id,
                    "partner_id": (employee.work_contact_id or self.env.user.partner_id).id,
                    "counterpart_account_id": self._his_link_account().id,
                }
            )
        )
        return line.move_id

    # -- remise --------------------------------------------------------------

    def action_send(self):
        for transfer in self:
            if transfer.state != "draft":
                raise UserError(_("%(name)s is already sent.", name=transfer.name))
            if not (self.env.su or self.env.user.has_group("his_purchase_finance.group_finance")):
                raise AccessError(_("Only Finance sends cash from the back office."))
            if transfer.amount_sent <= 0:
                raise UserError(_("The amount must be positive."))
            if transfer.from_journal_id == transfer.to_journal_id:
                raise UserError(_("Choose two different cash boxes."))
            if transfer._his_is_till(transfer.from_journal_id):
                # sinon la caisse serait debitee hors session, puis une seconde
                # fois comme manquant a l'ouverture suivante
                raise UserError(_("Cash leaves a till only through its own hand over, from the till."))
            source = transfer.from_journal_id
            move = transfer._his_move(
                source, transfer._his_link_account(), source.default_account_id, transfer.amount_sent
            )
            transfer.sudo().write(
                {"state": "sent", "send_move_id": move.id, "sent_by": self.env.uid, "sent_at": fields.Datetime.now()}
            )

    def action_open_receive(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "his.cash.transfer.receive",
            "view_mode": "form",
            "target": "new",
            "context": {"default_transfer_id": self.id, "default_amount": self.amount_sent},
        }

    # -- reception -----------------------------------------------------------

    def _his_receiver_ok(self):
        if self.env.su:
            return True
        user = self.env.user
        if self._his_is_till(self.to_journal_id):
            return user.has_group("point_of_sale.group_pos_user")
        if self.to_journal_id.code == "CDIR":
            return user.has_group("his_purchase.group_purchase_director") or user.has_group(
                "his_pos_finance.group_finance_head"
            )
        return user.has_group("his_purchase_finance.group_finance")

    def action_receive(self, amount):
        self._his_check_receive(amount)
        # Droits verifies : la comptabilite se passe en sudo (un caissier ne lit
        # pas les comptes), l'utilisateur reste trace dans received_by.
        self.sudo()._his_receive(amount, self.env.uid)

    def _his_check_receive(self, amount):
        self.ensure_one()
        if self.state != "sent":
            raise UserError(_("%(name)s is not waiting to be received.", name=self.name))
        if not self._his_receiver_ok():
            raise AccessError(_("You cannot receive cash into %(box)s.", box=self.to_journal_id.display_name))
        if amount < 0:
            raise UserError(_("The amount received cannot be negative."))
        if not self.env.su and self.sent_by == self.env.user:
            # decision 12 : deux personnes, celle qui remet ne compte pas a l'arrivee
            raise UserError(_("You sent %(name)s: someone else receives and counts it.", name=self.name))

    def _his_receive(self, amount, uid, employee=None):
        target = self.to_journal_id
        link = self._his_link_account()
        session = self.env["pos.session"]
        if self._his_is_till(target):
            session = self._his_open_session(target)
            if not session:
                raise UserError(_("Open the till before receiving cash into it."))
            move = self._his_till_line(session, amount, employee) if amount else self.env["account.move"]
        else:
            move = (
                self._his_move(target, target.default_account_id, link, amount) if amount else self.env["account.move"]
            )
        self.write(
            {
                "state": "received",
                "amount_received": amount,
                "receive_move_id": move.id,
                "to_session_id": session.id,
                "received_by": uid,
                "received_employee_id": employee.id if employee else False,
                "received_at": fields.Datetime.now(),
            }
        )
        reste = self.amount_sent - amount
        moves = self.send_move_id | move
        if not self.currency_id.is_zero(reste):
            ecart = self.env["account.account"].search(
                [("code", "=", "476000"), ("company_ids", "in", self.company_id.id)], limit=1
            )
            general = self.env["account.journal"].search(
                [("type", "=", "general"), ("company_id", "=", self.company_id.id)], limit=1
            )
            # reste > 0 : moins recu que remis, 581 garde un solde debiteur.
            residual = self._his_move(general, *((ecart, link) if reste > 0 else (link, ecart)), abs(reste))
            moves |= residual
            self.env["his.cash.discrepancy"].his_open(
                "handover",
                target,
                expected=self.amount_sent,
                counted=amount,
                provisional_move=residual,
                # la note du versement n'explique pas l'ecart : le
                # reviseur saisit l'explication du detenteur sur la fiche
                transfer_id=self.id,
                session_id=session.id,
                holder_id=uid,
            )
        moves.line_ids.filtered(lambda line: line.account_id == link and not line.reconciled).reconcile()


class PosSession(models.Model):
    _inherit = "pos.session"

    his_transfer_ids = fields.One2many("his.cash.transfer", "from_session_id", string="Hand Overs")
    his_no_handover = fields.Boolean(
        string="Closed Without Hand Over", compute="_compute_his_no_handover", search="_search_his_no_handover"
    )

    def _compute_his_no_handover(self):
        for session in self:
            session.his_no_handover = session.state == "closed" and not session.his_transfer_ids

    def _search_his_no_handover(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise NotImplementedError(_("Unsupported search on Closed Without Hand Over."))
        domain = [("state", "=", "closed"), ("his_transfer_ids", "=", False)]
        return domain if (operator == "=") == value else ["!", "&", *domain]

    def _his_till_employee(self, employee_id):
        """Controle l'appel venu de la caisse et renvoie l'employe qui le fait.

        Le compte doit etre un compte de cette caisse (role du comptoir), et
        l'employe doit pouvoir s'y connecter (meme liste que le selecteur de
        caissier de pos_hr). Sans employe transmis (onglet ouvert avant la mise
        a jour), on garde l'employe du compte s'il en a un.
        """
        self.ensure_one()
        config = self.config_id
        config._his_check_cashier()
        Employee = self.env["hr.employee"].sudo()
        if not config.module_pos_hr:
            return Employee
        if not employee_id:
            return Employee.search(
                [("user_id", "=", self.env.uid), ("company_id", "in", (False, self.company_id.id))], limit=1
            )
        employee = Employee.search(
            Domain.AND([config.sudo()._employee_domain(self.env.uid), [("id", "=", int(employee_id))]]), limit=1
        )
        if not employee:
            raise AccessError(_("This cashier cannot work on %(till)s.", till=config.name))
        return employee

    def his_handover(self, amount, note="", employee_id=False):
        """Versement du soir a la Finance depuis la caisse ; renvoie l'id du versement."""
        self.ensure_one()
        employee = self._his_till_employee(employee_id)
        if self.state != "opened" or not self.cash_journal_id:
            raise UserError(_("Hand over only from an open till that takes cash."))
        if amount <= 0 or self.currency_id.compare_amounts(amount, self.cash_register_balance_end) > 0:
            raise UserError(
                _(
                    "Hand over an amount between 0 and the cash expected in the till (%(cash)s).",
                    cash=self.cash_register_balance_end,
                )
            )
        finance = (
            self.env["account.journal"]
            .sudo()
            .search([("code", "=", "CFIN"), ("company_id", "=", self.company_id.id)], limit=1)
        )
        Transfer = self.env["his.cash.transfer"].sudo()
        transfer = Transfer.create(
            {
                "from_journal_id": self.cash_journal_id.id,
                "to_journal_id": finance.id,
                "amount_sent": amount,
                "note": note or False,
                "from_session_id": self.id,
            }
        )
        move = transfer._his_till_line(self, -amount, employee)
        transfer.write(
            {
                "state": "sent",
                "send_move_id": move.id,
                "sent_by": self.env.uid,
                "sent_employee_id": employee.id,
                "sent_at": fields.Datetime.now(),
            }
        )
        return transfer.id

    def his_handover_proposal(self):
        """Ce qu'on propose de verser : les especes attendues moins le fonds fixe."""
        self.ensure_one()
        return max(self.cash_register_balance_end - self.config_id.his_float_amount, 0.0)

    def his_pending_transfers(self):
        self.ensure_one()
        self.config_id._his_check_cashier()
        transfers = (
            self.env["his.cash.transfer"]
            .sudo()
            .search([("state", "=", "sent"), ("to_journal_id", "=", self.cash_journal_id.id)])
        )
        return [{"id": t.id, "name": t.name, "amount_sent": t.amount_sent} for t in transfers]

    def his_receive_transfer(self, transfer_id, amount, employee_id=False):
        self.ensure_one()
        employee = self._his_till_employee(employee_id)
        transfer = self.env["his.cash.transfer"].sudo().browse(transfer_id)
        if transfer.to_journal_id != self.cash_journal_id:
            raise UserError(_("This transfer is not for this till."))
        transfer.sudo(False)._his_check_receive(amount)
        transfer.sudo()._his_receive(amount, self.env.uid, employee)
