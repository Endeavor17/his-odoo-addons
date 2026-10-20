# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Domaine d'achat (pos/general) -> type d'achat (usual/investment), 2026-10-20.

Les points de vente etaient deja menes par l'acheteur seul : achat courant.
Le reste passait par le directeur : investissement. La colonne du departement
reste en place, Odoo retire seul le champ de ses metadonnees.
"""

TABLES = ("his_purchase_request", "purchase_order", "purchase_requisition")


def migrate(cr, version):
    for table in TABLES:
        cr.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = 'his_purchase_domain'",
            (table,),
        )
        if not cr.fetchone():
            continue
        cr.execute(f'ALTER TABLE "{table}" RENAME COLUMN his_purchase_domain TO his_purchase_type')
        cr.execute(
            f"""UPDATE "{table}" SET his_purchase_type = CASE his_purchase_type
                WHEN 'pos' THEN 'usual' WHEN 'general' THEN 'investment' END"""
        )
