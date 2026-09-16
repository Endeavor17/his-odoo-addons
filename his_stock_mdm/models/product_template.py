# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # --- Hooks create/write --------------------------------------------------
    #
    # Volontairement PAS des @api.constrains / computes :
    #  - default_code est un champ calcule stocke, miroir de la variante,
    #    alimente par l'inverse _set_default_code. Pendant create(),
    #    _validate_fields s'execute avant que l'inverse ait propage la valeur :
    #    une contrainte se declencherait systematiquement a tort.
    #  - tracking est precompute et son calcul intervient avant que is_storable
    #    soit resolu, un compute surcharge lirait donc is_storable=False.
    # Apres create()/write(), les deux valeurs sont fiables.

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # MDM regle 1 bis : reference opaque sequentielle attribuee
            # automatiquement. Une valeur fournie explicitement est respectee
            # (cas de reprise ou de saisie manuelle justifiee), sous reserve
            # des controles d'unicite et de format (cf. product_product.py).
            if not vals.get("default_code"):
                vals["default_code"] = self.env["ir.sequence"].next_by_code("product.internal.reference")
        templates = super().create(vals_list)
        for template, vals in zip(templates, vals_list, strict=False):
            template._apply_mdm_category_defaults(vals)
        templates._assert_mdm_default_code()
        return templates

    def write(self, vals):
        res = super().write(vals)
        if "default_code" in vals or "active" in vals:
            self._assert_mdm_default_code()
        # MDM regle 3 bis (cf. plus bas). Pas de boucle : l'ecriture de
        # sale_ok ne porte ni list_price ni available_in_pos.
        if ("list_price" in vals or "available_in_pos" in vals) and "sale_ok" not in vals:
            self._mdm_a_mettre_en_vente().write({"sale_ok": True})
        return res

    # --- MDM Phase 5 : tracabilite heritee de la categorie -------------------

    def _apply_mdm_category_defaults(self, vals):
        """Applique le parametrage de la categorie A LA CREATION uniquement.

        Le MDM prevoit une valeur par defaut heritee pour tout nouveau produit,
        pas une valeur imposee en permanence : une saisie manuelle ulterieure
        doit rester possible. Un changement de categorie ne reajuste donc pas
        la tracabilite.
        """
        self.ensure_one()
        categ = self.categ_id
        if "tracking" not in vals and self.is_storable and categ.default_tracking:
            self.tracking = categ.default_tracking
        if "use_expiration_date" not in vals and self.tracking != "none":
            self.use_expiration_date = categ.default_use_expiration_date

    # --- MDM regle 1 : reference interne obligatoire -------------------------
    # L'unicite est verifiee sur product.product (cf. product_product.py) ;
    # seule la presence est verifiee ici, le template etant le point de saisie.

    def _assert_mdm_default_code(self):
        for template in self:
            if not template.active:
                continue
            # ponytail: sur un template multi-variantes, default_code vaut
            # toujours False (miroir de la variante unique) et les variantes
            # generees par attribut naissent sans reference. L'exiger bloquerait
            # le mecanisme de variantes que le MDM recommande lui-meme (4.4).
            # Regle donc appliquee aux fiches mono-variante = tout le catalogue
            # actuel. A durcir via un assistant de numerotation si besoin.
            if len(template.product_variant_ids) > 1:
                continue
            if not template.default_code:
                raise ValidationError(_("La référence interne est obligatoire pour « %s ».", template.name))

    # --- MDM regle 2 : categorie feuille obligatoire -------------------------

    @api.constrains("categ_id")
    def _check_mdm_leaf_category(self):
        for template in self:
            if template.categ_id.child_id:
                raise ValidationError(
                    _(
                        "La catégorie « %(categ)s » est un nœud intermédiaire. Un produit doit "
                        "être rattaché à une catégorie terminale (sans sous-catégorie).\n"
                        "Sous-catégories disponibles : %(children)s.",
                        categ=template.categ_id.complete_name,
                        children=", ".join(template.categ_id.child_id.mapped("name")),
                    )
                )

    # --- MDM regle 3 : prix de vente obligatoire si stockable et vendable ----

    @api.constrains("list_price", "type", "is_storable", "sale_ok")
    def _check_mdm_sale_price(self):
        precision = self.env["decimal.precision"].precision_get("Product Price")
        for template in self:
            if (
                template.type == "consu"
                and template.is_storable
                and template.sale_ok
                and float_is_zero(template.list_price, precision_digits=precision)
            ):
                raise ValidationError(
                    _(
                        "Le prix de vente est obligatoire pour « %s » : il s'agit d'un "
                        "produit stockable marqué comme vendable.",
                        template.name,
                    )
                )

    # --- MDM regle 3 bis — mise en vente automatique au prix saisi -----------
    #
    # Le piege : l'import du catalogue (tools/import_seed_catalogue.py) cree
    # chaque stockable en sale_ok=False et list_price=0, seule facon de
    # respecter la regle 3 sans inventer de prix. Or le POS ne charge que les
    # articles available_in_pos ET sale_ok (_load_pos_data_domain) : un prix
    # saisi ensuite dans l'interface ne rendait jamais l'article visible en
    # caisse (INV-001670 « Caps Cafe Capsules », audit du 2026-09-13).
    #
    # Un article de caisse qui recoit un prix non nul est donc mis en vente.
    # La regle 3 reste entiere : on ne coche jamais sale_ok sur un prix nul et
    # on ne le decoche jamais -- ramener a 0 le prix d'un article vendable leve
    # toujours son erreur, une caisse ne vend donc jamais a 0 DA.
    #  - Hors caisse (ingredients, entretien, emballages : consommes, pas
    #    vendus), rien ne bouge.
    #  - Un sale_ok saisi dans la meme ecriture l'emporte.
    #  - create() n'est pas concerne : l'import y passe sale_ok=False expres.

    def _mdm_a_mettre_en_vente(self):
        precision = self.env["decimal.precision"].precision_get("Product Price")
        return self.filtered(
            lambda t: (
                t.available_in_pos and not t.sale_ok and not float_is_zero(t.list_price, precision_digits=precision)
            )
        )

    @api.onchange("list_price")
    def _onchange_mdm_mise_en_vente(self):
        # Meme regle que write(), mais visible avant l'enregistrement : sans
        # elle, l'utilisateur ne comprend pas pourquoi l'article est devenu
        # vendable.
        if self._mdm_a_mettre_en_vente():
            self.sale_ok = True
