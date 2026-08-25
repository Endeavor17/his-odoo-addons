"""Remove the matricule generator left behind by version 19.0.1.0.0.

Deleting a record from a data file does not delete it from databases that
already have it — especially under `noupdate="1"`. So the `his.matricule`
sequence, which minted identifiers from a reserved 900000 block, survives a
plain upgrade and stays available to anything that asks for it.

The block was invented here to avoid colliding with HIS, and matched nothing in
section 2 of the data model, where NNNNNN is simply a sequential six-digit
number. HIS issues matricules; this system only records them.

Only the sequence is removed. Matricules already written onto people are left
alone: they are permanent by design ("assigné une seule fois, jamais réutilisé"),
and a migration cannot tell one this system fabricated from one HIS legitimately
issued in the same range. Clearing those is a deliberate, local decision.
"""


def migrate(cr, version):
    cr.execute("""
        DELETE FROM ir_sequence
         WHERE code = 'his.matricule'
    """)
    removed = cr.rowcount
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'his_meal_management'
           AND name = 'seq_matricule'
    """)
    if removed:
        from odoo import api, SUPERUSER_ID
        env = api.Environment(cr, SUPERUSER_ID, {})
        env['ir.logging'].create({
            'name': 'his_meal_management',
            'type': 'server',
            'level': 'INFO',
            'dbname': cr.dbname,
            'message': (
                "Removed the his.matricule sequence: matricules are issued by "
                "HIS and are no longer generated here."
            ),
            'path': 'migrations/19.0.1.1.0/post-migration.py',
            'func': 'migrate',
            'line': '0',
        })
