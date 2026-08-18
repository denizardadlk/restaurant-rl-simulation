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
BEST_MODEL_PATH = os.path.join(MODELS_DIR, "ppo_order_scheduler_best.zip")
DEFAULT_MODEL_PATH = BEST_MODEL_PATH if os.path.exists(BEST_MODEL_PATH) else os.path.join(MODELS_DIR, "ppo_order_scheduler.zip")

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

CELL_SIZE = 60
MARGIN = 20

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
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL_PATH, help="RL model dosyası")
    args = parser.parse_args()

    pygame.init()
    layout_path = resolve_layout_path(args.layout)
    print(f"[SIMULATOR] Layout yükleniyor: {layout_path} (Mod: {args.mode.upper()})")

    engine = SimulationEngine(layout_path)
    engine.reset()
    
    # Setup scheduler based on mode
    rl_agent = None
    env = None
    scheduler = None
    
    if args.mode == "rl":
        env = RestaurantGymEnv(layout_path)
        rl_agent = OrderSchedulerRLAgent(env, model_path=args.model)
        if rl_agent.load():
            print(f"[SIMULATOR] RL Modeli yüklendi: {args.model}")
        else:
            print("[WARN] Kayıtlı RL modeli bulunamadı! Varsayılan FIFO moduna geçiliyor.")
            args.mode = "fifo"
            scheduler = FIFOScheduler(engine)
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

    screen_width = grid_w * CELL_SIZE + 320
    screen_height = max(grid_h * CELL_SIZE + 2 * MARGIN, 620)

    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption(f"Restoran Simülasyonu - [{args.mode.upper()} Modu]")

    font = pygame.font.SysFont("Arial", 14)
    font_large = pygame.font.SysFont("Arial", 20, bold=True)
    clock = pygame.time.Clock()

    paused = False
    ticks_per_second = 5
    time_accumulator = 0.0
    running = True

    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
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

        if not paused:
            time_accumulator += dt
            tick_interval = 1.0 / ticks_per_second
            while time_accumulator >= tick_interval:
                # Step the selected scheduler
                if args.mode == "rl" and rl_agent and env:
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
        grid_offset_x = MARGIN
        grid_offset_y = MARGIN

        # 1. Grid
        for y in range(grid_h):
            for x in range(grid_w):
                rect = pygame.Rect(grid_offset_x + x * CELL_SIZE, grid_offset_y + y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(screen, GRID_COLOR, rect, 1)

        # 2. Tables
        for table in engine.grid.tables.values():
            tw = getattr(table, 'w', 1)
            th = getattr(table, 'h', 1)
            rect = pygame.Rect(grid_offset_x + table.x * CELL_SIZE, grid_offset_y + table.y * CELL_SIZE, CELL_SIZE * tw, CELL_SIZE * th)
            pygame.draw.rect(screen, TABLE_COLOR, rect.inflate(-4, -4), border_radius=8)

            txt = font.render(table.id, True, (0, 0, 0))
            screen.blit(txt, (rect.x + 4, rect.y + 4))

            if table.customers > 0:
                p_bar_w = int((table.patience / 100.0) * (CELL_SIZE * tw - 10))
                p_color = get_patience_color(table.patience)
                pygame.draw.rect(screen, BAR_BG, (rect.x + 5, rect.y + CELL_SIZE * th - 15, CELL_SIZE * tw - 10, 8))
                pygame.draw.rect(screen, p_color, (rect.x + 5, rect.y + CELL_SIZE * th - 15, p_bar_w, 8))

                cust_txt = font.render(f"{table.customers} Mst", True, (0, 0, 0))
                screen.blit(cust_txt, (rect.x + 4, rect.y + 20))

        # 3. Stations
        for station in engine.grid.stations.values():
            rect = pygame.Rect(grid_offset_x + station.x * CELL_SIZE, grid_offset_y + station.y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            st_color = (150, 50, 50) if station.is_broken else STATION_COLOR
            pygame.draw.rect(screen, st_color, rect.inflate(-4, -4), border_radius=4)

            txt = font.render(station.id[:4], True, (255, 255, 255))
            screen.blit(txt, (rect.x + 4, rect.y + 4))

            load = len(station.active_orders)
            cap = station.capacity
            load_txt = font.render(f"{load}/{cap}", True, (255, 255, 255))
            screen.blit(load_txt, (rect.x + 4, rect.y + 20))

        # 4. Chefs
        for chef in engine.grid.chefs.values():
            rect = pygame.Rect(grid_offset_x + chef.x * CELL_SIZE, grid_offset_y + chef.y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.circle(screen, CHEF_COLOR, rect.center, CELL_SIZE // 3)
            txt = font.render("C" + chef.id[-1:], True, (0, 0, 0))
            screen.blit(txt, (rect.centerx - 8, rect.centery - 8))

        # 5. Waiters
        for waiter in engine.grid.waiters.values():
            rect = pygame.Rect(grid_offset_x + waiter.x * CELL_SIZE, grid_offset_y + waiter.y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.polygon(screen, WAITER_COLOR, [(rect.centerx, rect.top+10), (rect.left+10, rect.bottom-10), (rect.right-10, rect.bottom-10)])
            txt = font.render("W" + waiter.id[-1:], True, (0, 0, 0))
            screen.blit(txt, (rect.centerx - 8, rect.centery - 2))

        # 6. Side Panel
        panel_x = grid_offset_x + grid_w * CELL_SIZE + 20
        y = MARGIN

        def draw_text(surf, text, f, color, px, py):
            img = f.render(text, True, color)
            surf.blit(img, (px, py))
            return py + f.get_linesize() + 5

        y = draw_text(screen, "Simülasyon Kontrolü", font_large, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, "----------------------", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, f"Aktif Mod: {args.mode.upper()}", font, (100, 200, 255), panel_x, y)
        y = draw_text(screen, f"Tick: {engine.tick}", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, f"Durum: {'DURAKLATILDI' if paused else 'ÇALIŞIYOR'}", font, (200, 50, 50) if paused else (50, 200, 50), panel_x, y)
        y = draw_text(screen, f"Hız: {ticks_per_second} tick/sn", font, TEXT_COLOR, panel_x, y)
        y += 10
        y = draw_text(screen, f"Kuyruktaki Sipariş: {len(engine.order_queue)}", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, f"Tamamlanan: {len(engine.completed_orders)}", font, (100, 255, 100), panel_x, y)
        y = draw_text(screen, f"Churned (Kayıp): {engine.churned_customers}", font, (255, 100, 100), panel_x, y)
        y += 10
        y = draw_text(screen, f"ML Eğitim Verisi: {engine.predictor.training_count}", font, (100, 200, 255), panel_x, y)

        y += 20
        y = draw_text(screen, "Kısayollar:", font_large, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, "SPACE : Başlat / Duraklat", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, "+ / = : Hızlandır", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, "-     : Yavaşlat", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, "R     : Sıfırla", font, TEXT_COLOR, panel_x, y)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
