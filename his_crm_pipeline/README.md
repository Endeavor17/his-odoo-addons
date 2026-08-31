# his_crm_pipeline — CRM Ventes/Admissions et Production Contenu

Remplace **GoHighLevel** par le CRM natif d'Odoo 19. L'abonnement SaaS payait
essentiellement un pipeline, une file d'attente et un scoring : Odoo sait déjà
faire les trois. Ce module ne réécrit donc rien du CRM, il l'équipe.

Deux processus **sans aucun rapport** cohabitent ici : le parcours candidat
(Ventes/Admissions) et la production de contenu (Marketing). Ils partagent
`crm.lead` et sont séparés par équipe.

## Pourquoi un seul modèle pour deux processus

Une demande de contenu n'est pas une opportunité commerciale. La tentation était
de lui créer un modèle dédié. On ne l'a pas fait, et c'est un arbitrage assumé :

**Ce qu'on gagne** — kanban, activités, chatter, pièces jointes, relances,
filtres, droits, tableaux de bord : tout existe déjà et fonctionne. Un modèle
dédié aurait signifié réécrire ces sept mécaniques pour un flux d'une dizaine de
demandes par semaine.

**Ce qu'on paie** — les demandes de contenu polluent les statistiques du CRM si
on ne filtre pas par équipe. Les rapports de revenu incluraient des « leads » qui
ne représentent aucun chiffre d'affaires. Le contournement est le filtre équipe,
déjà présent partout dans les vues natives.

Le jour où la production de contenu réclame des dépendances entre livrables, un
calendrier éditorial propre ou du suivi de temps, elle aura mérité son modèle.
Pas avant.

## Cloisonnement : deux verrous, deux défauts d'Odoo

Séparer les deux processus a demandé **deux** corrections, pour deux raisons
différentes. Aucune des deux n'est native.

### 1. Les étapes — le piège de l'étape sans équipe

`crm.lead.stage_id` porte ce domaine, écrit par Odoo lui-même
(`crm/models/crm_lead.py:134`) :

```
['|', ('team_ids', '=', False), ('team_ids', 'in', team_id)]
```

Une étape **sans équipe apparaît dans TOUS les pipelines**. Or Odoo en livre
quatre — New, Qualified, Proposition, Won — sans équipe. Résultat observé sur la
première version : la barre d'état d'une demande de contenu affichait
`New › Qualified › Proposition › Won › Demande/Idée › Priorisation › …`, les
deux processus mêlés sur la même ligne.

`data/crm_stage_native_data.xml` les rattache à l'équipe **Sales** que le noyau
crée lui-même. Elles gardent un pipeline cohérent là où Odoo les attend, et
disparaissent des deux nôtres — personne chez nous n'est membre de cette équipe.

Pourquoi les déplacer plutôt que les supprimer : `crm.lead.stage_id` est en
`ondelete='restrict'`. Un seul lead posé dessus et la mise à jour casse.
Déplacer est réversible, supprimer ne l'est pas.

Un test échoue si une étape sans équipe réapparaît, et un autre vérifie que les
jeux d'étapes des deux pipelines sont **disjoints**.

### 2. Les leads — ce qu'Odoo ne fait PAS non plus

**Odoo 19 n'a aucune règle de visibilité par équipe sur `crm.lead`.**
`crm/security/crm_security.xml` ne connaît que deux niveaux :

| Groupe | Domaine natif |
|---|---|
| `sales_team.group_sale_salesman` | `['|', ('user_id','=',user.id), ('user_id','=',False)]` |
| `sales_team.group_sale_salesman_all_leads` | `[(1,'=',1)]` — **tout** |

Sans intervention, un responsable verrait les candidatures d'admission et les
demandes de contenu dans le même pipeline.

`security/his_crm_security.xml` **resserre la règle native** au lieu d'en ajouter
une :

```
['|', ('team_id', '=', False), ('team_id', 'in', user.crm_team_ids.ids)]
```

