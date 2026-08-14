import math
import random
from typing import TYPE_CHECKING, List
from .entities import Order, Table, Waiter

if TYPE_CHECKING:
    from .engine import SimulationEngine

class JITWaiterManager:
    """
    Manages Just-In-Time (JIT) waiter dispatching, A* travel time synchronization,
    table group sync, and food delivery lifecycle.
    """
    def __init__(self, engine: 'SimulationEngine'):
        self.engine = engine

    def manage_waiters(self, tick: int):
        """
        Main tick handler for waiter dispatching and deliveries.
        """
        # 1. Takeout lingering deliveries check
        for order in list(self.engine.order_queue):
            if order.is_takeout and order.status == "READY":
                if tick >= order.courier_eta:
                    order.status = "SERVED"
                    order.timestamps["delivered_at"] = tick
                    self.engine.completed_orders.append(order)
                    self.engine.order_queue.remove(order)

        # 2. Group Sync & JIT Dispatch Logic for Dine-in Tables
        for table in self.engine.grid.tables.values():
            if not table.current_orders:
                continue

            # Group Sync: If Difficulty Level >= 2, wait until all table dishes are ready
            if self.engine.difficulty_level >= 2 and not table.is_fully_ready_for_service:
                # Emergency override: if patience is dangerously low (< 3.0), serve ready dishes
                if table.patience >= 3.0:
                    continue

            for order in table.current_orders:
                # Skip if already assigned or completed
                if order.assigned_waiter_id or order.status in ["DELIVERING", "SERVED"]:
                    continue

                needs_waiter = False

                if order.status == "READY":
                    needs_waiter = True
                elif order.status == "PREPARING" and order.predicted_time is not None:
                    # Check JIT dispatch timing based on A* walk duration
                    idle_waiters = self._get_idle_waiters(tick)
                    if idle_waiters:
                        waiter = idle_waiters[0]
                        station = self.engine.grid.stations.get(order.assigned_station_id)
                        if station:
                            dist_to_station = self.engine.pathfinder.get_distance((waiter.x, waiter.y), (station.x, station.y))
                            if dist_to_station == float('inf'):
                                dist_to_station = 5.0
                            walk_time = dist_to_station / waiter.speed

                            time_cooking = tick - order.timestamps["kitchen_start"]
                            time_remaining = order.predicted_time - time_cooking

                            if time_remaining <= walk_time:
                                needs_waiter = True

                if needs_waiter:
                    self._dispatch_waiter(order, table, tick)

        # 3. Process Arrivals & Deliveries
        self._process_deliveries(tick)

    def _get_idle_waiters(self, tick: int) -> List[Waiter]:
        return [w for w in self.engine.grid.waiters.values() if w.status == "IDLE" and w.busy_until <= tick]

    def _dispatch_waiter(self, order: Order, table: Table, tick: int):
        idle_waiters = self._get_idle_waiters(tick)
        if not idle_waiters:
            return

        waiter = idle_waiters[0]
        station = self.engine.grid.stations.get(order.assigned_station_id)
        if not station:
            return

        dist_to_station = self.engine.pathfinder.get_distance((waiter.x, waiter.y), (station.x, station.y))
        dist_to_table = self.engine.pathfinder.get_distance((station.x, station.y), (table.x, table.y))

        if dist_to_station == float('inf'): dist_to_station = 5.0
        if dist_to_table == float('inf'): dist_to_table = 5.0

        walk_time_to_station = dist_to_station / waiter.speed
        walk_time_to_table = dist_to_table / waiter.speed

        time_cooking = tick - order.timestamps.get("kitchen_start", tick)
        est_wait_time_at_station = max(0.0, (order.predicted_time or 0.0) - time_cooking - walk_time_to_station) if order.status == "PREPARING" else 0.0

        total_busy_time = walk_time_to_station + est_wait_time_at_station + walk_time_to_table

        waiter.status = "DELIVERING"
        waiter.busy_until = tick + total_busy_time

        order.status = "DELIVERING"
        order.assigned_waiter_id = waiter.id

    def _process_deliveries(self, tick: int):
        for waiter in self.engine.grid.waiters.values():
            if waiter.status == "DELIVERING" and tick >= waiter.busy_until:
                # Find matching order
                for table in self.engine.grid.tables.values():
                    for order in table.current_orders:
                        if order.assigned_waiter_id == waiter.id and order.status == "DELIVERING":
                            # Delivered!
                            order.status = "SERVED"
                            order.timestamps["delivered_at"] = tick
                            self.engine.completed_orders.append(order)

                            waiter.status = "IDLE"
                            waiter.x = table.x
                            waiter.y = table.y

                            # Check if all orders for this table are served
                            all_served = all(o.status == "SERVED" for o in table.current_orders)
                            if all_served and table.status != "EATING":
                                table.status = "EATING"
                                mean_eat = 20.0 + 7.0 * max(0, math.floor((table.capacity - 2) / 2.0))
                                table.eating_time_remaining = max(5.0, random.gauss(mean_eat, 0.15 * mean_eat))

                            break
                    if waiter.status == "IDLE":
                        break
