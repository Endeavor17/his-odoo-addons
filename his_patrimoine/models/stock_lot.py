# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, models
from odoo.exceptions import UserError


class StockLot(models.Model):
    _inherit = "stock.lot"

    @api.model
    def _his_import_patrimoine(self, rows):
        """Etiquetage initial des biens existants (tools/import_patrimoine.py).

        rows : dicts building_code, room, category_xmlid, default_code,
        product_name, serial (vide = numero PAT- suivant). Une ligne refusee
        n'annule pas les autres. Relancer le meme fichier ne cree pas de
        doublon : un numero deja importe est ignore, et la N-ieme ligne sans
        numero d'un article dans une salle ne cree rien si la salle en a deja N.
        Renvoie (biens crees, [motifs de refus]).
        """
        created, rejected, seen = 0, [], {}
        for index, row in enumerate(rows, start=1):
            key = (row["default_code"], row["building_code"], row["room"])
            if not row["serial"]:
                seen[key] = seen.get(key, 0) + 1
            try:
                with self.env.cr.savepoint():
                    created += self._his_import_row(row, seen.get(key, 0))
            except Exception as error:  # pylint: disable=broad-exception-caught  # le motif est rapporte
                rejected.append(_("row %(index)s: %(error)s", index=index, error=error))
        return created, rejected

    def _his_import_row(self, row, nth):
        root = self.env.ref("his_patrimoine.categ_patrimoine")
        categ = self.env.ref(row["category_xmlid"], raise_if_not_found=False)
        if not categ or not categ.parent_path.startswith(root.parent_path):
            raise UserError(_("%s is not a Patrimoine category.", row["category_xmlid"]))
        if not row["default_code"]:
            raise UserError(_("The internal reference (default_code) is required."))
        Product = self.env["product.product"]
        product = Product.search([("default_code", "=", row["default_code"])], limit=1) or Product.create(
            {"name": row["product_name"], "default_code": row["default_code"], "categ_id": categ.id}
        )
        if row["serial"] and self.search_count([("name", "=", row["serial"]), ("product_id", "=", product.id)]):
            return 0
        Building = self.env["maintenance.building"]
        building = Building.search([("code", "=", row["building_code"])], limit=1) or Building.create(
            {"name": row["building_code"], "code": row["building_code"]}
        )
        Location = self.env["stock.location"]
        room = Location.search(
            [("name", "=", row["room"]), ("location_id", "=", building.his_location_id.id)], limit=1
        ) or Location.create({"name": row["room"], "location_id": building.his_location_id.id})
        if not row["serial"]:
            in_room = self.env["stock.quant"].search_count(
                [("product_id", "=", product.id), ("location_id", "=", room.id), ("quantity", ">", 0)]
            )
            if in_room >= nth:
                return 0
        name = row["serial"] or self.env.ref("his_patrimoine.seq_patrimoine").next_by_id()
        lot = self.create({"name": name, "product_id": product.id})
        self.env["stock.quant"].with_context(inventory_mode=True).create(
            {"product_id": product.id, "location_id": room.id, "lot_id": lot.id, "inventory_quantity": 1}
        ).action_apply_inventory()
        return 1