Le détail qui compte : **deux règles portant sur le même groupe se combinent en
OU, pas en ET**. Une règle supplémentaire aurait été purement décorative — le
`[(1,'=',1)]` natif l'aurait annulée à chaque lecture. C'est le piège classique
des règles d'enregistrement Odoo.

Conséquences à connaître :

- un responsable membre d'**aucune** équipe ne voit plus que les leads sans
  équipe. Quelqu'un qui suit les deux processus est membre des deux équipes ;
- `team_id = False` reste visible, sinon un lead entrant par formulaire web ou
  import disparaîtrait de toutes les vues dès sa création.

### Les menus : séparés, mais pas cachés

Deux entrées distinctes sous CRM — **Admissions** et **Production Contenu** —
chacune filtrée sur son équipe. Le pipeline natif « Sales › My Pipeline »
mélange toutes les équipes de l'utilisateur ; ouvrir le sien depuis un menu
nommé évite d'y tomber par accident.

Les deux menus restent **visibles de tous**. Le cloisonnement est dans les
données, pas dans l'affichage : un membre de Production Contenu qui ouvre
Admissions voit une liste vide, avec un message qui dit pourquoi. Une seule
source de vérité — l'appartenance à l'équipe — plutôt qu'un groupe de sécurité
à tenir en phase avec elle, qui dériverait au premier changement d'équipe.

## Qui est dans quelle équipe

| Équipe | Membres | Rôle |
|---|---|---|
| Ventes / Admissions | **Asma** (responsable), Aicha, Rahma | Traite les leads scorés par le Marketing |
| Cellule d'Orientation | *TODO Endeavor* | Évaluation psychologique — unité distincte des Ventes |
| Production Contenu | *TODO Endeavor* | Priorisateur, copywriter, designer(s), vidéaste, approbateur |

Asma est responsable d'équipe : c'est elle, et elle seule, qui reçoit les
relances SLA de premier contact.

**Le Marketing est membre des deux équipes.** Il fait la capture et le scoring
(pipeline Admissions, étape 1) *et* la production de contenu — c'était le double
rôle qu'il tenait dans GHL. Un utilisateur Odoo peut appartenir à plusieurs
équipes ; aucun code n'est nécessaire pour cela. Conséquence assumée : le
Marketing voit les candidatures après la passation aux Ventes. Les conseillères
Ventes, elles, ne voient pas les demandes de contenu.

**`data/crm_team_member_data.xml` crée trois comptes** (`asma`, `aicha`,
`rahma`) avec des emails d'espace réservé et sans mot de passe. **Si ces
personnes ont déjà un compte Odoo, retirez ce fichier du manifeste avant
d'installer** — il créerait des doublons — et rattachez les comptes existants
depuis CRM › Configuration › Équipes commerciales.

## Pipeline Ventes / Admissions

| # | Étape | Note |
|---|---|---|
| 1 | Nouveau (score) | Lead capté par le Marketing, `score_academique` renseigné |
| 2 | Pris en charge | Affectation **manuelle** depuis la file triée par score |
| 3 | Contact établi | Le conseiller a parlé au candidat — étape déclencheuse de l'identité |
| 4 | Accompagnement décision | Dérivation optionnelle, candidat indécis, reste aux Ventes |
| 5 | Évaluation psychologique | Dérivation optionnelle, portée par la **Cellule d'Orientation** |
| 6 | Dossier et pré-admission | Atteignable depuis 3, 4 ou 5 |
| 7 | Pré-admis (`is_won`) | Déclenche le paiement des frais — Finance/Admission, hors module |

Les étapes 4 et 5 sont des dérivations, pas des passages obligés : un lead en
traverse une, les deux ou aucune. Rien n'est codé pour cela — c'est la `sequence`
qui les place et le conseiller qui choisit.

