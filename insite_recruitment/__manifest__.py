{
    'name': 'InSite Recruitment',
    'version': '19.0.2.0.0',
    'summary': 'InSite teacher recruitment: need, internal/external candidates, contract, integration, module',
    'description': """
InSite Recruitment
===================
A second recruitment process inside the same Odoo Recruitment application as
Campus+, sharing one Person identity and the generic academic reference data
(Faculty, Module, AcademicPeriod, Engagement) while keeping its own
Need -> internal/external candidate -> contract -> signature -> integration ->
module assignment -> module preparation -> validation -> publication pipeline
fully separate from Campus+'s.

* A teacher exists as exactly one ``academic.person`` record, whether they
  come through Campus+, InSite, or both.
* Identity matching (exact matricule, then probabilistic name/email/phone with
  mandatory human confirmation) happens before any new Person is created.
* Internal teachers are always searched first (an explicit, administrator-set
  flag — never inferred); external candidates are ranked with an explicit,
  deterministic, human-readable explanation, never an opaque score.
* The 48h no-response reminder only ever notifies Pédagogie — it never
  auto-advances to the next candidate.
* Account/email provisioning and student-platform publication are isolated
  behind clean service boundaries (services/) that are honest about not being
  configured yet, rather than faking an integration that doesn't exist.
* Campus+ itself is not modified: every touch point on a Campus+-owned model
  is an additive ``_inherit`` from this module, never an edit to its files.
""",
    'author': 'Abdo Chabouti',
    'category': 'Human Resources/Recruitment',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
        'calendar',
        'hr_recruitment',
        'campus_teacher_management',
    ],

    'data': [
        'security/insite_security.xml',
        'security/ir.model.access.csv',
        'data/insite_process_data.xml',
        'data/insite_mail_templates.xml',
        'data/insite_cron.xml',
        'views/insite_identity_match_wizard_views.xml',
        'views/insite_submission_views.xml',
        'views/insite_recruitment_need_views.xml',
        'views/academic_engagement_views.xml',
        'views/insite_contract_views.xml',
        'views/insite_meeting_schedule_wizard_views.xml',
        'views/insite_candidature_views.xml',
        'views/insite_module_sheet_views.xml',
        'views/insite_process_permission_views.xml',
        'views/insite_menus.xml',
        'views/academic_person_views.xml',
    ],

    'installable': True,
    'application': False,
    'post_init_hook': '_insite_grant_manager_process_permissions',
}
