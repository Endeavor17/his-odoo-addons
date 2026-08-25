from datetime import timedelta

import psycopg2

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.his_meal_management import post_init_hook


def make_person(env, name, **vals):
    """A person, created where identity now lives.

    Fixtures create a `his.person` and hand back the partner underneath it,
    because that is what the wallet hangs off: the card mirrors onto
    `res.partner.barcode` and the POS sells to a partner. Every assertion about
    credits therefore reads the same as before this module gave up owning
    identity.

    No matricule is passed: his_person_core mints one, and it is the only thing
    allowed to. A test that invented one would be re-testing the socle's own
    suite, badly.

    sudo() because registering a person is a privileged act in this design and
    the meal groups deliberately hold no write access to the referential — the
    POS class below runs as a Meal Officer, who cannot create one. That is the
    rule under test in `test_a_card_cannot_be_issued_to_an_unregistered_contact`,
    not something to weaken here: this is fixture setup, and the officer's real
    workflow is to receive people from HR or the student import.
    """
    vals.setdefault('type_personne', 'etudiant')
    vals.setdefault('source_system', 'manual')
    return env['his.person'].sudo().create({'name': name, **vals})


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
        cls.person = make_person(cls.env, "Ahmed", nom_arabe="أحمد")
        # The wallet hangs off the partner; the person is the identity above it.
        cls.student = cls.person.partner_id
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
        cls.person = make_person(cls.env, "Ahmed", nom_arabe="أحمد")
        cls.student = cls.person.partner_id
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
class TestMealPersonAttributes(TransactionCase):
    """What this module still says about a person, now that the socle owns identity.

    The matricule's format, uniqueness and write-once rules used to be tested
    here. They are his_person_core's rules now, and its own suite tests them
    more thoroughly than this one ever did — it verifies the check digit, which
    this module deliberately refused to compute. Re-testing them here would
    duplicate a contract we no longer own, and duplicated tests rot in exactly
    the way duplicated code does.

    What is left is what this module actually added: the academic attributes and
    the faculty referential, plus the one rule that matters at the till — that
    identity never gates a meal.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plan = cls.env['product.product'].create({
            'name': "Monthly Meal Plan",
            'type': 'service',
            'list_price': 12000.0,
            'meal_credits': 25,
            'meal_validity_days': 30,
        })

    def _person(self, **vals):
        name = vals.pop('name', "Test Person")
        vals.setdefault('nom_arabe', "شخص")
        return make_person(self.env, name, **vals)

    # --- identity belongs to the socle now -------------------------------
    def test_this_module_owns_no_identity_field(self):
        """The fields moved to his.person; leaving copies behind is the bug.

        A second column holding the same fact is how a person ends up with two
        matricules and, eventually, two wallets. This asserts the split stayed
        clean rather than trusting that it did.
        """
        partner_fields = self.env['res.partner']._fields
        for name in ('matricule_institutionnel', 'nom_arabe', 'type_personne',
                     'statut', 'email_institutionnel', 'email_personnel'):
            self.assertNotIn(
                name, partner_fields,
                "%s is still on res.partner: identity belongs to his_person_core" % name,
            )

    def test_this_module_owns_no_matricule_sequence(self):
        """One counter in the group. Two would collide on a lifetime identifier."""
        self.assertFalse(
            self.env['ir.sequence'].sudo().search_count(
                [('code', 'in', ('his.matricule', 'hr.employee.matricule.institutionnel'))]
            ),
        )

    def test_a_person_gets_a_matricule_from_the_socle(self):
        person = self._person()
        self.assertRegex(person.matricule_institutionnel, r'^HIS-\d{4}-\d{6}-[0-9X]$')

    # --- the academic attributes this module adds ------------------------
    def test_an_academic_rank_only_applies_to_a_teacher(self):
        with self.assertRaises(ValidationError):
            self._person(type_personne='etudiant', rang_academique='PROF')
        teacher = self._person(type_personne='enseignant', rang_academique='PROF')
        self.assertEqual(teacher.rang_academique, 'PROF')

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
        self.assertEqual(set(person.faculty_ids.mapped('code')), {'MI', 'ST'})

    # --- no wallet without an identity -----------------------------------
    def test_a_card_cannot_be_issued_to_an_unregistered_contact(self):
        """The officer holds no rights on his.person, but core Odoo lets any
        internal user create a plain contact. Without this guard that is a back
        door to a card holder outside the referential."""
        stranger = self.env['res.partner'].create({'name': "Walk-in"})
        with self.assertRaises(ValidationError):
            self.env['his.meal.card'].create({
                'partner_id': stranger.id,
                'code': card_uid(40),
            })

    def test_credits_cannot_be_granted_to_an_unregistered_contact(self):
        """Same gate from the POS side: selling a plan opens a balance too."""
        stranger = self.env['res.partner'].create({'name': "Walk-in"})
        with self.assertRaises(ValidationError):
            stranger._grant_meal_credits(self.plan)

    # --- identity gates nothing at the till ------------------------------
    def test_a_teacher_can_hold_a_card_and_eat(self):
        """Anyone holding a card eats, whatever their role."""
        teacher = self._person(
            name="Prof Karim", type_personne='enseignant', rang_academique='MCA',
        )
        partner = teacher.partner_id
        card = self.env['his.meal.card'].create({
            'partner_id': partner.id, 'code': card_uid(41),
        })
        self.assertEqual(partner.barcode, card.code)

        partner._grant_meal_credits(self.plan)
        partner._consume_meal_credit()
        self.assertEqual(partner.meal_credits_remaining, 24)

    def test_the_balance_reads_off_the_person_through_delegation(self):
        """No mirrored field: the person sees the partner's wallet directly.

        This is what buys the whole refactor — the wallet stayed on res.partner
        where the barcode and the POS need it, and the person form still shows a
        balance without a single duplicated field.
        """
        person = self._person()
        self.env['his.meal.card'].create({
            'partner_id': person.partner_id.id, 'code': card_uid(42),
        })
        person.partner_id._grant_meal_credits(self.plan)
        self.assertEqual(person.meal_credits_remaining, 25)
        self.assertEqual(person.meal_card_code, card_uid(42))

    def test_archiving_a_person_archives_the_contact(self):
        """One state, not two: `statut` is gone, `active` is delegated."""
        person = self._person()
        self.assertTrue(person.partner_id.active)
        person.active = False
        self.assertFalse(person.partner_id.active)

    def test_a_plain_contact_is_not_forced_through_the_person_rules(self):
        """A supplier is not a HIS person and must stay creatable.

        This is why the socle uses delegation instead of putting identity on
        res.partner: this contact carries no matricule and no person type, and
        nothing in the system asks it to.
        """
        company = self.env['res.partner'].create({'name': "Some Supplier", 'is_company': True})
        self.assertFalse(company.his_person_ids)


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
        person = make_person(self.env, "CHABOUTI Abderrahim").partner_id
        uid = card_uid(1)
        self.env['his.meal.card'].create({'partner_id': person.id, 'code': uid})

        self.assertEqual(person.barcode, uid)
        self.assertEqual(self.env['res.partner'].search([('barcode', '=', uid)]), person)

    def test_leading_zeros_are_not_lost(self):
        """0001063810 is not 1063810. Losing a zero loses the person."""
        person = make_person(self.env, "LAMLOUM Rayane").partner_id
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
        person = make_person(self.env, "CHABOUTI Abderrahim").partner_id
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


@tagged('post_install', '-at_install')
class TestBadgeFromIdentity(TransactionCase):
    """The badge is issued through the card, whichever screen writes it.

    his_person_core declares `numero_carte` as a plain Char and its README says
    that field must be replaced by a model with a lifecycle before the wallet
    stores money. This module is that model, so the field is taken over here:
    same name, same label, same unique constraint, computed from the person's
    active card and writable through an inverse.

    These tests pin both directions and the till's two lookups. His own suite
    pins the rest — this one does not re-test his rules.
    """

    def _person(self, name="Badge Person", **vals):
        return make_person(self.env, name, **vals)

    def test_writing_a_badge_issues_a_card(self):
        person = self._person()
        person.numero_carte = card_uid(50)

        card = person.partner_id.meal_card_ids
        self.assertEqual(len(card), 1, "one badge, one card")
        self.assertEqual(card.code, card_uid(50))
        self.assertEqual(card.state, 'active')
        self.assertEqual(
            person.partner_id.barcode, card_uid(50),
            "the till resolves a scan through the contact's barcode",
        )

    def test_changing_a_badge_replaces_the_card_and_keeps_the_old_one(self):
        """The half a plain Char could not do.

        Overwriting a text field loses the previous number. Here the old card is
        retired and kept, which is what lets anyone answer which card was valid
        when a disputed meal was served — the question his README says must be
        answerable before the wallet holds money.
        """
        person = self._person()
        person.numero_carte = card_uid(51)
        first = person.partner_id.meal_card_ids

        person.numero_carte = card_uid(52)

        cards = person.partner_id.meal_card_ids
        self.assertEqual(len(cards), 2, "the previous card must survive")
        self.assertEqual(first.state, 'replaced')
        active = cards.filtered(lambda c: c.state == 'active')
        self.assertEqual(active.code, card_uid(52))
        self.assertEqual(active.replaced_card_id, first, "the chain is recorded")
        self.assertEqual(person.numero_carte, card_uid(52))
        self.assertEqual(person.partner_id.barcode, card_uid(52))

    def test_clearing_the_badge_stops_it_being_scannable(self):
        person = self._person()
        person.numero_carte = card_uid(53)
        person.numero_carte = False

        self.assertEqual(person.partner_id.meal_card_ids.state, 'blocked')
        self.assertFalse(person.partner_id.barcode)
        self.assertFalse(
            self.env['res.partner'].search([('barcode', '=', card_uid(53))]),
            "a cleared badge must not find anybody",
        )

    def test_a_badge_cannot_be_held_by_two_people(self):
        self._person("First").numero_carte = card_uid(54)
        second = self._person("Second")
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'):
            with self.cr.savepoint():
                second.numero_carte = card_uid(54)

    def test_tapping_a_card_updates_the_person(self):
        """The other direction: the Cards screen is the officer's entry point."""
        person = self._person()
        self.env['his.meal.card'].create({
            'partner_id': person.partner_id.id, 'code': card_uid(55),
        })
        self.assertEqual(person.numero_carte, card_uid(55))

    def test_the_employee_badge_id_follows_the_same_card(self):
        """One physical card: attendance, door access and meals read one number.

        hr.employee.barcode is a stored related to person_id.numero_carte, so
        the chain is card -> person -> employee. If it ever broke, a badge the
        till accepts would be refused at the attendance reader.

        Skipped when his_hr_base is absent: this module has no business
        depending on HR just to serve meals, so the employee half of the chain
        only exists on a database that installed it.
        """
        if 'hr.employee' not in self.env:
            self.skipTest("his_hr_base is not installed: no employee half to check")
        employee = self.env['hr.employee'].sudo().create({'name': "Badge Employee"})
        employee.person_id.numero_carte = card_uid(56)

        self.assertEqual(employee.barcode, card_uid(56))
        self.assertEqual(
            employee.person_id.partner_id.meal_card_ids.code, card_uid(56),
            "the employee's badge is a real card, not a loose string",
        )

    def test_the_till_finds_a_student_by_name_and_by_badge(self):
        """Exactly the two queries the POS itself runs.

        point_of_sale/.../partner_list.js `_getSearchFields` returns
        complete_name and barcode for a typed query, and product_screen.js
        `_getPartnerByBarcode` searches barcode for a tapped one. Both resolve
        res.partner, which is why the badge is mirrored there.
        """
        person = self._person("Meriem Zerrouki")
        person.numero_carte = card_uid(57)
        partner = person.partner_id

        self.assertIn(
            partner,
            self.env['res.partner'].search([('complete_name', 'ilike', "Zerrouki")]),
            "typing a name at the till must find the person",
        )
        self.assertIn(
            partner,
            self.env['res.partner'].search([('barcode', '=', card_uid(57))]),
            "typing or scanning a badge at the till must find the person",
        )


