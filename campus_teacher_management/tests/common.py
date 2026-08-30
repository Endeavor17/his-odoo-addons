from odoo.tests import common

# The specified priorities. Kept here so every test agrees on the input.
PRIORITIES = {
    'C1': 3, 'C2': 1, 'C3': 2, 'C4': 1, 'C5': 3, 'C6': 0,
    'C7': 1, 'C8': 2, 'C9': 1, 'C10': 0, 'C11': 1, 'C12': 2,
}


class CampusCommon(common.TransactionCase):
    """Builds a small evaluation version by hand.

    Deliberately not reusing the shipped 2026 data: these tests must fail when
    the *code* breaks, not when someone edits a barème.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Version = cls.env['campus.evaluation.version']
        cls.Criterion = cls.env['campus.criterion']
        cls.Scale = cls.env['campus.criterion.scale']
        cls.Applicant = cls.env['hr.applicant']
        cls.Subject = cls.env['campus.subject']

        cls.version = cls.Version.create({
            'name': 'Test Campaign',
            'version': 1,
            'weighting_method': 'car',
            'normalize': True,
            'years_cap': 20,
        })

        cls.math = cls.Subject.create({
            'name': 'Test Mathematics', 'code': 'T1', 'level': 'L1', 'language': 'AR',
        })

    @classmethod
    def _make_criterion(cls, code, priority, value_type='scale', source_key=None,
                        scale=None, version=None, **extra):
        criterion = cls.Criterion.create(dict({
            'version_id': (version or cls.version).id,
            'code': code,
            'name': f'Criterion {code}',
            'priority': priority,
            'value_type': value_type,
            'source_key': source_key or code.lower(),
        }, **extra))
        for index, (key, score) in enumerate(scale or []):
            cls.Scale.create({
                'criterion_id': criterion.id,
                'key': key,
                'name': key.title(),
                'score': score,
                'sequence': index * 10,
            })
        return criterion

    @classmethod
    def _make_full_criteria_set(cls, version=None):
        """The twelve criteria with the specified priorities and barèmes."""
        version = version or cls.version
        yes_no = [('yes', 5), ('no', 0)]
        criteria = {}
        criteria['C1'] = cls._make_criterion(
            'C1', 3, 'scale', 'rank', version=version,
            scale=[('prof', 6), ('mca', 5), ('mcb', 4), ('maa', 3), ('mab', 2), ('autre', 1)])
        criteria['C2'] = cls._make_criterion(
            'C2', 1, 'scale', 'taughtCampus', version=version, scale=yes_no)
        criteria['C3'] = cls._make_criterion(
            'C3', 2, 'number', 'yearsExp', version=version,
            use_version_years_cap=True, max_score=20)
        criteria['C4'] = cls._make_criterion(
            'C4', 1, 'scale', 'camConfidence', version=version,
            scale=[('4', 5), ('3', 4), ('2', 3), ('1', 1), ('0', 0)])
        criteria['C5'] = cls._make_criterion(
            'C5', 3, 'scale', 'taughtSelectedSubjects', version=version,
            scale=[('oui', 5), ('non', 0)])
        criteria['C6'] = cls._make_criterion(
            'C6', 0, 'scale', 'taughtHIS', version=version, scale=yes_no)
        criteria['C7'] = cls._make_criterion(
            'C7', 1, 'count', 'digitalTools', version=version, max_score=6)
        criteria['C8'] = cls._make_criterion(
            'C8', 2, 'scale', 'flippedKnowledge', version=version,
            scale=[('4', 4), ('3', 3), ('2', 2), ('1', 1), ('0', 0)])
        criteria['C9'] = cls._make_criterion(
            'C9', 1, 'scale', 'subjectExperienceProvided', version=version,
            scale=[('oui', 5), ('non', 0)])
        criteria['C10'] = cls._make_criterion(
            'C10', 0, 'count', 'teachMethods', version=version, max_score=5)
        criteria['C11'] = cls._make_criterion(
            'C11', 1, 'answered', 'concernsHandled', version=version, answered_score=5)
        criteria['C12'] = cls._make_criterion(
            'C12', 2, 'answered', 'flippedDef', version=version, answered_score=5)
        return criteria

    @classmethod
    def _make_applicant(cls, name='Test Candidate', version=None, **values):
        return cls.Applicant.create(dict({
            'partner_name': name,
            'email_from': f"{name.lower().replace(' ', '.')}@example.com",
            'campus_version_id': (version or cls.version).id,
        }, **values))
