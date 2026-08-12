import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Optional, Dict, Any, Tuple
import os

from .engine import SimulationEngine

class RestaurantGymEnv(gym.Env):
    """
    Gymnasium wrapper for the Restaurant Simulation Engine.
    Allows RL agents to schedule queued orders to kitchen stations.
    """
    metadata = {"render_modes": ["human"]}

    def __init__(self, config_path: str, max_queue_size: int = 5, render_mode: Optional[str] = None):
        super().__init__()
        self.config_path = config_path
        self.engine = SimulationEngine(config_path)
        self.max_queue_size = max_queue_size
        self.render_mode = render_mode
        
        # We need to know the number of stations to define action space
        self.engine.reset()
        self.num_stations = len(self.engine.grid.stations)
        self.station_ids = list(self.engine.grid.stations.keys())
        
        # Action Space: 0 = No-Op.
        # > 0: Assign Order i to Station j
        self.action_space = spaces.Discrete(1 + self.max_queue_size * self.num_stations)
        
        # Observation Space: Flattened 1D vector
        # 3 features per queued order (wait_time, theoretical_time, table_patience) * max_queue_size
        # 2 features per station (load, capacity) * num_stations
        # 1 feature for global kitchen load
        # Total = 3 * 5 + 2 * 4 + 1 = 24
        obs_dim = 3 * self.max_queue_size + 2 * self.num_stations + 1
        self.observation_space = spaces.Box(low=-1000.0, high=1000.0, shape=(obs_dim,), dtype=np.float32)

    def _get_obs(self) -> np.ndarray:
        obs = []
        
        # 1. Top queued orders
        for i in range(self.max_queue_size):
            if i < len(self.engine.order_queue):
                order = self.engine.order_queue[i]
                wait_time = self.engine.tick - order.timestamps["created_at"]
                table_patience = self.engine.grid.tables[order.table_id].patience
                obs.extend([float(wait_time), float(order.theoretical_time), float(table_patience)])
            else:
                obs.extend([0.0, 0.0, 0.0])
                
        # 2. Stations status
        for s_id in self.station_ids:
            station = self.engine.grid.stations[s_id]
            obs.extend([float(len(station.active_orders)), float(station.capacity)])
            
        # 3. Global kitchen load
        kitchen_load = sum(len(s.active_orders) for s in self.engine.grid.stations.values())
        obs.append(float(kitchen_load))
        
        return np.array(obs, dtype=np.float32)

    def _get_info(self) -> Dict[str, Any]:
        return {
            "tick": self.engine.tick,
            "queue_len": len(self.engine.order_queue),
            "completed": len(self.engine.completed_orders),
            "churned": self.engine.churned_customers
        }

    def reset(self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        self.engine.reset()
        
        # Fast forward simulation until there is at least one order in the queue
        # so the agent actually has something to do
        while len(self.engine.order_queue) == 0 and self.engine.tick < 1440:
            self.engine.step(actions=[])
            
        return self._get_obs(), self._get_info()

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        # Map action to simulation commands
        sim_actions = []
        if action > 0:
            order_idx = (action - 1) // self.num_stations
            station_idx = (action - 1) % self.num_stations
            
            if order_idx < len(self.engine.order_queue):
                order = self.engine.order_queue[order_idx]
                station_id = self.station_ids[station_idx]
                station = self.engine.grid.stations[station_id]
                
                # Check if station is full
                if not station.is_full:
                    # Find a free chef
                    free_chef = next((c for c in self.engine.grid.chefs.values() if not c.is_full), None)
                    if free_chef:
                        sim_actions.append({
                            "type": "ASSIGN",
                            "order_id": order.order_id,
                            "station_id": station_id,
                            "chef_id": free_chef.id
                        })

        # Capture state BEFORE step to calculate reward diff
        completed_before = len(self.engine.completed_orders)
        churned_before = self.engine.churned_customers

        # Apply action & advance tick
        # Note: If sim_actions is empty, it acts as a No-Op, and engine will progress cooking/waiters
        # BUT we must handle the manual assignment since engine._simple_fifo_scheduler is bypassed if actions != None
        if sim_actions:
            self._apply_manual_actions(sim_actions)
            
        # Step the engine (we pass empty list to bypass FIFO, but progress time)
        self.engine.step(actions=[]) 
        
        # Fast forward if queue is empty
        while len(self.engine.order_queue) == 0 and self.engine.tick < 1440:
            self.engine.step(actions=[])

        # Calculate Reward
        completed_after = len(self.engine.completed_orders)
        churned_after = self.engine.churned_customers
        
        reward = 0.0
        
        # Bonus for completed orders
        if completed_after > completed_before:
            # Let's say +10 per completed order
            reward += (completed_after - completed_before) * 10.0
            
        # Heavy penalty for churn
        if churned_after > churned_before:
            reward -= (churned_after - churned_before) * 50.0
            
        # Penalty for queue waiting time (small penalty per tick per waiting order)
        reward -= len(self.engine.order_queue) * 0.1
        
        # Penalty for cold food on the counter (READY but not DELIVERING)
        cold_food_count = 0
        for t in self.engine.grid.tables.values():
            for o in t.current_orders:
                if o.status == "READY":
                    cold_food_count += 1
        reward -= cold_food_count * 0.5
        
        # Invalid action penalty (tried to assign but couldn't)
        if action > 0 and not sim_actions:
            reward -= 1.0 # minor penalty for invalid assignment choice

        terminated = self.engine.tick >= 1440
        truncated = False
        
        return self._get_obs(), float(reward), terminated, truncated, self._get_info()

    def _apply_manual_actions(self, actions: list):
        for act in actions:
            if act["type"] == "ASSIGN":
                # Find the order in queue
                order = next((o for o in self.engine.order_queue if o.order_id == act["order_id"]), None)
                if order:
                    station = self.engine.grid.stations[act["station_id"]]
                    chef = self.engine.grid.chefs[act["chef_id"]]
                    
                    order.status = "PREPARING"
                    order.assigned_station_id = station.id
                    order.assigned_chef_id = chef.id
                    order.timestamps["kitchen_start"] = self.engine.tick
                    
                    # ML Snapshot (Zero Leakage)
                    order.station_load_at_start = len(station.active_orders)
                    order.kitchen_load_at_start = sum(len(s.active_orders) for s in self.engine.grid.stations.values())
                    order.chef_efficiency_at_start = chef.efficiency
                    order.day_tick_at_start = self.engine.tick
                    
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
                    order.predicted_time = self.engine.predictor.predict(features, len(self.engine.completed_orders))
                    
                    import random
                    mean_time = (order.theoretical_time / chef.efficiency) * (1 + 0.15 * order.station_load_at_start)
                    std_dev = mean_time * 0.1 # 10% standard deviation noise
                    order.actual_target_time = max(1.0, random.gauss(mean_time, std_dev))
                    
                    station.active_orders.append(order)
                    chef.active_orders.append(order)
                    chef.status = "COOKING"
                    
                    self.engine.order_queue.remove(order)
