import unittest
from simulation.engine import SimulationEngine
from simulation.entities import Order, Table
from simulation.generator import OrderGenerator

class TestMenuCategoriesAndDrinks(unittest.TestCase):
    def test_menu_categories_loading(self):
        engine = SimulationEngine('layouts/custom_layout.json', difficulty_level=2)
        engine.reset()
        self.assertIsNotNone(engine.grid.beverage_counter)
        self.assertEqual(engine.grid.beverage_counter.id, 'BEVERAGE_FRIDGE')
        
        cfg = engine.time_config
        self.assertIn('Burger', cfg.menu_categories['main_dishes'])
        self.assertIn('Patates', cfg.menu_categories['appetizers'])
        self.assertIn('Kola', cfg.menu_categories['beverages'])
        
    def test_order_taking_routes_drinks_to_fridge(self):
        engine = SimulationEngine('layouts/custom_layout.json', difficulty_level=2)
        engine.reset()
        table = engine.grid.tables['T1']
        waiter = next(iter(engine.grid.waiters.values()))
        
        drink_order = Order(table_id=table.id, dish_type='Kola', category='beverage', theoretical_time=0.0, stages=[])
        food_order = Order(table_id=table.id, dish_type='Burger', category='main_dish', theoretical_time=12.0, stages=[{'station_type': 'GRILL', 'time': 10.0}])
        
        table.pending_orders = [drink_order, food_order]
        table.status = 'WAITING_ORDER'
        
        engine.waiter_manager._finalize_order_taking(waiter, table, tick=10)
        
        # Drink must be in beverage counter ready_orders
        self.assertIn(drink_order, engine.grid.beverage_counter.ready_orders)
        self.assertEqual(drink_order.status, 'READY')
        # Food must be in engine order_queue
        self.assertIn(food_order, engine.order_queue)
        self.assertEqual(food_order.status, 'QUEUED_STAGE')
        self.assertEqual(table.status, 'WAITING_FOOD')

if __name__ == '__main__':
    unittest.main()
