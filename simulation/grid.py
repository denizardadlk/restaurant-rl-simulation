import os
import json
from typing import Dict, Any, List, Optional
from .entities import Table, Station, Chef, Waiter, DeliveryCounter

class RestaurantGrid:
    def __init__(self, config_path: str):
        if not os.path.exists(config_path) and not os.path.isabs(config_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            for folder in ["layouts", "config"]:
                alt_path = os.path.join(base_dir, folder, os.path.basename(config_path))
                if os.path.exists(alt_path):
                    config_path = alt_path
                    break
                alt_path2 = os.path.join(base_dir, config_path)
                if os.path.exists(alt_path2):
                    config_path = alt_path2
                    break
        self.config_path = config_path
        self.width = 0
        self.height = 0
        self.kitchen_zone = {"x": 0, "y": 0, "w": 0, "h": 0}
        self.tables: Dict[str, Table] = {}
        self.stations: Dict[str, Station] = {}
        self.waiters: Dict[str, Waiter] = {}
        self.chefs: Dict[str, Chef] = {}
        self.delivery_counters: Dict[str, DeliveryCounter] = {}
        self.obstacles = set()
        
        self._load_config()

    @property
    def delivery_counter(self) -> Optional[DeliveryCounter]:
        """Backward-compatibility property returning the primary/first delivery counter."""
        if self.delivery_counters:
            return next(iter(self.delivery_counters.values()))
        return None

    def _load_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self.width = data["grid_size"]["width"]
        self.height = data["grid_size"]["height"]
        self.kitchen_zone = data.get("kitchen_zone", {"x": 0, "y": 0, "w": 0, "h": 0})
        
        for t_data in data.get("tables", []):
            table = Table(**t_data)
            self.tables[table.id] = table
            for dx in range(table.w):
                for dy in range(table.h):
                    self.obstacles.add((table.x + dx, table.y + dy))
            
        for s_data in data.get("stations", []):
            station = Station(**s_data)
            self.stations[station.id] = station
            self.obstacles.add((station.x, station.y))
            
        for w_data in data.get("waiters", []):
            waiter = Waiter(**w_data)
            self.waiters[waiter.id] = waiter
            
        for c_data in data.get("chefs", []):
            chef = Chef(**c_data)
            chef.capacity = max(4, getattr(chef, "capacity", 4))
            self.chefs[chef.id] = chef

        # Multi Delivery Counters (Pass Array)
        if "delivery_counters" in data and isinstance(data["delivery_counters"], list) and data["delivery_counters"]:
            for c_info in data["delivery_counters"]:
                counter = DeliveryCounter(**c_info)
                self.delivery_counters[counter.id] = counter
                self.obstacles.add((counter.x, counter.y))
        elif "delivery_counter" in data and data["delivery_counter"]:
            c_info = data["delivery_counter"]
            counter = DeliveryCounter(**c_info)
            self.delivery_counters[counter.id] = counter
            self.obstacles.add((counter.x, counter.y))
        else:
            # Fallback default location on kitchen zone edge
            kz = self.kitchen_zone
            cx = kz.get("x", max(0, self.width - 3))
            cy = kz.get("y", 0) + kz.get("h", self.height) // 2
            counter = DeliveryCounter(id="COUNTER_1", x=cx, y=cy)
            self.delivery_counters[counter.id] = counter
            self.obstacles.add((counter.x, counter.y))

        # Dedicated Takeout Counter (Courier Shelf)
        if "takeout_counter" in data and data["takeout_counter"]:
            self.takeout_counter = DeliveryCounter(**data["takeout_counter"])
            self.obstacles.add((self.takeout_counter.x, self.takeout_counter.y))
        else:
            kz = self.kitchen_zone
            cx = kz.get("x", max(0, self.width - 3))
            cy = max(0, kz.get("y", 0))
            self.takeout_counter = DeliveryCounter(id="TAKEOUT_SHELF", x=cx, y=cy, capacity=24)
            self.obstacles.add((self.takeout_counter.x, self.takeout_counter.y))

        # Dedicated Beverage Counter / Fridge (Independent drink fridge in the restaurant hall)
        if "beverage_counter" in data and data["beverage_counter"]:
            self.beverage_counter = DeliveryCounter(**data["beverage_counter"])
            self.obstacles.add((self.beverage_counter.x, self.beverage_counter.y))
        else:
            # Default location in the main hall
            bx = max(0, self.width // 2)
            by = max(0, self.height // 2)
            self.beverage_counter = DeliveryCounter(id="BEVERAGE_FRIDGE", x=bx, y=by, capacity=999)
            self.obstacles.add((self.beverage_counter.x, self.beverage_counter.y))
            
    def is_walkable(self, x: int, y: int) -> bool:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return False
        # In a real game, you might allow walking UP to a table but not THROUGH it.
        # For simplicity, if a cell is an obstacle, it's not walkable.
        # But actors need to reach the table/station. 
        # Usually, pathfinding goes to adjacent cells.
        if (x, y) in self.obstacles:
            return False
        return True
