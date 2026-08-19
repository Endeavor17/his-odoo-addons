from datetime import date, timedelta

import psycopg2

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


def matricule(n):
    """A well-formed matricule reserved for tests.

    Fixtures must never depend on the database being empty: real people and
    these tests share one table, and a hard-coded value collides with whatever
    happens to be there. The final digit is arbitrary — the system stores the
    check digit but does not verify it, because section 2 never says how it is
    computed.
    """
    return f"HIS-{date.today().year}-{990000 + n:06d}-0"


def card_uid(n):
    """A 10-digit card UID reserved for tests.

    Same reasoning as `matricule`: the three real UIDs are live data in this
    database, so a fixture that writes one collides with it. The shape is kept
    honest — ten digits, leading zeros — so the tests still exercise the real
    format. Parsing tests use the genuine UIDs, because they write nothing.
    """
    return f"00009{n:05d}"


@tagged('post_install', '-at_install')
class TestMealCredits(TransactionCase):
    """The smallest set of checks that fails if the credit logic breaks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = cls.env['res.partner'].create({
            'name': "Ahmed",
            'nom_arabe': "أحمد",
            'type_personne': 'etudiant',
            'matricule_institutionnel': matricule(1),
        })
        cls.monthly = cls.env['product.product'].create({
            'name': "Monthly Meal Plan",
            'type': 'service',
            'list_price': 12000.0,
            'meal_credits': 25,
            'meal_validity_days': 30,
        })
        cls.weekly = cls.env['product.product'].create({
            'name': "Weekly Meal Plan",
            'type': 'service',
            'list_price': 3000.0,
            'meal_credits': 6,
            'meal_validity_days': 7,
        })

    def test_purchase_grants_credits_and_validity(self):
        sub = self.student._grant_meal_credits(self.monthly)
        today = fields.Date.context_today(self.student)

        self.assertEqual(sub.credits_total, 25)
        self.assertEqual(sub.credits_used, 0)
        self.assertEqual(sub.credits_remaining, 25)
        self.assertEqual(sub.state, 'active')
        self.assertEqual(sub.date_start, today)
        # A 30-day plan bought today is usable today through day 30.
        self.assertEqual(sub.date_end, today + timedelta(days=29))
        self.assertEqual(self.student.meal_credits_remaining, 25)

        ledger = self.env['his.meal.transaction'].search([('partner_id', '=', self.student.id)])
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger.type, 'purchase')
        self.assertEqual(ledger.credits, 25)
        self.assertEqual(ledger.balance_after, 25)

    def test_every_credit_is_spendable_and_then_it_stops(self):
        self.student._grant_meal_credits(self.monthly)

        for expected_left in range(24, -1, -1):
            self.student._consume_meal_credit()
            self.assertEqual(self.student.meal_credits_remaining, expected_left)

        ledger_before = self.env['his.meal.transaction'].search_count(
            [('partner_id', '=', self.student.id)]
        )
        # The 26th meal is refused, and refusing it writes nothing.
        with self.assertRaises(UserError):
            self.student._consume_meal_credit()
        self.assertEqual(
            self.env['his.meal.transaction'].search_count([('partner_id', '=', self.student.id)]),
            ledger_before,
        )
        self.assertEqual(self.student.meal_credits_remaining, 0)

    def test_expired_subscription_is_not_edible(self):
        sub = self.student._grant_meal_credits(self.weekly)
        sub.write({
            'date_start': fields.Date.context_today(self.student) - timedelta(days=30),
            'date_end': fields.Date.context_today(self.student) - timedelta(days=1),
        })

        self.assertEqual(sub.credits_remaining, 6, "the credits are still there")
        self.assertEqual(self.student.meal_credits_remaining, 0, "but none of them count")
        with self.assertRaises(UserError):
            self.student._consume_meal_credit()

    def test_soonest_to_expire_is_drained_first(self):
        """Otherwise a student loses credits that were about to expire."""
        long_sub = self.student._grant_meal_credits(self.monthly)
        short_sub = self.student._grant_meal_credits(self.weekly)
        self.assertLess(short_sub.date_end, long_sub.date_end)

        self.student._consume_meal_credit()

        self.assertEqual(short_sub.credits_used, 1)
        self.assertEqual(long_sub.credits_used, 0)
        self.assertEqual(self.student.meal_credits_remaining, 30)

    def test_balance_cannot_go_negative_even_by_hand(self):
        """The database refuses it, not just the Python."""
        sub = self.student._grant_meal_credits(self.weekly)
        with self.assertRaises(psycopg2.errors.CheckViolation), mute_logger('odoo.sql_db'):
            with self.cr.savepoint():
                sub.credits_used = sub.credits_total + 1
                sub.flush_recordset()

    def test_active_card_is_reachable_by_scanning_and_a_dead_one_is_not(self):
        card = self.env['his.meal.card'].create({
            'partner_id': self.student.id,
            'code': "HIS-TEST-CARD-1",
        })
        # This is what the POS 'client' barcode rule looks up.
        self.assertEqual(self.student.barcode, "HIS-TEST-CARD-1")
        self.assertEqual(
            self.env['res.partner'].search([('barcode', '=', "HIS-TEST-CARD-1")]),
            self.student,
        )

        card.action_block()
        self.assertFalse(self.student.barcode)
        self.assertFalse(self.env['res.partner'].search([('barcode', '=', "HIS-TEST-CARD-1")]))

    def test_deleting_a_card_stops_it_being_scannable(self):
        """Blocking a card was covered; deleting one was not, and leaked.

        Four people in the live database were still scannable by cards that had
        been deleted, because only create()/write() maintained the mirrored
        barcode. Deleting the record left the code on the person forever.
        """
        card = self.env['his.meal.card'].create({
            'partner_id': self.student.id,
            'code': "HIS-TEST-CARD-DEL",
        })
        self.assertEqual(self.student.barcode, "HIS-TEST-CARD-DEL")

        card.unlink()
        self.assertFalse(self.student.barcode)
        self.assertFalse(
            self.env['res.partner'].search([('barcode', '=', "HIS-TEST-CARD-DEL")]),
            "a deleted card must not leave the person scannable",
        )

    def test_deleting_a_retired_card_leaves_the_new_one_alone(self):
        """The replacement owns the barcode; deleting the old card is a no-op."""
        old = self.env['his.meal.card'].create({
            'partner_id': self.student.id,
            'code': "HIS-TEST-CARD-OLD",
        })
        old.action_block()
        new = self.env['his.meal.card'].create({
            'partner_id': self.student.id,
            'code': "HIS-TEST-CARD-NEW",
        })
        self.assertEqual(self.student.barcode, new.code)

        old.unlink()
        self.assertEqual(self.student.barcode, new.code)

    def test_replacing_a_lost_card_keeps_the_credits(self):
        card = self.env['his.meal.card'].create({
            'partner_id': self.student.id,
            'code': "HIS-TEST-CARD-1",
        })
        self.student._grant_meal_credits(self.monthly)
        self.student._consume_meal_credit(qty=8)
        self.assertEqual(self.student.meal_credits_remaining, 17)

        action = card.action_replace()
        self.assertEqual(card.state, 'replaced')
        self.assertFalse(self.student.barcode, "the lost card stops working immediately")

        # The officer now taps the replacement card into the form the action opens.
        new_card = self.env['his.meal.card'].create({
            'partner_id': action['context']['default_partner_id'],
            'replaced_card_id': action['context']['default_replaced_card_id'],
            'code': "HIS-TEST-CARD-9",
        })

        self.assertEqual(new_card.replaced_card_id, card)
        self.assertEqual(self.student.barcode, new_card.code)
        self.assertEqual(self.student.meal_credits_remaining, 17, "credits follow the person")

    def test_a_student_holds_only_one_active_card(self):
        self.env['his.meal.card'].create({
            'partner_id': self.student.id,
            'code': "HIS-TEST-CARD-1",
        })
        with self.assertRaises(ValidationError):
            self.env['his.meal.card'].create({
                'partner_id': self.student.id,
                'code': "HIS-TEST-CARD-2",
            })

    def test_ledger_is_append_only(self):
        self.student._grant_meal_credits(self.weekly)
        line = self.env['his.meal.transaction'].search([('partner_id', '=', self.student.id)])
        with self.assertRaises(UserError):
            line.credits = 999
        with self.assertRaises(UserError):
            line.unlink()

    def test_correction_is_logged_and_still_cannot_go_negative(self):
        self.student._grant_meal_credits(self.weekly)
        wizard = self.env['his.meal.adjust.wizard'].create({
            'partner_id': self.student.id,
            'credits': -2,
            'reason': "meals never served",
        })
        wizard.action_apply()

        self.assertEqual(self.student.meal_credits_remaining, 4)
        corrections = self.env['his.meal.transaction'].search([
            ('partner_id', '=', self.student.id), ('type', '=', 'adjust'),
        ])
        self.assertEqual(len(corrections), 2)
        self.assertEqual(sum(corrections.mapped('credits')), -2)
        self.assertEqual(corrections[0].note, "meals never served")

        over = self.env['his.meal.adjust.wizard'].create({
            'partner_id': self.student.id,
            'credits': -99,
            'reason': "too much",
        })
        # All or nothing: a correction that runs out halfway must leave no trace,
        # which is what the rollback around the failing call proves.
        with self.assertRaises(UserError):
            with self.cr.savepoint():
                over.action_apply()
        self.assertEqual(self.student.meal_credits_remaining, 4)


@tagged('post_install', '-at_install')
class TestMealCreditsAtThePos(AccountTestInvoicingCommon):
    """The POS hook is where credits really move, so it gets its own checks.

    Built on the accounting test base because creating a pos.config needs a
    chart of accounts and a bank journal.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Unlike the class above, this one runs as a real (non-superuser) user,
        # so the access rules apply. It needs POS administration to build a
        # config and a session, and the officer group to read the ledger back.
        cls.env.user.group_ids |= (
            cls.env.ref('point_of_sale.group_pos_manager')
            | cls.env.ref('his_meal_management.group_meal_officer')
        )
        cls.student = cls.env['res.partner'].create({
            'name': "Ahmed",
            'nom_arabe': "أحمد",
            'type_personne': 'etudiant',
            'matricule_institutionnel': matricule(2),
        })
        cls.monthly = cls.env['product.product'].create({
            'name': "Monthly Meal Plan",
            'type': 'service',
            'list_price': 12000.0,
            'meal_credits': 25,
            'meal_validity_days': 30,
            'available_in_pos': True,
        })
        cls.daily_meal = cls.env['product.product'].create({
            'name': "Daily Meal",
            'type': 'consu',
            'list_price': 600.0,
            'available_in_pos': True,
        })
        cls.config = cls.env['pos.config'].create({
            'name': "Test Restaurant",
            'meal_product_id': cls.daily_meal.id,
        })
        cls.config.open_ui()
        cls.session = cls.config.current_session_id

    def _seed_credits(self):
        """Put a plan on the student the way the server does it.

        sudo() because nobody - not even an officer - may create a subscription
        directly; that is the point of the access rules.
        """
        return self.student.sudo()._grant_meal_credits(self.monthly)

    def _order(self, product, qty=1, price_unit=0.0, partner=None):
        """A validated-looking order, straight to the hook under test."""
        return self.env['pos.order'].create({
            'company_id': self.env.company.id,
            'session_id': self.session.id,
            'partner_id': (partner or self.student).id if partner is not False else False,
            'amount_tax': 0.0,
            'amount_total': price_unit * qty,
            'amount_paid': price_unit * qty,
            'amount_return': 0.0,
            'lines': [Command.create({
                'product_id': product.id,
                'qty': qty,
                'price_unit': price_unit,
                'price_subtotal': price_unit * qty,
                'price_subtotal_incl': price_unit * qty,
            })],
        })

    def test_selling_a_plan_grants_the_credits(self):
        order = self._order(self.monthly, price_unit=12000.0)
        order._apply_meal_credits()

        self.assertEqual(self.student.meal_credits_remaining, 25)
        sub = self.env['his.meal.subscription'].search([('partner_id', '=', self.student.id)])
        self.assertEqual(len(sub), 1)
        self.assertEqual(sub.pos_order_id, order)

    def test_a_free_meal_line_spends_exactly_one_credit(self):
        self._seed_credits()
        order = self._order(self.daily_meal, qty=1, price_unit=0.0)
        order._apply_meal_credits()

        self.assertEqual(self.student.meal_credits_remaining, 24)
        line = self.env['his.meal.transaction'].search(
            [('pos_order_id', '=', order.id), ('type', '=', 'consume')]
        )
        self.assertEqual(len(line), 1)
        self.assertEqual(line.credits, -1)
        self.assertEqual(line.balance_after, 24)
        self.assertEqual(line.config_id, self.config, "the ledger records where it happened")
        self.assertEqual(line.user_id, self.env.user, "and who was at the till")

    def test_a_paying_customer_does_not_touch_anyones_balance(self):
        """The same product at its real price is a walk-in sale, not a credit."""
        self._seed_credits()
        order = self._order(self.daily_meal, qty=1, price_unit=600.0)
        order._apply_meal_credits()

        self.assertEqual(self.student.meal_credits_remaining, 25)
        self.assertFalse(self.env['his.meal.transaction'].search([('pos_order_id', '=', order.id)]))

    def test_a_resynced_order_does_not_charge_twice(self):
        self._seed_credits()
        order = self._order(self.daily_meal, qty=1, price_unit=0.0)
        order._apply_meal_credits()
        order._apply_meal_credits()
        order._apply_meal_credits()

        self.assertEqual(self.student.meal_credits_remaining, 24)

    def test_a_student_with_no_credits_cannot_be_served(self):
        order = self._order(self.daily_meal, qty=1, price_unit=0.0)
        with self.assertRaises(UserError):
            with self.cr.savepoint():
                order._apply_meal_credits()
        self.assertFalse(self.env['his.meal.transaction'].search([('pos_order_id', '=', order.id)]))

    def test_a_meal_without_a_student_is_refused(self):
        order = self._order(self.daily_meal, qty=1, price_unit=0.0, partner=False)
        with self.assertRaises(UserError):
            with self.cr.savepoint():
                order._apply_meal_credits()

    def test_the_meal_product_stays_sellable_at_the_till(self):
        """It must not be a POS "special" product.

        POS hides every special product from the grid (getExcludedProductIds in
        pos_store.js), which is right for a tip or a discount and wrong here: a
        person with no credits pays the normal price for exactly this product, so
        the cashier has to be able to find it.
        """
        self.assertNotIn(
            self.daily_meal, self.config._get_special_products(),
            "marking the meal product special would hide it from the cashier",
        )

    def test_two_meals_on_one_order_spend_two_credits(self):
        self._seed_credits()
        order = self._order(self.daily_meal, qty=2, price_unit=0.0)
        order._apply_meal_credits()

        self.assertEqual(self.student.meal_credits_remaining, 23)
        self.assertEqual(
            self.env['his.meal.transaction'].search_count(
                [('pos_order_id', '=', order.id), ('type', '=', 'consume')]
            ),
            2,
            "one ledger line per meal, not one per order",
        )


