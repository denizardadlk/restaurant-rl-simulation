import unittest
import pandas as pd
from simulation.collector import EmpiricalDataCollector
from simulation.model import CookTimePredictor
from simulation.entities import Order

class TestMLCollector(unittest.TestCase):
    def test_zero_leakage_collection(self):
        collector = EmpiricalDataCollector()
        
        order = Order(table_id="T1", dish_type="Pizza", theoretical_time=15.0)
        order.assigned_station_id = "S_OVEN_1"
        order.station_load_at_start = 2
        order.kitchen_load_at_start = 5
        order.chef_efficiency_at_start = 1.0
        order.day_tick_at_start = 100
        
        # Record completed order with actual time
        collector.record_completed_order(order, actual_cook_time=18.5)
        
        df = collector.get_dataframe()
        self.assertEqual(len(df), 1)
        
        # Verify target is there but only from the final parameter
        self.assertIn("actual_cook_time", df.columns)
        self.assertEqual(df.iloc[0]["actual_cook_time"], 18.5)
        
        # Ensure it contains all expected features snapshot from start
        self.assertEqual(df.iloc[0]["station_load_at_start"], 2)
        
    def test_model_training_and_cold_start(self):
        predictor = CookTimePredictor()
        
        # Cold start
        features = {
            "theoretical_time": 15.0,
            "dish_type": "Pizza",
            "station_type": "OVEN",
            "station_load_at_start": 2,
            "kitchen_load_at_start": 5,
            "chef_efficiency_at_start": 1.0,
            "day_tick_at_start": 100
        }
        
        # Should return theoretical time directly when less than 20 orders
        pred_cold = predictor.predict(features, total_orders_so_far=10)
        self.assertEqual(pred_cold, 15.0)
        
        # Create dummy data to train
        data = []
        for _ in range(120):
            data.append({
                "theoretical_time": 15.0,
                "dish_type": "Pizza",
                "station_type": "OVEN",
                "station_load_at_start": 2,
                "kitchen_load_at_start": 5,
                "chef_efficiency_at_start": 1.0,
                "day_tick_at_start": 100,
                "actual_cook_time": 20.0
            })
            
        df = pd.DataFrame(data)
        predictor.train(df)
        
        self.assertTrue(predictor.is_trained)
        
        # Fully trained mode (> 100 orders)
        pred_trained = predictor.predict(features, total_orders_so_far=150)
        # Should be very close to 20.0
        self.assertAlmostEqual(pred_trained, 20.0, places=1)

if __name__ == "__main__":
    unittest.main()
