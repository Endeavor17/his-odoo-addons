# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Ce qu'un fichier de donnees ne peut pas faire.

Odoo declare ses trois motifs de perte anglais avec `noupdate="1"` sur leur
propre `ir.model.data`. Ce drapeau appartient a l'ENREGISTREMENT, pas au module
qui l'ecrit : tant qu'il est pose, aucun fichier XML — le notre compris — ne
peut les modifier. Un `<record id="crm.lost_reason_1">` s'installe sans bruit et
ne fait rien du tout, ce qui est exactement le genre de panne silencieuse que ce
depot cherche a eviter.

D'ou du code imperatif, appele des deux cotes : a l'installation (post_init_hook)
et a la mise a jour (migrations/19.0.3.3.0). Une seule fonction pour les deux,
sinon les deux chemins finissent par diverger.
"""
# « Too expensive » double « Frais trop eleves », en anglais. « Not enough
# stock » n'a aucun sens pour une candidature. Un conseiller voyait donc deux
# entrees pour la meme idee, dans deux langues — le compartiment coupe en deux
# qu'on venait de fusionner pour « Sans reponse », reintroduit par le haut.
MOTIFS_NATIFS = ('crm.lost_reason_1', 'crm.lost_reason_2', 'crm.lost_reason_3')


def desactiver_motifs_natifs(env):
    """Retire les motifs anglais d'Odoo de la liste de selection.

    DESACTIVES, jamais supprimes : `crm.lead.lost_reason_id` est en
    `ondelete='restrict'`, et l'un d'eux porte deja un lead sur la base de
    recette. Un motif desactive disparait de la liste sans rien casser de
    l'historique qui le reference.
    """
    for xmlid in MOTIFS_NATIFS:
        motif = env.ref(xmlid, raise_if_not_found=False)
        if motif and motif.active:
            motif.active = False


def post_init_hook(env):
    desactiver_motifs_natifs(env)
