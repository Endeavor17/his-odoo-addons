from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLanding(TransactionCase):
    """Where a user lands is a decision this module makes explicitly.

    The rule has two halves and upstream only writes one of them, so both are
    pinned here: no Home Action means the app grid, a Home Action means that
    action and never the grid.
    """

    def _user(self, login, **vals):
        return self.env['res.users'].create({
            'name': login, 'login': login, **vals,
        })

    def test_a_new_user_lands_on_the_app_grid(self):
        user = self._user('lands-on-grid')
        self.assertTrue(
            user.is_redirect_home,
            "A user with no home action must land on the app grid, which is "
            "the whole point of installing this module.",
        )

    def test_a_home_action_still_wins(self):
        """Upstream's rule, which this module must not have broken.

        Someone who opens one screen every day should keep landing on it.
        """
        action = self.env['ir.actions.act_window'].create({
            'name': "Somewhere deliberate",
            'res_model': 'res.partner',
        })
        user = self._user('lands-on-action', action_id=action.id)
        self.assertFalse(
            user.is_redirect_home,
            "A home action must override the app grid, or nobody can choose "
            "their own landing screen.",
        )

    def test_clearing_the_home_action_returns_the_user_to_the_grid(self):
        """The path the install hook takes for the stranded director.

        The hook clears action_id and writes nothing else, relying on this
        recompute. If that stopped working the hook would silently leave users
        with no landing at all.
        """
        action = self.env['ir.actions.act_window'].create({
            'name': "Temporary",
            'res_model': 'res.partner',
        })
        user = self._user('was-stranded', action_id=action.id)
        self.assertFalse(user.is_redirect_home)

        user.action_id = False
        self.assertTrue(
            user.is_redirect_home,
            "Clearing a home action must hand the user back to the app grid; "
            "the install hook depends on exactly this recompute.",
        )
