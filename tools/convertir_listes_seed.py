"""Convertit les listes fournisseur (tools/seed/sources/) en un seed importable
par tools/import_seed_catalogue.py.

    python tools/convertir_listes_seed.py          # ecrit tools/seed/Seed_Catalogue_v2.csv
    python tools/convertir_listes_seed.py --test   # controles internes

Ne touche pas a Odoo : il ne fait que transformer des CSV. L'import reel, avec
la gouvernance MDM, reste le role de import_seed_catalogue.py.

Deux listes decrivent le meme perimetre bureau. On prend la granularite de la
liste BRUTE (une ligne par couleur) et non celle de la liste classee, qui
regroupe « STYLO ULTRON X2 (BLEU / NOIR / ROUGE / VERT) » sur une ligne : une
telle fiche est incomptable en stock. La classee sert de controle de couverture.
"""
import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent / 'seed'
SOURCES = RACINE / 'sources'
SORTIE = RACINE / 'Seed_Catalogue_v2.csv'

# Chemins tels qu'attendus par import_seed_catalogue.py : il prefixe
# « All / Retail & Consommables (Storable) / » et remplace '/' par ' / '.
ALIMENTATIONS = 'Restaurant/Alimentations'
EPICES = 'Restaurant/Épices'
VIANDES = 'Restaurant/Viandes'
BOISSONS = 'Café/Boissons'
CHOCOLAT = 'Café/Chocolat'
BISCUITS = 'Café/Biscuits & Gâteaux'
DIVERS = 'Café/Divers'
EMBALLAGE = 'Café/Emballage'
BUREAUTIQUE = 'Copy/Articles Bureautique'
MENAGE = 'Ménage & Nettoyage'

# Listing 2 : le bloc epices occupe les lignes 88 a 111 du document (« Poivre
# Noire » a « epice fromage »). Repere par numero et non par mot-cle : « PIMENT
# CONSTANTINE » (ligne 23) est une conserve, pas une epice, et un mot-cle
# « piment » la deplacerait a tort.
EPICES_LIGNES = range(88, 112)
# Section « Gateaux et chocolat » : produits finis revendus vs vrac patissier.
CHOCOLAT_LIGNES = range(187, 197)     # tablettes et pates a tartiner
BISCUITS_LIGNES = {165, 166, 203}     # madeleines, roules, petit beurre
# tout le reste de la section = matiere premiere patisserie -> Café/Divers

# Exceptions a la section du document, tranchees avec l'admin inventaire.
LIGNES_FORCEES = {
    139: ALIMENTATIONS,  # « Ouefs » : dans la section « Poulet » du document,
                         # mais des oeufs ne sont pas de la viande.
}

# Articles d'hygiene glisses dans la liste bureau : ils relevent du menage.
HYGIENE = re.compile(r'\b(MOUCHOIR|LINGETTE|BAVETTE)\b', re.IGNORECASE)

# Trois designations sont tronquees dans la liste brute. La liste classee porte
# le libelle complet des memes articles : on corrige ici plutot que dans les
# sources, qui restent la piste d'audit de ce qui a ete recu.
CORRECTIONS = {
    'FLASH DISQUE 16 GB METAL HP REF': 'FLASH DISQUE 16 GB METAL HP REF 285',
    'SAC A CADEAU BLANCHE A4 25 X': 'SAC A CADEAU BLANCHE A4 25 X 37 CM',
    'PORTE STYLO METAL ROND NOIR OK 9502 C12 /': 'PORTE STYLO METAL ROND NOIR OK 9502 C12',
}

# Liste controlee de l'attribut Format (his_stock_mdm/data/product_attribute_data.xml).
FORMATS = ['33CL', '30CL', '25CL', '24CL', '20CL', '17.5CL', '1L', '2L', '5L',
           '125ML', '100G', '120G', '130G', '200G', '260G', '0.5KG', '1.5KG',
           '1.8KG', '5KG', '15KG', '25KG']
# Format n'est activable que sur ces categories (allowed_categ_ids du MDM).
FORMAT_ELIGIBLE = {BOISSONS, ALIMENTATIONS, EPICES, MENAGE}


