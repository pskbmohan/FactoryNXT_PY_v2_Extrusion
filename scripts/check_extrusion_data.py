#!/usr/bin/env python3
"""Check and optionally force-seed extrusion modules."""
import sys
from app import create_app, db
from scripts import seed_data

app = create_app()
with app.app_context():
    force_seed = "--force" in sys.argv

    print("=" * 60)
    print("Extrusion Seed Data Management")
    print("=" * 60)

    # Check Finishing module
    try:
        from app.models import FinishingProcessType, FinishingOrder
        proc_count = FinishingProcessType.query.count()
        order_count = FinishingOrder.query.count()
        print(f"\n🎨 Finishing Processes:")
        print(f"  Process Types: {proc_count}")
        print(f"  Finishing Orders: {order_count}")
        if proc_count == 0 or force_seed:
            print("  🔄 Seeding...")
            FinishingProcessType.query.delete()
            FinishingOrder.query.delete()
            db.session.commit()
            seed_data.seed_finishing_module()
            db.session.commit()
            print(f"  ✅ Seeded: {FinishingProcessType.query.count()} process types, {FinishingOrder.query.count()} orders")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    # Check Packaging/Logistics module
    try:
        from app.models import PackagingSpec, PackagingOrder, Shipment, ShipmentLine
        spec_count = PackagingSpec.query.count()
        pkg_count = PackagingOrder.query.count()
        ship_count = Shipment.query.count()
        line_count = ShipmentLine.query.count()
        print(f"\n📦 Logistics/Packaging:")
        print(f"  Packaging Specs: {spec_count}")
        print(f"  Packaging Orders: {pkg_count}")
        print(f"  Shipments: {ship_count}")
        print(f"  Shipment Lines: {line_count}")
        if spec_count == 0 or force_seed:
            print("  🔄 Seeding...")
            PackagingSpec.query.delete()
            PackagingOrder.query.delete()
            Shipment.query.delete()
            ShipmentLine.query.delete()
            db.session.commit()
            seed_data.seed_logistics_module()
            db.session.commit()
            print(f"  ✅ Seeded: {PackagingSpec.query.count()} specs, {PackagingOrder.query.count()} orders")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    # Check Cost Price module
    try:
        from app.models import CostPriceConfig
        cost_count = CostPriceConfig.query.count()
        print(f"\n💰 Cost Price Calculator:")
        print(f"  Configurations: {cost_count}")
        if cost_count == 0 or force_seed:
            print("  🔄 Seeding...")
            CostPriceConfig.query.delete()
            db.session.commit()
            seed_data.seed_cost_price_module()
            db.session.commit()
            print(f"  ✅ Seeded: {CostPriceConfig.query.count()} configurations")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    # Check Material Receipt module
    try:
        from app.models import RawMaterialType, AlloyComposition, MaterialReceipt
        mat_count = RawMaterialType.query.count()
        alloy_count = AlloyComposition.query.count()
        receipt_count = MaterialReceipt.query.count()
        print(f"\n📋 Material Receipt:")
        print(f"  Raw Material Types: {mat_count}")
        print(f"  Alloy Compositions: {alloy_count}")
        print(f"  Material Receipts: {receipt_count}")
        if mat_count == 0 or force_seed:
            print("  🔄 Seeding...")
            RawMaterialType.query.delete()
            AlloyComposition.query.delete()
            MaterialReceipt.query.delete()
            db.session.commit()
            seed_data.seed_material_receipt_module()
            db.session.commit()
            print(f"  ✅ Seeded: {RawMaterialType.query.count()} material types, {MaterialReceipt.query.count()} receipts")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    # Check Coating Schedule module
    try:
        from app.models import CoatingColor, CoatingScheduleEntry
        color_count = CoatingColor.query.count()
        entry_count = CoatingScheduleEntry.query.count()
        print(f"\n🎨 Coating Schedule:")
        print(f"  Colors: {color_count}")
        print(f"  Schedule Entries: {entry_count}")
        if color_count == 0 or force_seed:
            print("  🔄 Seeding...")
            CoatingColor.query.delete()
            CoatingScheduleEntry.query.delete()
            db.session.commit()
            seed_data.seed_coating_schedule_module()
            db.session.commit()
            print(f"  ✅ Seeded: {CoatingColor.query.count()} colors, {CoatingScheduleEntry.query.count()} entries")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    # Check Container module
    try:
        from app.models import Container, ContainerWeighEvent, ContainerMovement
        container_count = Container.query.count()
        weigh_count = ContainerWeighEvent.query.count()
        move_count = ContainerMovement.query.count()
        print(f"\n📦 Containers:")
        print(f"  Containers: {container_count}")
        print(f"  Weigh Events: {weigh_count}")
        print(f"  Movements: {move_count}")
        if container_count == 0 or force_seed:
            print("  🔄 Seeding...")
            Container.query.delete()
            ContainerWeighEvent.query.delete()
            ContainerMovement.query.delete()
            db.session.commit()
            seed_data.seed_containers_module()
            db.session.commit()
            print(f"  ✅ Seeded: {Container.query.count()} containers, {ContainerWeighEvent.query.count()} weigh events")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    # Check Furnace module
    try:
        from app.models import Furnace, HeatTreatmentProgram, FurnaceSession
        furnace_count = Furnace.query.count()
        program_count = HeatTreatmentProgram.query.count()
        session_count = FurnaceSession.query.count()
        print(f"\n🔥 Furnace Operations:")
        print(f"  Furnaces: {furnace_count}")
        print(f"  Heat Treatment Programs: {program_count}")
        print(f"  Furnace Sessions: {session_count}")
        if furnace_count == 0 or force_seed:
            print("  🔄 Seeding...")
            Furnace.query.delete()
            HeatTreatmentProgram.query.delete()
            FurnaceSession.query.delete()
            db.session.commit()
            seed_data.seed_furnace_module()
            db.session.commit()
            print(f"  ✅ Seeded: {Furnace.query.count()} furnaces, {FurnaceSession.query.count()} sessions")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    # Check Die Lifecycle Extended
    try:
        from app.models import DieFurnaceLog, DieRepairRecord
        furnace_log_count = DieFurnaceLog.query.count()
        repair_count = DieRepairRecord.query.count()
        print(f"\n🔧 Die Lifecycle Extended:")
        print(f"  Die Furnace Logs: {furnace_log_count}")
        print(f"  Die Repair Records: {repair_count}")
        if furnace_log_count == 0 or force_seed:
            print("  🔄 Seeding...")
            DieFurnaceLog.query.delete()
            DieRepairRecord.query.delete()
            db.session.commit()
            seed_data.seed_die_lifecycle_extended()
            db.session.commit()
            print(f"  ✅ Seeded: {DieFurnaceLog.query.count()} furnace logs, {DieRepairRecord.query.count()} repair records")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    print("\n" + "=" * 60)
    print("✅ All extrusion modules seeded successfully!")
    print("=" * 60)
