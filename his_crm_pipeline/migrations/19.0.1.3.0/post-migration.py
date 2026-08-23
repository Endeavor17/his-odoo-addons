# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Reapplique les regles de visibilite, et leve le verrou qui les figeait.

Le piege : `crm` declare ses regles d'enregistrement dans un bloc
`<data noupdate="1">`. Un module qui redefinit un tel enregistrement ne le
touche donc QU'A L'INSTALLATION — jamais sur `-u`.

Consequence vecue : une base de test reconstruite a chaque fois recevait la
derniere version des regles et tous les tests passaient, pendant que la base
reelle restait figee sur la toute premiere version, installee des semaines plus
tot. Le pire cas : vert partout, faux en production.

Ce script fait deux choses.

1. Il reapplique les domaines courants, pour rattraper les bases deja
   installees.

2. Il retire `noupdate` de ces deux enregistrements, une fois pour toutes. Les
   prochaines editions du XML passeront alors par un simple `-u`, sans nouveau
   script de migration. C'est le piege lui-meme qu'on desamorce, pas seulement
   son effet du jour.

Contrepartie assumee : ces regles redeviennent modifiables par une mise a jour
d'Odoo. Comme `crm` se charge avant `his_crm_pipeline`, une mise a jour globale
les remet au domaine natif puis nos donnees les resserrent a nouveau dans la
meme passe. Seul un `-u crm` isole les laisserait larges — ce qui ne se fait
pas.
"""
from odoo import SUPERUSER_ID, api

# Copie conforme de security/his_crm_security.xml. Les deux doivent rester
# identiques : le XML sert a l'installation, ce script aux bases existantes.
DOMAINES = {
    'crm.crm_rule_all_lead': (
        "['|', '|', ('team_id', '=', False), "
        "('team_id', 'in', user.crm_team_ids.ids), "
        "('stage_id.team_ids', 'in', user.crm_team_ids.ids)]"
    ),
    'crm.crm_rule_personal_lead': (
        "['&', '|', ('team_id', '=', False), "
        "('team_id', 'in', user.crm_team_ids.ids), "
        "'|', ('user_id', '=', user.id), ('user_id', '=', False)]"
    ),
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    for xmlid, domaine in DOMAINES.items():
        regle = env.ref(xmlid, raise_if_not_found=False)
        if regle:
            regle.domain_force = domaine

    env['ir.model.data'].search([
        ('model', '=', 'ir.rule'),
        ('module', '=', 'crm'),
        ('name', 'in', [x.split('.', 1)[1] for x in DOMAINES]),
    ]).noupdate = False
