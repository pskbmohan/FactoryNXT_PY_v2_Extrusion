#!/usr/bin/env python3
"""Seed script for Warehouse Management System demo data.

Creates sample racks, assigns some dies to slots, and generates transaction history
for demonstration purposes.

Usage:
    cd /home/mohan/FactoryNXT_PY_v2_Extrusion
    python scripts/seed_warehouse_data.py
"""

import sys
from datetime import datetime, timedelta
import uuid

# Add parent directory to path for imports
sys.path.insert(0, '/home/mohan/FactoryNXT_PY_v2_Extrusion')

from app import create_app, db
from app.models import (
    ToolRoomRack, DieRackAssignment, RackTransaction, DieLocationIndex,
    Die, WorkOrder, CustomerOrderLine, PartNumber, AlloyComposition
)


def generate_rack_code(zone: str, rack_num: int) -> str:
    """Generate a rack code."""
    return f"RACK-{zone}-{rack_num:03d}"


def seed_warehouse_data():
    """Seed the warehouse management system with demo data."""

    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("Warehouse Management System - Seed Data")
        print("=" * 60)

        # Check if already seeded
        existing_racks = ToolRoomRack.query.count()
        if existing_racks > 0:
            print(f"\n[INFO] Warehouse data already exists ({existing_racks} racks found). Skipping seed.")
            return

        operator_id = "system"

        # Create sample zones
        zones = ["ZONE_A", "ZONE_B", "TOOL_ROOM_1"]

        rack_types = [
            ("STORAGE_RACK", 20, "General storage rack for die inventory"),
            ("QUICK_CHANGE_RACK", 10, "Quick change rack near press for fast swaps"),
            ("INPRESS_RACK", 5, "In-press rack for dies currently in use")
        ]

        print("\n[1/4] Creating racks...")

        # Create racks across different zones and types
        rack_counter = {}
        created_racks = []

        for zone in zones:
            rack_counter[zone] = 1

            for rack_type, total_slots, description in rack_types:
                rack_code = generate_rack_code(zone, rack_counter[zone])

                # Create the rack
                new_rack = ToolRoomRack(
                    id=str(uuid.uuid4()),
                    rack_code=rack_code,
                    rack_name=f"{rack_type.replace('_', ' ').title()} - {zone}",
                    rack_type=rack_type,
                    location_zone=zone,
                    total_slots=total_slots,
                    available_slots=total_slots,
                    status="AVAILABLE",
                    description=description,
                    is_active=True,
                    created_by=operator_id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )

                db.session.add(new_rack)
                db.session.flush()  # Get the ID

                created_racks.append(new_rack)
                rack_counter[zone] += 1

                print(f"    Created: {rack_code} ({rack_type}) in {zone}")

        db.session.commit()
        print(f"\n[OK] Created {len(created_racks)} racks")

        # Get some existing dies to assign (or create sample ones)
        print("\n[2/4] Preparing die assignments...")

        # Query existing dies or use placeholder codes
        available_dies = Die.query.filter_by(status="AVAILABLE").all()

        if not available_dies:
            # Create some sample dies for demonstration
            alloy_compositions = AlloyComposition.query.all()
            alloys = [ac.alloy_code for ac in alloy_compositions] if alloy_compositions else ["6061", "6063"]

            sample_profiles = ["PROFILE-A-001", "PROFILE-B-002", "PROFILE-C-003", "PROFILE-D-004", "PROFILE-E-005"]

            print("    Creating sample dies for demonstration...")
            created_dies = []

            for i, profile in enumerate(sample_profiles):
                # Create a die record
                new_die = Die(
                    id=str(uuid.uuid4()),
                    die_code=f"DIE-{202607}{i+1:05d}",
                    profile_code=profile,
                    alloy=alloys[i % len(alloys)],
                    status="AVAILABLE",
                    press_count=i * 100 + 500,
                    press_count_limit=5000,
                    created_at=datetime.utcnow() - timedelta(days=30),
                    updated_at=datetime.utcnow()
                )
                db.session.add(new_die)
                created_dies.append(new_die)

            db.session.commit()
            available_dies = created_dies
            print(f"    Created {len(created_dies)} sample dies")

        # Assign some dies to rack slots
        print("\n[3/4] Assigning dies to rack slots...")

        assignments_created = 0
        total_assignments_target = min(len(available_dies), len(created_racks) * 15)

        for i, die in enumerate(available_dies):
            if assignments_created >= total_assignments_target:
                break

            # Assign to a random rack (prefer available racks with capacity)
            rack = created_racks[i % len(created_racks)]

            # Find an empty slot
            existing_assignment = DieRackAssignment.query.filter_by(
                rack_id=rack.id,
                assignment_status="ASSIGNED"
            ).first()

            if not existing_assignment:
                continue  # Rack is full or has no slots yet

            available_slot = (existing_assignment.slot_number % rack.total_slots) + 1

            new_assignment = DieRackAssignment(
                id=str(uuid.uuid4()),
                rack_id=rack.id,
                slot_number=available_slot,
                die_code=die.die_code,
                die_id=die.id,
                profile_code=die.profile_code,
                alloy=die.alloy,
                assignment_status="ASSIGNED",
                assigned_by=operator_id,
                last_accessed_at=datetime.utcnow(),
                notes=f"Demo assignment - {i + 1}"
            )

            db.session.add(new_assignment)
            assignments_created += 1

            # Update rack available slots
            rack.available_slots -= 1
            if rack.available_slots == 0:
                rack.status = "IN_USE"

        db.session.commit()
        print(f"\n[OK] Created {assignments_created} die-to-rack assignments")

        # Create location index entries
        print("\n[4/4] Creating location index...")

        for assignment in DieRackAssignment.query.filter_by(assignment_status="ASSIGNED").all():
            location = DieLocationIndex(
                id=str(uuid.uuid4()),
                die_code=assignment.die_code,
                rack_id=assignment.rack_id,
                slot_number=assignment.slot_number,
                profile_code=assignment.profile_code,
                alloy=assignment.alloy,
                status="IN_STOCK",
                last_updated_at=datetime.utcnow()
            )

            db.session.add(location)

        # Create some sample transaction history
        print("\n[5/4] Generating transaction history...")

        days_ago = 30
        transactions_created = 0

        for day_offset in range(days_ago, -1, -2):
            trans_time = datetime.utcnow() - timedelta(days=day_offset)

            # Create some IN and OUT transactions
            for _ in range(5 + (day_offset % 10)):  # Vary transaction count per day
                assignment = DieRackAssignment.query.filter_by(assignment_status="ASSIGNED").first()
                if not assignment:
                    break

                trans_type = "IN" if assignments_created > 0 else "OUT"
                rack_id = assignment.rack_id if assignments_created > 0 else None

                new_trans = RackTransaction(
                    id=str(uuid.uuid4()),
                    transaction_type=trans_type,
                    rack_id=rack_id,
                    slot_number=assignment.slot_number if trans_type == "IN" else None,
                    die_code=assignment.die_code,
                    die_id=assignment.die_id,
                    profile_code=assignment.profile_code,
                    alloy=assignment.alloy,
                    operator_id=f"user_{(day_offset % 5) + 1}",
                    transaction_time=trans_time - timedelta(hours=(day_offset * 2)),
                    notes="Demo transaction" if day_offset > days_ago // 2 else None
                )

                db.session.add(new_trans)
                transactions_created += 1

        # Update rack statuses based on assignments
        for rack in created_racks:
            assignment_count = DieRackAssignment.query.filter_by(
                rack_id=rack.id,
                assignment_status="ASSIGNED"
            ).count()

            if assignment_count == rack.total_slots:
                rack.status = "IN_USE"
            elif assignment_count > 0 and rack.status == "MAINTENANCE":
                rack.status = "AVAILABLE"

        db.session.commit()
        print(f"\n[OK] Generated {transactions_created} transaction records")

        # Summary
        print("\n" + "=" * 60)
        print("Seed Data Summary")
        print("=" * 60)
        print(f"  Racks created:           {len(created_racks)}")
        print(f"  Die assignments:         {assignments_created}")
        print(f"  Transaction records:     {transactions_created}")
        print(f"  Sample dies available:   {len(available_dies)}")

        # Display rack overview
        print("\nRack Overview:")
        for rack in created_racks[:10]:  # Show first 10 racks
            filled = DieRackAssignment.query.filter_by(
                rack_id=rack.id,
                assignment_status="ASSIGNED"
            ).count()

            print(f"    {rack.rack_code}: {filled}/{rack.total_slots} slots ({rack.status})")

        if len(created_racks) > 10:
            print(f"    ... and {len(created_racks) - 10} more racks")

        print("\n[SUCCESS] Warehouse seed data completed!")


if __name__ == "__main__":
    try:
        seed_warehouse_data()
    except Exception as e:
        print(f"\n[ERROR] Failed to seed warehouse data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
