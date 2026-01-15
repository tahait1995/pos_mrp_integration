/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductCard } from "@point_of_sale/app/generic_components/product_card/product_card";
import { _t } from "@web/core/l10n/translation";

/**
 * Extend ProductCard to show manufacturing indicator
 */
patch(ProductCard.prototype, {
    /**
     * Get additional CSS classes for products requiring manufacturing
     * 
     * @returns {string} CSS classes
     */
    getProductClasses() {
        let classes = super.getProductClasses ? super.getProductClasses() : "";

        if (this.props.product.pos_mrp_enabled) {
            classes += " o_pos_mrp_product";

            if (!this.props.product.pos_mrp_ready) {
                classes += " o_pos_mrp_not_ready";
            }
        }

        return classes;
    },

    /**
     * Check if product requires manufacturing
     * 
     * @returns {boolean}
     */
    get isMrpProduct() {
        return this.props.product.pos_mrp_enabled;
    },

    /**
     * Check if product is ready for manufacturing
     * 
     * @returns {boolean}
     */
    get isMrpReady() {
        return this.props.product.pos_mrp_ready;
    },

    /**
     * Get manufacturing status tooltip
     * 
     * @returns {string}
     */
    get mrpTooltip() {
        if (!this.props.product.pos_mrp_enabled) {
            return "";
        }

        if (this.props.product.pos_mrp_ready) {
            return _t("This product will trigger automatic manufacturing");
        }

        return _t("Manufacturing enabled but no valid BOM - Sale blocked");
    },
});
