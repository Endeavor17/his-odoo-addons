# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

ROOT = "All / Retail & Consommables (Storable)"

# XML ID -> complete_name de la categorie DEJA PRESENTE en base.
# Le module ne cree aucune categorie : il se rattache a l'arborescence existante
# (cf. MDM section 4.1). Une entree non resolue est simplement ignoree, avec un
# avertissement au log.
MDM_CATEGORIES = {
    'categ_retail': ROOT,
    'categ_book': f"{ROOT} / Book",
    'categ_cafe': f"{ROOT} / Café",
    'categ_cafe_biscuits': f"{ROOT} / Café / Biscuits & Gâteaux",
    'categ_cafe_boissons': f"{ROOT} / Café / Boissons",
    'categ_cafe_bonbons': f"{ROOT} / Café / Bonbons",
    'categ_cafe_chocolat': f"{ROOT} / Café / Chocolat",
    'categ_cafe_divers': f"{ROOT} / Café / Divers",
    'categ_cafe_snacks': f"{ROOT} / Café / Snacks",
    'categ_copy': f"{ROOT} / Copy",
    'categ_copy_bureautique': f"{ROOT} / Copy / Articles Bureautique",
    'categ_copy_flexy': f"{ROOT} / Copy / Flexy",
    'categ_copy_impression': f"{ROOT} / Copy / Impression",
    'categ_copy_photocopie': f"{ROOT} / Copy / Photocopie",
    'categ_copy_scan': f"{ROOT} / Copy / Scan",
    'categ_menage': f"{ROOT} / Ménage & Nettoyage",
    'categ_restaurant': f"{ROOT} / Restaurant",
    'categ_resto_alimentations': f"{ROOT} / Restaurant / Alimentations",
    'categ_resto_epices': f"{ROOT} / Restaurant / Épices",
    'categ_resto_fruits': f"{ROOT} / Restaurant / Fruits",
    'categ_resto_legumes': f"{ROOT} / Restaurant / Légumes",
    'categ_resto_viandes': f"{ROOT} / Restaurant / Viandes",
}


class ProductCategory(models.Model):
    _inherit = 'product.category'

    default_tracking = fields.Selection(
        selection=[
            ('serial', "Par numéro de série"),
            ('lot', "Par lots"),
            ('none', "Par quantité"),
        ],
        string="Traçabilité par défaut",
        help="Appliquée automatiquement aux produits stockables créés dans cette "
             "catégorie. Une valeur saisie manuellement sur le produit est conservée.")
    default_use_expiration_date = fields.Boolean(
        string="Date de péremption par défaut",
        help="Active la gestion des dates de péremption sur les produits créés "
             "dans cette catégorie.")

    @api.model
    def _bind_mdm_xmlids(self):
        """Rattache les categories existantes aux XML IDs du MDM.

        Appele par data/mdm_bind_data.xml AVANT tout autre fichier de donnees.
        Sans cela, les fichiers suivants creeraient une arborescence en double
        a cote de celle deja en production.
        """
        categories = self.search([('complete_name', 'in', list(MDM_CATEGORIES.values()))])
        by_path = {c.complete_name: c for c in categories}

        data_list = [
            {'xml_id': f'his_stock_mdm.{xml_id}', 'record': by_path[path], 'noupdate': False}
            for xml_id, path in MDM_CATEGORIES.items()
            if path in by_path
        ]
        self.env['ir.model.data']._update_xmlids(data_list)

        missing = [p for p in MDM_CATEGORIES.values() if p not in by_path]
        if missing:
            _logger.warning(
                "MDM: %d categorie(s) introuvable(s) en base, a creer manuellement "
                "puis relancer la mise a jour du module: %s",
                len(missing), ", ".join(missing))
