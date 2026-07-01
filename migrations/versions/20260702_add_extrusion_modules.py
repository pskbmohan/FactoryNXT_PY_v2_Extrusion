"""Add extrusion modules - complete schema

Revision ID: 20260702_extrusion_modules
Revises: aps_add_notes_columns
Create Date: 2026-07-02

This migration adds all tables required for the 8 extrusion MES modules:
- Die management extensions (die_furnace_logs, die_repair_records)
- Cost price module (cost_price_configs)
- Material receipt module (raw_material_types, alloy_compositions, material_receipts)
- Coating schedule module (coating_colors, coating_schedule_entries)
- Container management (containers, container_weigh_events, container_movements)
- Furnace operations (furnaces, heat_treatment_programs, furnace_sessions)
- Finishing processes (finishing_process_types, finishing_orders)
- Logistics (packaging_specs, packaging_orders, shipments, shipment_lines)

Plus adds 11 missing columns to existing dies table.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260702_extrusion_modules'
down_revision = 'aps_add_notes_columns'
branch_labels = None
depends_on = None


def upgrade():
    # =========================================================================
    # 1. DIE TABLE EXTENSIONS - Add missing columns to existing dies table
    # =========================================================================
    op.add_column('dies', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('dies', sa.Column('die_type', sa.String(length=64), nullable=True))
    op.add_column('dies', sa.Column('manufacturer', sa.String(length=128), nullable=True))
    op.add_column('dies', sa.Column('manufactured_date', sa.Date(), nullable=True))
    op.add_column('dies', sa.Column('press_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('dies', sa.Column('press_count_limit', sa.Integer(), nullable=True))
    op.add_column('dies', sa.Column('repair_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('dies', sa.Column('nitriding_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('dies', sa.Column('last_used_at', sa.DateTime(), nullable=True))
    op.add_column('dies', sa.Column('last_repaired_at', sa.DateTime(), nullable=True))
    op.add_column('dies', sa.Column('updated_at', sa.DateTime(), nullable=True))

    # =========================================================================
    # 2. DIE FURNACE AND REPAIR LOGS
    # =========================================================================
    op.create_table(
        'die_furnace_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('die_id', sa.String(length=36), nullable=False),
        sa.Column('furnace_id', sa.String(length=36), nullable=True),
        sa.Column('target_temp_celsius', sa.Float(), nullable=True),
        sa.Column('actual_temp_celsius', sa.Float(), nullable=True),
        sa.Column('soak_time_minutes', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='heating'),
        sa.Column('operator_id', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['die_id'], ['dies.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'die_repair_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('die_id', sa.String(length=36), nullable=False),
        sa.Column('repair_type', sa.String(length=32), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('performed_by', sa.String(length=64), nullable=True),
        sa.Column('performed_at', sa.DateTime(), nullable=False),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['die_id'], ['dies.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # =========================================================================
    # 3. COST PRICE MODULE
    # =========================================================================
    op.create_table(
        'cost_price_configs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('part_number', sa.String(length=64), nullable=False),
        sa.Column('revision', sa.String(length=8), server_default='A'),
        sa.Column('raw_material_cost_per_kg', sa.Float(), server_default='0'),
        sa.Column('material_weight_kg', sa.Float(), server_default='0'),
        sa.Column('machine_rate_per_hour', sa.Float(), server_default='0'),
        sa.Column('cycle_time_hours', sa.Float(), server_default='0'),
        sa.Column('labor_rate_per_hour', sa.Float(), server_default='0'),
        sa.Column('labor_hours', sa.Float(), server_default='0'),
        sa.Column('energy_kwh', sa.Float(), server_default='0'),
        sa.Column('energy_rate_per_kwh', sa.Float(), server_default='0'),
        sa.Column('overhead_percent', sa.Float(), server_default='10'),
        sa.Column('margin_percent', sa.Float(), server_default='15'),
        sa.Column('calculated_cost', sa.Float(), nullable=True),
        sa.Column('break_even_price', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=8), server_default='USD'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )

    # =========================================================================
    # 4. MATERIAL RECEIPT MODULE
    # =========================================================================
    op.create_table(
        'raw_material_types',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=True),
        sa.Column('uom', sa.String(length=16), server_default='KG'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )

    op.create_table(
        'alloy_compositions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('alloy_code', sa.String(length=64), nullable=False),
        sa.Column('alloy_name', sa.String(length=128), nullable=False),
        sa.Column('composition', sa.JSON(), server_default='{}'),
        sa.Column('standard', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('alloy_code')
    )

    op.create_table(
        'material_receipts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('receipt_number', sa.String(length=64), nullable=False),
        sa.Column('supplier_name', sa.String(length=128), nullable=True),
        sa.Column('truck_reference', sa.String(length=64), nullable=True),
        sa.Column('material_type_id', sa.String(length=36), nullable=True),
        sa.Column('alloy_code', sa.String(length=64), nullable=True),
        sa.Column('lot_number', sa.String(length=64), nullable=False),
        sa.Column('quantity_received', sa.Float(), nullable=False),
        sa.Column('quantity_available', sa.Float(), nullable=True),
        sa.Column('uom', sa.String(length=16), server_default='KG'),
        sa.Column('actual_composition', sa.JSON(), server_default='{}'),
        sa.Column('composition_status', sa.String(length=16), server_default='PENDING'),
        sa.Column('received_by', sa.String(length=64), nullable=True),
        sa.Column('received_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('location_id', sa.String(length=36), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['material_type_id'], ['raw_material_types.id']),
        sa.ForeignKeyConstraint(['alloy_code'], ['alloy_compositions.alloy_code']),
        sa.ForeignKeyConstraint(['location_id'], ['inventory_locations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('receipt_number')
    )

    # =========================================================================
    # 5. COATING SCHEDULE MODULE
    # =========================================================================
    op.create_table(
        'coating_colors',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('color_code', sa.String(length=64), nullable=False),
        sa.Column('color_name', sa.String(length=128), nullable=False),
        sa.Column('hex_value', sa.String(length=7), nullable=True),
        sa.Column('ral_code', sa.String(length=32), nullable=True),
        sa.Column('clean_time_minutes', sa.Integer(), server_default='30'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('color_code')
    )

    op.create_table(
        'coating_schedule_entries',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('wo_id', sa.String(length=36), nullable=False),
        sa.Column('coating_line_id', sa.String(length=64), nullable=True),
        sa.Column('color_id', sa.String(length=36), nullable=True),
        sa.Column('color_group_sequence', sa.Integer(), nullable=True),
        sa.Column('scheduled_start', sa.DateTime(), nullable=True),
        sa.Column('scheduled_end', sa.DateTime(), nullable=True),
        sa.Column('actual_start', sa.DateTime(), nullable=True),
        sa.Column('actual_end', sa.DateTime(), nullable=True),
        sa.Column('powder_quantity_kg', sa.Float(), nullable=True),
        sa.Column('actual_powder_used_kg', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='planned'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['wo_id'], ['work_orders.id']),
        sa.ForeignKeyConstraint(['color_id'], ['coating_colors.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # =========================================================================
    # 6. CONTAINER MANAGEMENT MODULE
    # =========================================================================
    op.create_table(
        'containers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('container_code', sa.String(length=64), nullable=False),
        sa.Column('container_type', sa.String(length=64), nullable=True),
        sa.Column('tare_weight_kg', sa.Float(), nullable=True),
        sa.Column('max_capacity_kg', sa.Float(), nullable=True),
        sa.Column('max_capacity_units', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='available'),
        sa.Column('current_location', sa.String(length=128), nullable=True),
        sa.Column('current_wo_id', sa.String(length=36), nullable=True),
        sa.Column('material', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['current_wo_id'], ['work_orders.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('container_code')
    )

    op.create_table(
        'container_weigh_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('container_id', sa.String(length=36), nullable=False),
        sa.Column('wo_id', sa.String(length=36), nullable=True),
        sa.Column('gross_weight_kg', sa.Float(), nullable=False),
        sa.Column('tare_weight_kg', sa.Float(), nullable=False),
        sa.Column('net_weight_kg', sa.Float(), nullable=True),
        sa.Column('expected_weight_kg', sa.Float(), nullable=True),
        sa.Column('weight_variance_percent', sa.Float(), nullable=True),
        sa.Column('weigh_station', sa.String(length=64), nullable=True),
        sa.Column('operator_id', sa.String(length=64), nullable=True),
        sa.Column('weighed_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('status', sa.String(length=16), server_default='OK'),
        sa.ForeignKeyConstraint(['container_id'], ['containers.id']),
        sa.ForeignKeyConstraint(['wo_id'], ['work_orders.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'container_movements',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('container_id', sa.String(length=36), nullable=False),
        sa.Column('from_location', sa.String(length=128), nullable=True),
        sa.Column('to_location', sa.String(length=128), nullable=False),
        sa.Column('moved_by', sa.String(length=64), nullable=True),
        sa.Column('moved_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('wo_id', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['container_id'], ['containers.id']),
        sa.ForeignKeyConstraint(['wo_id'], ['work_orders.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # =========================================================================
    # 7. FURNACE OPERATIONS MODULE
    # =========================================================================
    op.create_table(
        'furnaces',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('furnace_code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('furnace_type', sa.String(length=64), nullable=True),
        sa.Column('max_temp_celsius', sa.Float(), nullable=True),
        sa.Column('capacity_kg', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='idle'),
        sa.Column('current_program_id', sa.String(length=36), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('furnace_code')
    )

    op.create_table(
        'heat_treatment_programs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('program_code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('alloy_code', sa.String(length=64), nullable=True),
        sa.Column('temper_designation', sa.String(length=16), nullable=True),
        sa.Column('stages', sa.JSON(), server_default='[]'),
        sa.Column('total_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('program_code')
    )

    op.create_table(
        'furnace_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('furnace_id', sa.String(length=36), nullable=False),
        sa.Column('program_id', sa.String(length=36), nullable=False),
        sa.Column('wo_id', sa.String(length=36), nullable=True),
        sa.Column('batch_reference', sa.String(length=64), nullable=True),
        sa.Column('loaded_containers', sa.JSON(), server_default='[]'),
        sa.Column('total_load_kg', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='queued'),
        sa.Column('current_stage_index', sa.Integer(), server_default='0'),
        sa.Column('current_temp_celsius', sa.Float(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('operator_id', sa.String(length=64), nullable=True),
        sa.Column('temperature_log', sa.JSON(), server_default='[]'),
        sa.Column('result', sa.String(length=16), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['furnace_id'], ['furnaces.id']),
        sa.ForeignKeyConstraint(['program_id'], ['heat_treatment_programs.id']),
        sa.ForeignKeyConstraint(['wo_id'], ['work_orders.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # =========================================================================
    # 8. FINISHING PROCESSES MODULE
    # =========================================================================
    op.create_table(
        'finishing_process_types',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('requires_plc_instruction', sa.Boolean(), server_default='false'),
        sa.Column('default_parameters', sa.JSON(), server_default='{}'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )

    op.create_table(
        'finishing_orders',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('order_number', sa.String(length=64), nullable=False),
        sa.Column('wo_id', sa.String(length=36), nullable=False),
        sa.Column('process_type_id', sa.String(length=36), nullable=False),
        sa.Column('container_id', sa.String(length=36), nullable=True),
        sa.Column('sequence', sa.Integer(), server_default='1'),
        sa.Column('status', sa.String(length=32), server_default='pending'),
        sa.Column('parameters', sa.JSON(), server_default='{}'),
        sa.Column('plc_command', sa.JSON(), nullable=True),
        sa.Column('plc_ack_status', sa.String(length=16), nullable=True),
        sa.Column('operator_id', sa.String(length=64), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['wo_id'], ['work_orders.id']),
        sa.ForeignKeyConstraint(['process_type_id'], ['finishing_process_types.id']),
        sa.ForeignKeyConstraint(['container_id'], ['containers.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_number')
    )

    # =========================================================================
    # 9. LOGISTICS MODULE
    # =========================================================================
    op.create_table(
        'packaging_specs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('part_number', sa.String(length=64), nullable=False),
        sa.Column('packing_method', sa.String(length=128), nullable=True),
        sa.Column('units_per_pack', sa.Integer(), nullable=True),
        sa.Column('theoretical_weight_per_pack_kg', sa.Float(), nullable=True),
        sa.Column('label_template', sa.String(length=256), nullable=True),
        sa.Column('special_instructions', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'packaging_orders',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('wo_id', sa.String(length=36), nullable=False),
        sa.Column('packaging_spec_id', sa.String(length=36), nullable=True),
        sa.Column('pack_number', sa.String(length=64), nullable=False),
        sa.Column('barcode', sa.String(length=128), nullable=True),
        sa.Column('quantity_packed', sa.Integer(), nullable=True),
        sa.Column('actual_weight_kg', sa.Float(), nullable=True),
        sa.Column('theoretical_weight_kg', sa.Float(), nullable=True),
        sa.Column('weight_variance_percent', sa.Float(), nullable=True),
        sa.Column('label_printed', sa.Boolean(), server_default='false'),
        sa.Column('status', sa.String(length=32), server_default='pending'),
        sa.Column('packed_by', sa.String(length=64), nullable=True),
        sa.Column('packed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['wo_id'], ['work_orders.id']),
        sa.ForeignKeyConstraint(['packaging_spec_id'], ['packaging_specs.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pack_number'),
        sa.UniqueConstraint('barcode')
    )

    op.create_table(
        'shipments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('shipment_number', sa.String(length=64), nullable=False),
        sa.Column('customer_name', sa.String(length=128), nullable=True),
        sa.Column('delivery_address', sa.Text(), nullable=True),
        sa.Column('carrier', sa.String(length=128), nullable=True),
        sa.Column('truck_reference', sa.String(length=64), nullable=True),
        sa.Column('scheduled_ship_date', sa.Date(), nullable=True),
        sa.Column('actual_ship_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='open'),
        sa.Column('theoretical_total_weight_kg', sa.Float(), nullable=True),
        sa.Column('actual_total_weight_kg', sa.Float(), nullable=True),
        sa.Column('weight_check_status', sa.String(length=16), nullable=True),
        sa.Column('weight_check_variance_percent', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('shipment_number')
    )

    op.create_table(
        'shipment_lines',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('shipment_id', sa.String(length=36), nullable=False),
        sa.Column('packaging_order_id', sa.String(length=36), nullable=False),
        sa.Column('wo_id', sa.String(length=36), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('scanned_at', sa.DateTime(), nullable=True),
        sa.Column('scanned_by', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id']),
        sa.ForeignKeyConstraint(['packaging_order_id'], ['packaging_orders.id']),
        sa.ForeignKeyConstraint(['wo_id'], ['work_orders.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    # Drop tables in reverse order of creation
    op.drop_table('shipment_lines')
    op.drop_table('shipments')
    op.drop_table('packaging_orders')
    op.drop_table('packaging_specs')

    op.drop_table('finishing_orders')
    op.drop_table('finishing_process_types')

    op.drop_table('furnace_sessions')
    op.drop_table('heat_treatment_programs')
    op.drop_table('furnaces')

    op.drop_table('container_movements')
    op.drop_table('container_weigh_events')
    op.drop_table('containers')

    op.drop_table('coating_schedule_entries')
    op.drop_table('coating_colors')

    op.drop_table('material_receipts')
    op.drop_table('alloy_compositions')
    op.drop_table('raw_material_types')

    op.drop_table('cost_price_configs')

    op.drop_table('die_repair_records')
    op.drop_table('die_furnace_logs')

    # Drop columns from dies table
    op.drop_column('dies', 'updated_at')
    op.drop_column('dies', 'last_repaired_at')
    op.drop_column('dies', 'last_used_at')
    op.drop_column('dies', 'nitriding_count')
    op.drop_column('dies', 'repair_count')
    op.drop_column('dies', 'press_count_limit')
    op.drop_column('dies', 'press_count')
    op.drop_column('dies', 'manufactured_date')
    op.drop_column('dies', 'manufacturer')
    op.drop_column('dies', 'die_type')
    op.drop_column('dies', 'description')
