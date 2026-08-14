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

class SimulationEngine:
    """
    Core orchestrator of the Restaurant Simulation.
    Coordinates customer lifecycles, kitchen operations, and waiter dispatches.
    """
    def __init__(self, config_path: str = "config/default_layout.json", difficulty_level: int = 3, freeze_ml: bool = False):
        self.difficulty_level = difficulty_level
        self.freeze_ml = freeze_ml
        self.tick = 0
        self.grid = RestaurantGrid(config_path)
        self.pathfinder = Pathfinder(self.grid)
        self.generator = OrderGenerator(difficulty_level=self.difficulty_level)
        
        # System State
        self.order_queue: List[Order] = []
        self.completed_orders: List[Order] = []
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
        self.churned_customers = 0

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
        
        # 2. Generate New Orders
        self._generate_orders()
            
        # 3. Apply Actions (FIFO if no explicit RL actions provided)
        if actions is None:
            self._simple_fifo_scheduler()
            
        # 4. Progress Cooking & Multi-stage transitions
        self.kitchen_manager.progress_cooking(self.tick)
        
        # 5. JIT Waiter Dispatching & Deliveries
        self.waiter_manager.manage_waiters(self.tick)

    def _generate_orders(self):
        """Generates new orders for available empty tables."""
        empty_tables = [table for table in self.grid.tables.values() if table.is_empty]
        new_orders = self.generator.generate_orders(self.tick, empty_tables)
        
        for order in new_orders:
            self.order_queue.append(order)
            if not order.is_takeout:
                table = self.grid.tables[order.table_id]
                if table.status == "EMPTY":
                    table.status = "WAITING_FOOD"
                    table.customers = table.capacity
                    table.patience = 20.0
                    table.current_orders = []
                table.current_orders.append(order)

    def _simple_fifo_scheduler(self):
        """A simple FIFO fallback scheduler when RL agent is not attached."""
        for order in list(self.order_queue):
            if order.status in ["QUEUED", "QUEUED_STAGE"]:
                req_station_type = order.stages[order.current_stage_idx]["station_type"]
                assigned = False
                for station in self.grid.stations.values():
                    if station.type == req_station_type and not station.is_full and not station.is_broken:
                        for chef in self.grid.chefs.values():
                            if not chef.is_full:
                                self.assign_order(order, station, chef)
                                assigned = True
                                break
                    if assigned:
                        break
