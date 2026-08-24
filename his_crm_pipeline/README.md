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

## Hors périmètre (assumé)

- **Thème GHL** — aucune référence visuelle (capture ou palette) n'existe dans ce
  dépôt. Les vues sont fonctionnelles, pas thémées. Passe séparée, une fois la
  référence fournie.
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
