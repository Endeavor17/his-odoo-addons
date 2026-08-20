from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HisPerson(models.Model):
    """Academic attributes, added to the group's identity record.

    These three fields were on res.partner while this module carried its own
    Person. They belong with the rest of the identity, not with the wallet, so
    they follow it onto `his.person` rather than staying behind on every
    contact in the database.

    They are added from here and not from his_person_core because that module
    is the group's socle: it holds what every person has. A rank and a faculty
    are academic facts, and today it is this module that needs them. If Uniflow
    or the future Scolarité module ends up needing them too, that is the moment
    to propose moving them down into the socle - not before.

    Nothing about the meal wallet is defined here. It lives on res.partner and
    reaches this model for free through delegation, so a person form can show
    `meal_credits_remaining` with no field of its own.

    The one field this module takes over is `numero_carte` - see below.
    """

    _inherit = 'his.person'

    # --- The badge, taken over from his_person_core -------------------------
    #
    # his_person_core declares numero_carte as a plain stored Char and says so
    # in its own README:
    #
    #   « Un seul champ, pas de modele his.card. Ce qui n'est pas couvert :
    #     perte, reedition, desactivation. [...] A reprendre dans un modele
    #     dedie (person_id, numero, etat, dates de validite) AVANT que le
    #     portefeuille repas ne stocke de l'argent. »
    #
    # his.meal.card is that model, and the wallet already stores money. So this
    # is the handover, not a fork: the field keeps its name, its label, its
    # unique constraint and both of its entry points (the person form and, via
    # hr.employee.barcode's stored related, the employee form). What changes is
    # where the value comes FROM.
    #
    # compute + inverse rather than two fields kept in step: his_hr_base's own
    # comment puts it best - « deux champs qu'on recopie l'un dans l'autre
    # finissent toujours par diverger », and here diverging would mean a badge
    # the till accepts and the attendance reader refuses. There is exactly one
    # place a badge number lives now: an active his.meal.card row.
    numero_carte = fields.Char(
        compute='_compute_numero_carte',
        inverse='_inverse_numero_carte',
        store=True,
        readonly=False,
    )

    @api.depends('partner_id.meal_card_ids.code', 'partner_id.meal_card_ids.state')
    def _compute_numero_carte(self):
        """The badge is whatever the person's active card says it is."""
        for person in self:
            active = person.partner_id.meal_card_ids.filtered(
                lambda card: card.state == 'active'
            )[:1]
            person.numero_carte = active.code or False

    def _inverse_numero_carte(self):
        """Issuing a badge issues a card, so the history survives.

        This is the half his single field could not do. Overwriting a Char lost
        the previous number; here the old card is retired and kept, which is
        what lets anyone answer "which card was valid when that meal was
        served" - the question his README says has to be answerable before the
        wallet holds money.
        """
        for person in self:
            partner = person.partner_id
            active = partner.meal_card_ids.filtered(lambda card: card.state == 'active')
            if active and active[0].code == person.numero_carte:
                continue

            # Retire first: _check_single_active_card refuses two at once, and
            # 'replaced' is only honest when something replaces it.
            if active:
                active.state = 'replaced' if person.numero_carte else 'blocked'

            if person.numero_carte:
                self.env['his.meal.card'].create({
                    'partner_id': partner.id,
                    'code': person.numero_carte,
                    'replaced_card_id': active[:1].id or False,
                })

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
    faculty_ids = fields.Many2many(
        'his.faculty', 'his_faculty_person_rel', 'person_id', 'faculty_id',
        string="Facultés",
        help="A person may legitimately belong to more than one faculty.",
    )

    def action_open_meal_transactions(self):
        """Delegation carries fields across, not methods.

        `meal_credits_remaining` reads straight off a person because it is a
        field on the delegated partner; the button next to it would not resolve
        without this, so the person form forwards to the partner that owns the
        wallet.
        """
        self.ensure_one()
        return self.partner_id.action_open_meal_transactions()

    @api.constrains('rang_academique', 'type_personne')
    def _check_rang_academique(self):
        for person in self:
            if person.rang_academique and person.type_personne != 'enseignant':
                raise ValidationError(_(
                    "An academic rank only applies to a teacher. %s is recorded as %s.",
                    person.display_name,
                    dict(self._fields['type_personne'].selection).get(person.type_personne)
                    or _("nothing in particular"),
                ))
