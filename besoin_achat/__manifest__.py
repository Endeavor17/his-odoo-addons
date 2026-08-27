# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Besoin d'Achat",
    'version': '19.0.1.1.0',
    'category': 'Supply Chain/Purchase',
    'summary': "Expression et suivi des besoins d'achat avant la demande de prix",
    'description': """
Besoin d'Achat
===============
Ajoute à l'application Achats un processus d'expression de besoin d'achat,
en amont de la demande de prix (RFQ) :

Besoin d'achat -> Validation -> Consultation fournisseurs -> Sélection d'une offre -> RFQ -> Bon de commande
""",
    'depends': ['purchase'],
    'data': [
        'security/ir.model.access.csv',
        'data/besoin_achat_sequence.xml',
        'views/besoin_achat_views.xml',
        'views/purchase_order_views.xml',
        'views/product_template_views.xml',
    ],
    'application': False,
    'installable': True,
    'author': 'Custom',
    'license': 'LGPL-3',
}
