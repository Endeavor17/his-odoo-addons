"""Issue a card for every badge his_person_core recorded before this handover.

Until now `his.person.numero_carte` was a plain stored Char owned by
his_person_core: a badge number with no lifecycle, which its own README said had
to move into a dedicated model before the meal wallet stored money. This version
takes it over - the field is now computed from the person's active
`his.meal.card`.

That is precisely why this script exists, and why its order is not negotiable.
A person imported with a badge but no card row would, the moment the computed
field first runs, have that badge blanked: the compute reads the cards, and
there are none. So the cards are created FIRST, from the values already in the
column, and only then is the field allowed to recompute over them - landing on
the same number it started with.

Nothing to do on a database where the wallet always owned the badge: every card
holder already has a row, and the loop below finds nobody.
"""
import logging

_logger = logging.getLogger(__name__)


def _backfill_badges_from_cards(env):
    """Fill the badge of everyone who already holds a card.

    Odoo initialises a stored field when its COLUMN appears. Here the column
    was already there - his_person_core created it as a plain Char - so turning
    the field into a computed one leaves every existing row untouched, and the
    badge of every current card holder reads empty until something writes it.
    Nothing in normal operation would: the compute only runs when a card
    changes, and these cards are not changing.

    So the recomputation is asked for explicitly. This is the case that
    actually occurs on the group's database, where the wallet owned the badge
    long before the identity module had a field for it.
    """
    # active_test=False: an archived person still holds a card, and their badge
    # still has to agree with it. Skipping them would leave a row whose card
    # says one number and whose badge says nothing - and the day someone is
    # unarchived, the till and the attendance reader would disagree about them.
    People = env['his.person'].sudo().with_context(active_test=False)
    stale = People.search([('partner_id.meal_card_ids.state', '=', 'active')])
    if not stale:
        return 0
    env.add_to_compute(People._fields['numero_carte'], stale)
    env.flush_all()
    return len(stale)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    # Read the raw column rather than the ORM: at this point the field is
    # computed, so browsing a person would return what the cards say - which is
    # exactly the value being reconstructed here.
    cr.execute("""
        SELECT p.id, p.partner_id, p.numero_carte
          FROM his_person p
         WHERE p.numero_carte IS NOT NULL
           AND p.numero_carte <> ''
           AND NOT EXISTS (
                SELECT 1 FROM his_meal_card c
                 WHERE c.partner_id = p.partner_id
                   AND c.state = 'active'
           )
      ORDER BY p.id
    """)
    rows = cr.fetchall()
    env = api.Environment(cr, SUPERUSER_ID, {})
    Card = env['his.meal.card'].sudo()
    created = 0
    for person_id, partner_id, numero in rows:
        # A number already held by someone else cannot be issued twice - the
        # card's unique(code) would refuse it, and rightly: the till would not
        # know whom to debit. Leave it, log it, let a human arbitrate.
        if Card.search_count([('code', '=', numero)]):
            _logger.warning(
                "Badge %s (person %s) is already carried by another card - "
                "no card issued, to be settled by hand.", numero, person_id,
            )
            continue
        Card.create({'partner_id': partner_id, 'code': numero})
        created += 1

    if not rows:
        _logger.info("No orphan badge to convert: every badge already has a card.")
    else:
        _logger.info("Cards issued from badges recorded before the handover: %d.", created)

    # The other direction, and the one that happens here: cards that predate
    # the field. Runs last, so any card just issued above is included.
    backfilled = _backfill_badges_from_cards(env)
    _logger.info("Badges backfilled from existing cards: %d.", backfilled)
