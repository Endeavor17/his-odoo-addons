"""Student/module-platform publication boundary.

No student-platform API exists yet. Deliberately a no-op today, not a fake
success — see integration.py for the same policy applied to account
provisioning.

A real implementation would need, at minimum:
- The student platform's API base URL and authentication credentials.
- The payload shape it expects for a module (this service already builds the
  payload — plan, chapters, CLOs, teachers — from the validated module sheet
  and its engagement; only the actual HTTP call is missing).

None of this is hardcoded here.
"""

from collections import namedtuple

PublicationResult = namedtuple('PublicationResult', ['success', 'message', 'payload'])


class InsitePublicationService:
    """Publishes a validated module sheet to the student platform. Call
    ``publish(module_sheet)``; check ``.success`` on the result — never
    assume it succeeded."""

    def _build_payload(self, module_sheet):
        engagement = module_sheet.engagement_id
        return {
            'module': engagement.module_id.display_name,
            'plan': module_sheet.plan,
            'chapters': module_sheet.chapters,
            'clos': module_sheet.clos,
            'teachers': [engagement.person_id.display_name],
        }

    def publish(self, module_sheet):
        payload = self._build_payload(module_sheet) if module_sheet else {}
        return PublicationResult(
            success=False,
            message="Publication is not configured. No student/module platform "
                    "API is set up for this deployment — publish manually, "
                    "then mark it done.",
            payload=payload,
        )
