import math
import random
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from .entities import Order, Table, Waiter

if TYPE_CHECKING:
    from .engine import SimulationEngine

class JITWaiterManager:
    """
    Manages Just-In-Time (JIT) waiter dispatching, A* step-by-step path movement,
    multi-dish carrying (batch delivery), order taking, and table cleaning lifecycles.
    """
    def __init__(self, engine: 'SimulationEngine'):
        self.engine = engine

    def manage_waiters(self, tick: int):
        """
        Main tick handler for waiter movement, task execution, and dispatching.
        """
        # 1. Takeout lingering deliveries check
        self._process_takeout_deliveries(tick)

        # 2. Advance active waiters (movement along path and state machine)
        self._update_active_waiters(tick)

        # 3. Dispatch idle waiters to pending tasks (Priority: Deliver Food > Take Order > Clean Table)
        # When RL Waiter agent is active, rule-based dispatching is skipped so RL agent has full control.
        if not getattr(self.engine, 'enable_rl_waiter', False):
            self._dispatch_idle_waiters(tick)

    def _process_takeout_deliveries(self, tick: int):
        all_counters = list(self.engine.grid.delivery_counters.values())
        if getattr(self.engine.grid, "takeout_counter", None):
            all_counters.append(self.engine.grid.takeout_counter)
        if getattr(self.engine.grid, "beverage_counter", None):
            all_counters.append(self.engine.grid.beverage_counter)

        for c in all_counters:
            for order in list(c.ready_orders):
                if order.is_takeout and order.status == "READY":
                    if tick >= (order.courier_eta or 0):
                        order.status = "SERVED"
                        order.timestamps["delivered_at"] = tick
                        if order not in self.engine.completed_orders:
                            self.engine.completed_orders.append(order)
                        if order in c.ready_orders:
                            c.ready_orders.remove(order)
                        if order in self.engine.order_queue:
                            self.engine.order_queue.remove(order)

    def _get_idle_waiters(self, tick: int) -> List[Waiter]:
        return [
            w for w in self.engine.grid.waiters.values()
            if w.status == "IDLE" and w.current_task is None and (w.busy_until <= tick)
        ]

    def _update_active_waiters(self, tick: int):
        for waiter in self.engine.grid.waiters.values():
            if waiter.current_task is None:
                # If waiter has busy_until set without current_task (legacy compatibility)
                if waiter.status == "DELIVERING" and tick >= waiter.busy_until:
                    self._complete_legacy_delivery(waiter, tick)
                continue

            task = waiter.current_task
            task_type = task.get("type")

            # Check if simulation time jumped past busy_until (Fast-forward / test jump compatibility)
            time_jumped = (waiter.busy_until > 0 and tick >= waiter.busy_until)

            if task_type == "DELIVER":
                self._update_deliver_task(waiter, task, tick, time_jumped)
            elif task_type == "TRANSFER_TAKEOUT_DRINK":
                self._update_transfer_takeout_drink_task(waiter, task, tick, time_jumped)
            elif task_type == "TAKE_ORDER":
                self._update_take_order_task(waiter, task, tick, time_jumped)
            elif task_type == "CLEAN_TABLE":
                self._update_clean_table_task(waiter, task, tick, time_jumped)

    def _step_waiter_along_path(self, waiter: Waiter):
        speed = int(self.engine.time_config.walking_speed * getattr(waiter, "speed", 1.0))
        for _ in range(max(1, speed)):
            if waiter.path:
                next_cell = waiter.path.pop(0)
                if next_cell == (waiter.x, waiter.y) and waiter.path:
                    next_cell = waiter.path.pop(0)
                waiter.x, waiter.y = next_cell
            else:
                break

    def _update_deliver_task(self, waiter: Waiter, task: Dict[str, Any], tick: int, time_jumped: bool):
        table_id = task.get("target_table_id")
        table = self.engine.grid.tables.get(table_id)
        counter_id = task.get("counter_id")
        bev_counter = getattr(self.engine.grid, "beverage_counter", None)
        counter = self.engine.grid.delivery_counters.get(counter_id or "") or (bev_counter if counter_id == getattr(bev_counter, "id", None) else self.engine.grid.delivery_counter)

        if not table:
            self._reset_waiter_to_idle(waiter)
            return

        if time_jumped:
            self._finalize_food_delivery(waiter, table, tick)
            return

        substate = task.get("substate")
        if substate in ["WALK_TO_STATION", "WALK_TO_COUNTER"]:
            self._step_waiter_along_path(waiter)
            target_pos = (counter.x, counter.y) if counter else (0, 0)
            if not waiter.path or (waiter.x, waiter.y) == target_pos:
                if counter:
                    waiter.x, waiter.y = counter.x, counter.y
                task["substate"] = "PICKING_FOOD"

        if task.get("substate") == "PICKING_FOOD":
            orders_to_carry = []
            for order_id in list(task.get("order_ids", [])):
                matching = [o for o in table.current_orders if o.order_id == order_id]
                if matching:
                    orders_to_carry.extend(matching)

            # Pick up additional ready orders for same table if tray space allows
            for order in table.current_orders:
                if order not in orders_to_carry and order.status in ["READY", "PREPARING", "DELIVERING"] and len(orders_to_carry) < waiter.tray_capacity:
                    if not order.assigned_waiter_id or order.assigned_waiter_id == waiter.id:
                        orders_to_carry.append(order)

            ready_orders = [o for o in orders_to_carry if o.status in ["READY", "PREPARING", "DELIVERING"]]
            if ready_orders:
                for o in ready_orders:
                    o.status = "DELIVERING"
                    o.assigned_waiter_id = waiter.id
                    # Remove from whichever counter holds it
                    if counter and o in counter.ready_orders:
                        counter.ready_orders.remove(o)
                    else:
                        for c in self.engine.grid.delivery_counters.values():
                            if o in c.ready_orders:
                                c.ready_orders.remove(o)
                                break
                    if o not in waiter.carrying_orders:
                        waiter.carrying_orders.append(o)

                service_dur = self.engine.time_config.waiter_config.get("table_service_duration", 1.0)
                raw_path = self.engine.pathfinder.get_path((waiter.x, waiter.y), (table.x, table.y))
                waiter.path = raw_path[1:] if len(raw_path) > 1 else []
                task["substate"] = "WALK_TO_TABLE"
                waiter.status = "DELIVERING"
                # Step remaining path to table within same tick
                self._step_waiter_along_path(waiter)
                if not waiter.path or (waiter.x, waiter.y) == (table.x, table.y):
                    if service_dur > 0:
                        task["substate"] = "SERVING_TABLE"
                        task["finish_tick"] = tick + service_dur
                        waiter.busy_until = tick + service_dur
                    else:
                        self._finalize_food_delivery(waiter, table, tick)
                    return

        elif task.get("substate") == "WALK_TO_TABLE":
            self._step_waiter_along_path(waiter)
            if not waiter.path or (waiter.x, waiter.y) == (table.x, table.y):
                service_dur = self.engine.time_config.waiter_config.get("table_service_duration", 1.0)
                if service_dur > 0:
                    task["substate"] = "SERVING_TABLE"
                    task["finish_tick"] = tick + service_dur
                    waiter.busy_until = tick + service_dur
                else:
                    self._finalize_food_delivery(waiter, table, tick)

        elif task.get("substate") == "SERVING_TABLE":
            if tick >= task.get("finish_tick", tick):
                self._finalize_food_delivery(waiter, table, tick)

    def _calculate_eating_time(self, table: Table) -> float:
        eat_cfg = self.engine.time_config.eating_duration
        base_time = eat_cfg.get("base_time", 20.0)
        extra_time = eat_cfg.get("extra_time_per_two_seats", 7.0)
        std_ratio = eat_cfg.get("std_dev_ratio", 0.15)
        min_time = eat_cfg.get("min_time", 5.0)
        mean_eat = base_time + extra_time * max(0, math.floor((table.capacity - 2) / 2.0))
        return max(min_time, random.gauss(mean_eat, std_ratio * mean_eat))

    def _finalize_food_delivery(self, waiter: Waiter, table: Table, tick: int):
        waiter.x, waiter.y = table.x, table.y
        waiter.path.clear()

        # Mark all carrying orders as SERVED
        for order in list(waiter.carrying_orders):
            order.status = "SERVED"
            order.timestamps["delivered_at"] = tick
            if order not in self.engine.completed_orders:
                self.engine.completed_orders.append(order)

        # Also serve any orders assigned to this waiter for this table
        for order in table.current_orders:
            if order.assigned_waiter_id == waiter.id and order.status in ["DELIVERING", "READY"]:
                order.status = "SERVED"
                order.timestamps["delivered_at"] = tick
                if order not in self.engine.completed_orders:
                    self.engine.completed_orders.append(order)

        # Remove all served orders from any delivery counter ready_orders
        for c in self.engine.grid.delivery_counters.values():
            c.ready_orders = [o for o in c.ready_orders if o.status != "SERVED"]
        if getattr(self.engine.grid, "beverage_counter", None):
            self.engine.grid.beverage_counter.ready_orders = [o for o in self.engine.grid.beverage_counter.ready_orders if o.status != "SERVED"]

        waiter.carrying_orders.clear()

        # Check if table is fully served
        if table.current_orders and all(o.status == "SERVED" for o in table.current_orders):
            if table.status != "EATING":
                table.status = "EATING"
                table.eating_time_remaining = self._calculate_eating_time(table)

        self._reset_waiter_to_idle(waiter)

    def _update_transfer_takeout_drink_task(self, waiter: Waiter, task: Dict[str, Any], tick: int, time_jumped: bool):
        from_counter_id = task.get("from_counter_id")
        to_counter_id = task.get("to_counter_id")
        bev_counter = self.engine.grid.delivery_counters.get(from_counter_id or "") or getattr(self.engine.grid, "beverage_counter", None) or self.engine.grid.delivery_counter
        takeout_counter = self.engine.grid.delivery_counters.get(to_counter_id or "") or getattr(self.engine.grid, "takeout_counter", None) or self.engine.grid.delivery_counter

        if time_jumped:
            self._finalize_takeout_drink_transfer(waiter, takeout_counter, tick, task=task)
            return

        substate = task.get("substate")
        if substate == "WALK_TO_BEV":
            self._step_waiter_along_path(waiter)
            if not waiter.path or (waiter.x, waiter.y) == (bev_counter.x, bev_counter.y):
                waiter.x, waiter.y = bev_counter.x, bev_counter.y
                task["substate"] = "PICKING_BEV"

        if task.get("substate") == "PICKING_BEV":
            order_ids = task.get("order_ids", [])
            for o in list(bev_counter.ready_orders):
                if o.order_id in order_ids and len(waiter.carrying_orders) < waiter.tray_capacity:
                    bev_counter.ready_orders.remove(o)
                    o.status = "DELIVERING"
                    waiter.carrying_orders.append(o)

            raw_path = self.engine.pathfinder.get_path((waiter.x, waiter.y), (takeout_counter.x, takeout_counter.y))
            waiter.path = raw_path[1:] if len(raw_path) > 1 else []
            task["substate"] = "WALK_TO_TAKEOUT"
            self._step_waiter_along_path(waiter)
            if not waiter.path or (waiter.x, waiter.y) == (takeout_counter.x, takeout_counter.y):
                self._finalize_takeout_drink_transfer(waiter, takeout_counter, tick, task=task)

        elif task.get("substate") == "WALK_TO_TAKEOUT":
            self._step_waiter_along_path(waiter)
            if not waiter.path or (waiter.x, waiter.y) == (takeout_counter.x, takeout_counter.y):
                self._finalize_takeout_drink_transfer(waiter, takeout_counter, tick, task=task)

    def _finalize_takeout_drink_transfer(self, waiter: Waiter, takeout_counter: DeliveryCounter, tick: int, task: Optional[Dict[str, Any]] = None):
        waiter.x, waiter.y = takeout_counter.x, takeout_counter.y
        waiter.path.clear()

        # Transfer carrying orders
        for order in list(waiter.carrying_orders):
            order.status = "READY"
            order.assigned_counter_id = takeout_counter.id
            order.assigned_waiter_id = None
            if order not in takeout_counter.ready_orders:
                takeout_counter.ready_orders.append(order)
        waiter.carrying_orders.clear()

        # If task has orders not yet picked up from source counter, transfer them directly
        if task:
            from_counter_id = task.get("from_counter_id")
            bev_counter = self.engine.grid.delivery_counters.get(from_counter_id or "") or getattr(self.engine.grid, "beverage_counter", None) or self.engine.grid.delivery_counter
            order_ids = task.get("order_ids", [])
            for o in list(bev_counter.ready_orders):
                if o.order_id in order_ids:
                    bev_counter.ready_orders.remove(o)
                    o.status = "READY"
                    o.assigned_counter_id = takeout_counter.id
                    o.assigned_waiter_id = None
                    if o not in takeout_counter.ready_orders:
                        takeout_counter.ready_orders.append(o)

        self._reset_waiter_to_idle(waiter)

    def _update_take_order_task(self, waiter: Waiter, task: Dict[str, Any], tick: int, time_jumped: bool):
        table_id = task.get("target_table_id")
        table = self.engine.grid.tables.get(table_id)

        if not table or table.status != "WAITING_ORDER":
            self._reset_waiter_to_idle(waiter)
            return

        if time_jumped:
            self._finalize_order_taking(waiter, table, tick)
            return

        take_order_dur = self.engine.time_config.waiter_config.get("order_taking_duration", 1.0)
        substate = task.get("substate")
        if substate == "WALK_TO_TABLE":
            self._step_waiter_along_path(waiter)
            if not waiter.path or (waiter.x, waiter.y) == (table.x, table.y):
                task["substate"] = "TAKING_ORDER"
                waiter.status = "TAKING_ORDER"
                task["finish_tick"] = tick + take_order_dur
                waiter.busy_until = tick + take_order_dur

        elif substate == "TAKING_ORDER":
            if tick >= task.get("finish_tick", tick):
                self._finalize_order_taking(waiter, table, tick)

    def _finalize_order_taking(self, waiter: Waiter, table: Table, tick: int):
        waiter.x, waiter.y = table.x, table.y
        waiter.path.clear()

        if table.status == "WAITING_ORDER":
            for order in list(table.pending_orders):
                order.timestamps["created_at"] = tick
                if order.category == "beverage":
                    order.status = "READY"
                    order.timestamps["kitchen_start"] = tick
                    order.timestamps["kitchen_finish"] = tick
                    bev_counter = getattr(self.engine.grid, "beverage_counter", None) or self.engine.grid.delivery_counter
                    order.assigned_counter_id = bev_counter.id
                    bev_counter.ready_orders.append(order)
                else:
                    self.engine.order_queue.append(order)
                table.current_orders.append(order)
            table.pending_orders.clear()
            table.status = "WAITING_FOOD"
            table.patience = self.engine.time_config.customer_patience.get("waiting_food_initial", 30.0)

        self._reset_waiter_to_idle(waiter)

    def _update_clean_table_task(self, waiter: Waiter, task: Dict[str, Any], tick: int, time_jumped: bool):
        table_id = task.get("target_table_id")
        table = self.engine.grid.tables.get(table_id)

        if not table or table.status != "DIRTY":
            self._reset_waiter_to_idle(waiter)
            return

        if time_jumped:
            self._finalize_table_cleaning(waiter, table)
            return

        clean_dur = self.engine.time_config.waiter_config.get("table_cleaning_duration", 2.0)
        substate = task.get("substate")
        if substate == "WALK_TO_TABLE":
            self._step_waiter_along_path(waiter)
            if not waiter.path or (waiter.x, waiter.y) == (table.x, table.y):
                task["substate"] = "CLEANING"
                waiter.status = "CLEANING"
                task["finish_tick"] = tick + clean_dur
                waiter.busy_until = tick + clean_dur

        elif substate == "CLEANING":
            if tick >= task.get("finish_tick", tick):
                self._finalize_table_cleaning(waiter, table)

    def _finalize_table_cleaning(self, waiter: Waiter, table: Table):
        waiter.x, waiter.y = table.x, table.y
        waiter.path.clear()
        if table.status == "DIRTY":
            table.status = "EMPTY"
            table.clean_time_remaining = 0.0
        self._reset_waiter_to_idle(waiter)

    def _reset_waiter_to_idle(self, waiter: Waiter):
        waiter.current_task = None
        waiter.status = "IDLE"
        waiter.busy_until = 0.0
        waiter.path.clear()

    def _complete_legacy_delivery(self, waiter: Waiter, tick: int):
        for table in self.engine.grid.tables.values():
            for order in table.current_orders:
                if order.assigned_waiter_id == waiter.id and order.status in ["DELIVERING", "READY"]:
                    order.status = "SERVED"
                    order.timestamps["delivered_at"] = tick
                    if order not in self.engine.completed_orders:
                        self.engine.completed_orders.append(order)
                    waiter.status = "IDLE"
                    waiter.x = table.x
                    waiter.y = table.y

                    all_served = all(o.status == "SERVED" for o in table.current_orders)
                    if all_served and table.status != "EATING":
                        table.status = "EATING"
                        table.eating_time_remaining = self._calculate_eating_time(table)
                    return

    def _dispatch_idle_waiters(self, tick: int):
        assigned_tables = {
            w.current_task["target_table_id"]
            for w in self.engine.grid.waiters.values()
            if w.current_task and "target_table_id" in w.current_task
        }
        counter = self.engine.grid.delivery_counter

        # 1. PRIORITY: Deliver Food (JIT or READY)
        for table in self.engine.grid.tables.values():
            if not table.current_orders:
                continue

            for order in table.current_orders:
                if order.assigned_waiter_id or order.status in ["DELIVERING", "SERVED"]:
                    continue

                needs_waiter = False
                if order.status == "READY":
                    needs_waiter = True
                elif order.status == "PREPARING" and order.predicted_time is not None:
                    idle_waiters = self._get_idle_waiters(tick)
                    if idle_waiters:
                        order_cnt = self.engine.grid.delivery_counters.get(order.assigned_counter_id or "") or counter
                        station = self.engine.grid.stations.get(order.assigned_station_id)
                        target_pos = (order_cnt.x, order_cnt.y) if order_cnt else ((station.x, station.y) if station else (0, 0))
                        
                        # Find closest idle waiter to target
                        idle_waiters.sort(key=lambda w: self.engine.pathfinder.get_distance((w.x, w.y), target_pos))
                        waiter = idle_waiters[0]
                        dist = self.engine.pathfinder.get_distance((waiter.x, waiter.y), target_pos)
                        if dist == float('inf'): dist = 5.0
                        walk_speed = self.engine.time_config.walking_speed * getattr(waiter, "speed", 1.0)
                        walk_time = dist / max(1.0, walk_speed)
                        
                        dist_st_cnt = (self.engine.pathfinder.get_distance((station.x, station.y), target_pos) / max(1.0, walk_speed)) if station and order_cnt else 0.0
                        if dist_st_cnt == float('inf'): dist_st_cnt = 0.0

                        k_start = order.timestamps.get("kitchen_start")
                        time_cooking = tick - (k_start if k_start is not None else tick)
                        time_remaining = (order.predicted_time or 0.0) - time_cooking + dist_st_cnt
                        if time_remaining <= walk_time:
                            needs_waiter = True

                if needs_waiter:
                    idle_waiters = self._get_idle_waiters(tick)
                    if idle_waiters:
                        bev_counter = getattr(self.engine.grid, "beverage_counter", None)
                        if order.category == "beverage" and bev_counter:
                            order_cnt = bev_counter
                        else:
                            order_cnt = self.engine.grid.delivery_counters.get(order.assigned_counter_id or "") or counter
                        target_pos = (order_cnt.x, order_cnt.y) if order_cnt else (0, 0)
                        idle_waiters.sort(key=lambda w: self.engine.pathfinder.get_distance((w.x, w.y), target_pos))
                        self._dispatch_food_delivery(idle_waiters[0], order, table, tick)
                        assigned_tables.add(table.id)

        # 1.5 PRIORITY: Transfer Takeout Beverages to takeout_counter
        all_ready_sources = []
        if getattr(self.engine.grid, "beverage_counter", None):
            all_ready_sources.append(self.engine.grid.beverage_counter)
        for c in self.engine.grid.delivery_counters.values():
            if c not in all_ready_sources:
                all_ready_sources.append(c)

        takeout_counter = getattr(self.engine.grid, "takeout_counter", None)
        for src_cnt in all_ready_sources:
            if takeout_counter and src_cnt.id == takeout_counter.id:
                continue
            takeout_drinks = [o for o in src_cnt.ready_orders if o.is_takeout and not o.assigned_waiter_id and o.status == "READY"]
            if takeout_drinks:
                idle_waiters = self._get_idle_waiters(tick)
                if idle_waiters:
                    idle_waiters.sort(key=lambda w: self.engine.pathfinder.get_distance((w.x, w.y), (src_cnt.x, src_cnt.y)))
                    self._dispatch_takeout_drink_transfer(idle_waiters[0], takeout_drinks, tick)
                    break

        # 2. PRIORITY: Take Orders for WAITING_ORDER Tables
        for table in self.engine.grid.tables.values():
            if table.status == "WAITING_ORDER" and table.id not in assigned_tables:
                idle_waiters = self._get_idle_waiters(tick)
                if not idle_waiters:
                    break
                idle_waiters.sort(key=lambda w: self.engine.pathfinder.get_distance((w.x, w.y), (table.x, table.y)))
                waiter = idle_waiters[0]
                self._dispatch_take_order(waiter, table, tick)
                assigned_tables.add(table.id)

        # 3. PRIORITY: Clean DIRTY Tables
        for table in self.engine.grid.tables.values():
            if table.status == "DIRTY" and table.id not in assigned_tables:
                idle_waiters = self._get_idle_waiters(tick)
                if not idle_waiters:
                    break
                idle_waiters.sort(key=lambda w: self.engine.pathfinder.get_distance((w.x, w.y), (table.x, table.y)))
                waiter = idle_waiters[0]
                self._dispatch_clean_table(waiter, table, tick)
                assigned_tables.add(table.id)

    def _dispatch_takeout_drink_transfer(self, waiter: Waiter, drinks: List[Order], tick: int):
        from_counter_id = drinks[0].assigned_counter_id if drinks else None
        bev_counter = self.engine.grid.delivery_counters.get(from_counter_id or "") or getattr(self.engine.grid, "beverage_counter", None) or self.engine.grid.delivery_counter
        takeout_counter = getattr(self.engine.grid, "takeout_counter", None) or self.engine.grid.delivery_counter

        batch = drinks[:waiter.tray_capacity]
        for o in batch:
            o.assigned_waiter_id = waiter.id
            o.status = "DELIVERING"

        dist_to_bev = self.engine.pathfinder.get_distance((waiter.x, waiter.y), (bev_counter.x, bev_counter.y))
        dist_to_takeout = self.engine.pathfinder.get_distance((bev_counter.x, bev_counter.y), (takeout_counter.x, takeout_counter.y))
        if dist_to_bev == float('inf'): dist_to_bev = 5.0
        if dist_to_takeout == float('inf'): dist_to_takeout = 5.0

        walk_speed = self.engine.time_config.walking_speed * getattr(waiter, "speed", 1.0)
        total_busy = max(1.0, math.ceil((dist_to_bev + dist_to_takeout) / max(1.0, walk_speed)))

        waiter.status = "DELIVERING"
        waiter.busy_until = tick + total_busy

        raw_path = self.engine.pathfinder.get_path((waiter.x, waiter.y), (bev_counter.x, bev_counter.y))
        waiter.path = raw_path[1:] if len(raw_path) > 1 else []

        waiter.current_task = {
            "type": "TRANSFER_TAKEOUT_DRINK",
            "order_ids": [o.order_id for o in batch],
            "from_counter_id": bev_counter.id,
            "to_counter_id": takeout_counter.id,
            "substate": "WALK_TO_BEV" if (waiter.x, waiter.y) != (bev_counter.x, bev_counter.y) else "PICKING_BEV"
        }

    def _dispatch_food_delivery(self, waiter: Waiter, primary_order: Order, table: Table, tick: int):
        bev_counter = getattr(self.engine.grid, "beverage_counter", None)
        if primary_order.category == "beverage" and bev_counter:
            counter = bev_counter
        else:
            counter = self.engine.grid.delivery_counters.get(primary_order.assigned_counter_id or "") or self.engine.grid.delivery_counter
        station = self.engine.grid.stations.get(primary_order.assigned_station_id)
        target_pos = (counter.x, counter.y) if counter else ((station.x, station.y) if station else (0, 0))

        batch_orders = [primary_order]
        primary_counter_id = primary_order.assigned_counter_id
        for o in table.current_orders:
            if o != primary_order and not o.assigned_waiter_id and o.status == "READY":
                # Only batch if order is on the same counter as primary order
                if o.assigned_counter_id == primary_counter_id:
                    if len(batch_orders) < waiter.tray_capacity:
                        batch_orders.append(o)

        for o in batch_orders:
            o.assigned_waiter_id = waiter.id
            o.status = "DELIVERING"

        dist_to_counter = self.engine.pathfinder.get_distance((waiter.x, waiter.y), target_pos)
        dist_to_table = self.engine.pathfinder.get_distance(target_pos, (table.x, table.y))
        if dist_to_counter == float('inf'): dist_to_counter = 5.0
        if dist_to_table == float('inf'): dist_to_table = 5.0

        walk_speed = self.engine.time_config.walking_speed * getattr(waiter, "speed", 1.0)
        walk_time_to_counter = dist_to_counter / max(1.0, walk_speed)
        walk_time_to_table = dist_to_table / max(1.0, walk_speed)
        k_start = primary_order.timestamps.get("kitchen_start")
        time_cooking = tick - (k_start if k_start is not None else tick)
        est_wait = max(0.0, (primary_order.predicted_time or 0.0) - time_cooking - walk_time_to_counter) if primary_order.status == "PREPARING" else 0.0
        total_busy = max(1.0, math.ceil(walk_time_to_counter + est_wait + walk_time_to_table))

        waiter.status = "DELIVERING"
        waiter.busy_until = tick + total_busy

        raw_path = self.engine.pathfinder.get_path((waiter.x, waiter.y), target_pos)
        waiter.path = raw_path[1:] if len(raw_path) > 1 else []

        waiter.current_task = {
            "type": "DELIVER",
            "order_ids": [o.order_id for o in batch_orders],
            "counter_id": counter.id if counter else None,
            "target_counter_id": counter.id if counter else None,
            "target_table_id": table.id,
            "substate": "WALK_TO_COUNTER" if (waiter.x, waiter.y) != target_pos else "PICKING_FOOD"
        }

    def _dispatch_take_order(self, waiter: Waiter, table: Table, tick: int):
        dist = self.engine.pathfinder.get_distance((waiter.x, waiter.y), (table.x, table.y))
        if dist == float('inf'): dist = 4.0
        walk_speed = self.engine.time_config.walking_speed * getattr(waiter, "speed", 1.0)
        walk_time = dist / max(1.0, walk_speed)
        order_dur = self.engine.time_config.waiter_config.get("order_taking_duration", 1.0)
        total_busy = max(1.0, math.ceil(walk_time + order_dur))

        waiter.status = "TAKING_ORDER"
        waiter.busy_until = tick + total_busy

        raw_path = self.engine.pathfinder.get_path((waiter.x, waiter.y), (table.x, table.y))
        waiter.path = raw_path[1:] if len(raw_path) > 1 else []

        waiter.current_task = {
            "type": "TAKE_ORDER",
            "target_table_id": table.id,
            "substate": "WALK_TO_TABLE" if (waiter.x, waiter.y) != (table.x, table.y) else "TAKING_ORDER",
            "finish_tick": tick + total_busy
        }

    def _dispatch_clean_table(self, waiter: Waiter, table: Table, tick: int):
        dist = self.engine.pathfinder.get_distance((waiter.x, waiter.y), (table.x, table.y))
        if dist == float('inf'): dist = 4.0
        walk_speed = self.engine.time_config.walking_speed * getattr(waiter, "speed", 1.0)
        walk_time = dist / max(1.0, walk_speed)
        clean_dur = self.engine.time_config.waiter_config.get("table_cleaning_duration", 2.0)
        total_busy = max(1.0, math.ceil(walk_time + clean_dur))

        waiter.status = "CLEANING"
        waiter.busy_until = tick + total_busy

        raw_path = self.engine.pathfinder.get_path((waiter.x, waiter.y), (table.x, table.y))
        waiter.path = raw_path[1:] if len(raw_path) > 1 else []

        waiter.current_task = {
            "type": "CLEAN_TABLE",
            "target_table_id": table.id,
            "substate": "WALK_TO_TABLE" if (waiter.x, waiter.y) != (table.x, table.y) else "CLEANING",
            "finish_tick": tick + total_busy
        }
