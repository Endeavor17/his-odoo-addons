# Le sceau, en filigrane

**Le sceau est en place** : `his_seal.png`, la déclinaison bleue, 5740 × 5531 px
à fond transparent. `his_seal_teal.png` est la seconde déclinaison (turquoise),
conservée comme source de la couleur d'accent mais non utilisée à l'écran.

## Ce que le fichier doit être

| | |
|---|---|
| Format | **SVG de préférence**, sinon PNG |
| Fond | **transparent obligatoire** — pas de carré blanc autour du sceau |
| Couleur du tracé | peu importe : la CSS l'aplatit en blanc |
| Taille (PNG) | 1200 px de côté au minimum ; il est affiché jusqu'à 620 px sur grand écran |

Le fond transparent n'est pas une préférence esthétique. `app_grid.scss` applique
`filter: brightness(0) invert(1)` pour transformer le tracé bleu du sceau en
blanc : sur un fichier à fond blanc, ce filtre produirait **un carré blanc** au
milieu de la page d'accueil.

## Le brancher

Une fois le fichier déposé, une seule ligne à changer dans
`../src/scss/tokens.scss` :

```scss
--his-seal: url('/his_web_ui/static/img/his_seal.png');
```

Puis mettre le module à jour pour recompiler les assets :

```bash
docker compose run --rm odoo odoo -d <base> -u his_web_ui --stop-after-init
```

L'intensité se règle avec `--his-seal-opacity` (0.07 par défaut). Au-delà de
0.12 le filigrane commence à concurrencer les noms d'applications ; c'est un
fond, pas une illustration.

## Si le fichier venait à disparaître

`--his-seal` retomberait sur `none` et la page d'accueil afficherait son dégradé
bleu seul : délibéré et fini, pas un écran cassé.

## Le bleu vient du fichier, pas d'une intention

`--his-navy-700` (`#003874`) est la teinte **prélevée** sur le tracé du sceau —
la plus fréquente parmi les pixels opaques non blancs. Toute l'échelle en
dérive en ne bougeant que la luminosité, donc la barre du haut, la page
d'accueil et les survols partagent exactement la teinte (211°) et la saturation
de la marque.

L'accent `--his-teal` (`#00acc0`) est prélevé de la même façon sur
`his_seal_teal.png`. Il ne sert qu'aux repères, jamais à du texte sur la barre
bleue : 4,21:1 y suffit pour un élément d'interface (seuil 3:1) mais pas pour du
texte (seuil 4,5:1).