**La Cellule d'Orientation est une unité distincte des Ventes**, avec sa propre
équipe. Un refus qu'elle prononce sort du quota commercial des Ventes : c'est une
règle organisationnelle existante et assumée, matérialisée par le motif de perte
« Hors quota commercial ». Aucune restriction ni validation n'est posée dessus —
ce n'est pas à ce module de policer une pratique établie.

### Deux scores, pas un

Le Playbook Enrolment documente bien **deux** évaluations, par deux équipes à
deux moments :

- `score_academique` — Marketing, à la capture : profil académique et
  motivation. C'est lui qui ordonne la file d'affectation.
- `score_opportunite` — Ventes, **après** contact direct : engagement, adéquation
  au programme, potentiel de conversion.

Les confondre reviendrait à écraser le tri de la file avec un jugement qui
n'existe pas encore au moment où l'on trie.

### Affectation : manuelle, par choix

La vue **Leads à affecter** (menu CRM) liste les leads sans commercial en étapes
1–2, du meilleur score au moins bon. Le responsable coche plusieurs lignes,
modifie « Commercial » sur l'une d'elles, Odoo propage (`multi_edit="1"`).

Aucun round-robin, aucune règle d'affectation automatique : la Direction veut
que l'arbitrage reste humain. Le cron natif `crm.ir_cron_crm_lead_assign` est
laissé inactif comme Odoo le livre.

### Relance SLA premier contact

Un `ir.cron` **horaire** signale les leads en « Pris en charge » depuis plus de
4 h. Le rythme est explicite : le défaut d'Odoo est journalier, ce qui
signalerait un retard le lendemain, quand la relance n'a plus d'objet.

L'activité est posée sur le **responsable d'équipe**, jamais sur le conseiller
assigné — le conseiller sait déjà qu'il a le lead, c'est précisément le problème.
Une seule relance par retard, sinon le cron horaire empilerait une activité par
heure jusqu'à ce que le responsable cesse de les lire. Aucune avance d'étape,
aucune réaffectation.

Sans responsable d'équipe (`team_id.user_id`), **aucune relance n'est posée** :
la poser sur le conseiller rendrait le retard invisible tout en paraissant
traité.

## Pipeline Production Contenu

| # | Étape |
|---|---|
| 1 | Demande / Idée — n'importe quel département dépose |
| 2 | Priorisation — le stratégiste trie |
| 3 | Production — étape agrégée |
| 4 | Approbation — validation finale du directeur |
| 5 | Planification et publication (`is_won`) |

### Champs par type de livrable, pas sous-étapes

Une même demande peut exiger texte, design et vidéo **en parallèle**, et chacun
avance à son rythme : le texte peut être approuvé pendant que le design est
encore en révision.

Une étape ne peut pas représenter cet état. Trois paires
`besoin_X` / `statut_X` le peuvent, plus un assigné par type — le copywriter, le
designer et le vidéaste travaillent en même temps sur la même demande.

Ajouter un type de livrable (podcast, affiche) : trois champs et une ligne dans
la constante `LIVRABLES` de `models/crm_lead.py`. La contrainte, la vue et les
messages d'erreur suivent.

### Le verrou d'approbation

`@api.constrains` refuse l'étape **Approbation** tant qu'un livrable demandé
(`besoin_X = True`) ne porte pas `statut_X = 'approuve'`.

C'est le cœur du module. Le tableur qu'on remplace portait déjà une colonne
« Approval Status » — **vide dans presque toutes les lignes réelles**, parce que
rien ne la réclamait. Une règle posée dans la vue se contournerait par le kanban,
l'import ou le glisser-déposer, exactement comme la colonne se contournait par la
touche Entrée. La contrainte est donc serveur, même discipline que la gouvernance
de `his_stock_mdm`.

Un refus d'approbation n'est pas une perte sèche : le motif « Retour production
nécessaire » renvoie la demande en production.

## Les deux tableaux kanban

