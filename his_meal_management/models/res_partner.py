import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# HIS-AAAA-NNNNNN-C — data model section 2.
#
# The final character is the check digit. It is stored and its shape is checked,
# but its VALUE is deliberately not verified: section 2 states that the digit
# exists and never says how it is computed. Its own two examples,
# HIS-2026-000042-7 and HIS-2026-000125-7, carry the same digit for different
# sequence numbers, so no algorithm can be inferred from them either. Enforcing
# a guessed one would reject every real matricule HIS eventually issues, which is
# a far worse failure than accepting a typo in a field nothing depends on.
MATRICULE_RE = re.compile(r'^HIS-(\d{4})-(\d{6})-(\d)$')


class ResPartner(models.Model):
    """The Person of the HIS data model, section 2, plus the meal credit engine.

    Person is mapped onto res.partner rather than a new model so that a person
    is simultaneously an Odoo contact — POS customer, invoice recipient — without
    a second identity to keep in step. Fields the specification names are added
    explicitly; the two it already has (nom_latin, telephone) map onto Odoo's
    own `name` and `phone` instead of being duplicated.

    Credits hang off the person, never off the card. Everything that moves a
    balance goes through `_grant_meal_credits` or `_consume_meal_credit`.
    """

    _inherit = 'res.partner'

    # --- Person, data model section 2 -------------------------------------
    matricule_institutionnel = fields.Char(
        string="Matricule Institutionnel", copy=False, index=True,
        help="HIS-AAAA-NNNNNN-C, issued by HIS. Assigned once and never reused. "
             "Recorded here for later use — nothing in the meal system depends on "
             "it: a person is identified at the till by the card they tap.",
    )
    nom_arabe = fields.Char(
        string="Nom (arabe)",
        help="Both scripts always coexist in the HIS sources, never one without the other.",
    )
    type_personne = fields.Selection(
        [
            ('etudiant', "Étudiant"),
            ('enseignant', "Enseignant"),
            ('candidat', "Candidat"),
        ],
        string="Type de personne", index=True,
        help="Broad status. It does not replace tracking by engagement: the same "
             "person can be a candidate on one track and active on another.",
    )
    rang_academique = fields.Selection(
        [
            ('PROF', "Professeur"),
            ('MCA', "Maître de Conférences A"),
            ('MCB', "Maître de Conférences B"),
            ('MAA', "Maître Assistant A"),
            ('MAB', "Maître Assistant B"),
        ],
        string="Rang académique",
        help="Teachers only.",
    )
    specialite = fields.Char(
        string="Spécialité",
        help="Declarative free text, as it exists in the HIS referential.",
    )
    statut = fields.Selection(
        [
            ('actif', "Actif"),
            ('inactif', "Inactif"),
            ('archive', "Archivé"),
        ],
        string="Statut",
        help="Distinguishes a person still in activity from namesakes and old files. "
             "Setting it to Archivé also archives the contact in Odoo.",
    )
    email_institutionnel = fields.Char(
        string="Email institutionnel",
        help="prenom.nom@his.edu.dz. Students do not have one.",
    )
    email_personnel = fields.Char(
        string="Email personnel",
        help="The only address students have, until institutional accounts are provisioned.",
    )
    faculty_ids = fields.Many2many(
        'his.faculty', 'his_person_faculty_rel', 'partner_id', 'faculty_id',
        string="Facultés",
        help="A person may legitimately belong to more than one faculty.",
    )

    # --- Meal account ------------------------------------------------------
    meal_card_ids = fields.One2many('his.meal.card', 'partner_id', string="Meal Cards")
    meal_subscription_ids = fields.One2many('his.meal.subscription', 'partner_id')
    meal_transaction_ids = fields.One2many('his.meal.transaction', 'partner_id')
    # compute_sudo: a restaurant cashier is allowed to see a balance without
    # being granted read access to the subscription ledger itself.
    meal_credits_remaining = fields.Integer(
        string="Meal Credits", compute='_compute_meal_credits_remaining', compute_sudo=True,
    )
    meal_card_code = fields.Char(
        string="Card Code", compute='_compute_meal_card_code', compute_sudo=True,
        help="The code on the person's active card.",
    )
    meal_active_plan = fields.Char(
        string="Current Plan", compute='_compute_meal_credits_remaining', compute_sudo=True,
    )

    _matricule_unique = models.Constraint(
        'UNIQUE(matricule_institutionnel)',
        "This matricule institutionnel is already registered to someone else.",
    )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    @api.constrains('matricule_institutionnel')
    def _check_matricule(self):
        """Check the shape only. See MATRICULE_RE for why not the check digit."""
        for partner in self:
            matricule = partner.matricule_institutionnel
            if matricule and not MATRICULE_RE.match(matricule):
                raise ValidationError(_(
                    "“%(value)s” is not a valid matricule institutionnel.\n\n"
                    "The format is HIS-AAAA-NNNNNN-C: the fixed prefix HIS, a four-digit "
                    "year, a six-digit sequential number and one check digit — for "
                    "example HIS-2026-000042-7.",
                    value=matricule,
                ))

    # NOTE - deliberate deviation from section 2, which states that the Latin and
    # Arabic names coexist in every observed source, "jamais l'un sans l'autre".
    # The rule was enforced and then relaxed on request: the real lists carry
    # Latin names only, and a constraint that rejects every row of every import
    # is worse than a recorded gap. `nom_arabe` is kept and should be filled;
    # nothing forces it. Restore the constraint here if the sources ever carry
    # both.

    @api.constrains('rang_academique', 'type_personne')
    def _check_rang_academique(self):
        for partner in self:
            if partner.rang_academique and partner.type_personne != 'enseignant':
                raise ValidationError(_(
                    "An academic rank only applies to a teacher. %s is recorded as %s.",
                    partner.display_name,
                    dict(self._fields['type_personne'].selection).get(partner.type_personne)
                    or _("nothing in particular"),
                ))

    # This system does NOT issue matricules. HIS does, and they arrive by import
    # or by hand. An earlier version generated them from a sequence starting at
    # 900000 - a block invented here to avoid colliding with HIS - which put
    # fabricated identifiers on real people and matched nothing in section 2,
    # where NNNNNN is simply "un numéro séquentiel sur 6 chiffres". Do not bring
    # that back: two systems minting into one identifier space with only a local
    # unique constraint between them cannot end well.

    def _sync_identity_side_effects(self, vals):
        """Keep Odoo's own fields in step with the specification's fields."""
        for partner in self:
            # Odoo's `email` drives invoicing and the portal. Institutional
            # first, personal otherwise - students only ever have the latter.
            if not partner.email:
                fallback = partner.email_institutionnel or partner.email_personnel
                if fallback:
                    partner.email = fallback
            if 'statut' in vals:
                partner.active = partner.statut != 'archive'

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        for partner, vals in zip(partners, vals_list):
            partner._sync_identity_side_effects(vals)
        return partners

    def write(self, vals):
        if 'matricule_institutionnel' in vals:
            incoming = vals['matricule_institutionnel']
            for partner in self:
                current = partner.matricule_institutionnel
                if current and current != incoming:
                    raise UserError(_(
                        "%(name)s already holds the matricule %(current)s.\n\n"
                        "A matricule is assigned once and never reused, so it cannot be "
                        "changed to %(new)s. If it is genuinely wrong, archive this person "
                        "and register them again.",
                        name=partner.display_name, current=current, new=incoming or _("nothing"),
                    ))
        res = super().write(vals)
        if {'email_institutionnel', 'email_personnel', 'statut'} & vals.keys():
            self._sync_identity_side_effects(vals)
        return res

    # ------------------------------------------------------------------
    # Meal account
    # ------------------------------------------------------------------
    def _usable_subscriptions(self):
        """Subscriptions that may be eaten from today, soonest to expire first.

        Ordering by `date_end` means the credits about to be lost are spent
        before the ones that keep, which is what a person would choose.
        """
        self.ensure_one()
        today = fields.Date.context_today(self)
        return self.env['his.meal.subscription'].search(
            [
                ('partner_id', '=', self.id),
                ('state', '!=', 'cancelled'),
                ('credits_remaining', '>', 0),
                ('date_start', '<=', today),
                ('date_end', '>=', today),
            ],
            order='date_end asc, id asc',
        )

    @api.depends('meal_subscription_ids.credits_remaining', 'meal_subscription_ids.state')
    def _compute_meal_credits_remaining(self):
        for partner in self:
            subs = partner._usable_subscriptions() if partner.id else self.env['his.meal.subscription']
            partner.meal_credits_remaining = sum(subs.mapped('credits_remaining'))
            partner.meal_active_plan = subs[:1].product_id.display_name or ""

    @api.depends('meal_card_ids.state', 'meal_card_ids.code')
    def _compute_meal_card_code(self):
        for partner in self:
            active = partner.meal_card_ids.filtered(lambda c: c.state == 'active')
            partner.meal_card_code = active[:1].code or ""

    def _active_meal_card(self):
        self.ensure_one()
        return self.meal_card_ids.filtered(lambda c: c.state == 'active')[:1]

    def _add_meal_credits(self, credits, date_end, tx_type='purchase', product=None,
                          pos_order=None, note=None):
        """Put credits on the person as one new subscription, and log it."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        subscription = self.env['his.meal.subscription'].create({
            'partner_id': self.id,
            'product_id': product.id if product else False,
            'pos_order_id': pos_order.id if pos_order else False,
            'date_start': today,
            'date_end': date_end,
            'credits_total': credits,
        })
        self.invalidate_recordset(['meal_credits_remaining', 'meal_active_plan'])
        self._log_meal_transaction(
            tx_type=tx_type,
            credits=credits,
            subscription=subscription,
            product=product,
            pos_order=pos_order,
            note=note,
        )
        return subscription

    def _grant_meal_credits(self, product, pos_order=None, note=None):
        """Sell a plan: create the subscription and log the grant."""
        self.ensure_one()
        if product.meal_credits <= 0:
            raise UserError(_("%s is not a meal plan.", product.display_name))
        today = fields.Date.context_today(self)
        return self._add_meal_credits(
            credits=product.meal_credits,
            # -1 so a 7-day plan bought today is usable today through day 7,
            # not day 8.
            date_end=today + timedelta(days=product.meal_validity_days - 1),
            tx_type='purchase',
            product=product,
            pos_order=pos_order,
            note=note,
        )

    def _consume_meal_credit(self, qty=1, pos_order=None, tx_type='consume', note=None):
        """Eat `qty` meals. Raises if the person is short; never goes negative.

        Called from the POS order hook on the server, so the browser cannot
        decide whether a credit was really available.
        """
        self.ensure_one()
        if qty <= 0:
            return self.env['his.meal.transaction']

        # Lock this person's subscriptions for the length of the transaction.
        # Without it, two cashiers scanning the same card at the same instant
        # could both read "1 credit left" and both serve a meal.
        # Flush first so our own pending writes reach the rows we are locking,
        # then invalidate so the counters are re-read at their committed values.
        self.env['his.meal.subscription'].flush_model()
        self.env.cr.execute(
            "SELECT id FROM his_meal_subscription WHERE partner_id = %s FOR UPDATE",
            [self.id],
        )
        self.env['his.meal.subscription'].invalidate_model(
            ['credits_used', 'credits_remaining', 'state']
        )

        card = self._active_meal_card()
        transactions = self.env['his.meal.transaction']
        for _i in range(qty):
            subscription = self._usable_subscriptions()[:1]
            if not subscription:
                raise UserError(_(
                    "%(person)s has no meal credits available.",
                    person=self.display_name,
                ))
            subscription.credits_used += 1
            self.invalidate_recordset(['meal_credits_remaining', 'meal_active_plan'])
            transactions |= self._log_meal_transaction(
                tx_type=tx_type,
                credits=-1,
                subscription=subscription,
                product=pos_order.config_id.meal_product_id if pos_order else None,
                pos_order=pos_order,
                card=card,
                note=note,
            )
        return transactions

    def _log_meal_transaction(self, tx_type, credits, subscription=None, product=None,
                              pos_order=None, card=None, note=None):
        self.ensure_one()
        session = pos_order.session_id if pos_order else self.env['pos.session']
        return self.env['his.meal.transaction'].sudo().create({
            'partner_id': self.id,
            'card_id': (card or self._active_meal_card()).id or False,
            'subscription_id': subscription.id if subscription else False,
            'type': tx_type,
            'credits': credits,
            'balance_after': self.meal_credits_remaining,
            'product_id': product.id if product else False,
            'pos_order_id': pos_order.id if pos_order else False,
            'session_id': session.id or False,
            'config_id': session.config_id.id or False,
            'user_id': self.env.user.id,
            'note': note,
        })

    def get_meal_balance(self):
        """Read-only summary for the POS button. UX only — never authoritative.

        sudo because the cashier is shown a balance without being given read
        access to the subscriptions behind it.
        """
        self.ensure_one()
        subs = self.sudo()._usable_subscriptions()
        return {
            'partner_id': self.id,
            'name': self.display_name,
            'matricule': self.matricule_institutionnel or "",
            'credits': sum(subs.mapped('credits_remaining')),
            'plan': subs[:1].product_id.display_name or "",
            'expires': fields.Date.to_string(subs[:1].date_end) if subs else "",
        }

    def action_open_meal_transactions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Meal History"),
            'res_model': 'his.meal.transaction',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
