"""Import Seed_Catalogue_Produits.csv as NEW products (fresh catalog, not a
migration of the 1 301 legacy fiches). Run via `odoo shell -d his_dev`.

Chaque ligne passe par le create() reel de product.template : c'est la
gouvernance MDM deja testee (his_stock_mdm) qui arbitre, pas une reimplementation
ici. Une ligne rejetee est annulee via savepoint et n'affecte pas les autres.
"""

import csv
import os

# Par defaut le seed et le referentiel du depot, monte en /mnt/extra-addons :
# plus besoin du montage /mnt/host-downloads, absent du docker-compose.yml.
# Surchargeables par variable d'environnement pour rejouer un ancien seed.
SEED_PATH = os.environ.get("SEED_PATH", "/mnt/extra-addons/tools/seed/Seed_Catalogue_v2.csv")
REF_PATH = os.environ.get("REF_PATH", "/mnt/extra-addons/tools/seed/Categories_Reference.csv")
RETAIL_PREFIX = "All / Retail & Consommables (Storable) / "
RETAIL_ROOT = "All / Retail & Consommables (Storable)"

Category = env["product.category"]
Template = env["product.template"]
AttrValue = env["product.attribute.value"]

# --- Chargement de la reference (source de verite des 57 chemins valides) ---
with open(REF_PATH, encoding="utf-8-sig", newline="") as f:
    valid_paths = {row["Chemin_Categorie_Complet"] for row in csv.DictReader(f)}

format_attr = env.ref("his_stock_mdm.attribute_format")
format_values_by_name = {v.name: v for v in format_attr.value_ids}

