# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Regimes sans TVA : le fournisseur ne facture pas de TVA, ses devis se
# comparent donc TTC contre ceux d'un fournisseur au reel.
REGIMES_SANS_TVA = ("ifu", "auto_entrepreneur")


class ResPartner(models.Model):
    _inherit = "res.partner"

    his_rc = fields.Char(string="Trade Register (RC)", help="Registre de commerce number, e.g. 16/00-1234567B21.")
    his_nis = fields.Char(string="NIS", help="Statistical identification number.")
    his_ai = fields.Char(string="AI", help="Article d'imposition (tax article number).")
    his_nin = fields.Char(string="National ID (NIN)", help="National identification number of an individual.")
    his_tax_regime = fields.Selection(
        [
            ("real", "Real regime (charges VAT)"),
            ("ifu", "IFU flat tax (no VAT)"),
            ("auto_entrepreneur", "Auto-entrepreneur (no VAT)"),
        ],
        string="Tax Regime",
        default="real",
        help="Suppliers under IFU or auto-entrepreneur do not charge VAT: purchase lines get no tax.",
    )

    @api.model
    def _commercial_fields(self):
        # Les contacts d'une societe portent les identifiants de la societe.
        return [*super()._commercial_fields(), "his_rc", "his_nis", "his_ai", "his_tax_regime"]

    @api.constrains("his_nis", "his_ai", "his_nin")
    def _check_his_digits(self):
        champs = {"his_nis": _("NIS"), "his_ai": _("AI"), "his_nin": _("National ID (NIN)")}
        for partner in self:
            for champ, libelle in champs.items():
                valeur = (partner[champ] or "").replace(" ", "")
                if valeur and not valeur.isdigit():
                    raise ValidationError(
                        _(
                            "%(field)s of %(partner)s must contain digits only.",
                            field=libelle,
                            partner=partner.display_name,
                        )
                    )

    def his_is_vat_free(self):
        """Vrai si le tiers (sa societe) ne facture pas de TVA."""
        self.ensure_one()
        return self.commercial_partner_id.his_tax_regime in REGIMES_SANS_TVA

    def his_missing_identifiers(self):
        """Libelles des identifiants obligatoires manquants pour acheter a ce tiers.

        Societe : NIF et RC. Personne physique : NIF et NIN (decision de Mohamed,
        2026-10-15). Lu sur la societe du contact.
        """
        self.ensure_one()
        tiers = self.commercial_partner_id
        manquants = []
        if not tiers.vat:
            manquants.append(_("NIF"))
        if tiers.is_company:
            if not tiers.his_rc:
                manquants.append(_("Trade Register (RC)"))
        elif not tiers.his_nin:
            manquants.append(_("National ID (NIN)"))
        return manquants