Le pipeline se lit sur un tableau, pas dans une liste : c'est le geste que
l'équipe avait dans GoHighLevel et qu'elle voulait retrouver. Les deux vues
héritent de la kanban native d'Odoo (`crm.crm_case_kanban_view_leads`) en
`mode="primary"`, exactement comme Odoo le fait lui-même pour sa vue prévisionnelle.

**Pourquoi deux vues et non une seule partagée.** `<progressbar>` est un élément
de la vue, pas de la carte : il ne porte pas d'attribut `invisible` et ne peut
donc pas apparaître pour une équipe et disparaître pour l'autre, comme le font
les pages du formulaire. Chaque action pointe la sienne par `view_id`.

| | Admissions | Production Contenu |
|---|---|---|
| Barre de progression | oui, par état d'activité | **non** — rien ne pose d'activité sur une demande de contenu, la barre serait uniformément grise |
| Total de colonne | somme des `score_academique` | le compteur natif seul |
| Carte | score, visite effectuée, spécialité[^1] | département, marque, avancement des livrables |

[^1]: la spécialité est ajoutée par `his_admission`, qui apporte le référentiel.
`his_crm_pipeline` s'installe seul et ne le connaît pas — d'où le point
d'accroche `o_his_lead_kanban_meta`, stable, que les modules en aval visent.

**Le total de colonne n'est pas de l'argent.** Odoo somme le chiffre d'affaires
attendu ; une candidature n'en porte pas — les montants vivent sur
`his.engagement`. La somme des scores est utile pour comparer deux colonnes, pas
pour annoncer un chiffre d'affaires.

Ce que les cartes ne redéclarent pas : étiquettes, avatar du commercial,
activités, priorité, pourrissement. La carte native les rend déjà.

## Étiquettes et vues enregistrées

Huit étiquettes de départ (`data/crm_tag_data.xml`) et huit vues enregistrées
(`data/ir_filters_data.xml`), en `noupdate="1"` : ce sont des points de départ,
une équipe qui les affine ne doit pas les voir revenir à la prochaine livraison.

Les étiquettes ne doublent délibérément **pas** ce que des champs de sélection
disent déjà — pas d'étiquette « HIS » à côté de `marque`, sinon deux vérités pour
la même question. Elles portent ce que le dossier ne dit pas : « Bourse
demandée », « Indécis programme », « Urgent », « Réseaux sociaux »…

Chaque vue enregistrée est rattachée à **son** action (`action_id`) : sans cela
un favori est global au modèle, et « Livrables en retard » apparaîtrait dans les
Admissions. Le cloisonnement des favoris suit celui du reste du module.

**Deux pièges techniques, tous deux vérifiés par un test.**

`ir.filters.domain` est relu par `_get_eval_domain()` avec `ast.literal_eval`,
qui **refuse tout appel de fonction** : un domaine écrit avec `context_today()`
ou `relativedelta()` s'installe sans bruit et casse à la lecture. Les dates
relatives passent donc par le mini-langage d'Odoo 19 (`'now -4H'`, `'today -7d'`,
cf. `odoo/tools/date_utils.py:parse_date`), qui reste une simple chaîne — donc
littérale — tout en restant dynamique, et qui a son équivalent JavaScript.

Un nom de champ erroné dans un domaine de favori n'est vérifié **ni** à
l'installation, contrairement à l'arch d'une vue, **ni** par le `literal_eval` :
il n'échouerait qu'au premier clic. `test_les_vues_enregistrees_sont_litterales_et_executables`
relit ce qui est en base et l'exécute.

### Droits sur les étiquettes

Les rôles Admissions portent `sales_team.group_sale_salesman`, qui donne déjà
l'accès natif à `crm.tag` : rien à ajouter. Les rôles Contenu n'en portent aucun,
délibérément — et **`base.group_user` ne reçoit rien du tout sur `crm.tag` dans
Odoo natif** (`0,0,0,0`). Sans droit explicite, une demande étiquetée devenait
donc illisible pour son propre demandeur. Trois lignes le corrigent : lecture
pour Demandeur et Production, création et écriture pour la Priorisation — qui
trie les demandes entrantes, donc fait vivre la taxonomie, comme elle le fait
déjà pour les types de livrable. Jamais de `unlink` : une étiquette supprimée
disparaît de tous les leads qui la portaient, sans trace.

