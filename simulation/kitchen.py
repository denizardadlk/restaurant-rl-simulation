import random
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from .entities import Order, Station, Chef, DeliveryCounter

if TYPE_CHECKING:
    from .engine import SimulationEngine

class KitchenManager:
    """
    Manages kitchen operations: A* step-by-step chef movement between stations and delivery counter,
    station assignments, cook time sampling, ML feature snapshots, cooking progress,
    multi-stage progression, and equipment breakdowns.
    """
    def __init__(self, engine: 'SimulationEngine'):
        self.engine = engine
        self.fryer_inventory: Dict[str, int] = {"Patates": 0, "Sogan_Halkasi": 0}
        self.doner_inventory: int = 0

    def fulfill_from_fryer_stock(self, tick: int):
        """Immediately fulfills queued fries/onion rings/fried baskets if ready batch stock exists."""
        for order in list(self.engine.order_queue):
            if order.status not in ["QUEUED", "QUEUED_STAGE"]:
                continue

            fulfilled = False
            if order.dish_type == "Patates" and self.fryer_inventory.get("Patates", 0) > 0:
                self.fryer_inventory["Patates"] -= 1
                fulfilled = True
            elif order.dish_type in ["Sogan_Halkasi", "Sogan Halkasi"] and self.fryer_inventory.get("Sogan_Halkasi", 0) > 0:
                self.fryer_inventory["Sogan_Halkasi"] -= 1
                fulfilled = True
            elif order.dish_type in ["Fried_Basket", "Fried Basket"]:
                if self.fryer_inventory.get("Patates", 0) > 0 and self.fryer_inventory.get("Sogan_Halkasi", 0) > 0:
                    self.fryer_inventory["Patates"] -= 1
                    self.fryer_inventory["Sogan_Halkasi"] -= 1
                    fulfilled = True

            if fulfilled:
                if order in self.engine.order_queue:
                    self.engine.order_queue.remove(order)
                target_counter = self._find_best_counter_for_chef(chef=None, order=order)
                self._drop_order_at_counter(chef=None, order=order, tick=tick, counter=target_counter)

    def fulfill_from_doner_stock(self, tick: int):
        """If sliced doner meat stock exists, immediately completes the DONER cutting stage."""
        for order in list(self.engine.order_queue):
            if order.status not in ["QUEUED", "QUEUED_STAGE"]:
                continue
            if order.dish_type == "Doner" and order.current_stage_idx < len(order.stages):
                if order.stages[order.current_stage_idx]["station_type"] == "DONER" and self.doner_inventory > 0:
                    self.doner_inventory -= 1
                    if order.current_stage_idx < len(order.stages) - 1:
                        order.current_stage_idx += 1
                        order.status = "QUEUED_STAGE"
                    else:
                        if order in self.engine.order_queue:
                            self.engine.order_queue.remove(order)
                        target_counter = self._find_best_counter_for_chef(chef=None, order=order)
                        self._drop_order_at_counter(chef=None, order=order, tick=tick, counter=target_counter)

    def handle_breakdowns(self):
        """Station breakdowns cancelled completely as requested."""
        pass

    def sample_cook_time(self, order: Order, station: Station, chef: Optional[Chef] = None) -> float:
        """Samples the true physical cook time for the order's current stage with batching and Gamma noise."""
        current_stage = order.stages[order.current_stage_idx]
        cook_cfg = self.engine.time_config.cooking_mechanics
        load_penalty = cook_cfg.get("station_load_penalty_factor", 0.02)
        alpha = cook_cfg.get("gamma_distribution_alpha", 25.0)

        similar_items = sum(1 for o in station.active_orders if o.dish_type == order.dish_type)
        batch_multiplier = station.batch_efficiency_factor ** similar_items

        station_load = len(station.active_orders)
        efficiency = getattr(chef, "efficiency", 1.0) if chef else 1.0
        mean_time = (current_stage["time"] / max(0.1, efficiency)) * (1 + load_penalty * station_load) * batch_multiplier
        beta = mean_time / alpha
        return max(0.5, random.gammavariate(alpha, beta))

    def assign_order(self, order: Order, station: Station, chef: Chef, tick: int) -> bool:
        """
        Core assignment method: assigns an order to a station and chef, captures zero-leakage ML snapshot,
        predicts cook time, samples physical duration, and routes chef to station via A*.
        """
        if station.is_full or station.is_broken or chef.is_full:
            return False

        order.status = "PREPARING"
        order.assigned_station_id = station.id
        order.assigned_chef_id = chef.id

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
        order.actual_target_time = self.sample_cook_time(order, station, chef)

        # Update entity states
        station.active_orders.append(order)
        chef.active_orders.append(order)

        if order in self.engine.order_queue:
            self.engine.order_queue.remove(order)

        # Step chef to station along path with 30m/min
        raw_path = self.engine.pathfinder.get_path((chef.x, chef.y), (station.x, station.y))
        chef.path = raw_path[1:] if len(raw_path) > 1 else []
        self._step_chef_along_path(chef)
        chef.x, chef.y = station.x, station.y
        order.timestamps["kitchen_start"] = tick

        prep_dur = self.engine.time_config.chef_config.get("station_prep_duration", 1.0)

        if station.type in ["OVEN", "GRILL", "STOVE", "FRYER", "TOASTER"]:
            if prep_dur > 0:
                chef.status = "COOKING"
                chef.busy_until = tick + prep_dur
                chef.current_task = {
                    "type": "PREP_AUTO",
                    "order_id": order.order_id,
                    "station_id": station.id,
                    "substate": "PREP_AUTO",
                    "finish_tick": tick + prep_dur
                }
            else:
                self._reset_chef_to_idle(chef)
        else:
            # Manual PREP & DONER: Chef actively cooks
            chef.status = "COOKING"
            chef.current_task = {
                "type": "COOK",
                "order_id": order.order_id,
                "station_id": station.id,
                "substate": "COOKING"
            }

        return True

    def _step_chef_along_path(self, chef: Chef):
        speed = int(self.engine.time_config.walking_speed * getattr(chef, "speed", 1.0))
        for _ in range(max(1, speed)):
            if chef.path:
                next_cell = chef.path.pop(0)
                if next_cell == (chef.x, chef.y) and chef.path:
                    next_cell = chef.path.pop(0)
                chef.x, chef.y = next_cell
            else:
                break

    def _reset_chef_to_idle(self, chef: Chef):
        chef.current_task = None
        chef.path.clear()
        chef.carrying_orders.clear()

        # 1. First prioritize starting auto-cooking dishes (OVEN, GRILL, STOVE, FRYER, TOASTER) - Set & Forget!
        unstarted_auto = [
            o for o in list(chef.active_orders)
            if o.timestamps.get("kitchen_start") is None
            and o.assigned_station_id in self.engine.grid.stations
            and self.engine.grid.stations[o.assigned_station_id].type in ["OVEN", "GRILL", "STOVE", "FRYER", "TOASTER"]
        ]
        if unstarted_auto:
            next_order = unstarted_auto[0]
            station = self.engine.grid.stations[next_order.assigned_station_id]
            if (chef.x, chef.y) == (station.x, station.y):
                matching = [o for o in unstarted_auto if o.assigned_station_id == station.id]
                for o in matching:
                    o.timestamps["kitchen_start"] = self.engine.tick
                return self._reset_chef_to_idle(chef)
            else:
                raw_path = self.engine.pathfinder.get_path((chef.x, chef.y), (station.x, station.y))
                chef.path = raw_path[1:] if len(raw_path) > 1 else []
                chef.status = "WALKING_TO_STATION"
                chef.current_task = {
                    "type": "COOK",
                    "order_id": next_order.order_id,
                    "station_id": station.id,
                    "substate": "WALK_TO_STATION"
                }
                return

        # 2. Then start unstarted manual dishes (PREP, DONER)
        unstarted_manual = [
            o for o in chef.active_orders
            if o.timestamps.get("kitchen_start") is None
            and o.assigned_station_id in self.engine.grid.stations
            and self.engine.grid.stations[o.assigned_station_id].type in ["PREP", "DONER"]
        ]
        if unstarted_manual:
            next_order = unstarted_manual[0]
            station = self.engine.grid.stations[next_order.assigned_station_id]
            if (chef.x, chef.y) == (station.x, station.y):
                next_order.timestamps["kitchen_start"] = self.engine.tick
                chef.status = "COOKING"
                chef.current_task = {
                    "type": "COOK",
                    "order_id": next_order.order_id,
                    "station_id": station.id,
                    "substate": "COOKING"
                }
                return
            else:
                raw_path = self.engine.pathfinder.get_path((chef.x, chef.y), (station.x, station.y))
                chef.path = raw_path[1:] if len(raw_path) > 1 else []
                chef.status = "WALKING_TO_STATION"
                chef.current_task = {
                    "type": "COOK",
                    "order_id": next_order.order_id,
                    "station_id": station.id,
                    "substate": "WALK_TO_STATION"
                }
                return

        # 3. Continue active in-progress manual task (PREP, DONER)
        manual_in_prog = [
            o for o in chef.active_orders
            if o.assigned_station_id in self.engine.grid.stations
            and self.engine.grid.stations[o.assigned_station_id].type in ["PREP", "DONER"]
        ]
        if manual_in_prog:
            p_order = manual_in_prog[0]
            st = self.engine.grid.stations[p_order.assigned_station_id]
            if (chef.x, chef.y) == (st.x, st.y):
                chef.status = "COOKING"
                chef.current_task = {
                    "type": "COOK",
                    "order_id": p_order.order_id,
                    "station_id": st.id,
                    "substate": "COOKING"
                }
                return
            else:
                raw_path = self.engine.pathfinder.get_path((chef.x, chef.y), (st.x, st.y))
                chef.path = raw_path[1:] if len(raw_path) > 1 else []
                chef.status = "WALKING_TO_STATION"
                chef.current_task = {
                    "type": "COOK",
                    "order_id": p_order.order_id,
                    "station_id": st.id,
                    "substate": "WALK_TO_STATION"
                }
                return

        chef.status = "IDLE"

    def _find_best_counter_for_chef(self, chef: Optional[Chef] = None, order: Optional[Order] = None) -> Optional[DeliveryCounter]:
        """Finds the closest non-full delivery counter for the chef, or dedicated takeout_counter for takeout."""
        if order and order.is_takeout:
            takeout_cnt = getattr(self.engine.grid, "takeout_counter", None)
            if takeout_cnt:
                return takeout_cnt

        counters = list(self.engine.grid.delivery_counters.values())
        if not counters:
            return self.engine.grid.delivery_counter
        available = [c for c in counters if not c.is_full]
        candidate_pool = available if available else counters
        if chef:
            return min(candidate_pool, key=lambda c: abs(c.x - chef.x) + abs(c.y - chef.y))
        return candidate_pool[0]

    def _drop_order_at_counter(self, chef: Optional[Chef], order: Order, tick: int, counter: Optional[DeliveryCounter] = None) -> bool:
        if counter is None:
            if order.is_takeout and getattr(self.engine.grid, "takeout_counter", None):
                counter = self.engine.grid.takeout_counter
            else:
                counter = self.engine.grid.delivery_counters.get(order.assigned_counter_id or "") or self.engine.grid.delivery_counter
        if counter:
            if chef:
                chef.x, chef.y = counter.x, counter.y
            if counter.is_full:
                return False # Counter is full (e.g. 4 dishes capacity reached), chef must wait

        if chef:
            chef.path.clear()
        order.status = "READY"
        order.timestamps["kitchen_finish"] = tick

        if counter:
            order.assigned_counter_id = counter.id
            if order not in counter.ready_orders:
                counter.ready_orders.append(order)

        # Remove from any station active_orders
        if order.assigned_station_id and order.assigned_station_id in self.engine.grid.stations:
            st = self.engine.grid.stations[order.assigned_station_id]
            if order in st.active_orders:
                st.active_orders.remove(order)

        # Remove order from assigned chef and carrying chef
        assigned_chef = self.engine.grid.chefs.get(order.assigned_chef_id)
        if assigned_chef and order in assigned_chef.active_orders:
            assigned_chef.active_orders.remove(order)
        if assigned_chef and order in assigned_chef.carrying_orders:
            assigned_chef.carrying_orders.remove(order)

        if chef and chef != assigned_chef:
            if order in chef.active_orders:
                chef.active_orders.remove(order)
            if order in chef.carrying_orders:
                chef.carrying_orders.remove(order)

        # Takeout auto-delivery if courier is already waiting
        if order.is_takeout:
            if tick >= (order.courier_eta or 0):
                order.status = "SERVED"
                order.timestamps["delivered_at"] = tick
                if order not in self.engine.completed_orders:
                    self.engine.completed_orders.append(order)
                if counter and order in counter.ready_orders:
                    counter.ready_orders.remove(order)

        # Record completed cook time to ML Data Collector
        k_start = order.timestamps.get("kitchen_start")
        time_cooking = tick - (k_start if k_start is not None else tick)
        self.engine.collector.record_completed_order(order, max(1.0, float(time_cooking)))

        # Periodic ML Retraining
        data_len = len(self.engine.collector.data)
        should_train = False
        if data_len <= 200 and data_len % 50 == 0:
            should_train = True
        elif 200 < data_len <= 2000 and data_len % 200 == 0:
            should_train = True
        elif data_len > 2000 and data_len % 1000 == 0:
            should_train = True

        if should_train and not getattr(self.engine, 'freeze_ml', False):
            df = self.engine.collector.get_dataframe()
            self.engine.predictor.train(df, auto_save=False)

        return True

    def _dispatch_chef_pickup_to_counter(self, chef: Chef, station: Station, orders: List[Order], tick: int):
        """Dispatches an idle chef to pick up ready dishes from a station and carry to delivery counter."""
        if not orders or chef.is_hands_full:
            return
        batch = orders[:chef.carrying_capacity]
        target_counter = self._find_best_counter_for_chef(chef, order=batch[0])
        
        raw_path = self.engine.pathfinder.get_path((chef.x, chef.y), (station.x, station.y))
        chef.path = raw_path[1:] if len(raw_path) > 1 else []
        chef.status = "DELIVERING_TO_COUNTER"
        chef.current_task = {
            "type": "PICKUP_TO_COUNTER",
            "station_id": station.id,
            "order_ids": [o.order_id for o in batch],
            "counter_id": target_counter.id if target_counter else None,
            "substate": "WALK_TO_PICKUP"
        }

        # If chef is already at station, pick up immediately
        if (chef.x, chef.y) == (station.x, station.y):
            for o in batch:
                if o in station.active_orders:
                    station.active_orders.remove(o)
                o.status = "DELIVERING_TO_COUNTER"
                chef.carrying_orders.append(o)
            if target_counter:
                raw_path_cnt = self.engine.pathfinder.get_path((chef.x, chef.y), (target_counter.x, target_counter.y))
                chef.path = raw_path_cnt[1:] if len(raw_path_cnt) > 1 else []
                chef.current_task["substate"] = "WALK_TO_COUNTER"
            else:
                self._reset_chef_to_idle(chef)

    def _dispatch_chef_stage_transfer(self, chef: Chef, from_station: Station, to_station: Station, order: Order, tick: int):
        """Dispatches an idle chef to transfer an intermediate multi-stage dish between stations."""
        if chef.is_hands_full:
            return
        raw_path = self.engine.pathfinder.get_path((chef.x, chef.y), (from_station.x, from_station.y))
        chef.path = raw_path[1:] if len(raw_path) > 1 else []
        chef.status = "TRANSFERRING_STAGE"
        chef.current_task = {
            "type": "TRANSFER_STAGE",
            "from_station_id": from_station.id,
            "to_station_id": to_station.id,
            "order_id": order.order_id,
            "substate": "WALK_TO_FROM_STATION"
        }

        # If chef is already at from_station, pick up immediately
        if (chef.x, chef.y) == (from_station.x, from_station.y):
            if order in from_station.active_orders:
                from_station.active_orders.remove(order)
            order.status = "TRANSFERRING_STAGE"
            chef.carrying_orders.append(order)
            raw_path_to = self.engine.pathfinder.get_path((chef.x, chef.y), (to_station.x, to_station.y))
            chef.path = raw_path_to[1:] if len(raw_path_to) > 1 else []
            chef.current_task["substate"] = "WALK_TO_TO_STATION"

    def _update_chef_tasks(self, tick: int):
        """Updates chef movements, pickups, plating at counters, and stage transfers."""
        for chef in self.engine.grid.chefs.values():
            if chef.current_task is None:
                if chef.active_orders and chef.status == "IDLE":
                    self._reset_chef_to_idle(chef)
                continue

            task = chef.current_task
            order_id = task.get("order_id")
            # Watchdog: If task order is no longer present in simulation, reset chef to IDLE
            if order_id and not any(o.order_id == order_id for s in self.engine.grid.stations.values() for o in s.active_orders) and not any(o.order_id == order_id for o in chef.carrying_orders) and not any(o.order_id == order_id for o in chef.active_orders):
                self._reset_chef_to_idle(chef)
                continue

            substate = task.get("substate")

            if substate == "WALK_TO_STATION":
                self._step_chef_along_path(chef)
                station = self.engine.grid.stations.get(task.get("station_id"))
                if not chef.path or (station and (chef.x, chef.y) == (station.x, station.y)):
                    if station:
                        chef.x, chef.y = station.x, station.y

                    matching_orders = [o for o in list(chef.active_orders) if o.assigned_station_id == (station.id if station else None)]
                    for o in matching_orders:
                        if o.timestamps.get("kitchen_start") is None:
                            o.timestamps["kitchen_start"] = tick

                    if station and station.type in ["OVEN", "GRILL", "STOVE", "FRYER", "TOASTER"]:
                        prep_dur = self.engine.time_config.chef_config.get("station_prep_duration", 1.0)
                        if prep_dur > 0:
                            task["substate"] = "PREP_AUTO"
                            task["finish_tick"] = tick + prep_dur
                            chef.status = "COOKING"
                            chef.busy_until = tick + prep_dur
                        else:
                            self._reset_chef_to_idle(chef)
                    else:
                        # Manual PREP & DONER: Chef stays at station
                        task["substate"] = "COOKING"
                        chef.status = "COOKING"

            elif substate == "PREP_AUTO":
                if tick >= task.get("finish_tick", tick):
                    self._reset_chef_to_idle(chef)

            elif substate == "WALK_TO_PICKUP":
                self._step_chef_along_path(chef)
                station = self.engine.grid.stations.get(task.get("station_id"))
                if not chef.path or (station and (chef.x, chef.y) == (station.x, station.y)):
                    if station:
                        chef.x, chef.y = station.x, station.y
                    order_ids = task.get("order_ids", [])
                    picked = []
                    for o in list(station.active_orders):
                        if (o.order_id in order_ids or o.status == "WAITING_PICKUP") and len(chef.carrying_orders) < chef.carrying_capacity:
                            station.active_orders.remove(o)
                            o.status = "DELIVERING_TO_COUNTER"
                            chef.carrying_orders.append(o)
                            picked.append(o)

                    target_counter = self._find_best_counter_for_chef(chef, order=picked[0] if picked else None)
                    if target_counter:
                        raw_path = self.engine.pathfinder.get_path((chef.x, chef.y), (target_counter.x, target_counter.y))
                        chef.path = raw_path[1:] if len(raw_path) > 1 else []
                        task["counter_id"] = target_counter.id
                        task["substate"] = "WALK_TO_COUNTER"
                        if not chef.path or (chef.x, chef.y) == (target_counter.x, target_counter.y):
                            self._start_chef_plating(chef, task, tick, target_counter)
                    else:
                        self._reset_chef_to_idle(chef)

            elif substate == "WALK_TO_COUNTER":
                self._step_chef_along_path(chef)
                counter_id = task.get("counter_id")
                counter = self.engine.grid.delivery_counters.get(counter_id or "") or (self.engine.grid.takeout_counter if counter_id == getattr(self.engine.grid.takeout_counter, "id", None) else self.engine.grid.delivery_counter)
                if not chef.path or (counter and (chef.x, chef.y) == (counter.x, counter.y)):
                    if counter:
                        chef.x, chef.y = counter.x, counter.y
                    self._start_chef_plating(chef, task, tick, counter)

            elif substate == "PLATING":
                if tick >= task.get("finish_tick", tick):
                    counter_id = task.get("counter_id")
                    counter = self.engine.grid.delivery_counters.get(counter_id or "") or (self.engine.grid.takeout_counter if counter_id == getattr(self.engine.grid.takeout_counter, "id", None) else self.engine.grid.delivery_counter)
                    all_dropped = True
                    for order in list(chef.carrying_orders):
                        if not self._drop_order_at_counter(chef, order, tick, counter=counter):
                            all_dropped = False
                            break
                    if all_dropped:
                        self._reset_chef_to_idle(chef)
                    else:
                        task["substate"] = "PLATING" # Wait at counter if counter full

            elif substate == "WALK_TO_FROM_STATION":
                self._step_chef_along_path(chef)
                from_st = self.engine.grid.stations.get(task.get("from_station_id"))
                if not chef.path or (from_st and (chef.x, chef.y) == (from_st.x, from_st.y)):
                    if from_st:
                        chef.x, chef.y = from_st.x, from_st.y
                    order_id = task.get("order_id")
                    order = next((o for o in from_st.active_orders if o.order_id == order_id), None)
                    if order:
                        from_st.active_orders.remove(order)
                        order.status = "TRANSFERRING_STAGE"
                        chef.carrying_orders.append(order)
                        to_st = self.engine.grid.stations.get(task.get("to_station_id"))
                        if to_st:
                            raw_path = self.engine.pathfinder.get_path((chef.x, chef.y), (to_st.x, to_st.y))
                            chef.path = raw_path[1:] if len(raw_path) > 1 else []
                            task["substate"] = "WALK_TO_TO_STATION"
                            if not chef.path or (chef.x, chef.y) == (to_st.x, to_st.y):
                                self._start_stage_placing(chef, task, tick, to_st, order)
                        else:
                            self._reset_chef_to_idle(chef)
                    else:
                        self._reset_chef_to_idle(chef)

            elif substate == "WALK_TO_TO_STATION":
                self._step_chef_along_path(chef)
                to_st = self.engine.grid.stations.get(task.get("to_station_id"))
                if not chef.path or (to_st and (chef.x, chef.y) == (to_st.x, to_st.y)):
                    if to_st:
                        chef.x, chef.y = to_st.x, to_st.y
                    order_id = task.get("order_id")
                    order = next((o for o in chef.carrying_orders if o.order_id == order_id), None)
                    if order and to_st:
                        self._start_stage_placing(chef, task, tick, to_st, order)
                    else:
                        self._reset_chef_to_idle(chef)

            elif substate == "PLACING_STAGE":
                if tick >= task.get("finish_tick", tick):
                    to_st = self.engine.grid.stations.get(task.get("to_station_id"))
                    order_id = task.get("order_id")
                    order = next((o for o in chef.carrying_orders if o.order_id == order_id), None)
                    if order and to_st:
                        order.current_stage_idx += 1
                        order.status = "PREPARING"
                        order.assigned_station_id = to_st.id
                        order.timestamps["kitchen_start"] = tick
                        order.actual_target_time = self.sample_cook_time(order, to_st, chef)
                        to_st.active_orders.append(order)
                        if order in chef.carrying_orders:
                            chef.carrying_orders.remove(order)
                    self._reset_chef_to_idle(chef)

    def _start_chef_plating(self, chef: Chef, task: Dict[str, Any], tick: int, counter: Optional[DeliveryCounter]):
        plating_dur = self.engine.time_config.chef_config.get("plating_and_counter_drop_duration", 1.0)
        if plating_dur > 0 and task.get("substate") != "PLATING":
            task["substate"] = "PLATING"
            task["finish_tick"] = tick + plating_dur
            chef.busy_until = tick + plating_dur
        else:
            all_dropped = True
            for order in list(chef.carrying_orders):
                if not self._drop_order_at_counter(chef, order, tick, counter=counter):
                    all_dropped = False
                    break
            if all_dropped:
                self._reset_chef_to_idle(chef)

    def _start_stage_placing(self, chef: Chef, task: Dict[str, Any], tick: int, to_st: Station, order: Order):
        transfer_dur = self.engine.time_config.chef_config.get("stage_transfer_duration", 1.0)
        if transfer_dur > 0 and task.get("substate") != "PLACING_STAGE":
            task["substate"] = "PLACING_STAGE"
            task["finish_tick"] = tick + transfer_dur
            chef.busy_until = tick + transfer_dur
        else:
            order.current_stage_idx += 1
            order.status = "PREPARING"
            order.assigned_station_id = to_st.id
            order.timestamps["kitchen_start"] = tick
            order.actual_target_time = self.sample_cook_time(order, to_st, chef)
            to_st.active_orders.append(order)
            if order in chef.carrying_orders:
                chef.carrying_orders.remove(order)
            self._reset_chef_to_idle(chef)

    def _auto_dispatch_idle_chefs(self, tick: int):
        """Automatically dispatches available idle chefs to stage transfers and counter deliveries."""
        idle_chefs = [
            c for c in self.engine.grid.chefs.values()
            if c.status == "IDLE" and c.current_task is None and (c.busy_until <= tick) and not c.is_hands_full
        ]
        if not idle_chefs:
            return

        # Priority 1: Multi-stage transfers (WAITING_PICKUP_STAGE)
        for station in self.engine.grid.stations.values():
            for order in list(station.active_orders):
                if order.status == "WAITING_PICKUP_STAGE":
                    if not idle_chefs:
                        return
                    if order.current_stage_idx < len(order.stages) - 1:
                        next_stage = order.stages[order.current_stage_idx + 1]
                        req_type = next_stage["station_type"]
                        avail_stations = [s for s in self.engine.grid.stations.values() if s.type == req_type and not s.is_full and not s.is_broken]
                        if avail_stations:
                            target_station = avail_stations[0]
                            # Assign assigned chef if idle, or nearest idle chef
                            ch = self.engine.grid.chefs.get(order.assigned_chef_id)
                            if ch and ch in idle_chefs:
                                chef = ch
                                idle_chefs.remove(ch)
                            else:
                                idle_chefs.sort(key=lambda c: self.engine.pathfinder.get_distance((c.x, c.y), (station.x, station.y)))
                                chef = idle_chefs.pop(0)
                            self._dispatch_chef_stage_transfer(chef, station, target_station, order, tick)

        # Priority 2: Carry finished dishes to counter (WAITING_PICKUP)
        for station in self.engine.grid.stations.values():
            ready_orders = [o for o in station.active_orders if o.status == "WAITING_PICKUP"]
            if ready_orders:
                if not idle_chefs:
                    return
                # Check if assigned chef is idle
                first_order = ready_orders[0]
                ch = self.engine.grid.chefs.get(first_order.assigned_chef_id)
                if ch and ch in idle_chefs:
                    chef = ch
                    idle_chefs.remove(ch)
                else:
                    idle_chefs.sort(key=lambda c: self.engine.pathfinder.get_distance((c.x, c.y), (station.x, station.y)))
                    chef = idle_chefs.pop(0)
                batch = ready_orders[:chef.carrying_capacity]
                self._dispatch_chef_pickup_to_counter(chef, station, batch, tick)

    def progress_cooking(self, tick: int):
        """Advances active cooking timers, handles multi-stage transitions, and manages chef counter deliveries."""
        # 0. Fulfill queued fry and doner orders if ready batch stock exists
        self.fulfill_from_fryer_stock(tick)
        self.fulfill_from_doner_stock(tick)

        # 1. Update chef movements, pickups, platings, and transfers
        self._update_chef_tasks(tick)

        # 2. Check cooking progress on all stations
        for station in self.engine.grid.stations.values():
            for order in list(station.active_orders):
                if order.status in ["WAITING_PICKUP", "WAITING_PICKUP_STAGE", "DELIVERING_TO_COUNTER", "TRANSFERRING_STAGE"]:
                    continue

                if station.type in ["OVEN", "GRILL", "STOVE", "FRYER", "TOASTER"]:
                    # Autonomous cooking on oven/grill/stove/fryer/toaster
                    if order.timestamps.get("kitchen_start") is None:
                        continue
                    time_cooking = tick - order.timestamps["kitchen_start"]
                else:
                    # Manual cooking on PREP & DONER
                    chef = self.engine.grid.chefs.get(order.assigned_chef_id)
                    if order.timestamps.get("kitchen_start") is None:
                        if chef and (chef.x, chef.y) == (station.x, station.y):
                            order.timestamps["kitchen_start"] = tick
                        else:
                            continue
                    time_cooking = tick - order.timestamps["kitchen_start"]

                if time_cooking >= (order.actual_target_time or 1.0):
                    # Multi-stage check
                    if order.current_stage_idx < len(order.stages) - 1:
                        order.status = "WAITING_PICKUP_STAGE"
                        if station.type == "DONER":
                            self.doner_inventory += 1
                    else:
                        order.status = "WAITING_PICKUP"
                        self._apply_batch_yield(station.type, order.dish_type)

        # 3. Auto-dispatch idle chefs for transfers and deliveries
        self._auto_dispatch_idle_chefs(tick)

    def _apply_batch_yield(self, station_type: str, dish_type: str):
        """Applies batch inventory yields for Doner and Fryer based on time_config."""
        yield_cfg = self.engine.time_config.cooking_mechanics.get("batch_yields", {})
        if station_type == "DONER":
            self.doner_inventory += yield_cfg.get("Doner", 1)
        elif station_type == "FRYER":
            if dish_type == "Patates":
                self.fryer_inventory["Patates"] = self.fryer_inventory.get("Patates", 0) + yield_cfg.get("Patates", 4)
            elif dish_type in ["Sogan_Halkasi", "Sogan Halkasi"]:
                self.fryer_inventory["Sogan_Halkasi"] = self.fryer_inventory.get("Sogan_Halkasi", 0) + yield_cfg.get("Sogan_Halkasi", 7)
            elif dish_type in ["Fried_Basket", "Fried Basket"]:
                fb = yield_cfg.get("Fried_Basket", {"Patates": 2, "Sogan_Halkasi": 3})
                if isinstance(fb, dict):
                    self.fryer_inventory["Patates"] = self.fryer_inventory.get("Patates", 0) + fb.get("Patates", 2)
                    self.fryer_inventory["Sogan_Halkasi"] = self.fryer_inventory.get("Sogan_Halkasi", 0) + fb.get("Sogan_Halkasi", 3)
