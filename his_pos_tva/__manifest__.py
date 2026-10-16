# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "POS - TVA algerienne a 9 %",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "summary": "Les caisses encaissent la TVA a 9 %, comprise dans le prix affiche",
    "description": """
Avant ce module, aucune caisse ne collectait de TVA : les produits vendables
n'en portaient aucune, et les 900+ produits du catalogue encore sans prix
portaient « 19% G Prod » en HORS taxe — le jour ou un prix y serait saisi, le
client aurait paye 19 % de plus que l'etiquette.

Ce que le module en fait :

  - Taux reduit 9 % sur TOUT ce que vendent les caisses : repas, plats du
    menu, forfaits repas, revente Cafeteria, Copy Center (accord du
    2026-10-14, qui remplace le 19 % retenu le 2026-09-27).
  - Le prix affiche est le montant total paye (loi 04-02, art. 6) : les taxes
    sont donc COMPRISES dans le prix. Un repas a 600 DA reste a 600 DA
    (550,46 HT + 49,54 TVA). Odoo interdit de basculer la societe entiere en
    « toutes taxes comprises » des qu'elle a facture : on pose donc
    `price_include_override` sur les deux taxes utilisees, le levier prevu
    par le coeur pour ce cas.
  - Pour une prestation de services, la TVA est due a l'encaissement
    (CTCA art. 14-f) : un forfait repas est taxe a la vente, et le repas servi
    ensuite sur credits (0 DA) ne l'est pas une seconde fois.

Quelle taxe sur quel produit (le taux est le meme, seule change la ligne de
la declaration G50 — le comptable peut les reaffecter sans toucher un dinar) :

  - prestations du Copy Center       -> 9 % services
  - tout le reste vendu en caisse    -> 9 % biens, produits et denrees
                                        (aussi taxe par defaut de la societe)
  - carte cadeau, recharge eWallet   -> aucune (valeur stockee : la TVA est
                                        due quand elle est depensee)

Tout produit de caisse a 19 % passe a 9 %. Un produit qui porte un autre taux
choisi a la main (0 %, par exemple) n'est pas touche.

Hors perimetre : le droit de timbre sur les paiements en especes (Code du
timbre art. 100), prevu dans une branche a part.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": [
        "l10n_dz",
        "his_meal_management",
        "his_pos_copy_center",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
