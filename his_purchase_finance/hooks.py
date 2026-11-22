# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Journaux et sous-comptes d'achat de la procedure Finance (PROC-ACH, partie 3).

Ajoute seulement ce qui manque : le plan l10n_dz porte deja 300000, 380000,
401000... (codes completes a 6 chiffres), la CI charge le plan generique.
Codes de journaux en 4 lettres : Odoo les limite a 5 (ACH-GEN n'y tient pas).
L'affectation aux categories d'articles reste au Departement Finance.
"""

import logging

_logger = logging.getLogger(__name__)

STOCK = "asset_current"
EXPENSE = "expense"
PAYABLE = "liability_payable"

# Libelles de la procedure (381xxx / 382xxx completes sur le modele des 380xxx).
ACCOUNTS = [
    ("300000", "Stocks de marchandises – Général", STOCK),
    ("300100", "Stocks de marchandises – Copy Center", STOCK),
    ("300200", "Stocks de marchandises – Cafétéria", STOCK),
    ("300300", "Stocks de marchandises – Restaurant", STOCK),
    ("310000", "Matières premières – Général", STOCK),
    ("310200", "Matières premières – Cafétéria", STOCK),
    ("310300", "Matières premières – Restaurant", STOCK),
    ("320000", "Autres approvisionnements – Général", STOCK),
    ("320100", "Autres approvisionnements – Copy Center", STOCK),
    ("320200", "Autres approvisionnements – Cafétéria", STOCK),
    ("320300", "Autres approvisionnements – Restaurant", STOCK),
    ("380000", "Achats de marchandises stockés – Général", STOCK),
    ("380100", "Achats de marchandises stockés – Copy Center", STOCK),
    ("380200", "Achats de marchandises stockés – Cafétéria", STOCK),
    ("380300", "Achats de marchandises stockés – Restaurant", STOCK),
    ("381000", "Achats de matières premières stockées – Général", STOCK),
    ("381200", "Achats de matières premières stockées – Cafétéria", STOCK),
    ("381300", "Achats de matières premières stockées – Restaurant", STOCK),
    ("382000", "Achats d'autres approvisionnements stockés – Général", STOCK),
    ("382100", "Achats d'autres approvisionnements stockés – Copy Center", STOCK),
    ("382200", "Achats d'autres approvisionnements stockés – Cafétéria", STOCK),
    ("382300", "Achats d'autres approvisionnements stockés – Restaurant", STOCK),
    ("600000", "Consommation de marchandises – Général", EXPENSE),
    ("600100", "Consommation de marchandises – Copy Center", EXPENSE),
    ("600200", "Consommation de marchandises – Cafétéria", EXPENSE),
    ("600300", "Consommation de marchandises – Restaurant", EXPENSE),
    ("601000", "Consommation de matières premières – Général", EXPENSE),
    ("601200", "Consommation de matières premières – Cafétéria", EXPENSE),
    ("601300", "Consommation de matières premières – Restaurant", EXPENSE),
    ("602000", "Consommation d'autres approvisionnements – Général", EXPENSE),
    ("602100", "Consommation d'autres approvisionnements – Copy Center", EXPENSE),
    ("602200", "Consommation d'autres approvisionnements – Cafétéria", EXPENSE),
    ("602300", "Consommation d'autres approvisionnements – Restaurant", EXPENSE),
    ("401000", "Fournisseurs de stocks", PAYABLE),
    ("401200", "Fournisseurs de services", PAYABLE),
    ("404000", "Fournisseurs d'immobilisations", PAYABLE),
]

JOURNALS = [
    ("AGEN", "Achats généraux – Société (ACH-GEN)"),
    ("ACOP", "Achats – Copy Center (ACH-COP)"),
    ("ACAF", "Achats – Cafétéria (ACH-CAF)"),
    ("ARES", "Achats – Restaurant (ACH-RES)"),
]


def setup_accounts(env, company):
    """Cree les comptes et journaux manquants de `company` ; sans plan comptable, ne fait rien."""
    if not company.chart_template:
        _logger.warning(
            "his_purchase_finance: %s has no chart of accounts, purchase accounts not created.", company.name
        )
        return
    Account = env["account.account"].with_company(company)
    for code, name, account_type in ACCOUNTS:
        if not Account.search_count([("code", "=", code), ("company_ids", "in", company.id)]):
            Account.create(
                {
                    "code": code,
                    "name": name,
                    "account_type": account_type,
                    "reconcile": account_type == PAYABLE,
                    "company_ids": [(6, 0, company.ids)],
                }
            )
    Journal = env["account.journal"]
    for code, name in JOURNALS:
        if not Journal.search_count([("code", "=", code), ("company_id", "=", company.id)]):
            Journal.create({"code": code, "name": name, "type": "purchase", "company_id": company.id})


def post_init_hook(env):
    for company in env["res.company"].search([]):
        setup_accounts(env, company)
