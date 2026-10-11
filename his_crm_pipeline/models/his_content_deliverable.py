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
from odoo.exceptions import AccessError, ValidationError

STATUT_LIVRABLE = [
    ("a_faire", "To Do"),
    ("en_cours", "In Progress"),
    ("revision_interne", "Internal Review"),
    ("approuve", "Approved"),
    ("rejete", "Rejected"),
]


class HisContentDeliverableType(models.Model):
    _name = "his.content.deliverable.type"
    _description = "Content Deliverable Type"
    _order = "sequence, name"

    name = fields.Char(string="Type", required=True, translate=True)
    code = fields.Char(
        string="Code",
        required=True,
        help="Stable technical identifier. The label may change, this does not.",
    )
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)

    _code_unique = models.Constraint(
        "unique(code)",
        "Another deliverable type already uses this code.",
    )


class HisContentDeliverable(models.Model):
    _name = "his.content.deliverable"
    _description = "Content Deliverable"
    _order = "lead_id, sequence, id"

    lead_id = fields.Many2one(
        "crm.lead",
        string="Request",
        required=True,
        index=True,
        ondelete="cascade",
    )
    type_id = fields.Many2one(
        "his.content.deliverable.type",
        string="Type",
        required=True,
        ondelete="restrict",
    )
    sequence = fields.Integer(related="type_id.sequence", store=True)

    statut = fields.Selection(
        STATUT_LIVRABLE,
        string="Status",
        default="a_faire",
        required=True,
    )
    # Le domaine ne propose que ceux qui font le travail : « Production »
    # implique « Demandeur », et « Priorisation »/« Approbation »/Direction
    # impliquent « Production ». Un simple demandeur en est donc exclu — il
    # commande du contenu, il n'en produit pas.
    assignee_id = fields.Many2one(
        "res.users",
        string="Assigned To",
        index=True,
        domain=lambda self: [("all_group_ids", "in", self._groupes_producteurs())],
    )

    # --- Dates ---------------------------------------------------------------
    # Posees par le passage de statut, pas saisies. Ce sont elles qui permettent
    # de mesurer un delai et un retard — exactement ce que les anciens champs ne
    # savaient pas dire.

    date_assignation = fields.Datetime(string="Assigned On", readonly=True, copy=False)
    date_debut = fields.Datetime(string="Started On", readonly=True, copy=False)
    date_fin = fields.Datetime(string="Finished On", readonly=True, copy=False)

    date_echeance = fields.Date(
        related="lead_id.date_deadline",
        store=True,
        string="Deadline",
    )
    en_retard = fields.Boolean(
        string="Late",
        compute="_compute_en_retard",
        store=True,
    )

    # --- Axes d'analyse ------------------------------------------------------
    # Recopies de la demande et STOCKES : un tableau de bord groupe par marque
    # sans jointure, et l'outil de BI lira la table de faits telle quelle.

    marque = fields.Selection(related="lead_id.marque", store=True, string="Brand")
    team_id = fields.Many2one(related="lead_id.team_id", store=True, string="Team")
    stage_id = fields.Many2one(related="lead_id.stage_id", store=True, string="Stage")
    demandeur_id = fields.Many2one(
        related="lead_id.demandeur_id",
        store=True,
        string="Requester",
    )

    _type_unique_par_demande = models.Constraint(
        "unique(lead_id, type_id)",
        "This request already carries a deliverable of this type.",
    )

    @api.model
    def _groupes_producteurs(self):
        """Les groupes dont les membres peuvent porter un livrable."""
        groupe = self.env.ref(
            "his_crm_pipeline.group_contenu_production",
            raise_if_not_found=False,
        )
        return groupe.ids if groupe else []

    @api.constrains("assignee_id")
    def _verifier_assignee_produit_du_contenu(self):
        """Le domaine du champ ne protege que l'ecran.

        Un import, un batch ou l'API assignaient sans lui — et le livrable
        atterrissait chez quelqu'un qui n'a meme pas l'application. Personne ne
        voyait jamais l'oubli : ni l'assigne, qui ne peut pas ouvrir la
        demande, ni la file « non assignes », qui le compte comme assigne.
        """
        for livrable in self:
            assigne = livrable.assignee_id
            if assigne and not assigne.has_group(
                "his_crm_pipeline.group_contenu_production",
            ):
                raise ValidationError(
                    _(
                        '%(nom)s cannot receive the deliverable "%(livrable)s": this account has '
                        "no Content Production role and would not even have access to the "
                        "request.",
                        nom=assigne.display_name,
                        livrable=livrable.display_name,
                    )
                )

    @api.depends("date_echeance", "date_fin", "statut")
    def _compute_en_retard(self):
        aujourdhui = fields.Date.context_today(self)
        for livrable in self:
            if not livrable.date_echeance or livrable.statut == "approuve":
                livrable.en_retard = False
            else:
                livrable.en_retard = livrable.date_echeance < aujourdhui

    @api.depends("lead_id.name", "type_id.name")
    def _compute_display_name(self):
        for livrable in self:
            livrable.display_name = "%s / %s" % (
                livrable.lead_id.name or "",
                livrable.type_id.name or "",
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
        if vals.get("assignee_id") and not self.date_assignation:
            pose["date_assignation"] = maintenant
        statut = vals.get("statut")
        if statut and statut != "a_faire" and not self.date_debut:
            pose["date_debut"] = maintenant
        if statut == "approuve":
            pose["date_fin"] = maintenant
        elif statut and statut != "approuve" and self.date_fin:
            # Un livrable renvoye en revision n'est plus termine.
            pose["date_fin"] = False
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
        if user.has_group("his_crm_pipeline.group_contenu_priorisation"):
            return
        if "assignee_id" in vals:
            raise AccessError(_('Assigning a deliverable requires the "Prioritisation" role.'))
        if "statut" in vals:
            for livrable in self:
                if livrable.assignee_id != user:
                    raise AccessError(
                        _(
                            'The deliverable "%(livrable)s" is not yours. Only the person it is '
                            'assigned to moves its status forward, or the "Prioritisation" role, '
                            "which arbitrates.",
                            livrable=livrable.display_name,
                        )
                    )
