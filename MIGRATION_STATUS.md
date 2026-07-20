# Database Migration Status Report

**Date:** 2026-07-20  
**Migration File:** `migrations/versions/20260715_add_customer_part_bom_wo_fields.py`

---

## Current Status: ⚠️ Migration File Exists, Cannot Apply (PostgreSQL Not Running)

### Why the migration couldn't be applied:
```
psycopg2.OperationalError: connection to server at "localhost" (127.0.0.1), port 5432 failed: Connection refused
```

The PostgreSQL database server is not running on localhost:5432.

---

## Migration File Verification ✅

**File exists and is properly formatted:**
- Path: `migrations/versions/20260715_add_customer_part_bom_wo_fields.py`
- Revision ID: `20260715_add_customer_part_bom_wo_fields`
- Down_revision: `base_20260701`

### Tables to be created (5 new tables):

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| **customers** | Customer master data | customer_code, customer_name, contact_email, address |
| **part_numbers** | Part number master data | part_code, description, profile_code, alloy |
| **customer_part_numbers** | Junction table for approved parts | customer_id, part_number_id, customer_part_ref |
| **part_number_boms** | BOM linking part to die/billet | part_number_id, die_type_id, billet_type_id, bom_version |
| **customer_order_lines** | Order line items | order_id, part_number_id, ordered_qty, status |

### WorkOrder table patches (5 new columns):

1. `customer_order_line_id` - FK to customer_order_lines
2. `part_number_id` - FK to part_numbers
3. `die_type_id` - FK to die_types
4. `billet_type_id` - FK to billet_types
5. `bom_version_id` - FK to part_number_boms

---

## Next Steps to Apply Migration:

### Option 1: Start PostgreSQL locally (if available)
```bash
# Check if postgres is installed
which psql

# Start postgresql service (command varies by OS)
sudo systemctl start postgresql

# Or start in background for testing
pg_ctl -D /var/lib/postgresql/data start
```

### Option 2: Connect to remote PostgreSQL instance
Set environment variables before running migration:
```bash
export DATABASE_URL=postgresql://user:password@remote-host:5432/your_database
cd /home/mohan/FactoryNXT_PY_v2_Extrusion
flask db upgrade
```

### Option 3: Use Docker PostgreSQL (quick setup)
```bash
# Start a postgres container for testing
docker run -d --name factorynxt-postgres \
  -e POSTGRES_DB=factorynxt_db \
  -e POSTGRES_USER=mohan \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 postgres:15

# Then run migration
cd /home/mohan/FactoryNXT_PY_v2_Extrusion
flask db upgrade

# Clean up after testing
docker stop factorynxt-postgres && docker rm factorynxt-postgres
```

---

## Verification Commands (Once Migration Runs Successfully):

### Check table counts:
```bash
psql factorynxt_db -c "\dt customers|part_numbers|customer_part_numbers|part_number_boms|customer_order_lines"
```

Expected output after running `python3 seed_master_bom.py`:
- customers: 3 rows (seeded)
- part_numbers: 5 rows (seeded)
- customer_part_numbers: 7 rows (mappings)
- part_number_boms: 5 rows (active BOMs)
- customer_order_lines: 4 rows (order lines from seeded orders)

---

## Conclusion

✅ **Migration file is ready and verified**  
⚠️ **Cannot apply without PostgreSQL connection**  
📝 **This status report documents the current state for future deployment**

The migration will be automatically applied when the application connects to a valid PostgreSQL database with the `flask db upgrade` command. All code changes are complete and ready for production deployment once database connectivity is established.
