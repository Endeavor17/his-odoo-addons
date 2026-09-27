from odoo import Command

# Identifiants du modele l10n_dz (resolus par societe : account.<id>_<nom>).
TVA_REVENTE = "l10n_dz_vat_sale_19_resale"
TVA_SUR_PLACE = "l10n_dz_vat_sale_19_on_site_consumption"
TVA_SERVICES = "l10n_dz_vat_sale_19_other_services"
# La taxe par defaut du modele dz : « production de biens », fausse pour HIS
# qui revend. C'est la seule qu'on remplace sur un produit deja taxe.
TVA_PRODUCTION = "l10n_dz_vat_sale_19_prod"


def post_init_hook(env):
    for company in env["res.company"].search([("account_fiscal_country_id.code", "=", "DZ")]):
        appliquer_tva(env, company)


def appliquer_tva(env, company):
    """Pose la TVA a 19 % comprise dans le prix sur ce que vendent les caisses.

    Idempotent : peut etre rejoue (migration, nouvelle societe). Ne fait rien
    si le plan comptable dz n'est pas charge sur la societe.
    """
    chart = env["account.chart.template"].with_company(company)
    revente, sur_place, services = (
        chart.ref(xmlid, raise_if_not_found=False) for xmlid in (TVA_REVENTE, TVA_SUR_PLACE, TVA_SERVICES)
    )
    if not (revente and sur_place and services):
        return
    production = chart.ref(TVA_PRODUCTION, raise_if_not_found=False)

    (revente | sur_place | services).write({"active": True, "price_include_override": "tax_included"})
    company.account_sale_tax_id = revente

    # Valeur stockee (carte cadeau, eWallet) : pas une vente, reste sans taxe.
    valeur_stockee = env["product.template"]
    if "loyalty.program" in env:
        programmes = (
            env["loyalty.program"]
            .with_context(active_test=False)
            .search([("program_type", "in", ("gift_card", "ewallet"))])
        )
        valeur_stockee = programmes.trigger_product_ids.product_tmpl_id

    produits = (
        env["product.template"]
        .with_context(active_test=False)
        .search([("available_in_pos", "=", True), ("company_id", "in", (False, company.id))])
    )
    for produit in produits - valeur_stockee:
        taxes_societe = produit.taxes_id.filtered(lambda t, c=company: t.company_id == c)
        if produit.meal_credit_cost or produit.meal_credits:
            cible = sur_place
        elif produit.copy_service:
            cible = services
        elif taxes_societe - production:
            continue  # taxe choisie a la main : on n'y touche pas
        else:
            cible = revente
        if taxes_societe != cible:
            produit.taxes_id = [Command.unlink(t.id) for t in taxes_societe] + [Command.link(cible.id)]
