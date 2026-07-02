from app import create_app, db
from app.models import Machine, OeeSnapshot, DowntimeEvent
from datetime import datetime, timedelta
import uuid

app = create_app()

with app.app_context():
    # Test OEE page rendering
    print("=== Testing OEE Route ===")
    try:
        machines = Machine.query.limit(2).all()
        print(f"Found {len(machines)} machines")
        
        for machine in machines:
            oee_records = OeeSnapshot.query.filter_by(machine_id=machine.id).order_by(
                OeeSnapshot.ts.desc()
            ).limit(1).all()
            print(f"Machine {machine.id}: {len(oee_records)} OEE records")
        
        # Try to render template
        from flask import render_template
        rows = []
        for machine in machines:
            oee_records = OeeSnapshot.query.filter_by(machine_id=machine.id).order_by(
                OeeSnapshot.ts.desc()
            ).limit(1).all()
            if oee_records:
                latest = oee_records[0]
                rows.append({
                    "machine_id": machine.id,
                    "machine_name": machine.name,
                    "availability": round((latest.availability or 0) * 100, 1),
                    "performance": round((latest.performance or 0) * 100, 1),
                    "quality": round((latest.quality or 0) * 100, 1),
                    "oee": round((latest.availability or 0) * (latest.performance or 0) * (latest.quality or 0) * 10000, 1),
                })
        
        with app.test_request_context():
            html = render_template("kpi_alerts/oee.html", rows=rows, machines=machines)
            print(f"✓ OEE template rendered ({len(html)} bytes)")
    except Exception as e:
        print(f"✗ OEE error: {type(e).__name__}: {e}")
    
    # Test Downtime page rendering
    print("\n=== Testing Downtime Route ===")
    try:
        events = DowntimeEvent.query.limit(3).all()
        print(f"Found {len(events)} downtime events")
        
        if events:
            ev = events[0]
            print(f"Event attributes: reason_code={ev.reason_code}, reason_category={ev.reason_category}")
            print(f"Has 'reason' attr? {hasattr(ev, 'reason')}")
            print(f"Has 'resolved_at' attr? {hasattr(ev, 'resolved_at')}")
            print(f"Has 'resolved_by' attr? {hasattr(ev, 'resolved_by')}")
            print(f"Has 'machine_name' attr? {hasattr(ev, 'machine_name')}")
            
            # Try to access the problematic attributes
            try:
                _ = ev.reason
                print("✓ ev.reason accessible")
            except AttributeError as e:
                print(f"✗ ev.reason: {e}")
            
            try:
                _ = ev.resolved_at
                print("✓ ev.resolved_at accessible")
            except AttributeError as e:
                print(f"✗ ev.resolved_at: {e}")
            
            try:
                _ = ev.resolved_by
                print("✓ ev.resolved_by accessible")
            except AttributeError as e:
                print(f"✗ ev.resolved_by: {e}")
            
            try:
                _ = ev.machine_name
                print("✓ ev.machine_name accessible")
            except AttributeError as e:
                print(f"✗ ev.machine_name: {e}")
                
    except Exception as e:
        print(f"✗ Downtime error: {type(e).__name__}: {e}")

