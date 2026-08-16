"""Recree l'arborescence de categories telle qu'elle existe en production,
pour que le module puisse s'y rattacher comme il le fera sur la vraie base."""
ROOT = "Retail & Consommables (Storable)"
TREE = {
    "Book": [],
    "Café": ["Biscuits & Gâteaux", "Boissons", "Bonbons", "Chocolat", "Divers", "Snacks"],
    "Copy": ["Articles Bureautique", "Flexy", "Impression", "Photocopie", "Scan"],
    "Ménage & Nettoyage": [],
    "Restaurant": ["Alimentations", "Épices", "Fruits", "Légumes", "Viandes"],
}

Categ = env['product.category']


def ensure(name, parent=None):
    domain = [('name', '=', name), ('parent_id', '=', parent.id if parent else False)]
    return Categ.search(domain, limit=1) or Categ.create({
        'name': name, 'parent_id': parent.id if parent else False})


root = ensure(ROOT)
for family, children in TREE.items():
    node = ensure(family, root)
    for child in children:
        ensure(child, node)

env.cr.commit()
print("CATEGORIES:", Categ.search_count([('complete_name', 'like', ROOT)]))
