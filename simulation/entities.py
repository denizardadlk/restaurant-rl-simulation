import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class Order:
    table_id: str
    dish_type: str
    theoretical_time: float
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: str = "QUEUED"  # QUEUED, PREPARING, READY, DELIVERING, SERVED
    predicted_time: Optional[float] = None
    timestamps: Dict[str, Optional[float]] = field(default_factory=lambda: {
        "created_at": None,
        "kitchen_start": None,
        "kitchen_finish": None,
        "delivered_at": None
    })
    assigned_station_id: Optional[str] = None
    assigned_chef_id: Optional[str] = None
    assigned_waiter_id: Optional[str] = None
    
    # ML Features Snapshots (Captured exactly at kitchen_start to prevent target leakage)
    station_load_at_start: Optional[int] = None
    kitchen_load_at_start: Optional[int] = None
    chef_efficiency_at_start: Optional[float] = None
    day_tick_at_start: Optional[int] = None
    
    # True simulated cook time for the engine
    actual_target_time: Optional[float] = None

@dataclass
class Table:
    id: str
    x: int
    y: int
    capacity: int
    w: int = 1
    h: int = 1
    customers: int = 0
    patience: float = 20.0  # 0 to 20
    status: str = "EMPTY"  # EMPTY, WAITING_FOOD, EATING
    eating_time_remaining: float = 0.0
    current_orders: List[Order] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return self.status == "EMPTY"

@dataclass
class Station:
    id: str
    type: str  # OVEN, GRILL, STOVE, PREP
    x: int
    y: int
    capacity: int
    active_orders: List[Order] = field(default_factory=list)

    @property
    def is_full(self) -> bool:
        return len(self.active_orders) >= self.capacity

@dataclass
class Chef:
    id: str
    x: int
    y: int
    capacity: int
    efficiency: float = 1.0
    status: str = "IDLE"  # IDLE, COOKING
    active_orders: List[Order] = field(default_factory=list)

    @property
    def is_full(self) -> bool:
        return len(self.active_orders) >= self.capacity

@dataclass
class Waiter:
    id: str
    x: int
    y: int
    speed: float = 1.0
    status: str = "IDLE"  # IDLE, DELIVERING
    busy_until: float = 0.0
