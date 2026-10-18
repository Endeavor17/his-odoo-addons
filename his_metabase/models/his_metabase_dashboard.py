# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import hashlib
import hmac
import json
import time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

# Le site et la cle de l'instance Metabase : poses par un administrateur sur
# chaque serveur, jamais dans le depot (il est public).
SITE_PARAM = "his_metabase.site_url"
KEY_PARAM = "his_metabase.secret_key"
# Comme l'exemple de Metabase : la page signe a chaque ouverture.
TOKEN_SECONDS = 600


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


def _b64_json(data):
    return _b64(json.dumps(data, separators=(",", ":")).encode())


class HisMetabaseDashboard(models.Model):
    """Un tableau de bord Metabase, ouvert depuis le menu de son application.

    Le numero Metabase differe d'un serveur a l'autre : il est saisi par un
    administrateur, jamais livre dans les donnees.
    """

    _name = "his.metabase.dashboard"
    _description = "Metabase Dashboard"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, help="Stable key used by the app menus.")
    metabase_id = fields.Integer(
        string="Metabase Dashboard Number", help="The dashboard's number on this server's Metabase."
    )
    group_ids = fields.Many2many("res.groups", string="Allowed Groups")
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("UNIQUE(code)", "Each dashboard code must be unique.")

    @api.model
    def his_embed(self, code):
        """URL signee pour la page, ou le message a afficher a sa place.

        Les droits sont verifies ici : la methode est joignable par RPC quel
        que soit le menu. La cle reste sur le serveur ; le navigateur ne recoit
        qu'un jeton de 10 minutes.
        """
        dashboard = self.sudo().search([("code", "=", code)], limit=1)
        if not dashboard:
            return {"error": _("This dashboard does not exist or has been archived.")}
        if not dashboard.group_ids & self.env.user.all_group_ids:
            raise AccessError(_("You are not allowed to open the %s dashboard.", dashboard.name))
        get_param = self.env["ir.config_parameter"].sudo().get_param
        site_url, key = get_param(SITE_PARAM), get_param(KEY_PARAM)
        if not (site_url and key):
            return {
                "error": _(
                    "Metabase is not configured: set the %(site)s and %(key)s system parameters.",
                    site=SITE_PARAM,
                    key=KEY_PARAM,
                )
            }
        if not dashboard.metabase_id:
            return {
                "error": _(
                    "The %s dashboard has no Metabase number yet: set it in Settings > Technical > "
                    "Metabase Dashboards.",
                    dashboard.name,
                )
            }
        signing_input = (
            _b64_json({"alg": "HS256", "typ": "JWT"})
            + b"."
            + _b64_json(
                {
                    "resource": {"dashboard": dashboard.metabase_id},
                    "params": {},
                    "exp": int(time.time()) + TOKEN_SECONDS,
                }
            )
        )
        signature = _b64(hmac.new(key.encode(), signing_input, hashlib.sha256).digest())
        token = (signing_input + b"." + signature).decode()
        return {"url": f"{site_url.rstrip('/')}/embed/dashboard/{token}#bordered=false&titled=true"}
