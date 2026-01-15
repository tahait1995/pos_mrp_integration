# -*- coding: utf-8 -*-
{
    'name': 'POS MRP Integration',
    'version': '18.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Automatic Manufacturing Orders from Point of Sale',
    'description': """
POS MRP Integration
===================

This module integrates Point of Sale with Manufacturing (MRP) to automatically 
create Manufacturing Orders when products are sold through POS.

Key Features
------------
* **Automatic MO Creation**: Manufacturing Orders are automatically created when 
  POS orders containing manufactured products are paid.

* **Product Configuration**: Enable/disable manufacturing integration per product 
  with clear status indicators.

* **BOM Validation**: Prevents POS sales of manufactured products without valid 
  Bill of Materials.

* **Full Traceability**: Complete tracking between POS orders and Manufacturing 
  Orders in both directions.

* **Multi-Company Support**: Respects company boundaries and uses correct 
  warehouse/location settings.

* **Stock & Costing**: Proper inventory movements and cost tracking for raw 
  materials and finished goods.

Compatibility
-------------
* Odoo 18.0
* Odoo 19.0

Dependencies
------------
* Point of Sale (point_of_sale)
* Manufacturing (mrp)

Author
------
taha
    """,
    'author': 'taha',
    'website': 'https://web.whatsapp.com/send/?phone=%2B967777677756&text&type=phone_number&app_absent=0',
    'license': 'LGPL-3',
    'depends': [
        'point_of_sale',
        'mrp',
        'stock',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        
        # Views
        'views/product_template_view.xml',
        'views/pos_order_view.xml',
        'views/pos_session_view.xml',
        'views/mrp_production_view.xml',
    ],
    # JS assets disabled for initial installation - validation is done server-side
    # 'assets': {
    #     'point_of_sale._assets_pos': [
    #         'pos_mrp_integration/static/src/js/pos_mrp.js',
    #         'pos_mrp_integration/static/src/js/pos_product_screen.js',
    #         'pos_mrp_integration/static/src/css/pos_mrp.css',
    #     ],
    # },
    'installable': True,
    'application': False,
    'auto_install': False,
}