def categorie_listing(ligne, section):
    """Section + numero de ligne du Listing 2 -> chemin de categorie."""
    if ligne in LIGNES_FORCEES:
        return LIGNES_FORCEES[ligne]
    if section == 'Emballage':
        return EMBALLAGE
    if section == 'Boissons':
        return BOISSONS
    if section == 'Poulet':
        return VIANDES
    if section == 'Gateaux et chocolat':
        if ligne in CHOCOLAT_LIGNES:
            return CHOCOLAT
        if ligne in BISCUITS_LIGNES:
            return BISCUITS
        return DIVERS
    if section == 'Agro alimentaire' and ligne in EPICES_LIGNES:
        return EPICES
    if section in ('Pates', 'Agro alimentaire', 'Produit laitier'):
        return ALIMENTATIONS
    return None


def format_controle(designation, categorie):
    """Renvoie la valeur Format de la liste controlee si la designation en
    porte une, et seulement sur une categorie eligible. Sinon chaine vide.

    Volontairement strict : le conditionnement (« C/10 », « F/12 », « B/2,5kg »)
    est du colisage d'achat, pas un format, et n'a rien a faire ici.
    """
    if categorie not in FORMAT_ELIGIBLE:
        return ''
    # « 33 CL » et « 1,5 L » s'ecrivent de plusieurs facons dans les listes.
    texte = unicodedata.normalize('NFKD', designation).encode('ascii', 'ignore').decode()
    texte = texte.upper().replace(',', '.')
    texte = re.sub(r'(?<=\d)\s+(?=(?:CL|ML|KG|G|L)\b)', '', texte)
    for valeur in FORMATS:
        if re.search(r'(?<![\w.])' + re.escape(valeur) + r'(?![\w.])', texte):
            return valeur
    return ''


def lire(nom):
    chemin = SOURCES / nom
    if not chemin.exists():
        return []
    with open(chemin, encoding='utf-8', newline='') as f:
        return [r for r in csv.DictReader(f) if r.get('Designation', '').strip()]


def normaliser(texte):
    texte = unicodedata.normalize('NFKD', texte).encode('ascii', 'ignore').decode()
    return re.sub(r'[^A-Z0-9]+', ' ', texte.upper()).strip()


def construire():
    lignes = []      # dicts prets a ecrire
    alertes = []     # (source, designation, motif) a relire humainement

    # --- Listing 2 : restaurant + cafeteria ---------------------------------
    for row in lire('listing_restaurant_cafeteria.csv'):
        n = int(row['N'])
        categorie = categorie_listing(n, row['Section'].strip())
        designation = row['Designation'].strip()
        if not categorie:
            alertes.append(('listing', designation, 'section non mappee : %s' % row['Section']))
            continue
        lignes.append({
            'Nom': designation,
            'Categorie_Suggeree': categorie,
            'Type': 'Storable',
            'Format': format_controle(designation, categorie),
            'Variante': '',
            'Source': 'listing_restaurant_cafeteria',
            'Ligne': n,
        })
    # --- Bureau : granularite de la liste brute -----------------------------
    for row in lire('liste_articles_HIS.csv'):
        designation = row['Designation'].strip()
        designation = CORRECTIONS.get(designation, designation)
        categorie = MENAGE if HYGIENE.search(designation) else BUREAUTIQUE
        lignes.append({
            'Nom': designation,
            'Categorie_Suggeree': categorie,
            'Type': 'Storable',
            'Format': format_controle(designation, categorie),
            'Variante': '',
            'Source': 'liste_articles_HIS',
            'Ligne': int(row['N']),
        })
        # Designations visiblement tronquees a la saisie (« ... A4 25 X »).
        if re.search(r'\b(X|REF)\s*/?\s*$', designation):
            alertes.append(('liste_articles_HIS', designation, 'designation possiblement tronquee'))

    # --- Cotex : 4 articles ecrits deux fois --------------------------------
    for row in lire('articles_cotex.csv'):
        if row['Section'].strip() != 'Cotex bon de livraison':
            continue  # nommage « facture » des memes 4 articles
        designation = row['Designation'].strip()
        lignes.append({
            'Nom': designation,
            'Categorie_Suggeree': MENAGE,
            'Type': 'Storable',
            'Format': format_controle(designation, MENAGE),
            'Variante': '',
            'Source': 'articles_cotex',
            'Ligne': int(row['N']),
        })

    # --- Controles ----------------------------------------------------------
    vus = {}
    for ligne in lignes:
        cle = normaliser(ligne['Nom'])
        if cle in vus:
            alertes.append((ligne['Source'], ligne['Nom'],
                            'doublon de « %s »' % vus[cle]))
        else:
            vus[cle] = ligne['Nom']

    # La liste bureau classee ne sert pas de source, mais rien ne doit lui
    # echapper : chaque entree doit se retrouver dans la liste brute.
    mots_bruts = {m for ligne in lignes for m in normaliser(ligne['Nom']).split()}
    for row in lire('liste_fournitures_bureau.csv'):
        tete = normaliser(row['Designation'])
        significatifs = [m for m in tete.split() if len(m) > 3][:2]
        if significatifs and not all(m in mots_bruts for m in significatifs):
            alertes.append(('liste_fournitures_bureau', row['Designation'],
                            'presente dans la liste classee, introuvable dans la brute'))

    return lignes, alertes


