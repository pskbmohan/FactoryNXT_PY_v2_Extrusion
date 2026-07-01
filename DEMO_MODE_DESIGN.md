# FactoryNXT Demo Mode Design

## Purpose
Transform the app into a demo-first experience where every screen shows only 2-3 key data points plus a presenter walkthrough.

## Demo Mode Toggle
- Pill button in topbar (before theme toggle) toggles `html.demo-mode` class
- Sets cookie `demo_mode=0|1` (30-day expiry, `SameSite=Lax`)
- When ON: detail sections hidden, focus hero displayed, presenter drawer visible

## Per-Screen Pattern
Every screen shows:
1. **Demo focus hero** (always visible) — 2-3 headline KPIs in bordered card
2. **Full detail** (`[data-demo-detail]`) — hidden in demo mode via CSS

## Presenter Drawer
- Fixed bottom-right drawer that appears in demo mode
- Walks through 8 screens in order: dashboard → planning → tool_shop → process_line → traceability → kpi_alerts → integrations → admin
- Each step has: title, talk track, "why this matters" block
- Prev/Next buttons navigate between screens

## Walkthrough Sequence
1. Dashboard - Plant OEE, Open Alerts, ERP Sync Health
2. Planning & Scheduling - Orders Imported, Schedule Risk shortges, On-Time %
3. Tool Shop - Available dies, In QC/Testing, Pending Nitriding
4. Process Line - Running stations (/ 9), Active Alerts, Setpoint Match %
5. Quality & Traceability - Batch Traced, Latest Inspection, Process History Runs
6. KPI & Alerts - Throughput, Rejection %, Critical Alerts
7. Integrations - ERP active, PLC active, Failed Jobs 24h
8. Administration - Active Users, Plants Configured, Alert Rules Active

## CSS Hook
```
html.demo-mode [data-demo-detail] { display: none !important; }
```
