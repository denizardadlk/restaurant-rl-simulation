import gymnasium as gym
from gymnasium import spaces
import numpy as np
import os
from typing import Optional, Dict, Any, List

from simulation.engine import SimulationEngine
from simulation.entities import Waiter, Table, Order, DeliveryCounter

class WaiterGymEnv(gym.Env):
    """
    Gymnasium Environment for training the Waiter RL Agent.
    In this environment, the Kitchen dispatch and Chef movements are held fixed / deterministic,
    while the Waiter Agent learns the optimal policy for:
      - JIT Counter Pickup vs Table Order Taking vs Table Cleaning vs No-Op.
    """
    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        config_path: Optional[str] = None,
        max_ticks: int = 1000,
        debug_mode: bool = False,
        difficulty_level: int = 2,
        time_config_path: Optional[str] = None
    ):
        super().__init__()
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "..", "config", "default_layout.json")

        self.config_path = config_path
        self.max_ticks = max_ticks
        self.debug_mode = debug_mode
        self.difficulty_level = difficulty_level
        self.time_config_path = time_config_path

        # Initialize Simulation Engine with fixed kitchen and automatic order generation
        self.engine = SimulationEngine(
            config_path=self.config_path,
            auto_generate_orders=True,
            difficulty_level=self.difficulty_level,
            enable_rl_waiter=True,
            time_config_path=self.time_config_path
        )
        self.engine.freeze_ml = True  # Freeze ML to keep kitchen deterministic during waiter training

        self.table_keys = sorted(list(self.engine.grid.tables.keys()))
        counters_map = dict(self.engine.grid.delivery_counters)
        if getattr(self.engine.grid, "beverage_counter", None):
            counters_map[self.engine.grid.beverage_counter.id] = self.engine.grid.beverage_counter
        self.counter_keys = sorted(list(counters_map.keys()))
        self.waiter_keys = sorted(list(self.engine.grid.waiters.keys()))

        self.num_tables = len(self.table_keys)
        self.num_counters = max(1, len(self.counter_keys))
        self.num_waiters = max(1, len(self.waiter_keys))

        # Action Space:
        # 0: NO-OP (Let idle or maintain current substate)
        # 1 .. num_counters: Go to Counter K and pick up food for readiest table
        # num_counters + 1 .. num_counters + num_tables: Go to Table T to Take Order
        # num_counters + num_tables + 1 .. num_counters + 2 * num_tables: Go to Table T to Clean
        self.num_actions = 1 + self.num_counters + (2 * self.num_tables)
        self.action_space = spaces.Discrete(self.num_actions)

        # Observation Space:
        # Waiter features (4 per waiter: x, y, is_busy, tray_load)
        # Counter features (2 per counter: ready_count, max_cold_time)
        # Table features (3 per table: status_code, patience_ratio, orders_count)
        self.obs_dim = (self.num_waiters * 4) + (self.num_counters * 2) + (self.num_tables * 3)
        self.observation_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(self.obs_dim,),
            dtype=np.float32
        )

        self.debug_stats = {
            "served_orders": 0,
            "cold_food_penalty": 0.0,
            "wait_order_penalty": 0.0,
            "dirty_table_penalty": 0.0,
            "churn_penalty": 0.0,
            "total_reward": 0.0
        }

    def _get_obs(self) -> np.ndarray:
        obs = []
        w_grid = max(1, self.engine.grid.width)
        h_grid = max(1, self.engine.grid.height)

        # 1. Waiter Features
        for w_id in self.waiter_keys:
            w = self.engine.grid.waiters.get(w_id)
            if w:
                obs.extend([
                    w.x / float(w_grid),
                    w.y / float(h_grid),
                    1.0 if (w.status != "IDLE" or w.current_task is not None) else 0.0,
                    len(w.carrying_orders) / float(max(1, w.tray_capacity))
                ])
            else:
                obs.extend([0.0, 0.0, 0.0, 0.0])

        # 2. Counter Features
        for c_id in self.counter_keys:
            c = self.engine.grid.delivery_counters.get(c_id) or (self.engine.grid.beverage_counter if getattr(self.engine.grid, "beverage_counter", None) and c_id == self.engine.grid.beverage_counter.id else None)
            if c:
                max_cold = 0.0
                for o in c.ready_orders:
                    cold_t = o.get_cold_time(self.engine.tick, grace_period=5.0)
                    if cold_t > max_cold:
                        max_cold = cold_t
                obs.extend([
                    min(1.0, len(c.ready_orders) / float(max(1, c.capacity))),
                    min(1.0, max_cold / 30.0)
                ])
            else:
                obs.extend([0.0, 0.0])

        # 3. Table Features
        status_map = {"EMPTY": 0.0, "WAITING_ORDER": 0.25, "WAITING_FOOD": 0.5, "EATING": 0.75, "DIRTY": 1.0}
        for t_id in self.table_keys:
            t = self.engine.grid.tables.get(t_id)
            if t:
                obs.extend([
                    status_map.get(t.status, 0.0),
                    min(1.0, max(0.0, t.patience / 30.0)),
                    min(1.0, len(t.current_orders) / 8.0)
                ])
            else:
                obs.extend([0.0, 0.0, 0.0])

        return np.array(obs, dtype=np.float32)

    def action_masks(self) -> np.ndarray:
        """
        Returns valid actions for Waiter RL agent.
        Only allows picking up from counters with ready food, taking orders from WAITING_ORDER tables,
        or cleaning DIRTY tables when idle waiters exist.
        """
        mask = np.zeros(self.num_actions, dtype=np.int8)

        idle_waiters = self.engine.waiter_manager._get_idle_waiters(self.engine.tick)
        if not idle_waiters:
            mask[0] = 1 # Only No-Op if all waiters are busy
            return mask

        # Counters with ready food or beverages
        for c_idx, c_id in enumerate(self.counter_keys):
            c = self.engine.grid.delivery_counters.get(c_id) or (self.engine.grid.beverage_counter if getattr(self.engine.grid, "beverage_counter", None) and c_id == self.engine.grid.beverage_counter.id else None)
            if c and len(c.ready_orders) > 0:
                mask[1 + c_idx] = 1

        # Tables needing order
        for t_idx, t_id in enumerate(self.table_keys):
            t = self.engine.grid.tables.get(t_id)
            if t and t.status == "WAITING_ORDER":
                mask[1 + self.num_counters + t_idx] = 1

        # Tables needing cleaning
        for t_idx, t_id in enumerate(self.table_keys):
            t = self.engine.grid.tables.get(t_id)
            if t and t.status == "DIRTY":
                mask[1 + self.num_counters + self.num_tables + t_idx] = 1

        # If at least one task is available, mask out No-Op so waiters don't idle while tasks wait
        if np.any(mask[1:] > 0):
            mask[0] = 0
        else:
            mask[0] = 1

        return mask

    def reset(self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None):
        super().reset(seed=seed)
        self.engine.reset()
        self.engine.enable_rl_waiter = True
        if self.debug_mode:
            self.debug_stats = {
                "served_orders": 0,
                "cold_food_penalty": 0.0,
                "wait_order_penalty": 0.0,
                "dirty_table_penalty": 0.0,
                "churn_penalty": 0.0,
                "total_reward": 0.0
            }
        return self._get_obs(), {}

    def _execute_waiter_action(self, action: int) -> bool:
        if action == 0:
            return False

        idle_waiters = self.engine.waiter_manager._get_idle_waiters(self.engine.tick)
        if not idle_waiters:
            return False

        assigned = False

        # Action 1 .. num_counters: Pick up from specific counter
        if 1 <= action <= self.num_counters:
            c_idx = action - 1
            if c_idx < len(self.counter_keys):
                c_id = self.counter_keys[c_idx]
                counter = self.engine.grid.delivery_counters.get(c_id) or (self.engine.grid.beverage_counter if getattr(self.engine.grid, "beverage_counter", None) and c_id == self.engine.grid.beverage_counter.id else None)
                if counter and counter.ready_orders:
                    # Pick closest idle waiter to this counter
                    idle_waiters.sort(key=lambda w: self.engine.pathfinder.get_distance((w.x, w.y), (counter.x, counter.y)))
                    waiter = idle_waiters[0]
                    # Check if ready order is takeout vs table
                    order = counter.ready_orders[0]
                    if order.is_takeout:
                        takeout_drinks = [o for o in counter.ready_orders if o.is_takeout]
                        self.engine.waiter_manager._dispatch_takeout_drink_transfer(waiter, takeout_drinks, self.engine.tick)
                        assigned = True
                    else:
                        table = self.engine.grid.tables.get(order.table_id or "")
                        if table:
                            self.engine.waiter_manager._dispatch_food_delivery(waiter, order, table, self.engine.tick)
                            assigned = True

        # Action num_counters + 1 .. num_counters + num_tables: Take order from Table T
        elif self.num_counters < action <= self.num_counters + self.num_tables:
            t_idx = action - self.num_counters - 1
            if t_idx < len(self.table_keys):
                table = self.engine.grid.tables.get(self.table_keys[t_idx])
                if table and table.status == "WAITING_ORDER":
                    idle_waiters.sort(key=lambda w: self.engine.pathfinder.get_distance((w.x, w.y), (table.x, table.y)))
                    waiter = idle_waiters[0]
                    self.engine.waiter_manager._dispatch_take_order(waiter, table, self.engine.tick)
                    assigned = True

        # Action num_counters + num_tables + 1 ..: Clean Table T
        else:
            t_idx = action - self.num_counters - self.num_tables - 1
            if t_idx < len(self.table_keys):
                table = self.engine.grid.tables.get(self.table_keys[t_idx])
                if table and table.status == "DIRTY":
                    idle_waiters.sort(key=lambda w: self.engine.pathfinder.get_distance((w.x, w.y), (table.x, table.y)))
                    waiter = idle_waiters[0]
                    self.engine.waiter_manager._dispatch_clean_table(waiter, table, self.engine.tick)
                    assigned = True

        return assigned

    def step(self, action: int):
        # 1. Execute RL Waiter Action
        assigned = self._execute_waiter_action(action)
        subtick_reward = 0.5 if assigned else 0.0

        # Check if more waiter assignments are possible on the SAME tick (Sub-tick multi-assignment)
        idle_waiters = self.engine.waiter_manager._get_idle_waiters(self.engine.tick)
        mask = self.action_masks()
        can_assign_more = assigned and len(idle_waiters) > 0 and np.any(mask[1:] > 0)

        if can_assign_more:
            terminated = self.engine.tick >= self.max_ticks
            truncated = False
            info = {
                "tick": self.engine.tick,
                "completed_orders": len(self.engine.completed_orders),
                "churned_customers": self.engine.churned_customers
            }
            return self._get_obs(), float(subtick_reward), terminated, truncated, info

        # 2. Advance Simulation Step
        served_before = len(self.engine.completed_orders)
        churn_before = self.engine.churned_customers

        # Kitchen scheduling runs deterministically via fixed heuristic/engine step
        self.engine.step()

        served_after = len(self.engine.completed_orders)
        churn_after = self.engine.churned_customers

        # 3. Calculate Normalized Reward
        reward = subtick_reward

        # +5.0 per served order
        newly_served = served_after - served_before
        if newly_served > 0:
            reward += newly_served * 5.0
            if self.debug_mode:
                self.debug_stats["served_orders"] += newly_served

        # Cold food on counter penalty (Grace period: 5 ticks, normalized, capped to 3.0)
        raw_cold = 0.0
        all_cnts = list(self.engine.grid.delivery_counters.values())
        if getattr(self.engine.grid, "takeout_counter", None):
            all_cnts.append(self.engine.grid.takeout_counter)
        for counter in all_cnts:
            for o in counter.ready_orders:
                cold_t = o.get_cold_time(self.engine.tick, grace_period=5.0)
                if cold_t > 0.0:
                    raw_cold += cold_t
        cold_pen = min(3.0, raw_cold * 0.02)
        reward -= cold_pen
        if self.debug_mode:
            self.debug_stats["cold_food_penalty"] += cold_pen

        # Waiting order delay penalty (normalized, capped to 2.0)
        waiting_orders = sum(1 for t in self.engine.grid.tables.values() if t.status == "WAITING_ORDER")
        wait_pen = min(2.0, waiting_orders * 0.05)
        reward -= wait_pen
        if self.debug_mode:
            self.debug_stats["wait_order_penalty"] += wait_pen

        # Dirty table delay penalty (normalized, capped to 2.0)
        dirty_tables = sum(1 for t in self.engine.grid.tables.values() if t.status == "DIRTY")
        dirty_pen = min(2.0, dirty_tables * 0.05)
        reward -= dirty_pen
        if self.debug_mode:
            self.debug_stats["dirty_table_penalty"] += dirty_pen

        # Churned customers penalty (-10.0 per customer)
        newly_churned = churn_after - churn_before
        if newly_churned > 0:
            churn_pen = newly_churned * 10.0
            reward -= churn_pen
            if self.debug_mode:
                self.debug_stats["churn_penalty"] += churn_pen

        if self.debug_mode:
            self.debug_stats["total_reward"] += reward

        terminated = self.engine.tick >= self.max_ticks
        truncated = False
        info = {
            "tick": self.engine.tick,
            "completed_orders": len(self.engine.completed_orders),
            "churned_customers": self.engine.churned_customers
        }
        if self.debug_mode:
            info["debug_stats"] = self.debug_stats

        return self._get_obs(), float(reward), terminated, truncated, info
