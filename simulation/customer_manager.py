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
        Decrements customer patience and handles churn or table clearing.
        """
        # 1. Dine-in Table Patience
        for table in self.engine.grid.tables.values():
            if table.status == "WAITING_FOOD":
                table.patience -= 0.1  # Patience drops by 0.1 per tick
                if table.patience <= 0:
                    # Churn: customers leave unsatisfied
                    self.engine.churned_customers += table.customers

                    # Remove unstarted orders from the order queue
                    for order in table.current_orders:
                        if order in self.engine.order_queue:
                            self.engine.order_queue.remove(order)

                    table.customers = 0
                    table.current_orders = []
                    table.status = "EMPTY"

            elif table.status == "EATING":
                table.eating_time_remaining -= 1
                if table.eating_time_remaining <= 0:
                    # Finished eating, table becomes available again
                    table.customers = 0
                    table.current_orders = []
                    table.status = "EMPTY"

        # 2. Takeout Patience (Courier wait time)
        for order in list(self.engine.order_queue):
            if order.is_takeout and order.courier_eta is not None:
                if tick > order.courier_eta + 45.0:  # Courier leaves after waiting 45 mins (1.5x)
                    self.engine.churned_customers += 1
                    if order in self.engine.order_queue:
                        self.engine.order_queue.remove(order)
