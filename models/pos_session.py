# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PosSession(models.Model):
    _inherit = 'pos.session'

    # ============================================
    # Fields
    # ============================================
    
    mrp_production_count = fields.Integer(
        string='Manufacturing Orders',
        compute='_compute_mrp_production_count'
    )

    # ============================================
    # Compute Methods
    # ============================================
    
    def _compute_mrp_production_count(self):
        """Count all MOs created from orders in this session."""
        for session in self:
            session.mrp_production_count = self.env['mrp.production'].search_count([
                ('pos_session_id', '=', session.id)
            ])

    # ============================================
    # Action Methods
    # ============================================
    
    def action_view_mrp_productions(self):
        """View all manufacturing orders from this session."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('mrp.mrp_production_action')
        action['domain'] = [('pos_session_id', '=', self.id)]
        action['context'] = dict(self.env.context)
        return action

    # ============================================
    # Override Methods
    # ============================================
    
    def _loader_params_product_product(self):
        """Add POS MRP fields to product data loaded in POS."""
        result = super()._loader_params_product_product()
        result['search_params']['fields'].extend([
            'pos_mrp_enabled',
            'pos_mrp_ready',
        ])
        return result
