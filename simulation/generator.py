import random
import math
from typing import List, Optional
from .entities import Order
from .time_config import get_time_config, TimeConfig

class OrderGenerator:
    def __init__(self, lambda_normal: float = 0.05, lambda_peak: float = 0.2, difficulty_level: int = 2, time_config: Optional[TimeConfig] = None):
        self.difficulty_level = difficulty_level
        self.time_config = time_config or get_time_config()
        self.lambda_normal = lambda_normal
        self.lambda_peak = lambda_peak
        self._load_dish_types()

    def _load_dish_types(self):
        """Loads dish types categorized from time_config."""
        recipes = self.time_config.menu_recipes
        categories = self.time_config.menu_categories
        
        self.main_dishes = []
        self.appetizers = []
        self.beverages = []

        main_keys = categories.get("main_dishes", ["Burger", "Doner", "Sucuk", "Kofte", "Toast"])
        app_keys = categories.get("appetizers", ["Patates", "Sogan_Halkasi", "Fried_Basket"])
        bev_keys = categories.get("beverages", ["Kola", "Ayran", "Su", "Salgam"])

        for k in main_keys:
            if k in recipes:
                self.main_dishes.append({"type": k, "category": "main_dish", "stages": recipes[k].get("stages", [])})
        for k in app_keys:
            if k in recipes:
                self.appetizers.append({"type": k, "category": "appetizer", "stages": recipes[k].get("stages", [])})
        for k in bev_keys:
            if k in recipes:
                self.beverages.append({"type": k, "category": "beverage", "stages": recipes[k].get("stages", [])})

        # Fallback if categories are not defined
        if not self.main_dishes and not self.appetizers and not self.beverages:
            for d_name, d_data in recipes.items():
                cat = d_data.get("category", "main_dish")
                self.main_dishes.append({"type": d_name, "category": cat, "stages": d_data.get("stages", [])})

        self.dish_types = self.main_dishes + self.appetizers + self.beverages

    def _get_current_interval_info(self, current_tick: int) -> Optional[dict]:
        """Returns arrival interval dictionary for current tick, or None if restaurant is closed."""
        day_tick = current_tick % 1440
        open_tick = self.time_config.arrival_schedule.get("open_hour_tick", 540)
        close_tick = self.time_config.arrival_schedule.get("close_hour_tick", 1320)
        if not (open_tick <= day_tick < close_tick):
            return None

        intervals = self.time_config.arrival_schedule.get("intervals", [])
        for item in intervals:
            if item["start_tick"] <= day_tick < item["end_tick"]:
                return item
        return None

    def _get_current_lambda(self, current_tick: int) -> float:
        """Returns base Poisson arrival rate lambda (per minute)."""
        info = self._get_current_interval_info(current_tick)
        if not info:
            return 0.0
        interval_min = info.get("interval_minutes", 20.0)
        return 1.0 / max(0.1, interval_min)

    def generate_orders(self, current_tick: int, available_tables: List['Table'], total_tables_count: Optional[int] = None) -> List[Order]:
        if not available_tables:
            return []

        info = self._get_current_interval_info(current_tick)
        if not info:
            return []

        # Refresh dish types in case time_config was dynamically edited
        self._load_dish_types()
        base_target = info.get("target_occupancy", 0.40)
        burst_max = info.get("burst_max", 2)
        interval_min = info.get("interval_minutes", 10.0)

        # Total tables and occupancy calculation
        n_total = total_tables_count if total_tables_count is not None else len(available_tables)
        n_occupied = max(0, n_total - len(available_tables))
        
        # Difficulty scaling
        if self.difficulty_level == 1:
            eff_target = max(0.10, base_target - 0.15)
            burst_max = max(1, burst_max - 1)
        elif self.difficulty_level == 3:
            eff_target = min(0.95, base_target + 0.10)
            burst_max = min(len(available_tables), burst_max + 1)
        else:
            eff_target = base_target

        target_tables = eff_target * n_total
        gap = max(0.0, target_tables - n_occupied)

        # Dynamic lambda based on interval, capacity and gap to target occupancy
        base_lambda = 1.0 / max(0.1, interval_min)
        capacity_factor = max(1.0, n_total / 8.0)
        if gap > 0:
            gap_factor = 1.0 + (gap / max(1.0, n_total)) * 3.0
        else:
            gap_factor = 0.25  # Trickle arrival when at/above target occupancy

        arrival_lambda = base_lambda * capacity_factor * gap_factor

        # Knuth Poisson sampling for number of customer groups
        l_exp = math.exp(-min(20.0, arrival_lambda))
        k = 0
        p = 1.0
        while p > l_exp:
            k += 1
            p *= random.random()
        orders_to_create = max(0, k - 1)

        # Stochastic gap fill if Poisson sampled 0 but gap is significant
        if orders_to_create == 0 and gap >= 1.0:
            if random.random() < (gap / max(1.0, n_total)) * 0.6:
                orders_to_create = 1

        orders_to_create = min(orders_to_create, len(available_tables), max(1, burst_max))

        new_orders = []
        chosen_tables = random.sample(available_tables, orders_to_create)
        probs = self.time_config.order_probabilities

        main_prob = probs.get("main_dish", {"first_prob": 1.0, "second_prob": 0.20})
        app_prob = probs.get("appetizer", {"first_prob": 0.40, "second_prob": 0.20})
        bev_prob = probs.get("beverage", {"first_prob": 0.95, "second_prob": 0.40})

        for table in chosen_tables:
            customer_count = table.capacity
            table_orders = []

            for _ in range(customer_count):
                # 1. Main Dish
                if self.main_dishes:
                    if random.random() < main_prob.get("first_prob", 1.0):
                        dish = random.choice(self.main_dishes)
                        table_orders.append(dish)
                    if random.random() < main_prob.get("second_prob", 0.20):
                        dish = random.choice(self.main_dishes)
                        table_orders.append(dish)

                # 2. Appetizer
                if self.appetizers:
                    if random.random() < app_prob.get("first_prob", 0.40):
                        dish = random.choice(self.appetizers)
                        table_orders.append(dish)
                    if random.random() < app_prob.get("second_prob", 0.20):
                        dish = random.choice(self.appetizers)
                        table_orders.append(dish)

                # 3. Beverage
                if self.beverages:
                    if random.random() < bev_prob.get("first_prob", 0.95):
                        dish = random.choice(self.beverages)
                        table_orders.append(dish)
                    if random.random() < bev_prob.get("second_prob", 0.40):
                        dish = random.choice(self.beverages)
                        table_orders.append(dish)

            # Fallback: if somehow 0 orders were generated, at least give 1 main dish per person
            if not table_orders and self.main_dishes:
                for _ in range(customer_count):
                    table_orders.append(random.choice(self.main_dishes))

            for dish in table_orders:
                total_time = sum(stage["time"] for stage in dish["stages"])
                order = Order(
                    table_id=table.id,
                    dish_type=dish["type"],
                    category=dish.get("category", "main_dish"),
                    theoretical_time=total_time,
                    stages=dish["stages"]
                )
                order.timestamps["created_at"] = current_tick
                new_orders.append(order)
                
        # Takeout Orders Generation from time_config
        day_tick = current_tick % 1440
        open_tick = self.time_config.arrival_schedule.get("open_hour_tick", 540)
        close_tick = self.time_config.arrival_schedule.get("close_hour_tick", 1320)
        if open_tick <= day_tick < close_tick:
            takeout_cfg = self.time_config.takeout
            if (720 <= day_tick < 840) or (1200 <= day_tick < 1320):
                takeout_prob = takeout_cfg.get("peak_probability", 0.06)
            else:
                takeout_prob = takeout_cfg.get("normal_probability", 0.03)
            
            if random.random() < takeout_prob:
                food_pool = self.main_dishes + self.appetizers if (self.main_dishes or self.appetizers) else self.dish_types
                if food_pool:
                    dish = random.choice(food_pool)
                    total_time = sum(stage["time"] for stage in dish["stages"])
                    eta_min = takeout_cfg.get("courier_eta_min", 15.0)
                    eta_max = takeout_cfg.get("courier_eta_max", 30.0)
                    courier_eta = current_tick + random.uniform(eta_min, eta_max)
                    takeout_order = Order(
                        table_id=None,
                        dish_type=dish["type"],
                        category=dish.get("category", "main_dish"),
                        theoretical_time=total_time,
                        stages=dish["stages"],
                        is_takeout=True,
                        courier_eta=courier_eta
                    )
                    takeout_order.timestamps["created_at"] = current_tick
                    new_orders.append(takeout_order)

                    # Also add a beverage with probability (70%)
                    if self.beverages and random.random() < 0.70:
                        bev = random.choice(self.beverages)
                        takeout_bev = Order(
                            table_id=None,
                            dish_type=bev["type"],
                            category="beverage",
                            theoretical_time=0.0,
                            stages=[],
                            is_takeout=True,
                            courier_eta=courier_eta
                        )
                        takeout_bev.timestamps["created_at"] = current_tick
                        new_orders.append(takeout_bev)
            
        return new_orders
