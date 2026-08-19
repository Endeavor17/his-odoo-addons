# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import re
from datetime import date

from . import models

_logger = logging.getLogger(__name__)

# Table de sauvegarde de la reprise. Volontairement une vraie table et non un
# attribut de module : le pre_init et le post_init doivent survivre a un
# redemarrage de worker entre les deux, et cette table est la seule trace de
# l'etat des matricules AVANT migration. Migration a un coup sur un
# identifiant a vie : on ne la supprime pas apres coup.
BACKUP_TABLE = 'his_hr_base_matricule_backup'

# Portion analysable d'un matricule : annee + numero sequentiel.
MATRICULE_NUMBER_RE = re.compile(r'^HIS-(\d{4})-(\d{6})')


def _partner_vals(employee):
    """Rattache la fiche personne au partenaire que l'employe a deja.

    hr.employee.work_contact_id existe deja pour tout employe en base : la
    reprise doit s'y rattacher, jamais creer un second partenaire pour le meme
    humain. C'est verifie explicitement en recette (comptage de res_partner
    identique avant et apres migration).

    Si le partenaire est deja porte par une autre fiche, ou sert plusieurs
    employes, on laisse la delegation en creer un neuf plutot que de rendre le
    matricule ambigu : la collision est journalisee par l'appelant.
    """
    partner = employee.sudo().work_contact_id
    if partner and len(partner.sudo().employee_ids) <= 1:
        taken = employee.env['his.person'].sudo().with_context(
            active_test=False,
        ).search_count([('partner_id', '=', partner.id)])
        if not taken:
            return {'partner_id': partner.id}
        _logger.warning(
            "his_hr_base: le contact %s porte deja une fiche personne ; "
            "l'employe %s recoit un contact distinct.", partner.id, employee.id,
        )
    elif partner:
        _logger.warning(
            "his_hr_base: le contact %s sert %s employes ; l'employe %s recoit "
            "un contact distinct pour garder son matricule non ambigu.",
            partner.id, len(partner.sudo().employee_ids), employee.id,
        )
    return {'name': employee.name or "Employe %s" % employee.id}


def _advance_sequence_past_existing(env):
    """Cale la sequence commune au-dela des numeros deja consommes, par annee.

    L'ancienne sequence de maintenance_university a deja brule des numeros, et
    la nouvelle repart a 1 pour chaque annee. Sans ce calage, une embauche
    datee 2022 recevrait HIS-2022-000001-2 alors que HIS-2022-000001 est deja
    porte par quelqu'un : la cle de controle rend les deux chaines
    differentes, donc la contrainte d'unicite ne dit rien — mais c'est le meme
    numero pour deux personnes, et l'oeil humain ne fait pas la difference.

    Verifie en repetition de migration : sans cet appel, le doublon se produit.
    """
    sequence = env.ref('his_person_core.seq_his_person_matricule_institutionnel')
    highest = {}
    for person in env['his.person'].sudo().with_context(active_test=False).search([]):
        match = MATRICULE_NUMBER_RE.match(person.matricule_institutionnel or '')
        if match:
            year, number = int(match.group(1)), int(match.group(2))
            highest[year] = max(highest.get(year, 0), number)

    DateRange = env['ir.sequence.date_range'].sudo()
    for year, number in sorted(highest.items()):
        date_from, date_to = date(year, 1, 1), date(year, 12, 31)
        date_range = DateRange.search([
            ('sequence_id', '=', sequence.id),
            ('date_from', '=', date_from),
            ('date_to', '=', date_to),
        ], limit=1)
        if date_range:
            if date_range.number_next_actual <= number:
                date_range.number_next_actual = number + 1
        else:
            DateRange.create({
                'sequence_id': sequence.id,
                'date_from': date_from,
                'date_to': date_to,
                'number_next_actual': number + 1,
            })
        _logger.info(
            "his_hr_base: sequence %s calee a %s (plus haut numero repris : %s).",
            year, number + 1, number,
        )


def _column_exists(cr, table, column):
    cr.execute(
        """SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s""",
        (table, column),
    )
    return bool(cr.fetchone())


