# Note à Endeavor — anomalies relevées dans le socle identité

Salut Mohamed,

En travaillant sur `his_meal_management` j'ai audité l'ensemble des modules pour
vérifier que tout passe bien par le référentiel. **L'architecture tient** : une
seule `his.person`, une seule séquence de matricule, aucun modèle « personne »
concurrent, et la chaîne du badge est propre de bout en bout. Rien à redire
là-dessus.

En revanche j'ai trouvé six choses dans tes modules. Une bloquante, trois qui
fabriquent des doublons, une contradiction de documentation, et une dette.
J'ai corrigé les quatre premières **en local, rien n'est poussé** — dis-moi si
tu veux les récupérer, les réécrire autrement, ou en discuter d'abord.

Toutes les références de fichiers ci-dessous sont sur `origin/identity`
(= `origin/main`, commit `2ce56c15`), vérifiées ligne à ligne.

---

## 1. BLOQUANT — le formulaire Catégories est inouvrable

**Symptôme.** Maintenance → Configuration → Catégories, ouvrir n'importe quelle
catégorie :

```
RPC_ERROR — KeyError: 'maintenance_ids'
  odoo/orm/models.py:6896  _modified_triggers  ->  records = self[invf.name]
  odoo/addons/web/models/models.py:2144  onchange -> record.modified(...)
```

**Cause.** `maintenance_university_request.py:42` redirige `category_id` vers
notre `maintenance.category` :

```python
category_id = fields.Many2one('maintenance.category', ...)
```

Mais le One2many qui déclare `category_id` comme inverse vit sur le modèle du
cœur, pas sur le nôtre :

```
maintenance/models/maintenance.py:43
    maintenance_ids = fields.One2many('maintenance.request', 'category_id')
```

L'ORM enregistre donc « l'inverse de `category_id` s'appelle `maintenance_ids` »
et va le chercher sur le comodèle — `maintenance.category` — où il n'existe pas.
Au premier `onchange`, `web/models/models.py` appelle `modified()` sur tous les
champs, `_modified_triggers` déroule les inverses, et ça casse.

**Correctif.** Un champ, déclaré comme celui du cœur, dans
`maintenance_category.py` :

```python
maintenance_ids = fields.One2many(
    'maintenance.request', 'category_id', string="Requests", copy=False,
)
```

**Vérifié plutôt qu'affirmé.** J'ai retiré le champ et relancé la suite : `1
failed, 2 error(s) of 16`, avec le `KeyError` d'origine reproduit par un
`modified()` sur une catégorie. Remis : `0 failed, 0 error(s) of 16`. Le test
est dans `maintenance_university/tests/test_category_inverse.py`.

C'est le seul endroit où le problème se pose : `category_id` est le seul champ
redirigé vers un autre comodèle. Les autres inverses (`equipment_id`) sont
intacts.

---

## 2. L'assistant « Créer des travailleurs » fabrique une personne à chaque passage

`maintenance_university/wizard/maintenance_university_worker_create.py`

L'assistant crée un `res.users` puis un `hr.employee` à partir d'un nom et d'un
login. Ni l'un ni l'autre ne porte de `person_id`, donc
`his_hr_base.hr_employee.create()` tombe dans `_create_his_person()` et émet une
fiche neuve **avec un matricule neuf**, à chaque exécution.

Ton garde-fou dans `_create_his_person()` est correct mais ne couvre pas ce
cas : il vérifie qu'un *contact* ne porte pas déjà une fiche, jamais que
*l'humain* existe déjà.

Deuxième effet, plus discret : `Users.create()` est appelé sans `partner_id`.
`res.users` en fabrique donc un — un **second contact** pour un humain qui en a
déjà un. C'est exactement le fork que la délégation existe pour empêcher.

**Conséquence réelle sur la base du groupe.** Je suis en trois exemplaires :

| id | matricule | type | état |
|---|---|---|---|
| 7 | `HIS-2026-000007-3` | etudiant | actif — porte la carte et le portefeuille |
| 11 | `HIS-2026-000011-5` | employe | archivé, non fusionné |
| 13 | `HIS-2026-000013-9` | employe | archivé, non fusionné |

**Correctif local.** La ligne de l'assistant reçoit les trois champs qui
manquaient : `person_id` — le **même rattachement manuel que ton formulaire
employé offre déjà** —, une suggestion calculée sur le nom, et une case « New
Person » pour assumer un vrai homonyme. Sans l'un ou l'autre, le bouton refuse.

Rattacher réutilise tout ce qui existe : le contact de la fiche, le compte si la
personne en a déjà un, et `person_id` sur l'employé — ce qui fait sauter
`_create_his_person()` **par ton propre garde `if not employee.person_id`**,
sans rien changer chez toi.

