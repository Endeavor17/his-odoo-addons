{
    'name': 'University Maintenance',
    'version': '19.0.2.0.0',
    'summary': 'University maintenance management system',
    'description': """
University Maintenance
======================
Manage maintenance requests for university buildings:

* Requests dispatched by a manager to a worker, with a start/pause/resume/done
  workflow and automatic time tracking.
* Inspection requests that collect findings, each convertible into a new
  maintenance request.
* Institutional ID displayed on every employee — owned and issued by
  his_person_core, mirrored here through his_hr_base (this module no longer
  mints it).
""",
    'author': 'Abdo Chabouti',
    'category': 'Operations/Maintenance',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
        'hr',
        'his_hr_base',
        'maintenance',
    ],

    'data': [
        'security/maintenance_university_security.xml',
        'security/ir.model.access.csv',
        'data/maintenance_stage_data.xml',
        'views/hr_employee_views.xml',
        'views/maintenance_building_views.xml',
        'views/maintenance_category_views.xml',
        'views/maintenance_university_request_views.xml',
        'views/maintenance_university_finding_views.xml',
        'views/maintenance_university_report_views.xml',
        'views/hr_employee_maintenance_summary_views.xml',
        'views/maintenance_university_worker_create_views.xml',
        'views/maintenance_university_dashboard_actions.xml',
        'views/menus.xml',
        'views/other_apps_menu_restrictions.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'maintenance_university/static/src/dashboard/**/*',
        ],
    },

    'post_init_hook': 'post_init_hook',

    'installable': True,
    'application': True,
}
