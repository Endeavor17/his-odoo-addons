from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HisMealCard(models.Model):
    """The person's physical badge. It carries an identifier and nothing else.

    Credits belong to the person, not to the card, which is what makes a lost
    card replaceable without losing a balance.

    Since his_person_core handed the badge over to this model, one row here is
    the group's single physical card: attendance, door access and meals all
    read the same number. `his.person.numero_carte` and the native
    `hr.employee.barcode` are both fed from the active row.

    # ponytail: the model is still called his.meal.card while it is now the
    # group's card, not the restaurant's. Renaming a model means migrating
    # ir_model_data, every XML id and every FK - not worth it today. Rename to
    # his.card if a second module ever has to depend on it.
    """

    _name = 'his.meal.card'
    _description = "Meal Card"
    _rec_name = 'code'
    _order = 'create_date desc'

    code = fields.Char(
        required=True, copy=False, index=True,
        help="For an RFID card this is the 10-digit UID the reader sends, e.g. "
             "0007197786 — tap the card into this field rather than typing it, so "
             "the leading zeros cannot be lost. Printed cards use a HIS- code "
             "instead; both are matched by their own barcode rule.",
    )
    partner_id = fields.Many2one(
        'res.partner', string="Person", required=True, index=True, ondelete='cascade',
    )
    state = fields.Selection(
        [
            ('active', "Active"),
            ('blocked', "Blocked"),
            ('lost', "Lost"),
            ('replaced', "Replaced"),
        ],
        default='active', required=True, index=True,
    )
    # Not readonly: `action_replace` seeds it through the context, and a readonly
    # field is not sent back by the web client.
    replaced_card_id = fields.Many2one(
        'his.meal.card', string="Replaces", ondelete='set null',
    )
    credits_remaining = fields.Integer(
        related='partner_id.meal_credits_remaining', string="Credits", readonly=True,
    )

    _code_unique = models.Constraint('UNIQUE(code)', "This card code is already in use.")

    @api.constrains('partner_id')
    def _check_meal_holder_is_registered(self):
        """No wallet without an identity.

        The Meal Officer deliberately holds no write access to his.person, but
        core Odoo lets any internal user create an ordinary contact. Without
        this, issuing a card to such a contact would create a card holder
        outside the group referential - and a duplicate the day that human is
        properly registered. Enforced here rather than by handing out rights:
        the officer issues cards, the referential issues identities.
        """
        for card in self:
            if not card.partner_id.sudo().his_person_ids:
                raise ValidationError(_(
                    "%s has no person record, so no card can be issued.\n\n"
                    "A meal card belongs to a registered person. Ask for the person "
                    "to be created in the Personnes referential first — by HR for an "
                    "employee, or through the student import.",
                    card.partner_id.display_name,
                ))

    @api.constrains('state', 'partner_id')
    def _check_single_active_card(self):
        for card in self.filtered(lambda c: c.state == 'active'):
            others = self.search_count([
                ('partner_id', '=', card.partner_id.id),
                ('state', '=', 'active'),
                ('id', '!=', card.id),
            ])
            if others:
                raise ValidationError(_(
                    "%s already holds an active card. Block, lose or replace it first.",
                    card.partner_id.display_name,
                ))

    def _sync_partner_barcode(self):
        """Mirror the active card's code onto the person's contact.

        This is the entire bridge to POS: `res.partner.barcode` is what Odoo's
        own 'client' barcode rule looks up, so scanning a card sets the customer
        on the order with no custom JavaScript anywhere.

        his_person_core's README states this field is "deliberately not used"
        because it would be "un champ que personne ne lit". That is not what
        core 19.0 does - it reads it in three places, and the third is the one
        every scan in this module goes through:

          point_of_sale/models/res_partner.py:73
              _load_pos_data_fields() includes 'barcode' -> the till loads it
          .../static/src/app/screens/partner_list/partner_list.js:160
              _getSearchFields() returns 'barcode' for numeric AND text queries
              -> typing a badge in the customer list finds the person
          .../static/src/app/screens/product_screen/product_screen.js:285
              _getPartnerByBarcode() -> models["res.partner"].getBy("barcode"),
              then searchRead [('barcode','=',code)] -> a tapped badge resolves

        An RFID reader that types digits and Enter IS a barcode scanner as far
        as Odoo is concerned; that is the whole premise of data/barcode_rule.xml
        and its tests. Feeding this field is what makes both scanning and typed
        search work with no POS extension to maintain. his_person_core still
        never writes it - this is the wallet module's own call.
        """
        for card in self:
            partner = card.partner_id
            if card.state == 'active':
                partner.barcode = card.code
            elif partner.barcode == card.code:
                # Only clear it if this card still owns the barcode; a newer
                # active card may already have claimed it.
                partner.barcode = False

    @api.model_create_multi
    def create(self, vals_list):
        cards = super().create(vals_list)
        cards._sync_partner_barcode()
        return cards

    def write(self, vals):
        # The old code must be cleared off the partner before the new one lands,
        # otherwise a renamed card leaves its previous code scannable.
        stale = self.filtered(lambda c: c.state == 'active' and 'code' in vals)
        res = super().write(vals)
        if {'code', 'state', 'partner_id'} & vals.keys():
            for card in stale:
                card.partner_id.barcode = False
            self._sync_partner_barcode()
        return res

    def unlink(self):
        # Without this the person stays scannable by a card that no longer
        # exists: create() and write() mirror the code onto res.partner.barcode,
        # and nothing was taking it back off. Same "only if this card still owns
        # it" guard as _sync_partner_barcode, so deleting a retired card cannot
        # clear a barcode a newer active card has already claimed.
        for card in self:
            if card.partner_id.barcode == card.code:
                card.partner_id.barcode = False
        return super().unlink()

    @api.model
    def _next_code(self):
        return self.env['ir.sequence'].next_by_code('his.meal.card')

    def action_print_card(self):
        return self.env.ref('his_meal_management.action_report_meal_card').report_action(self)

    def action_block(self):
        self.write({'state': 'blocked'})

    def action_activate(self):
        self.write({'state': 'active'})

    def action_replace(self):
        """Retire this card and open a blank one for the new card to be tapped.

        An RFID card's code is its manufacturer UID, so it cannot be invented -
        the replacement has to be read off the physical card. This deliberately
        does not pre-fill a code: `code` is required, so the form cannot be saved
        until a real card has been tapped into it. The balance is untouched
        either way, because credits live on the person.
        """
        self.ensure_one()
        # Retire first: the single-active-card constraint would refuse the new
        # one otherwise.
        if self.state == 'active':
            self.state = 'replaced'
        return {
            'type': 'ir.actions.act_window',
            'name': _("Tap the new card"),
            'res_model': 'his.meal.card',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_replaced_card_id': self.id,
            },
        }
