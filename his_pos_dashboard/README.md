# his_pos_dashboard — Tableau de bord Metabase dans la caisse

Une entrée **Dashboard** dans le menu ☰ de la caisse ouvre un tableau de bord
Metabase en plein écran, sous la barre du haut. **Register** ramène à la vente.

---

## 1. Configuration

Trois paramètres système (Paramètres → Technique → Paramètres système, en mode
développeur), à poser **dans chaque base**, jamais dans le dépôt :

| Clé | Valeur |
|---|---|
| `his_metabase.site_url` | l'URL **https** de Metabase |
| `his_metabase.secret_key` | Metabase → Admin → Embedding → clé d'intégration statique |
| `his_pos_dashboard.metabase_dashboard_id` | le numéro du tableau de bord (ex. `5`) |

Les deux premières décrivent l'instance Metabase et sont **partagées** avec le
tableau de bord de `maintenance_university` : une rotation de clé se fait à un
seul endroit.

Tant que les trois ne sont pas posés, le menu reste celui d'Odoo : installer le
module ne change rien. Une fois posés : ☰ → **Reload Data** sur chaque caisse.

Côté Metabase : intégration statique activée, et tableau de bord **publié**
pour l'intégration.

**L'URL doit être en https.** Odoo est servi en https, et le navigateur bloque
un iframe `http://` dans une page https (contenu mixte).

## 2. Sécurité

- **La clé ne quitte jamais le serveur.** La caisse demande une URL à
  `pos.config.his_dashboard_url()`, qui signe un jeton HS256 valable
  10 minutes. Le navigateur ne voit que ce jeton.
- **Jamais dans le dépôt.** Le dépôt est public et la CI lance `gitleaks` sur
  tout l'historique. Si la clé a fuité, la régénérer dans Metabase et mettre à
  jour le paramètre.
- **Qui demande est vérifié d'abord** (audit S-6) : il faut être utilisateur
  Point de Vente, sinon `AccessError`.
- Tout caissier connecté voit le tableau de bord. Quiconque copie l'URL de
  l'iframe peut le consulter jusqu'à l'expiration du jeton : c'est le principe
  de l'intégration statique de Metabase.

## 3. Choix assumés

- **Pas de PyJWT.** L'image officielle d'Odoo ne l'a pas, et le déploiement
  n'a pas d'étape de build pour l'ajouter. HS256 tient en quelques lignes de
  bibliothèque standard ; Metabase ne vérifie que la signature et l'expiration.
- **Aucun champ stocké.** Un champ stocké, c'est une colonne, donc un `-u`
  obligatoire au déploiement ; oublié, il casse toutes les caisses. L'indicateur
  `his_dashboard_available` est calculé, non stocké. Il arrive au navigateur
  sans code de chargement : le POS lit `pos.config` avec une liste de champs
  vide, donc tous les champs (voir `his_pos_ui`, `test_theme_reaches_the_browser`).
- **Un module à part, pas `his_pos_ui`.** Celui-ci promet de ne faire aucun
  appel serveur ; celui-ci existe pour en faire un.

## 4. Limites connues

- **Économiseur d'écran.** Le minuteur d'inactivité du POS ne voit que la page
  du POS, pas les gestes dans l'iframe. Après 5 minutes, la caisse revient à la
  vente (ou à l'écran de verrouillage avec la connexion par employé). C'est
  voulu pour une caisse, et le jeton de 10 minutes n'expire jamais à l'écran.
  Pour un écran mural : exclure la page du minuteur et re-signer le jeton
  périodiquement.
- **Un seul tableau de bord pour toutes les caisses.** Un par caisse demanderait
  un champ stocké sur `pos.config`, donc un `-u` au déploiement.
- **Aucun filtre par caisse** (`params` vide). À ajouter dans la charge utile
  du jeton si un tableau de bord doit être restreint à une caisse.