Un point de méthode : la suggestion n'utilise volontairement pas
`_find_or_flag_match()`. Avec deux champs seulement, elle ne peut rien retourner
— le nom pèse 0,40 pour un seuil à 0,75, donc elle répondrait `new` pour un nom
qui correspond parfaitement. Elle réutilise en revanche ton `normalize_text()`,
donc « ABDO CHABOUTI » et « Chabouti Abdo » se retrouvent. Ce n'est pas un second
algorithme.

---

## 3. `hr.employee.person_id` n'a aucune contrainte d'unicité

`his_hr_base/models/hr_employee.py`

Rien n'empêche deux employés de désigner la même fiche personne. Le matricule
cesse alors d'identifier un seul dossier. C'est la porte jumelle du point 2 : le
formulaire employé standard crée un `hr.employee` de la même façon, et ton
commentaire à côté de `person_id` dit bien que le rattachement manuel est « le
seul moyen d'éviter un doublon » — mais rien ne vérifie que la fiche visée est
libre.

Au passage : le domaine de `hr_employee_views.xml:20` porte sur `address_id`
(adresse de travail) et écarte les personnes d'un sélecteur d'adresses. Il ne
protège pas le lien d'identité — je l'avais d'abord cru, à tort.

**Correctif local.** Une `@api.constrains('person_id')` qui refuse un second
employé, `active_test=False` compris — sinon le doublon réapparaît au
désarchivage.

**Vérifié avant application sur `his` :**

```sql
SELECT person_id, count(*) FROM hr_employee
WHERE person_id IS NOT NULL GROUP BY person_id HAVING count(*) > 1;
-- (0 rows)
```

Aucune fiche ne portait déjà deux employés : la contrainte passe sans casser la
migration. À revoir le jour où le groupe passerait en multi-sociétés, où le cœur
attend un employé par société.

---

## 4. L'import ne sait pas reconnaître quelqu'un par son badge

`his_person_core/models/his_person.py` — `_find_or_flag_match()`

Les clés déterministes sont le matricule et `(external_ref, source_system)`. Le
`numero_carte` n'est lu que par `_card_conflict()` dans
`his_person_sync_sheets`, et **uniquement pour rejeter une ligne**, jamais pour
retrouver son porteur.

Or le format annoncé par les sources est **Nom + Badge**. Une telle feuille ne
reconnaît donc personne et recrée tout le monde : le nom seul pèse 0,40 contre un
seuil à 0,75, la ligne repart en `new`, et chaque import fabrique un doublon avec
un matricule de plus.

**Correctif local — avec une nuance qui compte.** Le badge devient une clé
déterministe, placée entre le matricule et la référence source, **mais seulement
quand le nom concorde aussi**.

C'est ton propre test qui m'a fait ajouter cette condition :
`test_card_already_held_by_someone_else_is_a_conflict`. Une carte est un objet
physique, elle peut être rééditée et changer de main. Rapprocher sur le seul
numéro laisserait une ligne au nom différent **écraser silencieusement la fiche
du porteur précédent**. Nom différent = pas de rapprochement ici, et
`_card_conflict` rejette comme avant. Ton test passe inchangé.

L'ordre matériel : matricule (émis par l'institution, immuable) > badge confirmé
par le nom > référence source (simple clé de rejeu).

---

## 5. Trois affirmations du README contredites par le code du même dépôt

`his_person_core/README.md`, section « Badge RFID »

### 5a. `res.partner.barcode` — « un champ que personne ne lit »

Le README dit qu'y recopier le numéro reviendrait à « alimenter un champ que
personne ne lit ». Le cœur d'Odoo 19 le lit **trois fois**, et j'ai vérifié les
trois dans le conteneur de ce projet :

| Chemin | Ligne | Ce qu'il fait |
|---|---|---|
| `point_of_sale/models/res_partner.py` | 76 | `'barcode'` est dans `_load_pos_data_fields()` — la caisse le charge |
| `.../partner_list/partner_list.js` | 166, 177 | `barcode` est dans les champs de recherche — taper un badge dans la liste clients trouve la personne |
| `.../product_screen/product_screen.js` | 286, 288 | `getBy("barcode", code.code)` puis `searchRead("res.partner", [["barcode","=",code.code]])` — un badge tapé résout le client |

C'est précisément par ce champ que passe **chaque scan** de
`his_meal_management` : un lecteur RFID qui tape des chiffres et Entrée *est* un
lecteur de code-barres pour Odoo. Laissée telle quelle, cette ligne conduirait
quelqu'un à supprimer le miroir et à casser silencieusement la résolution du
badge à la caisse.

