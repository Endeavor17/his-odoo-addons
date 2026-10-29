import logging
from collections import defaultdict

from odoo import api, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    """Le papier sort du stock avec chaque copie vendue.

    Le coeur ne cree des mouvements que pour les lignes `consu` ; une copie est
    un service et n'en cree aucun. On ajoute donc, a cote des transferts du
    coeur, un transfert par destination portant le papier declare sur le
    produit (`copy_paper_product_id` x `copy_sheets_per_unit`).

    Une seule porte d'entree : `_create_picking_from_pos_order_lines` sert a la
    fois a la vente en temps reel (pos.order) et a la cloture de session
    (pos.session), donc le papier part une fois et une seule, dans les deux
    modes.
    """

    _inherit = "stock.picking"

    @api.model
    def _create_picking_from_pos_order_lines(self, location_dest_id, lines, picking_type, partner=False):
        pickings = super()._create_picking_from_pos_order_lines(location_dest_id, lines, picking_type, partner)
        return pickings | self._create_paper_pickings(lines, picking_type, location_dest_id, partner)

    @api.model
    def _create_paper_pickings(self, lines, picking_type, location_dest_id, partner=False):
        # Un remboursement ne rend pas le papier : les feuilles ont ete
        # imprimees. Seules les lignes positives consomment.
        paper_lines = lines.filtered(lambda line: line.qty > 0 and line.product_id.copy_paper_product_id)
        if not paper_lines:
            return self.env["stock.picking"]
        source = picking_type.default_location_src_id
        consumption = self.env["stock.location"]._his_copy_consumption_location(picking_type.company_id)

        # Une copie part en consommation ; une rame vendue telle quelle (pas de
        # copy_service) part vers le client, comme toute vente.
        sheets = defaultdict(float)
        for line in paper_lines:
            product = line.product_id
            dest = consumption.id if product.copy_service else location_dest_id
            sheets[dest, product.copy_paper_product_id] += line.qty * product.copy_sheets_per_unit

        pickings = self.env["stock.picking"]
        for dest in {dest for dest, _paper in sheets}:
            picking = self.create(self._prepare_picking_vals(partner, picking_type, source.id, dest))
            moves = self.env["stock.move"].create(
                [
                    {
                        "picking_id": picking.id,
                        "picking_type_id": picking_type.id,
                        "product_id": paper.id,
                        "product_uom": paper.uom_id.id,
                        "product_uom_qty": qty,
                        "location_id": source.id,
                        "location_dest_id": dest,
                        "company_id": picking.company_id.id,
                    }
                    for (move_dest, paper), qty in sheets.items()
                    if move_dest == dest
                ]
            )
            moves._action_confirm()
            for move in moves:
                move.quantity = move.product_uom_qty
            moves.picked = True
            # Comme le coeur : un echec de validation ne bloque jamais la vente.
            try:
                with self.env.cr.savepoint():
                    picking._action_done()
            except (UserError, ValidationError) as error:
                _logger.warning(
                    "Paper picking %s left in draft for %s: %s",
                    picking.name,
                    ", ".join(set(paper_lines.order_id.mapped("name"))),
                    error,
                )
            pickings |= picking
        return pickings
