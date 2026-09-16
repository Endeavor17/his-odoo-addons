"""Refuse to drop InSite identity data silently.

19.0.3.0.0 deletes academic.person and retargets every Person link to
his.person. On 2026-09-13 all these tables were empty in production, so no
conversion was written. If that is no longer true, stop here: the upgrade would
otherwise drop real rows without a word.
"""

TABLES = (
    "academic_person",
    "academic_faculty",
    "academic_engagement",
    "insite_candidature",
    "insite_contract",
    "insite_submission",
)


def migrate(cr, version):
    for table in TABLES:
        cr.execute("SELECT to_regclass(%s)", (table,))
        if not cr.fetchone()[0]:
            continue
        # table est une constante du module, pas une entree utilisateur.
        cr.execute(f'SELECT count(*) FROM "{table}"')
        count = cr.fetchone()[0]
        if count:
            raise Exception(
                "insite_recruitment 19.0.3.0.0: %s holds %s row(s). This upgrade "
                "moves InSite onto his.person and has no conversion for existing "
                "data. Write one before upgrading." % (table, count)
            )
