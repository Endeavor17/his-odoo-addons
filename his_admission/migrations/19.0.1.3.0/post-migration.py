# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Renomme les deux roles du back-office pour ne plus les confondre.

« Admission » et « Finance - Guichet » deviennent « Dossier - Instruction » et
« Dossier - Guichet ». Le CRM porte desormais des roles nommes *Admissions* :
sans ce renommage, l'ecran des droits d'un utilisateur affiche deux entrees
« Admission » qui ne recouvrent pas la meme chose.

Ce script existe parce que les groupes sont charges dans un bloc
`<data noupdate="1">` : une mise a jour du module ne les touche pas. C'est le
meme piege que pour les regles d'enregistrement de `crm`, et il se manifeste de
la meme facon — une base neuve recoit le bon libelle, une base existante garde
l'ancien sans que rien ne signale l'ecart.

Seuls les LIBELLES changent. Les identifiants techniques, les droits et les
membres de ces groupes ne bougent pas.
"""
from odoo import SUPERUSER_ID, api

LIBELLES = {
    'his_admission.group_his_admission': "Dossier - Instruction",
    'his_admission.group_his_finance': "Dossier - Guichet",
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, libelle in LIBELLES.items():
        groupe = env.ref(xmlid, raise_if_not_found=False)
        if groupe:
            groupe.name = libelle
