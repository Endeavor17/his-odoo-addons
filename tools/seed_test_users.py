# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Cree un compte par role du pipeline, pour derouler le parcours de bout en bout.

    docker compose run --rm -T odoo odoo shell -d <base> --no-http < tools/seed_test_users.py

Idempotent : relancer ne cree pas de doublon, mais REPOSE le mot de passe.

Comptes de RECETTE, pas de production. Ils partagent un mot de passe connu et
portent des adresses @example.com : a ne pas semer sur une base reelle.

Aucune fiche employe n'est creee, deliberement. his_hr_base frappe un matricule
institutionnel a chaque embauche — un matricule est un identifiant a vie, et
cinq comptes de test en consommeraient cinq pour toujours. Derouler le pipeline
n'en a pas besoin : seuls les groupes et les equipes comptent.
"""
MOT_DE_PASSE = 'his2026'

# (login, nom, groupes, equipes, responsable de l'equipe)
ROLES = [
    ('marketing', "Marketing (capture et contenu)",
     ['sales_team.group_sale_salesman_all_leads'],
     ['his_crm_pipeline.crm_team_ventes', 'his_crm_pipeline.crm_team_contenu'], None),

    ('orientation', "Cellule d'Orientation",
     ['sales_team.group_sale_salesman_all_leads'],
     ['his_crm_pipeline.crm_team_orientation'], 'his_crm_pipeline.crm_team_orientation'),

    # Le pool de production, tel que le BPMN le decrit : un redacteur, un
    # designer, un video, un approbateur final. Quatre comptes distincts et non
    # un seul : une demande de contenu porte trois livrables qui avancent en
    # parallele, et c'est precisement ce qu'une demonstration doit montrer.
    ('contenu', "Redaction (copywriting)",
     ['sales_team.group_sale_salesman_all_leads'],
     ['his_crm_pipeline.crm_team_contenu'], 'his_crm_pipeline.crm_team_contenu'),

    ('design', "Design",
     ['sales_team.group_sale_salesman_all_leads'],
     ['his_crm_pipeline.crm_team_contenu'], None),

    ('video', "Video",
     ['sales_team.group_sale_salesman_all_leads'],
     ['his_crm_pipeline.crm_team_contenu'], None),

    ('direction', "Direction (approbation finale)",
     ['sales_team.group_sale_salesman_all_leads'],
     ['his_crm_pipeline.crm_team_contenu'], None),

    ('admission', "Admission (back-office)",
     ['his_admission.group_his_admission'], [], None),

    ('finance', "Finance (guichet)",
     ['his_admission.group_his_finance'], [], None),
]

# Les trois conseilleres existent deja (his_crm_pipeline), sans mot de passe.
# Leur groupe est REPOSE ici : sur une base ou elles ont ete creees avant que
# la distinction manager / conseillere existe, les donnees du module ne les
# corrigent pas (noupdate).
EXISTANTS = {
    'asma': 'sales_team.group_sale_salesman_all_leads',
    'aicha': 'sales_team.group_sale_salesman',
    'rahma': 'sales_team.group_sale_salesman',
}

Users = env['res.users']
Membre = env['crm.team.member']


def groupe(xmlid):
    return env.ref(xmlid).id


for login, nom, groupes, equipes, responsable_de in ROLES:
    user = Users.with_context(active_test=False).search([('login', '=', login)], limit=1)
    ids = [groupe('base.group_user')] + [groupe(g) for g in groupes]
    if user:
        user.write({'group_ids': [(4, g) for g in ids]})
    else:
        user = Users.create({
            'name': nom, 'login': login, 'email': '%s@example.com' % login,
            'group_ids': [(6, 0, ids)],
        })
    user.password = MOT_DE_PASSE

    for equipe_xmlid in equipes:
        equipe = env.ref(equipe_xmlid)
        if not Membre.search_count([
            ('crm_team_id', '=', equipe.id), ('user_id', '=', user.id),
        ]):
            Membre.create({'crm_team_id': equipe.id, 'user_id': user.id})

    # Sans responsable d'equipe, aucune relance SLA n'est posee : une equipe de
    # test doit en avoir un, sinon le pas 3 du parcours ne montre rien.
    if responsable_de:
        equipe = env.ref(responsable_de)
        if not equipe.user_id:
            equipe.user_id = user

tous_leads = groupe('sales_team.group_sale_salesman_all_leads')
for login, groupe_voulu in EXISTANTS.items():
    user = Users.search([('login', '=', login)], limit=1)
    if not user:
        continue
    voulu = groupe(groupe_voulu)
    # Retirer « Tous les leads » quand il n'est pas voulu : l'ajout seul ne
    # suffirait pas, le groupe large l'emporterait.
    if voulu != tous_leads:
        user.write({'group_ids': [(3, tous_leads)]})
    user.write({'group_ids': [(4, voulu)]})
    user.password = MOT_DE_PASSE

env.cr.commit()

print("\n=== COMPTES DE RECETTE (mot de passe : %s) ===" % MOT_DE_PASSE)
logins = list(EXISTANTS) + [r[0] for r in ROLES]
for user in Users.search([('login', 'in', logins)], order='login'):
    equipes = ", ".join(user.crm_team_ids.mapped('name')) or "-"
    portee = (
        "tous les leads" if user.has_group('sales_team.group_sale_salesman_all_leads')
        else "mes leads" if user.has_group('sales_team.group_sale_salesman')
        else "-"
    )
    print("  %-12s %-32s portee: %-14s equipes: %s" % (
        user.login, user.name, portee, equipes))
