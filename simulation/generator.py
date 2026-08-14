import random
import math
from typing import List
from .entities import Order

class OrderGenerator:
    def __init__(self, lambda_normal: float = 0.05, lambda_peak: float = 0.2, difficulty_level: int = 3):
        self.difficulty_level = difficulty_level
        self.lambda_normal = lambda_normal
        self.lambda_peak = lambda_peak if difficulty_level >= 2 else lambda_normal
        
        if difficulty_level == 1:
            # Level 1: Simple single-stage dishes
            self.dish_types = [
                {"type": "Pizza", "stages": [{"station_type": "OVEN", "time": 14.0}]},
                {"type": "Burger", "stages": [{"station_type": "STOVE", "time": 10.0}]},
                {"type": "Salad", "stages": [{"station_type": "PREP", "time": 5.0}]},
                {"type": "Steak", "stages": [{"station_type": "GRILL", "time": 17.0}]}
            ]
        else:
            # Level 2 & 3: Multi-stage dishes
            self.dish_types = [
                {"type": "Pizza", "stages": [{"station_type": "PREP", "time": 4.0}, {"station_type": "OVEN", "time": 10.0}]},
                {"type": "Burger", "stages": [{"station_type": "PREP", "time": 2.0}, {"station_type": "STOVE", "time": 8.0}]},
                {"type": "Salad", "stages": [{"station_type": "PREP", "time": 5.0}]},
                {"type": "Steak", "stages": [{"station_type": "PREP", "time": 2.0}, {"station_type": "GRILL", "time": 15.0}]}
            ]

    def _get_current_lambda(self, current_tick: int) -> float:
        # Assuming 1 tick = 1 minute, a day is 1440 ticks.
        # Peak hours: 12:00-14:00 (ticks 720-840) and 19:00-21:00 (ticks 1140-1260)
        day_tick = current_tick % 1440
        if (720 <= day_tick <= 840) or (1140 <= day_tick <= 1260):
            return self.lambda_peak
        return self.lambda_normal

    def generate_orders(self, current_tick: int, available_tables: List['Table']) -> List[Order]:
        if not available_tables:
            return []

        current_lambda = self._get_current_lambda(current_tick)
        
        # Poisson distribution for number of arrivals
        orders_to_create = 0
        rand_val = random.random()
        
        p_0 = math.exp(-current_lambda)
        p_1 = current_lambda * p_0
        
        if rand_val > p_0 + p_1:
            orders_to_create = 2
        elif rand_val > p_0:
            orders_to_create = 1
            
        orders_to_create = min(orders_to_create, len(available_tables))
        
        new_orders = []
        # Randomly pick tables from available ones
        chosen_tables = random.sample(available_tables, orders_to_create)
        
        for table in chosen_tables:
            # Generate exactly `table.capacity` orders, independently picking random dishes
            for _ in range(table.capacity):
                dish = random.choice(self.dish_types)
                total_time = sum(stage["time"] for stage in dish["stages"])
                order = Order(
                    table_id=table.id,
                    dish_type=dish["type"],
                    theoretical_time=total_time,
                    stages=dish["stages"]
                )
                order.timestamps["created_at"] = current_tick
                new_orders.append(order)
                
        # Also randomly generate Takeout Orders if Level 3
        if self.difficulty_level >= 3 and random.random() < 0.02:
            dish = random.choice(self.dish_types)
            total_time = sum(stage["time"] for stage in dish["stages"])
            takeout_order = Order(
                table_id=None,
                dish_type=dish["type"],
                theoretical_time=total_time,
                stages=dish["stages"],
                is_takeout=True,
                courier_eta=current_tick + random.uniform(15.0, 30.0)
            )
            takeout_order.timestamps["created_at"] = current_tick
            new_orders.append(takeout_order)
            
        return new_orders
