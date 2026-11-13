import asyncio
import json
import os
import socket
import sys
import threading
import webbrowser
from typing import List, Optional, Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from simulation.engine import SimulationEngine
from simulation.entities import Order

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAYOUT_PATH = os.path.join(BASE_DIR, "layouts", "custom_layout.json")
if not os.path.exists(LAYOUT_PATH):
    LAYOUT_PATH = os.path.join(BASE_DIR, "layouts", "default_layout.json")
if not os.path.exists(LAYOUT_PATH):
    LAYOUT_PATH = os.path.join(BASE_DIR, "config", "default_layout.json")

# Initialize Engine (Manual Order Mode: auto_generate_orders=False)
engine = SimulationEngine(LAYOUT_PATH, auto_generate_orders=False)
engine.reset()

app = FastAPI(title="AI Restoran Backend & KDS Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections
active_connections: List[WebSocket] = []

class ConnectionManager:
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in active_connections:
            active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        dead_conns = []
        for connection in active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                dead_conns.append(connection)
        for dead in dead_conns:
            if dead in active_connections:
                active_connections.remove(dead)

manager = ConnectionManager()

# Pydantic Schemas for Android Requests
class OrderItemIn(BaseModel):
    dish_type: str
    quantity: int = 1
    note: str = ""

class OrderCreateIn(BaseModel):
    table_id: Optional[str] = None
    is_takeout: bool = False
    items: List[OrderItemIn]

def get_local_ip() -> str:
    """Detects local network Wi-Fi / Ethernet IPv4 address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def get_active_orders_data() -> List[dict]:
    active = []
    # 1. Orders in general queue (waiting to be cooked)
    for o in engine.order_queue:
        active.append({
            "order_id": o.order_id,
            "table_id": o.table_id,
            "dish_type": o.dish_type,
            "status": o.status,
            "current_stage": o.stages[o.current_stage_idx]["station_type"] if o.stages and o.current_stage_idx < len(o.stages) else None,
            "assigned_station": o.assigned_station_id,
            "assigned_chef": o.assigned_chef_id,
            "assigned_waiter": o.assigned_waiter_id,
            "predicted_time": o.predicted_time or o.theoretical_time,
            "is_takeout": o.is_takeout
        })
    # 2. Orders currently on stations
    for st in engine.grid.stations.values():
        for o in st.active_orders:
            if not any(x["order_id"] == o.order_id for x in active):
                active.append({
                    "order_id": o.order_id,
                    "table_id": o.table_id,
                    "dish_type": o.dish_type,
                    "status": o.status,
                    "current_stage": st.type,
                    "assigned_station": st.id,
                    "assigned_chef": o.assigned_chef_id,
                    "assigned_waiter": o.assigned_waiter_id,
                    "predicted_time": o.predicted_time or o.theoretical_time,
                    "is_takeout": o.is_takeout
                })
    return active

def get_kitchen_kds_state() -> dict:
    stations_data = []
    for st in engine.grid.stations.values():
        orders_in_st = []
        for o in st.active_orders:
            orders_in_st.append({
                "order_id": o.order_id,
                "table_id": o.table_id or "PAKET",
                "dish_type": o.dish_type,
                "status": o.status,
                "chef_id": o.assigned_chef_id or "Aşçı",
                "stage": st.type,
                "target_time": o.actual_target_time or o.theoretical_time,
                "created_at": o.timestamps.get("created_at", engine.tick)
            })
        stations_data.append({
            "id": st.id,
            "type": st.type,
            "capacity": st.capacity,
            "is_full": st.is_full,
            "is_broken": st.is_broken,
            "active_orders": orders_in_st
        })

    chefs_data = []
    for ch in engine.grid.chefs.values():
        chefs_data.append({
            "id": ch.id,
            "status": ch.status,
            "load": len(ch.active_orders),
            "capacity": ch.capacity,
            "active_orders": [o.order_id for o in ch.active_orders]
        })

    tables_data = []
    for t in engine.grid.tables.values():
        tables_data.append({
            "id": t.id,
            "capacity": t.capacity,
            "status": t.status,
            "customers": t.customers,
            "patience": round(t.patience, 1),
            "order_count": len(t.current_orders)
        })

    return {
        "tick": engine.tick,
        "stations": stations_data,
        "chefs": chefs_data,
        "tables": tables_data,
        "queue_orders": get_active_orders_data(),
        "completed_count": len(engine.completed_orders),
        "churned_count": engine.churned_customers
    }

# ----------------- REST ENDPOINTS -----------------

@app.get("/api/ping")
def ping():
    return {
        "status": "ok",
        "message": "AI Restoran Sunucusu Aktif ve Bağlı!",
        "server_ip": get_local_ip(),
        "tick": engine.tick
    }

@app.get("/api/tables")
def get_tables():
    res = []
    for t in engine.grid.tables.values():
        res.append({
            "id": t.id,
            "capacity": t.capacity,
            "status": t.status,
            "customers": t.customers,
            "patience": float(round(t.patience, 1))
        })
    return res

DISH_METADATA = {
    "Burger": {"name": "Gurme Burger", "price": 160.0, "icon": "🍔"},
    "Doner": {"name": "Yaprak Döner Dürüm", "price": 140.0, "icon": "🥙"},
    "Sucuk": {"name": "Izgara Sucuk Ekmek", "price": 130.0, "icon": "🌭"},
    "Kofte": {"name": "Izgara Köfte Tabağı", "price": 200.0, "icon": "🥩"},
    "Patates": {"name": "Patates Kızartması", "price": 60.0, "icon": "🍟"},
    "Sogan_Halkasi": {"name": "Soğan Halkası", "price": 60.0, "icon": "🧅"},
    "Fried_Basket": {"name": "Çıtır Karışık Sepet", "price": 110.0, "icon": "🧺"},
    "Toast": {"name": "Kaşarlı Karışık Tost", "price": 80.0, "icon": "🥪"},
    "Pizza": {"name": "Taş Fırın Pizza", "price": 180.0, "icon": "🍕"},
    "Steak": {"name": "Dana Antrikot", "price": 320.0, "icon": "🥩"},
    "Salad": {"name": "Akdeniz Salatası", "price": 90.0, "icon": "🥗"}
}

@app.get("/api/menu")
def get_menu():
    menu_recipes = engine.time_config.menu_recipes
    res = []
    for dish_type, info in menu_recipes.items():
        meta = DISH_METADATA.get(dish_type, {"name": dish_type, "price": 100.0, "icon": "🍽️"})
        res.append({
            "type": dish_type,
            "name": meta["name"],
            "category": info.get("category", "main_dish"),
            "stages": info.get("stages", []),
            "price": meta["price"],
            "icon": meta["icon"]
        })
    return res

@app.post("/api/orders")
async def create_order(req: OrderCreateIn):
    menu_map = {m["type"]: m for m in get_menu()}
    created_responses = []

    # If table order, update table status
    if not req.is_takeout and req.table_id in engine.grid.tables:
        table = engine.grid.tables[req.table_id]
        if table.status == "EMPTY":
            table.status = "WAITING_FOOD"
            table.customers = table.capacity
            table.patience = 30.0
            table.current_orders = []

    takeout_cfg = engine.time_config.takeout
    courier_min = takeout_cfg.get("courier_eta_min", 15.0)
    courier_max = takeout_cfg.get("courier_eta_max", 30.0)

    for item in req.items:
        for _ in range(item.quantity):
            dish_info = menu_map.get(item.dish_type, next(iter(menu_map.values())))
            total_time = sum(s["time"] for s in dish_info.get("stages", []))
            category = dish_info.get("category", "main_dish")
            order = Order(
                table_id=None if req.is_takeout else req.table_id,
                dish_type=dish_info["type"],
                category=category,
                theoretical_time=total_time,
                stages=dish_info.get("stages", []),
                is_takeout=req.is_takeout,
                courier_eta=engine.tick + (courier_min + courier_max) / 2.0 if req.is_takeout else None
            )
            order.timestamps["created_at"] = engine.tick
            
            if category == "beverage":
                order.status = "READY"
                order.timestamps["kitchen_start"] = engine.tick
                order.timestamps["kitchen_finish"] = engine.tick
                bev_counter = getattr(engine.grid, "beverage_counter", None) or engine.grid.delivery_counter
                order.assigned_counter_id = bev_counter.id
                bev_counter.ready_orders.append(order)
                if not req.is_takeout and req.table_id in engine.grid.tables:
                    engine.grid.tables[req.table_id].current_orders.append(order)
            else:
                # Predict cooking time via Model 1 ML
                features = {
                    "theoretical_time": total_time,
                    "dish_type": order.dish_type,
                    "station_type": order.stages[0]["station_type"] if order.stages else "PREP",
                    "station_load_at_start": 0,
                    "kitchen_load_at_start": len(engine.order_queue),
                    "chef_efficiency_at_start": 1.0,
                    "day_tick_at_start": engine.tick % 1440
                }
                order.predicted_time = engine.predictor.predict(features, len(engine.completed_orders))

                engine.order_queue.append(order)
                if not req.is_takeout and req.table_id in engine.grid.tables:
                    engine.grid.tables[req.table_id].current_orders.append(order)

                # Auto-assign if possible
                engine._simple_fifo_scheduler()

            created_responses.append({
                "order_id": order.order_id,
                "table_id": order.table_id,
                "dish_type": order.dish_type,
                "status": order.status,
                "current_stage": order.stages[order.current_stage_idx]["station_type"] if order.stages else None,
                "assigned_station": order.assigned_station_id,
                "assigned_chef": order.assigned_chef_id,
                "assigned_waiter": order.assigned_waiter_id,
                "predicted_time": order.predicted_time,
                "is_takeout": order.is_takeout
            })

    print(f"🔥 [SIPARIS GELDI] Hedef: {'Takeout' if req.is_takeout else 'Masa ' + str(req.table_id)} | {len(created_responses)} Adet")
    
    # Broadcast to KDS screen immediately
    await manager.broadcast(get_kitchen_kds_state())

    return {
        "status": "success",
        "message": f"{len(created_responses)} adet sipariş sisteme eklendi ve aşçılara yönlendirildi.",
        "created_orders": created_responses
    }

@app.get("/api/orders/active")
def get_active_orders():
    return get_active_orders_data()

@app.get("/api/system/status")
def get_system_status():
    return {
        "tick": engine.tick,
        "active_queue_count": len(engine.order_queue),
        "completed_count": len(engine.completed_orders),
        "churned_count": engine.churned_customers,
        "mode": "RL / AI Optimized"
    }

# ----------------- KDS (AŞÇI EKRANI) WEB ARAYÜZÜ -----------------

@app.get("/kds", response_class=HTMLResponse)
def get_kds_page():
    kds_html_path = os.path.join(BASE_DIR, "kds.html")
    if os.path.exists(kds_html_path):
        with open(kds_html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>KDS Sayfası Bulunamadı</h1>"

@app.get("/", response_class=HTMLResponse)
def root_redirect():
    return """
    <html>
        <head><meta http-equiv="refresh" content="0; url=/kds" /></head>
        <body><p><a href="/kds">Aşçı Mutfak Ekranı (KDS) için tıklayın</a></p></body>
    </html>
    """

# ----------------- WEBSOCKET LIVE FEED -----------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json(get_kitchen_kds_state())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# ----------------- BACKGROUND SIMULATION LOOP -----------------

async def simulation_tick_loop():
    """Advances the simulation engine tick periodically in real-time."""
    while True:
        try:
            # 1 tick every 1.5 seconds real time
            await asyncio.sleep(1.5)
            engine.step()
            if active_connections:
                await manager.broadcast(get_kitchen_kds_state())
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[LOOP ERROR] {e}")
            await asyncio.sleep(2.0)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulation_tick_loop())

def main():
    local_ip = get_local_ip()
    port = 8000

    print("\n" + "=" * 70)
    print("🍽️ AI RESTORAN SİPARİŞ & AŞÇI MUTFAK SİSTEMİ (KDS)")
    print("=" * 70)
    print(f"📱 TELEFONDAN BAĞLANMAK İÇİN GİRİLECEK IP (Wi-Fi):")
    print(f"   http://{local_ip}:{port}")
    print("-" * 70)
    print(f"🍳 AŞÇI MUTFAK EKRANI (KDS - Tarayıcı / 2. Ekran):")
    print(f"   http://localhost:{port}/kds")
    print(f"   http://{local_ip}:{port}/kds")
    print("=" * 70)
    print("💡 Telefon ve PC aynı Wi-Fi ağına bağlı olmalıdır.\n")

    # Open KDS in browser automatically
    def open_kds():
        webbrowser.open(f"http://localhost:{port}/kds")
    
    threading.Timer(1.0, open_kds).start()

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")

if __name__ == "__main__":
    main()
