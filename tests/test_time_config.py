import os
import json
import unittest
import tempfile
from simulation.time_config import load_time_config, TimeConfig, DEFAULT_TIME_CONFIG_PATH
from simulation.engine import SimulationEngine
from simulation.generator import OrderGenerator

class TestTimeConfig(unittest.TestCase):
    def test_default_time_config_loading(self):
        cfg = load_time_config()
        self.assertIn("Burger", cfg.menu_recipes)
        self.assertIn("Doner", cfg.menu_recipes)
        self.assertEqual(cfg.customer_patience.get("waiting_order_initial"), 20.0)
        self.assertEqual(cfg.waiter_config.get("order_taking_duration"), 1.0)
        self.assertEqual(cfg.waiter_config.get("table_cleaning_duration"), 2.0)
        self.assertEqual(cfg.cooking_mechanics.get("gamma_distribution_alpha"), 25.0)

    def test_dynamic_config_override(self):
        # Create a temporary custom time_config JSON
        custom_data = {
            "customer_patience": {
                "waiting_order_initial": 15.0,
                "waiting_food_initial": 20.0,
                "decay_rate_per_tick": 0.5
            },
            "menu_recipes": {
                "QuickBurger": {
                    "stages": [{"station_type": "GRILL", "time": 3.0}]
                }
            },
            "arrival_schedule": {
                "open_hour_tick": 600,
                "close_hour_tick": 1200,
                "intervals": [
                    {"start_tick": 600, "end_tick": 1200, "interval_minutes": 2.5, "description": "Super Peak"}
                ]
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(custom_data, f)
            temp_path = f.name

        try:
            cfg = load_time_config(temp_path)
            self.assertEqual(cfg.customer_patience["waiting_order_initial"], 15.0)
            self.assertEqual(cfg.customer_patience["decay_rate_per_tick"], 0.5)
            self.assertIn("QuickBurger", cfg.menu_recipes)
            # Fallback still preserved for unspecified keys
            self.assertEqual(cfg.waiter_config["table_cleaning_duration"], 2.0)

            # Generator with custom time_config
            gen = OrderGenerator(time_config=cfg)
            self.assertEqual(len(gen.dish_types), 1)
            self.assertEqual(gen.dish_types[0]["type"], "QuickBurger")
            self.assertEqual(gen.dish_types[0]["stages"][0]["time"], 3.0)

            # Arrival rate matches custom 2.5 min interval
            arrival_lambda = gen._get_current_lambda(700)
            self.assertAlmostEqual(arrival_lambda, 1.0 / 2.5)
            # Closed at tick 100
            self.assertEqual(gen._get_current_lambda(100), 0.0)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_engine_integration_with_time_config(self):
        custom_cfg = TimeConfig({
            "customer_patience": {
                "waiting_order_initial": 50.0,
                "decay_rate_per_tick": 0.2
            },
            "waiter": {
                "order_taking_duration": 3.0,
                "table_cleaning_duration": 4.0
            }
        })
        engine = SimulationEngine("config/default_layout.json", time_config=custom_cfg)
        self.assertEqual(engine.time_config.customer_patience["waiting_order_initial"], 50.0)
        self.assertEqual(engine.time_config.customer_patience["decay_rate_per_tick"], 0.2)

if __name__ == "__main__":
    unittest.main()
