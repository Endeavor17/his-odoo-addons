# his_hr_base — Rattachement RH au référentiel Personnes

Relie chaque `hr.employee` à sa fiche `his.person` et y **reflète** son
matricule institutionnel.

## La règle de propriété

> **`matricule_institutionnel` sur `hr.employee` est un miroir, pas une source.
> La source est `his_person_core`.**

Le champ est un `related='person_id.matricule_institutionnel'`, `store=True`,
`readonly=True`. Il n'existe aucun chemin par lequel un employé obtient un
matricule autrement qu'en obtenant d'abord une fiche `his.person`.

Le **nom du champ est conservé à l'identique** : `hr_employee_views.xml` de
`maintenance_university` le référence par ce nom et continue de fonctionner sans
la moindre modification.

Avant cette branche, `maintenance_university` définissait ce champ, sa propre
séquence (`hr.employee.matricule.institutionnel`) et sa propre contrainte
d'unicité. Un identifiant censé être commun aux employés, aux enseignants et aux
étudiants était donc émis par un compteur privé, à l'intérieur d'une application
de maintenance, et sans aucune coordination avec les matricules d'étudiants
attribués par ailleurs (export Sales/Admission). C'était un **risque de
collision réel sur un identifiant de groupe**, pas une question de frontière de
module.

## Année du matricule

L'année vient de `date_start_working`, pas de la date de création de la fiche :
une embauche saisie en retard ou signée pour la rentrée doit porter son année
réelle. Comportement repris **à l'identique** du code remplacé, via la clé de
service `matricule_sequence_date` de `his_person_core`.

`date_start_working` reste défini par `maintenance_university` : c'est une donnée
RH, sans rapport avec le modèle d'identité. `create()` lit simplement la clé dans
`vals` si elle est présente.

## Reprise de données — lire avant tout déploiement

`matricule_institutionnel` **existe déjà** comme vraie colonne sur `hr_employee`
et peut contenir des valeurs de production réelles. En redéfinissant le champ en
`related` stocké, l'ORM le recalcule au chargement depuis `person_id` — vide à ce
stade — et **écraserait** son contenu. D'où deux hooks :

1. **`pre_init_hook`** — avant le chargement des modèles de ce module, lit en SQL
   direct `id, matricule_institutionnel` depuis `hr_employee` et copie le
   résultat dans la table `his_hr_base_matricule_backup`.
2. **`post_init_hook`** — pour chaque couple capturé, crée une `his.person` avec
   `matricule_institutionnel` **explicitement** positionné à la valeur capturée
   (`his_person_core.create()` n'émet alors aucun nouveau numéro et n'en
   recalcule pas la clé), puis renseigne `person_id` sur l'employé. Les employés
   sans aucun matricule reçoivent une fiche et un numéro neufs.

**Une vraie table, pas un attribut de module** : les deux hooks doivent survivre à
un redémarrage de worker entre eux, et cette table est la **seule trace** de
l'état des matricules avant migration. Migration à un coup sur un identifiant à
vie : elle n'est pas supprimée après coup, délibérément.

**Idempotence** : un employé déjà rattaché (`person_id` renseigné) est ignoré ;
une fiche portant déjà le matricule capturé est réutilisée, pas dupliquée.
Rejouer le hook après un déploiement échoué ne crée aucun doublon.

**Collisions préexistantes** : si la capture contient deux fois le même
matricule, la donnée d'origine portait déjà une collision sur un identifiant
censé être unique. Elle est **journalisée en ERROR et remontée**, jamais résolue
en silence.

## Séquencement de déploiement

Les deux nouveaux modules s'installent et `maintenance_university` se met à jour
dans la **même commande** :

```bash
odoo -d <base> -i his_person_core,his_hr_base -u maintenance_university --stop-after-init
```

Odoo résout alors le graphe de dépendances et exécute les hooks de `his_hr_base`
au bon moment. **Ne pas** installer puis mettre à jour en deux commandes
séparées contre une base réelle : cela ouvre une fenêtre où deux définitions du
champ coexistent.

Répéter d'abord contre une **copie de la base de production** (ou le fixture le
plus réaliste disponible). Il n'y a pas de retour arrière propre si la migration
se passe mal sur des matricules vivants.

## Lancer les tests

```bash
docker compose run --rm odoo odoo -d <base> -u his_hr_base \
  --test-enable --test-tags /his_hr_base --stop-after-init
```

## Hors périmètre

Ni carte RFID, ni portefeuille repas, ni POS/Restaurant/Copy Center, ni Uniflow :
cf. la section « Hors périmètre » de [`his_person_core`](../his_person_core/README.md).

## Calage de la séquence

L'ancienne séquence a déjà brûlé des numéros, et la nouvelle repart à 1 chaque
année. Sans calage, une embauche datée 2022 recevrait `HIS-2022-000001-C` alors
que `HIS-2022-000001` est déjà porté : la clé de contrôle rend les deux chaînes
différentes, donc la contrainte d'unicité ne dit rien — mais c'est **le même
numéro pour deux personnes**, et l'œil humain ne fait pas la différence.

Le `post_init_hook` cale donc le compteur de chaque année au-delà du plus haut
numéro repris, avant d'émettre le moindre matricule neuf. Constaté en répétition
de migration : sans ce calage, le doublon se produit.

## Un seul contact par humain

`hr` crée déjà un `res.partner` pour chaque employé (`work_contact_id`). La
fiche personne s'y **rattache** au lieu d'en créer un second — vérifié en
répétition de migration : aucun `res.partner` n'est créé pendant la reprise, et
`person_id.partner_id == work_contact_id` pour chaque employé migré.

**L'ordre compte.** `hr.employee.create()` ne crée le `work_contact_id` qu'à sa
**dernière ligne** (`employees.filtered(...)._create_work_contacts()`). La
surcharge de ce module appelle donc `super()` **d'abord**, puis crée la fiche
personne. Créer la fiche avant, c'est garantir un second contact pour le même
humain.

**Contact partagé.** `res.partner.employee_ids` est un One2many : deux employés
peuvent légitimement partager un contact de travail. Un matricule, lui,
identifie une seule personne — la création est donc **refusée** avec un message
explicite, et la reprise donne un contact distinct en journalisant le cas.
Jamais de partage silencieux.
