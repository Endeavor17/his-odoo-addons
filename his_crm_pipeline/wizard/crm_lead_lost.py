# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.tools import html2plaintext
from odoo.tools.mail import is_html_empty

# Une precision est une ligne, pas un rapport. Au-dela, c'est le fil de
# discussion qui porte le detail — Odoo l'y met deja.
LONGUEUR_PRECISION = 200


class CrmLeadLost(models.TransientModel):
    """La note de cloture atterrit sur le lead, et pas seulement dans le fil.

    Odoo ne se sert de `lost_feedback` que comme message de suivi
    (crm/wizard/crm_lead_lost.py) : elle explique la perte a qui relit la
    fiche, mais AUCUN champ ne la porte. Une contrainte serveur ne peut donc
    pas l'exiger, et le motif « Autre » en a besoin — sans precision il ne dit
    rien de plus qu'un motif vide.

    On la recopie donc sur le lead avant que la perte ne s'applique. La
    conseillere continue d'utiliser l'assistant natif, sans rien apprendre de
    nouveau.
    """
    _inherit = 'crm.lead.lost'

    def action_lost_reason_apply(self):
        if not is_html_empty(self.lost_feedback):
            # sudo() : la note est une consequence du geste de cloture, pas une
            # modification que la conseillere s'autorise separement.
            self.lead_ids.sudo().perte_precision = html2plaintext(
                self.lost_feedback,
            ).strip()[:LONGUEUR_PRECISION]
        return super().action_lost_reason_apply()
