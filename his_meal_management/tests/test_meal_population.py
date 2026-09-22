"""Fifty students, a term of tills, and every way someone might eat for free.

The suite next door checks one rule at a time. This one exists for a different
worry: that the rules are each right and the *account* still drifts - a half
credit lost in a split, a balance that disagrees with its own ledger, a meal
that gets eaten twice, a cashier who finds the one line of the till that moves
food without moving credits.

Three classes, three questions:

* `TestFiftyStudentsOverATerm` puts a population through a term's worth of
  orders and then asks the books to balance. It never asserts a single
  student's balance against a magic number; it asserts *identities* that have
  to hold whatever the sequence was - the ledger against the subscriptions, the
  credits granted against the credits eaten, and the DA value of what was
  served against the DA value of what was paid for.

* `TestWaysToEatForFree` is the adversary. Each test is somebody trying
  something at the till, and the assertion is what the server does about it.

* `TestWhatTheTillReallySends` goes through `sync_from_ui`, the genuine entry
  point the browser calls, rather than through `_apply_meal_credits` directly -
  because a rule that is right and unwired is still a free meal.

The shadow ledger in the first class is deliberately written in halves of a
credit as integers. Every amount this module moves is a multiple of 0.5, so
integer halves are exact by construction: if the shadow and the database
disagree, the database drifted, not the arithmetic.
"""

import random
from datetime import timedelta

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import float_compare

from .test_meal_credits import make_person

# One credit is one 600 DA meal, a half credit is one 300 DA meal. The money
# assertions below convert with this and nothing else: if the price sheet ever
# stops lining up with the credit scheme, they are what says so.
DA_PER_CREDIT = 600.0

# Deterministic on purpose. A random population that fails once and passes on
# the retry tells you nothing; this one fails the same way every time, and the
# seed is the only thing to change to go looking for another shape of trouble.
SEED = 20260920


class MealShadow:
    """What the balance ought to be, kept independently of Odoo.

    Amounts are integers counting half-credits. `pool` is the subscriptions in
    the order they may be eaten - which, for the shipped offer, is the order
    they were bought in, since nothing in it expires.
    """

    def __init__(self):
        self.pool = []  # remaining half-credits per subscription, oldest first
        self.granted = 0  # every half-credit ever put on this person
        self.eaten = 0  # every half-credit ever taken off a subscription
        self.allowance_used = 0  # meals taken on an empty card this cycle
        self.debt = 0  # half-credits owed from those meals
        # The allowance belongs to subscribers only: someone who never bought a
        # plan is turned away on an empty card, and a hand correction does not
        # buy the right to run one empty either.
        self.ever_bought_a_plan = False

    @property
    def balance(self):
        return sum(self.pool)

    def snapshot(self):
        return (list(self.pool), self.granted, self.eaten, self.allowance_used, self.debt)

    def restore(self, snapshot):
        pool, self.granted, self.eaten, self.allowance_used, self.debt = snapshot
        self.pool = list(pool)

    def grant(self, halves, from_plan=True):
        self.ever_bought_a_plan = self.ever_bought_a_plan or from_plan
        self.pool.append(halves)
        self.granted += halves
        # Settle what was eaten on an empty card, out of what just arrived.
        repay = min(self.debt, self.balance)
        if repay > 0:
            self.consume(repay, overdraft=False)
        # A top-up is its own reset: whatever is still owed falls behind the
        # new cycle boundary and is written off, exactly as the module does it.
        self.allowance_used = 0
        self.debt = 0

    def consume(self, halves, overdraft=False):
        """Returns True if the meal was served, False if it was refused.

        A refusal leaves the shadow untouched, the way a raised UserError rolls
        the real transaction back.
        """
        before = self.snapshot()
        left = halves
        while left > 0:
            available = next((i for i, rest in enumerate(self.pool) if rest > 0), None)
            if available is None:
                if overdraft and self.ever_bought_a_plan and self.allowance_used < 2:
                    self.allowance_used += 1
                    self.debt += left
                    return True
                self.restore(before)
                return False
            take = min(self.pool[available], left)
            self.pool[available] -= take
            self.eaten += take
            left -= take
        return True


