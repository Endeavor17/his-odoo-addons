"""Account/professional-email provisioning boundary.

No Google Workspace (or any other) integration exists yet. This class is the
seam a real implementation plugs into later — it is deliberately a no-op today,
not a fake success.

A real implementation would need, at minimum:
- A Google Workspace customer/domain identifier.
- Service-account credentials with the Admin SDK Directory API's
  ``users`` scope (to create the account) enabled.
- A naming convention for the professional email address.

None of this is hardcoded here, and none of it is invented as if it already
works: ``provision()`` always reports "not configured" until a real
implementation replaces it (e.g. via ``ir.config_parameter`` for the domain
and an Odoo credential/secret store for the service-account key — neither of
which exists in this module).
"""

from collections import namedtuple

ProvisioningResult = namedtuple('ProvisioningResult', ['success', 'message'])


class InsiteAccountProvisioningService:
    """Provisions an institutional account + professional email for a newly
    signed teacher. Call ``provision(person)``; check ``.success`` on the
    result — never assume it succeeded."""

    def provision(self, person):
        return ProvisioningResult(
            success=False,
            message="Account/email provisioning is not configured. No Google "
                    "Workspace credentials are set up for this deployment — "
                    "complete this step manually, then mark it done.",
        )
