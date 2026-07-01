"""Schedule optimizer service.

Implements a simple greedy algorithm that respects die availability,
billet availability, and machine availability. This is a placeholder
implementation; a production system would use a constraint solver
(e.g., OR-Tools, Gurobi) or a more sophisticated heuristic.

Input: constraint_inputs = {
    "orders": [...],          # list of CustomerOrder dicts
    "available_dies": [...],  # list of Die dicts with status='Available'
    "available_billets": [...], # list of Billet dicts with status='AVAILABLE'
    "available_machines": [...], # list of Machine dicts with status='Available'
    "horizon_days": 7,        # planning horizon
}

Output: {
    "plans": [...],           # list of ProcessPlan dicts
    "unassigned_orders": [...], # orders that couldn't be scheduled
    "shortages": {...},        # projected die/billet shortages
}
"""

from datetime import datetime, timedelta
from .. import db
from ..models import CustomerOrder, Die, Billet, Machine, ProcessPlan


class ScheduleOptimizer:
    """Greedy scheduler for aluminum extrusion orders."""

    @classmethod
    def optimize(cls, constraint_inputs):
        """
        Run the optimizer.

        Algorithm:
        1. Sort orders by due_date (earliest first), then priority.
        2. For each order, try to assign a die+billet+machine that are
           available and match the alloy/profile requirements.
        3. If assignment succeeds, create a ProcessPlan row.
        4. Track which dies/billets/machines are now occupied.

        Returns a dict with the list of plans created and any unassigned
        orders that couldn't be scheduled.
        """
        orders = constraint_inputs.get("orders", [])
        available_dies = constraint_inputs.get("available_dies", [])
        available_billets = constraint_inputs.get("available_billets", [])
        available_machines = constraint_inputs.get("available_machines", [])
        horizon_days = constraint_inputs.get("horizon_days", 7)

        # Sort orders by due_date ASC, then priority DESC (urgent first)
        sorted_orders = sorted(
            orders,
            key=lambda o: (
                o.get("due_date") or datetime.utcnow().date(),
                -1 * (1 if o.get("priority") == "urgent" else 0),
            ),
        )

        plans = []
        unassigned = []
        used_dies = set()
        used_billets = set()
        used_machines = set()
        used_time_slots = []  # list of (machine_id, start, end)

        horizon_start = datetime.utcnow()
        horizon_end = horizon_start + timedelta(days=horizon_days)

        for order in sorted_orders:
            order_id = order.get("id")
            alloy = order.get("alloy")
            profile_shape = order.get("product_profile")
            quantity_tons = order.get("quantity_tons", 1.0)
            due_date = order.get("due_date")

            # Find a matching die (alloy + profile_shape)
            matching_die = None
            for die in available_dies:
                if die.get("id") in used_dies:
                    continue
                if die.get("alloy") == alloy and die.get("profile_code") == profile_shape:
                    matching_die = die
                    break

            # Find a matching billet (alloy)
            matching_billet = None
            for billet in available_billets:
                if billet.get("id") in used_billets:
                    continue
                if billet.get("alloy") == alloy:
                    matching_billet = billet
                    break

            # Find an available machine
            matching_machine = None
            for machine in available_machines:
                if machine.get("id") in used_machines:
                    continue
                # Check if machine is free during the proposed time slot
                # For simplicity, assume each order takes 1 day
                proposed_start = horizon_start
                proposed_end = proposed_start + timedelta(days=1)
                # Check for conflicts
                conflict = False
                for (m_id, s, e) in used_time_slots:
                    if m_id == machine.get("id") and not (
                        proposed_end <= s or proposed_start >= e
                    ):
                        conflict = True
                        break
                if not conflict:
                    matching_machine = machine
                    break

            # If we have all three, create a plan
            if matching_die and matching_billet and matching_machine:
                plan_number = f"PLAN-{order.get('order_number', 'UNKNOWN')}"
                plan = {
                    "order_id": order_id,
                    "plan_number": plan_number,
                    "alloy": alloy,
                    "profile_shape": profile_shape,
                    "scheduled_start": proposed_start.isoformat(),
                    "scheduled_end": proposed_end.isoformat(),
                    "status": "Draft",
                    "priority": order.get("priority", "normal"),
                    "die_id": matching_die.get("id"),
                    "billet_id": matching_billet.get("id"),
                    "machine_id": matching_machine.get("id"),
                }
                plans.append(plan)
                used_dies.add(matching_die.get("id"))
                used_billets.add(matching_billet.get("id"))
                used_machines.add(matching_machine.get("id"))
                used_time_slots.append(
                    (matching_machine.get("id"), proposed_start, proposed_end)
                )
            else:
                unassigned.append(order)

        # Compute projected shortages
        shortages = cls.compute_shortages(
            orders=sorted_orders,
            available_dies=available_dies,
            available_billets=available_billets,
        )

        return {
            "plans": plans,
            "unassigned_orders": unassigned,
            "shortages": shortages,
        }

    @classmethod
    def compute_shortages(cls, orders=None, available_dies=None,
                          available_billets=None):
        """
        Compute projected die/billet shortages.

        Returns a dict with:
        - die_shortages: list of {alloy, profile_shape, needed, available}
        - billet_shortages: list of {alloy, needed, available}
        """
        if orders is None:
            # Fetch from DB
            orders = [
                {
                    "id": o.id,
                    "alloy": o.alloy,
                    "product_profile": o.product_profile,
                    "quantity_tons": o.quantity_tons,
                }
                for o in CustomerOrder.query.filter(
                    CustomerOrder.status.in_(["CONFIRMED", "IN_PROGRESS"])
                ).all()
            ]

        if available_dies is None:
            available_dies = [
                {"id": d.id, "alloy": d.alloy, "profile_code": d.profile_code}
                for d in Die.query.filter_by(status="Available").all()
            ]

        if available_billets is None:
            available_billets = [
                {"id": b.id, "alloy": b.alloy}
                for b in Billet.query.filter_by(status="AVAILABLE").all()
            ]

        # Group demand by alloy+profile
        die_demand = {}
        billet_demand = {}
        for order in orders:
            alloy = order.get("alloy")
            profile = order.get("product_profile")
            key = (alloy, profile)
            die_demand[key] = die_demand.get(key, 0) + 1
            billet_demand[alloy] = billet_demand.get(alloy, 0) + 1

        # Group supply by alloy+profile
        die_supply = {}
        billet_supply = {}
        for die in available_dies:
            key = (die.get("alloy"), die.get("profile_code"))
            die_supply[key] = die_supply.get(key, 0) + 1
        for billet in available_billets:
            alloy = billet.get("alloy")
            billet_supply[alloy] = billet_supply.get(alloy, 0) + 1

        # Compute shortages
        die_shortages = []
        for key, needed in die_demand.items():
            available = die_supply.get(key, 0)
            if needed > available:
                die_shortages.append({
                    "alloy": key[0],
                    "profile_shape": key[1],
                    "needed": needed,
                    "available": available,
                    "shortage": needed - available,
                })

        billet_shortages = []
        for alloy, needed in billet_demand.items():
            available = billet_supply.get(alloy, 0)
            if needed > available:
                billet_shortages.append({
                    "alloy": alloy,
                    "needed": needed,
                    "available": available,
                    "shortage": needed - available,
                })

        return {
            "die_shortages": die_shortages,
            "billet_shortages": billet_shortages,
        }
