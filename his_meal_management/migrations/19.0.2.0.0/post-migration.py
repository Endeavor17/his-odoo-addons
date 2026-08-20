"""Move the people this module invented onto the group's identity referential.

Until 19.0.1.1.0 this module carried the HIS Person itself, as fields on
res.partner: matricule_institutionnel, nom_arabe, type_personne, statut, the two
emails, rang_academique, specialite and the faculty links. his_person_core now
owns all of that on `his.person`, so those fields are gone from the Python and
every person they described has to be given a real identity record.

Odoo does not drop a column when a field is removed - it leaves it in place and
stops using it - so the old values are still sitting in res_partner and can be
read here. That is why there is no pre-migration: nothing needs capturing before
the field definitions disappear.

Who gets a his.person: only the partners this module actually treated as people
- a card holder, someone with meal history, or a row carrying type_personne.
Companies, suppliers and Odoo's own internal contacts are left alone; giving
them a matricule would be inventing identities for records that never had one.

WARNING - this issues a permanent identifier per person migrated. A matricule is
assigned once and never reused; there is no clean rollback once they exist.
Rehearse against a copy of the database first.
"""
import logging

_logger = logging.getLogger(__name__)

# The old fields, still readable as orphan columns at this point.
LEGACY_COLUMNS = (
    'matricule_institutionnel', 'nom_arabe', 'type_personne', 'statut',
    'email_institutionnel', 'email_personnel', 'rang_academique', 'specialite',
)


def _existing_columns(cr, table, columns):
    """Only touch what is really there.

    A database installed fresh on 19.0.2.0.0 never had these columns, and a
    partially migrated one may have some of them. Reading the catalogue is
    cheaper than guessing, and it makes this script safe to re-run.
    """
    cr.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s AND column_name IN %s",
        (table, tuple(columns)),
    )
    return [row[0] for row in cr.fetchall()]


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    columns = _existing_columns(cr, 'res_partner', LEGACY_COLUMNS)
    if not columns:
        _logger.info("Nothing to migrate: no legacy identity column on res_partner.")
        return

    selected = ', '.join('p.%s' % column for column in columns)
    # A partner qualifies as a person if this module ever treated it as one.
    # LEFT JOIN on his_person, not a NOT EXISTS: a partner already carrying an
    # identity (an employee migrated by his_hr_base) must be skipped, because
    # his_person_core enforces unique(partner_id) - one contact, one person.
    cr.execute("""
        SELECT p.id, %s
          FROM res_partner p
     LEFT JOIN his_person hp ON hp.partner_id = p.id
         WHERE hp.id IS NULL
           AND (
                EXISTS (SELECT 1 FROM his_meal_card c WHERE c.partner_id = p.id)
             OR EXISTS (SELECT 1 FROM his_meal_subscription s WHERE s.partner_id = p.id)
             OR EXISTS (SELECT 1 FROM his_meal_transaction t WHERE t.partner_id = p.id)
             %s
           )
      ORDER BY p.id
    """ % (
        selected,
        "OR p.type_personne IS NOT NULL" if 'type_personne' in columns else "",
    ))
    rows = cr.fetchall()
    if not rows:
        _logger.info("No partner left to attach to his.person.")
        return

    Person = env['his.person'].sudo()
    created = 0
    for row in rows:
        partner_id, legacy = row[0], dict(zip(columns, row[1:]))

        # type_personne is required on his.person and its selection differs:
        # the socle adds 'employe' and drops nothing we used. A partner with no
        # value recorded is a card holder imported as name + card number, which
        # in this system means a student.
        vals = {
            'partner_id': partner_id,
            'type_personne': legacy.get('type_personne') or 'etudiant',
            # These records predate every adapter: they were typed in or
            # imported by hand into this module, which is what 'manual' means.
            'source_system': 'manual',
        }
        for field, column in (
            ('nom_arabe', 'nom_arabe'),
            ('email_personnel', 'email_personnel'),
            ('rang_academique', 'rang_academique'),
            ('specialite', 'specialite'),
        ):
            if legacy.get(column):
                vals[field] = legacy[column]

        # Only pass a matricule that genuinely exists. his.person.create()
        # stores a pre-existing value untouched - no reformatting, no checksum
        # recomputation - and mints a fresh one otherwise. Passing an empty
        # string would store an empty matricule instead of issuing one.
        if legacy.get('matricule_institutionnel'):
            vals['matricule_institutionnel'] = legacy['matricule_institutionnel']

        person = Person.create(vals)
        created += 1

        # The institutional address fed Odoo's own `email` on the old model;
        # the socle keeps that arrangement, so only fill a gap, never overwrite
        # an address the contact already carries.
        institutional = legacy.get('email_institutionnel')
        if institutional and not person.partner_id.email:
            person.partner_id.email = institutional

        # statut drove res.partner.active before; the socle uses `active`
        # directly. Archived stays archived.
        if legacy.get('statut') == 'archive':
            person.partner_id.active = False

    _logger.info("his.person created for %d partner(s) of his_meal_management.", created)

    # Faculty links: same pairs, new relation table, keyed by person instead of
    # partner. The old table is dropped rather than left behind - a stale copy
    # of a relation is the kind of thing that gets re-read years later.
    cr.execute("SELECT to_regclass('his_person_faculty_rel')")
    if cr.fetchone()[0]:
        cr.execute("""
            INSERT INTO his_faculty_person_rel (faculty_id, person_id)
            SELECT old.faculty_id, hp.id
              FROM his_person_faculty_rel old
              JOIN his_person hp ON hp.partner_id = old.partner_id
         LEFT JOIN his_faculty_person_rel new
                ON new.faculty_id = old.faculty_id AND new.person_id = hp.id
             WHERE new.person_id IS NULL
        """)
        _logger.info("Faculty links moved: %d row(s).", cr.rowcount)
        cr.execute("DROP TABLE his_person_faculty_rel")

    # Finally the orphan columns. Odoo would have left them forever, and a
    # second copy of an identity is exactly what this migration exists to end.
    for column in columns:
        cr.execute('ALTER TABLE res_partner DROP COLUMN "%s"' % column)
    _logger.info("Dropped %d legacy identity column(s) from res_partner.", len(columns))
