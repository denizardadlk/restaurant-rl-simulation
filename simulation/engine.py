from typing import List, Dict, Any, Tuple
from .grid import RestaurantGrid
from .pathfinding import Pathfinder
from .generator import OrderGenerator
from .entities import Order
import random
from .collector import EmpiricalDataCollector
from .model import CookTimePredictor

class SimulationEngine:
    def __init__(self, config_path: str):
        self.tick = 0
        self.grid = RestaurantGrid(config_path)
        self.pathfinder = Pathfinder(self.grid)
        self.generator = OrderGenerator()
        
        # System State
        self.order_queue: List[Order] = []
        self.completed_orders: List[Order] = []
        self.churned_customers: int = 0
        
        # ML System
        self.collector = EmpiricalDataCollector()
        self.predictor = CookTimePredictor()
        
    def reset(self):
        self.tick = 0
        # Reload grid to reset states
        self.grid = RestaurantGrid(self.grid.config_path)
        self.order_queue.clear()
        self.completed_orders.clear()
        self.churned_customers = 0

    def step(self, actions: List[Dict[str, Any]] = None):
        """
        Advances the simulation by 1 tick.
        actions: list of dicts for RL scheduler (e.g. assigning queued orders to stations)
        """
        self.tick += 1
        
        # 1. Update Customers & Patience
        self._update_patience()
        
        # 2. Generate New Orders
        empty_tables = [table for table in self.grid.tables.values() if table.is_empty]
        new_orders = self.generator.generate_orders(self.tick, empty_tables)
        
        for order in new_orders:
            self.order_queue.append(order)
            table = self.grid.tables[order.table_id]
            if table.status == "EMPTY":
                table.status = "WAITING_FOOD"
                table.customers = table.capacity
                table.patience = 20.0
                table.current_orders = []
            table.current_orders.append(order)
            
        # 3. Apply Actions (from RL Scheduler if any)
        # For Phase 1, if no actions provided, we can do a simple FIFO assignment if stations are free.
        if actions is None:
            self._simple_fifo_scheduler()
        else:
            # Process RL actions (Assign order -> station)
            pass
            
        # 4. Progress Cooking
        self._progress_cooking()
        
        # 5. JIT Waiter Dispatching & Deliveries
        self._manage_waiters()

    def _update_patience(self):
        for table in self.grid.tables.values():
            if table.status == "WAITING_FOOD":
                table.patience -= 0.1 # patience decreases by 0.1 per tick
                if table.patience <= 0:
                    # Churn
                    self.churned_customers += table.customers
                    
                    # Remove orders from queue if they haven't started cooking yet
                    for order in table.current_orders:
                        if order in self.order_queue:
                            self.order_queue.remove(order)
                    
                    table.customers = 0
                    table.current_orders = []
                    table.status = "EMPTY"
            
            elif table.status == "EATING":
                table.eating_time_remaining -= 1
                if table.eating_time_remaining <= 0:
                    # Finished eating, table becomes available again
                    table.customers = 0
                    table.current_orders = []
                    table.status = "EMPTY"

    def _simple_fifo_scheduler(self):
        # A very naive FIFO just to make the simulation run without RL agent
        # Look for queued orders and try to assign them to available stations and chefs
        for order in list(self.order_queue):
            if order.status == "QUEUED":
                assigned = False
                for station in self.grid.stations.values():
                    if not station.is_full:
                        # Find an available chef
                        for chef in self.grid.chefs.values():
                            if not chef.is_full:
                                # Assign!
                                order.status = "PREPARING"
                                order.assigned_station_id = station.id
                                order.assigned_chef_id = chef.id
                                order.timestamps["kitchen_start"] = self.tick
                                
                                # ML Snapshot (Zero Leakage)
                                order.station_load_at_start = len(station.active_orders)
                                order.kitchen_load_at_start = sum(len(s.active_orders) for s in self.grid.stations.values())
                                order.chef_efficiency_at_start = chef.efficiency
                                order.day_tick_at_start = self.tick
                                
                                # Ask ML for prediction
                                features = {
                                    "theoretical_time": order.theoretical_time,
                                    "dish_type": order.dish_type,
                                    "station_type": station.type,
                                    "station_load_at_start": order.station_load_at_start,
                                    "kitchen_load_at_start": order.kitchen_load_at_start,
                                    "chef_efficiency_at_start": order.chef_efficiency_at_start,
                                    "day_tick_at_start": order.day_tick_at_start
                                }
                                order.predicted_time = self.predictor.predict(features, len(self.completed_orders))
                                
                                # Sample the ACTUAL physical cook time from a normal distribution (User feedback)
                                mean_time = (order.theoretical_time / chef.efficiency) * (1 + 0.15 * order.station_load_at_start)
                                std_dev = mean_time * 0.1 # 10% standard deviation noise
                                order.actual_target_time = max(1.0, random.gauss(mean_time, std_dev))
                                
                                station.active_orders.append(order)
                                chef.active_orders.append(order)
                                chef.status = "COOKING"
                                
                                self.order_queue.remove(order)
                                assigned = True
                                break
                    if assigned:
                        break

    def _progress_cooking(self):
        for station in self.grid.stations.values():
            for order in list(station.active_orders):
                time_cooking = self.tick - order.timestamps["kitchen_start"]
                
                # Check against the true physical time sampled at start
                if time_cooking >= order.actual_target_time:
                    # Food is ready!
                    if order.status == "PREPARING":
                        order.status = "READY"
                    order.timestamps["kitchen_finish"] = self.tick
                    station.active_orders.remove(order)
                    
                    # Record to ML Data Collector
                    self.collector.record_completed_order(order, time_cooking)
                    
                    # Train model every 50 completed orders on cumulative dataset
                    if len(self.collector.data) % 50 == 0:
                        df = self.collector.get_dataframe()
                        self.predictor.train(df)
                    
                    # Free up the chef
                    chef = self.grid.chefs.get(order.assigned_chef_id)
                    if chef and order in chef.active_orders:
                        chef.active_orders.remove(order)
                        if not chef.active_orders:
                            chef.status = "IDLE"

    def _manage_waiters(self):
        import math
        import random
        # JIT Dispatch Logic: Check if any order is PREPARING or READY that needs a waiter
        for table in self.grid.tables.values():
            for order in table.current_orders:
                # If already assigned a waiter or served, skip
                if order.assigned_waiter_id or order.status in ["DELIVERING", "SERVED"]:
                    continue
                    
                needs_waiter = False
                
                if order.status == "READY":
                    needs_waiter = True
                elif order.status == "PREPARING" and order.predicted_time is not None:
                    # Check if it's time to dispatch waiter based on JIT estimate
                    idle_waiters = [w for w in self.grid.waiters.values() if w.status == "IDLE" and w.busy_until <= self.tick]
                    if idle_waiters:
                        waiter = idle_waiters[0]
                        station = self.grid.stations[order.assigned_station_id]
                        dist_to_station = self.pathfinder.get_distance((waiter.x, waiter.y), (station.x, station.y))
                        if dist_to_station == float('inf'):
                            dist_to_station = 5.0
                        walk_time = dist_to_station / waiter.speed
                        
                        time_cooking = self.tick - order.timestamps["kitchen_start"]
                        time_remaining = order.predicted_time - time_cooking
                        
                        if time_remaining <= walk_time:
                            needs_waiter = True
                
                if needs_waiter:
                    # Dispatch the first available idle waiter
                    idle_waiters = [w for w in self.grid.waiters.values() if w.status == "IDLE" and w.busy_until <= self.tick]
                    if idle_waiters:
                        waiter = idle_waiters[0]
                        station = self.grid.stations[order.assigned_station_id]
                        
                        dist_to_station = self.pathfinder.get_distance((waiter.x, waiter.y), (station.x, station.y))
                        dist_to_table = self.pathfinder.get_distance((station.x, station.y), (table.x, table.y))
                        
                        if dist_to_station == float('inf'): dist_to_station = 5.0
                        if dist_to_table == float('inf'): dist_to_table = 5.0
                            
                        walk_time_to_station = dist_to_station / waiter.speed
                        walk_time_to_table = dist_to_table / waiter.speed
                        
                        time_cooking = self.tick - order.timestamps.get("kitchen_start", self.tick)
                        est_wait_time_at_station = max(0.0, order.predicted_time - time_cooking - walk_time_to_station) if order.status == "PREPARING" else 0.0
                        
                        total_busy_time = walk_time_to_station + est_wait_time_at_station + walk_time_to_table
                        
                        waiter.status = "DELIVERING"
                        waiter.busy_until = self.tick + total_busy_time
                        
                        order.status = "DELIVERING"
                        order.assigned_waiter_id = waiter.id

        # Check deliveries that have arrived at tables
        for waiter in self.grid.waiters.values():
            if waiter.status == "DELIVERING" and self.tick >= waiter.busy_until:
                # Find the order they are delivering
                for table in self.grid.tables.values():
                    for order in table.current_orders:
                        if order.assigned_waiter_id == waiter.id and order.status == "DELIVERING":
                            # Delivered!
                            order.status = "SERVED"
                            order.timestamps["delivered_at"] = self.tick
                            self.completed_orders.append(order)
                            
                            waiter.status = "IDLE"
                            waiter.x = table.x
                            waiter.y = table.y
                            
                            # Check if ALL orders for this table are SERVED
                            all_served = all(o.status == "SERVED" for o in table.current_orders)
                            if all_served and table.status != "EATING":
                                table.status = "EATING"
                                # Calculate T_eat
                                mean_eat = 20.0 + 7.0 * max(0, math.floor((table.capacity - 2) / 2.0))
                                table.eating_time_remaining = max(5.0, random.gauss(mean_eat, 0.15 * mean_eat))
                            
                            break
                    if waiter.status == "IDLE":
                        break
