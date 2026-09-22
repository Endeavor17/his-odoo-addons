"""Two tills, one card, one credit, at the same instant.

The test suite cannot ask this question: everything inside a `TransactionCase`
shares one transaction, and a lock only means something between two of them.
So this runs outside the suite, against a real database, over two genuine
connections that both commit.

    docker exec <odoo> odoo shell -c /etc/odoo/odoo.conf -d <db> --no-http \
        < tools/meal_race_check.py

What it does: registers a student, puts exactly one credit on a card that carries
no allowance, then has two threads serve a 600 DA meal simultaneously through the
real server hook. Exactly one must eat.

It writes to the database and cleans up after itself. Point it at a throwaway
copy, never at production.
"""

import logging
import os
import sys
import threading

from odoo.api import SUPERUSER_ID, Environment
from odoo.exceptions import UserError
from odoo.modules.registry import Registry

_logger = logging.getLogger("meal_race")
logging.getLogger().setLevel(logging.WARNING)

DB = env.cr.dbname
RESULTS = {}


def serve_a_meal(label, order_id, barrier):
    """One till, one connection, one meal - the real path, including commit.

    The order already exists and is committed. It has to: two `pos.order`
    creates at the same instant collide on Odoo's own order sequence, which is
    taken `FOR UPDATE NOWAIT`, and one of them dies there before ever reaching
    the credits. That collision is core Odoo's business (the browser retries
    the sync); what is being tested here is the next step, where two tills that
    both have a valid order try to spend the same credit.
    """

    def step(msg):
        print(f"    [{label}] {msg}", flush=True)

    registry = Registry(DB)
    with registry.cursor() as cr:
        thread_env = Environment(cr, SUPERUSER_ID, {})
        order = thread_env["pos.order"].browse(order_id)
        # Both tills arrive at the credit hook together. Without the barrier the
        # first one would be long finished before the second starts, and the
        # race would never happen.
        step("at the barrier")
        barrier.wait(timeout=30)
        step("applying credits")
        try:
            order._apply_meal_credits()
            cr.commit()
            RESULTS[label] = "served"
            step("served")
        except UserError as exc:
            cr.rollback()
            RESULTS[label] = f"refused: {exc}"
        except Exception as exc:
            cr.rollback()
            RESULTS[label] = f"{type(exc).__name__}: {exc}"


def main():
    # As the administrator, not as the superuser: Odoo 19 refuses to open a POS
    # session for uid 1 outside test mode, on purpose.
    shell_env = env
    admin = shell_env.ref("base.user_admin")
    admin.group_ids |= shell_env.ref("point_of_sale.group_pos_manager")
    env_ = shell_env(user=admin.id)

    person = (
        env_["his.person"]
        .sudo()
        .create({"name": "ZZ Race Test", "type_personne": "etudiant", "source_system": "manual"})
    )
    student = person.partner_id.sudo()
    meal = env_.ref("his_meal_management.product_daily_meal").product_variant_id

    config = env_["pos.config"].create({"name": "ZZ Race Till"})
    config.open_ui()
    session = config.current_session_id

    # Exactly one credit, and no allowance to fall back on - the credits come
    # from a hand correction, which deliberately does not buy the right to run
    # a card empty. Without that, the second till would be served legitimately
    # off the allowance and the lock would never be tested. Here the only thing
    # standing between it and a free meal is the lock.
    student._add_meal_credits(credits=1.0, date_end=False, tx_type="adjust", note="race fixture")
    if student.meal_credits_remaining != 1.0 or student.meal_allowance_left != 0:
        raise SystemExit(
            f"fixture is wrong: {student.meal_credits_remaining} credit(s), "
            f"{student.meal_allowance_left} allowance meal(s) left"
        )
    # Two tickets, one per till, created one after the other and committed:
    # the race is over the credit, not over Odoo's order sequence.
    orders = [
        env_["pos.order"].create(
            {
                "company_id": env_.company.id,
                "session_id": session.id,
                "partner_id": student.id,
                "amount_tax": 0.0,
                "amount_total": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": meal.id,
                            "qty": 1,
                            "price_unit": 0.0,
                            "price_subtotal": 0.0,
                            "price_subtotal_incl": 0.0,
                        },
                    )
                ],
            }
        )
        for _till in (1, 2)
    ]
    env_.cr.commit()  # the other connections have to be able to see it

    barrier = threading.Barrier(2)
    threads = [
        threading.Thread(
            target=serve_a_meal,
            daemon=True,
            args=(f"till-{n}", order.id, barrier),
        )
        for n, order in enumerate(orders, start=1)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    env_.invalidate_all()
    served = [label for label, outcome in RESULTS.items() if outcome == "served"]
    consumed = env_["his.meal.transaction"].search_count(
        [("partner_id", "=", student.id), ("type", "in", ("consume", "allowance")), ("pos_order_id", "!=", False)]
    )
    balance = student.meal_credits_remaining
    subs = env_["his.meal.subscription"].search([("partner_id", "=", student.id)])

    print("\n=== two tills, one card, one credit ===")
    for label, outcome in sorted(RESULTS.items()):
        print(f"  {label}: {outcome}")
    print(f"  meals actually charged : {consumed}")
    print(f"  balance afterwards     : {balance}")
    print(f"  any oversubscribed row : {any(s.credits_used > s.credits_total for s in subs)}")

    verdict = "PASS"
    if len(served) != 1:
        verdict = f"FAIL - {len(served)} till(s) served a meal off one credit"
    elif consumed != 1:
        verdict = f"FAIL - {consumed} meals charged"
    elif balance != 0.0:
        verdict = f"FAIL - balance is {balance}, expected 0"
    print(f"  VERDICT: {verdict}\n")

    # Clean up: the ledger refuses deletion by design, so the fixtures go in
    # the order that keeps the database consistent and the ledger untouched.
    env_.cr.execute("DELETE FROM his_meal_transaction WHERE partner_id = %s", [student.id])
    env_.cr.execute("DELETE FROM his_meal_subscription WHERE partner_id = %s", [student.id])
    env_.cr.execute(
        "DELETE FROM pos_order_line WHERE order_id IN (SELECT id FROM pos_order WHERE session_id = %s)", [session.id]
    )
    env_.cr.execute("DELETE FROM pos_order WHERE session_id = %s", [session.id])
    env_.cr.execute("DELETE FROM pos_session WHERE id = %s", [session.id])
    env_.cr.execute("DELETE FROM pos_config WHERE id = %s", [config.id])
    env_.cr.execute("DELETE FROM his_person WHERE id = %s", [person.id])
    env_.cr.execute("DELETE FROM res_partner WHERE id = %s", [student.id])
    env_.cr.commit()


main()

# The shell keeps the process alive on anything still hanging around; the work
# is done and committed by here, so leave on the spot.
sys.stdout.flush()
os._exit(0)
