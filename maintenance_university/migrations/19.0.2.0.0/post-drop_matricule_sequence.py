# -*- coding: utf-8 -*-
"""Supprime la sequence de matricule que ce module ne possede plus.

Retirer data/hr_employee_sequence.xml du manifeste ne suffit pas : un
enregistrement noupdate="1" n'est pas balaye a la mise a jour, il survit en
base. Le code qui l'appelait a disparu, elle est donc inerte — mais laisser un
second compteur de matricule en base est exactement le risque que cette branche
elimine. Verifie sur une base de recette migree depuis la version precedente.
"""

OBSOLETE_CODE = 'hr.employee.matricule.institutionnel'


def migrate(cr, version):
    cr.execute(
        "DELETE FROM ir_sequence_date_range WHERE sequence_id IN "
        "(SELECT id FROM ir_sequence WHERE code = %s)",
        (OBSOLETE_CODE,),
    )
    cr.execute("DELETE FROM ir_sequence WHERE code = %s", (OBSOLETE_CODE,))
    cr.execute(
        "DELETE FROM ir_model_data WHERE module = 'maintenance_university' "
        "AND name = 'seq_hr_employee_matricule_institutionnel'"
    )
