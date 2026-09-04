# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Jeu de demonstration des TABLEAUX, de la BOUCLE D'APPEL et du COCKPIT.

    docker compose run --rm -T odoo odoo shell -d <base> --no-http \
        < his_crm_pipeline/docs/seed_demo_tableaux.py

A lancer APRES tools/seed_test_users.py, sur la meme base : les candidatures
sont affectees aux comptes de recette qu'il cree (aicha, rahma, cherif...).
Le scenario qui s'appuie dessus est dans docs/demo_tableaux.md.

Idempotent : un enregistrement dont le nom existe deja n'est pas recree.

Donnees de RECETTE, pas de production : a ne pas semer sur une base reelle.

--------------------------------------------------------------------------
Ce que ce jeu doit rendre demontrable, et pourquoi chaque valeur est la :

  - la BOUCLE D'APPEL : des candidats a 0, 1, 2 et 3 tentatives, pour que la
    pastille grise, la pastille ROUGE (3 tentatives = candidature fantome) et
    l'absence de pastille soient toutes visibles sur un meme ecran ;
  - le GARDE-FOU DU LIEN WhatsApp : un numero volontairement illisible, dont
    la carte n'affiche NI WhatsApp NI telephone ;
  - les MOTIFS DE PERTE : cinq candidatures perdues, chacune avec un motif
    different, sans quoi le donut « Motifs de perte » n'a qu'une part ;
  - l'ACQUISITION : des sources UTM variees, sinon le quatrieme donut est un
    disque d'une seule couleur ;
  - le REVENU ATTENDU : une grille tarifaire, sans laquelle la tuile
    n'apparait pas du tout — c'est voulu, mais indemontrable ;
  - la QUALITE DES DONNEES : une specialite laissee SANS tarif et une
    candidature sans source, pour que la file ait quelque chose a dire.
"""
import datetime

Lead = env['crm.lead']
U = lambda l: env['res.users'].search([('login', '=', l)], limit=1)
X = lambda x: env.ref('his_crm_pipeline.' + x)

ventes, contenu = X('crm_team_ventes'), X('crm_team_contenu')
aicha, rahma, cherif = U('aicha'), U('rahma'), U('cherif')
redac, design_u, video_u, rh = U('contenu'), U('design'), U('video'), U('rh')
specs = env['his.specialite'].search([], limit=4)

Source = env['utm.source']


def source(nom):
    """La source d'acquisition, creee au besoin. Le flux n8n fait de meme."""
    if not nom:
        return False
    trouvee = Source.search([('name', '=', nom)], limit=1)
    return (trouvee or Source.create({'name': nom})).id


def poser(nom, etape, owner, tel, src, tags=(), visite=False, tentatives=0,
          notes=None, equipe=None, motif=None, extra=None):
    """Cree une candidature et la place VRAIMENT ou on la veut.

    team_id et stage_id sont ecrits APRES la creation, jamais dedans : les deux
    sont des champs calcules stockes, et crm.lead les rededuit de `user_id`.
    Les passer a create() les fait silencieusement remplacer par l'equipe par
    defaut du compte qui execute le script — la candidature atterrit alors dans
    « Sales / New » au lieu du pipeline Admissions.
    """
    if Lead.search_count([('name', '=', nom)]) or Lead.with_context(
            active_test=False).search_count([('name', '=', nom)]):
        return Lead.browse()
    lead = Lead.create(dict({
        'name': nom, 'type': 'opportunity', 'contact_name': nom,
        'email_from': '%s@example.com' % nom.split()[0].lower(),
        'phone': tel, 'source_id': source(src),
        'visite_campus_effectuee': visite,
        'tag_ids': [(6, 0, [X(t).id for t in tags])],
        'user_id': owner.id if owner else False,
    }, **(extra or {})))
    lead.sudo().write({
        'team_id': (equipe or ventes).id,
        'stage_id': X(etape).id,
    })
    if notes:
        lead.sudo().write(notes)
    if tentatives:
        # readonly : seule la boucle d'appel l'ecrit normalement.
        lead.sudo().write({'tentatives_appel': tentatives})
    if motif:
        lead.action_set_lost(lost_reason_id=X(motif).id)
    return lead


# ------------------------------------------------------- Grille tarifaire
# Sans elle, la tuile « Revenu attendu » n'existe pas — c'est la regle : un
# chiffre d'affaires invente est pire qu'un chiffre absent. La DERNIERE
# specialite reste volontairement SANS tarif, pour que la file « Qualite des
# donnees » ait une lacune reelle a signaler.
Tarif = env['his.tarif'].sudo() if 'his.tarif' in env else None
if Tarif is not None and specs:
    for i, spec in enumerate(specs):
        if i == len(specs) - 1:
            continue
        if not Tarif.search_count([('specialite_id', '=', spec.id)]):
            Tarif.create({
                'specialite_id': spec.id,
                'frais_inscription': 400000.0 if spec.cycle == 'licence' else 450000.0,
                'frais_scolarite': 900000.0 if spec.cycle == 'licence' else 1200000.0,
            })

# ----------------------------------------------------------- Admissions
NOTES = lambda bac, m, p, i: {
    'specialite_id': specs[i % len(specs)].id if specs else False,
    'bac_moyenne': bac, 'note_math': m, 'note_physique': p,
    'motivation_majeure': "Projet professionnel clair",
    'motivation_his': "Reputation de l'etablissement",
}

