from odoo import Command

# Identifiants du modele l10n_dz (resolus par societe : account.<id>_<nom>).
# Taux reduit 9 % sur tout ce que vendent les caisses (accord du 2026-10-14).
# Le modele dz n'a pas de 9 % « consommation sur place » : la nourriture va sur
# « Biens, produits et denrees », les prestations sur « Services ». Meme taux,
# seule change la ligne de la G50.
TVA_BIENS = "l10n_dz_vat_sale_9_g"
TVA_SERVICES = "l10n_dz_vat_sale_9_s"


def post_init_hook(env):
    for company in env["res.company"].search([("account_fiscal_country_id.code", "=", "DZ")]):
        appliquer_tva(env, company)


def appliquer_tva(env, company):
    """Pose la TVA a 9 % comprise dans le prix sur ce que vendent les caisses.

    Idempotent : peut etre rejoue (migration, nouvelle societe). Ne fait rien
    si le plan comptable dz n'est pas charge sur la societe.
    """
    chart = env["account.chart.template"].with_company(company)
    biens, services = (chart.ref(xmlid, raise_if_not_found=False) for xmlid in (TVA_BIENS, TVA_SERVICES))
    if not (biens and services):
        return

    # N'ecrire que ce qui change : le point de vente interdit d'ecrire
    # price_include_override sur une taxe deja vendue dans une session encore
    # ouverte, meme a valeur egale. Une migration rejouee sur une base vivante
    # (staging 2026-10-17, deux sessions ouvertes) ne doit pas bloquer le demarrage.
    for taxe in biens | services:
        vals = {}
        if not taxe.active:
            vals["active"] = True
        if taxe.price_include_override != "tax_included":
            vals["price_include_override"] = "tax_included"
        if vals:
            taxe.write(vals)
    company.account_sale_tax_id = biens

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
    # Les plats d'une formule sont hors grille mais vendus avec elle (recette P-09).
    produits |= produits.combo_ids.combo_item_ids.product_id.product_tmpl_id
    for produit in produits - valeur_stockee:
        taxes_societe = produit.taxes_id.filtered(lambda t, c=company: t.company_id == c)
        # Tout ce qui est a 19 % (le defaut « production » du modele dz, ou une
        # pose anterieure) passe a 9 % ; un autre taux choisi a la main reste.
        if taxes_societe.filtered(lambda t: t.amount != 19.0) - (biens | services):
            continue
        cible = services if produit.copy_service else biens
        if taxes_societe != cible:
            produit.taxes_id = [Command.unlink(t.id) for t in taxes_societe] + [Command.link(cible.id)]
