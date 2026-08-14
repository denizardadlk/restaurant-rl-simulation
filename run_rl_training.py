import os
import sys
import argparse
import time
import json

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from simulation.gym_env import RestaurantGymEnv
from simulation.rl_agent import OrderSchedulerRLAgent

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAYOUTS_DIR = os.path.join(BASE_DIR, "layouts")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
MODELS_DIR = os.path.join(BASE_DIR, "models")
DEFAULT_MODEL_PATH = os.path.join(MODELS_DIR, "ppo_order_scheduler.zip")

def extract_layout_info(path: str) -> dict:
    """Layout JSON dosyasından masa, istasyon, garson, aşçı detaylarını okur."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        grid_w = data.get("grid_size", {}).get("width", 0)
        grid_h = data.get("grid_size", {}).get("height", 0)
        tables = data.get("tables", [])
        stations = data.get("stations", [])
        waiters = data.get("waiters", [])
        chefs = data.get("chefs", [])
        
        total_capacity = sum(t.get("capacity", 4) for t in tables)
        station_types = list(set(s.get("type", "UNKNOWN") for s in stations))
        
        return {
            "grid_size": f"{grid_w}x{grid_h}",
            "table_count": len(tables),
            "total_capacity": total_capacity,
            "station_count": len(stations),
            "station_types": station_types,
            "waiter_count": len(waiters),
            "chef_count": len(chefs)
        }
    except Exception:
        return {
            "grid_size": "?", "table_count": 0, "total_capacity": 0,
            "station_count": 0, "station_types": [], "waiter_count": 0, "chef_count": 0
        }

def get_available_layouts():
    layouts = []
    seen = set()
    if os.path.exists(LAYOUTS_DIR):
        for f in sorted(os.listdir(LAYOUTS_DIR)):
            if f.endswith(".json") and f not in seen:
                full_p = os.path.join(LAYOUTS_DIR, f)
                layouts.append({"filename": f, "path": full_p, "info": extract_layout_info(full_p)})
                seen.add(f)
    if os.path.exists(CONFIG_DIR):
        for f in sorted(os.listdir(CONFIG_DIR)):
            if f.endswith(".json") and f not in seen:
                full_p = os.path.join(CONFIG_DIR, f)
                layouts.append({"filename": f, "path": full_p, "info": extract_layout_info(full_p)})
                seen.add(f)
    return layouts

def interactive_prompt(existing_model: bool, cli_days=None, cli_layout=None, cli_mode=None, cli_envs=None, cli_debug=None):
    print("\n" + "=" * 80)
    print("🤖 PEKİŞTİRMELİ ÖĞRENME (RL - MaskablePPO) AJANI EĞİTİM YÖNETİCİSİ")
    print("=" * 80)
    
    # 1. Mod Seçimi
    if cli_mode is not None:
        mode = cli_mode
    elif existing_model:
        print(f"\n[!] Kayıtlı bir RL modeli bulundu: {DEFAULT_MODEL_PATH}")
        print("  [1] Mevcut kayıtlı modeli yükle ve eğitime devam et (Fine-Tune)")
        print("  [2] Sıfırdan yeni bir model eğit (Kayıtlı modelin üzerine yaz)")
        choice = input("\nSeçiminiz [1/2] (Varsayılan: 1): ").strip()
        mode = "overwrite" if choice == "2" else "continue"
    else:
        print("\n[i] Henüz kayıtlı bir model yok. Sıfırdan eğitim başlatılacak.")
        mode = "new"
        
    # 2. Gün Seçimi
    if cli_days is not None:
        training_days = cli_days
    else:
        print("\n[ADIM 1/4] Kaç gün simülasyon eğitimi yapmak istersiniz?")
        print("  [1] 10 Gün  (14.400 timestep - Hızlı Prototipleme)")
        print("  [2] 50 Gün  (72.000 timestep - Standart Eğitim)")
        print("  [3] 100 Gün (144.000 timestep - Derin Yakınsama) [Varsayılan]")
        days_input = input("Seçiminiz [1/2/3 veya özel gün sayısı] (Varsayılan: 3): ").strip()
        if days_input == "1":
            training_days = 10
        elif days_input == "2":
            training_days = 50
        elif days_input == "3" or days_input == "":
            training_days = 100
        else:
            try:
                training_days = int(days_input)
                if training_days <= 0: training_days = 100
            except ValueError:
                training_days = 100
                
    # 3. Layout Seçimi
    available = get_available_layouts()
    if cli_layout is not None:
        matched = next((l for l in available if l["filename"] == cli_layout or l["path"] == cli_layout or os.path.basename(cli_layout) == l["filename"]), None)
        selected_layout = matched if matched else available[0]
    else:
        print("\n[ADIM 2/4] Hangi Restoran Düzeni (Layout) üzerinde eğitilsin?")
        for idx, l in enumerate(available, 1):
            inf = l.get("info", {})
            st_types = ", ".join(inf.get("station_types", [])) if inf.get("station_types") else "Yok"
            print(f"  [{idx}] {l['filename']:<22} | Boyut: {inf.get('grid_size', '?'):<5} | Masalar: {inf.get('table_count', 0):2d} ({inf.get('total_capacity', 0):2d} kişi) | İstasyon: {inf.get('station_count', 0):2d} ({st_types}) | Garson: {inf.get('waiter_count', 0)} | Aşçı: {inf.get('chef_count', 0)}")
        l_choice = input(f"\nSeçiminiz [1-{len(available)}] (Varsayılan: 1): ").strip()
        try:
            l_idx = int(l_choice) - 1
            selected_layout = available[l_idx] if 0 <= l_idx < len(available) else available[0]
        except ValueError:
            selected_layout = available[0]
            
    # 4. Paralel Çekirdek (CPU Threads) Seçimi
    if cli_envs is not None:
        selected_envs = cli_envs
    else:
        print("\n[ADIM 3/4] Kaç Paralel CPU Çekirdeği (Environment) Kullanılsın?")
        print("  [1] 1 Çekirdek (Tek İşlemci)")
        print("  [2] 2 Çekirdek (Hafif Paralel)")
        print("  [3] 4 Çekirdek (Önerilen Hızlı Mod - 4x Hız) [Varsayılan]")
        print("  [4] 8 Çekirdek (Maksimum Performans - 8x Hız)")
        env_choice = input("Seçiminiz [1/2/3/4 veya özel çekirdek sayısı] (Varsayılan: 3): ").strip()
        if env_choice == "1":
            selected_envs = 1
        elif env_choice == "2":
            selected_envs = 2
        elif env_choice == "3" or env_choice == "":
            selected_envs = 4
        elif env_choice == "4":
            selected_envs = 8
        else:
            try:
                selected_envs = int(env_choice)
                if selected_envs <= 0: selected_envs = 4
            except ValueError:
                selected_envs = 4
                
    # 5. Detaylı Hata Ayıklama (Debug) Modu Seçimi
    if cli_debug is not None:
        selected_debug = cli_debug
    else:
        print("\n[ADIM 4/4] Detaylı Hata Ayıklama (Debug) Modu Aktif Edilsin mi?")
        print("  [1] Hayır - Standart Hızlı Eğitim [Varsayılan]")
        print("  [2] Evet  - Detaylı İnceleme (results/training_debug.md kaydı oluşturur)")
        dbg_choice = input("Seçiminiz [1/2] (Varsayılan: 1): ").strip()
        selected_debug = (dbg_choice == "2")
            
    return mode, training_days, selected_layout, selected_envs, selected_debug

def main():
    parser = argparse.ArgumentParser(description="Pekiştirmeli Öğrenme (RL) Sipariş Çizelgeleyici Eğitimi")
    parser.add_argument("--days", type=int, default=None, help="Eğitilecek simülasyon günü sayısı (10, 50, 100)")
    parser.add_argument("--mode", type=str, choices=["continue", "overwrite", "new"], default=None, help="Eğitim modu")
    parser.add_argument("--layout", type=str, default=None, help="Kullanılacak layout dosyası")
    parser.add_argument("--difficulty", type=int, default=3, help="Zorluk seviyesi (1, 2, 3)")
    parser.add_argument("--num-envs", type=int, default=None, help="Paralel simülasyon ortamı (CPU çekirdeği) sayısı (varsayılan: 4)")
    parser.add_argument("--debug", action="store_true", default=None, help="Detaylı hata ayıklama modunu aktif eder ve results/training_debug.md oluşturur")
    args = parser.parse_args()
    
    os.makedirs(MODELS_DIR, exist_ok=True)
    existing_model = os.path.exists(DEFAULT_MODEL_PATH)
    
    mode, training_days, layout_entry, num_envs, debug_mode = interactive_prompt(
        existing_model, cli_days=args.days, cli_layout=args.layout, cli_mode=args.mode, cli_envs=args.num_envs, cli_debug=args.debug
    )
        
    timesteps_per_day = 1440
    total_timesteps = training_days * timesteps_per_day
    layout_path = layout_entry["path"]
    
    print("\n" + "=" * 80)
    print("EĞİTİM YAPILANDIRMASI")
    print("=" * 80)
    print(f"Layout       : {layout_entry['filename']} ({layout_path})")
    print(f"Mod          : {mode.upper()}")
    print(f"Eğitim Süresi: {training_days} Gün ({total_timesteps:,} Timestep)")
    print(f"Paralel Çekirdek (Envs): {1 if debug_mode else num_envs}")
    print(f"Debug Modu   : {'AKTİF (training_debug.md üretilecek)' if debug_mode else 'DEVRE DIŞI'}")
    print(f"Hedef Model  : {DEFAULT_MODEL_PATH}")
    print("=" * 80)
    
    rl_agent = OrderSchedulerRLAgent(
        config_path=layout_path,
        num_envs=num_envs,
        difficulty_level=args.difficulty,
        model_path=DEFAULT_MODEL_PATH,
        freeze_ml=True,
        debug_mode=debug_mode
    )
    
    if mode == "continue" and existing_model:
        print(f"\n[YÜKLENİYOR] Mevcut model yükleniyor: {DEFAULT_MODEL_PATH}...")
        if rl_agent.load():
            print("[OK] Model başarıyla yüklendi. Eğitime devam ediliyor...")
        else:
            print("[WARN] Model bu layout boyutuyla uyumlu değil, sıfırdan başlatılıyor...")
            
    print(f"\n[EĞİTİM BAŞLADI] {total_timesteps:,} adım boyunca MaskablePPO eğitimi yürütülüyor...")
    start_time = time.time()
    
    rl_agent.train(total_timesteps=total_timesteps)
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 80)
    print("🎉 EĞİTİM TAMAMLANDI!")
    print("=" * 80)
    print(f"Geçen Süre       : {elapsed:.2f} saniye")
    print(f"Model Kayıt Yolu : {DEFAULT_MODEL_PATH}")
    if debug_mode:
        print(f"Debug Raporu     : results/training_debug.md")
    print("=" * 80 + "\n")
    
    # Çift tıklamayla açıldığında pencere hemen kapanmasın
    try:
        input("Programı kapatmak için Enter tuşuna basın...")
    except Exception:
        pass

if __name__ == "__main__":
    main()
