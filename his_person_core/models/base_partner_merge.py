# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, models
from odoo.exceptions import UserError


class MergePartnerAutomatic(models.TransientModel):
    _inherit = "base.partner.merge.automatic.wizard"

    def _merge(self, partner_ids, dst_partner=None, extra_checks=True):
        # Fusionner deux contacts supprime le contact source, et sa fiche
        # his.person avec lui (delegation, ondelete cascade) : le matricule
        # disparaissait, meme pas archive (recette P-12). Deux personnes ne se
        # fusionnent pas : on archive le doublon, son matricule reste trace.
        people = (
            self.env["his.person"]
            .sudo()
            .with_context(active_test=False)
            .search([("partner_id", "in", list(partner_ids))])
        )
        if len(people) > 1:
            raise UserError(
                _(
                    "These contacts are %(people)s in the register: merging them would delete a registration "
                    "number. Archive the duplicate person instead.",
                    people=", ".join(f"{p.display_name} ({p.matricule_institutionnel or '-'})" for p in people),
                )
            )
        return super()._merge(partner_ids, dst_partner=dst_partner, extra_checks=extra_checks)
