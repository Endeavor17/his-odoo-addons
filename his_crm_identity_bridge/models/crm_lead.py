# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models

# Etape declencheuse. Lue depuis un ir.config_parameter et non ecrite en dur :
# « premier contact » n'est pas encore tranche par la Direction (hypothese A1).
# « Contact etabli » est la proposition — le conseiller a effectivement parle au
# candidat, pas seulement recu son lead. Changer d'avis doit rester un
# parametre, pas une modification de code.
PARAM_ETAPE_DECLENCHEUSE = 'his_crm.identity_trigger_stage_xmlid'
# Hypothese A1, TRANCHEE : la pre-admission.
#
# « Contact etabli » etait la proposition initiale. Elle a ete rejetee sur
# preuve : entrer dans le referentiel cree une fiche, et une fiche de candidat
# ouvre le dossier qui recevra l'encaissement. Or le CRM reel perd 954
# opportunites sur 1558. Declencher au premier contact revenait a ouvrir un
# dossier pour six candidats sur dix qui n'en auront jamais l'usage.
#
# La pre-admission est le dernier point AVANT l'argent : c'est le moment ou
# l'institution se prononce, et il reste un endroit ou enregistrer le paiement
# qui suit. Declencher a l'encaissement lui-meme etait impossible — le
# paiement s'enregistre SUR le dossier, qui n'existerait donc pas encore.
#
# Le matricule, lui, n'est plus emis ici : voir his_person_core, il est
# attribue a l'encaissement des frais d'inscription.
ETAPE_DECLENCHEUSE_DEFAUT = 'his_crm_pipeline.stage_vente_pre_admis'


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    his_person_id = fields.Many2one(
        'his.person', string="Fiche personne", readonly=True, copy=False, index=True,
        help="Fiche du referentiel Identite rattachee a ce lead. Creee ou "
             "rapprochee au premier contact.",
    )
    his_person_candidate_id = fields.Many2one(
        'his.person', string="Fiche proposee", readonly=True, copy=False,
        help="Meilleure correspondance trouvee dans le referentiel. Tant "
             "qu'elle n'est pas confirmee par un humain, RIEN n'est rattache.",
    )
    his_person_match_score = fields.Float(
        string="Score de rapprochement", digits=(3, 2), readonly=True, copy=False,
    )

    # --- Declencheur ---------------------------------------------------------

    @api.model
    def _his_etape_declencheuse(self):
        xmlid = self.env['ir.config_parameter'].sudo().get_param(
            PARAM_ETAPE_DECLENCHEUSE, ETAPE_DECLENCHEUSE_DEFAUT,
        )
        return self.env.ref(xmlid, raise_if_not_found=False)

    def write(self, vals):
        res = super().write(vals)
        # Seul un changement d'etape peut declencher : inutile de rejouer le
        # rapprochement a chaque edition d'un champ quelconque.
        if 'stage_id' in vals or 'team_id' in vals:
            self._his_creer_ou_rapprocher_personne()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        leads._his_creer_ou_rapprocher_personne()
        return leads

    def _his_creer_ou_rapprocher_personne(self):
        """Rapproche ou cree la fiche personne des leads arrives a l'etape voulue.

        Idempotent a trois niveaux, parce qu'un lead peut revenir en arriere
        puis repasser par l'etape :
          - his_person_id deja pose : on ne fait rien ;
          - une proposition en attente : on n'en refait pas une deuxieme ;
          - meme sans ces garde-fous, _find_or_flag_match retrouverait la fiche
            de facon deterministe sur (external_ref, source_system), la cle que
            his_person_core pose deja pour que rejouer un import ne duplique
            rien.
        """
        etape = self._his_etape_declencheuse()
        equipe = self.env.ref(
            'his_crm_pipeline.crm_team_ventes', raise_if_not_found=False,
        )
        if not etape or not equipe:
            return
        Person = self.env['his.person'].sudo()
        for lead in self:
            # « PARVENU a l'etape », et non « pose exactement dessus ».
            #
            # Le kanban autorise de tirer une carte de « Pris en charge » droit
            # vers « Dossier et pre-admission ». Avec une egalite stricte, ce
            # geste ordinaire ne creait NI personne NI dossier, et rien ne le
            # signalait : le candidat n'existait tout simplement pas pour
            # l'Admission. Constate sur la base de recette — 2 candidatures en
            # « Dossier » et 1 en « Pre-admis » sans aucun dossier ouvert.
            #
            # La comparaison porte sur la sequence et non sur l'id : c'est elle
            # qui ordonne le pipeline, et c'est elle que le kanban respecte.
            # Le cloisonnement par equipe reste la garde qui empeche les etapes
            # du pipeline Contenu d'entrer dans cette comparaison.
            # Un lead sans etape a une sequence de 0 : il tombe naturellement
            # du mauvais cote de la comparaison, aucun garde-fou de plus.
            if lead.team_id != equipe or lead.stage_id.sequence < etape.sequence:
                continue
            if lead.his_person_id or lead.his_person_candidate_id:
                continue

            match = Person._find_or_flag_match(lead._his_candidate_vals())

            if match['conflict']:
                lead._his_signaler(match['conflict'])
                continue

            if match['method'] == 'probabilistic':
                # Jamais de lien automatique, quel que soit le score. Meme
                # regle que l'import Google Sheets : au-dessus du seuil, c'est
                # un humain qui tranche.
                lead.write({
                    'his_person_candidate_id': match['person'].id,
                    'his_person_match_score': match['score'],
                })
                lead._his_signaler(_(
                    "Correspondance probable (%(score)d%%) avec « %(fiche)s » : "
                    "a confirmer ou refuser depuis le lead. Aucune fiche n'a ete "
                    "rattachee.",
                    score=round(match['score'] * 100),
                    fiche=match['person'].display_name,
                ))
                continue

            if match['person']:
                lead.his_person_id = match['person']
            else:
                lead.his_person_id = lead._his_creer_personne(match['method'])
            lead._his_assurer_engagement()

    # --- Construction des donnees -------------------------------------------

    def _his_candidate_vals(self):
        """Traduit le lead en vocabulaire du referentiel Personnes.

        email_personnel et non email institutionnel : a ce stade le candidat
        n'a aucun compte dans l'institution. Lui poser une adresse
        institutionnelle reviendrait a inventer une donnee.
        """
        self.ensure_one()
        return {
            'name': self.contact_name or self.partner_name or self.name,
            'email_personnel': self.email_from,
            'phone': self.phone,
            'source_system': 'odoo_crm',
            'external_ref': str(self.id),
        }

    def _his_creer_personne(self, method):
        self.ensure_one()
        vals = dict(
            self._his_candidate_vals(),
            type_personne='candidat',
            match_method=method,
        )
        # Le lead porte deja un contact : on le reprend au lieu d'en creer un
        # second. his.person delegue a res.partner, donc sans cette reprise le
        # meme humain se retrouverait avec deux fiches contact — l'une portant
        # l'historique commercial, l'autre le matricule. La contrainte
        # unique(partner_id) du socle interdit de rattacher un contact deja
        # porteur d'une fiche : on le verifie avant.
        partner = self.partner_id
        if partner and not partner.his_person_ids:
            vals['partner_id'] = partner.id
        # sudo() : creer une fiche, c'est emettre un matricule a vie. Le droit
        # est volontairement etroit dans his_person_core, les modules qui en
        # creent le font depuis leur logique serveur.
        person = self.env['his.person'].sudo().create(vals)
        person.message_post(body=_(
            "Fiche creee depuis le lead CRM « %(lead)s » au premier contact.",
            lead=self.display_name,
        ))
        return person

    def _his_assurer_engagement(self):
        """Ouvre l'engagement prospect, s'il n'y en a pas deja un.

        Aucune transition au-dela de prospect n'est faite ici : candidat_soumis
        et la suite dependent de la confirmation du paiement des frais
        d'inscription, qui appartient a Finance/Admission.
        """
        self.ensure_one()
        person = self.his_person_id
        if not person or person.engagement_ids.filtered(lambda e: e.etat == 'prospect'):
            return
        self.env['his.engagement'].sudo().create({
            'person_id': person.id,
            'etat': 'prospect',
        })

    def _his_signaler(self, message):
        """Rend un cas a arbitrer visible la ou le conseiller travaille."""
        self.ensure_one()
        self.message_post(body=message)
        destinataire = self.user_id or self.team_id.user_id
        if destinataire:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary="Rapprochement Identite a arbitrer",
                note=message,
                user_id=destinataire.id,
            )

    # --- Arbitrage humain ----------------------------------------------------

    def action_confirm_person_match(self):
        """Le conseiller reconnait la personne : on rattache, on trace qui et quand."""
        for lead in self:
            person = lead.his_person_candidate_id
            if not person:
                continue
            person.sudo().write({
                'match_method': 'probabilistic',
                'matched_by': self.env.user.id,
                'matched_on': fields.Datetime.now(),
            })
            lead.write({
                'his_person_id': person.id,
                'his_person_candidate_id': False,
            })
            lead._his_assurer_engagement()
            lead.message_post(body=_(
                "Rapprochement (%(score)d%%) confirme par %(user)s.",
                score=round(lead.his_person_match_score * 100),
                user=self.env.user.display_name,
            ))

    def action_reject_person_match(self):
        """Ce n'est pas la meme personne : fiche distincte, matricule distinct."""
        for lead in self:
            if not lead.his_person_candidate_id:
                continue
            lead.his_person_candidate_id = False
            lead.his_person_id = lead._his_creer_personne('new')
            lead._his_assurer_engagement()
            lead.message_post(body=_(
                "Rapprochement refuse par %(user)s : fiche distincte creee.",
                user=self.env.user.display_name,
            ))
