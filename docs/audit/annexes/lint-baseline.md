# Annex: lint baseline (2026-09-15, `main` @ `2bd6e37`)

The vendored OCA module `web_responsive/` was excluded, since its upstream owns it. No config file is committed yet; the commands below are the whole configuration.

## Tools and versions

| Tool | Version | Scope |
|---|---|---|
| ruff | 0.16.7 | Python: `E,W,F,B,S,UP,SIM,C90,PL,I,N,RUF,PERF,T20,ERA` |
| ruff format | 0.16.7 | Python formatting |
| pylint + pylint-odoo | 4.0.8 | Python, manifests, XML/CSV, with `--valid-odoo-versions=19.0` |
| eslint | 9 (`recommended`) | the 10 JS files |
| gitleaks | latest | all git history (174 commits) |

## Totals

| Check | Result |
|---|---|
| ruff check | **1,333 findings**, 74 auto-fixable (212 more with unsafe fixes) |
| ruff format | **197 of 275 files** would be reformatted |
| pylint-odoo | **1,743 messages**, score 8.38/10 |
| eslint | **0 problems** |
| gitleaks | **0 leaks** |

## ruff: what the 1,333 are

| Count | Rule | Reading |
|---|---|---|
| 598 | E501 line-too-long | Style. Settled by `ruff format` plus a line length of 120. |
| 160 | F401 unused-import | **158 are Odoo's `__init__.py` imports**, which Odoo needs. Ignore F401 in `__init__.py`. |
| 134 | UP031 printf formatting | Style, auto-fixable. |
| 67 | N806 variable naming | French names in capitals (`Person = env[...]`), an Odoo idiom. Ignore. |
| 57 | T201 print | All in `tools/` and `docs/` shell scripts. Allowed there. |
| 52 | I001 unsorted imports | Auto-fixable. |
| 47 | F821 undefined-name | All in `odoo shell` scripts that use `env` (`tools/`, `his_crm_pipeline/docs/seed_demo_tableaux.py`). **Not bugs.** |
| 19 | B018 useless-expression | Every `__manifest__.py` is a bare dict, as Odoo requires. Ignore for manifests. |
| 18 | RUF012 mutable class default | Class-level dicts used as constants. Low risk. |
| 7 | S608 SQL built from strings | All use constant table names (migrations, `his_hr_base/__init__.py`). **No injection path.** Annotate each one. |
| 6 | C901 too complex | See the structure annex. |
| 3 | B023 loop variable in closure | All three lambdas are called at once inside `filtered()`. **False positives.** |
| rest | about 70 | Small simplifications and naming. |

## pylint-odoo: what the 1,743 are

| Count | Message | Reading |
|---|---|---|
| 349 | W0212 protected-access | Calling `_private` methods across models, which is normal in Odoo. Disable. |
| 291 | W8161 prefer-env-translation | `_()` should become `self.env._()` (Odoo 18+ API). Real, and mechanical. |
| 156 | W8113 attribute-string-redundant | `string=` equals the field name. Cleanup. |
| 121 | C0209 consider-using-f-string | Style. |
| 26 | C8107 translation-required | User-facing `UserError` text not wrapped in `_()`. **Real**: it can't be translated. |
| 19+22+19 | manifest keys | Missing `author`, deprecated or superfluous keys. Mechanical. |
| 7 | E8140 no-raise-unlink | `unlink()` raises to protect records. Used on purpose (append-only ledger). Use `@api.ondelete` instead, which is the Odoo 17+ idiom and survives uninstall. |
| 4 | E8103 sql-injection | `his_hr_base/__init__.py`, constant table name. False positive. |
| 2 | E8148 inheritable-method-lambda | `default=_default_stage_id` in `maintenance_university`. Real, small. |
| 1 | E1102 not-callable | `getattr` dispatch in the scoring engine. False positive. |
| 14 | R0801 duplicate-code | See the structure annex. |
| 6 | C8112 missing-readme | `campus_identity_bridge`, `his_academic_base`, `his_access_base`, `his_pos_partner_scope`, `his_theme`, `insite_recruitment` |

## Deprecated APIs still in use

- `from odoo.osv import expression` at `his_person_core/models/his_person.py:7`. Deprecated in 19 in favour of `odoo.fields.Domain`; will break in 20.
- `t-esc` in `campus_teacher_management/static/src/dashboard/dashboard.xml` (10 uses). OWL prefers `t-out`. Both escape, so this is safe.

## Re-run

```sh
docker run --rm -v "<repo>:/r:ro" -w /r python:3.12-slim sh -c '
  pip install -q ruff pylint-odoo &&
  ruff check . --exclude web_responsive --select E,W,F,B,S,UP,SIM,C90,PL,I,N,RUF,PERF,T20,ERA --statistics &&
  ruff format . --exclude web_responsive --check &&
  pylint --load-plugins=pylint_odoo --valid-odoo-versions=19.0 \
    --disable=import-error,missing-docstring,too-few-public-methods <modules> tools'
```
