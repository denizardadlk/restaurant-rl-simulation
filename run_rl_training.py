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

def get_available_layouts():
    layouts = []
    seen = set()
    if os.path.exists(LAYOUTS_DIR):
        for f in sorted(os.listdir(LAYOUTS_DIR)):
            if f.endswith(".json") and f not in seen:
                full_p = os.path.join(LAYOUTS_DIR, f)
                layouts.append({"filename": f, "path": full_p})
                seen.add(f)
    if os.path.exists(CONFIG_DIR):
        for f in sorted(os.listdir(CONFIG_DIR)):
            if f.endswith(".json") and f not in seen:
                full_p = os.path.join(CONFIG_DIR, f)
                layouts.append({"filename": f, "path": full_p})
                seen.add(f)
    return layouts

def interactive_prompt(existing_model: bool, cli_days=None, cli_layout=None, cli_mode=None):
    print("\n" + "=" * 75)
    print("🤖 PEKİŞTİRMELİ ÖĞRENME (RL) AJANI EĞİTİM YÖNETİCİSİ")
    print("=" * 75)
    
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
        print("\n[ADIM 1/2] Kaç gün simülasyon eğitimi yapmak istersiniz?")
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
        print("\n[ADIM 2/2] Hangi Restoran Düzeni (Layout) üzerinde eğitilsin?")
        for idx, l in enumerate(available, 1):
            print(f"  [{idx}] {l['filename']}")
        l_choice = input(f"Seçiminiz [1-{len(available)}] (Varsayılan: 1): ").strip()
        try:
            l_idx = int(l_choice) - 1
            selected_layout = available[l_idx] if 0 <= l_idx < len(available) else available[0]
        except ValueError:
            selected_layout = available[0]
            
    return mode, training_days, selected_layout

def main():
    parser = argparse.ArgumentParser(description="Pekiştirmeli Öğrenme (RL) Sipariş Çizelgeleyici Eğitimi")
    parser.add_argument("--days", type=int, default=None, help="Eğitilecek simülasyon günü sayısı (10, 50, 100)")
    parser.add_argument("--mode", type=str, choices=["continue", "overwrite", "new"], default=None, help="Eğitim modu")
    parser.add_argument("--layout", type=str, default=None, help="Kullanılacak layout dosyası")
    parser.add_argument("--difficulty", type=int, default=3, help="Zorluk seviyesi (1, 2, 3)")
    parser.add_argument("--num-envs", type=int, default=4, help="Paralel simülasyon ortamı (CPU çekirdeği) sayısı (varsayılan: 4)")
    args = parser.parse_args()
    
    os.makedirs(MODELS_DIR, exist_ok=True)
    existing_model = os.path.exists(DEFAULT_MODEL_PATH)
    
    mode, training_days, layout_entry = interactive_prompt(
        existing_model, cli_days=args.days, cli_layout=args.layout, cli_mode=args.mode
    )
        
    timesteps_per_day = 1440
    total_timesteps = training_days * timesteps_per_day
    layout_path = layout_entry["path"]
    
    print("\n" + "=" * 75)
    print("EĞİTİM YAPILANDIRMASI")
    print("=" * 75)
    print(f"Layout       : {layout_entry['filename']} ({layout_path})")
    print(f"Mod          : {mode.upper()}")
    print(f"Eğitim Süresi: {training_days} Gün ({total_timesteps:,} Timestep)")
    print(f"Paralel Çekirdek (Envs): {args.num_envs}")
    print(f"Hedef Model  : {DEFAULT_MODEL_PATH}")
    print("=" * 75)
    
    rl_agent = OrderSchedulerRLAgent(
        config_path=layout_path,
        num_envs=args.num_envs,
        difficulty_level=args.difficulty,
        model_path=DEFAULT_MODEL_PATH,
        freeze_ml=True
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
    print("\n" + "=" * 75)
    print("🎉 EĞİTİM TAMAMLANDI!")
    print("=" * 75)
    print(f"Geçen Süre       : {elapsed:.2f} saniye")
    print(f"Model Kayıt Yolu : {DEFAULT_MODEL_PATH}")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    main()
