# POS MRP Integration for Odoo 18

**Version:** 18.0.1.0.0  
**License:** LGPL-3  
**Category:** Point of Sale / Manufacturing  

## 📖 Overview

This module bridges the gap between **Point of Sale (POS)** and **Manufacturing (MRP)** in Odoo. It is designed for businesses that sell manufactured products directly to customers (e.g., restaurants, bakeries, custom shops) and need real-time generation of Manufacturing Orders (MOs) and accurate raw material stock deduction.

---

## 🔄 Integration Flow & Scenarios

The module follows a strict, transactional workflow to ensure data integrity between sales and inventory.

### Standard Workflow:
1.  **Sales Process (POS)**: Cashier adds a manufactured product (e.g., "Cheese Burger") to the cart.
2.  **Smart Validation (Pre-Payment)**:
    -   The system checks if **Bills of Materials (BOM)** exist for the items.
    -   It performs a **Material Availability Check** (if configured) to ensure raw materials (Bun, Patty, Cheese) are in stock.
    -   *Feature*: **Smart Batch Validation** ensures that if a background sync contains mixed valid/invalid orders, the valid ones are processed immediately while invalid ones are blocked safely.
3.  **Payment & Confirmation**: Upon payment, the POS order is confirmed.
4.  **MO Creation (Backend)**: The system automatically triggers the creation of Manufacturing Orders.
5.  **Inventory Update**:
    -   Raw materials are consumed (Stock decreases).
    -   Finished goods are produced and immediately sold (Stock increases then decreases).

---

## 💡 Key Design Decisions

The following architectural decisions were made to ensure robustness and traceability:

### 1. MO Granularity: One MO per Order Line
**Decision**: Each line in a POS order generates a distinct Manufacturing Order.
-   **Method**: `1 POS Line` = `1 MO`.
-   **Rationale**:
    -   **Traceability**: Provides a direct 1-to-1 link (`pos_order_line_id`) between the sold item and its production record.
    -   **Simplicity**: Avoids complexity when handling POS Refunds/Returns. If a customer returns 1 out of 3 items, we can track exactly which production record matches the return.
    -   **Independence**: Allows specific products to be managed differently (e.g., one requires extra time) without holding up the entire batch.

### 2. MO Initial State: "Confirmed" (Auto-Confirm)
**Decision**: Manufacturing Orders are created in the **Confirmed** state by default, triggering immediate material reservation.
-   **Method**: `state = 'confirmed'` (and `action_confirm()` is called automatically).
-   **Rationale**:
    -   **Real-Time Nature**: POS is an immediate transaction. The customer is usually waiting for the product. Leaving an MO as "Draft" implies a delay or a need for Production Manager approval, which bottlenecks retail operations.
    -   **Stock Integrity**: Confirming immediately strictly **reserves** the raw materials. This prevents the same stock from being "promised" to multiple walk-in customers simultaneously.
    -   *Flexibility*: This behavior is configurable per product via the `Auto Confirm MO` checkbox if a "Draft" workflow is preferred.

### 3. Smart Batch Validation
**Decision**: Filter invalid orders in batch syncs rather than failing the entire request.
-   **Rationale**: In Odoo's POS, offline orders are synced in batches. If one old order fails (e.g., due to stock shortage), standard logic blocks the whole batch, stopping new valid sales. Our **Smart Validation** allows valid orders to pass while isolating the problematic order for review.

---

## ⚙️ Configuration & Setup

### 1. Product Configuration
To enable manufacturing for a product:
1.  Go to **Point of Sale > Products**.
2.  Open the Product form and navigate to the **"POS Manufacturing"** tab.
3.  **Manufacturing from POS**: Enable this to trigger MO creation.
4.  **Auto Confirm MO**: Uncheck if you want MOs to stay in "Draft" state (default: Checked).
5.  **Check Material Availability**: Enable to prevent sales if raw materials are insufficient.
    -   *Note*: Requires a valid Bill of Materials (BOM).

### 2. Bill of Materials (BOM)
Ensure every enabled product has a valid BOM type **"Manufacture this product"**. Kit BOMs are not supported for this specific MO generation flow (as Kits are handled natively by Odoo Stock).

---

## 📋 Assumptions & Limitations

### Assumptions
-   **Stock Locations**: The module uses the warehouse/picking type defined in the POS Configuration. It assumes the POS location has access to the raw materials.
-   **Company Consistency**: In multi-company environments, the POS Session, Product, and BOM belong to the same company.

### Limitations
-   **Partial Production**: The module assumes the full quantity of the line is produced at once.
-   **Work Orders**: While MOs are created, specific Work Order timer tracking is not triggered automatically by the POS; the MO is simply created/confirmed to account for stock.

---

## 🛠 Technical Dependencies
-   `point_of_sale`
-   `mrp`
-   `stock`

---

**Developed for Odoo 18**
