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

    def __init__(self, config_path: str = "config/default_layout.json", difficulty_level: int = 3, freeze_ml: bool = True, debug_mode: bool = False):
        super(RestaurantGymEnv, self).__init__()
        
        self.config_path = config_path
        self.difficulty_level = difficulty_level
        self.freeze_ml = freeze_ml
        self.debug_mode = debug_mode
        self.engine = SimulationEngine(config_path=self.config_path, difficulty_level=self.difficulty_level, freeze_ml=self.freeze_ml)
        self.max_queue_size = 15
        
        self.station_ids = list(self.engine.grid.stations.keys())
        self.num_stations = len(self.station_ids)
        
        # Action Space: 0 = No-Op, 1 to (max_queue_size * num_stations) = Assign order i to station j
        self.action_space = spaces.Discrete(1 + self.max_queue_size * self.num_stations)
        
        # Observation Space: Flattened 1D vector
        obs_dim = 8 * self.max_queue_size + 2 * self.num_stations + 1
        self.observation_space = spaces.Box(low=-1000.0, high=1000.0, shape=(obs_dim,), dtype=np.float32)
        
        # Debug Stats Collector
        self.debug_stats = {
            "total_steps": 0,
            "actions_noop": 0,
            "actions_valid_assign": 0,
            "actions_invalid_assign": 0,
            "station_busy_ticks": {s_id: 0 for s_id in self.station_ids},
            "station_full_ticks": {s_id: 0 for s_id in self.station_ids},
            "station_broken_ticks": {s_id: 0 for s_id in self.station_ids},
            "reward_breakdown": {
                "completed_bonus": 0.0,
                "churn_penalty": 0.0,
                "queue_wait_penalty": 0.0,
                "cold_food_penalty": 0.0,
                "courier_wait_penalty": 0.0,
                "subtick_assign_bonus": 0.0
            },
            "churn_events": [],
            "bottlenecks": []
        }

    def _get_obs(self) -> np.ndarray:
        obs = []
        
        # 1. Top queued orders
        for i in range(self.max_queue_size):
            if i < len(self.engine.order_queue):
                order = self.engine.order_queue[i]
                wait_time = self.engine.tick - order.timestamps["created_at"]
                
                # Fetch live ML prediction & uncertainty
                pred_time = getattr(order, 'predicted_time', None)
                if pred_time is None:
                    curr_stage = order.stages[order.current_stage_idx]
                    feat = {
                        "theoretical_time": curr_stage["time"],
                        "dish_type": order.dish_type,
                        "station_type": curr_stage["station_type"],
                        "station_load_at_start": 0,
                        "kitchen_load_at_start": sum(len(s.active_orders) for s in self.engine.grid.stations.values()),
                        "chef_efficiency_at_start": 1.0,
                        "day_tick_at_start": self.engine.tick
                    }
                    pred_time, pred_uncertainty = self.engine.predictor.predict_with_uncertainty(feat, len(self.engine.completed_orders))
                else:
                    pred_uncertainty = 1.5
                    
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
                    
                obs.extend([
                    float(wait_time),
                    float(order.stages[order.current_stage_idx]["time"]),
                    float(table_patience),
                    float(remaining_patience),
                    float(is_tk),
                    float(courier_diff),
                    float(pred_time),
                    float(pred_uncertainty)
                ])
            else:
                obs.extend([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
                
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
                    if station.type == req_station and not station.is_full and not getattr(station, 'is_broken', False):
                        mask[action_idx] = 1
        
        return mask

    def reset(self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        dl = self.difficulty_level
        if options and "difficulty_level" in options:
            dl = options["difficulty_level"]
        self.engine = SimulationEngine(config_path=self.config_path, difficulty_level=dl, freeze_ml=self.freeze_ml)
        self.difficulty_level = dl
        self.engine.reset()
        
        # Fast forward simulation until there is at least one order in the queue
        while len(self.engine.order_queue) == 0 and self.engine.tick < 1440:
            self.engine.step(actions=[])
            
        return self._get_obs(), self._get_info()

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        if self.debug_mode:
            self.debug_stats["total_steps"] += 1
            
        assigned_order = False
        subtick_reward = 0.0
        
        # 1. Process Discrete Assignment Action
        if action > 0:
            order_idx = (action - 1) // self.num_stations
            station_idx = (action - 1) % self.num_stations
            
            if order_idx < len(self.engine.order_queue):
                order = self.engine.order_queue[order_idx]
                station_id = self.station_ids[station_idx]
                station = self.engine.grid.stations[station_id]
                req_station_type = order.stages[order.current_stage_idx]["station_type"]
                
                # Check station validity & capacity
                if station.type == req_station_type and not station.is_full and not getattr(station, 'is_broken', False):
                    free_chef = next((c for c in self.engine.grid.chefs.values() if not c.is_full), None)
                    if free_chef:
                        self.engine.assign_order(order, station, chef=free_chef)
                        assigned_order = True
                        subtick_reward += 1.0 # Small immediate incentive for valid throughput assignment
                        if self.debug_mode:
                            self.debug_stats["actions_valid_assign"] += 1
                            self.debug_stats["reward_breakdown"]["subtick_assign_bonus"] += 1.0
            
            if not assigned_order and self.debug_mode:
                self.debug_stats["actions_invalid_assign"] += 1
        else:
            if self.debug_mode:
                self.debug_stats["actions_noop"] += 1

        # 2. Check if further assignments are possible on the SAME tick (Sub-tick multi-assignment)
        has_free_chef = any(not c.is_full for c in self.engine.grid.chefs.values())
        has_queue = len(self.engine.order_queue) > 0
        mask = self.action_masks()
        can_assign_more = assigned_order and has_free_chef and has_queue and np.any(mask[1:] > 0)
        
        if can_assign_more:
            # Continue on the same tick! Give the agent another chance to fill remaining chefs/stations
            terminated = self.engine.tick >= 1440
            truncated = False
            return self._get_obs(), float(subtick_reward), terminated, truncated, self._get_info()

        # 3. Advance the Simulation Clock by 1 Tick (No-Op or no more valid assignments possible)
        completed_before = len(self.engine.completed_orders)
        churned_before = self.engine.churned_customers
        
        self.engine.step(actions=[])
        
        # Fast-forward if queue is completely empty
        while len(self.engine.order_queue) == 0 and self.engine.tick < 1440:
            self.engine.step(actions=[])

        # 4. Calculate Tick End Rewards
        completed_after = len(self.engine.completed_orders)
        churned_after = self.engine.churned_customers
        
        reward = subtick_reward
        
        # Completed orders bonus
        if completed_after > completed_before:
            bonus = (completed_after - completed_before) * 20.0
            reward += bonus
            if self.debug_mode:
                self.debug_stats["reward_breakdown"]["completed_bonus"] += bonus
            
        # Heavy penalty for churn
        if churned_after > churned_before:
            penalty = (churned_after - churned_before) * 100.0
            reward -= penalty
            if self.debug_mode:
                self.debug_stats["reward_breakdown"]["churn_penalty"] += penalty
                self.debug_stats["churn_events"].append({
                    "tick": self.engine.tick,
                    "churned_count": (churned_after - churned_before)
                })
            
        # Queue waiting penalty
        wait_penalty = len(self.engine.order_queue) * 0.1
        reward -= wait_penalty
        if self.debug_mode:
            self.debug_stats["reward_breakdown"]["queue_wait_penalty"] += wait_penalty
        
        # Cold food on counter penalty
        cold_food_count = sum(
            1 for t in self.engine.grid.tables.values() if t.customers > 0
            for o in t.current_orders if o.status == "READY" and not t.is_fully_ready_for_service
        )
        cold_penalty = cold_food_count * 0.5
        reward -= cold_penalty
        if self.debug_mode:
            self.debug_stats["reward_breakdown"]["cold_food_penalty"] += cold_penalty
        
        # Courier waiting penalty
        courier_wait_count = sum(
            1 for o in self.engine.order_queue
            if o.is_takeout and o.courier_eta and self.engine.tick > o.courier_eta
        )
        courier_penalty = courier_wait_count * 1.0
        reward -= courier_penalty
        if self.debug_mode:
            self.debug_stats["reward_breakdown"]["courier_wait_penalty"] += courier_penalty

        # Track station stats in debug mode
        if self.debug_mode:
            for s_id, s in self.engine.grid.stations.items():
                if len(s.active_orders) > 0:
                    self.debug_stats["station_busy_ticks"][s_id] += 1
                if s.is_full:
                    self.debug_stats["station_full_ticks"][s_id] += 1
                if getattr(s, "is_broken", False):
                    self.debug_stats["station_broken_ticks"][s_id] += 1

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
