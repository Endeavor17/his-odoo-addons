# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Toute commande est approuvee (decision du 2026-10-15) : deux niveaux,
    # montant 0, y compris pour une societe creee apres l'installation.
    po_double_validation = fields.Selection(default="two_step")
    po_double_validation_amount = fields.Monetary(default=0)

    # L'acheteur est l'occupant du poste « Purchasing Officer » (2026-10-19) :
    # un remplacement passe par la fiche employe, comme les droits.
    his_purchase_officer_id = fields.Many2one(
        "res.users",
        string="Purchasing Officer",
        compute="_compute_his_purchase_officer_id",
        help="Holder of the Purchasing Officer position: sources approved purchase requests and chases suppliers.",
    )
    his_purchase_manager_id = fields.Many2one(
        "res.users",
        string="Purchase Manager",
        help="Approves point-of-sale orders; first level of escalation.",
    )
    his_purchase_director_id = fields.Many2one(
        "res.users",
        string="Executive Director",
        help="Approves general orders; last level of escalation.",
    )

    def _compute_his_purchase_officer_id(self):
        job = self.env.ref("his_purchase.job_purchasing_officer", raise_if_not_found=False)
        Employee = self.env["hr.employee"].sudo()
        for company in self:
            domain = [("job_id", "=", job.id), ("user_id", "!=", False), ("company_id", "=", company.id)]
            company.his_purchase_officer_id = Employee.search(domain, limit=1).user_id if job else False
