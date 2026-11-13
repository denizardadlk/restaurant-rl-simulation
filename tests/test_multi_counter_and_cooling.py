import unittest
import os
import json
from simulation.engine import SimulationEngine
from simulation.entities import Order, Table, Station, Chef, DeliveryCounter
from simulation.waiter_gym_env import WaiterGymEnv

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "default_layout.json")

class TestMultiCounterAndCooling(unittest.TestCase):
    def setUp(self):
        self.engine = SimulationEngine(CONFIG_PATH, auto_generate_orders=False)
        self.engine.reset()

    def test_multi_counter_loading(self):
        """Test that multiple counters are parsed properly into grid.delivery_counters."""
        grid = self.engine.grid
        self.assertGreaterEqual(len(grid.delivery_counters), 1)
        self.assertIsNotNone(grid.delivery_counter)
        for c_id, counter in grid.delivery_counters.items():
            self.assertIsInstance(counter, DeliveryCounter)
            self.assertIn((counter.x, counter.y), grid.obstacles)

    def test_chef_nearest_available_counter_selection(self):
        """Test that chef delivers to the nearest non-full counter when one is full."""
        grid = self.engine.grid
        # Ensure at least 2 counters exist
        c1 = grid.delivery_counters.get("COUNTER_1")
        if "COUNTER_2" not in grid.delivery_counters:
            c2 = DeliveryCounter(id="COUNTER_2", x=c1.x, y=c1.y + 1, capacity=4)
            grid.delivery_counters["COUNTER_2"] = c2
            grid.obstacles.add((c2.x, c2.y))
        else:
            c2 = grid.delivery_counters["COUNTER_2"]

        # Fill C1 completely
        c1.ready_orders = [
            Order(table_id="T1", dish_type="Pizza", theoretical_time=5.0, status="READY")
            for _ in range(c1.capacity)
        ]
        self.assertTrue(c1.is_full)
        c2.ready_orders.clear()
        self.assertFalse(c2.is_full)

        chef = grid.chefs["C1"]
        best_counter = self.engine.kitchen_manager._find_best_counter_for_chef(chef)
        self.assertEqual(best_counter.id, "COUNTER_2")

        # Drop order
        new_order = Order(table_id="T2", dish_type="Burger", theoretical_time=5.0)
        chef.carrying_orders.append(new_order)
        dropped = self.engine.kitchen_manager._drop_order_at_counter(chef, new_order, self.engine.tick, counter=best_counter)
        self.assertTrue(dropped)
        self.assertEqual(new_order.assigned_counter_id, "COUNTER_2")
        self.assertIn(new_order, c2.ready_orders)
        self.assertNotIn(new_order, c1.ready_orders)

    def test_waiter_picks_up_from_assigned_counter(self):
        """Test that waiter targets the exact counter where order was placed."""
        grid = self.engine.grid
        c2 = grid.delivery_counters.get("COUNTER_2")
        if not c2:
            c2 = DeliveryCounter(id="COUNTER_2", x=7, y=5, capacity=4)
            grid.delivery_counters["COUNTER_2"] = c2

        table = grid.tables["T1"]
        table.status = "WAITING_FOOD"
        order = Order(table_id="T1", dish_type="Pasta", theoretical_time=5.0, status="READY", assigned_counter_id="COUNTER_2")
        table.current_orders.append(order)
        c2.ready_orders.append(order)

        waiter = grid.waiters["W1"]
        self.engine.waiter_manager._dispatch_food_delivery(waiter, order, table, self.engine.tick)

        self.assertEqual(waiter.current_task.get("counter_id"), "COUNTER_2")
        self.assertEqual(waiter.status, "DELIVERING")

        # Process steps until waiter picks up food and delivers
        for t in range(1, 25):
            self.engine.tick = t
            self.engine.waiter_manager.manage_waiters(t)
            if table.status == "EATING":
                break

        self.assertEqual(order.status, "SERVED")
        self.assertNotIn(order, c2.ready_orders)

    def test_grace_period_cooling(self):
        """Test that cooling penalty is 0 during first 5 ticks (grace period) and increases after."""
        order = Order(table_id="T1", dish_type="Steak", theoretical_time=10.0)
        order.timestamps["kitchen_finish"] = 10.0

        # At tick 12 (2 ticks on counter) -> within 5-tick grace period
        self.assertEqual(order.get_cold_time(current_tick=12, grace_period=5.0), 0.0)

        # At tick 15 (5 ticks on counter) -> exact end of grace period
        self.assertEqual(order.get_cold_time(current_tick=15, grace_period=5.0), 0.0)

        # At tick 18 (8 ticks on counter) -> 3 ticks cold
        self.assertEqual(order.get_cold_time(current_tick=18, grace_period=5.0), 3.0)

        # At tick 25 (15 ticks on counter) -> 10 ticks cold
        self.assertEqual(order.get_cold_time(current_tick=25, grace_period=5.0), 10.0)

    def test_waiter_gym_env_integration(self):
        """Test WaiterGymEnv observation and step transitions."""
        env = WaiterGymEnv(config_path=CONFIG_PATH, max_ticks=20)
        obs, info = env.reset(seed=42)
        self.assertEqual(len(obs), env.obs_dim)
        self.assertGreater(env.num_actions, 1)

        # Step NO-OP
        obs, reward, terminated, truncated, info = env.step(0)
        self.assertFalse(terminated)
        self.assertEqual(len(obs), env.obs_dim)

        # Step Pickup Counter 1
        obs, reward, terminated, truncated, info = env.step(1)
        self.assertFalse(terminated)

    def test_enable_rl_waiter_prevents_rule_based_dispatch(self):
        """Test that enable_rl_waiter flag prevents engine from auto-dispatching waiters."""
        engine = SimulationEngine(config_path=CONFIG_PATH, auto_generate_orders=False, enable_rl_waiter=True)
        engine.reset()
        engine.enable_rl_waiter = True

        table = engine.grid.tables["T1"]
        table.status = "WAITING_ORDER"
        table.pending_orders.append(Order(table_id="T1", dish_type="Salad", theoretical_time=5.0))

        # Advance engine step with enable_rl_waiter = True
        engine.step()

        # Rule-based dispatch should NOT have dispatched idle waiters
        self.assertEqual(table.status, "WAITING_ORDER")
        self.assertTrue(all(w.status == "IDLE" for w in engine.grid.waiters.values()))

        # Now set enable_rl_waiter = False
        engine.enable_rl_waiter = False
        engine.step()

        # Rule-based dispatch SHOULD now dispatch an idle waiter
        assigned = any(w.status != "IDLE" or w.current_task is not None for w in engine.grid.waiters.values())
        self.assertTrue(assigned)

if __name__ == "__main__":
    unittest.main()
