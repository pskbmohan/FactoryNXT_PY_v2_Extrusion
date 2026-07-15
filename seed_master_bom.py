#!/usr/bin/env python3
"""
Seed script for BOM-driven Work Order feature.
Populates: Customers, PartNumbers, CustomerPartMappings, PartNumberBOMs, CustomerOrders with lines

Run with:  python seed_master_bom.py
"""
import uuid
from datetime import datetime, date, timedelta


def seed():
    from app import create_app, db
    from app.models import (
        Customer, PartNumber, CustomerPartNumber, PartNumberBOM,
        CustomerOrder, CustomerOrderLine, WorkOrder, Die, Billet
    )

    app = create_app()
    with app.app_context():
        print("🌱 Starting seed for BOM Master Data...")

        # ── 1. Seed Customers (3 customers) ───────────────────────────────
        customer_defs = [
            {"customer_code": "CUST-001", "customer_name": "Apex Profiles Pvt Ltd",
             "contact_email": "procurement@apexprofiles.com", "contact_phone": "+91-22-12345678",
             "address": "Plot 45, Industrial Estate, Mumbai, Maharashtra 400001"},
            {"customer_code": "CUST-002", "customer_name": "Delta Systems Ltd",
             "contact_email": "orders@deltasystems.in", "contact_phone": "+91-80-98765432",
             "address": "Sector 18, Electronic City, Bangalore, Karnataka 560100"},
            {"customer_code": "CUST-003", "customer_name": "Vertex Metals",
             "contact_email": "supply@vertexmetals.com", "contact_phone": "+91-79-87654321",
             "address": "SG Highway, Ahmedabad, Gujarat 380015"},
        ]

        customers = []
        for cd in customer_defs:
            cust = Customer.query.filter_by(customer_code=cd["customer_code"]).first()
            if not cust:
                cust = Customer(
                    id=str(uuid.uuid4()),
                    customer_code=cd["customer_code"],
                    customer_name=cd["customer_name"],
                    contact_email=cd.get("contact_email"),
                    contact_phone=cd.get("contact_phone"),
                    address=cd.get("address"),
                    is_active=True,
                )
                db.session.add(cust)
                print(f"  ✅ Created Customer: {cd['customer_code']} - {cd['customer_name']}")
            else:
                cust.is_active = True
                db.session.flush()
            customers.append(cust)
        db.session.flush()

        # ── 2. Seed Part Numbers (5 part numbers) ─────────────────────────
        part_defs = [
            {"part_code": "PN-6063-H-100", "description": "6063 Alloy Hollow Profile 100mm",
             "profile_code": "PROF-FH-100X50", "alloy": "6063", "unit_weight_kg": 2.5},
            {"part_code": "PN-6063-S-200", "description": "6063 Alloy Solid Profile 200mm",
             "profile_code": "PROF-SQ-200X200", "alloy": "6063", "unit_weight_kg": 15.0},
            {"part_code": "PN-6082-H-300", "description": "6082 Alloy Hollow Profile 300mm",
             "profile_code": "PROF-FH-300X150", "alloy": "6082", "unit_weight_kg": 4.2},
            {"part_code": "PN-6082-S-400", "description": "6082 Alloy Solid Profile 400mm",
             "profile_code": "PROF-SQ-400X400", "alloy": "6082", "unit_weight_kg": 35.0},
            {"part_code": "PN-7075-H-500", "description": "7075 Alloy High-Strength Hollow Profile 500mm",
             "profile_code": "PROF-FH-500X250", "alloy": "7075", "unit_weight_kg": 6.8},
        ]

        part_numbers = []
        for pd in part_defs:
            pn = PartNumber.query.filter_by(part_code=pd["part_code"]).first()
            if not pn:
                pn = PartNumber(
                    id=str(uuid.uuid4()),
                    part_code=pd["part_code"],
                    description=pd["description"],
                    profile_code=pd.get("profile_code"),
                    alloy=pd.get("alloy"),
                    unit_weight_kg=pd.get("unit_weight_kg"),
                    uom="KG",
                    is_active=True,
                )
                db.session.add(pn)
                print(f"  ✅ Created Part Number: {pd['part_code']}")
            else:
                pn.is_active = True
                db.session.flush()
            part_numbers.append(pn)
        db.session.flush()

        # ── 3. Seed Customer-Part Mappings ────────────────────────────────
        # CUST-001: PN-6063-H-100, PN-6063-S-200, PN-6082-H-300
        # CUST-002: PN-6082-H-300, PN-6082-S-400
        # CUST-003: PN-7075-H-500, PN-6063-H-100
        mapping_defs = [
            (customers[0], part_numbers[0]),  # CUST-001 -> PN-6063-H-100
            (customers[0], part_numbers[1]),  # CUST-001 -> PN-6063-S-200
            (customers[0], part_numbers[2]),  # CUST-001 -> PN-6082-H-300
            (customers[1], part_numbers[2]),  # CUST-002 -> PN-6082-H-300
            (customers[1], part_numbers[3]),  # CUST-002 -> PN-6082-S-400
            (customers[2], part_numbers[4]),  # CUST-003 -> PN-7075-H-500
            (customers[2], part_numbers[0]),  # CUST-003 -> PN-6063-H-100
        ]

        for cust, pn in mapping_defs:
            existing = CustomerPartNumber.query.filter_by(
                customer_id=cust.id, part_number_id=pn.id
            ).first()
            if not existing:
                cmap = CustomerPartNumber(
                    id=str(uuid.uuid4()),
                    customer_id=cust.id,
                    part_number_id=pn.id,
                    customer_part_ref=f"{cust.customer_code}-{pn.part_code}",
                    is_active=True,
                )
                db.session.add(cmap)
                print(f"  ✅ Mapped: {cust.customer_code} -> {pn.part_code}")
        db.session.flush()

        # ── 4. Get available Dies and Billets for BOM creation ────────────
        dies = Die.query.filter_by(is_active=True).all()
        billets = Billet.query.filter(Billet.status.in_(['AVAILABLE', 'IN_STOCK'])).all()

        if not dies or not billets:
            print("  ⚠️ Warning: No active Dies or Billets found. Creating sample data...")
            # Create default die and billet if none exist
            if not dies:
                for i, d in enumerate([
                    {"die_code": "DIE-6063-H100", "profile_code": "PROF-FH-100X50"},
                    {"die_code": "DIE-6063-S200", "profile_code": "PROF-SQ-200X200"},
                ]):
                    die = Die(
                        id=str(uuid.uuid4()),
                        die_code=d["die_code"],
                        profile_code=d["profile_code"],
                        alloy="6063",
                        status="Available",
                        is_active=True,
                    )
                    db.session.add(die)
                    dies.append(die)
                die_count = len(["DIE-6063-H100", "DIE-6063-S200"])
                print(f"  ✅ Created {die_count} Die(s)")

            if not billets:
                for i, b in enumerate([
                    {"billet_code": "BLT-6063-STD", "alloy": "6063"},
                    {"billet_code": "BLT-6082-STD", "alloy": "6082"},
                ]):
                    billet = Billet(
                        id=str(uuid.uuid4()),
                        billet_code=b["billet_code"],
                        alloy=b["alloy"],
                        diameter_mm=150,
                        length_mm=6000,
                        quantity_kg=1000.0,
                        status="AVAILABLE",
                    )
                    db.session.add(billet)
                    billets.append(billet)
                billet_count = len(["BLT-6063-STD", "BLT-6082-STD"])
                print(f"  ✅ Created {billet_count} Billet(s)")
            db.session.flush()

        # ── 5. Seed PartNumberBOMs (active BOM for each part number) ───────
        today = date.today()
        bom_versions = {}  # Track version per part_number_id

        pn_bom_mappings = [
            (part_numbers[0], dies[0] if len(dies) > 0 else None, billets[0] if len(billets) > 0 else None),  # PN-6063-H-100
            (part_numbers[1], dies[0] if len(dies) > 0 else None, billets[0] if len(billets) > 0 else None),  # PN-6063-S-200
            (part_numbers[2], dies[1] if len(dies) > 1 else dies[0], billets[1] if len(billets) > 1 else billets[0]),  # PN-6082-H-300
            (part_numbers[3], dies[1] if len(dies) > 1 else dies[0], billets[1] if len(billets) > 1 else billets[0]),  # PN-6082-S-400
            (part_numbers[4], dies[0] if len(dies) > 0 else None, billets[0] if len(billets) > 0 else None),  # PN-7075-H-500
        ]

        for pn, die, billet in pn_bom_mappings:
            if not die or not billet:
                print(f"  ⚠️ Skipping BOM for {pn.part_code} - missing die/billet")
                continue

            version = bom_versions.get(pn.id, 0) + 1
            bom_versions[pn.id] = version

            # Check if active BOM exists (deactivate it first)
            existing_active = PartNumberBOM.query.filter_by(
                part_number_id=pn.id, is_active=True
            ).first()
            if existing_active:
                existing_active.is_active = False

            bom = PartNumberBOM(
                id=str(uuid.uuid4()),
                part_number_id=pn.id,
                version=version,
                die_type_id=die.id,
                billet_type_id=billet.id,
                billet_weight_kg=pn.unit_weight_kg or 5.0,
                extrusion_ratio=20 + (version * 2),
                notes=f"Standard BOM v{version} for {pn.part_code}",
                is_active=True,
                created_by="seed",
            )
            db.session.add(bom)
            print(f"  ✅ Created BOM: {pn.part_code} -> Die:{die.die_code}, Billet:{billet.billet_code}")

        db.session.flush()

        # ── 6. Seed Customer Orders with Lines ─────────────────────────────
        today = date.today()
        order_defs = [
            {
                "order_number": "CO-2026-100", "customer_id": customers[0].id,
                "due_date": today + timedelta(days=7),
                "lines": [
                    {"part_number_id": part_numbers[0].id, "qty": 500, "required_date": today + timedelta(days=5)},
                    {"part_number_id": part_numbers[1].id, "qty": 200, "required_date": today + timedelta(days=7)},
                ]
            },
            {
                "order_number": "CO-2026-101", "customer_id": customers[1].id,
                "due_date": today + timedelta(days=10),
                "lines": [
                    {"part_number_id": part_numbers[2].id, "qty": 350, "required_date": today + timedelta(days=8)},
                    {"part_number_id": part_numbers[3].id, "qty": 150, "required_date": today + timedelta(days=10)},
                ]
            },
        ]

        for od in order_defs:
            co = CustomerOrder.query.filter_by(order_number=od["order_number"]).first()
            if not co:
                co = CustomerOrder(
                    id=str(uuid.uuid4()),
                    customer_id=od["customer_id"],
                    order_number=od["order_number"],
                    status="PENDING",
                    due_date=od["due_date"],
                )
                db.session.add(co)
                print(f"  ✅ Created CustomerOrder: {od['order_number']}")

                # Add lines to this order
                for i, line_def in enumerate(od["lines"]):
                    pn = PartNumber.query.get(line_def["part_number_id"])
                    if not pn:
                        continue

                    line = CustomerOrderLine(
                        id=str(uuid.uuid4()),
                        order_id=co.id,
                        part_number_id=line_def["part_number_id"],
                        line_number=i + 1,
                        ordered_qty=line_def["qty"],
                        uom="KG",
                        required_date=line_def.get("required_date"),
                        status="OPEN",
                    )
                    db.session.add(line)

                db.session.flush()
            else:
                print(f"  ⚠️ Order {od['order_number']} already exists, skipping...")

        # ── 7. Commit everything ──────────────────────────────────────────
        try:
            db.session.commit()
            print("\n✅ Seed complete! Summary:")
            from app.models import Customer as C, PartNumber as PN, CustomerOrder as CO
            print(f"   Customers:           {C.query.count()}")
            print(f"   Part Numbers:        {PN.query.count()}")
            print(f"   BOMs:                {PartNumberBOM.query.count()}")
            print(f"   Customer-Part Maps:  {CustomerPartNumber.query.count()}")
            print(f"   Customer Orders:     {CO.query.count()}")
            print(f"   Order Lines:         {CustomerOrderLine.query.count()}")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Seed FAILED: {e}")
            raise


if __name__ == "__main__":
    seed()
