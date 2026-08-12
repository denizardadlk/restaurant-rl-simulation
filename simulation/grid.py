import os
import json
from typing import Dict, Any, List
from .entities import Table, Station, Chef, Waiter

class RestaurantGrid:
    def __init__(self, config_path: str):
        if not os.path.exists(config_path) and not os.path.isabs(config_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            alt_path = os.path.join(base_dir, config_path)
            if os.path.exists(alt_path):
                config_path = alt_path
        self.config_path = config_path
        self.width = 0
        self.height = 0
        self.tables: Dict[str, Table] = {}
        self.stations: Dict[str, Station] = {}
        self.waiters: Dict[str, Waiter] = {}
        self.chefs: Dict[str, Chef] = {}
        self.obstacles = set()
        
        self._load_config()

    def _load_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self.width = data["grid_size"]["width"]
        self.height = data["grid_size"]["height"]
        
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
            self.chefs[chef.id] = chef
            
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
