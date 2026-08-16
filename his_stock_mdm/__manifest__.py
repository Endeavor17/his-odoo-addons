# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "MDM Produits, Stock & POS - Groupe HIS-HTC-IRA",
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': "Gouvernance du catalogue produit, structure multi-points de vente et valorisation",
    'description': """
Traduit en contraintes serveur et en donnees versionnees le MDM Produits/Stock/POS
du Groupe HIS-HTC-IRA (reference unique, categorie feuille, eligibilite des attributs,
tracabilite par categorie, valorisation FIFO/CUMP, motifs de perte, 3 points de vente).

Aucune reprise de donnees : les regles ne s'appliquent qu'aux creations et
modifications posterieures a l'installation.
    """,
    'author': "Groupe HIS-HTC-IRA",
    'license': 'LGPL-3',
    'depends': [
        'stock',
        'stock_account',
        'product_expiry',
        'point_of_sale',
    ],
    'data': [
        'data/ir_sequence_data.xml',
        'data/mdm_bind_data.xml',
        'data/product_category_data.xml',
        'data/product_attribute_data.xml',
        'data/stock_location_data.xml',
        'data/stock_scrap_reason_data.xml',
        'data/pos_config_data.xml',
        'views/mdm_views.xml',
    ],
    'installable': True,
}
