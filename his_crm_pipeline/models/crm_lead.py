# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Delai de premier contact. Au-dela, le responsable d'equipe est relance.
SLA_PREMIER_CONTACT_HEURES = 4

STATUT_LIVRABLE = [
    ('a_faire', "A faire"),
    ('en_cours', "En cours"),
    ('revision_interne', "Revision interne"),
    ('approuve', "Approuve"),
    ('rejete', "Rejete"),
]

# (besoin, statut, assigne, libelle) — une seule source pour la contrainte, la
# vue et les messages d'erreur. Ajouter un type de livrable (podcast, affiche)
# se fait ici plus trois champs, sans toucher a la logique.
LIVRABLES = [
    ('besoin_copy', 'statut_copy', 'assignee_copy', "Copywriting"),
    ('besoin_design', 'statut_design', 'assignee_design', "Design"),
    ('besoin_video', 'statut_video', 'assignee_video', "Video"),
]


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # --- Parcours candidat (equipe Ventes / Admissions) ---------------------

    # Deux scores, pas un. Le Playbook Enrolment en documente bien deux, poses
    # par deux equipes a deux moments : le Marketing score le profil au moment
    # de la capture, les Ventes evaluent l'opportunite APRES avoir parle au
    # candidat. Les confondre reviendrait a ecraser le tri de la file
    # d'attente avec un jugement qui n'existe pas encore au moment du tri.
    score_academique = fields.Integer(
        string="Score academique",
        help="Score pose par le Marketing a la capture : profil academique et "
             "motivation. C'est lui qui ordonne la file des leads a affecter.",
    )
    motivation_notes = fields.Text(
        string="Notes de motivation",
        help="Texte libre recueilli au moment du scoring.",
    )
    score_opportunite = fields.Integer(
        string="Score d'opportunite",
        help="Evaluation des Ventes apres contact direct : engagement, "
             "adequation au programme, potentiel de conversion. Distinct du "
             "score academique, qui lui precede tout echange.",
    )
    visite_campus_effectuee = fields.Boolean(string="Visite du campus effectuee")
    date_visite_campus = fields.Datetime(string="Date de visite du campus")

    # --- Production Contenu (equipe Production Contenu) ---------------------

    departement_demandeur = fields.Selection(
        selection=[
            ('sales', "Ventes / Admissions"),
            ('hr', "Ressources humaines"),
            ('pedagogie', "Pedagogie"),
            ('marketing', "Marketing"),
        ],
        string="Departement demandeur",
    )

    # Un booleen « besoin » et un statut par type de livrable, plutot que des
    # sous-etapes : une meme demande peut exiger texte, design et video en
    # parallele, et chacun avance a son rythme. Une etape unique ne peut pas
    # representer « texte approuve, design en revision, video pas commencee ».
    besoin_copy = fields.Boolean(string="Besoin copywriting")
    besoin_design = fields.Boolean(string="Besoin design")
    besoin_video = fields.Boolean(string="Besoin video")

    statut_copy = fields.Selection(STATUT_LIVRABLE, string="Statut copy", default='a_faire')
    statut_design = fields.Selection(STATUT_LIVRABLE, string="Statut design", default='a_faire')
    statut_video = fields.Selection(STATUT_LIVRABLE, string="Statut video", default='a_faire')

    assignee_copy = fields.Many2one('res.users', string="Copywriter")
    assignee_design = fields.Many2one('res.users', string="Designer")
    assignee_video = fields.Many2one('res.users', string="Video")

    marque = fields.Selection(
        selection=[
            ('his', "HIS"),
            ('htc', "HTC"),
            ('ira', "IRA"),
        ],
        string="Marque",
    )

    # --- La file d'attente d'affectation -------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Un lead qui naît en « Nouveau (score) » n'a pas de proprietaire.

        crm.lead.user_id porte `default=lambda self: self.env.user` : Odoo
        affecte tout lead a son createur. Le Marketing capture, donc chaque
        lead naissait affecte au Marketing — et la file « Leads a affecter »,
        qui filtre sur les leads SANS commercial, restait vide en permanence.
        Le geste d'arbitrage du responsable n'existait tout simplement pas.

        La regle vaut a la CREATION seulement, et elle dit exactement ce que
        les deux premieres etapes signifient deja : « Nouveau (score) » est la
        file d'attente, « Pris en charge » est la prise en charge. Qui veut
        creer un lead deja affecte le cree directement en « Pris en charge » —
        c'est le sens de l'etape, pas un contournement.

        Poser la regle ici et non dans le contexte de l'action la rend vraie
        pour toutes les entrees : l'interface, l'import, et demain le
        formulaire de candidature qui arrivera par n8n.
        """
        leads = super().create(vals_list)
        etape = self.env.ref(
            'his_crm_pipeline.stage_vente_nouveau', raise_if_not_found=False,
        )
        if etape:
            # Apres super() et non sur les vals : crm.lead.stage_id est un champ
            # calcule stocke. Un lead cree depuis un formulaire n'apporte aucun
            # stage_id dans ses vals, Odoo le deduit de l'equipe apres coup —
            # filtrer les vals aurait laisse passer le cas le plus courant.
            leads.filtered(lambda l: l.stage_id == etape and l.user_id).user_id = False
        return leads

    # --- Verrou d'approbation ----------------------------------------------

    @api.constrains(
        'stage_id',
        'besoin_copy', 'besoin_design', 'besoin_video',
        'statut_copy', 'statut_design', 'statut_video',
    )
    def _check_livrables_approuves(self):
        """Interdit l'etape Approbation tant qu'un livrable demande n'est pas approuve.

        Contrainte serveur et non regle de vue : le tableur qu'on remplace
        portait deja une colonne « Approval Status », restee vide dans presque
        toutes les lignes reelles parce que rien ne la reclamait. Une regle
        posee dans la vue se contourne par le kanban, l'import ou le glisser-
        deposer, exactement comme la colonne se contournait par la touche
        Entree. Meme raisonnement que la gouvernance de his_stock_mdm.
        """
        approbation = self.env.ref(
            'his_crm_pipeline.stage_contenu_approbation', raise_if_not_found=False,
        )
        if not approbation:
            return
        for lead in self:
            if lead.stage_id != approbation:
                continue
            manquants = [
                libelle for besoin, statut, _assignee, libelle in LIVRABLES
                if lead[besoin] and lead[statut] != 'approuve'
            ]
            if manquants:
                raise ValidationError(_(
                    "« %(lead)s » ne peut pas passer en Approbation : "
                    "le ou les livrables suivants ne sont pas approuves — "
                    "%(manquants)s.\n\n"
                    "Chaque livrable demande doit porter le statut « Approuve » "
                    "avant la validation finale.",
                    lead=lead.display_name,
                    manquants=", ".join(manquants),
                ))

    # --- Relance SLA premier contact ----------------------------------------

    @api.model
    def _cron_relance_sla_premier_contact(self):
        """Relance le responsable d'equipe quand un lead pris en charge dort > 4 h.

        Le destinataire est le responsable, jamais le conseiller assigne : le
        conseiller sait deja qu'il a le lead, c'est precisement le probleme. La
        relance sert a rendre le retard visible a qui peut le corriger.

        Aucune avance d'etape, aucune reaffectation : ce cron ne fait que poser
        une activite.
        """
        stage = self.env.ref(
            'his_crm_pipeline.stage_vente_pris_en_charge', raise_if_not_found=False,
        )
        if not stage:
            return
        limite = fields.Datetime.now() - timedelta(hours=SLA_PREMIER_CONTACT_HEURES)
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        leads = self.search([
            ('stage_id', '=', stage.id),
            ('date_last_stage_update', '<', limite),
            ('active', '=', True),
        ])
        for lead in leads:
            responsable = lead.team_id.user_id
            # Sans responsable d'equipe, il n'y a personne a prevenir. Poser
            # l'activite sur le conseiller serait pire que rien : le retard
            # deviendrait invisible tout en paraissant traite.
            if not responsable:
                continue
            # Une seule relance par retard. Sans ce filtre, le cron horaire
            # empilerait une activite par heure sur le meme lead et le
            # responsable cesserait de les lire.
            deja = self.env['mail.activity'].search_count([
                ('res_model', '=', 'crm.lead'),
                ('res_id', '=', lead.id),
                ('activity_type_id', '=', activity_type.id),
                ('user_id', '=', responsable.id),
                ('summary', '=', "Relance SLA - premier contact en retard (>4h)"),
            ])
            if deja:
                continue
            lead.activity_schedule(
                'mail.mail_activity_data_todo',
                summary="Relance SLA - premier contact en retard (>4h)",
                note=_(
                    "Ce lead est en « Pris en charge » depuis plus de %(heures)s heures "
                    "sans premier contact. Conseiller assigne : %(conseiller)s.",
                    heures=SLA_PREMIER_CONTACT_HEURES,
                    conseiller=lead.user_id.display_name or _("aucun"),
                ),
                user_id=responsable.id,
            )
