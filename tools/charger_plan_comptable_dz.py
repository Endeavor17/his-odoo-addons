# Charge le plan comptable algerien (l10n_dz) sur la societe principale.
#
# Le POS exige un plan comptable pour creer une pos.config : ce script le met
# en place avant l'installation de his_stock_mdm / his_meal_management, en CI
# comme pour monter une base de recette. Installer le module l10n_dz ne suffit
# pas — il faut charger son modele sur la societe (ce que fait l'assistant de
# comptabilite en interactif).
#
# A lancer via `odoo shell` : odoo shell -d <base> < tools/charger_plan_comptable_dz.py
# (fichier plutot qu'un heredoc : le terminateur d'un heredoc indente dans un
# `run:` YAML n'est pas reconnu, ce qui cassait l'etape de CI).
env["account.chart.template"].try_loading("dz", company=env.ref("base.main_company"), install_demo=False)
env.cr.commit()
print(
    "Plan comptable dz charge ; journaux bancaires :",
    env["account.journal"].search_count([("type", "=", "bank")]),
)
