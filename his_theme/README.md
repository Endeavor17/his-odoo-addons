# HIS Theme

Seul propriétaire des jetons de design du Groupe : couleurs, polices, et
bientôt rayons et ombres. Aucun autre module n'écrit une valeur de marque.

## Où vit quoi

| Fichier | Rôle |
|---|---|
| `static/src/scss/primary_variables.scss` | **Les valeurs**, une seule fois, en variables SCSS `$his-*`. Ajouté en tête de `web._assets_primary_variables`, que compilent le client web, la caisse (`point_of_sale.base_app`) et la page de connexion (`web.assets_frontend`). Odoo en dérive ses propres couleurs (`$o-community-color`…) et ses polices. |
| `static/src/scss/tokens.scss` | **La publication** : les `@font-face` et les propriétés CSS `--his-*`, plus les noms limités à `.his-pos` que lisent `his_pos_ui` et la boîte « Travail de copie ». Listé dans les trois bundles : la caisse reçoit les jetons sans qu'aucune valeur soit recopiée. |
| `static/src/scss/pos.scss` | Le bandeau d'une caisse sans thème `his_pos_ui`, et la forme des deux boutons d'action de la caisse. |
| `static/src/fonts/` | Les polices, servies par le module lui-même. |

Un module qui veut une couleur lit `var(--his-…)`. S'il lui faut un nom qui
n'existe pas, il s'ajoute ici, jamais dans le module.

## Décisions

- **Bleu sceau `#003874`** pour l'interface et pour l'action qui termine une
  tâche (`--his-action` : Enregistrer, Paiement, Valider, Servir le repas).
  Blanc sur ce bleu : 11,55:1.
- **Turquoise sceau `#00acc0`** pour les repères seulement (onglet actif,
  focus). 2,74:1 sur blanc, 4,21:1 sur le bleu : jamais du texte, jamais seul
  porteur de sens sur fond clair.
- **Turquoise caisse `#006883`** pour les caisses (décision acceptée : back-office
  bleu, caisses turquoise). Blanc dessus : 6,35:1.
- **L'or** vient de la charte du site his.edu.dz, pas du sceau. Il reste un jeton
  hérité, lu par les tableaux de bord de maintenance et la carte repas imprimée.
  L'action principale est bleue (décision du 2026-10-15).
- **Une famille par écriture** : Figtree pour le latin, Readex Pro pour les seuls
  glyphes arabes (son `unicode-range` le tient à l'écart de tout caractère latin),
  IBM Plex Mono pour les codes et les montants.

## Polices embarquées

Aucune police n'est chargée depuis un CDN au moment de l'exécution.

| Fichier | Famille | Version | Source | Licence |
|---|---|---|---|---|
| `figtree-latin-wght-normal.woff2` (20 Ko, variable 300–900) | Figtree | Fontsource 5.3.0 | [erikdkennedy/figtree](https://github.com/erikdkennedy/figtree), paquet npm `@fontsource-variable/figtree` | SIL OFL 1.1, `OFL-Figtree.txt` |
| `readex-pro-arabic-wght-normal.woff2` (23 Ko, variable 160–700, sous-ensemble arabe) | Readex Pro | Fontsource 5.3.0 | [ThomasJockin/readexpro](https://github.com/ThomasJockin/readexpro), paquet npm `@fontsource-variable/readex-pro` | SIL OFL 1.1, `OFL-ReadexPro.txt` |
| `ibm-plex-mono-latin-{400,500,600}-normal.woff2` (15 Ko chacun) | IBM Plex Mono | Fontsource 5.3.0 | [IBM/plex](https://github.com/IBM/plex), paquet npm `@fontsource/ibm-plex-mono` | SIL OFL 1.1, `OFL-IBMPlexMono.txt`. Nom réservé par IBM : fichiers utilisés sans modification. |

Les fichiers sont ceux des paquets, inchangés. Pour une mise à jour : `npm pack`
du paquet, puis copier le fichier `files/…woff2` correspondant et la `LICENSE`.

## Ce qui n'est pas couvert

Les rapports PDF (`web.report_layout`, wkhtmltopdf) ne chargent pas ce bundle :
la carte repas imprimée nomme Figtree dans son style et retombe sur la police
système, comme avant. Le WebKit de wkhtmltopdf 0.12 ne lit pas le woff2.
