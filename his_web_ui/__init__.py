import logging

from . import models

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Land every existing user on the app grid, and undo the one Home Action
    that was sending a director somewhere he could not read.

    Two separate faults produced the same symptom, and both are settled here:

      - `menu_direction_root` carried sequence="2". With no Home Action, Odoo
        Community opens the first root menu the user can see, ordered by
        sequence, so the Direction dashboard outranked every other app and
        caught everyone holding the group. That half is fixed in the menu
        itself, not here.
      - a Home Action pointing at that dashboard survives the removal of the
        group that grants it, because hiding a menu removes the link and not
        the action. The user then lands on a screen whose data they cannot
        read, and — since web_responsive clears the redirect flag whenever a
        Home Action is set — never reaches the app grid either.

    Only that one action is cleared. Wiping every Home Action would silently
    discard deliberate choices made for other people.

    Install-time only, so a later upgrade never overrides what someone has
    since chosen for themselves.
    """
    direction = env.ref(
        'his_crm_pipeline.action_dashboard_direction', raise_if_not_found=False)

    if direction:
        # action_id points at ir.actions.actions; every action subtype shares
        # that id space, so a client action compares directly.
        stranded = env['res.users'].search([('action_id', '=', direction.id)])
        if stranded:
            _logger.info(
                "his_web_ui: clearing the Direction home action for %s.",
                ", ".join(stranded.mapped('login')),
            )
            # Clearing action_id re-fires _compute_redirect_home, which now
            # sets the flag — these users need no second write.
            stranded.action_id = False

    # Everyone else who has no Home Action at all: the compute only runs when
    # action_id changes, so existing rows still hold the stored False.
    grounded = env['res.users'].search([
        ('action_id', '=', False),
        ('is_redirect_home', '=', False),
        ('share', '=', False),
    ])
    if grounded:
        grounded.is_redirect_home = True
        _logger.info(
            "his_web_ui: %s internal user(s) now land on the app grid.",
            len(grounded),
        )
