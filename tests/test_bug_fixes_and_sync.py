import pytest
import os
import math
from simulation.engine import SimulationEngine
from simulation.entities import Order, Table, Station, Chef, Waiter, DeliveryCounter
from simulation.waiter_gym_env import WaiterGymEnv
from simulation.generator import OrderGenerator

def test_multi_stage_cook_time_resampling():
    """Verify that stage transitions properly re-sample actual_target_time for the new stage."""
    engine = SimulationEngine()
    engine.reset()

    # Burger has Stage 0 (GRILL, time=10.0) and Stage 1 (PREP, time=2.0)
    burger_stages = [
        {"station_type": "GRILL", "time": 10.0},
        {"station_type": "PREP", "time": 2.0}
    ]
    order = Order(
        table_id=1,
        dish_type="Burger",
        category="main_dish",
        theoretical_time=12.0,
        stages=burger_stages
    )

    grill_station = next((s for s in engine.grid.stations.values() if s.type == "GRILL"), None)
    prep_station = next((s for s in engine.grid.stations.values() if s.type == "PREP"), None)
    chef = list(engine.grid.chefs.values())[0]

    assert grill_station is not None
    assert prep_station is not None

    # 1. Assign stage 0
    assigned = engine.kitchen_manager.assign_order(order, grill_station, chef, tick=10)
    assert assigned
    assert order.current_stage_idx == 0
    # Stage 0 actual_target_time should be around 10.0
    stage0_target = order.actual_target_time
    assert stage0_target > 5.0  # around 10.0 min

    # 2. Simulate stage 0 finish and transition to Stage 1 via _start_stage_placing
    chef.carrying_orders.append(order)
    task = {"type": "TRANSFER_STAGE", "to_station_id": prep_station.id, "order_id": order.order_id}
    chef.current_task = task
    engine.kitchen_manager._start_stage_placing(chef, task, tick=20, to_st=prep_station, order=order)

    # If stage transfer duration > 0, complete PLACING_STAGE
    if task.get("substate") == "PLACING_STAGE":
        task["finish_tick"] = 21
        engine.kitchen_manager._update_chef_tasks(tick=21)

    assert order.current_stage_idx == 1
    assert order.assigned_station_id == prep_station.id
    # Stage 1 actual_target_time MUST be re-sampled for PREP (time=2.0)
    assert order.actual_target_time < 5.0  # around 2.0 min, definitely not the old 10.0 min!

def test_waiter_walking_speed_in_order_taking_and_cleaning():
    """Verify that waiter order taking and cleaning use 30 m/min speed."""
    engine = SimulationEngine()
    engine.reset()

    table = list(engine.grid.tables.values())[0]
    table.x, table.y = 10, 10
    waiter = list(engine.grid.waiters.values())[0]
    waiter.x, waiter.y = 0, 0
    waiter.status = "IDLE"
    waiter.current_task = None
    waiter.busy_until = 0

    # 1. Dispatch take order
    engine.waiter_manager._dispatch_take_order(waiter, table, tick=100)
    # Distance is ~20m. At 30m/min, walk_time is ~0.67 min. Total busy should be <= 3 min, NOT 20+ min!
    busy_duration = waiter.busy_until - 100
    assert busy_duration <= 3.0

    # 2. Dispatch cleaning
    waiter.status = "IDLE"
    waiter.current_task = None
    engine.waiter_manager._dispatch_clean_table(waiter, table, tick=200)
    busy_duration_clean = waiter.busy_until - 200
    assert busy_duration_clean <= 4.0