@tagged('post_install', '-at_install')
class TestHisIdentity(TransactionCase):
    """Sections 2 and 3 of the HIS data model.

    A matricule is assigned once and never reused, so these rules have to hold
    before real people are imported: a wrong identifier cannot be quietly
    corrected afterwards.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']
        cls.plan = cls.env['product.product'].create({
            'name': "Monthly Meal Plan",
            'type': 'service',
            'list_price': 12000.0,
            'meal_credits': 25,
            'meal_validity_days': 30,
        })

    def _person(self, **vals):
        base = {'name': "Test Person", 'nom_arabe': "شخص", 'type_personne': 'etudiant'}
        base.update(vals)
        return self.Partner.create(base)

    # --- the identifier -------------------------------------------------
    def test_a_correct_matricule_is_accepted(self):
        person = self._person(matricule_institutionnel=matricule(10))
        self.assertEqual(person.matricule_institutionnel, matricule(10))

    def test_the_documents_own_examples_are_accepted(self):
        """The check digit is stored, not second-guessed.

        Section 2 never says how the digit is computed, and its two examples
        carry the same one for different sequence numbers, so nothing can be
        inferred. An earlier version enforced Luhn and rejected both of these —
        which would have rejected HIS's real numbers too.
        """
        for good in ("HIS-2026-000042-7", "HIS-2026-000125-7"):
            with self.subTest(good=good):
                with self.cr.savepoint():
                    person = self._person(matricule_institutionnel=good)
                    self.assertEqual(person.matricule_institutionnel, good)

    def test_a_malformed_matricule_is_refused(self):
        for bad in (
            "HIS-2026-000042",       # no check digit
            "HIS-26-000042-5",       # two-digit year
            "HIS-2026-42-5",         # sequence not padded to six
            "HIS-2026-ABCDEF-5",     # letters where digits belong
            "XXX-2026-000042-5",     # wrong prefix
            "his-2026-000042-5",     # lower case prefix
            " HIS-2026-000042-5",    # stray whitespace
        ):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                with self.cr.savepoint():
                    self._person(matricule_institutionnel=bad)

    def test_a_matricule_is_assigned_once_and_never_changed(self):
        person = self._person(matricule_institutionnel=matricule(10))
        with self.assertRaises(UserError):
            person.matricule_institutionnel = "HIS-2026-000043-3"
        self.assertEqual(person.matricule_institutionnel, matricule(10))

    def test_a_matricule_belongs_to_one_person_only(self):
        self._person(matricule_institutionnel=matricule(10))
        with self.assertRaises(psycopg2.errors.UniqueViolation), mute_logger('odoo.sql_db'):
            with self.cr.savepoint():
                self._person(matricule_institutionnel=matricule(10))
                self.Partner.flush_model()

    def test_this_system_never_invents_a_matricule(self):
        """HIS issues them. An earlier version minted them from a 9xxxxx block.

        Two systems allocating into one identifier space, with only a local
        unique constraint between them, cannot end well — and the block matched
        nothing in section 2, where NNNNNN is a plain sequential number.
        """
        self.assertFalse(
            hasattr(self.Partner, 'action_assign_matricule'),
            "the Assign button is gone",
        )
        self.assertFalse(
            self.env['ir.sequence'].search([('code', '=', 'his.matricule')]),
            "the matricule sequence is gone",
        )

    # --- the matricule gates nothing -------------------------------------
    def test_a_person_with_no_matricule_can_hold_a_card_and_eat(self):
        """The whole point of the change: identity at the till is the card."""
        plan = self.env['product.product'].create({
            'name': "Monthly Meal Plan",
            'type': 'service',
            'meal_credits': 25,
            'meal_validity_days': 30,
        })
        person = self.Partner.create({'name': "No Matricule"})
        self.assertFalse(person.matricule_institutionnel)

        self.env['his.meal.card'].create({
            'partner_id': person.id,
            'code': card_uid(30),
        })
        self.assertEqual(person.barcode, card_uid(30))

        person._grant_meal_credits(plan)
        person._consume_meal_credit()
        self.assertEqual(person.meal_credits_remaining, 24)

    def test_a_bare_card_and_name_row_imports_into_a_usable_person(self):
        """Exactly the shape of the real sheet: card number and name, nothing else.

        No matricule, no type_personne, no Arabic name. `load()` is the engine
        behind Odoo's CSV importer, so this is the real import path.
        """
        result = self.Partner.load(
            ['name', 'meal_card_ids/code'],
            [["IMPORTED Person", card_uid(31)]],
        )
        self.assertFalse(result['messages'], result['messages'])

        person = self.Partner.browse(result['ids'])
        self.assertFalse(person.matricule_institutionnel)
        self.assertFalse(person.type_personne)
        self.assertEqual(person.meal_card_ids.code, card_uid(31))
        self.assertEqual(
            self.Partner.search([('barcode', '=', card_uid(31))]), person,
            "the imported row is immediately scannable at the till",
        )

    # --- the rest of Person ---------------------------------------------
    def test_an_arabic_name_is_recorded_but_not_required(self):
        """A deliberate, documented deviation from section 2.

        The specification says the Latin and Arabic names coexist in every
        observed source, "jamais l'un sans l'autre", and the constraint was
        written and then relaxed on request: the real lists carry Latin names
        only, and a rule that rejects every row of every import is worse than a
        recorded gap. This test exists so the deviation stays a decision rather
        than quietly becoming an accident — if the sources ever carry both, put
        the constraint back and invert it.
        """
        latin_only = self.Partner.create({'name': "No Arabic", 'type_personne': 'etudiant'})
        self.assertFalse(latin_only.nom_arabe)

        both = self._person(name="Karim", nom_arabe="كريم")
        self.assertEqual(both.nom_arabe, "كريم")

    def test_a_plain_contact_is_not_forced_through_the_person_rules(self):
        """A supplier or a company is not a HIS person and must stay creatable."""
        company = self.Partner.create({'name': "Some Supplier", 'is_company': True})
        self.assertFalse(company.type_personne)
        self.assertFalse(company.nom_arabe)

    def test_an_academic_rank_only_applies_to_a_teacher(self):
        with self.assertRaises(ValidationError):
            self._person(type_personne='etudiant', rang_academique='PROF')
        teacher = self._person(type_personne='enseignant', rang_academique='PROF')
        self.assertEqual(teacher.rang_academique, 'PROF')

    def test_archiving_a_person_archives_the_contact(self):
        person = self._person(statut='actif')
        self.assertTrue(person.active)
        person.statut = 'archive'
        self.assertFalse(person.active)

    def test_odoo_email_follows_the_specification_fields(self):
        student = self._person(email_personnel="ahmed@gmail.com")
        self.assertEqual(
            student.email, "ahmed@gmail.com",
            "a student has only a personal address",
        )
        teacher = self._person(
            type_personne='enseignant',
            email_institutionnel="a.b@his.edu.dz",
            email_personnel="a.b@gmail.com",
        )
        self.assertEqual(
            teacher.email, "a.b@his.edu.dz",
            "the institutional address wins when there is one",
        )

    # --- faculties, section 3 -------------------------------------------
    def test_the_six_faculty_codes_are_seeded(self):
        codes = set(self.env['his.faculty'].search([]).mapped('code'))
        self.assertEqual(codes, {'MI', 'SEGC', 'DSP', 'SHS', 'ST', 'EDU'})

    def test_edu_is_flagged_as_unconfirmed(self):
        """The source document records that no catalogue was received for EDU."""
        edu = self.env['his.faculty'].search([('code', '=', 'EDU')])
        self.assertFalse(edu.name_confirmed)

    def test_a_person_can_belong_to_more_than_one_faculty(self):
        """Section 3 requires many-to-many; a single field would lose this."""
        faculties = self.env['his.faculty'].search([('code', 'in', ('MI', 'ST'))])
        person = self._person(faculty_ids=[Command.set(faculties.ids)])
        self.assertEqual(len(person.faculty_ids), 2)
        self.assertEqual(set(person.faculty_ids.mapped('code')), {'MI', 'ST'})

    # --- the role coupling is gone ---------------------------------------
    def test_a_teacher_can_hold_a_card_and_eat(self):
        """The matricule is never tied to a role, so neither is the meal account."""
        teacher = self._person(
            name="Prof Karim",
            type_personne='enseignant',
            rang_academique='MCA',
            matricule_institutionnel=matricule(12),
        )
        card = self.env['his.meal.card'].create({
            'partner_id': teacher.id,
            'code': "HIS-TEST-CARD-3",
        })
        self.assertEqual(teacher.barcode, card.code)

        teacher._grant_meal_credits(self.plan)
        self.assertEqual(teacher.meal_credits_remaining, 25)
        teacher._consume_meal_credit()
        self.assertEqual(teacher.meal_credits_remaining, 24)


@tagged('post_install', '-at_install')
class TestRfidScanning(TransactionCase):
    """The scanning contract, pinned against Odoo's own barcode parser.

    These are real UIDs off real cards. The reader types the ten digits and an
    Enter, so as far as Odoo is concerned it is a barcode scanner — which means a
    single `barcode.rule` is the entire hardware integration, and these tests are
    what stop someone "simplifying" its pattern back into a bug.
    """

    REAL_UIDS = {
        "0007197786": "CHABOUTI Abderrahim",
        "0001063810": "LAMLOUM Rayane",
        "0007089073": "BOUNOUA MOHAMED",
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.nomenclature = cls.env.ref('barcodes.default_barcode_nomenclature')

    def _parse(self, code):
        return self.nomenclature.parse_barcode(code)

    def test_a_real_card_uid_is_recognised_as_a_customer(self):
        for uid in self.REAL_UIDS:
            with self.subTest(uid=uid):
                self.assertEqual(
                    self._parse(uid)['type'], 'client',
                    f"{uid} must route to the customer lookup, not the product catalogue",
                )

    def test_the_rule_beats_the_lot_and_product_rules(self):
        """A UID starting '10' would hit the Lot rule at sequence 80.

        None of the three real cards happens to start that way, which is exactly
        why this is tested: sitting below sequence 80 the rule would look correct
        today and fail on some future card.
        """
        self.assertEqual(self._parse("1012345678")['type'], 'client')

    def test_a_thirteen_digit_product_barcode_still_reads_as_a_product(self):
        """The catalogue must not be hijacked. This is what the trailing $ buys."""
        self.assertEqual(self._parse("5449000000996")['type'], 'product')

    def test_neither_shorter_nor_longer_numbers_are_claimed(self):
        for code in ("12345678", "123456789", "12345678901"):
            with self.subTest(code=code):
                self.assertNotEqual(
                    self._parse(code)['type'], 'client',
                    f"{code} is not a 10-digit UID and must not be treated as a card",
                )

    def test_the_parsed_code_is_handed_over_intact(self):
        """POS looks the partner up by `code`, so it must survive parsing whole."""
        parsed = self._parse("0001063810")
        self.assertEqual(parsed['code'], "0001063810")

    def test_a_uid_resolves_to_its_person_the_way_pos_resolves_it(self):
        """Reproduces `_barcodePartnerAction`: search res.partner on barcode."""
        person = self.env['res.partner'].create({
            'name': "CHABOUTI Abderrahim",
            'type_personne': 'etudiant',
            'matricule_institutionnel': matricule(20),
        })
        uid = card_uid(1)
        self.env['his.meal.card'].create({'partner_id': person.id, 'code': uid})

        self.assertEqual(person.barcode, uid)
        self.assertEqual(self.env['res.partner'].search([('barcode', '=', uid)]), person)

    def test_leading_zeros_are_not_lost(self):
        """0001063810 is not 1063810. Losing a zero loses the person."""
        person = self.env['res.partner'].create({
            'name': "LAMLOUM Rayane",
            'type_personne': 'etudiant',
            'matricule_institutionnel': matricule(21),
        })
        uid = card_uid(2)                     # 0000900002
        card = self.env['his.meal.card'].create({'partner_id': person.id, 'code': uid})

        self.assertEqual(card.code, uid)
        self.assertEqual(person.barcode, uid)
        self.assertFalse(
            self.env['res.partner'].search([('barcode', '=', uid.lstrip('0'))]),
            "the un-padded number must not find anybody",
        )

    def test_replacing_a_card_asks_for_a_tap_instead_of_inventing_a_code(self):
        """An RFID code cannot be minted: it has to be read off the new card."""
        person = self.env['res.partner'].create({
            'name': "CHABOUTI Abderrahim",
            'type_personne': 'etudiant',
            'matricule_institutionnel': matricule(23),
        })
        card = self.env['his.meal.card'].create({
            'partner_id': person.id,
            'code': card_uid(3),
        })

        action = card.action_replace()

        self.assertEqual(card.state, 'replaced')
        self.assertFalse(person.barcode, "the retired card stops being scannable at once")
        self.assertFalse(
            person.meal_card_ids.filtered(lambda c: c.state == 'active'),
            "no card is created until a real one is tapped",
        )
        self.assertEqual(action['res_model'], 'his.meal.card')
        self.assertNotIn('res_id', action)
        self.assertEqual(action['context']['default_partner_id'], person.id)
        self.assertEqual(action['context']['default_replaced_card_id'], card.id)
