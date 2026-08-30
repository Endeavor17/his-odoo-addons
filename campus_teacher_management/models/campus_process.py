from odoo import fields, models


class CampusProcess(models.Model):
    """One of the Campus+ Recruitment menu items that carries per-user permissions.

    Not the same thing as ``hr.recruitment.stage``: a process is the menu/screen
    (e.g. "Contrat"), a stage is where a specific candidate sits in the pipeline.
    ``stage_id`` links the two for the five phases that have one; Dashboard and
    Candidatures have no single stage, so it stays empty for them.
    """

    _name = 'campus.process'
    _description = 'Campus+ Recruitment Process'
    _order = 'sequence, id'

    code = fields.Selection([
        ('dashboard', 'Dashboard'),
        ('candidatures', 'Candidatures'),
        ('interview1', '1er Interview'),
        ('interview2', '2ème Interview'),
        ('course_breakdown', 'Course Breakdown'),
        ('contract', 'Contrat'),
        ('shooting', 'Shooting'),
    ], required=True, index=True)
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    # Which recruitment process family a row belongs to — lets the Process
    # Permissions screens filter declaratively (see campus_process_permission_views.xml
    # and insite_recruitment's own equivalent) instead of hardcoding a copy
    # of each side's code list. Base option here, extended with 'insite' via
    # selection_add from insite_recruitment, same pattern already used for code.
    family = fields.Selection([
        ('campus', 'Campus+'),
    ], default='campus')
    stage_id = fields.Many2one(
        'hr.recruitment.stage', "Recruitment Stage",
        help="The pipeline stage this process corresponds to, if any. Used to "
             "tell which process a given candidate is currently in.")

    _code_uniq = models.Constraint(
        'unique(code)', 'A Campus+ process already exists for this code.',
    )
