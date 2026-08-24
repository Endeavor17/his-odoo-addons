# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Garde-fous de capacite : qui a le droit de faire quoi a un lead.

Trois couches repondent a trois questions differentes, et il ne faut pas les
confondre :

  - `ir.model.access`  : quels MODELES je touche
  - `ir.rule`          : quels ENREGISTREMENTS je vois
  - ce fichier         : quelles TRANSITIONS je peux provoquer

Odoo ne sait pas exprimer la troisieme de facon declarative. Un utilisateur qui
peut ecrire sur un enregistrement peut ecrire tous ses champs — c'est ainsi
qu'un graphiste pouvait marquer une demande « Gagnee ». Les regles ci-dessous
comblent ce trou, et elles sont posees en une seule table lisible plutot qu'en
`if` disperses dans le modele.

Les vues masquent les memes gestes (boutons, champs en lecture seule), mais
elles ne protegent rien : un import, l'API ou le kanban les contournent. Ce
fichier est la ou la regle tient reellement.
"""
from odoo import _, api, models
from odoo.exceptions import AccessError

# La regle « un livrable n'avance que par la main de son assigne » ne vit plus
# ici : elle a suivi les livrables dans his.content.deliverable.write(), ou
# l'enregistrement EST le livrable et ou elle tient en une comparaison. Elle
# devait auparavant balayer neuf champs pour deviner de quel livrable on
# parlait.


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # --- Points d'entree -----------------------------------------------------

    def write(self, vals):
        self._his_verifier_capacites(vals)
        return super().write(vals)

    # --- Le controle ---------------------------------------------------------

    def _his_verifier_capacites(self, vals):
        """Refuse une ecriture que le role de l'utilisateur n'autorise pas.

        Le superutilisateur et les ecritures systeme passent sans controle :
        creer une fiche personne au premier contact, faire passer un dossier a
        « admis », gagner un lead sur encaissement sont des CONSEQUENCES d'un
        geste legitime, pas des gestes d'utilisateur. Elles sont declenchees en
        sudo() par le code, et doivent aboutir meme quand celui qui a clique
        n'aurait pas le droit de les faire a la main.
        """
        if self.env.su or not self:
            return
        for lead in self:
            if lead._his_est_contenu():
                lead._his_capacites_contenu(vals)
            else:
                lead._his_capacites_admissions(vals)

    def _his_est_contenu(self):
        self.ensure_one()
        equipe = self.env.ref(
            'his_crm_pipeline.crm_team_contenu', raise_if_not_found=False,
        )
        return bool(equipe) and self.team_id == equipe

    @staticmethod
    def _his_refus(message):
        raise AccessError(message)

    # --- Production Contenu --------------------------------------------------

    def _his_capacites_contenu(self, vals):
        self.ensure_one()
        etape_production = self.env.ref(
            'his_crm_pipeline.stage_contenu_production', raise_if_not_found=False,
        )
        peut_approuver = self.env.user.has_group('his_crm_pipeline.group_contenu_approbation')
        peut_prioriser = self.env.user.has_group('his_crm_pipeline.group_contenu_priorisation')

        # 1. Sortir de « Production » — approuver, publier, renvoyer — est le
        #    geste du directeur. C'est precisement ce qu'un producteur pouvait
        #    faire jusqu'ici en cliquant « Gagne » ou « Perdu ».
        sortie = (
            ('stage_id' in vals and etape_production
             and self.stage_id == etape_production
             and vals['stage_id'] != etape_production.id)
            or vals.get('active') is False
            or vals.get('lost_reason_id')
        )
        if sortie and not peut_approuver:
            self._his_refus(_(
                "Approuver, publier ou refuser une demande de contenu demande le "
                "role « Approbation ». Votre role vous permet de faire avancer "
                "votre livrable, pas de clore la demande."
            ))

        # 2. Faire avancer l'etape avant la production appartient au tri, donc a
        #    la priorisation. L'avancement des livrables eux-memes est garde
        #    dans his.content.deliverable.write(), aupres de l'enregistrement
        #    qu'il concerne.
        if not peut_prioriser and 'stage_id' in vals and not sortie:
            self._his_refus(_(
                "Faire avancer une demande demande le role « Priorisation »."
            ))

    # --- Admissions ----------------------------------------------------------

    def _his_capacites_admissions(self, vals):
        self.ensure_one()
        user = self.env.user

        # Un lead sans role Admissions n'est pas de notre ressort : le CRM natif
        # reste utilisable pour d'autres equipes, ce module n'a pas a policer
        # leurs pipelines.
        if not user.has_group('his_crm_pipeline.group_admissions_acquisition') \
                and not user.has_group('his_crm_pipeline.group_admissions_orientation'):
            return

        # 1. La Cellule d'Orientation n'agit que sur un candidat qui se trouve
        #    dans SON etape. Elle voit les autres passer, elle n'y touche pas.
        etape_psy = self.env.ref(
            'his_crm_pipeline.stage_vente_evaluation_psy', raise_if_not_found=False,
        )
        if user.has_group('his_crm_pipeline.group_admissions_orientation') \
                and not user.has_group('his_crm_pipeline.group_admissions_conseiller') \
                and etape_psy and self.stage_id != etape_psy:
            self._his_refus(_(
                "La Cellule d'Orientation n'intervient que sur un candidat en "
                "evaluation psychologique."
            ))

        # 2. Le Marketing capture et score. La prise en charge appartient aux
        #    Ventes : c'est la passation, elle doit rester un geste des Ventes.
        etape_nouveau = self.env.ref(
            'his_crm_pipeline.stage_vente_nouveau', raise_if_not_found=False,
        )
        if 'stage_id' in vals and etape_nouveau \
                and self.stage_id == etape_nouveau \
                and vals['stage_id'] != etape_nouveau.id \
                and not user.has_group('his_crm_pipeline.group_admissions_conseiller'):
            self._his_refus(_(
                "Le role « Acquisition » capture et score les candidatures. Faire "
                "avancer un lead au-dela de « Nouveau (score) » appartient aux "
                "conseilleres."
            ))

        # 3. Affecter est l'arbitrage du responsable. Sans cela, une conseillere
        #    pourrait se servir dans la file avant ses collegues, ce que le tri
        #    par score existe precisement pour eviter.
        if 'user_id' in vals \
                and not user.has_group('his_crm_pipeline.group_admissions_responsable'):
            self._his_refus(_(
                "Affecter un lead a une conseillere appartient au responsable "
                "d'equipe. La file est triee par score : s'y servir soi-meme "
                "viderait ce tri de son sens."
            ))

    # --- Creation ------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Trace qui a demande, AVANT la creation et non apres.

        `demandeur_id` porte la portee du role Demandeur : sa regle
        d'enregistrement est `demandeur_id = user.id`. Le poser apres coup
        n'aurait pas marche — entre le `create` et l'ecriture, la demande ne
        correspond a aucune regle et son propre auteur ne peut deja plus la
        relire. Odoo repond alors « top-secret records » sur un enregistrement
        cree une milliseconde plus tot.

        On ne s'appuie pas sur `user_id` : celui-la change de main a la
        priorisation, et le demandeur perdrait sa demande de vue au moment
        precis ou elle commence a avancer.
        """
        equipe_contenu = self.env.ref(
            'his_crm_pipeline.crm_team_contenu', raise_if_not_found=False,
        )
        if equipe_contenu:
            defaut = self.env.context.get('default_team_id')
            for vals in vals_list:
                equipe = vals.get('team_id', defaut)
                if equipe == equipe_contenu.id and not vals.get('demandeur_id'):
                    vals['demandeur_id'] = self.env.uid
        return super().create(vals_list)
