# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import api, models
from odoo.exceptions import ValidationError

# Prefixes de l'ancienne convention de nommage (MDM section 2 et regle 7).
# Les fiches historiques les conservent ; plus aucune reference nouvelle ne
# peut les reutiliser, sans quoi le schema opaque serait contourne a la main.
LEGACY_SEMANTIC_PREFIX = re.compile(r'^\s*(CAF|COP|RES|NET|SAN)\s*-', re.IGNORECASE)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.constrains('default_code', 'active')
    def _check_mdm_default_code_unique(self):
        """MDM regle 1, volet unicite.

        L'unicite est verifiee ici et non sur product.template : default_code
        est stocke sur la variante, le champ du template n'en est qu'un miroir
        (compute/inverse) qui vaut False des qu'il y a plusieurs variantes.
        Toutes les ecritures (UI, import, POS, achats) convergent donc ici.

        Le volet « obligatoire » est sur product.template : a la creation d'un
        template, la variante est creee AVANT que l'inverse _set_default_code
        ne lui propage la reference, une contrainte de presence serait donc
        toujours declenchee a tort.

        Volontairement en Python et non en contrainte SQL : la base contient
        des doublons historiques qu'on ne reprend pas (MDM section 1). Un
        UNIQUE en base echouerait a s'installer ; un @api.constrains ne se
        declenche qu'a l'ecriture, donc uniquement sur les donnees futures.
        """
        for product in self:
            if not product.active or not product.default_code:
                continue
            # ponytail: search() exclut les archives, un doublon avec une fiche
            # archivee passe donc au travers. Ajouter active_test=False si besoin.
            if self.search_count([
                ('default_code', '=', product.default_code),
                ('id', '!=', product.id),
            ], limit=1):
                raise ValidationError(
                    "La référence interne « %s » existe déjà sur un autre produit. "
                    "Elle doit être unique sur l'ensemble du catalogue."
                    % product.default_code)

    @api.constrains('default_code')
    def _check_mdm_default_code_opaque(self):
        """MDM regle 1 bis : la reference interne est opaque.

        Elle ne doit encoder ni categorie, ni type, ni format, ni variante, ni
        marque : toute information descriptive vit dans les champs structures.
        Seules les references NOUVELLEMENT attribuees sont controlees ; les
        fiches historiques en CAF-/COP-/RES-/NET-/SAN- ne sont jamais reecrites
        et ne declenchent donc jamais cette contrainte (@api.constrains ne se
        declenche qu'a l'ecriture du champ).
        """
        for product in self:
            if product.default_code and LEGACY_SEMANTIC_PREFIX.match(product.default_code):
                raise ValidationError(
                    "La référence interne « %s » reprend une convention de nommage "
                    "historique (CAF-, COP-, RES-, NET-, SAN-).\n"
                    "Les nouvelles références sont opaques et séquentielles "
                    "(INV-NNNNNN) : elles n'encodent jamais la catégorie, le type "
                    "ou un attribut. Laissez le champ vide pour qu'une référence "
                    "soit attribuée automatiquement.\n"
                    "Les fiches existantes conservent leur référence d'origine."
                    % product.default_code)
