# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.tools import SQL

# Une seule definition de la regle, partagee par le chargement et la recherche :
# deux copies finiraient par diverger, et un contact serait alors cache au
# chargement mais retrouve par la recherche (ou l'inverse).
HIDDEN_PARTNER_IDS = SQL("""
    SELECT partner.id
      FROM res_partner partner
     WHERE EXISTS (SELECT 1 FROM hr_applicant a WHERE a.partner_id = partner.id)
       AND NOT EXISTS (SELECT 1 FROM pos_order o WHERE o.partner_id = partner.id)
       AND NOT EXISTS (SELECT 1 FROM res_users u WHERE u.partner_id = partner.id)
       AND NOT EXISTS (SELECT 1 FROM hr_employee e WHERE e.work_contact_id = partner.id)
       AND NOT EXISTS (SELECT 1 FROM his_person p
                        WHERE p.partner_id = partner.id
                          AND p.type_personne != 'candidat')
""")


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def get_limited_partners_loading(self, offset=0):
        # Requete du coeur (point_of_sale/models/pos_config.py) recopiee a
        # l'identique — tri, limite, decalage — avec la seule clause NOT IN en
        # plus. Filtrer APRES super() rendrait moins de 100 contacts au lieu
        # de laisser les vrais clients remonter dans les places liberees.
        return self.env.execute_query(SQL("""
            WITH pm AS
            (
                     SELECT   partner_id,
                              Count(partner_id) order_count
                     FROM     pos_order
                     GROUP BY partner_id)
            SELECT    id
            FROM      res_partner AS partner
            LEFT JOIN pm
            ON        (
                                partner.id = pm.partner_id)
            WHERE (
                partner.company_id=%s OR partner.company_id IS NULL
            )
            AND partner.id NOT IN (%s)
            ORDER BY  COALESCE(pm.order_count, 0) DESC,
                      NAME limit %s offset %s;
        """, self.company_id.id, HIDDEN_PARTNER_IDS, self._get_limited_partner_count(), offset))
