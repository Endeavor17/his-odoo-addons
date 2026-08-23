# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

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
