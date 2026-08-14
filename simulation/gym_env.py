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

    def __init__(self, config_path: str = "config/default_layout.json", difficulty_level: int = 3):
        super(RestaurantGymEnv, self).__init__()
        
        self.config_path = config_path
        self.difficulty_level = difficulty_level
        self.engine = SimulationEngine(config_path=self.config_path, difficulty_level=self.difficulty_level)
        self.max_queue_size = 15
        
        self.station_ids = list(self.engine.grid.stations.keys())
        self.num_stations = len(self.station_ids)
        
        # Action Space: 0 = No-Op, 1 to (max_queue_size * num_stations) = Assign order i to station j
        self.action_space = spaces.Discrete(1 + self.max_queue_size * self.num_stations)
        
        # Observation Space: Flattened 1D vector
        # 8 features per queued order (wait_time, theoretical_time, table_patience, remaining_patience, is_takeout, courier_eta_diff, predicted_time, prediction_uncertainty) * max_queue_size
        # 2 features per station (load, capacity) * num_stations
        # 1 feature for global kitchen load
        # Total = 8 * 15 + 2 * num_stations + 1
        obs_dim = 8 * self.max_queue_size + 2 * self.num_stations + 1
        self.observation_space = spaces.Box(low=-1000.0, high=1000.0, shape=(obs_dim,), dtype=np.float32)

    def _get_obs(self) -> np.ndarray:
        obs = []
        
        # 1. Top queued orders
        for i in range(self.max_queue_size):
            if i < len(self.engine.order_queue):
                order = self.engine.order_queue[i]
                wait_time = self.engine.tick - order.timestamps["created_at"]
                if order.is_takeout:
                    table_patience = 0.0
                    remaining_patience = 0.0
                    is_tk = 1.0
                    courier_diff = order.courier_eta - self.engine.tick if order.courier_eta else 0.0
                else:
                    table_patience = self.engine.grid.tables[order.table_id].patience
                    remaining_patience = table_patience - wait_time
                    is_tk = 0.0
                    courier_diff = 0.0
                    
                # Fetch fast ML Prediction (use cached or theoretical if not available)
                stage_time = float(order.stages[order.current_stage_idx]["time"])
                pred_time = order.predicted_time if order.predicted_time is not None else stage_time
                pred_uncert = 1.0 if order.predicted_time is None else 0.2

                obs.extend([
                    float(wait_time),
                    stage_time,
                    float(table_patience),
                    float(remaining_patience),
                    float(is_tk),
                    float(courier_diff),
                    float(pred_time),
                    float(pred_uncert)
                ])
            else:
                obs.extend([0.0] * 8)
                
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

    def action_masks(self) -> np.ndarray:
        """
        Returns a boolean array representing valid actions for MaskablePPO.
        1 = valid, 0 = invalid.
        """
        mask = np.zeros(self.action_space.n, dtype=np.int8)
        mask[0] = 1 # No-Op is always valid
        
        # Check if there is any free chef globally
        has_free_chef = any(not c.is_full for c in self.engine.grid.chefs.values())
        
        if not has_free_chef:
            return mask
            
        queue_len = len(self.engine.order_queue)
        
        for i in range(self.max_queue_size):
            if i < queue_len:
                order = self.engine.order_queue[i]
                req_station = order.stages[order.current_stage_idx]["station_type"]
                for j, s_id in enumerate(self.station_ids):
                    action_idx = 1 + i * self.num_stations + j
                    station = self.engine.grid.stations[s_id]
                    if station.type == req_station and not station.is_full and not station.is_broken:
                        mask[action_idx] = 1
        
        return mask

    def reset(self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        # Use existing difficulty level unless overridden in options
        dl = self.difficulty_level
        if options and "difficulty_level" in options:
            dl = options["difficulty_level"]
        self.engine = SimulationEngine(config_path=self.config_path, difficulty_level=dl)
        self.difficulty_level = dl
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
            # Increased base bonus, implicitly encouraging JIT sync to avoid cold food
            reward += (completed_after - completed_before) * 20.0
            
        # Heavy penalty for churn
        if churned_after > churned_before:
            reward -= (churned_after - churned_before) * 100.0
            
        # Penalty for queue waiting time (small penalty per tick per waiting order)
        reward -= len(self.engine.order_queue) * 0.1
        
        # Penalty for cold food on the counter (READY but not DELIVERING) -> Group Sync Penalty
        cold_food_count = sum(
            1 for t in self.engine.grid.tables.values() if t.customers > 0
            for o in t.current_orders if o.status == "READY" and not t.is_fully_ready_for_service
        )
        reward -= cold_food_count * 0.5
        
        # Penalty for courier waiting
        courier_wait_count = 0
        for o in self.engine.order_queue:
            if o.is_takeout and o.courier_eta and self.engine.tick > o.courier_eta:
                courier_wait_count += 1
        reward -= courier_wait_count * 1.0
        
        # Invalid action penalty (tried to assign but couldn't)
        if action > 0 and not sim_actions:
            reward -= 1.0 # minor penalty for invalid assignment choice

        terminated = self.engine.tick >= 1440
        truncated = False
        
        return self._get_obs(), float(reward), terminated, truncated, self._get_info()

    def _apply_manual_actions(self, actions: list):
        for act in actions:
            if act["type"] == "ASSIGN":
                order = next((o for o in self.engine.order_queue if o.order_id == act["order_id"]), None)
                if order:
                    station = self.engine.grid.stations.get(act["station_id"])
                    chef = self.engine.grid.chefs.get(act["chef_id"])
                    if station and chef:
                        self.engine.assign_order(order, station, chef)

