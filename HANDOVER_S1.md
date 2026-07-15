# BOM-Driven Work Order Feature - Handover (Session 1 Complete)

## Session Status: **COMPLETE**

### What Was Completed in Session 1

#### 1. New Database Models Added to `app/models.py`

All 5 new models have been successfully added under the section marker:
```python
# ─── EXTRUSION MASTER DATA: CUSTOMER / PART NUMBER / BOM ──────────────────────
```

| Model | Table Name | Purpose |
|-------|------------|---------|
| `Customer` | `customers` | Customer master data with contact info and status flags |
| `PartNumber` | `part_numbers` | Part number master data with alloy, weight, profile code |
| `CustomerPartNumber` | `customer_part_numbers` | Junction table mapping customers to their approved part numbers |
| `PartNumberBOM` | `part_number_boms` | BOM linking parts to die/billet types with version tracking |
| `CustomerOrderLine` | `customer_order_lines` | Line items within customer orders, linked to part numbers |

#### 2. WorkOrder Model Patched

Added the following fields and relationships to existing `WorkOrder` class:

**New Columns:**
- `customer_order_line_id` - FK to customer_order_lines (nullable)
- `part_number_id` - FK to part_numbers (nullable)
- `die_type_id` - FK to dies (nullable)
- `billet_type_id` - FK to billets (nullable)
- `bom_version_id` - FK to part_number_boms (nullable)

**New Relationships:**
- `customer_order_line` → CustomerOrderLine
- `part_number_ref` → PartNumber
- `die_type_ref` → Die
- `billet_type_ref` → Billet
- `bom_ref` → PartNumberBOM

#### 3. Alembic Migration Created

**File:** `migrations/versions/20260715_add_customer_part_bom_wo_fields.py`

Migration includes:
- CREATE TABLE for all 5 new tables with proper constraints and foreign keys
- ALTER TABLE ADD COLUMN for the 5 BOM-related fields on work_orders table
- FK constraints linking to dies, billets, part_numbers, customer_order_lines, part_number_boms
- Unique constraint on (customer_id, part_number_id) in customer_part_numbers

**Revision ID:** `20260715_add_customer_part_bom_wo_fields`  
**Down Revision:** `base_20260701`

### Files Modified/Created

| File | Action | Notes |
|------|--------|-------|
| `app/models.py` | MODIFIED | Added 5 new model classes + patched WorkOrder |
| `migrations/versions/20260715_add_customer_part_bom_wo_fields.py` | CREATED | New migration file with upgrade/downgrade functions |

### Syntax Verification Results

All models import successfully and have correct column definitions:
- ✓ Customer has all expected columns (customer_code, customer_name, contact_email, is_active)
- ✓ PartNumber has all expected columns (part_code, description, alloy, unit_weight_kg)
- ✓ CustomerPartNumber has all expected columns (customer_id, part_number_id, customer_part_ref)
- ✓ PartNumberBOM has all expected columns (die_type_id, billet_type_id, version, billet_weight_kg)
- ✓ CustomerOrderLine has all expected columns (order_id, part_number_id, line_number, ordered_qty)
- ✓ WorkOrder has all BOM-related fields

### Next Session: Session 2 - Backend Services & API Routes

**Tasks for S2:**
1. Create `app/services/bom_service.py` with functions:
   - `get_active_bom(part_number_id)` 
   - `validate_part_for_customer(customer_id, part_number_id)`
   - `resolve_bom_for_wo(part_number_id)`

2. Create `app/services/work_order_service.py` with function:
   - `create_wo_from_order_line(order_line_id, ...)`

3. Create `app/routes/master_data_bom.py` blueprint with API endpoints for customers, part numbers, customer-part mappings, and BOMs

4. Create `app/routes/customer_orders_bom.py` blueprint with API endpoints for customer orders and order lines

5. Register both blueprints in `app/__init__.py`

6. Test all endpoints with curl/httpie

### Data Flow (Session 1 Foundation)

```
Customer → CustomerPartNumber → PartNumber → PartNumberBOM → die_type_id + billet_type_id
         ↓
    CustomerOrder → CustomerOrderLine → [create-wo] → WorkOrder (auto-resolved BOM fields populated)
```

### Notes for Next Session

- The `customer_part_numbers` relationship creates backrefs dynamically via SQLAlchemy - the `Customer.customer_part_numbers` and `PartNumber.customer_part_numbers` are accessible through ORM relationships even though they don't appear as static attributes.
- Migration can be applied when PostgreSQL is available: `flask db upgrade`
- All foreign key constraints use proper CASCADE behavior for referential integrity
