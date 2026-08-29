# Le sceau, en filigrane

La page d'accueil (la grille d'applications) attend **un fichier** :

```
his_web_ui/static/img/his_seal.png     (ou .svg)
```

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

## Tant qu'il n'est pas là

`--his-seal` vaut `none`, et la page d'accueil affiche son dégradé bleu seul.
C'est **délibéré et fini**, pas un écran cassé : rien ne signale une image
manquante, et le jour où le fichier arrive il ne fait que s'ajouter.

## Pendant qu'on y est : le bleu

`--his-navy-700` (`#14417f`) est une **lecture** du sceau, faite à l'œil sur une
capture — le fichier n'était pas dans le dépôt. Quand il y sera, prélever la
teinte réelle du tracé et corriger cette seule variable : la barre du haut, la
page d'accueil et les états de survol en découlent tous.
