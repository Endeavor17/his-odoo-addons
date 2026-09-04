# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .his_document_type import BAC_FILIERE, TYPE_INSCRIPTION
from .his_specialite import CYCLE

LIBELLES_PAIEMENT = {
    'frais_inscription_payes': "Frais d'inscription",
    'frais_scolarite_payes': "Frais de scolarite",
    'droits_prog_qualifiant_payes': "Droits du programme qualifiant",
}

# Les deux droits exiges avant l'inscription definitive. Les droits du
# programme qualifiant n'en font pas partie : tous les etudiants n'en suivent
# pas, et le classeur ne montre aucun dossier bloque pour cette raison. Les
# ajouter au verrou serait inventer une regle.
PAIEMENTS_REQUIS_POUR_INSCRIPTION = (
    'frais_inscription_payes',
    'frais_scolarite_payes',
)


class HisEngagement(models.Model):
    """Le dossier d'admission EST l'engagement.

    Pas de modele « dossier » separe. L'engagement porte deja le parcours date
    d'une personne ; le dossier d'admission n'est que ce parcours vu par le
    back-office Admission.

    Cette lecture corrige un defaut du classeur : il rangeait « Re-Registration »
    parmi les STATUTS, a cote de « Admis » et « Inscrit ». Une reinscription
    n'est pas un etat, c'est un second parcours sur la meme personne et le meme
    matricule. Les deux axes sont ici separes : `etat` et `type_inscription`.
    """
    _inherit = 'his.engagement'

    # « Admis » manquait entre candidature soumise et inscription : le classeur
    # y garde 68 dossiers, c'est son etat le plus peuple. « Blocage
    # administratif » est un arret, pas un abandon — le candidat veut toujours
    # s'inscrire, c'est le dossier qui coince.
    etat = fields.Selection(
        selection_add=[
            ('candidat_soumis',),
            ('admis', "Admis"),
            ('blocage_administratif', "Blocage administratif"),
            ('inscrit',),
        ],
        ondelete={'admis': 'set default', 'blocage_administratif': 'set default'},
    )

    type_inscription = fields.Selection(
        TYPE_INSCRIPTION, string="Type d'inscription", default='nouveau', tracking=True,
    )
    cycle = fields.Selection(CYCLE, string="Cycle", tracking=True)
    niveau = fields.Selection(
        selection=[
            ('l1', "L1"), ('l2', "L2"), ('l3', "L3"),
            ('m1', "M1"), ('m2', "M2"),
        ],
        string="Niveau", tracking=True,
    )
    specialite_id = fields.Many2one(
        'his.specialite', string="Specialite", ondelete='restrict', tracking=True,
    )
    domaine_id = fields.Many2one(
        related='specialite_id.domaine_id', string="Domaine", store=True, readonly=True,
    )
    programme_qualifiant = fields.Selection(
        selection=[
            ('aucun', "Sans programme qualifiant"),
            ('inf', "PREP INF"),
            ('eco', "PREP ECO"),
            ('elc', "PREP ELC"),
        ],
        string="Programme qualifiant", default='aucun',
    )
    langue_etude = fields.Selection(
        selection=[
            ('arabe', "Arabe"), ('francais', "Francais"), ('anglais', "Anglais"),
        ],
        string="Langue d'etude",
    )
    # Numero libre, volontairement. Ils numerotent aujourd'hui en 260511001
    # (annee + filiere + specialite + sequence) ; rien n'est verifie ni impose.
    # Le matricule institutionnel du groupe vit sur his.person et prendra le
    # relais plus tard — decision prise, pas oubli.
    numero_etudiant = fields.Char(
        string="Numero d'etudiant", copy=False, index=True,
        help="Numero utilise aujourd'hui par l'Admission. Distinct du matricule "
             "institutionnel porte par la fiche personne.",
    )
    date_inscription = fields.Date(string="Date d'inscription")

    # --- Dossier academique --------------------------------------------------

    bac_numero = fields.Char(string="Numero du BAC")
    bac_session = fields.Char(string="Session du BAC", help="Annee, ex. 2025.")
    bac_filiere = fields.Selection(BAC_FILIERE, string="Filiere du BAC")
    bac_moyenne = fields.Float(string="Moyenne du BAC", digits=(4, 2))
    note_math = fields.Float(string="Note de maths", digits=(4, 2))
    note_physique = fields.Float(string="Note de physique", digits=(4, 2))
    type_lycee = fields.Selection(
        selection=[
            ('public', "Publique"), ('prive', "Privee"), ('libre', "Libre"),
        ],
        string="Type d'etablissement",
    )

    moyenne_ponderee = fields.Float(
        string="Moyenne ponderee", digits=(4, 2),
        compute='_compute_eligibilite', store=True, readonly=True,
    )
    eligibilite = fields.Selection(
        selection=[
            ('eligible', "Eligible"),
            ('a_verifier', "A verifier"),
        ],
        string="Eligibilite", compute='_compute_eligibilite', store=True, readonly=True,
    )
    eligibilite_motif = fields.Char(
        string="Motif", compute='_compute_eligibilite', store=True, readonly=True,
    )

    # --- Jalons du process ---------------------------------------------------

    inscription_initiale = fields.Boolean(string="Inscription initiale")
    lettre_acceptation = fields.Boolean(string="Lettre d'acceptation emise")
    inscription_definitive = fields.Boolean(string="Inscription definitive")
    lettre_definitive = fields.Boolean(string="Lettre definitive emise")

    # --- Paiements -----------------------------------------------------------
    # Paye / non paye seulement, comme le classeur. Aucun montant, aucun raccord
    # a la comptabilite : la caisse encaisse dans son propre outil, le guichet
    # enregistre. Le jour ou les montants comptent, c'est un chantier account,
    # pas trois champs de plus ici.
    #
    # readonly=True n'est pas cosmetique : depuis Odoo 16 le serveur REFUSE une
    # ecriture cliente sur un champ readonly. Un encaissement ne se coche donc
    # pas, il s'enregistre par _encaisser() — le seul chemin, pour le guichet
    # comme pour l'Admission, et demain pour le module Finance qui appellera la
    # meme methode. Un chemin unique est ce qui rend la trace fiable.
    frais_inscription_payes = fields.Boolean(
        string="Frais d'inscription payes", readonly=True, copy=False, tracking=True,
    )
    frais_scolarite_payes = fields.Boolean(
        string="Frais de scolarite payes", readonly=True, copy=False, tracking=True,
    )
    droits_prog_qualifiant_payes = fields.Boolean(
        string="Droits programme qualifiant payes", readonly=True, copy=False, tracking=True,
    )

    # --- Pieces --------------------------------------------------------------

    document_ids = fields.One2many(
        'his.admission.document', 'engagement_id', string="Pieces du dossier",
    )
    documents_complets = fields.Boolean(
        string="Dossier complet", compute='_compute_documents_complets', store=True,
    )
    documents_manquants = fields.Char(
        string="Pieces manquantes", compute='_compute_documents_complets', store=True,
    )

    # --- Carte etudiant ------------------------------------------------------

    carte_recue_it = fields.Boolean(string="Carte recue de l'IT")
    carte_etudiant_informe = fields.Boolean(string="Etudiant informe")
    carte_date_remise = fields.Date(string="Date de remise de la carte")

    # --- Origine commerciale -------------------------------------------------

    conseiller_id = fields.Many2one(
        'res.users', string="Conseillere", tracking=True,
        help="Conseillere Ventes qui a amene ce candidat. Reprise du lead a la "
             "pre-admission.",
    )
    lead_id = fields.Many2one(
        'crm.lead', string="Lead d'origine", ondelete='set null', copy=False,
    )

    # --- Eligibilite ---------------------------------------------------------

    @api.depends(
        'bac_moyenne', 'note_math', 'note_physique', 'domaine_id',
        'domaine_id.coef_bac', 'domaine_id.coef_math', 'domaine_id.coef_physique',
        'domaine_id.seuil_eligibilite', 'domaine_id.min_bac', 'domaine_id.min_math',
    )
    def _compute_eligibilite(self):
        """Calculee, jamais saisie.

        Le classeur laissait la formule dans une cellule recopiee a la main par
        domaine. Sa branche ST comparait `D18` — une cellule de TEXTE — au lieu
        de `C18` qui porte la moyenne. Excel juge tout texte superieur a tout
        nombre : cette branche repondait ELIGIBLE quelle que soit la moyenne, et
        un dossier sous le seuil passait sans que personne le voie. Ici la
        formule est unique et testee.
        """
        for eng in self:
            domaine = eng.domaine_id
            if not domaine or not eng.bac_moyenne:
                eng.moyenne_ponderee = 0.0
                eng.eligibilite = False
                eng.eligibilite_motif = False
                continue

            total_coef = domaine.coef_bac + domaine.coef_math + domaine.coef_physique
            moyenne = (
                eng.bac_moyenne * domaine.coef_bac
                + eng.note_math * domaine.coef_math
                + eng.note_physique * domaine.coef_physique
            ) / total_coef
            eng.moyenne_ponderee = moyenne

            # Les planchers sont eliminatoires independamment de la moyenne :
            # une excellente moyenne generale ne rachete pas une note de maths
            # sous le minimum exige par le domaine.
            if eng.bac_moyenne < domaine.min_bac:
                eng.eligibilite = 'a_verifier'
                eng.eligibilite_motif = _(
                    "Moyenne BAC %(valeur).2f inferieure au minimum %(mini).2f.",
                    valeur=eng.bac_moyenne, mini=domaine.min_bac,
                )
            elif domaine.min_math and eng.note_math < domaine.min_math:
                eng.eligibilite = 'a_verifier'
                eng.eligibilite_motif = _(
                    "Note de maths %(valeur).2f inferieure au minimum %(mini).2f.",
                    valeur=eng.note_math, mini=domaine.min_math,
                )
            elif moyenne < domaine.seuil_eligibilite:
                eng.eligibilite = 'a_verifier'
                eng.eligibilite_motif = _(
                    "Moyenne ponderee %(valeur).2f sous le seuil %(seuil).2f.",
                    valeur=moyenne, seuil=domaine.seuil_eligibilite,
                )
            else:
                eng.eligibilite = 'eligible'
                eng.eligibilite_motif = False

    # --- Pieces du dossier ---------------------------------------------------

    @api.depends('document_ids.fourni', 'document_ids.type_id.obligatoire')
    def _compute_documents_complets(self):
        for eng in self:
            manquantes = eng.document_ids.filtered(
                lambda d: d.type_id.obligatoire and not d.fourni,
            )
            eng.documents_complets = not manquantes
            eng.documents_manquants = ", ".join(manquantes.mapped('type_id.name'))

    def _types_documents_applicables(self):
        self.ensure_one()
        return self.env['his.document.type'].search([])._applicable(
            self.cycle, self.type_inscription, self.bac_filiere,
        )

    def _sync_documents(self):
        """Ajoute les pieces devenues applicables. N'en retire jamais aucune.

        Jamais de suppression : une piece deja cochee doit garder sa trace meme
        si le dossier change de cycle ou de filiere entre-temps. Effacer la
        ligne effacerait la preuve qu'un document a reellement ete recu. Les
        lignes devenues sans objet restent visibles et se retirent a la main.
        """
        for eng in self:
            manquants = eng._types_documents_applicables() - eng.document_ids.type_id
            if manquants:
                eng.document_ids = [(0, 0, {'type_id': t.id}) for t in manquants]

    @api.model_create_multi
    def create(self, vals_list):
        engagements = super().create(vals_list)
        engagements._sync_documents()
        return engagements

    def write(self, vals):
        res = super().write(vals)
        # Seuls ces trois champs decident des pieces applicables : inutile de
        # rejouer la synchronisation a chaque edition.
        if {'cycle', 'type_inscription', 'bac_filiere'} & vals.keys():
            self._sync_documents()
        return res

    def action_generer_documents(self):
        """Rattrapage, pour un dossier cree avant l'ouverture d'une nouvelle piece."""
        self._sync_documents()

    # --- Encaissements -------------------------------------------------------

    def _encaisser(self, champ):
        """Enregistre un encaissement. Seul chemin vers les champs de paiement.

        sudo() : le guichet Finance n'a que la LECTURE sur le dossier
        (ir.model.access.csv). C'est voulu — il enregistre un encaissement, il
        ne corrige pas une note de BAC ni ne coche « contrat signe ». Cette
        methode est la porte etroite par laquelle il agit, et elle n'ecrit
        qu'un champ.

        C'est aussi le point d'entree que le futur module Finance appellera :
        quand la caisse notifiera un paiement, elle passera par ici et tout le
        reste — le chatter, le passage du lead en gagne — suivra sans etre
        reecrit ailleurs.
        """
        for eng in self:
            if eng[champ]:
                continue
            eng.sudo().write({champ: True})
            eng.sudo().message_post(body=_(
                "%(droit)s : encaissement enregistre par %(user)s.",
                droit=LIBELLES_PAIEMENT.get(champ, champ),
                user=self.env.user.display_name,
            ))
            # C'est ICI que le candidat devient quelqu'un de l'institution.
            #
            # Le matricule est a vie et sa sequence ne se recycle jamais : le
            # poser au premier contact revenait a en bruler un par candidature,
            # dont six sur dix pour des gens qui ne seront jamais etudiants.
            # Les frais d'inscription sont non remboursables — c'est le premier
            # engagement irreversible des DEUX cotes, donc le bon moment.
            #
            # Le dossier, lui, existe depuis la pre-admission : il faut bien un
            # endroit ou enregistrer cet encaissement. Voir hypothese A1.
            if champ == 'frais_inscription_payes' and eng.person_id:
                # sudo() : le guichet Finance n'a AUCUN droit sur le
                # referentiel d'identite, et c'est voulu. Emettre le matricule
                # est une consequence de l'encaissement qu'il enregistre, pas
                # un geste qu'il s'autorise — meme raisonnement que la porte
                # etroite ci-dessus.
                personne = eng.person_id.sudo()
                personne._his_attribuer_matricule()
                eng.sudo().message_post(body=_(
                    "Matricule institutionnel attribue : %(matricule)s.",
                    matricule=personne.matricule_institutionnel,
                ))

    def action_encaisser_frais_inscription(self):
        """Les frais non remboursables. C'est CE geste qui gagne le lead."""
        self._encaisser('frais_inscription_payes')
        self._his_gagner_le_lead()

    def action_encaisser_frais_scolarite(self):
        self._encaisser('frais_scolarite_payes')

    def action_encaisser_droits_prog_qualifiant(self):
        self._encaisser('droits_prog_qualifiant_payes')

    def _his_gagner_le_lead(self):
        """Pousse le lead d'origine a l'etape gagnante.

        La conversion commerciale n'est pas declaree par les Ventes : elle est
        la consequence d'un encaissement enregistre par une autre equipe. Le
        chiffre du pipeline reflete donc de l'argent recu, pas des intentions,
        et il n'y a rien a surveiller pour que cela reste vrai.
        """
        etape = self.env.ref(
            'his_crm_pipeline.stage_vente_frais_payes', raise_if_not_found=False,
        )
        if not etape:
            return
        for eng in self:
            if eng.lead_id and eng.lead_id.stage_id != etape:
                # sudo() : c'est le guichet qui declenche, et il n'a aucun droit
                # sur le CRM. Le fait est acquis, l'ecriture doit aboutir.
                eng.lead_id.sudo().stage_id = etape

    # --- Le verrou -----------------------------------------------------------

    @api.constrains(
        'etat', 'document_ids', 'document_ids.fourni',
        'frais_inscription_payes', 'frais_scolarite_payes',
    )
    def _check_dossier_complet_avant_inscription(self):
        """Pas d'« Inscrit » sans dossier complet ni droits encaisses.

        Contrainte serveur et non regle de vue, meme discipline que le verrou
        d'approbation de his_crm_pipeline et que la gouvernance de
        his_stock_mdm. C'est exactement le trou du classeur : des dossiers y
        sont marques Inscrit avec des cases de pieces restees a False, parce que
        rien n'obligeait a les remplir. Une regle contournable par import ou par
        API n'est pas une regle.
        """
        for eng in self:
            if eng.etat != 'inscrit':
                continue
            griefs = []
            if eng.documents_manquants:
                griefs.append(_("pieces manquantes : %s", eng.documents_manquants))
            impayes = [
                LIBELLES_PAIEMENT[champ]
                for champ in PAIEMENTS_REQUIS_POUR_INSCRIPTION if not eng[champ]
            ]
            if impayes:
                griefs.append(_("droits non encaisses : %s", ", ".join(impayes)))
            if griefs:
                raise ValidationError(_(
                    "« %(personne)s » ne peut pas passer a « Inscrit » — %(griefs)s.\n\n"
                    "Un dossier incomplet reste en « Admis » ou en « Blocage "
                    "administratif ».",
                    personne=eng.person_id.display_name,
                    griefs=" ; ".join(griefs),
                ))
