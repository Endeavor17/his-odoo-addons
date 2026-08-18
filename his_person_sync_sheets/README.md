# his_person_sync_sheets — Import des personnes depuis l'export Google Sheets

Adaptateur qui fait entrer les étudiants (et, plus tard, les autres personnes
non-employées) dans `his_person_core`, à partir de l'export Sales/Admission.

Ne dépend **que** de `his_person_core` — ni de `his_hr_base`, ni de `hr`.

## Les deux règles de gouvernance

> **1. Aucune fusion automatique. Jamais.**
> Au-dessus du seuil de similarité, la ligne est *proposée* à un humain, qui
> confirme ou refuse explicitement. `_find_or_flag_match()` ne rattache rien.
>
> **2. Sens unique, source → `his_person_core`.**
> Ce module n'écrit jamais dans le fichier source.

Ces règles ont le même poids que les règles de valorisation de `his_stock_mdm` :
cette donnée portera à terme des soldes de portefeuille réels. Une fusion à tort,
c'est le solde de quelqu'un attribué à quelqu'un d'autre.

## Où vit l'algorithme de rapprochement

Sur **`his.person`**, pas ici : `his.person._find_or_flag_match()`.

Un futur `his_person_sync_uniflow` doit exécuter exactement le même calcul sans
dépendre de ce module-ci. Un algorithme dupliqué dérive, et deux fiches pour la
même personne, c'est deux portefeuilles. La normalisation des noms
(`normalize_text`) est au même endroit, pour la même raison : deux
normalisations différentes rendent les scores incomparables.

## Déroulé d'une ligne

| Situation | Décision | `match_method` |
|---|---|---|
| Matricule présent, fiche trouvée, type compatible | Mise à jour des champs non identitaires. **Le matricule n'est pas touché.** | `deterministic` |
| Matricule présent, fiche trouvée, **type incompatible** (ex. déjà `employe`) | **Ligne rejetée, conflit signalé.** Ni fusion, ni écrasement. | — |
| Matricule présent, aucune fiche | Création, **matricule repris tel quel** (aucune émission) | `deterministic` |
| Pas de matricule, référence source déjà connue | Mise à jour de la même fiche | `deterministic` |
| Pas de matricule, score ≥ seuil | **Proposé à l'arbitrage.** Rien n'est rattaché tant que l'admin n'a pas tranché. | `probabilistic` après confirmation |
| Pas de matricule, aucune correspondance | Création, matricule neuf émis par la séquence commune | `new` |

### Seuils

| Critère | Poids |
|---|---|
| Nom (latin normalisé, ou arabe exact) | 0,40 |
| Email (institutionnel ou personnel, l'un des deux suffit) | 0,35 |
| Téléphone (8 derniers chiffres) | 0,25 |

**Seuil de proposition : 0,75.** En dessous, la ligne crée une fiche neuve.
Au-dessus, elle est proposée — **jamais liée automatiquement**, quel que soit le
score, y compris à 1,00.

Le nom est comparé sur ses tokens (recouvrement de Jaccard) : une source qui
inverse nom et prénom décrit la même personne. Le téléphone est comparé sur ses
8 derniers chiffres : indicatif et espacement varient d'un export à l'autre.

Ces valeurs sont dans `his.person.MATCH_WEIGHTS` et `his.person.MATCH_THRESHOLD`.
Les changer change le comportement de **tous** les adaptateurs, présents et à
venir : c'est délibéré.

## Matricules préexistants dans la feuille

On ne suppose **pas** que la feuille est vierge de matricules, et on ne la
suppose **pas** faisant autorité non plus. Un matricule déjà présent est repris
tel quel, sans recalcul de clé de contrôle ni reformatage. Un matricule qui
entre en collision avec une fiche existante d'un type incompatible fait l'objet
d'un **arrêt net sur la ligne**, remonté dans le journal : c'est un problème de
donnée source, il s'arbitre à la main.

## Traçabilité

Chaque décision est journalisée dans `his.person.sync.log` — y compris les
conflits et les refus, qui ne sont rattachés à aucune fiche et n'auraient nulle
part où se poser dans un chatter. Les fiches réellement touchées reçoivent
**en plus** leur message de chatter. Chaque ligne du journal porte l'utilisateur
et la date.

## Format de fichier

CSV (délimiteur détecté automatiquement, `,` `;` ou tabulation) ou XLSX si
`openpyxl` est disponible, sinon un message explicite invite à exporter en CSV.
Les intitulés de colonnes sont tolérants (`matricule`, `nom`, `name`, `email`,
`tel`…) : l'export est produit à la main et ses en-têtes varient.

Une ligne sans référence propre reçoit `<fichier>#L<n>` comme référence source,
pour que réimporter le même fichier retombe sur les mêmes fiches.

## Hors périmètre (assumé)

- **Pas d'appel à l'API Google Sheets.** Import manuel par dépôt de fichier
  uniquement, dans cette branche.
- **Pas d'intégration Uniflow.** La couche est conçue pour l'accueillir comme
  second adaptateur — l'algorithme de rapprochement est déjà partagé — mais elle
  n'est pas écrite ici.
- Ni carte RFID, ni portefeuille, ni POS/Restaurant/Copy Center : cf. la section
  « Hors périmètre » de [`his_person_core`](../his_person_core/README.md).

## Lancer les tests

```bash
docker compose run --rm odoo odoo -d <base> -u his_person_sync_sheets \
  --test-enable --test-tags /his_person_sync_sheets --stop-after-init
```
