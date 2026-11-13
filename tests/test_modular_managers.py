import unittest
import os
from simulation.engine import SimulationEngine
from simulation.entities import Order

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "default_layout.json")

class TestModularManagers(unittest.TestCase):
    def setUp(self):
        self.engine = SimulationEngine(CONFIG_PATH)
        self.engine.reset()

    def test_customer_manager_patience_and_churn(self):
        # Simulate table with low patience
        table = self.engine.grid.tables["T1"]
        table.status = "WAITING_FOOD"
        table.customers = 4
        table.patience = 0.05
        
        dummy_order = Order(table_id="T1", dish_type="Pizza", theoretical_time=10.0)
        self.engine.order_queue.append(dummy_order)
        table.current_orders.append(dummy_order)
        
        # Advance customer manager
        self.engine.customer_manager.update_patience(self.engine.tick)
        
        # Patience should hit 0, table should be empty, churn count should increase
        self.assertEqual(table.status, "EMPTY")
        self.assertEqual(table.customers, 0)
        self.assertEqual(self.engine.churned_customers, 4)
        self.assertNotIn(dummy_order, self.engine.order_queue)

    def test_kitchen_manager_assign_order(self):
        order = Order(
            table_id="T1", 
            dish_type="Pizza", 
            theoretical_time=14.0,
            stages=[{"station_type": "OVEN", "time": 14.0}]
        )
        self.engine.order_queue.append(order)
        
        station = self.engine.grid.stations["S_OVEN_1"]
        chef = self.engine.grid.chefs["C1"]
        
        success = self.engine.assign_order(order, station, chef)
        self.assertTrue(success)
        self.assertEqual(order.status, "PREPARING")
        self.assertEqual(order.assigned_station_id, station.id)
        self.assertEqual(order.assigned_chef_id, chef.id)
        self.assertIsNotNone(order.station_load_at_start)
        self.assertIsNotNone(order.actual_target_time)
        self.assertIn(order, station.active_orders)
        self.assertNotIn(order, self.engine.order_queue)
        # After 1-min prep duration, chef is freed (IDLE) for set-and-forget OVEN
        self.engine.kitchen_manager.progress_cooking(tick=1)
        self.assertEqual(chef.status, "IDLE")

    def test_jit_waiter_manager_dispatch(self):
        table = self.engine.grid.tables["T1"]
        table.status = "WAITING_FOOD"
        table.customers = 4
        
        order = Order(
            table_id="T1",
            dish_type="Pizza",
            theoretical_time=14.0,
            stages=[{"station_type": "OVEN", "time": 14.0}],
            status="READY",
            assigned_station_id="S_OVEN_1"
        )
        order.timestamps["kitchen_start"] = 10
        order.timestamps["kitchen_finish"] = 24
        table.current_orders.append(order)
        
        # Run waiter manager
        self.engine.waiter_manager.manage_waiters(25)
        
        # A waiter should be assigned and state updated to DELIVERING
        self.assertEqual(order.status, "DELIVERING")
        self.assertIsNotNone(order.assigned_waiter_id)
        
        waiter = self.engine.grid.waiters[order.assigned_waiter_id]
        self.assertEqual(waiter.status, "DELIVERING")
        
        # Advance tick to delivery completion
        self.engine.waiter_manager.manage_waiters(int(waiter.busy_until) + 1)
        self.assertEqual(order.status, "SERVED")
        self.assertEqual(waiter.status, "IDLE")
        self.assertEqual(table.status, "EATING")

if __name__ == "__main__":
    unittest.main()
