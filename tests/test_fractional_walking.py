import unittest
from simulation.engine import SimulationEngine
from simulation.entities import Order, Table, Waiter, Chef, DeliveryCounter, Station
from simulation.time_config import TimeConfig

class TestFractionalWalking(unittest.TestCase):
    def test_waiter_30m_per_min_single_tick_delivery(self):
        engine = SimulationEngine("config/default_layout.json", difficulty_level=2)
        engine.reset()

        waiter = next(iter(engine.grid.waiters.values()))
        counter = engine.grid.delivery_counter
        table = next(iter(engine.grid.tables.values()))

        # Place waiter at counter
        waiter.x, waiter.y = counter.x, counter.y
        waiter.status = "IDLE"
        waiter.current_task = None
        waiter.carrying_orders.clear()

        # Create ready order
        order = Order(table_id=table.id, dish_type="Burger", theoretical_time=12.0, stages=[])
        order.status = "READY"
        counter.ready_orders.append(order)
        table.current_orders = [order]
        table.status = "WAITING_FOOD"

        # Dispatch delivery
        engine.waiter_manager._dispatch_food_delivery(waiter, order, table, tick=10)

        # Step tick 10: Waiter walks to table (5-15m in <1 min) and starts 1-min table service
        engine.waiter_manager.manage_waiters(tick=10)
        self.assertEqual(waiter.status, "DELIVERING")

        # Step tick 11: Waiter completes 1-min table service
        engine.waiter_manager.manage_waiters(tick=11)

        # Order must be SERVED and table EATING
        self.assertEqual(order.status, "SERVED")
        self.assertIn(order, engine.completed_orders)
        self.assertEqual(table.status, "EATING")
        self.assertEqual(waiter.status, "IDLE")

    def test_chef_instant_teleport_and_start(self):
        engine = SimulationEngine("config/default_layout.json", difficulty_level=2)
        engine.reset()
        engine.tick = 10

        chef = next(iter(engine.grid.chefs.values()))
        station = next(iter(engine.grid.stations.values()))

        # Chef placed far from station
        chef.x, chef.y = 0, 0
        chef.status = "IDLE"
        chef.current_task = None

        order = Order(table_id=1, dish_type="Toast", theoretical_time=7.0, stages=[{"station_type": station.type, "time": 7.0}])
        engine.assign_order(order, station, chef)

        # Chef teleports immediately and starts cooking in current tick (tick 10)
        self.assertEqual((chef.x, chef.y), (station.x, station.y))
        self.assertEqual(order.timestamps.get("kitchen_start"), 10)

if __name__ == "__main__":
    unittest.main()
