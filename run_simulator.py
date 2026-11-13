import pygame
import sys
import os
import argparse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from simulation.engine import SimulationEngine
from simulation.gym_env import RestaurantGymEnv
from simulation.rl_agent import OrderSchedulerRLAgent
from simulation.scheduler_baselines import FIFOScheduler, SPTScheduler, LPTScheduler, MinPatienceScheduler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAYOUTS_DIR = os.path.join(BASE_DIR, "layouts")
MODELS_DIR = os.path.join(BASE_DIR, "models")
BEST_KITCHEN_MODEL = os.path.join(MODELS_DIR, "ppo_order_scheduler_best.zip")
DEFAULT_KITCHEN_MODEL = BEST_KITCHEN_MODEL if os.path.exists(BEST_KITCHEN_MODEL) else os.path.join(MODELS_DIR, "ppo_order_scheduler.zip")

BEST_WAITER_MODEL = os.path.join(MODELS_DIR, "ppo_waiter_policy_best.zip")
DEFAULT_WAITER_MODEL = BEST_WAITER_MODEL if os.path.exists(BEST_WAITER_MODEL) else os.path.join(MODELS_DIR, "ppo_waiter_policy.zip")

from simulation.waiter_gym_env import WaiterGymEnv
from simulation.rl_agent import WaiterRLAgent

# Colors
BG_COLOR = (30, 30, 40)
GRID_COLOR = (50, 50, 60)
TABLE_COLOR = (100, 150, 200)
STATION_COLOR = (200, 100, 100)
CHEF_COLOR = (255, 200, 50)
WAITER_COLOR = (150, 255, 150)
TEXT_COLOR = (255, 255, 255)
BAR_BG = (50, 50, 50)
BAR_FG_GREEN = (50, 200, 50)
BAR_FG_RED = (200, 50, 50)
BAR_FG_YELLOW = (200, 200, 50)

CELL_SIZE = 46
MARGIN = 15
SIDE_PANEL_WIDTH = 290

def get_patience_color(p):
    if p > 70: return BAR_FG_GREEN
    if p > 30: return BAR_FG_YELLOW
    return BAR_FG_RED

def resolve_layout_path(custom_name: str = None) -> str:
    if custom_name:
        p = os.path.join(LAYOUTS_DIR, custom_name)
        if os.path.exists(p): return p
        if os.path.exists(custom_name): return custom_name
        
    for name in ["custom_layout.json", "default_layout.json"]:
        p = os.path.join(LAYOUTS_DIR, name)
        if os.path.exists(p): return p
        p_cfg = os.path.join(BASE_DIR, "config", name)
        if os.path.exists(p_cfg): return p_cfg
    raise FileNotFoundError("Layout dosyası bulunamadı!")

