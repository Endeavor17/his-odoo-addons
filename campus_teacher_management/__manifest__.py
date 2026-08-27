{
    'name': 'Campus+ Teacher Management',
    'version': '19.0.2.0.0',
    'summary': 'Teacher recruitment, CAR evaluation and ranking for Campus+',
    'description': """
Campus+ Teacher Management
==========================
Collects teacher applications from the Campus+ web form, scores them against a
versioned set of criteria using the CAR weighting algorithm, ranks candidates
and drives the accept/refuse + subject-assignment workflow.

* Extends hr.applicant rather than reinventing the candidate.
* Criteria, scales (barèmes) and priorities are configuration data, not code.
* Weights are derived from priorities by the CAR algorithm; two variants are
  available so historical rankings stay reproducible.
* Published criteria sets are immutable, and every score line snapshots the
  scale and weight that produced it.
""",
    'author': 'Abdo Chabouti',
    'category': 'Human Resources/Recruitment',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
        'hr',
        'hr_recruitment',
        'calendar',
    ],

    'data': [
        'security/campus_security.xml',
        'security/ir.model.access.csv',
        'data/config_params.xml',
        'data/recruitment_stages.xml',
        'data/campus_subjects.xml',
        'data/campus_criteria_2026.xml',
        'data/campus_mail_templates.xml',
        'data/campus_stages_phase2.xml',
        'data/campus_mail_templates_phase2.xml',
        'data/campus_process_data.xml',
        'views/campus_evaluation_version_views.xml',
        'views/campus_criterion_views.xml',
        'views/campus_subject_views.xml',
        'views/campus_submission_views.xml',
        'views/campus_interview_slot_views.xml',
        'views/campus_wizard_views.xml',
        'views/campus_course_breakdown_views.xml',
        'views/campus_shooting_session_views.xml',
        'views/campus_shooting_program_views.xml',
        'views/campus_process_permission_views.xml',
        'views/hr_applicant_views.xml',
        'views/campus_dashboard_actions.xml',
        'views/menus.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'campus_teacher_management/static/src/dashboard/**/*',
        ],
    },

    'installable': True,
    'application': True,
    'post_init_hook': '_campus_grant_manager_process_permissions',
}
