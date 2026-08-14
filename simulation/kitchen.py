import random
from typing import TYPE_CHECKING, List, Optional
from .entities import Order, Station, Chef

if TYPE_CHECKING:
    from .engine import SimulationEngine

class KitchenManager:
    """
    Manages kitchen operations: station assignments, cook time sampling,
    ML feature snapshots, cooking progress, multi-stage progression, and equipment breakdowns.
    """
    def __init__(self, engine: 'SimulationEngine'):
        self.engine = engine

    def handle_breakdowns(self):
        """Manages random station breakdowns for difficulty level 3+."""
        if self.engine.difficulty_level >= 3:
            for s in self.engine.grid.stations.values():
                if s.is_broken:
                    s.broken_until -= 1
                    if s.broken_until <= 0:
                        s.is_broken = False
                else:
                    if random.random() < 0.002:  # 0.2% chance per tick to break down
                        s.is_broken = True
                        s.broken_until = random.randint(10, 30)

    def assign_order(self, order: Order, station: Station, chef: Chef, tick: int) -> bool:
        """
        Core assignment method: assigns an order to a station and chef, captures zero-leakage ML snapshot,
        predicts cook time, and samples true simulated cook duration.
        Used by both SimulationEngine (FIFO) and Gymnasium RL Environment.
        """
        if station.is_full or station.is_broken or chef.is_full:
            return False

        order.status = "PREPARING"
        order.assigned_station_id = station.id
        order.assigned_chef_id = chef.id
        order.timestamps["kitchen_start"] = tick

        # ML Feature Snapshot (Zero Leakage)
        order.station_load_at_start = len(station.active_orders)
        order.kitchen_load_at_start = sum(len(s.active_orders) for s in self.engine.grid.stations.values())
        order.chef_efficiency_at_start = chef.efficiency
        order.day_tick_at_start = tick

        # Fetch ML Model Prediction
        current_stage = order.stages[order.current_stage_idx]
        features = {
            "theoretical_time": current_stage["time"],
            "dish_type": order.dish_type,
            "station_type": station.type,
            "station_load_at_start": order.station_load_at_start,
            "kitchen_load_at_start": order.kitchen_load_at_start,
            "chef_efficiency_at_start": order.chef_efficiency_at_start,
            "day_tick_at_start": order.day_tick_at_start
        }
        order.predicted_time = self.engine.predictor.predict(features, len(self.engine.completed_orders))

        # Sample true physical cook time with batching efficiency and chef speed
        similar_items = sum(1 for o in station.active_orders if o.dish_type == order.dish_type)
        batch_multiplier = station.batch_efficiency_factor ** similar_items

        mean_time = (current_stage["time"] / chef.efficiency) * (1 + 0.15 * order.station_load_at_start) * batch_multiplier
        std_dev = mean_time * 0.1  # 10% standard deviation noise
        order.actual_target_time = max(1.0, random.gauss(mean_time, std_dev))

        # Update entity states
        station.active_orders.append(order)
        chef.active_orders.append(order)
        chef.status = "COOKING"

        if order in self.engine.order_queue:
            self.engine.order_queue.remove(order)

        return True

    def progress_cooking(self, tick: int):
        """
        Advances cooking timers on all active stations, handles stage transitions and completion.
        """
        for station in self.engine.grid.stations.values():
            for order in list(station.active_orders):
                time_cooking = tick - order.timestamps["kitchen_start"]

                # Check against the true physical time sampled at start
                if time_cooking >= order.actual_target_time:
                    # Stage finished
                    station.active_orders.remove(order)
                    chef = self.engine.grid.chefs.get(order.assigned_chef_id)
                    if chef and order in chef.active_orders:
                        chef.active_orders.remove(order)
                        if not chef.active_orders:
                            chef.status = "IDLE"

                    # Check for multi-stage progression
                    if order.current_stage_idx < len(order.stages) - 1:
                        order.current_stage_idx += 1
                        order.status = "QUEUED_STAGE"
                        self.engine.order_queue.append(order)
                    else:
                        order.status = "READY"
                        order.timestamps["kitchen_finish"] = tick

                        # Takeout auto-delivery if courier is already waiting
                        if order.is_takeout:
                            if tick >= order.courier_eta:
                                order.status = "SERVED"
                                order.timestamps["delivered_at"] = tick
                                self.engine.completed_orders.append(order)

                        # Record completed cook time to ML Data Collector
                        self.engine.collector.record_completed_order(order, time_cooking)

                        # Retrain ML model periodically on cumulative dataset
                        # Initial warm-up: train at 50, 100, 150, 200 orders.
                        # Steady state: train every 200 orders to avoid RL simulation bottleneck.
                        data_len = len(self.engine.collector.data)
                        should_train = False
                        if data_len <= 200 and data_len % 50 == 0:
                            should_train = True
                        elif data_len > 200 and data_len <= 2000 and data_len % 200 == 0:
                            should_train = True
                        elif data_len > 2000 and data_len % 1000 == 0:
                            should_train = True

                        if should_train and not getattr(self.engine, 'freeze_ml', False):
                            df = self.engine.collector.get_dataframe()
                            self.engine.predictor.train(df, auto_save=False)
