# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HisPerson(models.Model):
    _inherit = "his.person"

    # Meme raisonnement que his_crm_identity_bridge : source_system est requis
    # et sans defaut, les fiches nees de Campus+ basculent en saisie manuelle a
    # la desinstallation ; leur origine reste lisible dans external_ref.
    source_system = fields.Selection(
        selection_add=[("campus_plus", "Campus+")],
        ondelete={"campus_plus": lambda recs: recs.write({"source_system": "manual"})},
    )
    campus_applicant_ids = fields.One2many(
        "hr.applicant",
        "his_person_id",
        string="Candidatures Campus+",
    )
