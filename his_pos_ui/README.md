# his_pos_ui — Habillage partagé des points de vente

Interface tactile et identité visuelle des trois caisses du Groupe HIS-HTC-IRA :
Cafétéria, Restaurant, Copy Center.

L'idée directrice, énoncée d'abord :

> **L'interface peut être redessinée ; la transaction, non.** Ce module ne
> contient que du CSS et une classe. Il ne patche aucun composant, n'ajoute
> aucun appel serveur et ne touche à aucune ligne de commande. Aucune décision
> d'habillage ne peut donc casser une vente.

---

## 1. Ce que ce module possède, et ce qu'il ne possède pas

| | Propriétaire |
|---|---|
| Thème d'un point de vente, jetons de couleur, taille tactile | **ici** |
| Écran d'entrée : voile, typographie, repli sans image | **ici** |
| Crédits repas, cartes, abonnements | `his_meal_management` — **pas ici** |
| Catalogue, catégories, attributs, gouvernance MDM | `his_stock_mdm` — **pas ici** |
| Composition d'un travail de copie | `his_pos_copy_center` — **pas ici** |

Le module ne connaît ni les copies, ni les repas, ni le café. Il sait à quoi
ressemble une caisse HIS. Les modules de flux en dépendent ; lui ne dépend que
de `point_of_sale`.

## 2. Le thème est une classe, et rien d'autre

`pos.config.his_pos_theme` porte le choix (`copy_center`, `restaurant`,
`cafeteria`). Une héritance de template ajoute la classe correspondante sur la
racine du POS, et **toutes** les règles livrées ici sont portées par elle.

**Vide signifie Odoo standard.** C'est le repli sur lequel repose toute la
conception : une caisse sans thème garde exactement les classes qu'Odoo lui a
données, donc installer ce module sur un registre en service ne peut, au pire,
rien changer du tout.

Le champ est une `Selection` et non un `many2one` vers un modèle de thème,
délibérément. Il y a trois points de vente, ils sont nommés dans le MDM, et
l'apparence de chacun est une feuille de style livrée dans ce dépôt. Une *table*
de thèmes laisserait créer une quatrième ligne à laquelle aucun CSS ne répond :
un écran de configuration qui ment sur ce qu'il configure.

### Le champ arrive au navigateur sans code de chargement

`pos.load.mixin._load_pos_data_read` lit `pos.config` avec une liste de champs
vide, et une liste vide fait lire *tous* les champs. C'est la même raison pour
laquelle `his_meal_management.meal_product_id` est lisible depuis le POS sans
surcharge. Un test épingle ce comportement : s'il change, le thème cesserait
silencieusement d'arriver et chaque caisse redeviendrait standard — une panne
qui se présente comme « le CSS est cassé » et coûte une journée.

**Attention :** cela ne vaut *que* pour `pos.config`. `product.product` publie
une vraie liste blanche (voir `his_pos_copy_center`).

## 3. Réutiliser les variables d'Odoo plutôt que surcharger ses règles

| Variable | Valeur Odoo | Ce qu'on en fait |
|---|---|---|
| `--btn-height-size` | `54px` | passée à `64px` — toute la cible tactile, sans surcharger une seule règle de bouton |
| `--homeMenu-bg-image` | un SVG de `hr_attendance` | pointée sur le fond du point de vente |
| `--homeMenu-bg-color` | `$o-gray-200` | la teinte profonde du thème |

`login_screen.scss` d'Odoo lit déjà ces deux dernières : **le fond d'écran
d'entrée arrive donc sans aucune surcharge de template.** Il ne restait qu'à
poser un voile pour que le texte ait un sol.

Les jetons propres au module (`--his-surface`, `--his-accent`, …) sont des
propriétés personnalisées et non des variables SCSS : Odoo compile son SCSS
avant le nôtre et ses variables sont hors de portée, alors qu'une propriété
personnalisée est résolue au moment du rendu. Une classe sur la racine
re-thématise toute l'application, et les futurs modules Restaurant et Cafétéria
n'auront rien à restyler pour obtenir leur couleur.

## 4. La palette

Les fonds d'écran sont des photographies sombres et chaudes. Derrière une grille
de produits, une photographie détruit la lisibilité de chaque prix affiché — et
une caisse se lit à bout de bras par quelqu'un qui parle en même temps à un
client. Donc :

- **le fond d'écran n'apparaît que sur l'écran d'entrée** ; les écrans de
  travail restent une surface neutre et calme ;
- **le voile est en CSS, pas cuit dans l'image** : le contraste reste réglable
  sans réexporter un fichier ;
- **un accent saturé par point de vente**, dépensé sur l'action principale et
  sur rien d'autre — bleu encre au Copy Center, vert herbe au Restaurant, ambre
  espresso à la Cafétéria. « Le bouton coloré » est toujours l'action voulue.

Les sélecteurs habillés (`.product`, `.orderline`, `.numpad-button`, `.total`)
ont tous été relevés dans les templates de `point_of_sale` avant d'être écrits.
Un thème fait de sélecteurs devinés est du CSS mort qui paraît fonctionner parce
que personne ne remarque que les règles n'ont jamais rien ciblé.

## 5. Les images

`static/src/img/` attend `copy_center.webp`, `restaurant.webp` et
`cafeteria.webp`. **Elles ne sont pas versionnées à ce jour.**

Ce n'est pas une panne : chaque thème définit `--his-wallpaper-color` à côté de
`--his-wallpaper`, donc une image absente retombe sur la teinte profonde du
thème et l'écran d'entrée reste délibéré plutôt que cassé. Voir
`static/src/img/README.md`.

## 6. Écarts assumés

- **Pas de RTL.** `pos_app.scss` d'Odoo impose `direction: ltr` sur `.pos`. Les
  chaînes arabes se traduisent, la mise en page ne se reflète pas. Changer cela
  est un combat à l'échelle d'Odoo, hors sujet ici.
- **Pas de police web.** La pile système est conservée : une caisse n'est pas
  l'endroit où payer un aller-retour réseau au démarrage d'une session.
- **L'apparence n'est pas testée.** Aucune campagne de captures d'écran. Les
  rapports de contraste sont vérifiés à la main contre les jetons.
