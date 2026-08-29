{
    'name': 'HIS Web Interface',
    'version': '19.0.1.0.0',
    'summary': 'Land on the app grid, not on whichever menu happens to sort first',
    'description': """
HIS Web Interface
=================
Landing is a decision, not a sort order.

Odoo Community ships no landing page: with no Home Action it opens the first
root menu the user can see, ordered by sequence. That is how a director with no
business in the CRM ended up on the Direction dashboard every morning, and how
everyone else ended up in Discuss.

* The app grid comes from OCA's web_responsive (vendored at the root of this
  repository, see its VENDOR.md). This module does not re-implement it.
* web_responsive states only half the rule — it clears its redirect flag for
  anyone holding a Home Action and never sets it. Here the grid is the default,
  so the other half is stated explicitly.
* A Home Action always wins over the grid. That is deliberate and upstream's
  design: someone who should open one screen every day still can.
* The install clears exactly one Home Action, the Direction dashboard, because
  it outlived the group that granted it. No other choice is touched.
""",
    'author': 'Abdo Chabouti',
    'category': 'Technical',
    'license': 'LGPL-3',

    'depends': ['web_responsive'],

    'post_init_hook': 'post_init_hook',

    'installable': True,
}
