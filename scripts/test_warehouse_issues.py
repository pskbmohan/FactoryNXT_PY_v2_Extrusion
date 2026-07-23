#!/usr/bin/env python3
"""
Test script to verify warehouse module fixes
"""
import sys
import os
import json

sys.path.insert(0, '/Users/pskbmohan/Documents/GitHub/FactoryNXT_PY_v2_Extrusion')

from app import create_app
from app.models import db, ToolRoomRack, DieRackAssignment, DieLocationIndex

def test_warehouse():
    app = create_app()
    app.config['TESTING'] = True
    app.config['DEBUG'] = False

    with app.test_client() as client:
        print("=" * 70)
        print("TESTING WAREHOUSE MODULE FIXES")
        print("=" * 70)
        print()

        # Initialize test data if needed
        with app.app_context():
            db.create_all()

            # Create test rack if none exists
            if ToolRoomRack.query.count() == 0:
                print("Creating test data...")
                rack = ToolRoomRack(
                    rack_code='TEST-001',
                    rack_name='Test Rack',
                    rack_type='STORAGE_RACK',
                    location_zone='ZONE_A',
                    total_slots=20,
                    available_slots=15,
                    status='AVAILABLE'
                )
                db.session.add(rack)
                db.session.commit()

                # Create some die assignments
                for i in range(1, 6):
                    assignment = DieRackAssignment(
                        rack_id=rack.id,
                        slot_number=i,
                        die_code=f'DIE-{i:03d}',
                        profile_code=f'PROF-{i}',
                        alloy=f'ALLOY-{i}',
                        assignment_status='ASSIGNED'
                    )
                    db.session.add(assignment)

                db.session.commit()
                print(f"✓ Created test rack: {rack.rack_code} with 5 dies")
                print()

        # Test 1: Dashboard modal (API endpoint)
        print("TEST 1: Dashboard Modal - Rack Details API")
        print("-" * 70)
        with app.app_context():
            rack = ToolRoomRack.query.first()
            if rack:
                resp = client.get(f'/warehouse/api/racks/{rack.id}')
                print(f"GET /warehouse/api/racks/{rack.id}")
                print(f"Status: {resp.status_code}")

                if resp.status_code == 200:
                    data = resp.get_json()
                    print(f"Success: {data.get('success')}")
                    if data.get('success') and 'rack' in data:
                        rack_data = data['rack']
                        slots = rack_data.get('slots', [])
                        print(f"Slots in response: {len(slots)}")
                        if slots:
                            print("✓ PASS: Slots are included in rack data")
                            print(f"  First slot: {slots[0]}")
                        else:
                            print("✗ FAIL: No slots in response")
                    else:
                        print("✗ FAIL: Unexpected response structure")
                else:
                    print(f"✗ FAIL: HTTP {resp.status_code}")
            else:
                print("✗ SKIP: No racks in database")
        print()

        # Test 2: Racks management view
        print("TEST 2: Racks Management View")
        print("-" * 70)
        resp = client.get('/warehouse/racks')
        print(f"GET /warehouse/racks")
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            html = resp.get_data(as_text=True)
            if 'TEST-001' in html or 'rack-row' in html:
                print("✓ PASS: Racks page renders with data")
                print(f"  Page size: {len(html)} bytes")
            else:
                print("✗ FAIL: Page doesn't contain expected content")
        else:
            print(f"✗ FAIL: HTTP {resp.status_code}")
        print()

        # Test 3: Die search
        print("TEST 3: Die Search")
        print("-" * 70)
        resp = client.get('/warehouse/search')
        print(f"GET /warehouse/search")
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            print("✓ PASS: Search page loads without error")
            html = resp.get_data(as_text=True)
            if 'Search for dies' in html or 'search-form' in html:
                print("  Search form present")
        else:
            print(f"✗ FAIL: HTTP {resp.status_code}")
            if resp.status_code == 500:
                print("  Internal Server Error - check Flask logs")

        # Test search with query
        print()
        resp = client.get('/warehouse/search?q=DIE')
        print(f"GET /warehouse/search?q=DIE")
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            html = resp.get_data(as_text=True)
            if 'Search Results' in html or 'DIE' in html:
                print("✓ PASS: Search with query works")
                if 'die(s) found' in html:
                    print("  Result count displayed")
            else:
                print("? UNCLEAR: Page loads but may not show results")
        else:
            print(f"✗ FAIL: HTTP {resp.status_code}")
        print()

        # Test API endpoints
        print("TEST 4: API Endpoints")
        print("-" * 70)

        with app.app_context():
            rack = ToolRoomRack.query.first()
            if rack:
                resp = client.get(f'/warehouse/api/racks/{rack.id}')
                print(f"GET /api/racks/{rack.id[:8]}...")
                print(f"Status: {resp.status_code}")

                if resp.status_code == 200:
                    data = resp.get_json()
                    rack_info = data.get('rack', {})
                    slots = rack_info.get('slots', [])
                    print(f"Rack: {rack_info.get('rack_code')}")
                    print(f"Total slots: {rack_info.get('total_slots')}")
                    print(f"Assigned slots: {len(slots)}")

                    if len(slots) > 0:
                        print("✓ PASS: API returns slot data")
                        print("  Sample slot:")
                        print(f"    Slot {slots[0]['slot_number']}: {slots[0]['die_code']}")
                    else:
                        print("✗ FAIL: No slots returned")
                else:
                    print(f"✗ FAIL: HTTP {resp.status_code}")
        print()

        print("=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print()
        print("All critical endpoints tested.")
        print("Check results above for PASS/FAIL status.")
        print()
        print("If all tests pass, the fixes are working correctly.")
        print("If any test fails, check Flask logs for detailed errors.")
        print()

if __name__ == '__main__':
    test_warehouse()
