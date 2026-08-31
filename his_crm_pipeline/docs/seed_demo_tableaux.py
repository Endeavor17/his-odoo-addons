# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Jeu de demonstration des TABLEAUX (kanban, etiquettes, vues enregistrees).

    docker compose run --rm -T odoo odoo shell -d <base> --no-http \
        < his_crm_pipeline/docs/seed_demo_tableaux.py

A lancer APRES tools/seed_test_users.py, sur la meme base : les candidatures
sont affectees aux comptes de recette qu'il cree (aicha, rahma, cherif...).
Le scenario qui s'appuie dessus est dans docs/demo_tableaux.md.

Idempotent : un enregistrement dont le nom existe deja n'est pas recree.

Donnees de RECETTE, pas de production : a ne pas semer sur une base reelle.
"""
import datetime

Lead = env['crm.lead']
U = lambda l: env['res.users'].search([('login', '=', l)], limit=1)
X = lambda x: env.ref('his_crm_pipeline.' + x)

ventes, contenu = X('crm_team_ventes'), X('crm_team_contenu')
aicha, rahma, cherif = U('aicha'), U('rahma'), U('cherif')
redac, design_u, video_u, rh = U('contenu'), U('design'), U('video'), U('rh')
specs = env['his.specialite'].search([], limit=4)

# ----------------------------------------------------------- Admissions
adm = [
    # nom, etape, (bac, math, phys), etiquettes, visite, proprietaire
    ("Yacine Belkacem", 'stage_vente_nouveau',        (16.5, 15.0, 14.0), ['tag_bourse_demandee'],     False, None),
    ("Lina Hamadi",     'stage_vente_pris_en_charge', (14.2, 13.5, 12.0), ['tag_relance_prioritaire'], False, aicha),
    ("Sofiane Meziane", 'stage_vente_contact_etabli', (12.8, 11.0, 10.5), ['tag_indecis_programme'],   True,  aicha),
    ("Nour Cherifi",    'stage_vente_contact_etabli', (11.4, 10.0,  9.5), [],                          False, rahma),
    ("Amine Djellal",   'stage_vente_dossier',        (17.1, 16.0, 15.5), ['tag_parent_implique'],     True,  aicha),
    ("Rania Bouzid",    'stage_vente_pre_admis',      (10.6,  9.0,  8.5), [],                          True,  rahma),
]
for i, (nom, etape, (bac, m, p), tags, visite, owner) in enumerate(adm):
    if Lead.search_count([('name', '=', nom)]):
        continue
    lead = Lead.create({
        'name': nom, 'type': 'opportunity', 'team_id': ventes.id,
        'stage_id': X(etape).id, 'contact_name': nom,
        'email_from': '%s@example.com' % nom.split()[0].lower(),
        'phone': '0770%06d' % (110000 + i),
        'visite_campus_effectuee': visite,
        'tag_ids': [(6, 0, [X(t).id for t in tags])],
    })
    lead.sudo().write({
        'specialite_id': specs[i % len(specs)].id if specs else False,
        'bac_moyenne': bac, 'note_math': m, 'note_physique': p,
        'motivation_majeure': "Projet professionnel clair",
        'motivation_his': "Reputation de l'etablissement",
        # « Nouveau (score) » est la file d'attente : elle reste sans commercial.
        'user_id': owner.id if owner else False,
    })

# ------------------------------------------------------------- Contenu
copy, dsg, vid = (X('deliverable_type_%s' % c) for c in ('copy', 'design', 'video'))
hier = datetime.date.today() - datetime.timedelta(days=3)
con = [
    # nom, departement, marque, etape, [(type, statut, assigne)], etiquettes, echeance
    ("Campagne rentree 2026", 'marketing', 'his', 'stage_contenu_demande',
     [(copy, 'a_faire', None), (dsg, 'a_faire', None)], ['tag_urgent'], False),
    ("Video temoignage master", 'pedagogie', 'htc', 'stage_contenu_production',
     [(vid, 'en_cours', video_u), (copy, 'approuve', redac)], ['tag_reseaux_sociaux'], hier),
    ("Refonte page filieres", 'marketing', 'ira', 'stage_contenu_production',
     [(copy, 'approuve', redac), (dsg, 'approuve', design_u)], ['tag_site_web'], False),
    ("Affiche journee portes ouvertes", 'hr', 'his', 'stage_contenu_approbation',
     [(dsg, 'approuve', design_u)], ['tag_evenement'], False),
]
for nom, dep, marque, etape, livrables, tags, echeance in con:
    if Lead.search_count([('name', '=', nom)]):
        continue
    Lead.create({
        'name': nom, 'type': 'opportunity', 'team_id': contenu.id,
        'stage_id': X(etape).id, 'departement_demandeur': dep, 'marque': marque,
        'date_deadline': echeance or False,
        'demandeur_id': rh.id, 'user_id': cherif.id,
        'tag_ids': [(6, 0, [X(t).id for t in tags])],
        'deliverable_ids': [
            (0, 0, {'type_id': t.id, 'statut': s,
                    'assignee_id': a.id if a else False})
            for t, s, a in livrables
        ],
    })

# --------------------------------------------------------- Antidatage
# APRES tout travail ORM et un flush explicite : un flush ulterieur reecrirait
# la valeur avec celle que le cache ORM porte encore.
env.flush_all()
env.cr.execute("UPDATE crm_lead SET date_last_stage_update = now() - interval '9 hours'"
               " WHERE name = 'Lina Hamadi'")
env.cr.execute("UPDATE crm_lead SET date_last_stage_update = now() - interval '12 days'"
               " WHERE name = 'Rania Bouzid'")
env.cr.commit()
env.invalidate_all()

import ast
print("\n=== JEU DE DEMONSTRATION DES TABLEAUX ===")
print("Admissions :", Lead.search_count([('team_id', '=', ventes.id)]), "candidatures")
print("Contenu    :", Lead.search_count([('team_id', '=', contenu.id)]), "demandes")
print("\nVues enregistrees :")
for x in ('filter_admissions_sla_retard', 'filter_admissions_candidatures_chaudes',
          'filter_admissions_pre_admis_sans_encaissement', 'filter_admissions_visite_a_programmer',
          'filter_contenu_livrables_en_retard', 'filter_contenu_livrables_non_assignes',
          'filter_contenu_attente_approbation', 'filter_contenu_urgent'):
    f = X(x)
    print("  %-32s -> %s" % (f.name, Lead.search(ast.literal_eval(f.domain)).mapped('name')))
