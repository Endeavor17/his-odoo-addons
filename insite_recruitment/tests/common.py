from odoo.tests import common


class InsiteCommon(common.TransactionCase):
    """Shared fixtures for InSite tests: a period/module pair, a manager user
    with every InSite process permission (mirrors how the manager bootstrap
    hook grants Campus+ managers full access on install)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Person = cls.env['academic.person']
        cls.Need = cls.env['insite.recruitment.need']
        cls.Candidature = cls.env['insite.candidature']
        cls.Submission = cls.env['insite.submission']
        cls.Engagement = cls.env['academic.engagement']
        cls.Contract = cls.env['insite.contract']
        cls.ModuleSheet = cls.env['insite.module.sheet']
        cls.Process = cls.env['campus.process']
        cls.Permission = cls.env['campus.process.permission']

        cls.period = cls.env['academic.period'].create({
            'name': 'Test Period 2026',
            'date_start': '2026-09-01',
            'date_end': '2027-06-30',
        })
        cls.module = cls.env['campus.subject'].create({
            'name': 'Test InSite Module', 'code': 'INS-T1', 'level': 'L2', 'language': 'FR',
        })

        cls.manager = cls._make_user('insite_manager_test', 'group_campus_manager')
        cls._grant_all(cls.manager)

    @classmethod
    def _make_user(cls, login, group_xmlid):
        return cls.env['res.users'].create({
            'name': login,
            'login': login,
            'email': f'{login}@example.com',
            'group_ids': [(6, 0, [cls.env.ref(f'campus_teacher_management.{group_xmlid}').id])],
        })

    @classmethod
    def _grant_all(cls, user):
        for process in cls.Process.search([('code', 'like', 'insite_%')]):
            cls.Permission.create({
                'process_id': process.id, 'user_id': user.id,
                'can_view': True, 'can_execute': True, 'can_validate': True,
            })

    @classmethod
    def _grant(cls, user, code, view=False, execute=False, validate=False):
        process = cls.Process.search([('code', '=', code)], limit=1)
        return cls.Permission.create({
            'process_id': process.id, 'user_id': user.id,
            'can_view': view, 'can_execute': execute, 'can_validate': validate,
        })

    def _make_submission(self, reference, payload):
        return self.Submission.create({
            'reference': reference,
            'payload': payload,
        })

    def _make_need(self, **kwargs):
        vals = {
            'module_id': self.module.id,
            'academic_period_id': self.period.id,
            'hourly_volume': 40.0,
        }
        vals.update(kwargs)
        return self.Need.with_user(self.manager).create(vals)
