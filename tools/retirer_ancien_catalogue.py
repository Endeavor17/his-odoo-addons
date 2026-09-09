"""Retire l'ancien catalogue avant d'importer le nouveau. Via `odoo shell`.

    odoo shell -d <base> --no-http < tools/retirer_ancien_catalogue.py

Archive par defaut. Pour supprimer reellement :

    MODE=supprimer odoo shell -d <base> --no-http < tools/retirer_ancien_catalogue.py

POURQUOI ARCHIVER PLUTOT QUE SUPPRIMER
--------------------------------------
Sur une base de travail vierge, supprimer est propre : rien ne s'y rattache.
Sur une base vivante, un article vendu porte des lignes de caisse, des
mouvements de stock et des ecritures comptables. Odoo refuse alors de le
supprimer, et il a raison : effacer un produit vendu detruirait la piste
comptable.

Un article archive disparait des caisses et des listes exactement comme s'il
n'existait plus -- c'est ce qu'on veut -- mais son historique reste lisible et
l'operation se defait d'un clic.

Le script mesure d'abord et affiche ce qui rattache les articles a la vie de
l'entreprise. Si ces compteurs ne sont pas nuls, la suppression est a exclure.

CE QUI EST TOUJOURS EPARGNE
---------------------------
Les produits repas (forfaits et repas d'Abdo), et les produits speciaux des
caisses -- le pourboire notamment, qu'Odoo refuse d'archiver tant qu'une
configuration POS le designe.
"""
import os

MODE = os.environ.get('MODE', 'archiver')
Template = env['product.template']
Product = env['product.product']


def compter(modele, champ, libelle):
    lignes = env[modele].search([])
    produits = lignes.mapped(champ)
    return libelle, len(produits.mapped('product_tmpl_id'))


print("=== CE QUI RATTACHE LES ARTICLES A LA VIE DE L'ENTREPRISE ===")
mesures = []
for modele, champ, libelle in (
    ('stock.quant', 'product_id', 'articles avec du stock'),
    ('stock.move', 'product_id', 'articles avec un mouvement'),
    ('pos.order.line', 'product_id', 'articles vendus en caisse'),
):
    try:
        mesures.append(compter(modele, champ, libelle))
    except Exception as exc:
        mesures.append((libelle, "illisible (%s)" % str(exc)[:40]))
for libelle, valeur in mesures:
    print("  %-32s %s" % (libelle, valeur))

# Les produits du module repas ne font pas partie du catalogue a retirer.
domaine = []
if 'meal_credits' in Template._fields:
    domaine = [('meal_credits', '=', 0), ('meal_credit_cost', '=', 0)]
cibles = Template.search(domaine)

# Un produit special d'une caisse (pourboire, remise) casse le POS s'il part.
speciaux = env['pos.config'].search([])._get_special_products().product_tmpl_id
cibles -= speciaux

# Odoo refuse de supprimer un produit disponible en caisse tant qu'une session
# est ouverte. Sans ce controle on obtient une ligne d'erreur identique par
# article -- 916 fois le meme message -- au lieu de la seule chose a faire.
ouvertes = env['pos.session'].search([('state', '!=', 'closed')])
if ouvertes and MODE == 'supprimer':
    print()
    print("=== ARRET : %d session(s) de caisse ouverte(s) ===" % len(ouvertes))
    for s in ouvertes:
        print("  %-28s %s" % (s.config_id.name, s.name))
    print()
    print("Odoo interdit de supprimer un article disponible en caisse tant qu'une")
    print("session est ouverte. Deux issues :")
    print("  - fermer ces sessions (Point de vente > Sessions > Fermer), puis relancer ;")
    print("  - ou lancer sans MODE=supprimer : l'archivage, lui, n'est pas bloque.")
    raise SystemExit(1)

print()
print("=== %s ===" % ('SUPPRESSION' if MODE == 'supprimer' else 'ARCHIVAGE'))
print("articles en base :", Template.search_count([]))
print("cibles           :", len(cibles), "(%d epargnes : repas et produits speciaux)"
      % (Template.search_count([]) - len(cibles)))

traites, bloques = 0, []
for tmpl in cibles:
    nom = tmpl.name
    savepoint = env.cr.savepoint()
    try:
        if MODE == 'supprimer':
            tmpl.unlink()
        else:
            tmpl.active = False
    except Exception as exc:
        savepoint.close(rollback=True)
        bloques.append((nom, str(exc).split('\n')[0][:90]))
    else:
        savepoint.close(rollback=False)
        traites += 1

env.cr.commit()
print()
print("traites :", traites)
print("bloques :", len(bloques))
for nom, motif in bloques[:20]:
    print("  %-42s | %s" % (nom[:42], motif))
if len(bloques) > 20:
    print("  ... et %d autres" % (len(bloques) - 20))
