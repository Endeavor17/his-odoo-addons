# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


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
    his_type_personne = fields.Selection(related="his_person_id.type_personne", string="Type de personne")
    his_engagement_id = fields.Many2one(
        "his.engagement",
        string="Engagement en cours",
        compute="_compute_his_engagement_id",
    )

    @api.depends("his_person_id")
    def _compute_his_engagement_id(self):
        for ticket in self:
            # _order de his.engagement : date_debut desc, id desc.
            ticket.his_engagement_id = ticket.his_person_id.engagement_ids[:1]
