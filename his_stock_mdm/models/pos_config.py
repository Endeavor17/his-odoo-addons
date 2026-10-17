# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Qui tient quelle caisse : un role par caisse (recette P-18).

Decision de Mohamed (2026-10-17) : un role a donner par le poste
(his_access_base), plutot qu'une liste de PIN. Le role d'une caisse donne le
Point de vente ; une caisse ne s'ouvre, ne se charge et ne s'affiche au tableau
de bord que pour qui porte l'un de ses roles. Le responsable POS les voit
toutes. Une caisse sans role reste ouverte a tout utilisateur POS, comme avant.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class PosConfig(models.Model):
    _inherit = "pos.config"

    his_group_ids = fields.Many2many(
        "res.groups",
        "his_pos_config_cashier_group_rel",
        string="Cashier Roles",
        help="Roles allowed to open this till. Empty: every Point of Sale user.",
    )
    his_is_my_till = fields.Boolean(
        string="My Till", compute="_compute_his_is_my_till", search="_search_his_is_my_till"
    )

    def _his_sees_every_till(self):
        return self.env.su or self.env.user.has_group("point_of_sale.group_pos_manager")

    @api.depends_context("uid")
    def _compute_his_is_my_till(self):
        everything = self._his_sees_every_till()
        mine = self.env.user.all_group_ids
        for config in self:
            config.his_is_my_till = everything or not config.his_group_ids or bool(config.his_group_ids & mine)

    def _search_his_is_my_till(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise NotImplementedError(_("Unsupported search on My Till."))
        if self._his_sees_every_till():
            domain = []
        else:
            domain = ["|", ("his_group_ids", "=", False), ("his_group_ids", "in", self.env.user.all_group_ids.ids)]
        positive = (operator == "=") == value
        if positive:
            return domain
        return [("id", "not in", self.search(domain).ids)] if domain else [("id", "=", False)]

    def _his_check_cashier(self):
        for config in self:
            if not config.his_is_my_till:
                raise AccessError(
                    _(
                        "You cannot open %(till)s: it needs one of these roles: %(roles)s.",
                        till=config.name,
                        roles=", ".join(config.his_group_ids.mapped("name")),
                    )
                )

    def open_ui(self):
        self._his_check_cashier()
        return super().open_ui()

    def open_existing_session_cb(self):
        self._his_check_cashier()
        return super().open_existing_session_cb()


class PosSession(models.Model):
    _inherit = "pos.session"

    def load_data(self, models_to_load):
        # Le lien direct /pos/ui/<id> passe par ici, pas par open_ui.
        self.config_id._his_check_cashier()
        return super().load_data(models_to_load)
