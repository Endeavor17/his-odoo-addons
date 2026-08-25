from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPosTheme(TransactionCase):
    """The theme is a label on the till, and nothing more.

    It must be optional, because an unthemed point of sale has to keep looking
    exactly like stock Odoo. That fallback is what makes a CSS-only theme safe
    to install on a running register: the worst case is that nothing changes.
    """

    def test_theme_is_optional(self):
        config = self.env['pos.config'].create({'name': "Untouched Till"})
        self.assertFalse(
            config.his_pos_theme,
            "A new point of sale must carry no theme, so it renders as stock Odoo.",
        )

    def test_theme_accepts_the_three_points_of_sale(self):
        config = self.env['pos.config'].create({'name': "Themed Till"})
        for theme in ('copy_center', 'restaurant', 'cafeteria'):
            config.his_pos_theme = theme
            self.assertEqual(config.his_pos_theme, theme)

    def test_theme_reaches_the_browser(self):
        """POS reads pos.config with an empty field list, which means *all* fields.

        This test pins that behaviour. If a future Odoo starts whitelisting
        pos.config fields, the theme silently stops arriving in the browser and
        every till quietly reverts to looking stock — a bug that presents as
        "the CSS is broken" and wastes a day. Better to fail here, naming the
        real cause, than to debug a stylesheet that was never given a class to
        hang on.
        """
        config = self.env['pos.config'].create({
            'name': "Loaded Till",
            'his_pos_theme': 'copy_center',
        })
        fields = self.env['pos.config']._load_pos_data_fields(config)
        loaded = config.read(fields, load=False)[0]
        self.assertEqual(loaded.get('his_pos_theme'), 'copy_center')
