# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, models
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

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
