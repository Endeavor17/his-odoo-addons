# Listes fournisseur — source de vérité du catalogue

Transcription des listes fournies par l'admin inventaire (septembre 2026). Ces
fichiers, **et non le catalogue en base**, font foi : le catalogue actuel vient
d'un seed de reprise de l'ancien système (`Seed_Catalogue_Produits.csv`, 1301
lignes) qui est désormais périmé.

Les pièces jointes d'origine étaient des exports de tableur avec cellules
fusionnées et colonnes vides. Le contenu est repris **intégralement et dans
l'ordre**, remis en CSV plat `N°,Section,Designation` pour être lisible par
`tools/convertir_listes_seed.py`. Aucune désignation n'a été corrigée, y compris
les fautes de frappe du fournisseur (« spaghitti », « HIULE », « Cornicho ») :
c'est ce qui figure sur les bons de livraison.

| Fichier | Origine | Lignes |
|---|---|---|
| `listing_restaurant_cafeteria.csv` | « Listing 2 » | 214 |
| `liste_articles_HIS.csv` | « liste_articles_HIS », liste brute | 130 |
| `liste_fournitures_bureau.csv` | « Liste_Fournitures_Bureau_HIS_FR », liste classée | 115 |
| `articles_cotex.csv` | « Articles_cotex » | 8 |
| `cafeteria_gateaux.csv` | « cafetria et gateaux » | 745 |
| `nettoyage.csv` | « nettoyage » | 75 |

## Pièges connus

- **« Feuille de calcul sans titre » n'est pas reprise** : c'est le même contenu
  que « Listing 2 », au caractère près.
- **Les deux listes bureau décrivent le même périmètre.** La brute
  (`liste_articles_HIS`) donne **une ligne par couleur** ; la classée
  (`liste_fournitures_bureau`) regroupe les couleurs sur une ligne
  (`STYLO ULTRON X2 (BLEU / NOIR / ROUGE / VERT)`) mais apporte les 8 sections.
  Le convertisseur prend **la granularité de la brute et le classement de la
  classée** : une fiche par couleur, sinon le stock est incomptable.
- **`articles_cotex` liste 4 articles écrits deux fois** — lignes 1-4 au nommage
  « bon de livraison », lignes 5-8 au nommage « facture » pour les mêmes
  produits. 4 articles réels.
- **Numérotation à trous** dans « Listing 2 » : 79, 80, 81 et 83 n'existent pas.
  Conservée telle quelle pour pouvoir confronter au document d'origine.
- **L'arabe est perdu dans `cafeteria_gateaux` et `nettoyage`** : l'export a
  transcode chaque lettre arabe en `?`. Deux consequences distinctes — 33 lignes
  ne sont QUE cela (« A ?????? », « ??? / ?????? B ») et sont des en-tetes, pas
  des produits ; 14 produits reels ont juste perdu leur parenthese arabe
  (« Baklava (??????) ») et gardent un nom francais exploitable. Le convertisseur
  ecarte les premieres et retire la parenthese des seconds. **Un reexport en
  UTF-8 restaurerait les noms arabes** si on les veut.
- **Les codes-barres sont propres** : 0 doublon sur 538, 3 suspects seulement
  (`CAF-CHO-DUBI` qui est une ancienne reference interne et non un code-barres,
  un code a 7 chiffres, une cle de controle EAN fausse).
- **`Chips Master Natural Ketchup` figure deux fois avec deux codes-barres
  differents** : deux SKU reels que seul le scan distingue. A renommer.

- **Liste biscuits attendue** (annoncée pour le 2026-09-09) : la déposer ici et
  relancer le convertisseur, il est prévu pour.
