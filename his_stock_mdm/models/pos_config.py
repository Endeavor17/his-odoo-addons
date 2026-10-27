# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Qui tient quelle caisse : un role par caisse (recette P-18).

Decision de Mohamed (2026-10-17) : un role a donner par le poste
(his_access_base), plutot qu'une liste de PIN. Le role d'une caisse donne le
Point de vente ; une caisse ne s'ouvre, ne se charge et ne s'affiche au tableau
de bord que pour qui porte l'un de ses roles. Le responsable POS les voit
toutes. Une caisse sans role reste ouverte a tout utilisateur POS, comme avant.

Deux questions distinctes, deux reponses (MDM des roles, 2026-10-27) :
- quel PC ouvre quelle caisse : le role du compte comptoir (`his_group_ids`) ;
- quels noms on tape a la caisse : les employes dont le POSTE porte un role de
  caissier lie a cette caisse (`his_cashier_role_ids`), et qui ont un PIN. Ces
  listes pos_hr se deduisent des postes ; personne ne les edite a la main.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.fields import Command, Domain


class PosConfig(models.Model):
    _inherit = "pos.config"

    his_group_ids = fields.Many2many(
        "res.groups",
        "his_pos_config_cashier_group_rel",
        string="Cashier Roles",
        help="Roles allowed to open this till. Empty: every Point of Sale user.",
    )
    his_cashier_role_ids = fields.Many2many(
        "his.role",
        "his_role_pos_config_rel",
        "config_id",
        "role_id",
        string="Cashier Business Roles",
        readonly=True,
        # Comme l'acces a his.role : sinon la caisse, qui lit tous les champs
        # de pos.config, ne charge plus pour un simple utilisateur POS.
        groups="point_of_sale.group_pos_manager,base.group_erp_manager",
        help="Employees whose job post carries one of these roles tap their name at this till.",
    )
    his_till_issue = fields.Text(string="Till Issue", compute="_compute_his_till_issue")
    his_is_my_till = fields.Boolean(
        string="My Till", compute="_compute_his_is_my_till", search="_search_his_is_my_till"
    )

    def _his_titulaires(self):
        """Les employes dont le poste porte un role de caissier de cette caisse."""
        self.ensure_one()
        roles = self.sudo().his_cashier_role_ids
        if not roles:
            return self.env["hr.employee"]
        return (
            self.env["hr.employee"]
            .sudo()
            .search([("job_id.role_ids", "in", roles.ids), ("company_id", "=", self.company_id.id)])
        )

    @api.depends("his_cashier_role_ids", "advanced_employee_ids")
    def _compute_his_till_issue(self):
        for config in self:
            issue = False
            if config.module_pos_hr:
                titulaires = config._his_titulaires()
                # Les responsables POS ajoutes par pos_hr comptent aussi.
                sans_pin = (titulaires | config.sudo().advanced_employee_ids).filtered(lambda e: not e.pin)
                if not config.sudo().his_cashier_role_ids:
                    issue = _("No cashier role linked: only POS managers with a PIN can tap in.")
                elif not (titulaires - sans_pin):
                    issue = _("No cashier can open this till.")
                if sans_pin:
                    sans = _("Without a PIN, so not offered: %(names)s", names=", ".join(sans_pin.mapped("name")))
                    issue = "%s\n%s" % (issue, sans) if issue else sans
            config.his_till_issue = issue

    @api.model
    def _his_sync_tills(self):
        """Deduit des postes la liste des noms de chaque caisse.

        Les caissiers vont dans la liste « avancee » : ils font les entrees et
        sorties d'especes et ferment la caisse (decision de Mohamed). pos_hr y
        rajoute lui-meme, a chaque ecriture, les responsables POS — qui restent
        sur toutes les caisses (decision de Mohamed). Sans PIN, pas de nom.
        """
        # ponytail: syncs every till on any change; scope it to affected tills if tills grow beyond a handful.
        for config in self.sudo().search([("module_pos_hr", "=", True)]):
            caissiers = config._his_titulaires().filtered("pin")
            # Comme pos_hr : les responsables de la societe de cette caisse.
            responsables = (
                config._get_group_pos_manager()
                .with_company(config.company_id)
                .user_ids.filtered(lambda u, c=config.company_id: c in u.company_ids)
                .employee_id
            )
            avances = config.advanced_employee_ids
            if (
                avances - responsables == caissiers - responsables
                and responsables <= avances
                and not config.basic_employee_ids
                and not config.minimal_employee_ids
            ):
                continue
            config.write(
                {
                    "advanced_employee_ids": [Command.set(caissiers.ids)],
                    "basic_employee_ids": [Command.clear()],
                    "minimal_employee_ids": [Command.clear()],
                }
            )

    def _employee_domain(self, user_id):
        """Qui peut taper son nom a cette caisse.

        pos_hr ne filtre que si la liste « basique » est remplie ; nos caissiers
        sont dans l'« avancee ». Ici, toute liste remplie — ou un role de caissier
        lie — restreint la caisse a ses listes : retirer le dernier role ne la
        rouvre donc pas a tout le monde. Et seulement ceux qui ont un PIN : pos_hr
        met tout responsable POS sur la liste, PIN ou pas, et sans PIN n'importe
        qui taperait « Administrator » au comptoir (decision 12 : pas de PIN, pas
        de nom). Le PIN se lit en sudo : le champ est reserve aux RH.
        """
        domain = super()._employee_domain(user_id)
        caisse = self.sudo()
        listes = caisse.basic_employee_ids | caisse.advanced_employee_ids | caisse.minimal_employee_ids
        if caisse.his_cashier_role_ids or listes:
            avec_pin = listes.filtered("pin")
            domain = Domain.AND([domain, ["|", ("user_id", "=", user_id), ("id", "in", avec_pin.ids)]])
        return domain

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
