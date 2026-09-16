# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models


def _campus_identity_backfill(env):
    """Rattache les candidatures deja parvenues a l'etape declencheuse.

    Idempotent : une candidature deja rattachee, ou en attente d'arbitrage, est
    ignoree. Au 2026-09-13 aucune ne l'est en production (les 249 sont
    « not_selected »), mais une installation ulterieure ne doit rien oublier.
    """
    env["hr.applicant"].search([])._his_creer_ou_rapprocher_personne()