def pre_init_hook(env):
    """Capture les matricules deja attribues, AVANT redefinition du champ.

    `matricule_institutionnel` existe deja comme vraie colonne sur hr_employee
    (posee par maintenance_university) et peut contenir des valeurs de
    production. Ce module la redefinit en champ related stocke : au chargement,
    l'ORM la recalculera depuis person_id — vide a ce stade — et ecrasera son
    contenu. La lecture doit donc se faire ici, en SQL direct, avant que le
    modele de ce module ne soit charge.
    """
    cr = env.cr
    cr.execute(
        "CREATE TABLE IF NOT EXISTS %s ("
        "  employee_id integer PRIMARY KEY,"
        "  matricule character varying NOT NULL,"
        "  captured_at timestamp without time zone DEFAULT (now() AT TIME ZONE 'UTC')"
        ")" % BACKUP_TABLE
    )
    if not _column_exists(cr, 'hr_employee', 'matricule_institutionnel'):
        # Base neuve : maintenance_university n'est pas encore installe, il n'y
        # a rien a reprendre. Ce n'est pas une erreur.
        _logger.info(
            "his_hr_base: aucune colonne hr_employee.matricule_institutionnel, "
            "rien a reprendre."
        )
        return
    # ON CONFLICT DO NOTHING : si le hook rejoue (deploiement relance apres
    # echec), la capture initiale reste la reference. Ne jamais ecraser une
    # sauvegarde par un etat deja partiellement migre.
    cr.execute(
        "INSERT INTO %s (employee_id, matricule) "
        "SELECT id, matricule_institutionnel FROM hr_employee "
        " WHERE matricule_institutionnel IS NOT NULL "
        "   AND matricule_institutionnel <> '' "
        "ON CONFLICT (employee_id) DO NOTHING" % BACKUP_TABLE
    )
    cr.execute("SELECT count(*) FROM %s" % BACKUP_TABLE)
    _logger.info(
        "his_hr_base: %s matricule(s) captures avant migration.", cr.fetchone()[0],
    )


def post_init_hook(env):
    """Rattache chaque employe a une fiche his.person, sans perdre un matricule.

    Idempotent : un employe deja rattache (person_id renseigne) est ignore.
    Relancer le hook apres un deploiement echoue ne cree aucun doublon.
    """
    cr = env.cr
    Employee = env['hr.employee'].sudo().with_context(active_test=False)
    Person = env['his.person'].sudo().with_context(active_test=False)

    cr.execute(
        "SELECT employee_id, matricule FROM %s ORDER BY employee_id" % BACKUP_TABLE
    )
    captured = cr.fetchall()

    # Une valeur presente deux fois dans la capture signifie que la donnee
    # d'origine portait deja une collision sur un identifiant cense etre
    # unique. On la remonte, on ne la resout pas en silence.
    seen = {}
    duplicates = []
    for employee_id, matricule in captured:
        if matricule in seen:
            duplicates.append((matricule, seen[matricule], employee_id))
        else:
            seen[matricule] = employee_id
    if duplicates:
        for matricule, first_id, second_id in duplicates:
            _logger.error(
                "his_hr_base: COLLISION de matricule preexistante : %s porte par les "
                "employes %s et %s. A arbitrer manuellement.",
                matricule, first_id, second_id,
            )

    migrated = relinked = 0
    for employee_id, matricule in captured:
        employee = Employee.browse(employee_id).exists()
        if not employee or employee.person_id:
            continue  # deja rattache : le hook rejoue, ou l'employe a disparu
        existing = Person.search([('matricule_institutionnel', '=', matricule)], limit=1)
        if existing:
            # Fiche deja creee par un passage precedent interrompu avant
            # l'ecriture de person_id : on la reutilise, on n'en cree pas une
            # seconde avec le meme matricule.
            employee.person_id = existing
            relinked += 1
            continue
        person = Person.create(dict(
            _partner_vals(employee),
            # Valeur explicite : his_person_core.create() n'emet alors AUCUN
            # nouveau matricule et stocke celui-ci tel quel. C'est tout
            # l'objet de la reprise.
            matricule_institutionnel=matricule,
            type_personne='employe',
            source_system='odoo_hr',
            match_method='new',
            external_ref='hr.employee,%s' % employee_id,
        ))
        employee.person_id = person
        migrated += 1

    # Avant d'emettre quoi que ce soit de neuf : caler la sequence au-dela des
    # numeros que l'ancienne a deja consommes.
    _advance_sequence_past_existing(env)

    # Employes sans matricule du tout (base anterieure, ou employe cree hors
    # de ce module) : ils recoivent une fiche et un matricule neufs. Reprend le
    # role du backfill que maintenance_university faisait pour son propre
    # champ, desormais assure ici puisque le champ ne lui appartient plus.
    minted = 0
    for employee in Employee.search([('person_id', '=', False)]):
        sequence_date = employee.date_start_working \
            if 'date_start_working' in employee._fields else False
        employee.person_id = Person.create(dict(
            _partner_vals(employee),
            type_personne='employe',
            source_system='odoo_hr',
            match_method='new',
            external_ref='hr.employee,%s' % employee.id,
            matricule_sequence_date=sequence_date,
        ))
        minted += 1

    _logger.info(
        "his_hr_base: reprise terminee — %s matricule(s) repris, %s rattachement(s) "
        "a une fiche existante, %s matricule(s) neufs, %s collision(s) preexistante(s).",
        migrated, relinked, minted, len(duplicates),
    )
