# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HisEngagement(models.Model):
    """Le parcours d'une personne dans l'institution, distinct de son identite.

    Une personne est un humain : une fiche, un matricule, a vie. Un engagement
    est une relation datee avec l'institution — une candidature, une
    inscription. Les deux ne se confondent pas : un candidat recale qui
    repostule deux ans plus tard garde sa fiche et son matricule, et porte deux
    engagements.

    Ce modele porte l'etat, pas les transitions. Passer a `candidat_soumis` et
    au-dela appartient a Finance/Admission (confirmation du paiement des frais
    d'inscription) : aucun code de ce depot ne declenche ces transitions
    aujourd'hui. Le CRM, lui, cree l'engagement a `prospect` et s'arrete la.
    """
    _name = 'his.engagement'
    _description = "Engagement d'une personne aupres de l'institution"
    _inherit = ['mail.thread']
    _order = 'date_debut desc, id desc'
    _rec_name = 'person_id'

    person_id = fields.Many2one(
        'his.person', string="Personne", required=True, index=True,
        ondelete='cascade', tracking=True,
    )
    # ponytail: aucune contrainte « un seul engagement actif par personne ».
    # Tant qu'un seul parcours existe (candidature), le doublon se voit a l'oeil
    # nu. A trancher quand la reinscription arrivera : c'est la qu'il faudra
    # decider si deux engagements peuvent etre ouverts en meme temps.
    etat = fields.Selection(
        selection=[
            ('prospect', "Prospect"),
            ('candidat_soumis', "Candidature soumise"),
            ('inscrit', "Inscrit"),
            ('abandonne', "Abandonne"),
        ],
        string="Etat", required=True, default='prospect', tracking=True,
    )
    date_debut = fields.Date(
        string="Date de debut", required=True, default=fields.Date.context_today,
    )
    notes = fields.Text(string="Notes")
