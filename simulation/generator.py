import random
import math
from typing import List
from .entities import Order

class OrderGenerator:
    def __init__(self, lambda_normal: float = 0.05, lambda_peak: float = 0.2):
        self.lambda_normal = lambda_normal
        self.lambda_peak = lambda_peak
        self.dish_types = [
            {"type": "Pizza", "theoretical_time": 15.0},
            {"type": "Burger", "theoretical_time": 10.0},
            {"type": "Salad", "theoretical_time": 5.0},
            {"type": "Steak", "theoretical_time": 25.0}
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
                order = Order(
                    table_id=table.id,
                    dish_type=dish["type"],
                    theoretical_time=dish["theoretical_time"]
                )
                order.timestamps["created_at"] = current_tick
                new_orders.append(order)
            
        return new_orders