adm = [
    # nom, etape, notes, etiquettes, visite, proprietaire, tel, source, tentatives
    ("Yacine Belkacem", 'stage_vente_nouveau',        (16.5, 15.0, 14.0),
     ['tag_bourse_demandee'],     False, None,  '0770110001', "Facebook Ads",     0),
    ("Lina Hamadi",     'stage_vente_pris_en_charge', (14.2, 13.5, 12.0),
     ['tag_relance_prioritaire'], False, aicha, '0770110002', "Instagram",        3),
    ("Sofiane Meziane", 'stage_vente_contact_etabli', (12.8, 11.0, 10.5),
     ['tag_indecis_programme'],   True,  aicha, '0770110003', "Site web",         1),
    ("Nour Cherifi",    'stage_vente_contact_etabli', (11.4, 10.0,  9.5),
     [],                          False, rahma, 'a rappeler chez la tante', None, 2),
    ("Amine Djellal",   'stage_vente_dossier',        (17.1, 16.0, 15.5),
     ['tag_parent_implique'],     True,  aicha, '0770110005', "Salon etudiant",   0),
    ("Rania Bouzid",    'stage_vente_pre_admis',      (10.6,  9.0,  8.5),
     [],                          True,  rahma, '0770110006', "Bouche a oreille", 0),
]
for i, (nom, etape, (bac, m, p), tags, visite, owner, tel, src, tent) in enumerate(adm):
    poser(nom, etape, owner, tel, src, tags, visite, tent, notes=NOTES(bac, m, p, i))

# Les candidatures PERDUES. Cinq motifs differents : sans elles, le donut
# « Motifs de perte » n'a qu'une seule part et ne demontre rien. Quatre sur
# cinq meurent au telephone — c'est ce que disent les chiffres reels.
perdues = [
    ("Karim Saidi",   'stage_vente_pris_en_charge', 'lost_reason_sans_reponse',  4, "Facebook Ads"),
    ("Imane Toubal",  'stage_vente_nouveau',        'lost_reason_fantome',       3, "Instagram"),
    ("Bilal Ferhani", 'stage_vente_contact_etabli', 'lost_reason_trop_cher',     1, "Facebook Ads"),
    ("Sara Mansouri", 'stage_vente_contact_etabli', 'lost_reason_profil_inadapte', 2, "Site web"),
    ("Omar Belhadj",  'stage_vente_pris_en_charge', 'lost_reason_numero_errone', 5, None),
]
for i, (nom, etape, motif, tent, src) in enumerate(perdues):
    poser(nom, etape, aicha if i % 2 else rahma, '0770220%03d' % i, src,
          tentatives=tent, motif=motif, notes=NOTES(12.0 + i, 11.0, 10.0, i))

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
    lead = Lead.create({
        'name': nom, 'type': 'opportunity',
        'departement_demandeur': dep, 'marque': marque,
        'date_deadline': echeance or False,
        'demandeur_id': rh.id, 'user_id': cherif.id,
        'tag_ids': [(6, 0, [X(t).id for t in tags])],
        'deliverable_ids': [
            (0, 0, {'type_id': t.id, 'statut': s,
                    'assignee_id': a.id if a else False})
            for t, s, a in livrables
        ],
    })
    lead.sudo().write({'team_id': contenu.id, 'stage_id': X(etape).id})

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
actives = Lead.search([('team_id', '=', ventes.id)])
perdues_ids = Lead.with_context(active_test=False).search(
    [('team_id', '=', ventes.id), ('active', '=', False)])
print("\n=== JEU DE DEMONSTRATION ===")
print("Admissions actives :", len(actives))
print("Admissions perdues :", len(perdues_ids), "->",
      ", ".join(sorted(set(perdues_ids.mapped('lost_reason_id.name')))))
print("Contenu            :", Lead.search_count([('team_id', '=', contenu.id)]), "demandes")
if Tarif is not None:
    print("Tarifs             :", Tarif.search_count([]), "( 1 specialite laissee sans tarif )")
print("Fiches personne    :", env['his.person'].sudo().search_count([('type_personne', '=', 'candidat')]),
      "(la pre-admission en ouvre une ; le matricule attend l'encaissement)")
print("\nTentatives d'appel :")
for lead in actives.filtered('tentatives_appel').sorted('tentatives_appel'):
    print("  %-20s %s tentative(s)%s" % (
        lead.contact_name, lead.tentatives_appel,
        "  <- pastille ROUGE" if lead.tentatives_appel >= 3 else ""))
print("\nLien WhatsApp absent (numero illisible) :",
      actives.filtered(lambda l: l.phone and not l.whatsapp_url).mapped('contact_name'))
print("\nVues enregistrees :")
for x in ('filter_admissions_sla_retard', 'filter_admissions_candidatures_chaudes',
          'filter_admissions_pre_admis_sans_encaissement', 'filter_admissions_visite_a_programmer',
          'filter_contenu_livrables_en_retard', 'filter_contenu_livrables_non_assignes',
          'filter_contenu_attente_approbation', 'filter_contenu_urgent'):
    f = X(x)
    print("  %-32s -> %s" % (f.name, Lead.search(ast.literal_eval(f.domain)).mapped('name')))
