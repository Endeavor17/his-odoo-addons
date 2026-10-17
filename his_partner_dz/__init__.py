# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import models


def post_init_hook(env):
    defauts_algeriens(env)


def defauts_algeriens(env):
    """Une base neuve naissait aux Etats-Unis et sans le francais (recette P-26).

    La societe principale passe en Algerie si son pays fiscal l'est deja (plan
    l10n_dz) ; le francais est active et ses traductions chargees. Rien n'est
    impose aux personnes : un compte cree depuis une session en francais l'est
    deja.
    """
    company = env.ref("base.main_company")
    algerie = env.ref("base.dz")
    if company.country_id != algerie and company.account_fiscal_country_id in (algerie, env["res.country"]):
        company.country_id = algerie
    if not env["res.lang"]._lang_get("fr_FR").active:
        env["res.lang"]._activate_lang("fr_FR")
        env["ir.module.module"].search([("state", "=", "installed")])._update_translations(["fr_FR"])
