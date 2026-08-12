from typing import List, Dict, Any
from .engine import SimulationEngine

class FIFOScheduler:
    def __init__(self, engine: SimulationEngine):
        self.engine = engine

    def step(self):
        # Tries to assign orders from queue based on arrival time (FIFO)
        # engine.order_queue is already sorted by arrival time by default
        sim_actions = []
        for order in self.engine.order_queue:
            assigned = False
            for station in self.engine.grid.stations.values():
                if not station.is_full:
                    # Find a free chef
                    for chef in self.engine.grid.chefs.values():
                        if not chef.is_full:
                            sim_actions.append({
                                "type": "ASSIGN",
                                "order_id": order.order_id,
                                "station_id": station.id,
                                "chef_id": chef.id
                            })
                            assigned = True
                            break
                if assigned:
                    break
        return sim_actions

class SPTScheduler:
    def __init__(self, engine: SimulationEngine):
        self.engine = engine

    def step(self):
        # Sort queue by Shortest Processing Time (theoretical_time)
        sorted_queue = sorted(self.engine.order_queue, key=lambda o: o.theoretical_time)
        
        sim_actions = []
        for order in sorted_queue:
            assigned = False
            for station in self.engine.grid.stations.values():
                if not station.is_full:
                    # Find a free chef
                    for chef in self.engine.grid.chefs.values():
                        if not chef.is_full:
                            sim_actions.append({
                                "type": "ASSIGN",
                                "order_id": order.order_id,
                                "station_id": station.id,
                                "chef_id": chef.id
                            })
                            assigned = True
                            break
                if assigned:
                    break
        return sim_actions
