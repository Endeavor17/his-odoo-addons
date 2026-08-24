# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Les livrables quittent crm.lead pour leur propre table.

Ils etaient trois triplets de colonnes — besoin_/statut_/assignee_ fois copy,
design, video. Une demande de contenu reelle porte donc son travail dans ces
colonnes, et ce script est le seul chemin entre l'ancienne forme et la nouvelle.

Lire en SQL et non par l'ORM : les champs ont ete retires du modele, l'ORM ne
les connait plus. Les COLONNES, elles, survivent — Odoo ne supprime jamais de
lui-meme une colonne dont le champ a disparu. C'est precisement ce qui rend
cette migration possible, et c'est aussi pourquoi on les supprime a la fin :
des colonnes mortes portant d'anciens statuts induiraient en erreur quiconque
lit la base directement, a commencer par l'outil de BI a venir.
"""
from odoo import SUPERUSER_ID, api

# (colonne besoin, colonne statut, colonne assigne, xmlid du type)
ANCIENS_LIVRABLES = [
    ('besoin_copy', 'statut_copy', 'assignee_copy',
     'his_crm_pipeline.deliverable_type_copy'),
    ('besoin_design', 'statut_design', 'assignee_design',
     'his_crm_pipeline.deliverable_type_design'),
    ('besoin_video', 'statut_video', 'assignee_video',
     'his_crm_pipeline.deliverable_type_video'),
]

COLONNES = [c for triplet in ANCIENS_LIVRABLES for c in triplet[:3]]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Une base ou le module vient d'etre installe n'a jamais eu ces colonnes.
    cr.execute("""
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'crm_lead' AND column_name = ANY(%s)
    """, (COLONNES,))
    presentes = {ligne[0] for ligne in cr.fetchall()}
    if not presentes:
        return

    Livrable = env['his.content.deliverable']
    a_creer = []

    for col_besoin, col_statut, col_assigne, xmlid_type in ANCIENS_LIVRABLES:
        if col_besoin not in presentes:
            continue
        type_livrable = env.ref(xmlid_type, raise_if_not_found=False)
        if not type_livrable:
            continue

        # Le booleen « besoin » decide seul de l'existence de la ligne : c'est
        # lui qui portait la distinction entre « pas encore fait » et « pas
        # concerne ». Un statut renseigne sans besoin coche etait un residu de
        # la valeur par defaut, pas un travail demande.
        cr.execute("""
            SELECT id, %s, %s FROM crm_lead
             WHERE %s IS TRUE
        """ % (col_statut, col_assigne, col_besoin))

        for lead_id, statut, assigne_id in cr.fetchall():
            a_creer.append({
                'lead_id': lead_id,
                'type_id': type_livrable.id,
                'statut': statut or 'a_faire',
                'assignee_id': assigne_id or False,
            })

    if a_creer:
        # Sans le contexte : les dates d'horodatage se posent aux transitions
        # de statut, pas a la reprise. Inventer une date de demarrage pour un
        # travail commence il y a des semaines serait pire que de n'en avoir
        # aucune — les premiers delais mesures seraient faux.
        Livrable.create(a_creer)

    for colonne in presentes:
        cr.execute('ALTER TABLE crm_lead DROP COLUMN "%s"' % colonne)
