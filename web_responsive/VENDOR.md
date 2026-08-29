# web_responsive — module tiers, copie versionnee

Ce module n'est **pas** de nous. Il est copie tel quel depuis l'OCA et sert de
lanceur d'applications facon Enterprise : Odoo Community n'en fournit aucun.

| | |
|---|---|
| Origine | https://github.com/OCA/web/tree/19.0/web_responsive |
| Branche | `19.0` |
| Commit | `0b9cd932032275f9b7c68a14ac7cd5a18e8a34b3` (2026-08-28) |
| Version | `19.0.1.1.0` |
| Licence | LGPL-3 |
| Copie le | 2026-08-29 |
| Depend de | `web`, `web_tour`, `mail` (tous standards) |

## Pourquoi copie plutot qu'installe

Le deploiement de ce depot n'a **aucune etape de build** : dev et production
lancent l'image `odoo:19.0` d'origine avec le depot monte sur
`/mnt/extra-addons`, donc mettre en ligne se resume a `git pull` puis
redemarrage. Passer par un `Dockerfile` et `pip` aurait ete plus propre en
matiere de provenance, mais aurait ajoute un mode de panne : un `--build`
oublie laisse Odoo incapable de charger un module que la base declare installe.
Une copie arrive avec le `git pull`, comme le reste.

## Ne pas modifier ces fichiers

Toute correction locale serait perdue a la prochaine mise a jour. Si un
changement est necessaire, il se fait dans un module separe qui surcharge
celui-ci — c'est ce que fait `his_web_ui` pour le comportement d'atterrissage.

## Mettre a jour

```bash
curl -sL https://codeload.github.com/OCA/web/tar.gz/refs/heads/19.0 -o web19.tar.gz
tar -xzf web19.tar.gz --wildcards '*/web_responsive/*'
# remplacer le repertoire, puis mettre a jour le commit et la date ci-dessus
docker compose run --rm odoo odoo -d <base> -u web_responsive --stop-after-init
```

Relire ensuite les verifications du module `his_web_ui`, qui depend du champ
`res.users.is_redirect_home` fourni ici.

## Poids

8,8 Mo, dont **7,2 Mo de GIF de documentation** dans `static/img/` (des captures
animees citees par le README, sans role a l'execution). Ils sont conserves pour
que la copie reste identique a l'amont et que la prochaine mise a jour se lise
comme un diff propre. Les supprimer ferait tomber le module a ~1,6 Mo au prix
d'une divergence permanente avec l'origine.
