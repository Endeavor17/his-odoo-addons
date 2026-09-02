# Politique de droits — Groupe HIS-HTC-IRA

Une page. Elle vaut pour tout module du dépôt, livré ou à venir, et elle est
**tenue par des tests** : `his_access_base/tests/test_politique_acces.py` lit le
registre réellement installé et échoue si l'une de ces règles est enfreinte.

---

## 1. Refus par défaut

**Aucun modèle métier n'accorde de droit à `base.group_user`.**

C'est la règle qui manquait. Une seule ligne d'ACL suffisait à ouvrir le
registre d'identité du groupe — personnes, étudiants, matricules à vie — à
n'importe quel salarié, et rien ne l'aurait signalé.

### Ce qui verrouille réellement : l'ACL, pas le menu

`ir_ui_menu._visible_menu_ids()` masque déjà tout menu dont l'action cible un
modèle illisible, et un menu-dossier n'apparaît que s'il a un descendant
visible.

**Un `menuitem` sans `groups=` n'est donc pas un trou.** Il disparaît de lui-même
dès que l'ACL est correcte. Mettre un groupe sur un menu ne sert qu'à départager
deux rôles qui lisent le même modèle — « Leads à affecter », réservé au
responsable alors que la conseillère lit les mêmes leads.

Corollaire : ne pas perdre de temps à décorer les menus. Fermer les ACL.

## 2. Dérogation : la donnée de référence

Un modèle peut être lu par tout utilisateur interne s'il est **non nominatif,
non sensible, et nécessaire pour lire un écran métier** — un barème, un
catalogue de spécialités, une liste de types de pièces.

En **lecture seule**, et inscrit au registre `REFERENCE_PARTAGEE` du fichier de
test, **avec son motif**. Y ajouter une entrée est une décision, pas une
formalité : c'est le sens d'un registre de dérogations, assumer l'exception
plutôt que l'oublier.

## 3. La fonction donne les droits, l'échelon en donne l'étendue

L'organigramme croise sept grades
(مجلس الإدارة → مدير → مدير عمليات → مسؤول → مكلف → موظف → عون/مساعد) et une
quinzaine de départements.

**Le grade ne devient jamais un groupe Odoo.** Sept grades × quinze départements
font une centaine de groupes vides de sens : un *مسؤول* de la restauration et un
*مسؤول* des admissions n'ont aucun droit commun. C'est l'explosion de rôles que
tout référentiel IAM cherche à éviter.

Le grade et le département restent **descriptifs**, dans `hr.job` et
`hr.department`. Quand le grade change réellement un droit, il devient un
**échelon à l'intérieur de l'échelle métier concernée**.

### La forme à suivre

Un `res.groups.privilege` par fonction — une seule sélection dans la fiche
utilisateur — et des groupes qui s'impliquent en chaîne :

```
Acquisition → Conseiller → Responsable → Direction
```

Chacun contient le précédent. Le modèle de référence est
`his_crm_pipeline/security/his_crm_roles.xml`.

**Aucun groupe pour un département sans module.** Un groupe sans permission est
du bruit. Le catalogue grandit avec les modules.

### Les quatre couches, à ne pas confondre

| Couche | Répond à |
|---|---|
| `ir.model.access` | Quels **modèles** je touche |
| `ir.rule` | Quels **enregistrements** je vois |
| Garde-fous serveur | Quelles **transitions** je peux provoquer |
| Vues | Confort — **ne protège rien** |

Exemple de la troisième : `his_crm_pipeline/models/crm_capacites.py`. Odoo ne
sait pas l'exprimer déclarativement — qui peut écrire un enregistrement peut
écrire tous ses champs.

## 4. Séparation des tâches

Certaines paires de rôles ne se cumulent pas. Première inscrite :
**Finance (encaissement)** et **Conseiller Admissions** — qui encaisse ne doit
pas être celui qui a vendu, l'encaissement faisant basculer le lead en gagné.

Le test vérifie aussi qu'aucun des deux n'implique l'autre par une chaîne : le
cumul se ferait alors sans que personne l'ait coché.

---

## Attribution des rôles

`hr.job` porte les rôles Odoo du poste. À l'application, on distingue :

- **le droit du poste** — automatique, réconcilié ;
- **la dérogation individuelle** — posée à la main, **jamais touchée**.

Sans cette distinction, une resynchronisation efface les exceptions et personne
ne comprend pourquoi. Un cron hebdomadaire **signale** les écarts sans les
corriger : corriger en silence masquerait une attribution manuelle qui
contredit le poste, ce qu'une revue d'accès doit précisément voir.

La majorité de l'organigramme — cuisine, sécurité, entretien — n'a pas de compte
Odoo. C'est le cas normal, pas une anomalie.

---

## Deux pièges vérifiés

**`(6, 0, [...])` sur un menu qu'on ne possède pas.** Il *remplace* : il efface
les groupes natifs — donc l'accès des vrais RH à leur propre application — et il
ne survit pas à une désinstallation, laissant le menu **sans aucun groupe**,
c'est-à-dire ouvert à tous. Utiliser `(3, ...)` et `(4, ...)`.

**Les tests tournent en superuser** et contournent ACL, règles et garde-fous.
Tout test de droits passe par `with_user()`. Trois défauts sont déjà passés à
cause de ça.

---

## Limite assumée

Fermer `Employees` et `Contacts` est un contrôle de **visibilité**, pas de
**donnée**. `res.partner` et `hr.employee` restent lisibles au niveau du modèle,
et doivent l'être : le chatter, les activités et les partenaires des leads en
dépendent. Fermer l'application retire l'exposition courante, pas l'accès par un
lien direct.
