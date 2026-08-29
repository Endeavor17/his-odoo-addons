"""Recree l'arborescence de categories telle qu'elle existe en production,
pour que le module puisse s'y rattacher comme il le fera sur la vraie base.

La racine "All" et la sous-arborescence complete de Book (16 rayons) sont
confirmees par un export reel de product.category (Categories_Reference_57.csv,
2026-08-26) : la production a bien "All" comme racine, contrairement a ce que
recreait la version precedente de ce script."""
ROOT_NAME = "All"
RETAIL = "Retail & Consommables (Storable)"
TREE = {
    "Book": ["Administratif", "Arabe", "Droit", "Français", "General", "Histoire",
             "Informatique", "Livres En Anglais", "Memoires", "Religion", "Revus",
             "Science", "Science Economique", "Science Politique",
             "Science Psychologique", "Science de Communication"],
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


all_root = ensure(ROOT_NAME)
root = ensure(RETAIL, all_root)
for family, children in TREE.items():
    node = ensure(family, root)
    for child in children:
        ensure(child, node)

env.cr.commit()
print("CATEGORIES:", Categ.search_count([('complete_name', 'like', RETAIL)]))
