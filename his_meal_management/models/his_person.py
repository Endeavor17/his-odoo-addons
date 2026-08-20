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
    """

    _inherit = 'his.person'

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
