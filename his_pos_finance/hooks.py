# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Comptes, journaux et caisses de la procedure points de vente (PROC-FIN-PDV, partie 3).

Idempotent. Ne cree que ce qui manque ; le plan l10n_dz porte deja 411000,
476000, 530000, 530001, 581000, 657000, 757000 (codes a 6 chiffres), la CI
peut charger le plan generique. Codes de journaux en 4 lettres : Odoo les
limite a 5 (VEN-CAF n'y tient pas).
"""

import logging

from odoo.addons.his_pos_tva.hooks import TVA_BIENS, TVA_SERVICES
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CASH = "asset_cash"
CURRENT = "asset_current"
LIABILITY = "liability_current"
RECEIVABLE = "asset_receivable"
INCOME = "income"

# (code, libelle, type, lettrable)
ACCOUNTS = [
    ("530000", "Caisse – Direction", CASH, False),
    ("530001", "Caisse – Département Finance", CASH, False),
    ("530100", "Caisse – Copy Center", CASH, False),
    ("530200", "Caisse – Cafétéria", CASH, False),
    ("530300", "Caisse – Restaurant", CASH, False),
    # Compte de liaison : solde une fois le versement recu, donc lettrable
    # (un compte de tresorerie ne peut pas l'etre).
    ("581000", "Virements internes", CURRENT, True),
    ("476000", "Écarts de caisse à régulariser", CURRENT, True),
    ("657000", "Autres charges exceptionnelles", "expense", False),
    ("757000", "Autres produits exceptionnels", "income_other", False),
    ("700100", "Ventes de marchandises – Copy Center", INCOME, False),
    ("700200", "Ventes de marchandises – Cafétéria", INCOME, False),
    ("700300", "Ventes de marchandises – Restaurant", INCOME, False),
    ("701200", "Ventes de produits finis – Cafétéria", INCOME, False),
    ("701300", "Ventes de produits finis – Restaurant", INCOME, False),
    ("706000", "Prestations de services – Société", INCOME, False),
    ("706100", "Autres prestations de services – Société", INCOME, False),
    ("706200", "Prestations de services – Copy Center", INCOME, False),
    ("411000", "Clients – Général", RECEIVABLE, True),
    ("411100", "Clients – Copy Center", RECEIVABLE, True),
    ("411200", "Clients – Cafétéria", RECEIVABLE, True),
    ("411300", "Clients – Restaurant", RECEIVABLE, True),
    ("445600", "TVA déductible sur achats – Global", CURRENT, False),
    ("445720", "TVA collectée sur ventes – Global", LIABILITY, False),
]

# (code, libelle, type, compte par defaut)
JOURNALS = [
    ("VGEN", "Ventes générales – Société (VEN-GEN)", "sale", "706000"),
    ("VCOP", "Ventes – Copy Center (VEN-COP)", "sale", "700100"),
    ("VCAF", "Ventes – Cafétéria (VEN-CAF)", "sale", "700200"),
    ("VRES", "Ventes – Restaurant (VEN-RES)", "sale", "701300"),
    ("CDIR", "Caisse – Direction (CAI-DIR)", "cash", "530000"),
    ("CFIN", "Caisse – Département Finance (CAI-FIN)", "cash", "530001"),
    ("CCOP", "Caisse – Copy Center (CAI-COP)", "cash", "530100"),
    ("CCAF", "Caisse – Cafétéria (CAI-CAF)", "cash", "530200"),
    ("CRES", "Caisse – Restaurant (CAI-RES)", "cash", "530300"),
]

# Compte de produit de base par categorie d'articles.
INCOME_BY_CATEGORY = {
    "706200": [
        "his_stock_mdm.categ_copy_impression",
        "his_stock_mdm.categ_copy_photocopie",
        "his_stock_mdm.categ_copy_scan",
    ],
    "700100": ["his_stock_mdm.categ_copy_bureautique", "his_stock_mdm.categ_copy_flexy", "his_stock_mdm.categ_book"],
    "700200": [
        "his_stock_mdm.categ_cafe_biscuits",
        "his_stock_mdm.categ_cafe_boissons",
        "his_stock_mdm.categ_cafe_bonbons",
        "his_stock_mdm.categ_cafe_chocolat",
        "his_stock_mdm.categ_cafe_divers",
        "his_stock_mdm.categ_cafe_snacks",
    ],
    "701200": ["his_pos_menu.product_category_cafeteria_menu"],
    "701300": ["his_pos_menu.product_category_menu", "his_meal_management.product_category_meal_plans"],
}

# Par caisse : journal de ventes, journal de caisse, et reaffectation des
# marchandises revendues vers le compte de l'activite qui les vend.
TILLS = {
    "his_stock_mdm.pos_config_copy_center": ("VCOP", "CCOP", {"700200": "700100"}),
    "his_stock_mdm.pos_config_cafeteria": ("VCAF", "CCAF", {"700100": "700200"}),
    "his_stock_mdm.pos_config_restaurant": ("VRES", "CRES", {"700100": "700300", "700200": "700300"}),
}


def _changes(record, vals):
    """Les seules valeurs qui different, pretes a ecrire (ids) : ne rien ecrire de plus."""
    return {name: getattr(value, "id", value) for name, value in vals.items() if record[name] != value}


def _setup_accounts(env, company, account):
    Account = env["account.account"].with_company(company)
    for code, name, account_type, reconcile in ACCOUNTS:
        existing = account(code)
        if not existing:
            Account.create(
                {
                    "code": code,
                    "name": name,
                    "account_type": account_type,
                    "reconcile": reconcile,
                    "company_ids": [(6, 0, company.ids)],
                }
            )
        elif reconcile and not existing.reconcile:
            # 581000 est en tresorerie dans le plan dz : un compte de
            # tresorerie ne peut pas etre lettrable.
            vals = {"reconcile": True}
            if existing.account_type == CASH:
                vals["account_type"] = account_type
            existing.write(vals)


def _setup_journals(env, company, account):
    Journal = env["account.journal"]
    ecart = account("476000")
    for code, name, journal_type, default_code in JOURNALS:
        journal = Journal.search([("code", "=", code), ("company_id", "=", company.id)], limit=1)
        vals = {"default_account_id": account(default_code)}
        if journal_type == "cash":
            vals.update(loss_account_id=ecart, profit_account_id=ecart)
        if not journal:
            Journal.create(
                {"code": code, "name": name, "type": journal_type, "company_id": company.id, **_changes(Journal, vals)}
            )
        else:
            vals = _changes(journal, vals)
            if vals:
                journal.write(vals)


def setup_pos_finance(env, company):
    """Cree comptes et journaux manquants, puis regle les trois caisses de `company`."""
    if not company.chart_template:
        _logger.warning("his_pos_finance: %s has no chart of accounts, nothing set up.", company.name)
        return

    def account(code):
        return (
            env["account.account"]
            .with_company(company)
            .search([("code", "=", code), ("company_ids", "in", company.id)], limit=1)
        )

    _setup_accounts(env, company, account)
    _setup_journals(env, company, account)

    if company.transfer_account_id != account("581000"):
        company.transfer_account_id = account("581000")

    for code, xmlids in INCOME_BY_CATEGORY.items():
        for xmlid in xmlids:
            categ = env.ref(xmlid, raise_if_not_found=False)
            if categ and categ.with_company(company).property_account_income_categ_id != account(code):
                categ.with_company(company).property_account_income_categ_id = account(code)

    chart = env["account.chart.template"].with_company(company)
    collectee = account("445720")
    for xmlid in (TVA_BIENS, TVA_SERVICES):
        tax = chart.ref(xmlid, raise_if_not_found=False)
        lines = tax and (tax.invoice_repartition_line_ids | tax.refund_repartition_line_ids).filtered(
            lambda r: r.repartition_type == "tax" and r.account_id != collectee
        )
        if lines:
            lines.write({"account_id": collectee.id})

    _setup_tills(env, company, account)
    # apres le report : retirer un moyen de paiement recalcule le journal de
    # caisse des anciennes sessions, et le report ne les retrouverait plus
    carry_legacy_cash(env, company)
    cash_only_tills(env, company)


def cash_only_tills(env, company):
    """Decision 18 : especes seulement. Retire Carte et Compte client des caisses.

    Odoo pose tous les moyens de paiement de la societe sur une caisse creee ;
    le Compte client passerait la vente en 411, reserve aux clients factures.
    Une caisse ouverte est laissee telle quelle (on ne change pas ses moyens en
    pleine session) : elle sera nettoyee a la prochaine mise a jour.
    """
    for xmlid in TILLS:
        config = env.ref(xmlid, raise_if_not_found=False)
        if not config or config.sudo().company_id != company:
            continue
        others = config.payment_method_ids.filtered(lambda m: not m.is_cash_count)
        if not others:
            continue
        if config.current_session_id:
            _logger.warning("his_pos_finance: %s is open, %s left on it", config.name, others.mapped("name"))
            continue
        config.payment_method_ids = [(3, method.id) for method in others]


def carry_legacy_cash(env, company):
    """Reporte le fonds de chaque caisse de l'ancien compte de caisse vers le sien.

    Avant ce module, les caisses versaient leurs especes dans le journal de
    caisse du plan (CSH1, CSH2...), sur 530001 : le compte que la procedure
    donne a la caisse Finance (CFIN). La premiere session sur le nouveau
    journal part du compte de la derniere cloture (le fonds reste en caisse),
    alors que le nouveau compte 530x est vide : on deplace ce fonds de l'ancien
    compte vers le compte de la caisse. Puis on archive les anciens journaux qui
    partagent le compte d'une caisse Finance ou Direction : 530001 et 530000
    ne bougent plus que par CFIN et CDIR. Ce qui reste sur 530001 venait
    d'especes sorties des caisses hors du systeme : le premier comptage de
    CFIN le fait apparaitre sur une fiche d'ecart.

    Idempotent : une ecriture par ancienne session, retrouvee par sa reference.
    """
    Journal = env["account.journal"]
    Move = env["account.move"]
    for xmlid in TILLS:
        config = env.ref(xmlid, raise_if_not_found=False)
        if not config or config.sudo().company_id != company:
            continue
        journal = config.payment_method_ids.filtered("is_cash_count")[:1].journal_id
        if not journal:
            continue
        legacy = env["pos.session"].search(
            [
                ("config_id", "=", config.id),
                ("state", "=", "closed"),
                ("cash_journal_id", "!=", False),
                ("cash_journal_id", "!=", journal.id),
            ],
            order="id desc",
            limit=1,
        )
        old_account = legacy.cash_journal_id.default_account_id
        amount = legacy.cash_register_balance_end_real
        if not legacy or not old_account or old_account == journal.default_account_id:
            continue
        if company.currency_id.is_zero(amount):
            continue
        ref = env._("Till float carried over from %s", legacy.name)
        if Move.search_count([("journal_id", "=", journal.id), ("ref", "=", ref)]):
            continue
        # un fonds negatif (caisse a decouvert) se reporte dans l'autre sens
        debit, credit = (
            (journal.default_account_id, old_account) if amount > 0 else (old_account, journal.default_account_id)
        )
        move = Move.create(
            {
                "journal_id": journal.id,
                "ref": ref,
                "line_ids": [
                    (0, 0, {"account_id": debit.id, "name": ref, "debit": abs(amount), "credit": 0}),
                    (0, 0, {"account_id": credit.id, "name": ref, "debit": 0, "credit": abs(amount)}),
                ],
            }
        )
        move.action_post()
        _logger.info(
            "his_pos_finance: %s carried %s from %s to %s", config.name, amount, old_account.code, journal.code
        )

    ours = Journal.search([("code", "in", [code for code, *_rest in JOURNALS]), ("company_id", "=", company.id)])
    boxes = ours.filtered(lambda j: j.code in ("CFIN", "CDIR")).default_account_id
    used = env["pos.payment.method"].with_context(active_test=False).search([]).journal_id
    legacy_journals = Journal.search(
        [
            ("type", "=", "cash"),
            ("company_id", "=", company.id),
            ("default_account_id", "in", boxes.ids),
            ("id", "not in", (ours | used).ids),
        ]
    )
    if legacy_journals:
        _logger.info("his_pos_finance: archiving legacy cash journals %s", legacy_journals.mapped("code"))
        legacy_journals.active = False


def _setup_tills(env, company, account):
    Journal = env["account.journal"]

    def journal(code):
        return Journal.search([("code", "=", code), ("company_id", "=", company.id)], limit=1)

    # Le plan dz rattache ses taxes nationales (dont la 9 % de his_pos_tva) a la
    # position domestique (« Regime national ») ; une position sans taxes les retirerait de
    # la vente. Nos positions portent donc les memes taxes : seuls les comptes
    # changent.
    # Champ stocke, encore vide sur une base dont les positions n'ont pas
    # bouge depuis le chargement du plan (constate a l'installation) : on le
    # recalcule avant de le lire.
    company._compute_domestic_fiscal_position_id()
    domestic_taxes = company.domestic_fiscal_position_id.tax_ids

    todo = []
    for xmlid, (sale_code, cash_code, mapping) in TILLS.items():
        config = env.ref(xmlid, raise_if_not_found=False)
        # sudo : la caisse d'une autre societe n'est pas lisible depuis celle-ci
        if not config or config.sudo().company_id != company:
            continue
        name = f"Revenue – {config.name}"
        position = env["account.fiscal.position"].search(
            [("name", "=", name), ("company_id", "=", company.id)], limit=1
        ) or env["account.fiscal.position"].create({"name": name, "company_id": company.id})
        wanted = {(account(src), account(dest)) for src, dest in mapping.items()}
        have = {(line.account_src_id, line.account_dest_id) for line in position.account_ids}
        if domestic_taxes - position.tax_ids:
            position.tax_ids |= domestic_taxes
        if wanted - have:
            position.write(
                {"account_ids": [(0, 0, {"account_src_id": s.id, "account_dest_id": d.id}) for s, d in wanted - have]}
            )
        vals = _changes(
            config,
            {
                "journal_id": journal(sale_code),
                "invoice_journal_id": journal(sale_code),
                "cash_control": True,
                "set_maximum_difference": False,
                "restrict_price_control": True,
                "default_fiscal_position_id": position,
            },
        )
        if position not in config.fiscal_position_ids:
            vals["fiscal_position_ids"] = [(4, position.id)]
        cash = config.payment_method_ids.filtered("is_cash_count")[:1]
        cash_vals = {}
        if not cash:
            cash = env["pos.payment.method"].create(
                {"name": f"Cash {config.name}", "journal_id": journal(cash_code).id, "company_id": company.id}
            )
            vals["payment_method_ids"] = [(4, cash.id)]
        elif cash.journal_id != journal(cash_code):
            cash_vals = {"journal_id": journal(cash_code).id}
        if vals or cash_vals:
            todo.append((config, vals, cash, cash_vals))

    if todo and env["pos.session"].search_count(
        [("config_id", "in", [config.id for config, *_rest in todo]), ("state", "!=", "closed")]
    ):
        raise UserError(env._("Close every till before installing Finance controls."))
    for config, vals, cash, cash_vals in todo:
        if cash_vals:
            cash.write(cash_vals)
        if vals:
            config.write(vals)


def post_init_hook(env):
    for company in env["res.company"].search([]):
        setup_pos_finance(env, company)
    # Les caissiers deja en place passent en liste « basique » (his_stock_mdm).
    env["pos.config"]._his_sync_tills()
