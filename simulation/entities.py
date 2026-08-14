import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class Order:
    table_id: Optional[str] # None for takeout orders
    dish_type: str
    theoretical_time: float # kept for compatibility, can be sum of stage times
    stages: List[Dict[str, Any]] = field(default_factory=list) # e.g. [{"station_type": "PREP", "time": 3.0}]
    current_stage_idx: int = 0
    is_takeout: bool = False
    courier_eta: Optional[float] = None
    
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: str = "QUEUED_STAGE"  # QUEUED_STAGE, PREPARING, READY, DELIVERING, SERVED
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
    orient: str = "H"
    customers: int = 0
    patience: float = 20.0  # 0 to 20
    status: str = "EMPTY"  # EMPTY, WAITING_FOOD, EATING
    eating_time_remaining: float = 0.0
    current_orders: List[Order] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return self.status == "EMPTY"
        
    @property
    def is_fully_ready_for_service(self) -> bool:
        if not self.current_orders:
            return False
        return all(o.status in ["READY", "DELIVERING", "SERVED"] for o in self.current_orders)

@dataclass
class Station:
    id: str
    type: str  # OVEN, GRILL, STOVE, PREP
    x: int
    y: int
    capacity: int
    batch_efficiency_factor: float = 0.85
    active_orders: List[Order] = field(default_factory=list)
    is_broken: bool = False
    broken_until: float = 0.0

    @property
    def is_full(self) -> bool:
        if self.is_broken:
            return True
        return len(self.active_orders) >= self.capacity

@dataclass
class Chef:
    id: str
    x: int
    y: int
    capacity: int = 2
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
