/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Order } from "@point_of_sale/app/store/models";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

/**
 * POS MRP Integration
 * 
 * This module extends the POS Order model to validate products
 * that require manufacturing have valid BOMs before payment.
 */

patch(Order.prototype, {
    /**
     * Check if any orderline contains products requiring manufacturing
     * without a valid BOM configuration.
     * 
     * @returns {Array} List of product names that are not properly configured
     */
    getMrpProductsWithoutBom() {
        const invalidProducts = [];
        
        for (const line of this.get_orderlines()) {
            const product = line.get_product();
            if (product.pos_mrp_enabled && !product.pos_mrp_ready) {
                invalidProducts.push(product.display_name);
            }
        }
        
        return invalidProducts;
    },

    /**
     * Check if this order has any products requiring manufacturing
     * 
     * @returns {boolean}
     */
    hasMrpProducts() {
        return this.get_orderlines().some(line => {
            const product = line.get_product();
            return product.pos_mrp_enabled;
        });
    },

    /**
     * Validate MRP products before payment
     * Override to add BOM validation
     * 
     * @returns {boolean} True if valid, throws error otherwise
     */
    async pay() {
        const invalidProducts = this.getMrpProductsWithoutBom();
        
        if (invalidProducts.length > 0) {
            this.env.services.dialog.add(AlertDialog, {
                title: _t("Manufacturing Configuration Error"),
                body: _t(
                    "The following products require manufacturing but have no valid Bill of Materials (BOM):\n\n• %s\n\nPlease contact your administrator to configure these products.",
                    invalidProducts.join("\n• ")
                ),
            });
            return false;
        }
        
        return super.pay(...arguments);
    },
});
