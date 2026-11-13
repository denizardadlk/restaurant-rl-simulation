import unittest
import os
from simulation.engine import SimulationEngine
from simulation.entities import Order, Table, Station, Chef, DeliveryCounter

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "default_layout.json")

class TestChefMovementAndCounter(unittest.TestCase):
    def setUp(self):
        self.engine = SimulationEngine(CONFIG_PATH, auto_generate_orders=False)
        self.engine.reset()

    def test_delivery_counter_initialization(self):
        """Test that DeliveryCounter is initialized properly on RestaurantGrid."""
        counter = self.engine.grid.delivery_counter
        self.assertIsNotNone(counter)
        self.assertIsInstance(counter, DeliveryCounter)
        self.assertEqual(counter.id, "COUNTER_1")
        self.assertEqual(len(counter.ready_orders), 0)
        self.assertIn((counter.x, counter.y), self.engine.grid.obstacles)

    def test_chef_movement_to_station_and_cooking(self):
        """Test that chef navigates step-by-step to the assigned station."""
        order = Order(
            table_id="T1",
            dish_type="Pizza",
            theoretical_time=10.0,
            stages=[{"station_type": "OVEN", "time": 10.0}]
        )
        self.engine.order_queue.append(order)

        station = self.engine.grid.stations["S_OVEN_1"]
        chef = self.engine.grid.chefs["C1"]

        # Place chef at a different location (e.g. at delivery counter or 7, 5)
        counter = self.engine.grid.delivery_counter
        chef.x, chef.y = counter.x, counter.y
        chef.status = "IDLE"
        chef.path.clear()
        chef.active_orders.clear()

        # Assign order -> Immediate start with 1-min station prep
        assigned = self.engine.assign_order(order, station, chef)
        self.assertTrue(assigned)
        self.assertEqual((chef.x, chef.y), (station.x, station.y))
        self.assertIsNotNone(order.timestamps.get("kitchen_start"))
        # After 1-min prep duration, chef is freed (IDLE) for set-and-forget OVEN
        self.engine.kitchen_manager.progress_cooking(tick=1)
        self.assertEqual(chef.status, "IDLE")

    def test_chef_delivers_to_counter_and_waiter_picks_up(self):
        """Test full pipeline: Set-and-forget cooking -> Delivery to Counter -> Waiter picks up -> Table."""
        table = self.engine.grid.tables["T1"]
        table.status = "WAITING_FOOD"
        table.customers = 2

        order = Order(
            table_id="T1",
            dish_type="Pizza",
            theoretical_time=5.0,
            stages=[{"station_type": "OVEN", "time": 5.0}]
        )
        table.current_orders.append(order)
        self.engine.order_queue.append(order)

        station = self.engine.grid.stations["S_OVEN_1"]
        chef = self.engine.grid.chefs["C1"]
        counter = self.engine.grid.delivery_counter

        # Start chef directly at station
        chef.x, chef.y = station.x, station.y
        self.engine.assign_order(order, station, chef)

        # In set-and-forget, dish is in station and kitchen_start is stamped
        self.assertIsNotNone(order.timestamps.get("kitchen_start"))
        order.actual_target_time = 4.0

        # Step until cooking finishes and chef delivers to counter
        delivered_to_counter = False
        for t in range(1, 30):
            self.engine.tick = t
            self.engine.kitchen_manager.progress_cooking(t)
            self.engine.waiter_manager.manage_waiters(t)

            if order in counter.ready_orders or order.status in ["READY", "DELIVERING", "SERVED"]:
                delivered_to_counter = True

            if table.status == "EATING":
                break

        self.assertTrue(delivered_to_counter, "Order was never delivered to counter or served")
        self.assertEqual(order.status, "SERVED")
        self.assertEqual(table.status, "EATING")
        self.assertIn(order, self.engine.completed_orders)

    def test_counter_holds_multiple_ready_orders(self):
        """Test that DeliveryCounter can hold multiple dishes from different chefs up to capacity."""
        counter = self.engine.grid.delivery_counter
        self.assertEqual(counter.capacity, 4)
        o1 = Order(table_id="T1", dish_type="Pizza", theoretical_time=5.0, status="READY")
        o2 = Order(table_id="T2", dish_type="Burger", theoretical_time=5.0, status="READY")

        counter.ready_orders.extend([o1, o2])
        self.assertEqual(len(counter.ready_orders), 2)
        self.assertFalse(counter.is_full)

    def test_counter_capacity_limit_and_chef_waiting(self):
        """Test that DeliveryCounter rejects 5th dish when capacity is 4, and chef waits."""
        counter = self.engine.grid.delivery_counter
        self.assertEqual(counter.capacity, 4)

        # Fill counter with 4 orders
        for i in range(4):
            counter.ready_orders.append(Order(table_id="T1", dish_type="Pizza", theoretical_time=5.0, status="READY"))

        self.assertTrue(counter.is_full)
        self.assertEqual(len(counter.ready_orders), 4)

        # 5th order cooked by Chef
        chef = self.engine.grid.chefs["C1"]
        o5 = Order(table_id="T2", dish_type="Salad", theoretical_time=5.0)
        chef.carrying_orders.append(o5)

        # Try dropping order at full counter
        dropped = self.engine.kitchen_manager._drop_order_at_counter(chef, o5, self.engine.tick)
        self.assertFalse(dropped, "Chef dropped food onto a full counter!")
        self.assertIn(o5, chef.carrying_orders)
        self.assertEqual(len(counter.ready_orders), 4)

        # Waiter frees up space by taking 1 dish
        counter.ready_orders.pop(0)
        self.assertFalse(counter.is_full)

        # Chef can now drop the 5th order
        dropped_retry = self.engine.kitchen_manager._drop_order_at_counter(chef, o5, self.engine.tick)
        self.assertTrue(dropped_retry)
        self.assertNotIn(o5, chef.carrying_orders)
        self.assertIn(o5, counter.ready_orders)
        self.assertEqual(len(counter.ready_orders), 4)

    def test_10_chefs_drop_10_burgers_on_single_10_capacity_grill(self):
        """Verify that 10 different chefs can assign 10 burger orders to a single 10-capacity grill, and all 10 cook in parallel."""
        self.engine.grid.delivery_counter.capacity = 20
        grill = self.engine.grid.stations.get("S_GRILL_1")
        self.assertIsNotNone(grill)
        grill.capacity = 10
        grill.active_orders.clear()

        # Create 10 chefs (or use existing chefs)
        chefs = []
        for i in range(1, 11):
            c_id = f"C{i}"
            if c_id not in self.engine.grid.chefs:
                self.engine.grid.chefs[c_id] = Chef(id=c_id, x=grill.x, y=grill.y, capacity=4, efficiency=1.0)
            c = self.engine.grid.chefs[c_id]
            c.x, c.y = grill.x, grill.y
            c.status = "IDLE"
            c.active_orders.clear()
            chefs.append(c)

        orders = []
        for i in range(10):
            order = Order(
                table_id=f"T{i+1}",
                dish_type="Burger",
                theoretical_time=10.0,
                stages=[{"station_type": "GRILL", "time": 10.0}]
            )
            orders.append(order)
            self.engine.order_queue.append(order)
            # Assign order to grill with different chef
            success = self.engine.assign_order(order, grill, chefs[i])
            self.assertTrue(success, f"Failed to assign burger {i+1} to 10-capacity grill!")

        # All 10 orders must be actively in grill
        self.assertEqual(len(grill.active_orders), 10)
        self.assertTrue(grill.is_full)

        # All 10 orders must have started cooking (kitchen_start set)
        for order in orders:
            self.assertIsNotNone(order.timestamps.get("kitchen_start"))

        # Step simulation by 1 tick: all 10 chefs finish 1-min prep and become freed (IDLE)
        self.engine.tick = 1
        self.engine.kitchen_manager.progress_cooking(tick=1)
        for chef in chefs:
            self.assertEqual(chef.status, "IDLE")
            # Dishes remain in chef.active_orders to count against 8-dish quota until cooked
            self.assertEqual(len(chef.active_orders), 1)

        # Step simulation to cook and deliver all 10 burgers simultaneously
        for t in range(2, 40):
            self.engine.tick = t
            self.engine.kitchen_manager.progress_cooking(t)
            if len(grill.active_orders) == 0 and all(len(c.carrying_orders) == 0 for c in chefs):
                break

        # All 10 burgers must have finished cooking on grill, picked up and delivered to counter
        self.assertEqual(len(grill.active_orders), 0)
        for chef in chefs:
            self.assertEqual(len(chef.active_orders), 0)

if __name__ == "__main__":
    unittest.main()
