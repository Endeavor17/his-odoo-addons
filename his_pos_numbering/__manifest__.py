# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "POS - Numero d'operation lisible",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "summary": "Les onglets de commande affichent 1, 2, 3 au lieu de 5001 ou 4001",
    "description": """
En Odoo 19, l'onglet d'une commande affiche `tracking_number`, que le coeur
compose ainsi (pos_store.js:1432, et pos_config.py:216 cote serveur) :

    identifiant_de_peripherique + (numero % 1000) sur trois chiffres

D'ou « 5001 », « 4001 », « 6003 ». Le chiffre de tete n'est PAS la caisse :
c'est un compteur de NAVIGATEURS enregistres pour cette caisse
(`pos.config.device_seq_id`), donc il change des qu'on vide les donnees de
site d'une caisse, et la meme caisse passe de 2xxx a 6xxx sans que rien de
metier ait bouge. Ce compteur n'a aucun rembourrage : au dixieme navigateur
l'affichage passerait a « 10001 ».

Ce module affiche a la place `sequence_number`, que le coeur pose deja sur
chaque commande depuis `pos.config.order_seq_id` : une sequence PAR CAISSE,
en `no_gap`, qui ne se reinitialise jamais. C'est le 1, 2, 3 attendu, et il
existait deja — rien n'est invente ici.

Portee volontairement minuscule :
  - `tracking_number` n'est PAS touche. Il continue d'alimenter les
    remboursements, les tickets et pos_self_order exactement comme avant.
  - aucun champ, aucune vue, aucun appel serveur, aucune migration.
  - deux extensions JS seulement : l'affichage du nom de la commande, et la
    recherche de l'ecran des tickets qui doit chercher ce qui est affiche.

Pourquoi un module separe et non `his_pos_ui` : celui-ci promet dans son
README de ne contenir que du CSS et une classe, sans patcher aucun composant.
C'est cette promesse qui le rend sans danger sur une caisse qui encaisse deja.
La numerotation est un comportement : elle vit donc chez elle.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": [
        "point_of_sale",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "his_pos_numbering/static/src/app/*.js",
        ],
    },
    "installable": True,
}
