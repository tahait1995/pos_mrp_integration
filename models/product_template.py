# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ============================================
    # POS MRP Integration Fields
    # ============================================
    
    pos_mrp_enabled = fields.Boolean(
        string='Manufacturing from POS',
        default=False,
        help='If enabled, a manufacturing order will be automatically created '
             'when this product is sold through POS.'
    )
    
    pos_mrp_auto_confirm = fields.Boolean(
        string='Auto Confirm MO',
        default=True,
        help='If enabled, Manufacturing Orders will be automatically confirmed '
             'and materials reserved. If disabled, MO will be created as Draft.'
    )
    
    pos_bom_id = fields.Many2one(
        'mrp.bom',
        string='POS Bill of Materials',
        domain="[('product_tmpl_id', '=', id), ('type', '=', 'normal')]",
        help='Bill of Materials to use when creating manufacturing orders from POS. '
             'If not set, the default BOM will be used.'
    )
    
    pos_mrp_check_availability = fields.Boolean(
        string='Check Material Availability',
        default=False,
        help='If enabled, POS sale will be blocked if BOM components are not available '
             'in stock. If disabled, MO will be created regardless of stock availability.'
    )

    # ============================================
    # Computed Fields
    # ============================================
    
    pos_mrp_ready = fields.Boolean(
        string='Ready for POS Manufacturing',
        compute='_compute_pos_mrp_ready',
        store=True,
        help='Indicates if the product is properly configured for POS manufacturing.'
    )
    
    pos_bom_count = fields.Integer(
        string='BOM Count',
        compute='_compute_pos_bom_count'
    )

    # ============================================
    # Compute Methods
    # ============================================
    
    @api.depends('pos_mrp_enabled', 'bom_ids', 'pos_bom_id')
    def _compute_pos_mrp_ready(self):
        """Check if product is ready for POS manufacturing."""
        for product in self:
            if not product.pos_mrp_enabled:
                product.pos_mrp_ready = False
                continue
            
            # Check if there's a valid BOM
            has_valid_bom = bool(product.pos_bom_id) or bool(
                product.bom_ids.filtered(lambda b: b.type == 'normal' and b.active)
            )
            product.pos_mrp_ready = has_valid_bom

    def _compute_pos_bom_count(self):
        """Count available BOMs for this product."""
        for product in self:
            product.pos_bom_count = len(
                product.bom_ids.filtered(lambda b: b.type == 'normal' and b.active)
            )

    # ============================================
    # Constraint Methods
    # ============================================
    
    @api.constrains('pos_mrp_enabled', 'pos_bom_id', 'bom_ids')
    def _check_pos_mrp_bom(self):
        """Ensure product has a valid BOM when POS MRP is enabled."""
        for product in self:
            if product.pos_mrp_enabled:
                if not product.pos_bom_id and not product.bom_ids.filtered(
                    lambda b: b.type == 'normal' and b.active
                ):
                    raise ValidationError(_(
                        'Product "%s" requires a valid Bill of Materials (BOM) '
                        'to enable manufacturing from POS. Please create a BOM first.'
                    ) % product.name)

    # ============================================
    # Business Methods
    # ============================================
    
    def get_pos_bom(self, product_id=None, company_id=None):
        """
        Get the appropriate BOM for POS manufacturing.
        
        :param product_id: Optional specific product variant
        :param company_id: Company to filter BOM by
        :return: mrp.bom record or False
        """
        self.ensure_one()
        
        # First priority: explicitly set POS BOM
        if self.pos_bom_id:
            return self.pos_bom_id
        
        # Second priority: find default BOM
        domain = [
            ('product_tmpl_id', '=', self.id),
            ('type', '=', 'normal'),
            ('active', '=', True),
        ]
        
        if product_id:
            domain.append(('product_id', 'in', [product_id, False]))
        
        if company_id:
            domain.append(('company_id', 'in', [company_id, False]))
        
        bom = self.env['mrp.bom'].search(domain, limit=1, order='sequence, product_id desc')
        return bom if bom else False

    def action_view_pos_bom(self):
        """Open BOMs related to this product."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('mrp.mrp_bom_form_action')
        action['domain'] = [('product_tmpl_id', '=', self.id)]
        action['context'] = {
            'default_product_tmpl_id': self.id,
            'default_type': 'normal',
        }
        return action

    def check_components_availability(self, product_id=None, quantity=1.0, company_id=None, warehouse_id=None):
        """
        Check if all BOM components are available in stock for manufacturing.
        
        :param product_id: Optional specific product variant ID
        :param quantity: Quantity to manufacture
        :param company_id: Company ID for location filtering
        :param warehouse_id: Warehouse ID for location filtering
        :return: dict with 'available' (bool) and 'missing_components' (list)
        """
        self.ensure_one()
        
        result = {
            'available': True,
            'missing_components': [],
        }
        
        # Get BOM
        bom = self.get_pos_bom(product_id=product_id, company_id=company_id)
        if not bom:
            result['available'] = False
            result['missing_components'].append({
                'product': self.name,
                'required': quantity,
                'available': 0,
                'shortage': quantity,
                'reason': _('No BOM found')
            })
            return result
        
        # Get BOM lines (components)
        bom_lines = bom.bom_line_ids
        
        if not bom_lines:
            # No components in BOM
            return result
        
        # Get location for stock check
        location = False
        if warehouse_id:
            warehouse = self.env['stock.warehouse'].browse(warehouse_id)
            if warehouse.exists():
                location = warehouse.lot_stock_id
        
        if not location:
            # Use company's main warehouse
            company = self.env['res.company'].browse(company_id) if company_id else self.env.company
            warehouse = self.env['stock.warehouse'].search([
                ('company_id', '=', company.id)
            ], limit=1)
            if warehouse:
                location = warehouse.lot_stock_id
        
        if not location:
            # Cannot check availability without location - block by default when check is enabled
            result['available'] = False
            result['missing_components'].append({
                'product': _('System'),
                'required': 0,
                'available': 0,
                'shortage': 0,
                'reason': _('No warehouse location found for stock check')
            })
            return result
        
        # Check each component
        for line in bom_lines:
            component = line.product_id
            
            # Calculate required quantity based on BOM quantity
            required_qty = line.product_qty * quantity
            
            # Get available quantity using Odoo standard method
            # This handles reservations, incoming, outgoing properly
            available_qty = self.env['stock.quant']._get_available_quantity(
                component, 
                location,
                strict=True
            )
            
            if available_qty < required_qty:
                result['available'] = False
                result['missing_components'].append({
                    'product': component.display_name,
                    'required': required_qty,
                    'available': available_qty,
                    'shortage': required_qty - available_qty,
                    'uom': line.product_uom_id.name,
                })
        
        return result
