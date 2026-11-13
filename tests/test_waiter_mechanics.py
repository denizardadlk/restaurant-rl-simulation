import unittest
import os
from simulation.engine import SimulationEngine
from simulation.entities import Order, Table, Waiter

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "default_layout.json")

class TestWaiterMechanics(unittest.TestCase):
    def setUp(self):
        self.engine = SimulationEngine(CONFIG_PATH, auto_generate_orders=False)
        self.engine.reset()

    def test_pathfinder_step_by_step_path(self):
        pathfinder = self.engine.pathfinder
        table = self.engine.grid.tables["T1"]
        station = self.engine.grid.stations["S_OVEN_1"]

        path = pathfinder.get_path((table.x, table.y), (station.x, station.y))
        self.assertIsInstance(path, list)
        self.assertGreater(len(path), 0)
        self.assertEqual(path[0], (table.x, table.y))
        self.assertEqual(path[-1], (station.x, station.y))

        # Check connectivity: each step should be a 4-way neighbor
        for i in range(len(path) - 1):
            dx = abs(path[i+1][0] - path[i][0])
            dy = abs(path[i+1][1] - path[i][1])
            self.assertEqual(dx + dy, 1, f"Path step between {path[i]} and {path[i+1]} is not adjacent")

    def test_waiter_order_taking_flow(self):
        table = self.engine.grid.tables["T1"]
        table.status = "WAITING_ORDER"
        table.customers = 2
        table.patience = 30.0

        o1 = Order(table_id="T1", dish_type="Pizza", theoretical_time=10.0, stages=[{"station_type": "OVEN", "time": 10.0}])
        o2 = Order(table_id="T1", dish_type="Salad", theoretical_time=5.0, stages=[{"station_type": "PREP", "time": 5.0}])
        table.pending_orders.extend([o1, o2])

        # Initial dispatch tick
        self.engine.waiter_manager.manage_waiters(self.engine.tick)

        # Waiter should be assigned to take order
        busy_waiters = [w for w in self.engine.grid.waiters.values() if w.status in ["TAKING_ORDER", "WALKING"]]
        self.assertGreater(len(busy_waiters), 0)

        # Advance ticks until order is taken
        for t in range(1, 20):
            self.engine.tick = t
            self.engine.waiter_manager.manage_waiters(t)
            if table.status == "WAITING_FOOD":
                break

        self.assertEqual(table.status, "WAITING_FOOD")
        self.assertEqual(len(table.pending_orders), 0)
        self.assertEqual(len(table.current_orders), 2)
        self.assertIn(o1, self.engine.order_queue)
        self.assertIn(o2, self.engine.order_queue)

    def test_waiter_batch_delivery(self):
        table = self.engine.grid.tables["T1"]
        table.status = "WAITING_FOOD"
        table.customers = 2

        station = self.engine.grid.stations["S_OVEN_1"]

        o1 = Order(table_id="T1", dish_type="Pizza", theoretical_time=10.0, stages=[{"station_type": "OVEN", "time": 10.0}], status="READY", assigned_station_id=station.id)
        o2 = Order(table_id="T1", dish_type="Burger", theoretical_time=10.0, stages=[{"station_type": "STOVE", "time": 10.0}], status="READY", assigned_station_id=station.id)
        table.current_orders.extend([o1, o2])

        # Run dispatch
        self.engine.waiter_manager.manage_waiters(self.engine.tick)

        # Advance ticks to pick up and deliver
        for t in range(1, 30):
            self.engine.tick = t
            self.engine.waiter_manager.manage_waiters(t)
            if table.status == "EATING":
                break

        self.assertEqual(o1.status, "SERVED")
        self.assertEqual(o2.status, "SERVED")
        self.assertEqual(table.status, "EATING")
        self.assertIn(o1, self.engine.completed_orders)
        self.assertIn(o2, self.engine.completed_orders)

    def test_table_cleaning_flow(self):
        table = self.engine.grid.tables["T1"]
        table.status = "DIRTY"
        table.clean_time_remaining = 3.0

        # Run dispatch
        self.engine.waiter_manager.manage_waiters(self.engine.tick)

        # Advance ticks until cleaned
        for t in range(1, 20):
            self.engine.tick = t
            self.engine.waiter_manager.manage_waiters(t)
            if table.status == "EMPTY":
                break

        self.assertEqual(table.status, "EMPTY")

    def test_waiting_order_patience_churn(self):
        table = self.engine.grid.tables["T1"]
        table.status = "WAITING_ORDER"
        table.customers = 4
        table.patience = 0.05

        o1 = Order(table_id="T1", dish_type="Pizza", theoretical_time=10.0)
        table.pending_orders.append(o1)

        self.engine.customer_manager.update_patience(self.engine.tick)

        self.assertEqual(table.status, "EMPTY")
        self.assertEqual(table.customers, 0)
        self.assertEqual(self.engine.churned_customers, 4)
        self.assertEqual(len(table.pending_orders), 0)

if __name__ == "__main__":
    unittest.main()
