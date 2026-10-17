# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Identifiants algeriens des tiers - Groupe HIS-HTC-IRA",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "RC, NIF, NIS, AI, NIN et regime fiscal sur les fournisseurs et les societes",
    "description": """
Porte les identifiants legaux algeriens que le plan comptable l10n_dz ne
fournit pas : registre de commerce (RC), numero d'identification statistique
(NIS), article d'imposition (AI), numero d'identification national (NIN) des
personnes physiques, et le regime fiscal du tiers (reel avec TVA, IFU ou
auto-entrepreneur sans TVA). Le NIF vit dans le champ standard `vat`.

Utilise par his_purchase (fournisseurs) et imprimable sur tout document.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": ["account", "l10n_dz"],
    "data": [
        "views/res_partner_views.xml",
        "views/res_company_views.xml",
    ],
    "installable": True,
}
