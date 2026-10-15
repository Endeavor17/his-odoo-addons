"""Rend au coeur son category_id ; nos categories passent dans maintenance_category_id.

Avant 19.0.4.0.0, maintenance.request.category_id etait detourne vers
maintenance.category. Le coeur le declare related='equipment_id.category_id'
vers maintenance.equipment.category : toute mise a jour de `maintenance` (qui
passe avant ce module) recreait sa cle etrangere sur des valeurs qui pointent
vers maintenance_category, et echouait.

Avant que l'ORM ne relise le schema :
1. copier category_id dans la nouvelle colonne maintenance_category_id ;
2. retirer la cle etrangere vers maintenance_category et le NOT NULL ;
3. remettre dans category_id la valeur du coeur : la categorie de l'equipement
   (vide pour nos demandes, qui portent sur un batiment).
L'ORM pose ensuite lui-meme le NOT NULL, l'index et la cle etrangere de
maintenance_category_id, et la cle du coeur sur category_id.
"""

import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT con.conname
          FROM pg_constraint con
          JOIN pg_attribute att
            ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
         WHERE con.contype = 'f'
           AND con.conrelid = 'maintenance_request'::regclass
           AND att.attname = 'category_id'
           AND con.confrelid = 'maintenance_category'::regclass
        """
    )
    detournees = [row[0] for row in cr.fetchall()]
    if not detournees:
        _logger.info("category_id ne pointe pas vers maintenance_category : rien a migrer")
        return

    if not sql.column_exists(cr, "maintenance_request", "maintenance_category_id"):
        sql.create_column(cr, "maintenance_request", "maintenance_category_id", "int4")
    cr.execute(
        """
        UPDATE maintenance_request
           SET maintenance_category_id = category_id
         WHERE maintenance_category_id IS NULL
        """
    )
    _logger.info("%s demande(s) : categorie copiee dans maintenance_category_id", cr.rowcount)

    for conname in detournees:
        sql.drop_constraint(cr, "maintenance_request", conname)
    sql.drop_not_null(cr, "maintenance_request", "category_id")
    cr.execute(
        """
        UPDATE maintenance_request req
           SET category_id = (
                   SELECT eq.category_id
                     FROM maintenance_equipment eq
                    WHERE eq.id = req.equipment_id
               )
        """
    )
    _logger.info("category_id rendu au coeur sur %s demande(s)", cr.rowcount)
