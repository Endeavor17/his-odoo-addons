# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Bareme du HIS Lead Score, sur 10. Fourni verbatim par la Direction, repris
# du script de scoring qui tournait dans GoHighLevel.
#
# ponytail: des constantes, pas un modele de configuration. Trois seuils et
# quatre valeurs de points, donnes une fois comme une regle etablie — un
# modele de configuration coûterait plus a maintenir qu'il ne rapporte. Si la
# Direction se met a reviser ce bareme d'une rentree a l'autre, en faire des
# donnees se fait en une passe : la logique ci-dessous ne lit ces constantes
# qu'a trois endroits.
BAC_SEUIL_HAUT, BAC_POINTS_HAUT = 14.0, 6
BAC_SEUIL_MOYEN, BAC_POINTS_MOYEN = 12.0, 4
BAC_POINTS_BAS = 2

PONDERE_SEUIL, PONDERE_POINTS_HAUT, PONDERE_POINTS_BAS = 12.0, 3, 2

MOTIVATION_POINTS = 1


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # --- Ce que le formulaire de candidature envoie -------------------------

    specialite_id = fields.Many2one(
        'his.specialite', string="Specialite visee", ondelete='restrict',
        help="Determine quelles notes comptent dans le score : le domaine de la "
             "specialite dit deja lesquelles il utilise.",
    )
    domaine_id = fields.Many2one(
        related='specialite_id.domaine_id', string="Domaine", store=True, readonly=True,
    )
    bac_moyenne = fields.Float(string="Moyenne du BAC", digits=(4, 2))
    note_math = fields.Float(string="Note de maths", digits=(4, 2))
    note_physique = fields.Float(string="Note de physique", digits=(4, 2))

    motivation_majeure = fields.Text(string="Pourquoi cette specialite ?")
    motivation_his = fields.Text(string="Pourquoi HIS ?")

    # Quelles notes sont demandees depend de la majeure. Plutot qu'une seconde
    # table de correspondance a tenir en phase avec la premiere, on lit celle
    # qui existe : un domaine qui ne pondere pas les maths ne les demande pas.
    note_math_utilisee = fields.Boolean(compute='_compute_notes_utilisees')
    note_physique_utilisee = fields.Boolean(compute='_compute_notes_utilisees')

    # --- Le score, calcule ---------------------------------------------------

    # Redefinition : his_crm_pipeline le livre en saisie libre, pour rester
    # installable seul. Des que le referentiel academique est la, le score
    # cesse d'etre une opinion et devient un calcul.
    score_academique = fields.Integer(
        compute='_compute_score_academique', store=True, readonly=True,
    )
    score_detail = fields.Char(
        string="Detail du score", compute='_compute_score_academique', store=True,
        readonly=True,
        help="Comment les points ont ete obtenus. Le score ordonne la file "
             "d'affectation : il doit pouvoir s'expliquer a la conseillere qui "
             "recoit le lead.",
    )

    @api.depends('domaine_id.coef_math', 'domaine_id.coef_physique')
    def _compute_notes_utilisees(self):
        for lead in self:
            lead.note_math_utilisee = bool(lead.domaine_id.coef_math)
            lead.note_physique_utilisee = bool(lead.domaine_id.coef_physique)

    def _moyenne_ponderee_lead(self):
        """Moyenne des notes que la majeure utilise reellement, ou None.

        Le bareme de la Direction donne deux formules — (BAC + Math) / 2 pour
        l'informatique, l'economie et le commerce, (BAC + Math + Physique) / 3
        pour l'electronique — et aucune pour la psychologie clinique et le
        droit public.

        Les trois cas se ramenent a un seul : c'est la moyenne simple des notes
        que le domaine pondere. Le referentiel encode deja cette distinction
        dans ses coefficients d'eligibilite ; en deduire une seconde table
        serait se donner deux verites a tenir en phase. Ouvrir une specialite
        dans un domaine existant lui donne donc le bon scoring sans rien
        ajouter.

        Retourne None si la moyenne n'est pas calculable — majeure sans notes
        ponderees, ou note exigee non saisie. « Pas calculable » et « faible »
        ne rapportent pas le meme nombre de points, il faut les distinguer.
        """
        self.ensure_one()
        notes = [self.bac_moyenne]
        if self.note_math_utilisee:
            notes.append(self.note_math)
        if self.note_physique_utilisee:
            notes.append(self.note_physique)
        if len(notes) == 1 or not all(notes):
            return None
        return sum(notes) / len(notes)

    @api.depends(
        'bac_moyenne', 'note_math', 'note_physique',
        'note_math_utilisee', 'note_physique_utilisee',
        'motivation_majeure', 'motivation_his',
    )
    def _compute_score_academique(self):
        for lead in self:
            if not lead.bac_moyenne:
                lead.score_academique = 0
                lead.score_detail = _("Moyenne du BAC non renseignee.")
                continue

            if lead.bac_moyenne >= BAC_SEUIL_HAUT:
                points_bac = BAC_POINTS_HAUT
            elif lead.bac_moyenne >= BAC_SEUIL_MOYEN:
                points_bac = BAC_POINTS_MOYEN
            else:
                points_bac = BAC_POINTS_BAS
            detail = [_("BAC %(note).2f : %(pts)s pts", note=lead.bac_moyenne, pts=points_bac)]

            ponderee = lead._moyenne_ponderee_lead()
            if ponderee is None:
                points_ponderee = 0
                detail.append(_("moyenne ponderee non applicable : 0 pt"))
            else:
                points_ponderee = (
                    PONDERE_POINTS_HAUT if ponderee >= PONDERE_SEUIL
                    else PONDERE_POINTS_BAS
                )
                detail.append(_(
                    "ponderee %(note).2f : %(pts)s pts", note=ponderee, pts=points_ponderee,
                ))

            motive = bool(
                (lead.motivation_majeure or '').strip()
                or (lead.motivation_his or '').strip()
            )
            points_motivation = MOTIVATION_POINTS if motive else 0
            detail.append(_("motivation : %(pts)s pt", pts=points_motivation))

            lead.score_academique = points_bac + points_ponderee + points_motivation
            lead.score_detail = " + ".join(detail)

    def _his_assurer_engagement(self):
        """Le dossier reprend ce que la capture a recueilli.

        Le lead porte les donnees academiques parce que c'est la qu'elles
        arrivent — le formulaire les envoie avant qu'aucune fiche personne
        n'existe. Le dossier en prend possession au premier contact ; un lead
        perdu garde donc sa saisie sans avoir rien depose dans le referentiel
        d'identite.
        """
        super()._his_assurer_engagement()
        engagement = self.his_person_id.engagement_ids.filtered(
            lambda e: e.etat == 'prospect',
        )[:1]
        if not engagement or engagement.specialite_id:
            return
        engagement.sudo().write({
            'specialite_id': self.specialite_id.id,
            'cycle': self.specialite_id.cycle,
            'bac_moyenne': self.bac_moyenne,
            'note_math': self.note_math,
            'note_physique': self.note_physique,
        })

    def _his_engagement(self):
        """Le dossier rattache a ce lead, s'il y en a un."""
        self.ensure_one()
        if not self.his_person_id:
            return self.env['his.engagement']
        propre = self.his_person_id.engagement_ids.filtered(
            lambda e: e.lead_id == self,
        )
        # Avant la pre-admission, lead_id n'est pas encore pose : on retombe
        # sur le parcours ouvert de la personne, celui que le pont a cree.
        return propre[:1] or self.his_person_id.engagement_ids[:1]

    @api.constrains('stage_id')
    def _check_gagne_seulement_si_encaisse(self):
        """On n'entre pas en gagne sans encaissement.

        C'est la regle demandee : un lead n'est gagne qu'au paiement des frais
        d'inscription non remboursables. La poser en contrainte serveur et non
        en droit d'acces a une consequence utile — meme un administrateur, meme
        un import, meme l'API ne peuvent pas gonfler le pipeline. Le chiffre
        commercial ne peut mentir que si l'argent est entre.

        Le passage en gagne se fait tout seul, depuis l'encaissement
        (his.engagement._his_gagner_le_lead). Personne n'a a l'y mettre a la
        main : cette contrainte n'attrape donc qu'une tentative de raccourci.
        """
        etape = self.env.ref(
            'his_crm_pipeline.stage_vente_frais_payes', raise_if_not_found=False,
        )
        if not etape:
            return
        for lead in self:
            if lead.stage_id != etape:
                continue
            engagement = lead._his_engagement()
            if not engagement or not engagement.frais_inscription_payes:
                raise ValidationError(_(
                    "« %(lead)s » ne peut pas etre gagne : les frais d'inscription "
                    "ne sont pas encaisses.\n\n"
                    "Le lead y passera de lui-meme quand le guichet enregistrera "
                    "l'encaissement. Un candidat pre-admis qui ne paie pas se perd "
                    "avec le motif « Paiement non confirme ».",
                    lead=lead.display_name,
                ))

    def write(self, vals):
        res = super().write(vals)
        if 'stage_id' in vals:
            self._his_passer_engagement_a_admis()
        return res

    def _his_passer_engagement_a_admis(self):
        """Pre-admission prononcee : l'engagement passe a « Admis ».

        C'est la passation Ventes -> Admission. Le pont d'identite
        (his_crm_identity_bridge) a cree l'engagement a « prospect » au premier
        contact ; ici il devient un dossier a instruire, et la conseillere qui
        a amene le candidat reste tracee dessus.

        Rien au-dela : « Inscrit » depend du dossier complet et des droits
        encaisses, et c'est le verrou du dossier qui en decide, pas le CRM.
        """
        etape = self.env.ref(
            'his_crm_pipeline.stage_vente_pre_admis', raise_if_not_found=False,
        )
        if not etape:
            return
        for lead in self:
            if lead.stage_id != etape or not lead.his_person_id:
                continue
            # Le dossier deja instruit ne redescend pas : repasser par
            # « Pre-admis » apres une inscription ne doit pas defaire le travail
            # de l'Admission.
            engagement = lead.his_person_id.engagement_ids.filtered(
                lambda e: e.etat in ('prospect', 'candidat_soumis'),
            )[:1]
            if not engagement:
                continue
            # sudo() : la conseillere prononce la pre-admission, mais elle n'a
            # que la LECTURE sur le dossier — c'est l'Admission qui l'instruit.
            # Le passage a « admis » est une consequence de sa decision, pas
            # une modification qu'elle s'autorise. Sans cela, le seul geste
            # legitime des Ventes leve une erreur de droits.
            engagement = engagement.sudo()
            engagement.write({
                'etat': 'admis',
                'conseiller_id': lead.user_id.id,
                'lead_id': lead.id,
            })
            engagement.message_post(body=_(
                "Pre-admission prononcee sur le lead « %(lead)s ». Dossier "
                "transmis a l'Admission.",
                lead=lead.display_name,
            ))

    def action_ouvrir_dossier_admission(self):
        """Bouton statistique : la conseillere suit son candidat, en lecture seule."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Dossier d'admission"),
            'res_model': 'his.engagement',
            'view_mode': 'form',
            'res_id': self.his_person_id.engagement_ids[:1].id,
        }