@tagged("post_install", "-at_install")
class TestFiftyStudentsOverATerm(AccountTestInvoicingCommon):
    """A population, a term of orders, and books that have to balance."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref("point_of_sale.group_pos_manager") | cls.env.ref(
            "his_meal_management.group_meal_officer"
        )

        # The shipped offer itself, not a fixture that resembles it. If someone
        # edits a pack's credit count in data/meal_plans.xml, this population
        # eats the new one.
        ref = cls.env.ref
        cls.plans = [
            ref(f"his_meal_management.{name}").product_variant_id
            for name in (
                "product_plan_300_weekly",
                "product_plan_300_monthly",
                "product_plan_300_semester",
                "product_plan_weekly",
                "product_plan_monthly",
                "product_plan_semester",
            )
        ]
        cls.meal_300 = ref("his_meal_management.product_meal_300").product_variant_id
        cls.meal_600 = ref("his_meal_management.product_daily_meal").product_variant_id

        cls.config = cls.env["pos.config"].create({"name": "Population Restaurant"})
        cls.config.open_ui()
        cls.session = cls.config.current_session_id

        cls.students = [make_person(cls.env, f"Etudiant {n:02d}").partner_id for n in range(50)]

    # ------------------------------------------------------------------
    # Driving the till
    # ------------------------------------------------------------------
    def _order(self, partner, lines):
        """`lines` is a list of (product, qty, price_unit)."""
        total = sum(qty * price for _p, qty, price in lines)
        return self.env["pos.order"].create(
            {
                "company_id": self.env.company.id,
                "session_id": self.session.id,
                "partner_id": partner.id if partner else False,
                "amount_tax": 0.0,
                "amount_total": total,
                "amount_paid": total,
                "amount_return": 0.0,
                "lines": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "qty": qty,
                            "price_unit": price,
                            "price_subtotal": qty * price,
                            "price_subtotal_incl": qty * price,
                        }
                    )
                    for product, qty, price in lines
                ],
            }
        )

    def _ring_up(self, partner, lines):
        """Validate an order the way the server does, refusal included."""
        order = self._order(partner, lines)
        try:
            with self.env.cr.savepoint():
                order._apply_meal_credits()
        except UserError:
            return False
        return True

    def _halves(self, credits):  # pylint: disable=redefined-builtin
        """Credits to integer half-credits, refusing anything off the grid."""
        doubled = credits * 2
        self.assertAlmostEqual(
            doubled,
            round(doubled),
            places=6,
            msg=f"{credits} is not a whole number of half-credits - the offer has left the scheme this suite can verify",
        )
        return round(doubled)

    # ------------------------------------------------------------------
    # The run
    # ------------------------------------------------------------------
    def test_a_term_of_service_leaves_the_books_balanced(self):
        # A seeded PRNG is the point here: this draws a plausible sequence of
        # tickets, not a secret.
        rng = random.Random(SEED)  # noqa: S311
        shadows = {student.id: MealShadow() for student in self.students}
        # What the restaurant actually handed over, and what the student centre
        # actually took in. Both in DA, both counted here and nowhere else.
        meals_served_da = 0.0
        plans_sold_da = 0.0
        refusals = 0

        # Everyone starts somewhere different: a third of the population on the
        # small packs, a third on the large, a few with no plan at all (they
        # are the ones who must never be served), and a few with two packs at
        # once (they are the ones whose meals get split across subscriptions).
        for index, student in enumerate(self.students):
            if index % 10 == 0:
                continue  # no plan, no credits, no meals
            plan = self.plans[index % len(self.plans)]
            self.assertTrue(self._ring_up(student, [(plan, 1, plan.list_price)]))
            shadows[student.id].grant(self._halves(plan.meal_credits))
            plans_sold_da += plan.list_price
            if index % 7 == 0:
                second = self.plans[(index + 3) % len(self.plans)]
                self.assertTrue(self._ring_up(student, [(second, 1, second.list_price)]))
                shadows[student.id].grant(self._halves(second.meal_credits))
                plans_sold_da += second.list_price

        # Now the term. Six hundred tickets, drawn the way a restaurant draws
        # them: mostly one meal for one student, sometimes two on a tray,
        # sometimes a walk-in paying cash, and now and then someone buying
        # another pack halfway through.
        for _ticket in range(600):
            student = rng.choice(self.students)
            shadow = shadows[student.id]
            roll = rng.random()

            if roll < 0.08:
                plan = rng.choice(self.plans)
                self.assertTrue(self._ring_up(student, [(plan, 1, plan.list_price)]))
                shadow.grant(self._halves(plan.meal_credits))
                plans_sold_da += plan.list_price
                continue

            if roll < 0.16:
                # A paying customer buying the very same dish. Nothing about
                # this may touch anybody's credits.
                meal = rng.choice([self.meal_300, self.meal_600])
                self.assertTrue(self._ring_up(student, [(meal, 1, meal.list_price)]))
                continue

            meal = self.meal_300 if rng.random() < 0.6 else self.meal_600
            qty = 1 if rng.random() < 0.85 else 2
            cost = self._halves(meal.meal_credit_cost)

            # The shadow decides first, on its own arithmetic, and the till is
            # then held to that answer - both for serving and for refusing. A
            # ticket the shadow cannot serve in full is rolled back in full,
            # because that is what a raised UserError does to the real one:
            # there is no such thing as a half-served tray.
            before = shadow.snapshot()
            expected = all([shadow.consume(cost, overdraft=True) for _meal in range(qty)])
            if not expected:
                shadow.restore(before)

            served = self._ring_up(student, [(meal, qty, 0.0)])
            self.assertEqual(
                served,
                expected,
                f"the till and the shadow disagree about serving {qty}x{meal.display_name} to {student.display_name}",
            )
            if served:
                meals_served_da += qty * meal.list_price
            else:
                refusals += 1

        self.assertGreater(refusals, 0, "a term where nobody was ever refused has not tested the refusal")

        # --- 1. Every student's balance, against an independent count -------
        for student in self.students:
            shadow = shadows[student.id]
            self.assertEqual(
                float_compare(student.meal_credits_remaining, shadow.balance / 2.0, 2),
                0,
                f"{student.display_name}: till says {student.meal_credits_remaining}, shadow says {shadow.balance / 2.0}",
            )
            # Someone who never bought a plan is shown no allowance at all,
            # rather than two meals they would be refused at the counter.
            self.assertEqual(
                student.meal_allowance_left,
                max(0, 2 - shadow.allowance_used) if shadow.ever_bought_a_plan else 0,
                f"{student.display_name}: allowance disagrees",
            )
            self.assertEqual(
                float_compare(student.meal_allowance_debt, shadow.debt / 2.0, 2),
                0,
                f"{student.display_name}: debt disagrees",
            )

        # --- 2. The ledger against the subscriptions ------------------------
        # Exact identity, whatever the sequence was: every credit granted made
        # a subscription, every credit eaten raised a `credits_used`, and an
        # allowance meal is the one line with nothing behind it.
        for student in self.students:
            lines = self.env["his.meal.transaction"].search([("partner_id", "=", student.id)])
            subs = self.env["his.meal.subscription"].search([("partner_id", "=", student.id)])
            allowance = -sum(lines.filtered(lambda line: line.type == "allowance").mapped("credits"))
            self.assertEqual(
                float_compare(sum(lines.mapped("credits")), sum(subs.mapped("credits_remaining")) - allowance, 2),
                0,
                f"{student.display_name}: the ledger and the subscriptions tell different stories",
            )

        # --- 3. No subscription outside its own bounds ----------------------
        for sub in self.env["his.meal.subscription"].search([("partner_id", "in", [s.id for s in self.students])]):
            self.assertGreaterEqual(sub.credits_used, 0, f"{sub.display_name} has eaten a negative amount")
            self.assertLessEqual(
                sub.credits_used, sub.credits_total, f"{sub.display_name} has eaten more than it holds"
            )
            self.assertEqual(
                float_compare(sub.credits_remaining, sub.credits_total - sub.credits_used, 2),
                0,
                f"{sub.display_name}: remaining is not total minus used",
            )

        # --- 4. Nothing was created for someone who never bought ------------
        # The population starts one student in ten with no plan at all; some of
        # them buy one during the term, and the rest must end it holding
        # nothing - no subscription, and no meal charged to a card they never
        # had. This is the check that catches a credit appearing from nowhere.
        never_bought = [s for s in self.students if not shadows[s.id].ever_bought_a_plan]
        self.assertTrue(never_bought, "the population no longer contains anyone without a plan")
        for student in never_bought:
            self.assertFalse(
                self.env["his.meal.subscription"].search([("partner_id", "=", student.id)]),
                f"{student.display_name} never bought anything and holds a subscription",
            )
            self.assertFalse(
                self.env["his.meal.transaction"].search(
                    [("partner_id", "=", student.id), ("type", "in", ("consume", "allowance"))]
                ),
                f"{student.display_name} never bought anything and was served anyway",
            )

        # --- 5. The money ---------------------------------------------------
        # The restaurant handed out `meals_served_da` worth of food. The
        # student centre took in `plans_sold_da`. The gap between them has to
        # be exactly what is still on the cards plus what the allowance let
        # out - not a rupee more, because a rupee more is a meal nobody paid
        # for.
        granted = sum(shadow.granted for shadow in shadows.values()) / 2.0
        eaten = sum(shadow.eaten for shadow in shadows.values()) / 2.0
        outstanding = sum(shadow.balance for shadow in shadows.values()) / 2.0
        on_allowance = sum(shadow.debt for shadow in shadows.values()) / 2.0

        db_granted = sum(
            self.env["his.meal.subscription"]
            .search([("partner_id", "in", [s.id for s in self.students])])
            .mapped("credits_total")
        )
        self.assertEqual(float_compare(db_granted, granted, 2), 0, "credits sold do not match credits recorded")
        self.assertEqual(
            float_compare(granted, eaten + outstanding, 2),
            0,
            "credits granted do not equal credits eaten plus credits left",
        )
        self.assertEqual(
            float_compare(meals_served_da, (eaten + on_allowance) * DA_PER_CREDIT, 2),
            0,
            "the food that left the kitchen is not what the credits paid for",
        )
        # And the worst case, stated in money so it can be argued about: what
        # the allowance has let out and not yet been repaid.
        self.assertLessEqual(
            on_allowance * DA_PER_CREDIT,
            len(self.students) * 2 * DA_PER_CREDIT,
            "the allowance has let out more than two meals a head",
        )

    def test_the_ledger_never_reports_a_negative_balance(self):
        """`balance_after` is what a cashier reads back. It cannot be a lie."""
        student = self.students[1]
        plan = self.plans[0]
        self._ring_up(student, [(plan, 1, plan.list_price)])
        for _meal in range(10):
            self._ring_up(student, [(self.meal_600, 1, 0.0)])

        lines = self.env["his.meal.transaction"].search([("partner_id", "=", student.id)], order="id asc")
        self.assertTrue(lines)
        for line in lines:
            self.assertGreaterEqual(line.balance_after, 0.0, "a ledger line claims a negative balance")
        self.assertEqual(
            float_compare(lines[-1].balance_after, student.meal_credits_remaining, 2),
            0,
            "the last ledger line disagrees with the balance the till shows",
        )


@tagged("post_install", "-at_install")
class TestWaysToEatForFree(AccountTestInvoicingCommon):
    """Somebody at the till, trying it on. What does the server do?

    Every test here is written from the attempt, not from the rule, because
    the rules were already tested next door and the attempts are what actually
    walks up to the counter.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref("point_of_sale.group_pos_manager") | cls.env.ref(
            "his_meal_management.group_meal_officer"
        )
        cls.student = make_person(cls.env, "Sofiane").partner_id
        cls.other = make_person(cls.env, "Nadia").partner_id
        cls.walkin = cls.env["res.partner"].create({"name": "Passant"})
        cls.plan = cls.env.ref("his_meal_management.product_plan_weekly").product_variant_id
        cls.meal_300 = cls.env.ref("his_meal_management.product_meal_300").product_variant_id
        cls.meal_600 = cls.env.ref("his_meal_management.product_daily_meal").product_variant_id
        cls.config = cls.env["pos.config"].create({"name": "Adversary Restaurant"})
        cls.config.open_ui()
        cls.session = cls.config.current_session_id

    def _order(self, lines, partner=None, state=None):
        """`lines` is a list of (product, qty, price_unit[, discount %])."""
        commands = []
        total = 0.0
        for product, qty, price, *rest in lines:
            discount = rest[0] if rest else 0.0
            subtotal = qty * price * (1 - discount / 100.0)
            total += subtotal
            commands.append(
                Command.create(
                    {
                        "product_id": product.id,
                        "qty": qty,
                        "price_unit": price,
                        "discount": discount,
                        "price_subtotal": subtotal,
                        "price_subtotal_incl": subtotal,
                    }
                )
            )
        vals = {
            "company_id": self.env.company.id,
            "session_id": self.session.id,
            "partner_id": partner.id if partner else False,
            "amount_tax": 0.0,
            "amount_total": total,
            "amount_paid": total,
            "amount_return": 0.0,
            "lines": commands,
        }
        if state:
            vals["state"] = state
        return self.env["pos.order"].create(vals)

    def _fund(self, partner=None):
        return (partner or self.student).sudo()._grant_meal_credits(self.plan)

    def _ledger(self, partner=None):
        return self.env["his.meal.transaction"].search([("partner_id", "=", (partner or self.student).id)])

    def _meals_charged(self, partner=None):
        """Only the lines that took something off a card.

        `_fund` writes a purchase line, so "the ledger is empty" is never the
        right question here - "nothing was charged" is.
        """
        return self._ledger(partner).filtered(lambda line: line.type in ("consume", "allowance"))

    # --- the till's own buttons -----------------------------------------
    def test_a_cashier_discounting_a_meal_to_zero_still_spends_a_credit(self):
        """The one that paid for this suite.

        The hook used to read `price_unit`, which a 100% discount does not
        touch: the student paid nothing, ate, and the meal ledger never heard
        about it. No developer console needed - the discount button is on every
        till, and the only trace was a discounted POS line nobody reconciles
        against meal credits. A meal that costs the student nothing is a
        student meal, however the till got it to zero.
        """
        self._fund()
        order = self._order([(self.meal_600, 1, 600.0, 100.0)], partner=self.student)
        order._apply_meal_credits()

        self.assertEqual(order.amount_total, 0.0, "the student paid nothing")
        self.assertEqual(
            self.student.meal_credits_remaining,
            5.0,
            "SECURITY: a 100% discount served a meal without spending a credit",
        )
        self.assertEqual(len(self._meals_charged()), 1, "SECURITY: the free meal left no trace in the meal ledger")

    def test_a_half_price_meal_is_still_a_sale(self):
        """The fix must not swallow ordinary discounts: 50% off is a sale."""
        self._fund()
        self._order([(self.meal_600, 1, 600.0, 50.0)], partner=self.student)._apply_meal_credits()
        self.assertEqual(self.student.meal_credits_remaining, 6.0)
        self.assertFalse(self._meals_charged())

    def test_a_discounted_meal_with_no_student_is_refused_like_any_free_one(self):
        """Closing the hole must not open a quiet way round the card scan."""
        order = self._order([(self.meal_600, 1, 600.0, 100.0)])
        with self.assertRaises(UserError), self.env.cr.savepoint():
            order._apply_meal_credits()

    def test_a_meal_priced_at_a_fraction_of_a_dinar_is_treated_as_free(self):
        """Below the currency's rounding, `float_is_zero` says zero - correctly.

        Worth pinning: it means a cashier cannot dodge the credit by typing
        0.001 instead of 0. The credit is taken.
        """
        self._fund()
        order = self._order([(self.meal_600, 1, 0.004)], partner=self.student)
        order._apply_meal_credits()
        self.assertEqual(self.student.meal_credits_remaining, 5.0, "a near-zero price must still spend the credit")

    def test_a_meal_at_one_dinar_is_a_sale_and_not_a_credit(self):
        """And just above the rounding, it is a paying customer again.

        The pair of tests is the boundary: there is no price at which a student
        both pays nothing and keeps the credit, except the discount hole above.
        """
        self._fund()
        order = self._order([(self.meal_600, 1, 1.0)], partner=self.student)
        order._apply_meal_credits()
        self.assertEqual(self.student.meal_credits_remaining, 6.0)
        self.assertFalse(self._meals_charged())

    def test_a_negative_price_does_not_refund_a_credit(self):
        self._fund()
        order = self._order([(self.meal_600, 1, -600.0)], partner=self.student)
        order._apply_meal_credits()
        self.assertEqual(self.student.meal_credits_remaining, 6.0)
        self.assertFalse(self._meals_charged())

    # --- quantity and refunds -------------------------------------------
    def test_a_ticket_for_more_meals_than_the_card_holds_serves_none_of_them(self):
        """Partial service is the dangerous outcome: food out, credits short."""
        self._fund()  # 6 credits
        order = self._order([(self.meal_600, 9, 0.0)], partner=self.student)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            order._apply_meal_credits()
        self.assertEqual(self.student.meal_credits_remaining, 6.0, "credits were spent on a ticket that was refused")
        self.assertFalse(self._meals_charged(), "a refused ticket wrote to the ledger")

    def test_refunding_a_plan_does_not_take_the_credits_back(self):
        """Pinned, not endorsed: this is the module's documented no-op.

        A negative quantity produces an empty range, so the money goes back over
        the counter and the credits stay on the card. An officer is supposed to
        settle it with the correction wizard. The test exists so that the day
        somebody changes it, they change it on purpose.
        """
        self._fund()
        order = self._order([(self.plan, -1, 3000.0)], partner=self.student)
        order._apply_meal_credits()
        self.assertEqual(
            self.student.meal_credits_remaining,
            6.0,
            "refunding a plan now moves credits - decide whether that is what you want",
        )

    def test_refunding_a_meal_does_not_give_a_credit_back(self):
        self._fund()
        self._order([(self.meal_600, 1, 0.0)], partner=self.student)._apply_meal_credits()
        self.assertEqual(self.student.meal_credits_remaining, 5.0)
        refund = self._order([(self.meal_600, -1, 0.0)], partner=self.student)
        refund._apply_meal_credits()
        self.assertEqual(self.student.meal_credits_remaining, 5.0, "a refunded meal handed a credit back")

    # --- who the credits belong to ---------------------------------------
    def test_a_meal_cannot_be_charged_to_somebody_else(self):
        """The order's partner is the only account it can touch."""
        self._fund(self.other)
        order = self._order([(self.meal_600, 1, 0.0)], partner=self.student)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            order._apply_meal_credits()
        self.assertEqual(self.other.meal_credits_remaining, 6.0, "somebody else's card was charged")

    def test_a_walk_in_contact_cannot_be_given_a_balance(self):
        """No `his.person`, no wallet - the gate that keeps the referential in."""
        order = self._order([(self.plan, 1, 3000.0)], partner=self.walkin)
        with self.assertRaises(Exception), self.env.cr.savepoint():
            order._apply_meal_credits()
        self.assertFalse(
            self.env["his.meal.subscription"].search([("partner_id", "=", self.walkin.id)]),
            "a contact outside the referential now holds meal credits",
        )

    def test_an_anonymous_meal_is_refused_outright(self):
        order = self._order([(self.meal_600, 1, 0.0)])
        with self.assertRaises(UserError), self.env.cr.savepoint():
            order._apply_meal_credits()

    # --- replaying and re-syncing ----------------------------------------
    def test_replaying_the_same_order_twenty_times_charges_once(self):
        self._fund()
        order = self._order([(self.meal_600, 1, 0.0)], partner=self.student)
        for _replay in range(20):
            order._apply_meal_credits()
        self.assertEqual(self.student.meal_credits_remaining, 5.0)
        self.assertEqual(len(self._meals_charged()), 1)

    def test_two_orders_for_the_same_meal_are_two_charges(self):
        """The mirror of the test above: idempotency is per order, not per meal."""
        self._fund()
        self._order([(self.meal_600, 1, 0.0)], partner=self.student)._apply_meal_credits()
        self._order([(self.meal_600, 1, 0.0)], partner=self.student)._apply_meal_credits()
        self.assertEqual(self.student.meal_credits_remaining, 4.0)

    def test_a_cancelled_order_moves_nothing(self):
        self._fund()
        order = self._order([(self.meal_600, 1, 0.0)], partner=self.student, state="cancel")
        order._process_saved_order(draft=False)
        self.assertEqual(self.student.meal_credits_remaining, 6.0)
        self.assertFalse(self._meals_charged())

    def test_an_order_still_in_draft_moves_nothing(self):
        self._fund()
        order = self._order([(self.meal_600, 1, 0.0)], partner=self.student)
        order._process_saved_order(draft=True)
        self.assertEqual(self.student.meal_credits_remaining, 6.0)
        self.assertFalse(self._meals_charged())

    # --- the allowance ----------------------------------------------------
    def test_the_allowance_cannot_be_stretched_by_putting_three_on_one_ticket(self):
        self._fund()
        self.student.sudo()._consume_meal_credit(amount=6.0)
        order = self._order([(self.meal_600, 3, 0.0)], partner=self.student)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            order._apply_meal_credits()
        self.assertEqual(
            len(self._meals_charged().filtered(lambda line: line.type == "allowance")),
            0,
            "a three-meal ticket on an empty card left allowance lines behind",
        )

    def test_the_allowance_cannot_be_rearmed_by_a_one_credit_top_up_loop(self):
        """The cycle resets on any top-up, so what does a tiny one cost?

        Buying the smallest thing that grants credits resets the allowance -
        by design, and it has to, because the debt is settled out of the
        top-up. What this pins is the price of the loop: each round costs the
        student a real plan, so the house is never out of pocket by more than
        the two meals of the current cycle.
        """
        self._fund()
        self.student.sudo()._consume_meal_credit(amount=6.0)
        for _meal in range(2):
            self._order([(self.meal_600, 1, 0.0)], partner=self.student)._apply_meal_credits()
        self.assertEqual(self.student.meal_allowance_debt, 2.0)

        # Another pack: the debt is paid out of it before anything else.
        self._order([(self.plan, 1, 3000.0)], partner=self.student)._apply_meal_credits()
        self.assertEqual(self.student.meal_credits_remaining, 4.0, "the debt was not taken off the new pack")
        self.assertEqual(self.student.meal_allowance_debt, 0.0)
        self.assertEqual(self.student.meal_allowance_left, 2)

    def test_somebody_who_only_ever_got_a_hand_correction_has_no_allowance(self):
        self.student.sudo()._add_meal_credits(credits=1.0, date_end=False, tx_type="adjust", note="geste")
        self.student.sudo()._consume_meal_credit(amount=1.0)
        order = self._order([(self.meal_600, 1, 0.0)], partner=self.student)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            order._apply_meal_credits()

    # --- going round the till --------------------------------------------
    def test_a_cashier_cannot_write_a_credit_onto_a_subscription(self):
        sub = self._fund()
        cashier = self.env["res.users"].create(
            {
                "name": "Caissier",
                "login": "caissier.meal.test",
                "group_ids": [Command.link(self.env.ref("his_meal_management.group_meal_cashier").id)],
            }
        )
        # The S-4 guard answers (UserError) before the ACL would (AccessError).
        with self.assertRaises(UserError), self.env.cr.savepoint():
            sub.with_user(cashier).write({"credits_total": 999.0})
        self.assertEqual(sub.credits_total, 6.0)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env["his.meal.subscription"].with_user(cashier).create(
                {
                    "partner_id": self.student.id,
                    "date_start": fields.Date.context_today(self.student),
                    "credits_total": 999.0,
                }
            )

    def test_nobody_at_all_may_create_a_subscription_by_hand(self):
        """Not even the officer: credits arrive through the guarded path only."""
        officer = self.env["res.users"].create(
            {
                "name": "Officier",
                "login": "officier.meal.test",
                "group_ids": [Command.link(self.env.ref("his_meal_management.group_meal_officer").id)],
            }
        )
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env["his.meal.subscription"].with_user(officer).create(
                {
                    "partner_id": self.student.id,
                    "date_start": fields.Date.context_today(self.student),
                    "credits_total": 50.0,
                }
            )

    def test_the_ledger_cannot_be_rewritten_to_hide_a_meal(self):
        self._fund()
        self._order([(self.meal_600, 1, 0.0)], partner=self.student)._apply_meal_credits()
        line = self._meals_charged().filtered(lambda tx: tx.type == "consume")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            line.write({"credits": 0.0})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            line.unlink()

    def test_a_correction_cannot_push_a_card_negative(self):
        self._fund()
        wizard = self.env["his.meal.adjust.wizard"].create(
            {"partner_id": self.student.id, "credits": -99.0, "reason": "erreur"}
        )
        with self.assertRaises(UserError), self.env.cr.savepoint():
            wizard.action_apply()
        self.assertEqual(self.student.meal_credits_remaining, 6.0)

    def test_an_expired_pack_is_not_eaten_the_allowance_is(self):
        """An expired pack is untouchable, and the student still gets fed.

        Worth knowing before it happens at the counter: the meal is not refused,
        it comes out of the two-meal allowance, and the ledger says so. The
        expired credits stay exactly where they are - which is the part that
        must never change, because they have been paid for and written off.
        """
        sub = self._fund()
        today = fields.Date.context_today(self.student)
        sub.sudo().write({"date_start": today - timedelta(days=40), "date_end": today - timedelta(days=1)})

        self._order([(self.meal_600, 1, 0.0)], partner=self.student)._apply_meal_credits()

        self.assertEqual(sub.credits_remaining, 6.0, "an expired pack was eaten")
        self.assertEqual(self.student.meal_credits_remaining, 0.0)
        charged = self._meals_charged()
        self.assertEqual(len(charged), 1)
        self.assertEqual(charged.type, "allowance", "an expired pack should feed through the allowance, not the pack")

        # And when the allowance runs out, the expired pack is still no help.
        self._order([(self.meal_600, 1, 0.0)], partner=self.student)._apply_meal_credits()
        order = self._order([(self.meal_600, 1, 0.0)], partner=self.student)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            order._apply_meal_credits()
        self.assertEqual(sub.credits_remaining, 6.0, "an expired pack was eaten once the allowance ran out")


