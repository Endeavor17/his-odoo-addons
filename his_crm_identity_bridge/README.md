# his_crm_identity_bridge — du lead CRM à la fiche personne

Pont entre le pipeline Admissions
([`his_crm_pipeline`](../his_crm_pipeline/)) et le référentiel Identité
([`his_person_core`](../his_person_core/)).

Module volontairement **petit et isolé**. `his_crm_pipeline` s'installe et
fonctionne sans lui : un CRM qui marche ne doit pas dépendre du référentiel
d'identité pour ouvrir un pipeline.

**Aucune dépendance à `hr` ni à `his_hr_base`** — un candidat n'est pas un
`hr.employee`. Même discipline que `his_person_sync_sheets`.

## Ce que ce module ne possède pas

Trois choses, et c'est délibéré :

| Il ne possède pas | Qui possède |
|---|---|
| L'algorithme de rapprochement | `his.person._find_or_flag_match` |
| L'émission du matricule | La séquence unique de `his_person_core` |
| Les transitions d'engagement au-delà de `prospect` | Finance/Admission, hors de ce dépôt |

Réimplémenter le rapprochement ici aurait produit deux algorithmes divergents
pour la même question — celui de l'import Google Sheets et celui du CRM — et le
jour où le seuil bouge, un seul des deux aurait suivi.

## Le déclencheur

Quand un lead de l'équipe **Ventes / Admissions** entre en étape **« Contact
établi »** et ne porte pas encore de fiche personne.

**Cette étape est une proposition, pas une décision** (hypothèse A1). « Premier
contact » a été lu au sens le plus littéral : le conseiller a effectivement
parlé au candidat, pas seulement reçu son lead. La Direction n'a pas tranché.

Elle est donc lue depuis un paramètre système, jamais écrite en dur :

```
his_crm.identity_trigger_stage_xmlid = his_crm_pipeline.stage_vente_contact_etabli
```

Changer d'avis est un changement de paramètre (Paramètres → Technique →
Paramètres système), pas une modification de code. Un test le vérifie.

Ce n'est **pas** l'étape « Pré-admis » : celle-ci déclenche le paiement des
frais d'inscription, qui appartient à Finance/Admission.

## Ce qui se passe

1. Le lead est traduit en vocabulaire du référentiel : nom, **`email_personnel`**
   — jamais institutionnel, le candidat n'a aucun compte à ce stade —, téléphone,
   `source_system = 'odoo_crm'`, `external_ref` = l'ID du lead.
2. `his.person._find_or_flag_match()` tranche.
3. **Aucune correspondance** → fiche créée en `type_personne='candidat'`,
   matricule frappé par la séquence partagée, plus un `his.engagement` à
   `prospect`.
4. **Correspondance déterministe** → rattachement à la fiche existante.
5. **Correspondance probable** → **rien n'est rattaché**. La fiche proposée
   s'affiche sur le lead avec son score et deux boutons ; une activité est posée
   sur le conseiller. Un humain tranche, jamais le système. Même geste que
   l'import Google Sheets.

### `source_system = 'odoo_crm'` sans toucher au socle

La valeur est ajoutée par `selection_add` depuis ce module. `his_person_core`
est déjà fusionné et sert trois autres modules : l'étendre depuis ici le laisse
intact et fait apparaître la valeur exactement là où elle a un sens.

À la désinstallation du pont, les fiches nées du CRM basculent en « Saisie
manuelle » — `source_system` est requis et sans défaut, `set default` y
laisserait un champ obligatoire vide. Leur provenance reste lisible dans
`external_ref` et dans le chatter.

### Un seul contact, jamais deux

`his.person` délègue à `res.partner`. Si le lead porte déjà un contact, ce
contact est **repris** au lieu d'en créer un second — sinon le même humain se
retrouverait avec deux fiches contact, l'une portant l'historique commercial,
l'autre le matricule. La contrainte `unique(partner_id)` du socle interdit de
rattacher un contact déjà porteur d'une fiche : on le vérifie avant. Un test
compte les `res.partner` avant et après.

### Repasser par l'étape ne duplique rien

Trois garde-fous, dans cet ordre :

1. `his_person_id` déjà posé → on ne fait rien ;
2. une proposition en attente → on n'en refait pas une seconde ;
3. même sans ces deux-là, `_find_or_flag_match` retrouve la fiche de façon
   déterministe sur `(external_ref, source_system)` — la clé que
   `his_person_core` pose déjà pour que rejouer un import ne duplique rien.

## Hors périmètre (assumé)

- **Toute transition d'engagement au-delà de `prospect`.** `candidat_soumis` et
  la suite dépendent de la confirmation du paiement des frais d'inscription non
  remboursables : c'est Finance/Admission, et aucun code de ce dépôt ne le fait
  aujourd'hui.
- Aucune écriture retour du référentiel vers le lead : sens unique, CRM →
  Identité.
- Aucune fusion automatique, quel que soit le score.

## Installation

```bash
docker compose run --rm odoo odoo -d <base> -i his_crm_identity_bridge --stop-after-init
```

## Lancer les tests

```bash
docker compose stop odoo
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' docker compose run --rm odoo odoo \
  -d <base_test> --without-demo=all -i his_crm_identity_bridge \
  --test-enable --test-tags /his_crm_identity_bridge --stop-after-init
```
