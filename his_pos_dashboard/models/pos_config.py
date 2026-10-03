import base64
import hashlib
import hmac
import json
import time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

# Set by an administrator in each database, never committed: the repository is
# public, so the key that signs dashboards cannot live in it. The site and the
# key are the Metabase instance's, shared with maintenance_university's
# dashboard; only the dashboard number belongs to the till.
PARAMS = (
    "his_metabase.site_url",
    "his_metabase.secret_key",
    "his_pos_dashboard.metabase_dashboard_id",
)
# ponytail: 10 minutes, as in Metabase's own snippet. The till signs again on
# every opening and its screensaver leaves the page after 5 idle minutes, so a
# token never outlives its screen. A wall display left open would need the
# token re-signed on a timer.
TOKEN_SECONDS = 600


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


def _b64_json(data):
    return _b64(json.dumps(data, separators=(",", ":")).encode())


class PosConfig(models.Model):
    """The Metabase dashboard a till opens from its menu.

    One dashboard for every till, held in system parameters rather than on this
    model: a stored field is a column, and a deploy that forgets the upgrade
    would take every till down with it. The flag below is computed and never
    stored, so it needs no column either, and it reaches the browser without
    loader code: the POS reads pos.config with an empty field list, which means
    all fields (see his_pos_ui's test_theme_reaches_the_browser).
    """

    _inherit = "pos.config"

    his_dashboard_available = fields.Boolean(
        compute="_compute_his_dashboard_available",
        help="Set when the three Metabase system parameters are: the till then shows a Dashboard menu item.",
    )

    @api.model
    def _his_metabase_settings(self):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        return [get_param(key) for key in PARAMS]

    def _compute_his_dashboard_available(self):
        available = all(self._his_metabase_settings())
        for config in self:
            config.his_dashboard_available = available

    @api.model
    def his_dashboard_url(self):
        """Signed embed URL, asked for by the till each time the dashboard opens.

        The key is read in sudo and never leaves the server: the browser only
        gets a token that expires. Which is why it checks who is asking first,
        like get_meal_balance (audit S-6).
        """
        if not self.env.user.has_group("point_of_sale.group_pos_user"):
            raise AccessError(_("Only a point of sale user can open the POS dashboard."))
        site_url, key, dashboard_id = self._his_metabase_settings()
        if not (site_url and key and dashboard_id):
            raise UserError(
                _(
                    "The POS dashboard is not configured: set the his_metabase.site_url, his_metabase.secret_key "
                    "and his_pos_dashboard.metabase_dashboard_id system parameters."
                )
            )
        # HS256 by hand: the official Odoo image has no PyJWT and deploys have no
        # build step to add it. Metabase checks the HMAC and the expiry, nothing
        # a library would add.
        signing_input = (
            _b64_json({"alg": "HS256", "typ": "JWT"})
            + b"."
            + _b64_json(
                {
                    "resource": {"dashboard": int(dashboard_id)},
                    "params": {},
                    "exp": int(time.time()) + TOKEN_SECONDS,
                }
            )
        )
        signature = _b64(hmac.new(key.encode(), signing_input, hashlib.sha256).digest())
        token = (signing_input + b"." + signature).decode()
        return f"{site_url.rstrip('/')}/embed/dashboard/{token}#bordered=true&titled=true"
