import json

from odoo.tests import HttpCase, tagged

from .common import CampusCommon

ENDPOINT = '/api/campus/applications'
GOOD_ORIGIN = 'https://campusplus.his.edu.dz'


@tagged('post_install', '-at_install')
class TestApi(CampusCommon, HttpCase):

    def setUp(self):
        super().setUp()
        self._make_full_criteria_set()
        self.version.action_publish()
        self.env['ir.config_parameter'].sudo().set_param(
            'campus_teacher.allowed_origins', GOOD_ORIGIN)
        # Keep the limits out of the way except in the test that targets them.
        self.env['ir.config_parameter'].sudo().set_param('campus_teacher.rate_limit_ip', '1000')
        self.env['ir.config_parameter'].sudo().set_param('campus_teacher.rate_limit_email', '1000')
        self.env.flush_all()

    def _post(self, payload, origin=GOOD_ORIGIN):
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        return self.url_open(ENDPOINT, data=json.dumps(payload).encode(), headers=headers)

    def _valid_payload(self, **overrides):
        return dict({
            'nameAr': 'مرشح تجريبي',
            'nameLat': 'Test Candidate',
            'email': 'api.candidate@example.com',
            'phone': '0770000000',
            'yearsExp': 8,
            'rank': 'mca',
            'taughtHIS': 'yes',
            'taughtCampus': 'no',
            'camConfidence': '3',
            'flippedKnowledge': '3',
            'flippedDef': 'Students prepare before class.',
            'concernsHandled': 'Recorded backups.',
            'digitalTools': ['moodle', 'zoom'],
            'teachMethods': ['onsite', 'online'],
            'selectedSubjects': [{'id': 'T1', 'name': 'Test Mathematics', 'exp': 3}],
        }, **overrides)

    # ------------------------------------------------------------------
    def test_valid_submission_creates_and_scores(self):
        response = self._post(self._valid_payload())
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertTrue(body['success'])

        applicant = self.Applicant.browse(body['application_id'])
        self.assertEqual(applicant.email_from, 'api.candidate@example.com')
        self.assertEqual(applicant.campus_name_ar, 'مرشح تجريبي')
        self.assertEqual(applicant.campus_years_exp, 8)
        self.assertEqual(applicant.campus_version_id, self.version)
        self.assertEqual(applicant.campus_state, 'evaluated')
        self.assertGreater(applicant.campus_final_score, 0)
        self.assertEqual(len(applicant.campus_score_ids), 12)
        self.assertEqual(applicant.campus_digital_tools, ['moodle', 'zoom'])
        self.assertEqual(len(applicant.campus_subject_ids), 1)
        self.assertEqual(applicant.campus_subject_ids.subject_id, self.math)
        self.assertEqual(applicant.campus_subject_ids.years_exp, 3)

    def test_application_lands_in_a_recruitment_stage(self):
        """Odoo only computes a stage for an applicant that has a job position.

        Without the campaign carrying one, every incoming application arrives
        with no stage and is invisible in the recruitment pipeline.
        """
        job = self.env['hr.job'].create({'name': 'Test Teaching Post'})
        self.version.job_id = job.id

        response = self._post(self._valid_payload(email='staged@example.com'))
        self.assertEqual(response.status_code, 201, response.text)
        applicant = self.Applicant.browse(response.json()['application_id'])
        self.assertEqual(applicant.job_id, job)
        self.assertTrue(applicant.stage_id,
                        "an application with a job position must receive a stage")

    def test_raw_submission_is_always_stored(self):
        self._post(self._valid_payload())
        submission = self.env['campus.submission'].search([], order='id desc', limit=1)
        self.assertEqual(submission.state, 'processed')
        self.assertEqual(submission.payload['email'], 'api.candidate@example.com')
        self.assertTrue(submission.applicant_id)

    def test_disallowed_origin_is_refused(self):
        response = self._post(self._valid_payload(), origin='https://evil.example.com')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error_code'], 'origin_not_allowed')

    def test_malformed_json_is_rejected(self):
        response = self.url_open(
            ENDPOINT, data=b'{not json',
            headers={'Content-Type': 'application/json', 'Origin': GOOD_ORIGIN})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error_code'], 'invalid_json')

    def test_missing_required_field_is_rejected(self):
        payload = self._valid_payload()
        del payload['email']
        response = self._post(payload)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['error_code'], 'missing_field')

    def test_invalid_email_is_rejected(self):
        response = self._post(self._valid_payload(email='not-an-email'))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['error_code'], 'invalid_email')

    def test_out_of_range_years_is_rejected(self):
        response = self._post(self._valid_payload(yearsExp=500))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['error_code'], 'invalid_years')

    def test_unknown_subject_is_rejected(self):
        response = self._post(self._valid_payload(
            selectedSubjects=[{'id': 'NOPE', 'name': 'Ghost', 'exp': 1}]))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['error_code'], 'unknown_subject')

    def test_more_than_three_subjects_is_rejected(self):
        response = self._post(self._valid_payload(selectedSubjects=[
            {'id': 'T1', 'exp': 1}, {'id': 'T1', 'exp': 1},
            {'id': 'T1', 'exp': 1}, {'id': 'T1', 'exp': 1},
        ]))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['error_code'], 'too_many_subjects')

    def test_duplicate_email_in_the_same_campaign_is_refused(self):
        self.assertEqual(self._post(self._valid_payload()).status_code, 201)
        response = self._post(self._valid_payload())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error_code'], 'duplicate_application')
        self.assertTrue(response.json()['application_id'])

    def test_external_ref_makes_a_retry_idempotent(self):
        payload = self._valid_payload(external_ref='web-abc-123')
        first = self._post(payload)
        self.assertEqual(first.status_code, 201)

        retry = self._post(payload)
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json()['duplicate'])
        self.assertEqual(retry.json()['application_id'], first.json()['application_id'])
        self.assertEqual(
            self.Applicant.search_count([('campus_external_ref', '=', 'web-abc-123')]), 1)

    def test_honeypot_is_silently_dropped(self):
        response = self._post(self._valid_payload(website='http://spam.example'))
        # Answers 201 so a bot cannot tell it was caught...
        self.assertEqual(response.status_code, 201)
        # ...but no application exists.
        self.assertFalse(self.Applicant.search_count(
            [('email_from', '=', 'api.candidate@example.com')]))
        submission = self.env['campus.submission'].search([], order='id desc', limit=1)
        self.assertEqual(submission.state, 'rejected')
        self.assertEqual(submission.error_code, 'honeypot')

    def test_rate_limit_by_email(self):
        self.env['ir.config_parameter'].sudo().set_param('campus_teacher.rate_limit_email', '1')
        self.env.flush_all()
        self.assertEqual(self._post(self._valid_payload()).status_code, 201)
        response = self._post(self._valid_payload(email='api.candidate@example.com'))
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()['error_code'], 'rate_limited')

    def test_no_published_version_closes_applications(self):
        # Close every published version, not just this test's own: the module
        # ships a criteria set that an administrator may well have published, and
        # the endpoint falls back to whichever one is open.
        self.Version.search([('state', '=', 'published')]).action_close()
        self.env.flush_all()
        response = self._post(self._valid_payload(email='closed@example.com'))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['error_code'], 'no_published_version')

    # ------------------------------------------------------------------
    def test_subjects_endpoint_lists_the_catalogue(self):
        response = self.url_open('/api/campus/subjects', headers={'Origin': GOOD_ORIGIN})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['success'])
        codes = {item['id'] for item in body['subjects']}
        self.assertIn('T1', codes)

    def test_version_endpoint_never_leaks_scores(self):
        response = self.url_open('/api/campus/version', headers={'Origin': GOOD_ORIGIN})
        self.assertEqual(response.status_code, 200)
        text = response.text
        for forbidden in ('score', 'weight', 'priority', 'barème', 'scale'):
            self.assertNotIn(forbidden, text.lower(),
                             f"the public endpoint must not expose {forbidden}")

    def test_preflight_is_answered(self):
        response = self.url_open(ENDPOINT, method='OPTIONS', headers={
            'Origin': GOOD_ORIGIN,
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'content-type',
        })
        self.assertEqual(response.status_code, 204)
        self.assertIn('Content-Type', response.headers.get('Access-Control-Allow-Headers', ''))
