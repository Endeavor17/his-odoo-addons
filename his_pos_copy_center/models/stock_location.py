from odoo import api, fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    his_copy_consumption = fields.Boolean(
        "Copy Center Paper Consumption",
        help="Where the paper used by the copies sold at the Copy Center goes.",
    )

    @api.model
    def _his_copy_consumption_location(self, company):
        """L'emplacement de consommation du papier de cette societe.

        Un par societe (HIS, IRA, HTC sont des societes distinctes) : un
        emplacement d'une autre societe serait illisible pour le caissier et
        refuse par les regles multi-societes. Cree au premier besoin sous
        l'emplacement de perte de la societe, comme les pertes de his_stock_mdm.
        """
        Location = self.sudo()
        location = Location.search(
            [("his_copy_consumption", "=", True), ("company_id", "=", company.id)],
            limit=1,
        )
        if not location:
            parent = Location.search(
                [("usage", "=", "inventory"), ("company_id", "=", company.id)], order="id", limit=1
            )
            location = Location.create(
                {
                    "name": "Consommation Copy Center",
                    "usage": "inventory",
                    "company_id": company.id,
                    "location_id": parent.id,
                    "his_copy_consumption": True,
                }
            )
        return location