@tagged("post_install", "-at_install")
class TestWhatTheTillReallySends(AccountTestInvoicingCommon):
    """Through `sync_from_ui`, the way the browser actually gets there.

    Everything else in both files calls `_apply_meal_credits` directly, which
    proves the rule and not the wiring. These go in through the front door with
    a payment attached, so a hook that stopped being called would fail here and
    nowhere else.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref("point_of_sale.group_pos_manager") | cls.env.ref(
            "his_meal_management.group_meal_officer"
        )
        cls.student = make_person(cls.env, "Lamia").partner_id
        cls.plan = cls.env.ref("his_meal_management.product_plan_weekly").product_variant_id
        cls.meal_600 = cls.env.ref("his_meal_management.product_daily_meal").product_variant_id
        cls.cash = cls.env["pos.payment.method"].create(
            {
                "name": "Especes",
                "receivable_account_id": cls.company_data["default_account_receivable"].id,
                "journal_id": cls.company_data["default_journal_cash"].id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Front Door Restaurant",
                "payment_method_ids": [Command.set(cls.cash.ids)],
                "invoice_journal_id": cls.company_data["default_journal_sale"].id,
            }
        )
        cls.config.open_ui()
        cls.session = cls.config.current_session_id

    def _payload(self, product, qty, price_unit, uuid):
        total = qty * price_unit
        return {
            "company_id": self.env.company.id,
            "session_id": self.session.id,
            "partner_id": self.student.id,
            "uuid": uuid,
            "lines": [
                [
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "qty": qty,
                        "price_unit": price_unit,
                        "tax_ids": [[6, False, []]],
                        "price_subtotal": total,
                        "price_subtotal_incl": total,
                    },
                ]
            ],
            "payment_ids": [
                [0, 0, {"amount": total, "name": fields.Datetime.now(), "payment_method_id": self.cash.id}]
            ],
            "amount_paid": total,
            "amount_total": total,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "last_order_preparation_change": "{}",
        }

    def test_the_browser_selling_a_pack_really_lands_the_credits(self):
        self.env["pos.order"].sync_from_ui([self._payload(self.plan, 1, self.plan.list_price, "pack-0001")])
        self.assertEqual(self.student.meal_credits_remaining, 6.0)

    def test_the_browser_serving_a_meal_really_spends_a_credit(self):
        self.env["pos.order"].sync_from_ui([self._payload(self.plan, 1, self.plan.list_price, "pack-0002")])
        self.env["pos.order"].sync_from_ui([self._payload(self.meal_600, 1, 0.0, "repas-0002")])
        self.assertEqual(self.student.meal_credits_remaining, 5.0)
        line = self.env["his.meal.transaction"].search([("partner_id", "=", self.student.id), ("type", "=", "consume")])
        self.assertEqual(len(line), 1)
        self.assertEqual(line.credits, -1.0)
        self.assertTrue(line.pos_order_id, "the ledger line does not name the order it came from")
        self.assertEqual(line.session_id, self.session, "the ledger line does not name the session")

    def test_the_same_ticket_sent_twice_by_a_flaky_connection_charges_once(self):
        """The one that matters on a campus wifi: the till retries a sync."""
        self.env["pos.order"].sync_from_ui([self._payload(self.plan, 1, self.plan.list_price, "pack-0003")])
        payload = self._payload(self.meal_600, 1, 0.0, "repas-0003")
        self.env["pos.order"].sync_from_ui([payload])
        self.env["pos.order"].sync_from_ui([payload])
        self.assertEqual(self.student.meal_credits_remaining, 5.0, "a retried sync charged the card twice")
        self.assertEqual(
            len(
                self.env["his.meal.transaction"].search(
                    [("partner_id", "=", self.student.id), ("type", "=", "consume")]
                )
            ),
            1,
        )


@tagged("post_install", "-at_install")
class TestTheOfferAddsUp(TransactionCase):
    """The price sheet, checked as arithmetic rather than as a list.

    A pack whose credits stop matching its price is not a bug the server can
    catch: it just quietly sells food below cost.
    """

    def test_every_pack_costs_between_450_and_500_da_a_meal(self):
        for name in (
            "product_plan_300_weekly",
            "product_plan_300_monthly",
            "product_plan_300_semester",
            "product_plan_weekly",
            "product_plan_monthly",
            "product_plan_semester",
        ):
            plan = self.env.ref(f"his_meal_management.{name}")
            da_per_credit = plan.list_price / plan.meal_credits
            self.assertGreaterEqual(
                da_per_credit,
                450.0,
                f"{plan.name} sells a credit for {da_per_credit} DA - below the floor of the price sheet",
            )
            self.assertLessEqual(
                da_per_credit,
                DA_PER_CREDIT,
                f"{plan.name} sells a credit above the price of the meal it buys",
            )

    def test_both_meals_cost_what_their_price_says(self):
        meal_300 = self.env.ref("his_meal_management.product_meal_300")
        meal_600 = self.env.ref("his_meal_management.product_daily_meal")
        self.assertEqual(meal_300.list_price / meal_300.meal_credit_cost, DA_PER_CREDIT)
        self.assertEqual(meal_600.list_price / meal_600.meal_credit_cost, DA_PER_CREDIT)

    def test_no_product_grants_and_costs_credits_at_once(self):
        both = self.env["product.template"].search([("meal_credits", ">", 0), ("meal_credit_cost", ">", 0)])
        self.assertFalse(both, f"{both.mapped('name')} would grant and spend credits in the same sale")
