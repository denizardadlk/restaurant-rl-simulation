import unittest
from simulation.engine import SimulationEngine
from simulation.analyzer import BottleneckAnalyzer

CONFIG_PATH = "config/default_layout.json"

class TestBottleneckAnalyzer(unittest.TestCase):
    def setUp(self):
        self.engine = SimulationEngine(CONFIG_PATH, auto_generate_orders=False)
        self.engine.reset()
        self.analyzer = BottleneckAnalyzer(self.engine)

    def test_analyzer_tracking_and_summaries(self):
        """Test that BottleneckAnalyzer tracks tick statistics without error."""
        for _ in range(10):
            self.engine.step()
            self.analyzer.track_tick()

        station_summary = self.analyzer.get_station_summary()
        self.assertGreater(len(station_summary), 0)
        self.assertIn("bottleneck_score", station_summary[0])

        stage_summary = self.analyzer.get_stage_queue_summary()
        self.assertGreater(len(stage_summary), 0)
        self.assertIn("avg_queue_wait_minutes", stage_summary[0])

        chef_summary = self.analyzer.get_chef_summary()
        self.assertGreater(len(chef_summary), 0)
        self.assertIn("total_work_load", chef_summary[0])

        waiter_summary = self.analyzer.get_waiter_summary()
        self.assertGreater(len(waiter_summary), 0)
        self.assertIn("total_work_load", waiter_summary[0])

        counter_summary = self.analyzer.get_counter_summary()
        self.assertGreater(len(counter_summary), 0)

    def test_churn_recording_and_top_bottlenecks(self):
        """Test churn categorization and top bottlenecks retrieval."""
        self.analyzer.record_churn("WAITING_ORDER", count=5)
        self.analyzer.record_churn("WAITING_FOOD", count=15)

        self.assertEqual(self.analyzer.churn_reasons["WAITING_ORDER"], 5)
        self.assertEqual(self.analyzer.churn_reasons["WAITING_FOOD"], 15)

        top = self.analyzer.get_top_bottlenecks(top_n=3)
        self.assertIsInstance(top, list)
        self.assertLessEqual(len(top), 3)

    def test_dish_and_interval_summaries(self):
        """Test dish performance and hourly interval summaries."""
        # Create a sample order and track
        from simulation.entities import Order
        order = Order(table_id=1, dish_type="Burger", theoretical_time=10.0, category="main_dish", stages=[{"station_type": "GRILL", "time": 10.0}])
        self.engine.order_queue.append(order)
        self.analyzer.track_tick()

        dish_summary = self.analyzer.get_dish_performance_summary()
        self.assertGreaterEqual(len(dish_summary), 1)
        self.assertEqual(dish_summary[0]["dish_type"], "Burger")
        self.assertEqual(dish_summary[0]["category"], "main_dish")

        interval_summary = self.analyzer.get_interval_summary()
        self.assertGreater(len(interval_summary), 0)
        self.assertIn("target_occupancy", interval_summary[0])

        staff_summary = self.analyzer.get_staff_detailed_summary()
        self.assertIn("chefs", staff_summary)
        self.assertIn("waiters", staff_summary)

if __name__ == "__main__":
    unittest.main()
