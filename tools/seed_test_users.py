# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Cree un compte par ROLE, pour derouler les deux processus de bout en bout.

    docker compose run --rm -T odoo odoo shell -d <base> --no-http < tools/seed_test_users.py

Idempotent : relancer ne cree pas de doublon, mais REPOSE le role et le mot de
passe. C'est voulu — c'est ce qui permet de rattraper une base ou les comptes
ont ete crees avant que les roles existent.

Comptes de RECETTE, pas de production. Ils partagent un mot de passe connu et
portent des adresses @example.com : a ne pas semer sur une base reelle.

Aucune fiche employe n'est creee, deliberement. his_hr_base frappe un matricule
institutionnel a chaque embauche — un matricule est un identifiant a vie, et des
comptes de test en consommeraient autant pour toujours. Derouler les processus
n'en a pas besoin : seuls les roles et les equipes comptent.
"""
MOT_DE_PASSE = 'his2026'

# (login, nom, roles, equipes, responsable de l'equipe)
#
# Un compte porte un role par ECHELLE, pas plus. Les roles d'une meme echelle
# se contiennent — le Responsable contient le Conseiller, qui contient
# l'Acquisition — donc en empiler deux ne servirait a rien et rendrait
# illisible ce que la personne peut vraiment faire. En revanche un compte peut
# porter un role de chaque echelle, ce que le Marketing illustre.
COMPTES = [
    # --- Processus Admissions ---
    # Le Marketing est present des DEUX cotes : il capte les candidatures et il
    # produit le contenu. C'etait son double role dans GoHighLevel. Deux roles
    # sur un compte, issus de deux echelles distinctes — c'est exactement ce que
    # deux privileges separes permettent d'exprimer.
    ('marketing', "Marketing (acquisition et contenu)",
     ['his_crm_pipeline.group_admissions_acquisition',
      'his_crm_pipeline.group_contenu_production'],
     ['his_crm_pipeline.crm_team_ventes', 'his_crm_pipeline.crm_team_contenu'], None),

    ('asma', "Asma (responsable admissions)",
     ['his_crm_pipeline.group_admissions_responsable'],
     ['his_crm_pipeline.crm_team_ventes'], 'his_crm_pipeline.crm_team_ventes'),

    ('aicha', "Aicha (conseillere)",
     ['his_crm_pipeline.group_admissions_conseiller'],
     ['his_crm_pipeline.crm_team_ventes'], None),

    ('rahma', "Rahma (conseillere)",
     ['his_crm_pipeline.group_admissions_conseiller'],
     ['his_crm_pipeline.crm_team_ventes'], None),

    ('orientation', "Cellule d'Orientation",
     ['his_crm_pipeline.group_admissions_orientation'],
     ['his_crm_pipeline.crm_team_orientation'], 'his_crm_pipeline.crm_team_orientation'),

    # --- Back-office et guichet ---
    ('admission', "Admission (instruction du dossier)",
     ['his_admission.group_his_admission'], [], None),

    ('finance', "Finance (guichet)",
     ['his_admission.group_his_finance'], [], None),

    # --- Processus Production Contenu ---
    # Le pool de production tel que le BPMN le decrit : un redacteur, un
    # designer, un video, un prioriseur, un approbateur. Des comptes distincts
    # et non un seul : une demande porte trois livrables qui avancent en
    # parallele, et c'est ce qu'une demonstration doit montrer.
    ('cherif', "Cherif (priorisation)",
     ['his_crm_pipeline.group_contenu_priorisation'],
     ['his_crm_pipeline.crm_team_contenu'], 'his_crm_pipeline.crm_team_contenu'),

    ('contenu', "Redaction (copywriting)",
     ['his_crm_pipeline.group_contenu_production'],
     ['his_crm_pipeline.crm_team_contenu'], None),

    ('design', "Design",
     ['his_crm_pipeline.group_contenu_production'],
     ['his_crm_pipeline.crm_team_contenu'], None),

    ('video', "Video",
     ['his_crm_pipeline.group_contenu_production'],
     ['his_crm_pipeline.crm_team_contenu'], None),

    ('direction', "Direction (approbation finale)",
     ['his_crm_pipeline.group_contenu_approbation'],
     ['his_crm_pipeline.crm_team_contenu'], None),

    # Un demandeur venu d'ailleurs : ni membre de l'equipe Contenu, ni
    # commercial. Il depose une demande et ne voit QUE les siennes.
    ('rh', "Ressources humaines (demandeur)",
     ['his_crm_pipeline.group_contenu_demandeur'], [], None),
]

# Tous les roles du depot. Un compte reseme est d'abord debarrasse de ceux
# qu'il ne doit plus porter : ajouter le bon groupe ne suffirait pas, l'ancien
# resterait et le plus large gagnerait.
TOUS_LES_ROLES = [
    'his_crm_pipeline.group_admissions_acquisition',
    'his_crm_pipeline.group_admissions_conseiller',
    'his_crm_pipeline.group_admissions_responsable',
    'his_crm_pipeline.group_admissions_orientation',
    'his_crm_pipeline.group_contenu_demandeur',
    'his_crm_pipeline.group_contenu_production',
    'his_crm_pipeline.group_contenu_priorisation',
    'his_crm_pipeline.group_contenu_approbation',
    'his_admission.group_his_admission',
    'his_admission.group_his_finance',
    # Les groupes commerciaux natifs : les roles Admissions les impliquent,
    # personne ne doit les porter en direct.
    'sales_team.group_sale_salesman',
    'sales_team.group_sale_salesman_all_leads',
    'sales_team.group_sale_manager',
]

Users = env['res.users']
Membre = env['crm.team.member']

a_retirer = [env.ref(x).id for x in TOUS_LES_ROLES]

for login, nom, roles, equipes, responsable_de in COMPTES:
    user = Users.with_context(active_test=False).search([('login', '=', login)], limit=1)
    if not user:
        user = Users.create({
            'name': nom, 'login': login, 'email': '%s@example.com' % login,
            'group_ids': [(6, 0, [env.ref('base.group_user').id])],
        })
    user.write({'group_ids': [(3, g) for g in a_retirer]})
    user.write({'group_ids': [(4, env.ref('base.group_user').id)]
                              + [(4, env.ref(r).id) for r in roles]})
    user.password = MOT_DE_PASSE

    for equipe_xmlid in equipes:
        equipe = env.ref(equipe_xmlid)
        if not Membre.search_count([
            ('crm_team_id', '=', equipe.id), ('user_id', '=', user.id),
        ]):
            Membre.create({'crm_team_id': equipe.id, 'user_id': user.id})

    # Sans responsable d'equipe, aucune relance SLA n'est posee.
    if responsable_de:
        equipe = env.ref(responsable_de)
        equipe.user_id = user

env.cr.commit()

print("\n=== COMPTES DE RECETTE (mot de passe : %s) ===\n" % MOT_DE_PASSE)
print("  %-12s %-34s %-24s %s" % ("LOGIN", "NOM", "ROLE", "EQUIPES"))
for login, nom, roles, _e, _r in COMPTES:
    user = Users.search([('login', '=', login)], limit=1)
    if not user:
        continue
    print("  %-12s %-34s %-24s %s" % (
        user.login, user.name, " + ".join(env.ref(r).name for r in roles),
        ", ".join(user.crm_team_ids.mapped('name')) or "-",
    ))
