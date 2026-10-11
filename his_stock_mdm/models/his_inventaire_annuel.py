# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class HisInventaireAnnuel(models.Model):
    _name = "his.inventaire.annuel"
    _description = "Annual Physical Inventory"
    _order = "name desc"

    _name_company_uniq = models.Constraint(
        "unique(name, company_id)",
        "An annual inventory with this name already exists for this company.",
    )

    # Pas d'etat 'brouillon' : sans lien stocke entre stock.quant et une
    # campagne, une ouverture separee de la creation n'apporterait rien.
    # create_uid/create_date natifs repondent deja a "ouvert par, quand".
    name = fields.Char(required=True, default=lambda self: self.env._("New Inventory"))
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    state = fields.Selection([("en_cours", "In Progress"), ("cloture", "Closed")], default="en_cours", required=True)
    date_cloture = fields.Date(string="Closing Date", readonly=True)
    cloture_par_id = fields.Many2one("res.users", string="Closed By", readonly=True)
    note = fields.Text()

    # --- Cloture : reservee au Manager, verrouillee une fois faite ----------

    def action_cloturer(self):
        if not (self.env.su or self.env.user.has_group("stock.group_stock_manager")):
            raise AccessError(_("Only an Inventory Manager can close an annual inventory."))
        self.write(
            {
                "state": "cloture",
                "date_cloture": fields.Date.context_today(self),
                "cloture_par_id": self.env.user.id,
            }
        )

    # --- Garde-fou serveur : declenche quel que soit le chemin d'ecriture ---
    #
    # Meme discipline que his_admission._check_dossier_complet_avant_inscription :
    # la regle vit ici, pas dupliquee dans action_cloturer(), pour rester
    # valable face a un import ou une ecriture ORM directe.
    @api.constrains("state")
    def _check_cloture_sans_comptage_en_attente(self):
        for inventaire in self:
            if inventaire.state != "cloture":
                continue
            pending = self.env["stock.quant"].search_count(
                [
                    ("company_id", "=", inventaire.company_id.id),
                    ("location_id.usage", "=", "internal"),
                    ("inventory_quantity_set", "=", True),
                ]
            )
            if pending:
                raise ValidationError(
                    _(
                        'Cannot close "%(name)s": %(count)d count(s) are still entered but not '
                        "applied to the books. Apply them first (Inventory ▸ Adjustments).",
                        name=inventaire.name,
                        count=pending,
                    )
                )

    # --- Immutabilite apres cloture ------------------------------------------

    def write(self, vals):
        if not self.env.su:
            for inventaire in self:
                if inventaire.state == "cloture":
                    raise AccessError(_('The inventory "%s" is closed: it can no longer be modified.', inventaire.name))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_closed(self):
        if not self.env.su:
            for inventaire in self:
                if inventaire.state == "cloture":
                    raise AccessError(_('The inventory "%s" is closed: it cannot be deleted.', inventaire.name))
