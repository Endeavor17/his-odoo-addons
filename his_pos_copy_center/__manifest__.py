{
    'name': 'HIS POS Copy Center',
    'version': '19.0.1.0.0',
    'summary': 'One dialog to compose a copy job, instead of one popup per dimension',
    'description': """
HIS POS Copy Center
===================
A copy is priced by its dimensions — copies, format, colour, sides — and stock
POS makes the cashier answer one popup per dimension, for every document in a
job.

* The dimensions are plain fields on the product, not attributes. his_stock_mdm
  forbids the Format attribute on the copy categories (MDM rule 6) and enforces
  it with a ValidationError; its own error text prescribes the alternative, a
  distinct product per physical variation. This module labels those products so
  a till can find one by description instead of by name.
* The builder resolves one product and adds one ordinary order line. It reads a
  price; it never computes one. The figure the cashier reads and the figure the
  server charges are the same number.
* A job of five documents is five ordinary order lines. There is no job model.
* A product carrying no copy_service is invisible to the builder and behaves
  exactly as it does today.
""",
    'author': 'Abdo Chabouti',
    'category': 'Sales/Point of Sale',
    'license': 'LGPL-3',

    'depends': ['his_pos_ui'],

    'data': [
        'views/product_template_views.xml',
    ],

    'demo': [
        'demo/copy_products.xml',
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            'his_pos_copy_center/static/src/app/*.scss',
            'his_pos_copy_center/static/src/app/*.js',
            'his_pos_copy_center/static/src/app/*.xml',
        ],
        'web.assets_tests': [
            'his_pos_copy_center/static/tests/tours/**/*',
        ],
    },

    'installable': True,
}
