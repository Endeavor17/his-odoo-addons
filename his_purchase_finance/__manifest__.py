# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Achats - Controles Finance",
    "version": "19.0.1.0.0",
    "category": "Supply Chain/Purchase",
    "summary": "Commande confirmee par la Finance, dossier fournisseur, rapprochement facture, preuve de paiement",
    "description": """
Controles du Departement Finance sur les achats
(docs/superpowers/specs/2026-11-22-purchase-finance-controls-design.md) :

- l'acheteur envoie la commande a la Finance, qui seule la confirme ; motif
  du choix toujours demande, regle des 3 devis a partir de 100 000 DA HT ;
- dossier fournisseur (4 statuts, pieces avec echeance) : seule la
  confirmation finale attend un fournisseur valide ; pas de paiement vers un
  compte bancaire non approuve ;
- rapprochement commande / reception / facture sans tolerance : une facture
  non conforme est mise en reserve et bloquee au paiement ;
- attestation de service fait par le departement ;
- preuve jointe a chaque paiement fournisseur, evaluation des fournisseurs ;
- journaux et sous-comptes d'achat de la procedure.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": ["his_purchase", "account", "purchase_stock"],
    "data": [
        "security/his_purchase_finance_security.xml",
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
        "views/purchase_order_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
