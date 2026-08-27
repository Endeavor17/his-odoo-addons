from odoo import fields, models

INSITE_PROCESS_CODES = [
    ('insite_needs', 'InSite Recruitment Needs'),
    ('insite_candidatures', 'InSite Candidatures'),
    ('insite_reviews', 'InSite Reviews'),
    ('insite_engagements', 'InSite Engagements'),
    ('insite_contracts', 'InSite Contracts'),
    ('insite_module_preparation', 'InSite Module Preparation'),
]


class CampusProcess(models.Model):
    """Additive only: extends the existing Process Permission matrix with the
    8 InSite process codes. Reuses campus.process/campus.process.permission
    verbatim rather than building a parallel permission system — the 7
    existing Campus+ codes, and every existing permission row, are untouched.
    """

    _inherit = 'campus.process'

    code = fields.Selection(
        selection_add=INSITE_PROCESS_CODES,
        ondelete={code: 'cascade' for code, _label in INSITE_PROCESS_CODES},
    )

    # Extends the base 'campus' option (declared on campus.process itself)
    # with 'insite' — same selection_add mechanism as code, just above.
    # InSite's 8 rows set family='insite' explicitly in insite_process_data.xml.
    family = fields.Selection(selection_add=[('insite', 'InSite')])