## Programmer une visite du campus

Bouton dans le formulaire et entrée du menu de la carte kanban, côté Admissions
seulement. Il appelle `action_schedule_meeting`, **native d'Odoo** (`crm`), qui
ouvre l'agenda pré-rempli du candidat et de l'équipe. Aucun code serveur ajouté.

**Il ne coche rien, et c'est le point.** `visite_campus_effectuee` reste ce
qu'une conseillère atteste après coup. Un rendez-vous pris n'est pas une visite
effectuée — les absences sont courantes — et un booléen qui deviendrait vrai tout
seul mentirait sur la moitié d'entre elles. Programmer et constater sont deux
gestes distincts ; ils le restent.

## Hors périmètre (assumé)

- **Thème GHL** — la passe *structurelle* est faite (tableaux kanban, étiquettes,
  vues enregistrées, totaux de colonne). La passe *visuelle* — couleurs, espacements
  exacts — attend toujours une capture réelle de l'instance du client : rien dans ce
  dépôt ne fixe de couleur en dur, tout passe par les composants et les jetons de
  thème d'Odoo, pour qu'un habillage ultérieur ne touche que ceux-ci.
- **Prise de rendez-vous en libre-service** — le module `appointment` est réservé à
  l'édition Enterprise et absent de cette image Community. La prise de rendez-vous
  reste donc à la main de l'équipe, via l'agenda natif. Un lien public de
  réservation à la GoHighLevel demanderait Enterprise ou un module tiers.
- **`visite_campus_effectuee` calculé depuis l'agenda** — non, et pas « pas encore » :
  voir ci-dessus. Le champ est une attestation, pas une déduction.
- **Chart.js sur l'entonnoir du cockpit** — les barres CSS suffisent tant qu'aucune
  courbe temporelle n'est demandée (cf. le commentaire dans `dashboard.scss`).
  L'entonnoir est un instantané, pas une série temporelle. Une répartition en donut
  par étape ferait double emploi avec le lien pivot déjà présent dans « Explorer ».
- Migration des données GHL : départ à neuf, aucun historique repris.
- WhatsApp, Facebook, Instagram : pas d'inbox, pas de threading.
- Séquences de nurturing et automatisation marketing.
- Capture UTM côté site ou plateformes publicitaires. Les champs UTM natifs
  (`source_id`, `medium_id`, `campaign_id`) sont laissés tels quels, une
  intégration ultérieure les remplira.
- Le rattachement au référentiel Personnes : c'est
  [`his_crm_identity_bridge`](../his_crm_identity_bridge/), module séparé. **Ce
  module-ci n'a aucune dépendance à `his_person_core`** et s'installe seul.

## Installation

```bash
docker compose run --rm odoo odoo -d <base> -i his_crm_pipeline --stop-after-init
```

Puis, **avant la mise en service** : renseigner les membres des trois équipes
(Ventes / Admissions, Cellule d'Orientation, Production Contenu) et le
responsable de l'équipe Ventes. Les équipes sont livrées vides — inventer des
noms aurait produit des droits d'accès faux, plus difficiles à repérer qu'une
équipe manifestement vide. La visibilité des leads dépend de cette appartenance.

## Lancer les tests

```bash
docker compose stop odoo
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' docker compose run --rm odoo odoo \
  -d <base_test> --without-demo=all -i his_crm_pipeline \
  --test-enable --test-tags /his_crm_pipeline --stop-after-init
```

`MSYS_NO_PATHCONV=1` est obligatoire sous Git Bash, sinon `/his_crm_pipeline`
est réécrit en chemin Windows et les tests ne tournent pas — en silence.
