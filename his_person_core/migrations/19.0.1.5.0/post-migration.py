"""Le compteur des matricules passe en no_gap (recette P-23).

La sequence est en noupdate : on la convertit ici. Odoo, en quittant
« standard », supprime les sequences PostgreSQL sans reporter leur valeur dans
number_next : sans la copie ci-dessous, la numerotation repartirait de l'ancien
number_next et reemettrait des matricules deja attribues.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    sequence = env.ref("his_person_core.seq_his_person_matricule_institutionnel", raise_if_not_found=False)
    if not sequence or sequence.implementation == "no_gap":
        return
    suivants = {plage: plage.number_next_actual for plage in sequence.date_range_ids}
    suivant = sequence.number_next_actual
    sequence.write({"implementation": "no_gap", "number_next": suivant})
    for plage, numero in suivants.items():
        plage.write({"number_next": numero})
