"""Seed Script - Quality Defect Codes Master Data

This script populates the defect_codes table with default defect types
for immediate use after database migration.

Usage:
    python3 seed_quality_defect_codes.py

Note: Requires running within a Flask app context and database connection.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from app import create_app, db
from app.models import DefectCode


def get_default_defect_codes():
    """Return list of default defect codes with categories and severity."""
    return [
        # Surface defects (DS)
        {
            'code': 'DS001',
            'name': 'Surface Scratches',
            'category': 'surface',
            'severity': 'minor',
            'description': 'Minor surface scratches from handling or equipment contact'
        },
        {
            'code': 'DS002',
            'name': 'Die Lines',
            'category': 'surface',
            'severity': 'moderate',
            'description': 'Longitudinal lines caused by die wear or contamination'
        },
        {
            'code': 'DS003',
            'name': 'Surface Roughness',
            'category': 'surface',
            'severity': 'moderate',
            'description': 'Excessive surface roughness beyond tolerance limits'
        },
        {
            'code': 'DS004',
            'name': 'Burn Marks',
            'category': 'surface',
            'severity': 'major',
            'description': 'Discoloration or burning from excessive friction/temperature'
        },
        # Dimensional defects (DW)
        {
            'code': 'DW001',
            'name': 'Dimensional Out of Tolerance - OD',
            'category': 'dimensional',
            'severity': 'major',
            'description': 'Outer diameter outside specified tolerance range'
        },
        {
            'code': 'DW002',
            'name': 'Dimensional Out of Tolerance - ID',
            'category': 'dimensional',
            'severity': 'major',
            'description': 'Inner diameter outside specified tolerance range'
        },
        {
            'code': 'DW003',
            'name': 'Straightness Deviation',
            'category': 'dimensional',
            'severity': 'moderate',
            'description': 'Profile straightness beyond allowable bend per meter'
        },
        {
            'code': 'DW004',
            'name': 'Length Variation',
            'category': 'dimensional',
            'severity': 'minor',
            'description': 'Cut length outside acceptable tolerance band'
        },
        # Functional defects (FW)
        {
            'code': 'FW001',
            'name': 'Incomplete Fill',
            'category': 'functional',
            'severity': 'critical',
            'description': 'Profile not fully formed - missing section details'
        },
        {
            'code': 'FW002',
            'name': 'Internal Voids',
            'category': 'functional',
            'severity': 'critical',
            'description': 'Air pockets or voids detected in solid sections'
        },
        {
            'code': 'FW003',
            'name': 'Hardness Below Minimum',
            'category': 'functional',
            'severity': 'major',
            'description': 'Material hardness below specified minimum requirement'
        },
        {
            'code': 'FW004',
            'name': 'Extrusion Speed Variation',
            'category': 'functional',
            'severity': 'moderate',
            'description': 'Inconsistent extrusion speed affecting product quality'
        },
        # Aesthetic defects (AW)
        {
            'code': 'AW001',
            'name': 'Color Variation',
            'category': 'aesthetic',
            'severity': 'minor',
            'description': 'Visible color difference from standard/reference sample'
        },
        {
            'code': 'AW002',
            'name': 'Visual Surface Defects',
            'category': 'aesthetic',
            'severity': 'moderate',
            'description': 'Pits, inclusions, or other visual imperfections'
        },
        {
            'code': 'AW003',
            'name': 'Handling Marks',
            'category': 'aesthetic',
            'severity': 'minor',
            'description': 'Marks from handling equipment or manual contact'
        },
    ]


def seed_defect_codes():
    """Seed the defect_codes table with default values."""
    app = create_app()

    with app.app_context():
        # Check if any defect codes already exist
        existing_count = DefectCode.query.count()

        if existing_count > 0:
            print(f"WARNING: {existing_count} defect code(s) already exist in database.")
            print("Skipping seed - remove data manually to re-seed.")
            return

        default_codes = get_default_defect_codes()

        inserted = 0
        for code_data in default_codes:
            # Check if this specific code already exists
            existing = DefectCode.query.filter_by(code=code_data['code']).first()
            if existing:
                print(f"  Skipping {code_data['code']} - already exists")
                continue

            defect = DefectCode(
                code=code_data['code'],
                name=code_data['name'],
                category=code_data['category'],
                severity=code_data['severity'],
                description=code_data['description'],
                is_active=True,
                created_at=db.func.now()
            )

            try:
                db.session.add(defect)
                inserted += 1
                print(f"  Added: {code_data['code']} - {code_data['name']}")
            except Exception as e:
                print(f"  ERROR adding {code_data['code']}: {e}")

        if inserted > 0:
            db.session.commit()
            print(f"\nSuccessfully seeded {inserted} defect codes.")
        else:
            print("\nNo new defect codes were added.")


if __name__ == '__main__':
    print("=" * 60)
    print("Quality Defect Codes Seeder")
    print("=" * 60)
    seed_defect_codes()
