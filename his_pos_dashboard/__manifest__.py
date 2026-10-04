{
    "name": "HIS POS Dashboard",
    "version": "19.0.1.0.0",
    "summary": "Metabase dashboard opened from the point of sale menu",
    "description": """
HIS POS Dashboard
=================
A "Dashboard" item in the till's menu opens a Metabase dashboard full screen.

* The embed URL is signed on the server with the Metabase key, read from a
  system parameter. The key never reaches the browser and is never committed:
  this repository is public.
* One dashboard for every till, set in three system parameters. Until all
  three are set the menu stays stock, so installing the module changes nothing.
* No stored field: a deploy that forgets `-u` cannot break a till.

Kept out of his_pos_ui on purpose: that module promises CSS only and no server
call, and this one exists to make a server call.
""",
    "author": "Abdo Chabouti",
    "category": "Sales/Point of Sale",
    "license": "LGPL-3",
    "depends": ["point_of_sale"],
    "assets": {
        "point_of_sale._assets_pos": [
            "his_pos_dashboard/static/src/app/*.js",
            "his_pos_dashboard/static/src/app/*.xml",
        ],
    },
    "installable": True,
}