def ecrire(lignes):
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    colonnes = ['Nom', 'Categorie_Suggeree', 'Type', 'Format', 'Variante', 'Source', 'Ligne']
    with open(SORTIE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=colonnes)
        writer.writeheader()
        writer.writerows(lignes)


def _autotest():
    assert categorie_listing(23, 'Agro alimentaire') == ALIMENTATIONS, "conserve piment != epice"
    assert categorie_listing(94, 'Agro alimentaire') == EPICES
    assert categorie_listing(112, 'Produit laitier') == ALIMENTATIONS
    assert categorie_listing(134, 'Poulet') == VIANDES
    assert categorie_listing(139, 'Poulet') == ALIMENTATIONS, "les oeufs ne sont pas de la viande"
    assert categorie_listing(190, 'Gateaux et chocolat') == CHOCOLAT
    assert categorie_listing(165, 'Gateaux et chocolat') == BISCUITS
    assert categorie_listing(173, 'Gateaux et chocolat') == DIVERS, "chantilly = vrac"
    assert categorie_listing(204, 'Emballage') == EMBALLAGE

    assert format_controle('Schweppes PET 33CL F/12', BOISSONS) == '33CL'
    assert format_controle('Hamoud PET 33 CL F/12', BOISSONS) == '33CL', "espace avant l'unite"
    assert format_controle('JUS TCHINA 2L F/6', BOISSONS) == '2L'
    assert format_controle('Farine MAMA 25KG', ALIMENTATIONS) == '25KG'
    # Categorie non eligible : aucun format, meme si la designation en porte un.
    assert format_controle('RAME EXTRA A4 80G TARGET', BUREAUTIQUE) == ''
    # Valeurs absentes de la liste controlee : on n'invente pas.
    assert format_controle('Schweppes Canette 14 CL F/24', BOISSONS) == ''
    assert format_controle('Riz basmatti SAC 10Kg', ALIMENTATIONS) == ''
    assert format_controle('Eau GUIDILA 0,5L F/12', BOISSONS) == ''
    # Le conditionnement ne doit jamais etre lu comme un format.
    assert format_controle('Pate Rossort Sim C/10', ALIMENTATIONS) == ''

    # Les designations tronquees de la liste brute sont completees.
    assert CORRECTIONS['SAC A CADEAU BLANCHE A4 25 X'].endswith('37 CM')
    print("autotest : OK")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test', action='store_true', help="controles internes puis sortie")
    args = parser.parse_args()
    if args.test:
        _autotest()
        return

    lignes, alertes = construire()
    ecrire(lignes)

    repartition = {}
    for ligne in lignes:
        repartition[ligne['Categorie_Suggeree']] = repartition.get(ligne['Categorie_Suggeree'], 0) + 1

    print("%d articles ecrits dans %s" % (len(lignes), SORTIE))
    print()
    for categorie, nombre in sorted(repartition.items(), key=lambda x: -x[1]):
        print("  %-32s %4d" % (categorie, nombre))
    avec_format = sum(1 for l in lignes if l['Format'])
    print("\n  %d articles portent un Format de la liste controlee" % avec_format)

    if alertes:
        print("\n=== %d point(s) a relire ===" % len(alertes))
        for source, designation, motif in alertes:
            print("  [%s] %s | %s" % (source, designation[:48], motif))


if __name__ == '__main__':
    main()
