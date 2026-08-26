"""Import Seed_Catalogue_Produits.csv as NEW products (fresh catalog, not a
migration of the 1 301 legacy fiches). Run via `odoo shell -d his_dev`.

Chaque ligne passe par le create() reel de product.template : c'est la
gouvernance MDM deja testee (his_stock_mdm) qui arbitre, pas une reimplementation
ici. Une ligne rejetee est annulee via savepoint et n'affecte pas les autres.
"""
import csv

SEED_PATH = '/mnt/host-downloads/Seed_Catalogue_Produits.csv'
REF_PATH = '/mnt/host-downloads/Categories_Reference_57.csv'
RETAIL_PREFIX = 'All / Retail & Consommables (Storable) / '
RETAIL_ROOT = 'All / Retail & Consommables (Storable)'

Category = env['product.category']
Template = env['product.template']
AttrValue = env['product.attribute.value']

# --- Chargement de la reference (source de verite des 57 chemins valides) ---
with open(REF_PATH, encoding='utf-8-sig', newline='') as f:
    valid_paths = {row['Chemin_Categorie_Complet'] for row in csv.DictReader(f)}

format_attr = env.ref('his_stock_mdm.attribute_format')
format_values_by_name = {v.name: v for v in format_attr.value_ids}

with open(SEED_PATH, encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))

accepted = []
rejected = []  # (nom, motif)

for row in rows:
    name = row['Nom'].strip()
    categ_suggeree = row['Categorie_Suggeree'].strip()
    type_ = row['Type'].strip()
    fmt = row['Format'].strip()
    variante = row['Variante'].strip()

    full_path = RETAIL_PREFIX + ' / '.join(categ_suggeree.split('/'))

    if full_path not in valid_paths:
        rejected.append((name, "categorie absente des 57 references : %s" % full_path))
        continue

    categ = Category.search([('complete_name', '=', full_path)], limit=1)
    if not categ:
        rejected.append((name, "categorie non trouvee en base (pourtant dans la reference) : %s" % full_path))
        continue

    if type_ == 'Storable':
        vals = {
            'name': name,
            'categ_id': categ.id,
            'type': 'consu',
            'is_storable': True,
            # Rule MDM 3 : prix obligatoire si stockable + vendable. Prix_Vente
            # est laisse vide par consigne (repricing ulterieur) : le produit
            # est donc cree non vendable pour ne pas violer la regle avec un
            # prix a 0 invente. A reactiver (sale_ok=True) une fois le prix saisi.
            'sale_ok': False,
            'list_price': 0.0,
        }
    elif type_ == 'Service':
        vals = {
            'name': name,
            'categ_id': categ.id,
            'type': 'service',
            'is_storable': False,
            # Sans ce champ, Odoo applique son propre defaut (1.0) : Prix_Vente
            # doit rester vide par consigne, comme pour les fiches stockables.
            'list_price': 0.0,
        }
    else:
        rejected.append((name, "type inconnu : %s" % type_))
        continue

    savepoint = env.cr.savepoint()
    try:
        template = Template.create(vals)
        if fmt:
            value = format_values_by_name.get(fmt)
            if not value:
                raise ValueError("valeur Format « %s » absente de la liste controlee" % fmt)
            env['product.template.attribute.line'].create({
                'product_tmpl_id': template.id,
                'attribute_id': format_attr.id,
                'value_ids': [(6, 0, value.ids)],
            })
        if variante:
            # Aucune ligne du seed n'utilise Variante a ce jour ; pas de logique
            # de creation de valeur libre ecrite tant qu'aucun cas reel n'existe.
            raise ValueError("Variante « %s » non geree (aucun cas dans ce seed)" % variante)
    except Exception as exc:
        savepoint.close(rollback=True)
        rejected.append((name, str(exc).split('\n')[0]))
    else:
        savepoint.close(rollback=False)
        accepted.append((name, template.default_code))

env.cr.commit()

print("=== RESUME IMPORT ===")
print("Acceptes :", len(accepted))
print("Rejetes  :", len(rejected))
print()
print("=== REJETS (nom | motif) ===")
for name, reason in rejected:
    print("%s | %s" % (name, reason))
