import unittest
from simulation.engine import SimulationEngine
from simulation.entities import Order, Table, Chef

class TestKitchenCarryingAndPickup(unittest.TestCase):
    def test_waiting_pickup_station_blocking(self):
        engine = SimulationEngine('layouts/custom_layout.json', difficulty_level=2)
        engine.reset()
        grill = next(s for s in engine.grid.stations.values() if s.type == 'GRILL')
        grill.capacity = 1
        grill.active_orders.clear()
        
        chef = next(iter(engine.grid.chefs.values()))
        chef.status = 'IDLE'
        chef.active_orders.clear()
        
        order = Order(table_id='T1', dish_type='Burger', theoretical_time=2.0, stages=[{'station_type': 'GRILL', 'time': 2.0}])
        engine.order_queue.append(order)
        engine.assign_order(order, grill, chef)
        
        # At tick 1, cooking starts
        order.actual_target_time = 2.0
        engine.tick = 1
        engine.kitchen_manager.progress_cooking(1)
        
        # At tick 3, cooking is done (2 mins passed)
        # Order should transition to WAITING_PICKUP and block grill capacity
        engine.tick = 3
        # Freeze chefs busy to observe WAITING_PICKUP before auto-dispatch
        for c in engine.grid.chefs.values():
            c.status = 'COOKING'
            c.busy_until = 999
        engine.kitchen_manager.progress_cooking(3)
        
        self.assertEqual(order.status, 'WAITING_PICKUP')
        self.assertEqual(len(grill.active_orders), 1)
        self.assertTrue(grill.is_full)
        
    def test_chef_carrying_max_2_plates_and_plating(self):
        engine = SimulationEngine('layouts/custom_layout.json', difficulty_level=2)
        engine.reset()
        grill = next(s for s in engine.grid.stations.values() if s.type == 'GRILL')
        grill.capacity = 5
        grill.active_orders.clear()
        
        chef = next(iter(engine.grid.chefs.values()))
        chef.x, chef.y = grill.x, grill.y
        chef.status = 'IDLE'
        chef.active_orders.clear()
        chef.carrying_orders.clear()
        
        # Put 3 WAITING_PICKUP orders on grill
        orders = [
            Order(table_id=f'T{i}', dish_type='Burger', status='WAITING_PICKUP', theoretical_time=2.0, stages=[{'station_type': 'GRILL', 'time': 2.0}])
            for i in range(1, 4)
        ]
        grill.active_orders = list(orders)
        
        # Dispatch chef to pick up
        engine.tick = 1
        engine.kitchen_manager._dispatch_chef_pickup_to_counter(chef, grill, grill.active_orders, tick=1)
        
        # Chef can only carry max 2 plates
        self.assertEqual(len(chef.carrying_orders), 2)
        # 1 order remains on grill!
        self.assertEqual(len(grill.active_orders), 1)
        self.assertEqual(chef.status, 'DELIVERING_TO_COUNTER')

    def test_multi_stage_transfer_between_stations(self):
        engine = SimulationEngine('layouts/custom_layout.json', difficulty_level=2)
        engine.reset()
        grill = next(s for s in engine.grid.stations.values() if s.type == 'GRILL')
        prep = next(s for s in engine.grid.stations.values() if s.type == 'PREP')
        grill.capacity = 1
        prep.capacity = 1
        grill.active_orders.clear()
        prep.active_orders.clear()
        
        chef = next(iter(engine.grid.chefs.values()))
        chef.x, chef.y = grill.x, grill.y
        chef.status = 'IDLE'
        
        # 2-stage dish: GRILL -> PREP
        order = Order(
            table_id='T1',
            dish_type='Burger',
            status='WAITING_PICKUP_STAGE',
            theoretical_time=10.0,
            stages=[{'station_type': 'GRILL', 'time': 5.0}, {'station_type': 'PREP', 'time': 2.0}]
        )
        grill.active_orders = [order]
        
        # Dispatch stage transfer
        engine.tick = 1
        engine.kitchen_manager._dispatch_chef_stage_transfer(chef, grill, prep, order, tick=1)
        
        self.assertEqual(chef.status, 'TRANSFERRING_STAGE')
        # Grill capacity freed immediately upon pickup
        self.assertEqual(len(grill.active_orders), 0)
        self.assertEqual(len(chef.carrying_orders), 1)

if __name__ == '__main__':
    unittest.main()
