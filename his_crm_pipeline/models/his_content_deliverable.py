# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Les livrables d'une demande de contenu, un par ligne.

Ils etaient trois triplets de champs sur crm.lead — besoin_/statut_/assignee_
fois copy, design, video. Cette forme repondait a « ce livrable est-il pret ? »
et a rien d'autre : on ne pouvait ni grouper la charge par personne, ni dater un
livrable, ni mesurer un retard, parce qu'une colonne ne se groupe pas avec ses
voisines. La question « qui a combien de travail cette semaine » n'avait pas de
reponse, et c'est la premiere que pose un directeur.

Une ligne par livrable rend tout cela natif : `_read_group` sur assignee_id,
`date_fin - date_debut` pour le delai, `date_echeance` pour le retard. C'est
aussi la forme qu'une table de faits doit avoir pour l'outil de BI qui viendra.

Le TYPE est une table de configuration, pas une enumeration figee. Meme choix
que his.document.type dans his_admission, et pour la meme raison : ajouter
« podcast » ou « affiche » est une decision de l'equipe Contenu, pas une
livraison de code.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

STATUT_LIVRABLE = [
    ('a_faire', "A faire"),
    ('en_cours', "En cours"),
    ('revision_interne', "Revision interne"),
    ('approuve', "Approuve"),
    ('rejete', "Rejete"),
]


class HisContentDeliverableType(models.Model):
    _name = 'his.content.deliverable.type'
    _description = "Type de livrable de contenu"
    _order = 'sequence, name'

    name = fields.Char(string="Type", required=True, translate=True)
    code = fields.Char(
        string="Code", required=True,
        help="Identifiant technique stable. Le libelle peut changer, pas lui.",
    )
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Actif", default=True)

    _code_unique = models.Constraint(
        'unique(code)', "Un autre type de livrable porte deja ce code.",
    )


class HisContentDeliverable(models.Model):
    _name = 'his.content.deliverable'
    _description = "Livrable de contenu"
    _order = 'lead_id, sequence, id'

    lead_id = fields.Many2one(
        'crm.lead', string="Demande", required=True, index=True,
        ondelete='cascade',
    )
    type_id = fields.Many2one(
        'his.content.deliverable.type', string="Type", required=True,
        ondelete='restrict',
    )
    sequence = fields.Integer(related='type_id.sequence', store=True)

    statut = fields.Selection(
        STATUT_LIVRABLE, string="Statut", default='a_faire', required=True,
    )
    assignee_id = fields.Many2one('res.users', string="Assigne a", index=True)

    # --- Dates ---------------------------------------------------------------
    # Posees par le passage de statut, pas saisies. Ce sont elles qui permettent
    # de mesurer un delai et un retard — exactement ce que les anciens champs ne
    # savaient pas dire.

    date_assignation = fields.Datetime(string="Assigne le", readonly=True, copy=False)
    date_debut = fields.Datetime(string="Demarre le", readonly=True, copy=False)
    date_fin = fields.Datetime(string="Termine le", readonly=True, copy=False)

    date_echeance = fields.Date(
        related='lead_id.date_deadline', store=True, string="Echeance",
    )
    en_retard = fields.Boolean(
        string="En retard", compute='_compute_en_retard', store=True,
    )

    # --- Axes d'analyse ------------------------------------------------------
    # Recopies de la demande et STOCKES : un tableau de bord groupe par marque
    # sans jointure, et l'outil de BI lira la table de faits telle quelle.

    marque = fields.Selection(related='lead_id.marque', store=True, string="Marque")
    team_id = fields.Many2one(related='lead_id.team_id', store=True, string="Equipe")
    stage_id = fields.Many2one(related='lead_id.stage_id', store=True, string="Etape")
    demandeur_id = fields.Many2one(
        related='lead_id.demandeur_id', store=True, string="Demandeur",
    )

    _type_unique_par_demande = models.Constraint(
        'unique(lead_id, type_id)',
        "Cette demande porte deja un livrable de ce type.",
    )

    @api.depends('date_echeance', 'date_fin', 'statut')
    def _compute_en_retard(self):
        aujourdhui = fields.Date.context_today(self)
        for livrable in self:
            if not livrable.date_echeance or livrable.statut == 'approuve':
                livrable.en_retard = False
            else:
                livrable.en_retard = livrable.date_echeance < aujourdhui

    @api.depends('lead_id.name', 'type_id.name')
    def _compute_display_name(self):
        for livrable in self:
            livrable.display_name = "%s / %s" % (
                livrable.lead_id.name or '', livrable.type_id.name or '',
            )

    # --- Horodatage ----------------------------------------------------------

    def _horodater(self, vals):
        """Traduit un changement de statut ou d'assignation en dates.

        En write() et non en compute : une date d'evenement doit rester ce qui
        s'est passe. Un champ calcule se recalculerait a la moindre
        modification voisine et reecrirait l'histoire.
        """
        maintenant = fields.Datetime.now()
        pose = {}
        if vals.get('assignee_id') and not self.date_assignation:
            pose['date_assignation'] = maintenant
        statut = vals.get('statut')
        if statut and statut != 'a_faire' and not self.date_debut:
            pose['date_debut'] = maintenant
        if statut == 'approuve':
            pose['date_fin'] = maintenant
        elif statut and statut != 'approuve' and self.date_fin:
            # Un livrable renvoye en revision n'est plus termine.
            pose['date_fin'] = False
        return pose

    # --- Garde-fou de capacite ----------------------------------------------

    def write(self, vals):
        """Un livrable n'avance que par la main de son assigne.

        La regle vivait dans crm.lead.write, ou elle devait balayer neuf champs
        pour deviner de quel livrable on parlait. Ici l'enregistrement EST le
        livrable : la regle tient en une comparaison.

        Elle n'est pas exprimable en ir.rule : la lecture doit rester large —
        le plan de charge de l'equipe est visible de tous — et seule l'ECRITURE
        du statut est reservee. Une regle porterait aussi sur la lecture.
        """
        if not self.env.su:
            self._verifier_capacites(vals)
        for livrable in self:
            pose = livrable._horodater(vals)
            if pose:
                super(HisContentDeliverable, livrable).write({**vals, **pose})
            else:
                super(HisContentDeliverable, livrable).write(vals)
        return True

    def _verifier_capacites(self, vals):
        user = self.env.user
        if user.has_group('his_crm_pipeline.group_contenu_priorisation'):
            return
        if 'assignee_id' in vals:
            raise AccessError(_(
                "Affecter un livrable demande le role « Priorisation »."
            ))
        if 'statut' in vals:
            for livrable in self:
                if livrable.assignee_id != user:
                    raise AccessError(_(
                        "Le livrable « %(livrable)s » n'est pas le votre. Seule "
                        "la personne a qui il est assigne fait avancer son "
                        "statut, ou le role « Priorisation » qui arbitre.",
                        livrable=livrable.display_name,
                    ))
