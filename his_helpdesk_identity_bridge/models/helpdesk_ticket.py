# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, tools


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    # Le lien est deterministe : une his.person delegue a UN res.partner.
    # Calcule depuis le contact, il ne peut pas se desynchroniser ; l'inverse
    # pose le contact quand l'agent choisit la personne.
    his_person_id = fields.Many2one(
        "his.person",
        string="Personne",
        compute="_compute_his_person_id",
        inverse="_inverse_his_person_id",
        store=True,
        readonly=False,
        index=True,
    )

    @api.depends("partner_id")
    def _compute_his_person_id(self):
        for ticket in self:
            ticket.his_person_id = ticket.partner_id.his_person_ids[:1]

    def _inverse_his_person_id(self):
        for ticket in self:
            # Vider la personne d'un ticket dont le contact est une personne
            # vide aussi le contact : sinon le calcul la remettrait.
            if ticket.his_person_id or ticket.partner_id.his_person_ids:
                ticket.partner_id = ticket.his_person_id.partner_id

    @api.onchange("his_person_id")
    def _onchange_his_person_id(self):
        # L'inverse n'agit qu'a l'enregistrement : remplir le contact tout de
        # suite dans le formulaire (et, en cascade, le nom et l'email du ticket).
        if self.his_person_id or self.partner_id.his_person_ids:
            self.partner_id = self.his_person_id.partner_id

    # En-tete du ticket : qui est-ce, sans ouvrir sa fiche.
    his_matricule = fields.Char(related="his_person_id.matricule_affiche", string="Matricule")
    # tracking=False : un related herite du suivi de sa source.
    his_type_personne = fields.Selection(
        related="his_person_id.type_personne",
        string="Type de personne",
        tracking=False,
    )
    # L'etat et non l'engagement : un his.engagement s'affiche sous le nom de
    # sa personne, ce qui ne dit rien a l'agent.
    his_engagement_etat = fields.Selection(
        selection=lambda self: self.env["his.engagement"]._fields["etat"].selection,
        string="Engagement en cours",
        compute="_compute_his_engagement_etat",
    )

    @api.depends("his_person_id.engagement_ids.etat")
    def _compute_his_engagement_etat(self):
        for ticket in self:
            # _order de his.engagement : date_debut desc, id desc.
            ticket.his_engagement_etat = ticket.his_person_id.engagement_ids[:1].etat

    def _track_template(self, changes):
        # Le courriel de cloture d'OCA passe par le compositeur en mode
        # mass_mail, qui envoie dans la requete (force_send) : l'agent
        # attendrait le SMTP. En file, et le cron mail reveille : il ne tourne
        # que toutes les heures.
        res = super()._track_template(changes)
        if "stage_id" in res:
            template, options = res["stage_id"]
            res["stage_id"] = (template, {**options, "force_send": False})
            self.env.ref("mail.ir_cron_mail_scheduler_action")._trigger()
        return res

    @api.model
    def message_new(self, msg, custom_values=None):
        # Un courriel recu (support@) : canal Email, et la personne quand
        # l'expediteur n'est pas deja un contact connu.
        values = dict(custom_values or {})
        values.setdefault("channel_id", self.env.ref("helpdesk_mgmt.helpdesk_ticket_channel_email").id)
        if not msg.get("author_id") and "partner_id" not in values:
            person = self._his_person_from_email(msg.get("email_from") or msg.get("from"))
            if person:
                values["partner_id"] = person.partner_id.id
        return super().message_new(msg, custom_values=values)

    @api.model
    def _his_person_from_email(self, email):
        """La personne dont l'email PERSONNEL est exactement celui-ci, ou rien.

        Deterministe : une seule fiche, sinon aucune. Jamais de score ici (le
        rapprochement probabiliste demande une confirmation humaine), jamais de
        creation. Le contact connu par son email principal est deja trouve par
        la passerelle mail elle-meme (author_id).
        """
        email = tools.email_normalize(email)
        if not email:
            return self.env["his.person"]
        # sudo : la releve tourne sous l'utilisateur du cron, pas sous un agent.
        persons = self.env["his.person"].sudo().search([("email_personnel", "=ilike", email)], limit=2)
        return persons if len(persons) == 1 else self.env["his.person"]

    def _message_track_post_template(self, changes):
        # Le compositeur transforme email_cc en contacts (find_or_create) : la
        # copie a l'adresse d'ecriture creerait un second contact pour une
        # personne du referentiel. Adresse brute, aucun contact cree.
        return super(
            HelpdeskTicket, self.with_context(mail_composer_force_partners=False)
        )._message_track_post_template(changes)
