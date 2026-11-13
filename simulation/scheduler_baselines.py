from typing import List, Dict, Any
from .engine import SimulationEngine

class FIFOScheduler:
    def __init__(self, engine: SimulationEngine):
        self.engine = engine

    def step(self):
        # Tries to assign orders from queue based on arrival time (FIFO)
        # engine.order_queue is already sorted by arrival time by default
        sim_actions = []
        chef_loads = {c.id: len(c.active_orders) for c in self.engine.grid.chefs.values()}
        station_loads = {s.id: len(s.active_orders) for s in self.engine.grid.stations.values()}

        for order in self.engine.order_queue:
            if order.status not in ["QUEUED", "QUEUED_STAGE"]:
                continue
            assigned = False
            req_station = order.stages[order.current_stage_idx]["station_type"]
            for station in self.engine.grid.stations.values():
                if station.type == req_station and not station.is_broken and station_loads[station.id] < station.capacity:
                    # Find a free chef (prefer least loaded chef)
                    avail_chefs = [c for c in self.engine.grid.chefs.values() if chef_loads[c.id] < c.capacity and c.status == "IDLE" and c.current_task is None and c.busy_until <= self.engine.tick]
                    avail_chefs.sort(key=lambda c: chef_loads[c.id])
                    for chef in avail_chefs:
                        sim_actions.append({
                            "type": "ASSIGN",
                            "order_id": order.order_id,
                            "station_id": station.id,
                            "chef_id": chef.id
                        })
                        chef_loads[chef.id] += 1
                        station_loads[station.id] += 1
                        assigned = True
                        break
                if assigned:
                    break
        return sim_actions

class SPTScheduler:
    def __init__(self, engine: SimulationEngine):
        self.engine = engine

    def step(self):
        # Sort queue by Shortest Processing Time (theoretical_time ascending)
        sorted_queue = sorted(
            [o for o in self.engine.order_queue if o.status in ["QUEUED", "QUEUED_STAGE"]],
            key=lambda o: o.theoretical_time
        )
        sim_actions = []
        chef_loads = {c.id: len(c.active_orders) for c in self.engine.grid.chefs.values()}
        station_loads = {s.id: len(s.active_orders) for s in self.engine.grid.stations.values()}

        for order in sorted_queue:
            assigned = False
            req_station = order.stages[order.current_stage_idx]["station_type"]
            for station in self.engine.grid.stations.values():
                if station.type == req_station and not station.is_broken and station_loads[station.id] < station.capacity:
                    avail_chefs = [c for c in self.engine.grid.chefs.values() if chef_loads[c.id] < c.capacity and c.status == "IDLE" and c.current_task is None and c.busy_until <= self.engine.tick]
                    avail_chefs.sort(key=lambda c: chef_loads[c.id])
                    for chef in avail_chefs:
                        sim_actions.append({
                            "type": "ASSIGN",
                            "order_id": order.order_id,
                            "station_id": station.id,
                            "chef_id": chef.id
                        })
                        chef_loads[chef.id] += 1
                        station_loads[station.id] += 1
                        assigned = True
                        break
                if assigned:
                    break
        return sim_actions

class LPTScheduler:
    def __init__(self, engine: SimulationEngine):
        self.engine = engine

    def step(self):
        # Sort queue by Longest Processing Time (theoretical_time descending)
        sorted_queue = sorted(
            [o for o in self.engine.order_queue if o.status in ["QUEUED", "QUEUED_STAGE"]],
            key=lambda o: o.theoretical_time,
            reverse=True
        )
        sim_actions = []
        chef_loads = {c.id: len(c.active_orders) for c in self.engine.grid.chefs.values()}
        station_loads = {s.id: len(s.active_orders) for s in self.engine.grid.stations.values()}

        for order in sorted_queue:
            assigned = False
            req_station = order.stages[order.current_stage_idx]["station_type"]
            for station in self.engine.grid.stations.values():
                if station.type == req_station and not station.is_broken and station_loads[station.id] < station.capacity:
                    avail_chefs = [c for c in self.engine.grid.chefs.values() if chef_loads[c.id] < c.capacity and c.status == "IDLE" and c.current_task is None and c.busy_until <= self.engine.tick]
                    avail_chefs.sort(key=lambda c: chef_loads[c.id])
                    for chef in avail_chefs:
                        sim_actions.append({
                            "type": "ASSIGN",
                            "order_id": order.order_id,
                            "station_id": station.id,
                            "chef_id": chef.id
                        })
                        chef_loads[chef.id] += 1
                        station_loads[station.id] += 1
                        assigned = True
                        break
                if assigned:
                    break
        return sim_actions

class MinPatienceScheduler:
    def __init__(self, engine: SimulationEngine):
        self.engine = engine

    def step(self):
        # Sort queue by table patience ascending (prioritize tables losing patience)
        sorted_queue = sorted(
            [o for o in self.engine.order_queue if o.status in ["QUEUED", "QUEUED_STAGE"]],
            key=lambda o: self.engine.grid.tables[o.table_id].patience if o.table_id in self.engine.grid.tables else 100.0
        )
        sim_actions = []
        chef_loads = {c.id: len(c.active_orders) for c in self.engine.grid.chefs.values()}
        station_loads = {s.id: len(s.active_orders) for s in self.engine.grid.stations.values()}

        for order in sorted_queue:
            assigned = False
            req_station = order.stages[order.current_stage_idx]["station_type"]
            for station in self.engine.grid.stations.values():
                if station.type == req_station and not station.is_broken and station_loads[station.id] < station.capacity:
                    avail_chefs = [c for c in self.engine.grid.chefs.values() if chef_loads[c.id] < c.capacity and c.status == "IDLE" and c.current_task is None and c.busy_until <= self.engine.tick]
                    avail_chefs.sort(key=lambda c: chef_loads[c.id])
                    for chef in avail_chefs:
                        sim_actions.append({
                            "type": "ASSIGN",
                            "order_id": order.order_id,
                            "station_id": station.id,
                            "chef_id": chef.id
                        })
                        chef_loads[chef.id] += 1
                        station_loads[station.id] += 1
                        assigned = True
                        break
                if assigned:
                    break
        return sim_actions
