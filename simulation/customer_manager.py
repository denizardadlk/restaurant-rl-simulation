from typing import TYPE_CHECKING, List
from .entities import Table, Order

if TYPE_CHECKING:
    from .engine import SimulationEngine

class CustomerManager:
    """
    Manages customer lifecycle, table patience, eating durations, and customer churn.
    """
    def __init__(self, engine: 'SimulationEngine'):
        self.engine = engine

    def update_patience(self, tick: int):
        """
        Decrements customer patience and handles churn or table clearing based on time_config.
        """
        patience_cfg = self.engine.time_config.customer_patience
        decay_rate = patience_cfg.get("decay_rate_per_tick", 0.1)
        waiter_cfg = self.engine.time_config.waiter_config
        clean_time = waiter_cfg.get("table_cleaning_duration", 2.0)
        max_courier_wait = patience_cfg.get("waiting_food_initial", 45.0)

        # 1. Dine-in Table Patience
        for table in self.engine.grid.tables.values():
            if table.status == "WAITING_ORDER":
                table.patience -= decay_rate
                if table.patience <= 0:
                    # Churn: customers leave before ordering
                    self.engine.churned_customers += table.customers
                    if getattr(self.engine, "analyzer", None):
                        self.engine.analyzer.record_churn("WAITING_ORDER", table.customers, table=table)
                    for o in list(table.pending_orders):
                        self.engine.churned_orders.append(o)
                    table.customers = 0
                    table.pending_orders.clear()
                    table.current_orders.clear()
                    table.status = "EMPTY"

            elif table.status == "WAITING_FOOD":
                table.patience -= decay_rate
                if table.patience <= 0:
                    # Churn: customers leave unsatisfied
                    self.engine.churned_customers += table.customers
                    if getattr(self.engine, "analyzer", None):
                        self.engine.analyzer.record_churn("WAITING_FOOD", table.customers, table=table)

                    # Record unserved churned orders and remove from everywhere
                    for order in list(table.current_orders):
                        if order.status != "SERVED":
                            self.engine.churned_orders.append(order)
                        if order in self.engine.order_queue:
                            self.engine.order_queue.remove(order)
                        # Remove from delivery counters and beverage counter
                        for c in self.engine.grid.delivery_counters.values():
                            if order in c.ready_orders:
                                c.ready_orders.remove(order)
                        if getattr(self.engine.grid, "beverage_counter", None) and order in self.engine.grid.beverage_counter.ready_orders:
                            self.engine.grid.beverage_counter.ready_orders.remove(order)
                        # Remove from stations
                        for s in self.engine.grid.stations.values():
                            if order in s.active_orders:
                                s.active_orders.remove(order)
                        # Remove from chefs
                        for ch in self.engine.grid.chefs.values():
                            if order in ch.active_orders:
                                ch.active_orders.remove(order)
                            if order in ch.carrying_orders:
                                ch.carrying_orders.remove(order)
                            if ch.current_task and ch.current_task.get("order_id") == order.order_id:
                                self.engine.kitchen_manager._reset_chef_to_idle(ch)

                        # Remove from waiters
                        for w in self.engine.grid.waiters.values():
                            if order in w.carrying_orders:
                                w.carrying_orders.remove(order)
                            if w.current_task and (w.current_task.get("target_table_id") == table.id or w.current_task.get("order_id") == order.order_id):
                                self.engine.waiter_manager._reset_waiter_to_idle(w)

                    table.customers = 0
                    table.current_orders.clear()
                    table.status = "EMPTY"

            elif table.status == "EATING":
                table.eating_time_remaining -= 1
                if table.eating_time_remaining <= 0:
                    # Finished eating, table becomes dirty and needs cleaning
                    table.customers = 0
                    table.current_orders.clear()
                    table.status = "DIRTY"
                    table.clean_time_remaining = clean_time

        # 2. Takeout Patience (Courier wait time)
        all_counters = list(self.engine.grid.delivery_counters.values())
        if getattr(self.engine.grid, "takeout_counter", None):
            all_counters.append(self.engine.grid.takeout_counter)

        for order in list(self.engine.order_queue):
            if order.is_takeout and order.courier_eta is not None:
                if tick > order.courier_eta + max_courier_wait:
                    self.engine.churned_customers += 1
                    if getattr(self.engine, "analyzer", None):
                        self.engine.analyzer.record_churn("TAKEOUT_COURIER", 1)
                    if order in self.engine.order_queue:
                        self.engine.order_queue.remove(order)
                    for c in all_counters:
                        if order in c.ready_orders:
                            c.ready_orders.remove(order)
