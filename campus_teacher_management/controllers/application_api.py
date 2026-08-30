"""Public REST endpoints for the Campus+ web form.

The form is a static page, so the browser posts here directly and cannot hold a
secret. CORS is therefore *not* the security boundary — it only makes the
legitimate browser call work, and curl ignores it entirely. The real defenses
are in the handler: an origin allowlist, per-IP and per-email rate limiting, a
honeypot, duplicate detection and strict payload validation.

Routes use ``type='http'`` rather than ``type='jsonrpc'`` so the form receives
real HTTP status codes instead of a JSON-RPC envelope that is always 200.
"""

import json
import logging
import uuid
from datetime import timedelta

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Odoo needs a concrete value at import time to emit the preflight headers; the
# per-request allowlist below is what actually decides who gets served.
CORS_ANY = '*'

PARAM_ORIGINS = 'campus_teacher.allowed_origins'
PARAM_RATE_IP = 'campus_teacher.rate_limit_ip'
PARAM_RATE_EMAIL = 'campus_teacher.rate_limit_email'
PARAM_WINDOW = 'campus_teacher.rate_limit_window_minutes'
PARAM_HONEYPOT = 'campus_teacher.honeypot_field'


class CampusApplicationApi(http.Controller):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _json(self, payload, status=200):
        response = request.make_response(
            json.dumps(payload, ensure_ascii=False),
            headers=[('Content-Type', 'application/json; charset=utf-8')],
        )
        response.status_code = status
        origin = request.httprequest.headers.get('Origin')
        if origin and self._origin_allowed(origin):
            # Echo the caller instead of leaving '*' in place, and tell caches
            # the body varies by origin.
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Vary'] = 'Origin'
        return response

    def _error(self, code, message, status=400, **extra):
        body = {'success': False, 'error_code': code, 'error': message}
        body.update(extra)
        return self._json(body, status=status)

    def _param(self, key, default=''):
        return request.env['ir.config_parameter'].sudo().get_param(key, default)

    def _origin_allowed(self, origin):
        raw = (self._param(PARAM_ORIGINS, '') or '').strip()
        if not raw or raw == '*':
            # Empty means "not configured yet"; allow so a fresh install is
            # testable, and the README tells the admin to lock it down.
            return True
        allowed = {item.strip().rstrip('/') for item in raw.split(',') if item.strip()}
        return (origin or '').rstrip('/') in allowed

    def _client_ip(self):
        headers = request.httprequest.headers
        forwarded = headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.httprequest.remote_addr or ''

    def _rate_limited(self, ip, email, exclude_id=None):
        """True if this IP or email has submitted too often lately.

        ``exclude_id`` is the submission row for the request being handled. It is
        written before validation so nothing is ever lost, which means it would
        otherwise count against its own limit and reject the very first request.
        """
        try:
            window = int(self._param(PARAM_WINDOW, '60') or 60)
            max_ip = int(self._param(PARAM_RATE_IP, '20') or 20)
            max_email = int(self._param(PARAM_RATE_EMAIL, '3') or 3)
        except ValueError:
            window, max_ip, max_email = 60, 20, 3

        since = fields.Datetime.now() - timedelta(minutes=window)
        Submission = request.env['campus.submission'].sudo()
        base = [('create_date', '>=', since)]
        if exclude_id:
            base.append(('id', '!=', exclude_id))
        if ip and Submission.search_count(base + [('source_ip', '=', ip)]) >= max_ip:
            return True
        if email and Submission.search_count(base + [('email', '=', email)]) >= max_email:
            return True
        return False

    def _read_payload(self):
        try:
            raw = request.httprequest.get_data(as_text=True)
            payload = json.loads(raw or '{}')
        except (ValueError, UnicodeDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    # ------------------------------------------------------------------
    # POST /api/campus/applications
    # ------------------------------------------------------------------
    @http.route('/api/campus/applications', type='http', auth='public',
                methods=['POST', 'OPTIONS'], csrf=False, cors=CORS_ANY, save_session=False)
    def create_application(self, **kwargs):
        origin = request.httprequest.headers.get('Origin', '')
        if origin and not self._origin_allowed(origin):
            _logger.warning("Rejected Campus+ submission from disallowed origin %r.", origin)
            return self._error('origin_not_allowed', "This origin is not allowed to submit.", 403)

        payload = self._read_payload()
        if payload is None:
            return self._error('invalid_json', "Request body must be a JSON object.", 400)

        ip = self._client_ip()
        email = (payload.get('email') or '').strip().lower()

        # Persist before validating: a payload we reject for a mapping reason is
        # still evidence, and re-processing it later beats asking the candidate
        # to fill the form again.
        Submission = request.env['campus.submission'].sudo()
        external_ref = str(payload.get('external_ref') or '')[:64]

        if external_ref:
            existing = Submission.search([('external_ref', '=', external_ref)], limit=1)
            if existing:
                return self._json({
                    'success': True,
                    'duplicate': True,
                    'reference': existing.reference,
                    'application_id': existing.applicant_id.id or None,
                    'message': "This submission was already received.",
                }, status=200)

        submission = Submission.create({
            'reference': Submission._next_reference(),
            'external_ref': external_ref or False,
            'payload': payload,
            'email': email or False,
            'source_ip': ip or False,
            'origin': origin or False,
            'user_agent': (request.httprequest.headers.get('User-Agent') or '')[:255] or False,
        })

        honeypot = self._param(PARAM_HONEYPOT, 'website') or 'website'
        if (payload.get(honeypot) or '').strip():
            submission.write({'state': 'rejected', 'error_code': 'honeypot',
                              'error_message': "Honeypot field was filled."})
            # Answer as though it worked so a bot learns nothing.
            return self._json({'success': True, 'reference': submission.reference}, status=201)

        if self._rate_limited(ip, email, exclude_id=submission.id):
            submission.write({'state': 'rejected', 'error_code': 'rate_limited',
                              'error_message': "Too many submissions."})
            return self._error('rate_limited', "Too many submissions. Please try again later.", 429)

        error = self._validate(payload)
        if error:
            code, message = error
            submission.write({'state': 'rejected', 'error_code': code, 'error_message': message})
            return self._error(code, message, 422)

        version = request.env['hr.applicant'].sudo()._campus_resolve_version(payload)
        if not version:
            submission.write({'state': 'rejected', 'error_code': 'no_published_version',
                              'error_message': "No published evaluation version."})
            return self._error('no_published_version',
                               "Applications are not open at the moment.", 422)
        if version.state != 'published':
            submission.write({'state': 'rejected', 'error_code': 'version_not_published',
                              'error_message': "Evaluation version is not published."})
            return self._error('version_not_published',
                               "Applications are not open at the moment.", 422)

        Applicant = request.env['hr.applicant'].sudo()
        duplicate = Applicant.search([
            ('email_from', '=ilike', email),
            ('campus_version_id', '=', version.id),
        ], limit=1) if email else Applicant.browse()
        if duplicate:
            submission.write({'state': 'duplicate', 'applicant_id': duplicate.id,
                              'version_id': version.id,
                              'error_code': 'duplicate_application',
                              'error_message': "This email already applied to this version."})
            return self._error('duplicate_application',
                               "An application with this email already exists for this campaign.",
                               409, application_id=duplicate.id)

        try:
            applicant = Applicant._campus_apply_payload(payload, version=version)
            applicant.action_campus_evaluate()
        except Exception as exc:  # noqa: BLE001 - never leak a traceback to the browser
            _logger.exception("Campus+ submission %s failed to process.", submission.reference)
            submission.write({'state': 'rejected', 'error_code': 'processing_error',
                              'error_message': str(exc)})
            return self._error('processing_error',
                               "We could not record your application. Please try again.", 500)

        submission.write({'state': 'processed', 'applicant_id': applicant.id,
                          'version_id': version.id})
        return self._json({
            'success': True,
            'reference': submission.reference,
            'application_id': applicant.id,
        }, status=201)

    def _validate(self, payload):
        """Return ``(error_code, message)`` or None."""
        required = {
            'nameAr': "Name in Arabic",
            'nameLat': "Name in Latin characters",
            'email': "Email",
            'phone': "Phone",
        }
        for key, label in required.items():
            if not (str(payload.get(key) or '').strip()):
                return ('missing_field', f"{label} is required.")

        email = str(payload.get('email')).strip()
        if '@' not in email or '.' not in email.split('@')[-1]:
            return ('invalid_email', "The email address is not valid.")

        if 'yearsExp' in payload and payload['yearsExp'] not in (None, ''):
            try:
                years = float(payload['yearsExp'])
            except (TypeError, ValueError):
                return ('invalid_years', "Years of experience must be a number.")
            if years < 0 or years > 70:
                return ('invalid_years', "Years of experience must be between 0 and 70.")

        subjects = payload.get('selectedSubjects') or []
        if not isinstance(subjects, (list, tuple)):
            return ('invalid_subjects', "Selected subjects must be a list.")
        if len(subjects) > 3:
            return ('too_many_subjects', "At most three subjects can be selected.")

        Subject = request.env['campus.subject'].sudo()
        for item in subjects:
            if not isinstance(item, dict) or not item.get('id'):
                continue
            code = str(item['id']).strip()
            domain = [('code', '=', code)]
            if code.isdigit():
                # The form may send either the catalogue code or the raw id.
                domain = ['|', ('code', '=', code), ('id', '=', int(code))]
            if not Subject.search_count(domain):
                return ('unknown_subject', f"Subject {code} does not exist.")
        return None

    # ------------------------------------------------------------------
    # GET /api/campus/subjects
    # ------------------------------------------------------------------
    @http.route('/api/campus/subjects', type='http', auth='public',
                methods=['GET', 'OPTIONS'], csrf=False, cors=CORS_ANY, save_session=False)
    def list_subjects(self, **kwargs):
        origin = request.httprequest.headers.get('Origin', '')
        if origin and not self._origin_allowed(origin):
            return self._error('origin_not_allowed', "This origin is not allowed.", 403)

        subjects = request.env['campus.subject'].sudo().search([('active', '=', True)])
        return self._json({
            'success': True,
            'subjects': [{
                'id': subject.code or str(subject.id),
                'name': subject.name,
                'level': subject.level or '',
                'track': subject.track or '',
                'lang': subject.language or 'AR',
            } for subject in subjects],
        })

    # ------------------------------------------------------------------
    # GET /api/campus/version
    # ------------------------------------------------------------------
    @http.route('/api/campus/version', type='http', auth='public',
                methods=['GET', 'OPTIONS'], csrf=False, cors=CORS_ANY, save_session=False)
    def current_version(self, **kwargs):
        """The open campaign. Scores and weights are deliberately not exposed —
        publishing the barème would tell candidates how to game it."""
        origin = request.httprequest.headers.get('Origin', '')
        if origin and not self._origin_allowed(origin):
            return self._error('origin_not_allowed', "This origin is not allowed.", 403)

        version = request.env['campus.evaluation.version'].sudo().search(
            [('state', '=', 'published')], order='version desc, id desc', limit=1)
        if not version:
            return self._error('no_published_version', "Applications are closed.", 404)
        return self._json({
            'success': True,
            'version': {
                'id': version.id,
                'name': version.name,
                'version': version.version,
                'external_ref_hint': str(uuid.uuid4()),
            },
        })