@tagged('post_install', '-at_install')
class TestRestaurantWiring(TransactionCase):
    """The one field joining this module to his_stock_mdm's POS configs.

    Neither module depends on the other and neither should, so the link is made
    by post_init_hook rather than by a <record>. That makes it worth testing:
    a hook has no XML id to fail loudly on, it just quietly does nothing.
    """

    def _restaurant(self):
        return self.env.ref(
            'his_stock_mdm.pos_config_restaurant', raise_if_not_found=False,
        )

    def test_the_restaurant_serves_the_student_meal(self):
        config = self._restaurant()
        if not config:
            self.skipTest("his_stock_mdm is not installed: no Restaurant to wire")
        self.assertEqual(
            config.meal_product_id,
            self.env.ref('his_meal_management.product_daily_meal').product_variant_id,
            "the Student Meal button would report 'Not configured' at the till",
        )

    def test_the_hook_never_overwrites_a_choice_made_at_the_till(self):
        """Re-running it after a failed deployment must not undo a manager."""
        config = self._restaurant()
        if not config:
            self.skipTest("his_stock_mdm is not installed: no Restaurant to wire")
        other = self.env['product.product'].create({
            'name': "Autre Repas", 'type': 'consu', 'available_in_pos': True,
        })
        config.meal_product_id = other
        post_init_hook(self.env)
        self.assertEqual(config.meal_product_id, other)

    def test_the_hook_is_silent_without_his_stock_mdm(self):
        """The meal module has to install on a database that has no stock module."""
        if self._restaurant():
            self.skipTest("his_stock_mdm is installed: the absent case cannot be run here")
        post_init_hook(self.env)  # must not raise