with open(SEED_PATH, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

accepted = []
rejected = []  # (nom, motif)
skipped = []  # deja en base : le script doit rester rejouable a chaque
# nouvelle liste fournisseur sans dupliquer l'existant.

existing_names = set(Template.search([]).mapped("name"))
updated = []  # fiches existantes mises a jour (fusion Copy Center)
archived = []  # fiches fusionnees dans une autre, archivees
kept_apart = []  # fiches fusionnees qui ont encore du stock : a traiter a la main

# --- Colonnes de la fusion Copy Center ------------------------------------
#
# Une ligne fusionnee porte sa reference INV- pre-attribuee, son prix, son
# cout, le libelle fournisseur (description d'achat) et ses ANCIENS noms : sur
# une base ou l'article existe deja sous le libelle fournisseur, l'import le
# retrouve par eux et le met a jour au lieu d'en creer un second.
copy_config = env.ref("his_stock_mdm.pos_config_copy_center", raise_if_not_found=False)
ream_uom = env.ref("his_pos_copy_center.uom_rame_500", raise_if_not_found=False)
pos_by_name = {"Articles Bureautique": env.ref("his_stock_mdm.pos_categ_fournitures", raise_if_not_found=False)}


def pos_category(label):
    if not label:
        return None
    if label not in pos_by_name or not pos_by_name[label]:
        PosCateg = env["pos.category"]
        pos_by_name[label] = PosCateg.search([("name", "=", label)], limit=1) or PosCateg.create({"name": label})
        if copy_config and copy_config.limit_categories:
            copy_config.iface_available_categ_ids = [(4, pos_by_name[label].id)]
    return pos_by_name[label]


def fusion_vals(row):
    vals = {}
    price = float(row.get("Prix_Vente") or 0)
    if price > 0:
        vals.update({"list_price": price, "sale_ok": True, "available_in_pos": True})
    if float(row.get("Cout") or 0) > 0:
        vals["standard_price"] = float(row["Cout"])
    if row.get("Description_Achat"):
        vals["description_purchase"] = row["Description_Achat"]
    categ = pos_category(row.get("Categorie_POS", "").strip())
    if categ:
        vals["pos_categ_ids"] = [(4, categ.id)]
    if row.get("Groupe_Papier") and ream_uom:
        vals["uom_ids"] = [(4, ream_uom.id)]
    return vals


def find_existing(row):
    """La fiche deja en base pour cette ligne, et celles qu'elle absorbe.

    Par NOM d'abord (le nouveau, puis les anciens). La reference ne sert qu'a
    departager : les codes INV- pre-attribues ne designent PAS les memes
    articles sur une base dont les codes ont ete tires localement (staging,
    poste de dev). Une fiche trouvee par sa reference mais dont le nom n'est
    aucun des noms de la ligne n'est pas la bonne.
    """
    Any = Template.with_context(active_test=False)
    reference = row.get("Reference", "").strip()
    names = [row["Nom"].strip()] + [n.strip() for n in row.get("Ancien_Noms", "").split(" | ") if n.strip()]
    candidates = Any.search([("name", "in", names)])
    if not candidates:
        return Any, Any
    by_code = candidates.filtered(lambda t: reference and t.default_code == reference)
    by_rank = sorted(candidates, key=lambda t: names.index(t.name))
    found = by_code[:1] or by_rank[0]
    return found, candidates - found


# Les lignes sans reference recoivent un code de la sequence MDM. Sur une base
# neuve elle part de INV-000001 et heurterait les codes pre-attribues des lignes
# qui en portent un (« Eau Besbassa » tirait INV-000819, deja pose sur un
# article Copy Center : 243 refus a la repetition du 2026-10-29). La sequence
# part donc d'abord apres la plus haute reference du seed.
sequence = env.ref("his_stock_mdm.seq_product_internal_reference", raise_if_not_found=False)
seed_codes = [r.get("Reference", "").strip() for r in rows]
seed_highest = max((int(c[4:]) for c in seed_codes if c.startswith("INV-") and c[4:].isdigit()), default=0)
if sequence and sequence.number_next_actual <= seed_highest:
    sequence.sudo().number_next_actual = seed_highest + 1

for row in rows:
    name = row["Nom"].strip()
    if row.get("Reference") or row.get("Ancien_Noms"):
        found, others = find_existing(row)
        if found:
            savepoint = env.cr.savepoint()
            try:
                vals = {"name": name, **fusion_vals(row)}
                barcode = row.get("Code_Barres", "").strip()
                if barcode and not env["product.product"].search_count(
                    [("barcode", "=", barcode), ("product_tmpl_id", "!=", found.id)]
                ):
                    vals["barcode"] = barcode
                found.write(vals)
                for other in others.filtered("active"):
                    if other.qty_available > 0:
                        kept_apart.append("%s (%s en stock)" % (other.name, other.qty_available))
                    else:
                        other.action_archive()
                        archived.append(other.name)
            except Exception as exc:
                savepoint.close(rollback=True)
                rejected.append((name, str(exc).split("\n")[0]))
            else:
                savepoint.close(rollback=False)
                updated.append(name)
            continue
    elif name in existing_names:
        skipped.append(name)
        continue
    categ_suggeree = row["Categorie_Suggeree"].strip()
    type_ = row["Type"].strip()
    fmt = row["Format"].strip()
    variante = row["Variante"].strip()
    barcode = row.get("Code_Barres", "").strip()

    full_path = RETAIL_PREFIX + " / ".join(categ_suggeree.split("/"))

    if full_path not in valid_paths:
        rejected.append((name, "categorie absente des 57 references : %s" % full_path))
        continue

    categ = Category.search([("complete_name", "=", full_path)], limit=1)
    if not categ:
        rejected.append((name, "categorie non trouvee en base (pourtant dans la reference) : %s" % full_path))
        continue

    if type_ == "Storable":
        vals = {
            "name": name,
            "categ_id": categ.id,
            "type": "consu",
            "is_storable": True,
            # Rule MDM 3 : prix obligatoire si stockable + vendable. Prix_Vente
            # est laisse vide par consigne (repricing ulterieur) : le produit
            # est donc cree non vendable pour ne pas violer la regle avec un
            # prix a 0 invente. A reactiver (sale_ok=True) une fois le prix saisi.
            "sale_ok": False,
            "list_price": 0.0,
        }
        if barcode:
            # Champ natif product.product ; Odoo en controle l'unicite en
            # Python (_check_barcode_uniqueness), y compris contre le colisage.
            vals["barcode"] = barcode
    elif type_ == "Service":
        vals = {
            "name": name,
            "categ_id": categ.id,
            "type": "service",
            "is_storable": False,
            # Sans ce champ, Odoo applique son propre defaut (1.0) : Prix_Vente
            # doit rester vide par consigne, comme pour les fiches stockables.
            "list_price": 0.0,
        }
    else:
        rejected.append((name, "type inconnu : %s" % type_))
        continue

    reference = row.get("Reference", "").strip()
    # Un code deja pris par un autre article (base aux codes tires localement)
    # n'est jamais reutilise : le MDM en tire un neuf.
    if reference and not env["product.product"].with_context(active_test=False).search_count(
        [("default_code", "=", reference)]
    ):
        vals["default_code"] = reference
    if type_ == "Service" and float(row.get("Prix_Vente") or 0) > 0:
        vals["sale_ok"] = True

    savepoint = env.cr.savepoint()
    try:
        template = Template.create(vals)
        extra = fusion_vals(row)
        if extra:
            template.write(extra)
        if fmt:
            value = format_values_by_name.get(fmt)
            if not value:
                raise ValueError("valeur Format « %s » absente de la liste controlee" % fmt)
            env["product.template.attribute.line"].create(
                {
                    "product_tmpl_id": template.id,
                    "attribute_id": format_attr.id,
                    "value_ids": [(6, 0, value.ids)],
                }
            )
        if variante:
            # Aucune ligne du seed n'utilise Variante a ce jour ; pas de logique
            # de creation de valeur libre ecrite tant qu'aucun cas reel n'existe.
            raise ValueError("Variante « %s » non geree (aucun cas dans ce seed)" % variante)
    except Exception as exc:
        savepoint.close(rollback=True)
        rejected.append((name, str(exc).split("\n")[0]))
    else:
        savepoint.close(rollback=False)
        accepted.append((name, template.default_code))

# La sequence MDM doit repartir apres la plus haute reference posee a la main,
# sinon la prochaine fiche creee recevrait un code deja pris. C'est la sequence
# PostgreSQL qui compte (implementation standard), number_next_actual l'ecrit.
sequence = env.ref("his_stock_mdm.seq_product_internal_reference", raise_if_not_found=False)
if sequence:
    codes = Template.with_context(active_test=False).search([("default_code", "=like", "INV-%")]).mapped("default_code")
    highest = max((int(c[4:]) for c in codes if c[4:].isdigit()), default=0)
    if sequence.number_next_actual <= highest:
        sequence.sudo().number_next_actual = highest + 1

env.cr.commit()

print("=== RESUME IMPORT ===")
print("Acceptes     :", len(accepted))
print("Mis a jour   :", len(updated))
print("Archives     :", len(archived), "(fusionnes dans une autre fiche)")
for line in kept_apart:
    print("A TRAITER    : fusionne mais encore en stock :", line)
print("Deja en base :", len(skipped))
print("Rejetes      :", len(rejected))
print("Codes-barres :", sum(1 for r in rows if r.get("Code_Barres", "").strip()))
print()
print("=== REJETS (nom | motif) ===")
for name, reason in rejected:
    print("%s | %s" % (name, reason))

# --- Mise en vente au comptoir ------------------------------------------
#
# available_in_pos et pos_categ_ids ne sont PAS derives du seed : ils se
# deduisent de la categorie produit, et doivent valoir aussi pour les fiches
# importees lors d'un passage precedent. Cette passe balaie donc tout le
# catalogue a chaque execution, et reste sans effet si rien n'a change.
#
# Ne sont vendables que les familles reellement proposees a un etudiant. Les
# ingredients de cuisine, l'entretien et les emballages de service en sont
# volontairement absents : ils se consomment, ils ne se vendent pas.
POS_PAR_CATEGORIE = {
    "Café / Boissons": "pos_categ_boissons",
    "Café / Snacks": "pos_categ_snacks",
    "Café / Chocolat": "pos_categ_chocolat",
    "Café / Biscuits & Gâteaux": "pos_categ_biscuits",
    "Café / Bonbons": "pos_categ_bonbons",
    "Café / Divers": "pos_categ_divers",
    "Copy / Articles Bureautique": "pos_categ_fournitures",
}

mis_en_vente = 0
for suffixe, xmlid in POS_PAR_CATEGORIE.items():
    categ = Category.search([("complete_name", "=", RETAIL_PREFIX + suffixe)], limit=1)
    if not categ:
        continue
    pos_categ = env.ref("his_stock_mdm." + xmlid)
    a_traiter = Template.search(
        [
            ("categ_id", "=", categ.id),
            "|",
            ("available_in_pos", "=", False),
            ("pos_categ_ids", "not in", pos_categ.ids),
        ]
    )
    if a_traiter:
        a_traiter.write(
            {
                "available_in_pos": True,
                "pos_categ_ids": [(4, pos_categ.id)],
            }
        )
        mis_en_vente += len(a_traiter)

env.cr.commit()
print()
print("Mis en vente au comptoir :", mis_en_vente)

# --- Mise en vente effective --------------------------------------------
#
# Le domaine de chargement du POS exige available_in_pos ET sale_ok
# (product_template._load_pos_data_domain). Or l'import cree tout en
# sale_ok=False, pour ne pas violer la regle MDM « prix obligatoire si
# stockable et vendable » avec un prix a 0 invente.
#
# Consequence : saisir un prix ne suffit pas, rien ne rebascule l'article, et
# il reste invisible en caisse. C'est cette passe qui ferme la boucle.
#
# La regle MDM n'est pas contournee, elle est respectee dans l'autre sens : un
# article sans prix reste non vendable, et c'est voulu -- une caisse ne doit
# pas pouvoir encaisser 0 DA par inadvertance.
# Depuis his_stock_mdm 1.4.0, la meme regle vaut aussi pour les saisies manuelles.
a_vendre = Template.search(
    [
        ("available_in_pos", "=", True),
        ("sale_ok", "=", False),
        ("list_price", ">", 0),
    ]
)
if a_vendre:
    a_vendre.write({"sale_ok": True})

env.cr.commit()
print("Bascules en vente (prix saisi) :", len(a_vendre))
