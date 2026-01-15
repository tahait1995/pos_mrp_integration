# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    # ============================================
    # POS Integration Fields
    # ============================================
    
    pos_order_id = fields.Many2one(
        'pos.order',
        string='POS Order',
        ondelete='set null',
        index=True,
        copy=False,
        help='The POS order that triggered this manufacturing order.'
    )
    
    pos_order_line_id = fields.Many2one(
        'pos.order.line',
        string='POS Order Line',
        ondelete='set null',
        index=True,
        copy=False,
        help='The specific POS order line that triggered this manufacturing order.'
    )
    
    pos_order_name = fields.Char(
        string='POS Order Reference',
        related='pos_order_id.name',
        store=True,
        readonly=True
    )
    
    pos_order_date = fields.Datetime(
        string='POS Order Date',
        related='pos_order_id.date_order',
        store=True,
        readonly=True
    )
    
    pos_session_id = fields.Many2one(
        'pos.session',
        string='POS Session',
        related='pos_order_id.session_id',
        store=True,
        readonly=True
    )
    
    is_from_pos = fields.Boolean(
        string='From POS',
        compute='_compute_is_from_pos',
        store=True,
        help='Indicates if this manufacturing order was created from a POS sale.'
    )
    
    pos_partner_id = fields.Many2one(
        'res.partner',
        string='POS Customer',
        related='pos_order_id.partner_id',
        store=True,
        readonly=True
    )

    # ============================================
    # Compute Methods
    # ============================================
    
    @api.depends('pos_order_id')
    def _compute_is_from_pos(self):
        for production in self:
            production.is_from_pos = bool(production.pos_order_id)

    # ============================================
    # Action Methods
    # ============================================
    
    def action_view_pos_order(self):
        """Open the related POS order."""
        self.ensure_one()
        if not self.pos_order_id:
            return False
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('POS Order'),
            'res_model': 'pos.order',
            'view_mode': 'form',
            'res_id': self.pos_order_id.id,
            'target': 'current',
            'context': dict(self.env.context),
        }

    # ============================================
    # Override Methods
    # ============================================
    
    def button_mark_done(self):
        """
        Override to add POS-specific logic when production is completed.
        
        When MO is marked as done:
        - Raw materials are consumed (stock decreased)
        - Finished goods are produced (stock increased)
        - Costs are recorded based on product costing method
        """
        result = super().button_mark_done()
        
        # Log completion for POS orders
        for production in self.filtered('is_from_pos'):
            production.message_post(
                body=_('Manufacturing completed for POS Order: %s') % production.pos_order_name,
                message_type='notification'
            )
        
        return result

    def action_cancel(self):
        """Add warning when canceling POS-originated MOs."""
        pos_productions = self.filtered('is_from_pos')
        if pos_productions:
            # Log the cancellation
            for production in pos_productions:
                production.pos_order_id.message_post(
                    body=_('Manufacturing Order %s was cancelled.') % production.name,
                    message_type='notification'
                )
        
        return super().action_cancel()

    # ============================================
    # Business Methods
    # ============================================
    
    def get_pos_order_details(self):
        """
        Get formatted POS order details for display.
        
        :return: dict with POS order information
        """
        self.ensure_one()
        if not self.pos_order_id:
            return {}
        
        return {
            'order_name': self.pos_order_name,
            'order_date': self.pos_order_date,
            'session': self.pos_session_id.name if self.pos_session_id else '',
            'customer': self.pos_partner_id.name if self.pos_partner_id else _('Walk-in Customer'),
            'cashier': self.pos_order_id.user_id.name if self.pos_order_id.user_id else '',
        }
