"""Point the InSite mail templates at his.person's email fields.

The templates are loaded with noupdate="1", so the new email_to in the data
file never reaches an existing database; left alone they would read
person_id.email_institutional, a field that no longer exists, at send time.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    # Odoo removes a deleted model's ir.model row but leaves its table. The
    # pre-migration proved academic_person and academic_faculty empty, so
    # dropping them loses nothing and leaves no orphan behind.
    cr.execute("""
        DROP TABLE IF EXISTS academic_person_hr_applicant_rel,
                             academic_person_insite_identity_match_wizard_rel,
                             academic_person,
                             academic_faculty CASCADE
    """)
    env = api.Environment(cr, SUPERUSER_ID, {})
    templates = env['mail.template'].with_context(active_test=False).search([
        ('email_to', 'like', 'email_institutional'),
    ])
    templates.write({
        'email_to': "{{ object.person_id.email_personnel or object.person_id.email }}",
    })