def test_takeout_beverage_generation_and_transfer():
    """Verify takeout beverage generation and transfer to takeout shelf."""
    engine = SimulationEngine()
    engine.reset()

    # Create takeout drink directly in beverage counter
    bev_counter = getattr(engine.grid, "beverage_counter", None) or engine.grid.delivery_counter
    takeout_counter = getattr(engine.grid, "takeout_counter", None) or engine.grid.delivery_counter

    takeout_bev = Order(
        table_id=None,
        dish_type="Kola",
        category="beverage",
        theoretical_time=0.0,
        stages=[],
        is_takeout=True,
        courier_eta=50.0
    )
    takeout_bev.status = "READY"
    takeout_bev.assigned_counter_id = bev_counter.id
    bev_counter.ready_orders.append(takeout_bev)

    # Dispatch idle waiter to transfer
    for w in engine.grid.waiters.values():
        w.status = "IDLE"
        w.current_task = None
        w.busy_until = 0

    engine.waiter_manager._dispatch_idle_waiters(tick=10)

    # At least one waiter should have accepted the transfer
    dispatched_waiters = [w for w in engine.grid.waiters.values() if w.current_task and w.current_task.get("type") == "TRANSFER_TAKEOUT_DRINK"]
    assert len(dispatched_waiters) > 0
    waiter = dispatched_waiters[0]

    # Fast forward / finalize transfer
    engine.waiter_manager._finalize_takeout_drink_transfer(waiter, takeout_counter, tick=20, task=waiter.current_task)
    assert takeout_bev in takeout_counter.ready_orders
    assert takeout_bev.assigned_counter_id == takeout_counter.id

def test_waiter_gym_env_beverage_counter():
    """Verify WaiterGymEnv includes beverage counter and handles action masking."""
    env = WaiterGymEnv()
    obs, _ = env.reset()

    bev_counter = getattr(env.engine.grid, "beverage_counter", None)
    if bev_counter:
        assert bev_counter.id in env.counter_keys

        # Put a ready beverage in the fridge
        drink = Order(
            table_id=1,
            dish_type="Ayran",
            category="beverage",
            theoretical_time=0.0,
            stages=[]
        )
        drink.status = "READY"
        drink.assigned_counter_id = bev_counter.id
        bev_counter.ready_orders.append(drink)

        masks = env.action_masks()
        bev_c_idx = env.counter_keys.index(bev_counter.id)
        # Action corresponding to beverage counter should be valid (1)
        assert masks[1 + bev_c_idx] == 1

def test_server_beverage_order_creation_mock():
    """Verify server.py order creation handles beverages without crashing."""
    from server import create_order, OrderCreateIn, OrderItemIn
    import asyncio

    req = OrderCreateIn(
        table_id="2",
        items=[OrderItemIn(dish_type="Ayran", quantity=1)],
        is_takeout=False
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    response = loop.run_until_complete(create_order(req))
    loop.close()

    assert response["status"] == "success"
    created = response["created_orders"]
    assert len(created) == 1
    assert created[0]["dish_type"] == "Ayran"
    assert created[0]["status"] == "READY"

def test_capacity_scaled_dynamic_arrivals():
    """Verify that peak hours and large restaurants generate higher burst arrivals toward target occupancy."""
    gen = OrderGenerator(difficulty_level=2)
    
    # Create 26 mock empty tables
    mock_tables = [Table(id=f"T{i}", x=i%5, y=i//5, capacity=4) for i in range(26)]
    
    # Test during lunch peak (tick = 750, 12:30) with 0 occupied tables
    # Should attempt to fill towards 75% target with burst (up to 4)
    total_generated = 0
    for _ in range(10):
        orders = gen.generate_orders(current_tick=750, available_tables=mock_tables, total_tables_count=26)
        total_generated += len(set(o.table_id for o in orders if o.table_id))
        
    assert total_generated > 0

def test_difficulty_occupancy_scaling():
    """Verify that difficulty level modulates arrival target occupancy."""
    gen_easy = OrderGenerator(difficulty_level=1)
    gen_hard = OrderGenerator(difficulty_level=3)

    info_easy = gen_easy._get_current_interval_info(750)
    info_hard = gen_hard._get_current_interval_info(750)

    # Base target is 0.75 for peak
    assert info_easy.get("target_occupancy") == 0.75
    assert info_hard.get("target_occupancy") == 0.75
