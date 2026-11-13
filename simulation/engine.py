import os
from typing import List, Dict, Any, Optional
from .grid import RestaurantGrid
from .pathfinding import Pathfinder
from .generator import OrderGenerator
from .entities import Order, Station, Chef
from .collector import EmpiricalDataCollector
from .model import CookTimePredictor
from .customer_manager import CustomerManager
from .kitchen import KitchenManager
from .waiter_manager import JITWaiterManager
from .time_config import load_time_config, TimeConfig

class SimulationEngine:
    """
    Core orchestrator of the Restaurant Simulation.
    Coordinates customer lifecycles, kitchen operations, and waiter dispatches.
    """
    def __init__(self, config_path: str = "config/default_layout.json", difficulty_level: int = 2, freeze_ml: bool = False, auto_generate_orders: bool = True, enable_rl_waiter: bool = False, time_config_path: Optional[str] = None, time_config: Optional[TimeConfig] = None):
        self.difficulty_level = difficulty_level
        self.freeze_ml = freeze_ml
        self.auto_generate_orders = auto_generate_orders
        self.enable_rl_waiter = enable_rl_waiter
        self.tick = 0
        self.grid = RestaurantGrid(config_path)
        self.pathfinder = Pathfinder(self.grid)
        self.time_config_path = time_config_path
        self.time_config = time_config or load_time_config(time_config_path)
        self.generator = OrderGenerator(difficulty_level=self.difficulty_level, time_config=self.time_config)
        
        # System State
        self.order_queue: List[Order] = []
        self.completed_orders: List[Order] = []
        self.churned_orders: List[Order] = []
        self.churned_customers: int = 0
        
        # ML Subsystems
        self.collector = EmpiricalDataCollector()
        self.predictor = CookTimePredictor()
        # Automatically load pre-trained ML cook time model if present
        if os.path.exists("models/ml_cook_time_model.pkl"):
            self.predictor.load("models/ml_cook_time_model.pkl")
        
        # Dedicated Sub-Managers
        self.customer_manager = CustomerManager(self)
        self.kitchen_manager = KitchenManager(self)
        self.waiter_manager = JITWaiterManager(self)

    def reset(self):
        """Resets the simulation clock, grid states, and queues."""
        self.tick = 0
        self.grid = RestaurantGrid(self.grid.config_path)
        self.order_queue.clear()
        self.completed_orders.clear()
        self.churned_orders.clear()
        self.churned_customers = 0
        self.kitchen_manager.fryer_inventory = {"Patates": 0, "Sogan_Halkasi": 0}
        self.kitchen_manager.doner_inventory = 0

    def assign_order(self, order: Order, station: Station, chef: Chef) -> bool:
        """
        Unified order assignment method. Delegates to KitchenManager.
        Used across simulation tick and Gymnasium RL environment.
        """
        return self.kitchen_manager.assign_order(order, station, chef, self.tick)

    def step(self, actions: Optional[List[Dict[str, Any]]] = None):
        """
        Advances the simulation by 1 tick.
        actions: list of dicts for RL scheduler (e.g. assigning queued orders to stations)
        """
        self.kitchen_manager.handle_breakdowns()
        self.tick += 1
        
        # 1. Update Customers & Patience
        self.customer_manager.update_patience(self.tick)
        
        # 2. Generate New Orders (only if enabled)
        if self.auto_generate_orders:
            self._generate_orders()
            
        # 3. Apply Actions (FIFO if no explicit RL actions provided)
        if actions is None:
            self._simple_fifo_scheduler()
        else:
            for act in actions:
                if isinstance(act, dict):
                    act_type = act.get("type")
                    if act_type == "ASSIGN":
                        order = next((o for o in self.order_queue if o.order_id == act.get("order_id")), None)
                        if order:
                            st = self.grid.stations.get(act.get("station_id"))
                            ch = self.grid.chefs.get(act.get("chef_id"))
                            if st and ch:
                                self.assign_order(order, st, ch)
                    elif act_type == "PICKUP_TO_COUNTER":
                        ch = self.grid.chefs.get(act.get("chef_id"))
                        st = self.grid.stations.get(act.get("station_id"))
                        orders = [o for o in st.active_orders if o.status == "WAITING_PICKUP"] if st else []
                        if ch and st and orders and ch.status == "IDLE":
                            self.kitchen_manager._dispatch_chef_pickup_to_counter(ch, st, orders[:ch.carrying_capacity], self.tick)
                    elif act_type == "TRANSFER_STAGE":
                        ch = self.grid.chefs.get(act.get("chef_id"))
                        from_st = self.grid.stations.get(act.get("from_station_id"))
                        to_st = self.grid.stations.get(act.get("to_station_id"))
                        o = next((x for x in from_st.active_orders if x.order_id == act.get("order_id")), None) if from_st else None
                        if ch and from_st and to_st and o and ch.status == "IDLE":
                            self.kitchen_manager._dispatch_chef_stage_transfer(ch, from_st, to_st, o, self.tick)
            
        # 4. Progress Cooking & Multi-stage transitions
        self.kitchen_manager.progress_cooking(self.tick)
        
        # 5. JIT Waiter Dispatching & Deliveries
        self.waiter_manager.manage_waiters(self.tick)

    def _generate_orders(self):
        """Generates new customer arrivals and orders for available empty tables."""
        empty_tables = [table for table in self.grid.tables.values() if table.is_empty]
        new_orders = self.generator.generate_orders(self.tick, empty_tables, total_tables_count=len(self.grid.tables))
        
        for order in new_orders:
            if order.is_takeout:
                if order.category == "beverage":
                    order.status = "READY"
                    order.timestamps["kitchen_start"] = self.tick
                    order.timestamps["kitchen_finish"] = self.tick
                    bev_counter = getattr(self.grid, "beverage_counter", None) or self.grid.delivery_counter
                    order.assigned_counter_id = bev_counter.id
                    bev_counter.ready_orders.append(order)
                else:
                    self.order_queue.append(order)
            else:
                table = self.grid.tables[order.table_id]
                if table.status == "EMPTY":
                    table.status = "WAITING_ORDER"
                    table.customers = table.capacity
                    table.patience = self.time_config.customer_patience.get("waiting_order_initial", 20.0)
                    table.pending_orders.clear()
                    table.current_orders.clear()
                table.pending_orders.append(order)

    def _simple_fifo_scheduler(self):
        """A simple FIFO fallback scheduler when RL agent is not attached."""
        for order in list(self.order_queue):
            if order.status in ["QUEUED", "QUEUED_STAGE"]:
                req_station_type = order.stages[order.current_stage_idx]["station_type"]
                assigned = False
                for station in self.grid.stations.values():
                    if station.type == req_station_type and not station.is_full and not station.is_broken:
                        for chef in self.grid.chefs.values():
                            if not chef.is_full and chef.status != "COOKING":
                                self.assign_order(order, station, chef)
                                assigned = True
                                break
                    if assigned:
                        break
