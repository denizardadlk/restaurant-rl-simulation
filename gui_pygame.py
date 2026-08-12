import pygame
import sys
import os
from simulation.engine import SimulationEngine

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

def main():
    pygame.init()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    elif os.path.exists(os.path.join(base_dir, "config", "custom_layout.json")):
        config_path = os.path.join(base_dir, "config", "custom_layout.json")
    else:
        config_path = os.path.join(base_dir, "config", "default_layout.json")

    print(f"[GUI] Layout yükleniyor: {config_path}")
    engine = SimulationEngine(config_path)
    engine.reset()
    
    grid_w = engine.grid.width
    grid_h = engine.grid.height
    
    screen_width = grid_w * CELL_SIZE + 300  # Extra space for side panel
    screen_height = max(grid_h * CELL_SIZE + 2 * MARGIN, 600)
    
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Restoran Simülasyonu - Pygame GUI")
    
    font = pygame.font.SysFont("Arial", 14)
    font_large = pygame.font.SysFont("Arial", 20, bold=True)
    
    clock = pygame.time.Clock()
    
    paused = False
    ticks_per_second = 5  # Speed of simulation
    time_accumulator = 0.0
    
    running = True
    while running:
        dt = clock.tick(60) / 1000.0  # seconds since last frame
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_KP_PLUS or event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    ticks_per_second = min(100, ticks_per_second + 1)
                elif event.key == pygame.K_KP_MINUS or event.key == pygame.K_MINUS:
                    ticks_per_second = max(1, ticks_per_second - 1)
                elif event.key == pygame.K_r:
                    engine.reset()
                    
        if not paused:
            time_accumulator += dt
            tick_interval = 1.0 / ticks_per_second
            while time_accumulator >= tick_interval:
                engine.step()
                time_accumulator -= tick_interval
                
        # --- DRAWING ---
        screen.fill(BG_COLOR)
        
        # 1. Draw Grid
        grid_offset_x = MARGIN
        grid_offset_y = MARGIN
        
        for y in range(grid_h):
            for x in range(grid_w):
                rect = pygame.Rect(grid_offset_x + x * CELL_SIZE, grid_offset_y + y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(screen, GRID_COLOR, rect, 1)
                
        # 2. Draw Tables
        for table in engine.grid.tables.values():
            tw = getattr(table, 'w', 1)
            th = getattr(table, 'h', 1)
            rect = pygame.Rect(grid_offset_x + table.x * CELL_SIZE, grid_offset_y + table.y * CELL_SIZE, CELL_SIZE * tw, CELL_SIZE * th)
            pygame.draw.rect(screen, TABLE_COLOR, rect.inflate(-4, -4), border_radius=8)
            
            # Text T[id]
            txt = font.render(table.id, True, (0, 0, 0))
            screen.blit(txt, (rect.x + 4, rect.y + 4))
            
            # Patience Bar
            if table.customers > 0:
                p_bar_w = int((table.patience / 100.0) * (CELL_SIZE * tw - 10))
                p_color = get_patience_color(table.patience)
                pygame.draw.rect(screen, BAR_BG, (rect.x + 5, rect.y + CELL_SIZE * th - 15, CELL_SIZE * tw - 10, 8))
                pygame.draw.rect(screen, p_color, (rect.x + 5, rect.y + CELL_SIZE * th - 15, p_bar_w, 8))
                
                # Table info
                if table.customers > 0:
                    cust_txt = font.render(f"{table.customers} Mst", True, (0, 0, 0))
                    screen.blit(cust_txt, (rect.x + 4, rect.y + 20))
        # 3. Draw Stations
        for station in engine.grid.stations.values():
            rect = pygame.Rect(grid_offset_x + station.x * CELL_SIZE, grid_offset_y + station.y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(screen, STATION_COLOR, rect.inflate(-4, -4), border_radius=4)
            
            txt = font.render(station.id[:4], True, (255, 255, 255))
            screen.blit(txt, (rect.x + 4, rect.y + 4))
            
            # Load info
            load = len(station.active_orders)
            cap = station.capacity
            load_txt = font.render(f"{load}/{cap}", True, (255, 255, 255))
            screen.blit(load_txt, (rect.x + 4, rect.y + 20))
            
            # Progress bar for oldest order
            if load > 0:
                oldest_order = station.active_orders[0]
                if oldest_order.actual_target_time and "kitchen_start" in oldest_order.timestamps:
                    cooking_time = engine.tick - oldest_order.timestamps["kitchen_start"]
                    progress = min(1.0, cooking_time / oldest_order.actual_target_time)
                    bar_w = int(progress * (CELL_SIZE - 10))
                    pygame.draw.rect(screen, BAR_BG, (rect.x + 5, rect.y + CELL_SIZE - 15, CELL_SIZE - 10, 8))
                    pygame.draw.rect(screen, (50, 200, 255), (rect.x + 5, rect.y + CELL_SIZE - 15, bar_w, 8))
                    
        # 4. Draw Chefs
        for chef in engine.grid.chefs.values():
            rect = pygame.Rect(grid_offset_x + chef.x * CELL_SIZE, grid_offset_y + chef.y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.circle(screen, CHEF_COLOR, rect.center, CELL_SIZE // 3)
            
            txt = font.render("C" + chef.id[-1:], True, (0, 0, 0))
            screen.blit(txt, (rect.centerx - 8, rect.centery - 8))
            
            # Status
            stat_txt = font.render(chef.status[:4], True, (255,255,255))
            screen.blit(stat_txt, (rect.x, rect.y - 15))
            
        # 5. Draw Waiters
        for waiter in engine.grid.waiters.values():
            rect = pygame.Rect(grid_offset_x + waiter.x * CELL_SIZE, grid_offset_y + waiter.y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.polygon(screen, WAITER_COLOR, [(rect.centerx, rect.top+10), (rect.left+10, rect.bottom-10), (rect.right-10, rect.bottom-10)])
            
            txt = font.render("W" + waiter.id[-1:], True, (0, 0, 0))
            screen.blit(txt, (rect.centerx - 8, rect.centery - 2))
            
            stat_txt = font.render(waiter.status[:4], True, (255,255,255))
            screen.blit(stat_txt, (rect.x, rect.y - 15))
            
        # 6. Draw Side Panel
        panel_x = grid_offset_x + grid_w * CELL_SIZE + 20
        y = MARGIN
        
        def draw_text(surf, text, font, color, x, y):
            img = font.render(text, True, color)
            surf.blit(img, (x, y))
            return y + font.get_linesize() + 5
            
        y = draw_text(screen, "Simülasyon Paneli", font_large, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, "----------------------", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, f"Tick: {engine.tick}", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, f"Durum: {'DURAKLATILDI' if paused else 'ÇALIŞIYOR'}", font, (200, 50, 50) if paused else (50, 200, 50), panel_x, y)
        y = draw_text(screen, f"Hız: {ticks_per_second} tick/sn", font, TEXT_COLOR, panel_x, y)
        y += 10
        y = draw_text(screen, f"Kuyruktaki Siparişler: {len(engine.order_queue)}", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, f"Tamamlanan Siparişler: {len(engine.completed_orders)}", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, f"Kaybedilen Müşteriler (Churn): {engine.churned_customers}", font, (255, 100, 100), panel_x, y)
        y += 10
        y = draw_text(screen, f"ML Eğitim Verisi: {engine.predictor.training_count}", font, (100, 200, 255), panel_x, y)
        
        y += 20
        y = draw_text(screen, "Kontroller:", font_large, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, "SPACE : Başlat / Duraklat", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, "+ / = : Hızlandır", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, "-     : Yavaşlat", font, TEXT_COLOR, panel_x, y)
        y = draw_text(screen, "R     : Sıfırla", font, TEXT_COLOR, panel_x, y)
        
        pygame.display.flip()
        
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
