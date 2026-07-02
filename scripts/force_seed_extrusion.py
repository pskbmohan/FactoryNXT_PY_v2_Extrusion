#!/usr/bin/env python3
"""Force seed extrusion module data (finishing, logistics, cost price).

Use this script to populate seed data for extrusion modules that may have
been skipped during initial seeding (before the modules existed).
"""
import sys
from app import create_app, db

def main():
    app = create_app()
    with app.app_context():
        from app.models import FinishingProcessType, FinishingOrder
        from app.models import PackagingSpec, PackagingOrder, Shipment, ShipmentLine
        from app.models import CostPriceConfig
        from scripts.seed_data import (
            seed_finishing_module,
            seed_logistics_module,
            seed_cost_price_module,
        )

        print("=" * 70)
        print("Force-Seeding Extrusion Modules")
        print("=" * 70)

        # Finish Processes
        print("\n[Finishing Processes]")
        count_types = FinishingProcessType.query.count()
        count_orders = FinishingOrder.query.count()
        print(f"Current: {count_types} process types, {count_orders} orders")

        # Delete existing data
        FinishingOrder.query.delete()
        FinishingProcessType.query.delete()
        db.session.commit()
        print("Deleted existing data")

        # Re-seed
        seed_finishing_module()
        db.session.commit()

        print(f"After: {FinishingProcessType.query.count()} process types, {FinishingOrder.query.count()} orders")

        # Logistics and Packaging Queue
        print("\n[Logistics & Packaging Queue]")
        count_specs = PackagingSpec.query.count()
        count_orders = PackagingOrder.query.count()
        count_shipments = Shipment.query.count()
        count_lines = ShipmentLine.query.count()
        print(f"Current: {count_specs} specs, {count_orders} orders, {count_shipments} shipments, {count_lines} lines")

        # Delete existing data
        ShipmentLine.query.delete()
        Shipment.query.delete()
        PackagingOrder.query.delete()
        PackagingSpec.query.delete()
        db.session.commit()
        print("Deleted existing data")

        # Re-seed
        seed_logistics_module()
        db.session.commit()

        print(f"After: {PackagingSpec.query.count()} specs, {PackagingOrder.query.count()} orders")
        print(f"After: {Shipment.query.count()} shipments, {ShipmentLine.query.count()} lines")

        # Cost Price Calculator
        print("\n[Cost Price Calculator]")
        count_configs = CostPriceConfig.query.count()
        print(f"Current: {count_configs} configs")

        # Delete existing data
        CostPriceConfig.query.delete()
        db.session.commit()
        print("Deleted existing data")

        # Re-seed
        seed_cost_price_module()
        db.session.commit()

        print(f"After: {CostPriceConfig.query.count()} configs")

        print("\n" + "=" * 70)
        print("Force-seed complete!")
        print("=" * 70)


if __name__ == "__main__":
    main()