### 5b. Le « Badge ID » présenté comme un badge séparé

Le README dit « à ne pas confondre… les deux coexistent sur le formulaire
employé ». Mais `his_hr_base/models/hr_employee.py:53` en fait un `related`
stocké vers `person_id.numero_carte`, et ton propre README de `his_hr_base` le
revendique : « **Conséquence assumée :** on ne peut plus donner à un employé un
Badge ID différent de son badge RFID. C'est le but. »

Les deux READMEs disent l'inverse l'un de l'autre. C'est `his_hr_base` qui
décrit le code.

### 5c. L'« écart assumé » sur le cycle de vie de carte est périmé

« À reprendre dans un modèle dédié (`person_id`, numéro, état, dates de
validité) **avant** que le portefeuille repas ne stocke de l'argent. »

C'est fait : `his.meal.card` est ce modèle (code, état, carte remplacée), et
`his.person.numero_carte` est devenu `compute` + `inverse` par-dessus. Écrire un
badge émet une carte et retire la précédente, donc l'historique survit — la
question « quelle carte était valide au moment de cette transaction » a une
réponse.

Je n'ai touché à aucun de tes README : c'est ton texte, à toi de trancher la
formulation.

---

## 6. Dette — `odoo.osv.expression` est déprécié en 19.0

`his_person_core/models/his_person.py:269`, dans `_search_matricule_affiche()` :

```python
domain = expression.OR([...])
```

Remonte à chaque exécution de la suite :

```
odoo/osv/expression.py:173  normalize_domain
    warnings.warn("Since 19.0, use odoo.fields.Domain", DeprecationWarning)
```

Rien ne casse aujourd'hui — c'est un avertissement, pas un échec — mais le
module sort une trace de dépréciation à chaque test, et ça partira dans une
version future. Le remplacement est `odoo.fields.Domain`. Je ne l'ai pas touché.

---

## Ce que j'ai appliqué, et ce que je n'ai pas touché

**Ta couche identité, je n'y ai rien laissé.** `his_person_core`, `his_hr_base`,
`his_person_sync_sheets` et `his_stock_mdm` sont chez moi **strictement
identiques à `origin/identity`** — `git diff origin/identity` sur ces quatre
modules ne sort rien. C'est ton périmètre, je le prends tel que publié.

| Point | État chez moi | Où c'est |
|---|---|---|
| 1 · Inverse `maintenance_ids` | **appliqué** | `99126b4` |
| 2 · Assistant travailleurs | **appliqué** | `d7abe8c` |
| 3 · Unicité `person_id` | **non appliqué** | patch seulement |
| 4 · Clé badge à l'import | **non appliqué** | patch seulement |
| 5 · README | non touché — c'est ton texte | — |
| 6 · `expression.OR` | non touché | — |

Les points 1 et 2 sont dans `maintenance_university`, donc dans ton module : je
te le dis franchement pour que tu ne le découvres pas en lisant un diff. C'est
la partie maintenance du projet dont j'ai la charge, et le point 1 rendait
l'écran Catégories inutilisable — je ne pouvais pas travailler sans.

Les points 3 et 4 touchaient le socle : je les ai **retirés de mon arbre**. Ils
existent en patch, prêt à appliquer, sur la branche locale
`endeavor_identity_fixes` (commit `bb37a89`) et exporté dans
`_backups/endeavor_fixes/`. À toi de décider si tu les reprends, les réécris
autrement, ou les refuses.

**Rien n'est poussé**, sur aucune branche.

### Ce que le retrait du point 4 me coûte concrètement

Ce n'est pas un confort, c'est bloquant de mon côté. Sans clé badge, une feuille
**Nom + Badge** — le format que les sources nous envoient — ne rapproche
personne : le nom seul pèse 0,40 pour un seuil à 0,75. Chaque réimport depuis un
fichier renommé recrée **tous** les étudiants, avec un matricule de plus à
chaque passage. Je ne peux donc pas charger les listes d'étudiants tant que ce
point n'est pas tranché chez toi.

Suite complète après ce retrait : **105 tests, 0 échec, 0 erreur**, sur un clone
de `his` puis appliqué à `his`.

Un dernier point qui n'est pas un bug mais qui te concerne : `his_stock_mdm` crée
les caisses du groupe et `meal_product_id` n'était renseigné nulle part, donc le
Restaurant affichait « Non configuré ». Je l'ai câblé depuis **mon** module (hook
+ script de migration, avec garde si `his_stock_mdm` est absent et jamais
d'écrasement d'un choix manuel), pour ne pas créer de dépendance entre ton module
stock et le mien.

Dis-moi comment tu veux procéder.

— Abdo