def main():
    parser = argparse.ArgumentParser(description="Restoran Simülasyonu Canlı 2D Görselleştirme")
    parser.add_argument("--mode", type=str, choices=["rl", "fifo", "spt", "lpt", "minpatience"], default="rl", help="Kontrol algoritması modu")
    parser.add_argument("--layout", type=str, default=None, help="Kullanılacak layout dosyası")
    parser.add_argument("--model", "--kitchen-model", type=str, default=DEFAULT_KITCHEN_MODEL, help="Mutfak RL model dosyası")
    parser.add_argument("--waiter-model", type=str, default=DEFAULT_WAITER_MODEL, help="Garson RL model dosyası")
    args = parser.parse_args()

    pygame.init()
    layout_path = resolve_layout_path(args.layout)
    print(f"[SIMULATOR] Layout yükleniyor: {layout_path} (Mod: {args.mode.upper()})")

    engine = SimulationEngine(layout_path)
    engine.reset()
    
    # Setup scheduler based on mode
    rl_agent = None
    waiter_agent = None
    env = None
    waiter_env = None
    scheduler = None
    
    if args.mode == "rl":
        env = RestaurantGymEnv(layout_path)
        rl_agent = OrderSchedulerRLAgent(env, model_path=args.model)
        if rl_agent.load():
            print(f"[SIMULATOR] Mutfak RL Modeli yüklendi: {args.model}")
        else:
            print("[WARN] Kayıtlı Mutfak RL modeli bulunamadı! Varsayılan FIFO moduna geçiliyor.")
            args.mode = "fifo"
            scheduler = FIFOScheduler(engine)

        if os.path.exists(args.waiter_model):
            waiter_env = WaiterGymEnv(layout_path)
            waiter_agent = WaiterRLAgent(waiter_env, model_path=args.waiter_model)
            if waiter_agent.load():
                print(f"[SIMULATOR] Garson RL Modeli yüklendi: {args.waiter_model}")
            else:
                waiter_agent = None
    elif args.mode == "fifo":
        scheduler = FIFOScheduler(engine)
    elif args.mode == "spt":
        scheduler = SPTScheduler(engine)
    elif args.mode == "lpt":
        scheduler = LPTScheduler(engine)
    elif args.mode == "minpatience":
        scheduler = MinPatienceScheduler(engine)

    grid_w = engine.grid.width
    grid_h = engine.grid.height

    # Compact & standard window dimensions (fits comfortably on 768p and 1080p screens)
    screen_width = min(1180, max(840, grid_w * CELL_SIZE + SIDE_PANEL_WIDTH + MARGIN * 2))
    screen_height = min(680, max(560, grid_h * CELL_SIZE + 2 * MARGIN))

    screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
    pygame.display.set_caption(f"Restoran Simülasyonu - [{args.mode.upper()} Modu]")

    font_small = pygame.font.SysFont("Arial", 11)
    font = pygame.font.SysFont("Arial", 13)
    font_bold = pygame.font.SysFont("Arial", 13, bold=True)
    font_large = pygame.font.SysFont("Arial", 17, bold=True)
    clock = pygame.time.Clock()

    paused = False
    ticks_per_second = 5
    time_accumulator = 0.0
    running = True

    # Camera Pan / Scroll state
    camera_x = 0
    camera_y = 0
    is_dragging = False
    drag_start_pos = (0, 0)
    drag_start_camera = (0, 0)

    while running:
        dt = clock.tick(60) / 1000.0
        cur_w, cur_h = screen.get_size()
        viewport_w = cur_w - SIDE_PANEL_WIDTH

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button in (1, 2, 3) and event.pos[0] < viewport_w:
                    is_dragging = True
                    drag_start_pos = event.pos
                    drag_start_camera = (camera_x, camera_y)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button in (1, 2, 3):
                    is_dragging = False
            elif event.type == pygame.MOUSEMOTION:
                if is_dragging:
                    dx = event.pos[0] - drag_start_pos[0]
                    dy = event.pos[1] - drag_start_pos[1]
                    camera_x = drag_start_camera[0] + dx
                    camera_y = drag_start_camera[1] + dy
            elif event.type == pygame.MOUSEWHEEL:
                # Vertical scrolling with mouse wheel
                camera_y += event.y * 30
                if event.x != 0:
                    camera_x += event.x * 30
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key in [pygame.K_KP_PLUS, pygame.K_PLUS, pygame.K_EQUALS]:
                    ticks_per_second = min(100, ticks_per_second + 2)
                elif event.key in [pygame.K_KP_MINUS, pygame.K_MINUS]:
                    ticks_per_second = max(1, ticks_per_second - 2)
                elif event.key == pygame.K_r:
                    engine.reset()
                    if env: env.reset()
                elif event.key in [pygame.K_c, pygame.K_HOME]:
                    # Center camera
                    camera_x = 0
                    camera_y = 0

        # Keyboard Pan continuous support
        keys = pygame.key.get_pressed()
        pan_speed = 8
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            camera_x += pan_speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            camera_x -= pan_speed
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            camera_y += pan_speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            camera_y -= pan_speed

        if not paused:
            time_accumulator += dt
            tick_interval = 1.0 / ticks_per_second
            while time_accumulator >= tick_interval:
                # Step the selected scheduler
                if args.mode == "rl" and rl_agent and env:
                    if waiter_agent and waiter_env:
                        env.engine.enable_rl_waiter = True
                        waiter_env.engine = env.engine
                        for _ in range(len(env.engine.grid.waiters)):
                            w_masks = waiter_env.action_masks()
                            if not np.any(w_masks[1:] > 0):
                                break
                            w_obs = waiter_env._get_obs()
                            w_act = waiter_agent.predict_action(w_obs)
                            if int(w_act) == 0:
                                break
                            assigned = waiter_env._execute_waiter_action(int(w_act))
                            if not assigned:
                                break

                    tick_start = env.engine.tick
                    while env.engine.tick == tick_start and env.engine.tick < 1440:
                        action_masks = env.action_masks()
                        action, _ = rl_agent.model.predict(env._get_obs(), action_masks=action_masks, deterministic=True)
                        obs, reward, term, trunc, info = env.step(action)
                        if action == 0 or term or trunc:
                            break

                    engine = env.engine
                else:
                    if scheduler:
                        actions = scheduler.step()
                        for act in actions:
                            if act["type"] == "ASSIGN":
                                order = next((o for o in engine.order_queue if o.order_id == act["order_id"]), None)
                                if order:
                                    st = engine.grid.stations.get(act["station_id"])
                                    ch = engine.grid.chefs.get(act["chef_id"])
                                    if st and ch:
                                        engine.assign_order(order, st, ch)
                    engine.step(actions=[])
                    
                time_accumulator -= tick_interval

        # --- DRAWING ---
        screen.fill(BG_COLOR)

        # 1. VIEWPORT CLIPPING FOR SCROLLABLE RESTAURANT GRID
        viewport_rect = pygame.Rect(0, 0, viewport_w, cur_h)
        screen.set_clip(viewport_rect)

        grid_offset_x = MARGIN + camera_x
        grid_offset_y = MARGIN + camera_y

        # Draw Grid background & lines
        for y_idx in range(grid_h):
            for x_idx in range(grid_w):
                rect = pygame.Rect(grid_offset_x + x_idx * CELL_SIZE, grid_offset_y + y_idx * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(screen, GRID_COLOR, rect, 1)

        # 2. Tables
        TABLE_STATUS_COLORS = {
            "EMPTY": (70, 85, 105),
            "WAITING_ORDER": (210, 160, 40),
            "WAITING_FOOD": (60, 130, 210),
            "EATING": (50, 170, 90),
            "DIRTY": (140, 100, 75)
        }

        for table in engine.grid.tables.values():
            tw = getattr(table, 'w', 1)
            th = getattr(table, 'h', 1)
            rect = pygame.Rect(grid_offset_x + table.x * CELL_SIZE, grid_offset_y + table.y * CELL_SIZE, CELL_SIZE * tw, CELL_SIZE * th)
            
            t_status = getattr(table, 'status', 'EMPTY')
            t_color = TABLE_STATUS_COLORS.get(t_status, TABLE_COLOR)
            pygame.draw.rect(screen, t_color, rect.inflate(-3, -3), border_radius=6)

            txt = font_small.render(f"{table.id}", True, (255, 255, 255) if t_status != "WAITING_ORDER" else (0, 0, 0))
            screen.blit(txt, (rect.x + 3, rect.y + 2))

            if table.customers > 0 and t_status in ["WAITING_ORDER", "WAITING_FOOD"]:
                p_ratio = max(0.0, min(1.0, table.patience / 30.0))
                p_bar_w = int(p_ratio * (CELL_SIZE * tw - 8))
                p_color = get_patience_color(table.patience * (100.0 / 30.0))
                pygame.draw.rect(screen, BAR_BG, (rect.x + 4, rect.y + CELL_SIZE * th - 10, CELL_SIZE * tw - 8, 5))
                pygame.draw.rect(screen, p_color, (rect.x + 4, rect.y + CELL_SIZE * th - 10, p_bar_w, 5))

                cust_txt = font_small.render(f"{table.customers}K", True, (255, 255, 255) if t_status != "WAITING_ORDER" else (0, 0, 0))
                screen.blit(cust_txt, (rect.x + 3, rect.y + 14))
            elif t_status == "EATING":
                eat_txt = font_small.render(f"{int(table.eating_time_remaining)}s", True, (255, 255, 255))
                screen.blit(eat_txt, (rect.x + 3, rect.y + 14))
            elif t_status == "DIRTY":
                dirty_txt = font_small.render("Kirli", True, (255, 230, 200))
                screen.blit(dirty_txt, (rect.x + 3, rect.y + 14))

        # 3. Stations
        STATION_TYPE_COLORS = {
            "GRILL": (220, 90, 70),
            "DONER": (210, 120, 50),
            "FRYER": (230, 180, 50),
            "TOASTER": (190, 130, 90),
            "PREP": (100, 180, 100),
            "OVEN": (180, 70, 70),
            "STOVE": (170, 100, 140)
        }
        for station in engine.grid.stations.values():
            rect = pygame.Rect(grid_offset_x + station.x * CELL_SIZE, grid_offset_y + station.y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            st_color = (150, 50, 50) if station.is_broken else STATION_TYPE_COLORS.get(station.type, STATION_COLOR)
            pygame.draw.rect(screen, st_color, rect.inflate(-3, -3), border_radius=4)

            txt = font_small.render(station.id[:4], True, (255, 255, 255))
            screen.blit(txt, (rect.x + 3, rect.y + 2))

            load = len(station.active_orders)
            cap = station.capacity
            load_txt = font_small.render(f"{load}/{cap}", True, (255, 255, 255))
            screen.blit(load_txt, (rect.x + 3, rect.y + 15))

        # 4. Delivery Counters & Takeout Counter
        counters = list(engine.grid.delivery_counters.values()) if hasattr(engine.grid, 'delivery_counters') and engine.grid.delivery_counters else ([engine.grid.delivery_counter] if getattr(engine.grid, 'delivery_counter', None) else [])
        for idx, counter in enumerate(counters):
            rect = pygame.Rect(grid_offset_x + counter.x * CELL_SIZE, grid_offset_y + counter.y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(screen, (190, 140, 60), rect.inflate(-3, -3), border_radius=4)
            c_label = f"C{idx+1}"
            txt = font_small.render(c_label, True, (255, 255, 255))
            screen.blit(txt, (rect.x + 3, rect.y + 2))
            num_ready = len(counter.ready_orders)
            r_txt = font_small.render(f"🍽️{num_ready}/{counter.capacity}", True, (255, 240, 160))
            screen.blit(r_txt, (rect.x + 2, rect.y + 15))

        if getattr(engine.grid, "takeout_counter", None):
            tk_cnt = engine.grid.takeout_counter
            rect = pygame.Rect(grid_offset_x + tk_cnt.x * CELL_SIZE, grid_offset_y + tk_cnt.y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(screen, (120, 60, 190), rect.inflate(-3, -3), border_radius=4)
            txt = font_small.render("TK", True, (255, 255, 255))
            screen.blit(txt, (rect.x + 3, rect.y + 2))
            num_ready = len(tk_cnt.ready_orders)
            r_txt = font_small.render(f"🛵{num_ready}", True, (230, 200, 255))
            screen.blit(r_txt, (rect.x + 2, rect.y + 15))

        # 5. Chefs
        CHEF_STATUS_COLORS = {
            "IDLE": (255, 200, 50),
            "WALKING_TO_STATION": (255, 140, 40),
            "COOKING": (255, 80, 80),
            "DELIVERING_TO_COUNTER": (220, 120, 255)
        }
        for chef in engine.grid.chefs.values():
            rect = pygame.Rect(grid_offset_x + chef.x * CELL_SIZE, grid_offset_y + chef.y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            ch_color = CHEF_STATUS_COLORS.get(chef.status, CHEF_COLOR)
            pygame.draw.circle(screen, ch_color, rect.center, CELL_SIZE // 3)
            txt = font_small.render("C" + str(chef.id)[-1:], True, (0, 0, 0))
            screen.blit(txt, (rect.centerx - 6, rect.centery - 6))

            if len(chef.carrying_orders) > 0:
                b_rect = pygame.Rect(rect.centerx + 2, rect.top, 14, 10)
                pygame.draw.rect(screen, (255, 255, 255), b_rect, border_radius=2)
                c_txt = font_small.render(f"{len(chef.carrying_orders)}", True, (0, 0, 0))
                screen.blit(c_txt, (b_rect.x + 3, b_rect.y - 2))

        # 6. Waiters
        WAITER_STATUS_COLORS = {
            "IDLE": (120, 230, 120),
            "DELIVERING": (100, 220, 255),
            "TAKING_ORDER": (255, 220, 100),
            "CLEANING": (255, 150, 220)
        }
        for waiter in engine.grid.waiters.values():
            rect = pygame.Rect(grid_offset_x + waiter.x * CELL_SIZE, grid_offset_y + waiter.y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            w_color = WAITER_STATUS_COLORS.get(waiter.status, WAITER_COLOR)
            pygame.draw.polygon(screen, w_color, [(rect.centerx, rect.top+6), (rect.left+6, rect.bottom-6), (rect.right-6, rect.bottom-6)])
            
            w_label = "W" + str(waiter.id)[-1:]
            txt = font_small.render(w_label, True, (0, 0, 0))
            screen.blit(txt, (rect.centerx - 6, rect.centery - 2))

            # Draw Tray Badge if carrying food
            num_carried = len(waiter.carrying_orders)
            if num_carried > 0:
                badge_rect = pygame.Rect(rect.centerx + 2, rect.top, 18, 12)
                pygame.draw.rect(screen, (255, 200, 50), badge_rect, border_radius=3)
                tray_txt = font_small.render(f"{num_carried}", True, (0, 0, 0))
                screen.blit(tray_txt, (badge_rect.x + 4, badge_rect.y - 2))

        # Reset clip for side panel
        screen.set_clip(None)

        # 7. FIXED RIGHT SIDE PANEL
        panel_rect = pygame.Rect(viewport_w, 0, SIDE_PANEL_WIDTH, cur_h)
        pygame.draw.rect(screen, (22, 22, 30), panel_rect)
        pygame.draw.line(screen, (60, 60, 80), (viewport_w, 0), (viewport_w, cur_h), 2)

        panel_x = viewport_w + 15
        y = 15

        def draw_text(surf, text, f, color, px, py):
            img = f.render(text, True, color)
            surf.blit(img, (px, py))
            return py + f.get_linesize() + 3

        y = draw_text(screen, "Simülasyon Kontrolü", font_large, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, "------------------------------------", font_small, (100, 100, 120), panel_x, y)
        y = draw_text(screen, f"Aktif Mod: {args.mode.upper()}", font_bold, (100, 200, 255), panel_x, y)
        y = draw_text(screen, f"Tick: {engine.tick}", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, f"Durum: {'DURAKLATILDI' if paused else 'ÇALIŞIYOR'}", font_bold, (200, 50, 50) if paused else (50, 200, 50), panel_x, y)
        y = draw_text(screen, f"Hız: {ticks_per_second} tick/sn", font, TEXT_COLOR, panel_x, y)
        y += 4
        y = draw_text(screen, f"Kuyruktaki Sipariş: {len(engine.order_queue)}", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, f"Tamamlanan: {len(engine.completed_orders)}", font_bold, (100, 255, 100), panel_x, y)
        y = draw_text(screen, f"Churned (Kayıp): {engine.churned_customers}", font, (255, 100, 100), panel_x, y)
        d_inv = getattr(engine.kitchen_manager, "doner_inventory", 0)
        f_p_inv = getattr(engine.kitchen_manager, "fryer_fries_inventory", 0)
        f_o_inv = getattr(engine.kitchen_manager, "fryer_onion_inventory", 0)
        if d_inv > 0 or f_p_inv > 0 or f_o_inv > 0:
            y = draw_text(screen, f"Stok: 🥙Döner:{d_inv} 🍟Pat:{f_p_inv} 🧅Soğ:{f_o_inv}", font_small, (255, 215, 120), panel_x, y)
        if counter:
            y = draw_text(screen, f"Teslim Tezgahı: {len(counter.ready_orders)} hazır tabak", font_small, (255, 215, 0), panel_x, y)
        y += 4
        y = draw_text(screen, "Şef Durumları:", font_bold, (255, 200, 100), panel_x, y)
        for ch in engine.grid.chefs.values():
            y = draw_text(screen, f"• {ch.id}: {ch.status}", font_small, CHEF_STATUS_COLORS.get(ch.status, (220, 220, 220)), panel_x + 6, y)
        y += 4
        y = draw_text(screen, "Garson Durumları:", font_bold, (255, 230, 150), panel_x, y)
        for w in engine.grid.waiters.values():
            carried_info = f" ({len(w.carrying_orders)}/{w.tray_capacity} tabak)" if len(w.carrying_orders) > 0 else ""
            y = draw_text(screen, f"• {w.id}: {w.status}{carried_info}", font_small, WAITER_STATUS_COLORS.get(w.status, (200, 200, 200)), panel_x + 6, y)
        y += 4
        y = draw_text(screen, f"ML Eğitim Verisi: {engine.predictor.training_count}", font_small, (100, 200, 255), panel_x, y)

        y += 10
        y = draw_text(screen, "Kısayollar & Gezinme:", font_bold, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, "🖱️ Sürükle / Yön Tuşları: Harita Kaydır", font_small, (200, 200, 220), panel_x, y)
        y = draw_text(screen, "🖱️ Tekerlek: Dikey Kaydır", font_small, (200, 200, 220), panel_x, y)
        y = draw_text(screen, "C / HOME : Kamerayı Ortala", font_small, (200, 200, 220), panel_x, y)
        y = draw_text(screen, "SPACE    : Başlat / Duraklat", font_small, (200, 200, 220), panel_x, y)
        y = draw_text(screen, "+ / -    : Hızlandır / Yavaşlat", font_small, (200, 200, 220), panel_x, y)
        y = draw_text(screen, "R        : Sıfırla", font_small, (200, 200, 220), panel_x, y)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
