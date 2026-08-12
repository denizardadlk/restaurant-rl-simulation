import pandas as pd
from typing import List, Dict, Any
from .entities import Order

class EmpiricalDataCollector:
    """
    Collects order data for ML training while strictly avoiding target leakage.
    Features X are snapshot exactly at kitchen_start.
    Target Y (actual cook time) is only recorded at kitchen_finish.
    """
    def __init__(self):
        self.data: List[Dict[str, Any]] = []
        
    def record_completed_order(self, order: Order, actual_cook_time: float):
        """
        Records a fully cooked order.
        Assumes order has its feature snapshots populated at start time.
        """
        # Ensure we have snapshots
        if order.station_load_at_start is None:
            return # Skip if snapshots are missing
            
        record = {
            "dish_type": order.dish_type,
            "theoretical_time": order.theoretical_time,
            "station_type": order.assigned_station_id.split('_')[1] if order.assigned_station_id else "UNKNOWN",
            "station_load_at_start": order.station_load_at_start,
            "kitchen_load_at_start": order.kitchen_load_at_start,
            "chef_efficiency_at_start": order.chef_efficiency_at_start,
            "day_tick_at_start": order.day_tick_at_start,
            # TARGET VARIABLE
            "actual_cook_time": actual_cook_time
        }
        self.data.append(record)
        
    def get_dataframe(self) -> pd.DataFrame:
        """Returns the collected data as a Pandas DataFrame."""
        return pd.DataFrame(self.data)
        
    def clear(self):
        self.data.clear()
