"""Cree les produits de photocopie d'une base de developpement.

Le builder du Copy Center resout un produit a partir de quatre choix (service,
format, couleur, recto/verso). Sur une base neuve les categories Copy sont
vides, donc le bouton « Copy job » reste cache et il n'y a rien a essayer.

Ce script n'est PAS un catalogue de reference : les prix sont des exemples. Le
vrai catalogue appartient au MDM, pas a ce script.

Usage :
    docker compose run --rm -T odoo odoo shell -d <base> --no-http \
        < tools/seed_copy_products.py
"""

# format, couleur, recto/verso, prix d'exemple
GRID = [
    ('a4', 'bw', 'recto', 10.0),
    ('a4', 'bw', 'duplex', 15.0),
    ('a4', 'color', 'recto', 40.0),
    ('a4', 'color', 'duplex', 70.0),
    ('a3', 'bw', 'recto', 20.0),
    ('a3', 'bw', 'duplex', 30.0),
    ('a3', 'color', 'recto', 80.0),
    ('a3', 'color', 'duplex', 140.0),
]

LABEL = {
    'a4': "A4", 'a3': "A3",
    'bw': "N&B", 'color': "Couleur",
    'recto': "Recto", 'duplex': "Recto-verso",
}

Product = env['product.template']
categ = env['product.category'].search([('name', '=', "Photocopie")], limit=1)

# Une caisse peut restreindre son catalogue (limit_categories). Le Copy Center
# de cette base le fait, sur des categories de demo Odoo, donc un produit sans
# categorie POS n'y arrive jamais : le POS affiche « No Product Yet? » et le
# bouton du builder reste cache. Creer la categorie POS et l'autoriser sur la
# caisse plutot que de lever la restriction, qui est un choix de gestion.
PosCateg = env['pos.category']
pos_categ = PosCateg.search([('name', '=', "Copy Center")], limit=1) or PosCateg.create({
    'name': "Copy Center",
})

created = 0
for fmt, color, sides, price in GRID:
    name = "Photocopie %s %s %s" % (LABEL[fmt], LABEL[color], LABEL[sides])
    existing = Product.search([
        ('copy_service', '=', 'photocopie'),
        ('copy_format', '=', fmt),
        ('copy_color', '=', color),
        ('copy_sides', '=', sides),
    ], limit=1)
    if existing:
        continue
    vals = {
        'name': name,
        'type': 'consu',
        'list_price': price,
        'available_in_pos': True,
        'sale_ok': True,
        'purchase_ok': False,
        'copy_service': 'photocopie',
        'copy_format': fmt,
        'copy_color': color,
        'copy_sides': sides,
        'pos_categ_ids': [(6, 0, [pos_categ.id])],
    }
    if categ:
        vals['categ_id'] = categ.id
    Product.create(vals)
    created += 1

# Le theme n'a rien d'obligatoire, mais une caisse Copy Center sans theme
# ressemble a Odoo standard et on ne voit pas ce qui a ete fait.
config = env['pos.config'].search([('name', 'ilike', 'Copy')], limit=1)
if config:
    if not config.his_pos_theme:
        config.his_pos_theme = 'copy_center'
    # Rattraper les produits deja crees par une execution precedente.
    Product.search([('copy_service', '!=', False)]).write({
        'pos_categ_ids': [(6, 0, [pos_categ.id])],
    })
    if config.limit_categories and pos_categ not in config.iface_available_categ_ids:
        config.iface_available_categ_ids = [(4, pos_categ.id)]

env.cr.commit()
print("Produits de photocopie crees : %s" % created)
print("Caisse thematisee : %s" % (config.display_name if config else "aucune trouvee"))
