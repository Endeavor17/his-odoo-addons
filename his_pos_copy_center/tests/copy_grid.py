# La grille de copie reelle du Copy Center (affiche « TARIFS Photocopie &
# Impression » et feuille du comptoir, 2026-10-29).
#
# Copie litterale de tools/seed/copy_services.csv : les tests ne lisent pas
# tools/, et un controle du convertisseur verifie que les deux concordent.
# Une dimension a None n'est pas demandee pour ce produit (pas de couleur sur
# l'autocollant, le glace, le luxe et la photo).

COPY_GRID = [
    # (nom, service, papier, couleur, faces, prix, prix au-dela de 20 pages)
    ("Photocopie N&B Recto", "photocopie", "normal", "bw", "recto", 5.0, 0.0),
    ("Photocopie N&B Recto-verso", "photocopie", "normal", "bw", "duplex", 10.0, 0.0),
    ("Photocopie Couleur Recto", "photocopie", "normal", "color", "recto", 30.0, 0.0),
    ("Photocopie Couleur Recto-verso", "photocopie", "normal", "color", "duplex", 50.0, 0.0),
    ("Impression N&B Recto", "impression", "normal", "bw", "recto", 10.0, 8.0),
    ("Impression N&B Recto-verso", "impression", "normal", "bw", "duplex", 15.0, 10.0),
    ("Impression Couleur Recto", "impression", "normal", "color", "recto", 30.0, 0.0),
    ("Impression Couleur Recto-verso", "impression", "normal", "color", "duplex", 50.0, 0.0),
    ("Impression A5 N&B", "impression", "a5", "bw", "recto", 5.0, 0.0),
    ("Impression A5 Couleur", "impression", "a5", "color", "recto", 15.0, 0.0),
    ("Impression Bristol N&B", "impression", "bristol", "bw", "recto", 15.0, 0.0),
    ("Impression Bristol Couleur", "impression", "bristol", "color", "recto", 35.0, 0.0),
    ("Impression Papier Autocollant", "impression", "sticker", None, "recto", 80.0, 0.0),
    ("Impression Papier Glacé", "impression", "glossy", None, "recto", 50.0, 0.0),
    ("Impression Papier Luxe", "impression", "luxury", None, "recto", 80.0, 0.0),
    ("Impression Papier Photo", "impression", "photo", None, "recto", 50.0, 0.0),
]


def copy_product_vals(row):
    """Valeurs product.template d'une ligne de la grille."""
    name, service, paper, color, sides, price, bulk = row
    return {
        "name": name,
        "type": "service",
        "list_price": price,
        "available_in_pos": True,
        "sale_ok": True,
        "purchase_ok": False,
        "copy_service": service,
        "copy_paper": paper,
        "copy_color": color or False,
        "copy_sides": sides,
        "copy_bulk_price": bulk,
    }
