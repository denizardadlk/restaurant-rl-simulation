import unittest
from simulation.grid import RestaurantGrid
from simulation.pathfinding import Pathfinder
from simulation.generator import OrderGenerator
from simulation.engine import SimulationEngine
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "default_layout.json")

class TestSimulationCore(unittest.TestCase):
    def test_grid_loading(self):
        grid = RestaurantGrid(CONFIG_PATH)
        self.assertEqual(grid.width, 10)
        self.assertEqual(grid.height, 10)
        self.assertEqual(len(grid.tables), 5)
        self.assertEqual(len(grid.stations), 4)
        self.assertEqual(len(grid.chefs), 2)
        self.assertEqual(len(grid.waiters), 2)

    def test_pathfinding(self):
        grid = RestaurantGrid(CONFIG_PATH)
        pathfinder = Pathfinder(grid)
        
        # Test distance between two adjacent walkable cells if possible
        # Or just test that distances exist and are >= 0
        self.assertIsNotNone(pathfinder.distance_matrix)
        
        table = grid.tables["T1"]
        station = grid.stations["S_OVEN_1"]
        
        dist = pathfinder.get_distance((table.x, table.y), (station.x, station.y))
        self.assertGreaterEqual(dist, 0.0)

    def test_order_generator(self):
        generator = OrderGenerator()
        # 09:00 - 11:00 (tick 600) -> 1/30
        self.assertAlmostEqual(generator._get_current_lambda(600), 1.0 / 30.0)
        # 11:00 - 12:00 (tick 700) -> 1/20
        self.assertAlmostEqual(generator._get_current_lambda(700), 1.0 / 20.0)
        # 12:00 - 14:00 (tick 750) -> 1/5 (Öğle Piki)
        self.assertAlmostEqual(generator._get_current_lambda(750), 1.0 / 5.0)
        # 14:00 - 16:00 (tick 900) -> 1/20
        self.assertAlmostEqual(generator._get_current_lambda(900), 1.0 / 20.0)
        # 16:00 - 20:00 (tick 1000) -> 1/15
        self.assertAlmostEqual(generator._get_current_lambda(1000), 1.0 / 15.0)
        # 20:00 - 22:00 (tick 1250) -> 1/10 (Akşam Piki)
        self.assertAlmostEqual(generator._get_current_lambda(1250), 1.0 / 10.0)
        # 22:00 - 09:00 (tick 100) -> 0.0 (Kapalı)
        self.assertEqual(generator._get_current_lambda(100), 0.0)

    def test_simulation_engine_step(self):
        import random
        random.seed(42)
        engine = SimulationEngine(CONFIG_PATH)
        engine.reset()
        engine.tick = 720  # 12:00 Açık pik saat
        
        for _ in range(100):
            engine.step()
            
        self.assertGreaterEqual(engine.tick, 820)
        # Check if some orders were generated
        has_orders = len(engine.order_queue) > 0 or len(engine.completed_orders) > 0 or any(len(t.current_orders) > 0 for t in engine.grid.tables.values())
        self.assertTrue(has_orders, "No orders were generated during open hours.")

if __name__ == "__main__":
    unittest.main()
