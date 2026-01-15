

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # ============================================
    # Fields
    # ============================================
    
    mrp_production_ids = fields.One2many(
        'mrp.production',
        'pos_order_id',
        string='Manufacturing Orders',
        help='Manufacturing orders created from this POS order.'
    )
    
    mrp_production_count = fields.Integer(
        string='Manufacturing Orders Count',
        compute='_compute_mrp_production_count',
        store=True
    )
    
    has_mrp_products = fields.Boolean(
        string='Has Manufacturing Products',
        compute='_compute_has_mrp_products',
        store=True
    )

    # ============================================
    # Compute Methods
    # ============================================
    
    @api.depends('mrp_production_ids')
    def _compute_mrp_production_count(self):
        for order in self:
            order.mrp_production_count = len(order.mrp_production_ids)

    @api.depends('lines.product_id.product_tmpl_id.pos_mrp_enabled')
    def _compute_has_mrp_products(self):
        for order in self:
            order.has_mrp_products = any(
                line.product_id.product_tmpl_id.pos_mrp_enabled 
                for line in order.lines
            )

    # ============================================
    # Action Methods
    # ============================================
    
    def action_view_mrp_productions(self):
        """Open the manufacturing orders related to this POS order."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('mrp.mrp_production_action')
        
        if self.mrp_production_count == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.mrp_production_ids.id
            action['views'] = [(False, 'form')]
        else:
            action['domain'] = [('pos_order_id', '=', self.id)]
        
        action['context'] = dict(
            self.env.context, 
            default_pos_order_id=self.id,
            default_company_id=self.company_id.id,
        )
        return action

    # ============================================
    # Validation Methods
    # ============================================
    
    def _validate_mrp_products(self):
        """
        Validate that all MRP-enabled products have valid BOMs and optionally
        check material availability.
        Called before payment processing.
        
        :raises UserError: If any product requires manufacturing but has no BOM
        :raises UserError: If material availability check is enabled and components are missing
        """
        self.ensure_one()
        
        invalid_products = []
        unavailable_products = []
        
        # Get warehouse from POS config
        warehouse_id = None
        if self.session_id and self.session_id.config_id:
            picking_type = self.session_id.config_id.picking_type_id
            if picking_type and picking_type.warehouse_id:
                warehouse_id = picking_type.warehouse_id.id
        
        for line in self.lines:
            product_tmpl = line.product_id.product_tmpl_id
            if product_tmpl.pos_mrp_enabled:
                # Check BOM exists
                bom = product_tmpl.get_pos_bom(
                    product_id=line.product_id.id,
                    company_id=self.company_id.id
                )
                if not bom:
                    invalid_products.append(line.product_id.display_name)
                    continue
                
                # Check material availability if enabled
                if product_tmpl.pos_mrp_check_availability:
                    availability = product_tmpl.check_components_availability(
                        product_id=line.product_id.id,
                        quantity=line.qty,
                        company_id=self.company_id.id,
                        warehouse_id=warehouse_id
                    )
                    
                    if not availability['available']:
                        missing_info = []
                        for comp in availability['missing_components']:
                            if 'reason' in comp:
                                missing_info.append(f"  - {comp['reason']}")
                            else:
                                missing_info.append(
                                    f"  - {comp['product']}: "
                                    f"Required {comp['required']} {comp.get('uom', '')}, "
                                    f"Available {comp['available']} "
                                    f"(Shortage: {comp['shortage']})"
                                )
                        
                        unavailable_products.append({
                            'product': line.product_id.display_name,
                            'missing': missing_info
                        })
        
        # Raise error for missing BOMs
        if invalid_products:
            raise UserError(_(
                'The following products require manufacturing but have no valid '
                'Bill of Materials (BOM):\n\n• %s\n\n'
                'Please configure a BOM for these products before selling them.'
            ) % '\n• '.join(invalid_products))
        
        # Raise error for unavailable materials
        if unavailable_products:
            error_lines = []
            for item in unavailable_products:
                error_lines.append(f"📦 {item['product']}:")
                error_lines.extend(item['missing'])
            
            raise UserError(_(
                'Cannot complete sale - insufficient materials for manufacturing:\n\n%s\n\n'
                'Please ensure all required components are in stock, '
                'or disable "Check Material Availability" on the product.'
            ) % '\n'.join(error_lines))

    # ============================================
    # Manufacturing Order Creation
    # ============================================
    
    def _create_manufacturing_orders(self):
        """
        Create Manufacturing Orders for all MRP-enabled products in this order.
        
        Design Decision: One MO per order line
        - Each POS order line generates one Manufacturing Order
        - This provides clear traceability between POS sale and production
        - Allows independent tracking of each product's manufacturing status
        
        :return: recordset of created mrp.production records
        """
        self.ensure_one()
        
        MrpProduction = self.env['mrp.production']
        created_productions = MrpProduction
        
        for line in self.lines:
            product_tmpl = line.product_id.product_tmpl_id
            
            # Skip non-MRP products and zero quantity lines
            if not product_tmpl.pos_mrp_enabled or line.qty <= 0:
                continue
            
            # Get BOM for this product
            bom = product_tmpl.get_pos_bom(
                product_id=line.product_id.id,
                company_id=self.company_id.id
            )
            
            if not bom:
                _logger.warning(
                    'No BOM found for product %s (ID: %s) in POS order %s',
                    line.product_id.display_name, line.product_id.id, self.name
                )
                continue
            
            # Prepare MO values
            production_vals = self._prepare_mrp_production_vals(line, bom)
            
            try:
                production = MrpProduction.create(production_vals)
                
                # Auto-confirm if configured
                if product_tmpl.pos_mrp_auto_confirm:
                    production.action_confirm()
                    _logger.info(
                        'Created and confirmed MO %s for POS order %s, product %s',
                        production.name, self.name, line.product_id.display_name
                    )
                else:
                    _logger.info(
                        'Created draft MO %s for POS order %s, product %s',
                        production.name, self.name, line.product_id.display_name
                    )
                
                created_productions |= production
                
            except Exception as e:
                _logger.error(
                    'Failed to create MO for POS order %s, product %s: %s',
                    self.name, line.product_id.display_name, str(e)
                )
                raise UserError(_(
                    'Failed to create Manufacturing Order for product "%s".\n'
                    'Error: %s'
                ) % (line.product_id.display_name, str(e)))
        
        return created_productions

    def _prepare_mrp_production_vals(self, line, bom):
        """
        Prepare values for manufacturing order creation.
        
        :param line: pos.order.line record
        :param bom: mrp.bom record
        :return: dict of values for mrp.production.create()
        """
        self.ensure_one()
        
        # Get the picking type for manufacturing
        picking_type = self._get_mrp_picking_type()
        
        return {
            'product_id': line.product_id.id,
            'product_qty': line.qty,
            'product_uom_id': line.product_id.uom_id.id,
            'bom_id': bom.id,
            'pos_order_id': self.id,
            'pos_order_line_id': line.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'picking_type_id': picking_type.id if picking_type else False,
            'user_id': self.env.user.id,
        }

    def _get_mrp_picking_type(self):
        """
        Get the appropriate manufacturing picking type for this order's company/warehouse.
        
        :return: stock.picking.type record or False
        """
        self.ensure_one()
        
        # Try to get picking type from POS config's warehouse
        if self.session_id and self.session_id.config_id:
            warehouse = self.session_id.config_id.picking_type_id.warehouse_id
            if warehouse:
                picking_type = self.env['stock.picking.type'].search([
                    ('code', '=', 'mrp_operation'),
                    ('warehouse_id', '=', warehouse.id),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)
                if picking_type:
                    return picking_type
        
        # Fallback: search for any manufacturing picking type in the company
        return self.env['stock.picking.type'].search([
            ('code', '=', 'mrp_operation'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

    # ============================================
    # Override Methods
    # ============================================
    
    @api.model
    def sync_from_ui(self, orders):
        """
        Override sync_from_ui for Odoo 18 to validate MRP products BEFORE sync.
        
        Smart Validation Logic:
        1. If single order (Active Pay): Raise UserError to show immediate feedback.
        2. If batch (Background Sync): Filter out invalid orders, save valid ones.
           This prevents old stuck orders from blocking new valid sales.
        """
        valid_orders = []
        blocked_orders = []
        
        # Validate each order
        for order_data in orders:
            validation_error = self._check_mrp_availability_for_order(order_data)
            if validation_error:
                blocked_orders.append((order_data, validation_error))
            else:
                valid_orders.append(order_data)
        
        # Scenario 1: Single order failed (User just clicked Pay)
        if len(orders) == 1 and blocked_orders:
            # Raise error to notify user immediately
            raise UserError(blocked_orders[0][1])
            
        # Scenario 2: Batch processing (User clicked Pay on New Order + Stored Orders)
        if len(orders) > 1 and blocked_orders:
            _logger.warning("POS MRP: Batch contains %s blocked orders. Skipping them to allow valid orders.", len(blocked_orders))
            for failed_ord, err in blocked_orders:
                _logger.warning("POS MRP: Skipped Order %s: %s", failed_ord.get('data', {}).get('name'), err)
                
            # Only proceed with valid orders
            if not valid_orders:
                # If ALL orders are bad, we must return something to stop infinite retry loop ideally,
                # but raising error here is safer to indicate system state.
                # However, since it's a batch, we just return empty list to simulate "Nothing created".
                # The POS will keep them in queue.
                return {'pos.order': []}
                
            return super().sync_from_ui(valid_orders)
            
        # Scenario 3: All Valid
        return super().sync_from_ui(orders)
    
    @api.model
    def _check_mrp_availability_for_order(self, order_data):
        """
        Check material availability for MRP products in order.
        Returns error message string if unavailable, None if OK.
        """
        data = order_data.get('data', order_data)
        lines = data.get('lines', [])
        order_name = data.get('name', 'Unknown Order')
        
        if not lines:
            return None
        
        # Get session info
        session_id = data.get('pos_session_id')
        session = self.env['pos.session'].browse(session_id) if session_id else False
        
        warehouse_id = None
        company_id = self.env.company.id
        
        if session and session.exists():
            company_id = session.company_id.id
            if session.config_id and session.config_id.picking_type_id:
                warehouse = session.config_id.picking_type_id.warehouse_id
                if warehouse:
                    warehouse_id = warehouse.id
        
        unavailable = []
        
        for idx, line_data in enumerate(lines):
            line_vals = line_data[2] if isinstance(line_data, (list, tuple)) and len(line_data) >= 3 else line_data if isinstance(line_data, dict) else None
            
            if not line_vals:
                continue
            
            product_id = line_vals.get('product_id')
            qty = line_vals.get('qty', 1)
            
            if not product_id or qty <= 0:
                continue
            
            # Ensure product_id is an integer
            try:
                product_id = int(product_id)
            except (ValueError, TypeError):
                continue

            product = self.env['product.product'].browse(product_id)
            if not product.exists():
                continue
            
            product_tmpl = product.product_tmpl_id
            
            # STRICT CHECK: Must be enabled AND check availability enabled
            if not product_tmpl.pos_mrp_enabled:
                continue
                
            if not product_tmpl.pos_mrp_check_availability:
                continue
            
            availability = product_tmpl.check_components_availability(
                product_id=product_id,
                quantity=qty,
                company_id=company_id,
                warehouse_id=warehouse_id
            )
            
            if not availability['available']:
                details = []
                for comp in availability['missing_components']:
                    if 'reason' in comp:
                        details.append(comp['reason'])
                    else:
                        details.append(f"{comp['product']}: مطلوب {comp['required']:.2f}, متوفر {comp['available']:.2f}")
                unavailable.append(f"📦 {product.display_name}: " + ", ".join(details))
        
        if unavailable:
            return f"طلب {order_name}:\nالمواد الخام غير كافية للتصنيع:\n" + "\n".join(unavailable)
        
        return None

    def action_pos_order_paid(self):
        """
        Override to create manufacturing orders when POS order is paid.
        
        Flow:
        1. Validate MRP products have valid BOMs
        2. Process payment (original method)
        3. Create Manufacturing Orders
        """
        # Validate before processing payment (backup validation)
        for order in self:
            order._validate_mrp_products()
        
        # Call original method
        result = super().action_pos_order_paid()
        
        # Create manufacturing orders after successful payment
        for order in self:
            if order.has_mrp_products:
                order._create_manufacturing_orders()
        
        return result

    @api.model
    def _order_fields(self, ui_order):
        """Extend to include MRP-related data from POS frontend."""
        result = super()._order_fields(ui_order)
        # Add any additional fields from UI if needed
        return result


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    # ============================================
    # Fields
    # ============================================
    
    mrp_production_ids = fields.One2many(
        'mrp.production',
        'pos_order_line_id',
        string='Manufacturing Orders',
        help='Manufacturing orders created from this order line.'
    )
    
    requires_manufacturing = fields.Boolean(
        string='Requires Manufacturing',
        compute='_compute_requires_manufacturing',
        store=True
    )

    # ============================================
    # Compute Methods
    # ============================================
    
    @api.depends('product_id.product_tmpl_id.pos_mrp_enabled')
    def _compute_requires_manufacturing(self):
        for line in self:
            line.requires_manufacturing = (
                line.product_id and 
                line.product_id.product_tmpl_id.pos_mrp_enabled
            )
