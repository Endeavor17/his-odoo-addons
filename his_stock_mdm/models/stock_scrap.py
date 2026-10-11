# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class StockScrap(models.Model):
    _inherit = "stock.scrap"

    # stock.scrap n'a aucun champ libre : `origin` est le document source.
    scrap_note = fields.Char(string="Comment")

    # --- Separation des taches : Collaborateur propose, Manager valide ------
    #
    # do_scrap() est l'unique methode qui cree le mouvement de stock et passe
    # l'etat a 'done' (verifie : aucun autre chemin natif ne finalise une
    # perte). Un Collaborateur (stock.group_stock_user) garde le droit de
    # creer/modifier une declaration en brouillon ; seul un Manager peut la
    # valider. self.env.su bypasse le controle : une consequence systeme
    # (import, donnees de demo) n'est pas un geste humain a arbitrer.
    def do_scrap(self):
        if not (self.env.su or self.env.user.has_group("stock.group_stock_manager")):
            raise AccessError(
                _(
                    "Only an Inventory Manager can validate a loss. The declaration stays in "
                    "draft until it is validated."
                )
            )
        return super().do_scrap()

    # 'product_id' est requis, donc toujours present dans les vals a la
    # creation : sans lui, une declaration creee sans aucun motif ne
    # declencherait pas la contrainte (Odoo ne valide que les champs ecrits).
    @api.constrains("scrap_reason_tag_ids", "scrap_note", "product_id")
    def _check_mdm_scrap_reason(self):
        """MDM Phase 7 : motif obligatoire, commentaire obligatoire si « Autre »."""
        autre = self.env.ref("his_stock_mdm.scrap_reason_autre", raise_if_not_found=False)
        for scrap in self:
            if not scrap.scrap_reason_tag_ids:
                raise ValidationError(_("A loss reason is required to allow reporting by cause."))
            if autre and autre in scrap.scrap_reason_tag_ids and not scrap.scrap_note:
                raise ValidationError(_('The "Other" reason requires a comment describing the cause.'))
