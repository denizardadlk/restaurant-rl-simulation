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
        # Peak hours 12:00-14:00 -> 720-840
        lambda_peak = generator._get_current_lambda(750)
        self.assertEqual(lambda_peak, generator.lambda_peak)
        
        lambda_normal = generator._get_current_lambda(100)
        self.assertEqual(lambda_normal, generator.lambda_normal)

    def test_simulation_engine_step(self):
        import random
        random.seed(42)
        engine = SimulationEngine(CONFIG_PATH)
        engine.reset()
        
        for _ in range(100):
            engine.step()
            
        self.assertGreaterEqual(engine.tick, 100)
        # Check if some orders were generated
        has_orders = len(engine.order_queue) > 0 or len(engine.completed_orders) > 0 or any(len(t.current_orders) > 0 for t in engine.grid.tables.values())
        self.assertTrue(has_orders, "No orders were generated in 100 ticks.")

if __name__ == "__main__":
    unittest.main()
