import os
import sys
import json
import time
import shutil
import argparse
import numpy as np

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
RESULTS_DIR = os.path.join(BASE_DIR, "results")

DEFAULT_MODEL_PATH = os.path.join(MODELS_DIR, "ppo_order_scheduler.zip")
BEST_MODEL_PATH = os.path.join(MODELS_DIR, "ppo_order_scheduler_best.zip")
HISTORY_JSON_PATH = os.path.join(RESULTS_DIR, "long_train_history.json")
SUMMARY_MD_PATH = os.path.join(RESULTS_DIR, "long_train_summary.md")

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

def evaluate_model_10_days(model_path: str, layout_path: str, difficulty: int = 3, eval_days: int = 10) -> dict:
    """Modeli 10 günlük bağımsız simülasyonda test eder ve metrikleri hesaplar."""
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.wrappers import ActionMasker
    
    def mask_fn(e):
        return e.action_masks()
        
    env = RestaurantGymEnv(config_path=layout_path, difficulty_level=difficulty, freeze_ml=True)
    wrapped_env = ActionMasker(env, mask_fn)
    model = MaskablePPO.load(model_path, env=wrapped_env)
    
    total_rewards = 0.0
    total_completed = 0
    total_churned = 0
    all_wait_times = []
    all_cold_times = []
    
    for day in range(1, eval_days + 1):
        obs, info = wrapped_env.reset(seed=2000 + day)
        done = False
        day_reward = 0.0
        
        while not done:
            action_masks = wrapped_env.action_masks()
            action, _ = model.predict(obs, action_masks=action_masks, deterministic=True)
            obs, reward, terminated, truncated, info = wrapped_env.step(action)
            day_reward += reward
            done = terminated or truncated
            
        total_rewards += day_reward
        completed = env.engine.completed_orders
        day_wait = [(o.timestamps["kitchen_start"] - o.timestamps["created_at"]) for o in completed if o.timestamps.get("kitchen_start") and o.timestamps.get("created_at")]
        day_cold = [max(0.0, o.timestamps["delivered_at"] - o.timestamps["kitchen_finish"] - 5.0) for o in completed if o.timestamps.get("delivered_at") and o.timestamps.get("kitchen_finish")]
        
        total_completed += len(completed)
        total_churned += env.engine.churned_customers
        all_wait_times.extend(day_wait)
        all_cold_times.extend(day_cold)
        
    mean_wait = float(np.mean(all_wait_times)) if all_wait_times else 0.0
    mean_cold = float(np.mean(all_cold_times)) if all_cold_times else 0.0
    mean_daily_completed = round(total_completed / max(1, eval_days), 2)
    mean_daily_churn = round(total_churned / max(1, eval_days), 2)
    mean_reward = round(total_rewards / max(1, eval_days), 2)
    
    # Kapsamlı değerlendirme skoru (Ödül temelli)
    eval_score = mean_reward
    
    return {
        "eval_days": eval_days,
        "total_completed": total_completed,
        "total_churned": total_churned,
        "mean_daily_completed": mean_daily_completed,
        "mean_daily_churn": mean_daily_churn,
        "mean_queue_wait_time": round(mean_wait, 2),
        "mean_food_cold_time": round(mean_cold, 2),
        "mean_reward_per_day": mean_reward,
        "eval_score": eval_score
    }

def update_summary_report(history: list, layout_filename: str, layout_path: str, difficulty: int, best_epoch: int, best_score: float):
    """results/long_train_summary.md dosyasını anlık günceller."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    lines = [
        "# 🚀 Uzun Süreli RL Eğitimi (Long Train) Canlı İlerleme Raporu\n",
        f"**Tarih:** {time.strftime('%Y-%m-%d %H:%M:%S')} | **Harita:** `{layout_filename}` | **Zorluk:** Seviye {difficulty}\n",
        f"**Döngü Yapısı:** 50 Gün Eğitim (72.000 Adım) $\\to$ 10 Gün Test (14.400 Adım) $\\to$ Early Stopping (Patience: 3)\n",
        f"**En İyi Model:** 🏆 **Döngü {best_epoch}** (Skor / Günlük Ödül: `{best_score:+.2f}`)\n",
        "---\n",
        "## 📊 İterasyon Geçmişi ve Doğrulama Tablosu\n",
        "| Döngü | Kümülatif Gün | Eğitim Süresi | Günlük Tamamlanan | Günlük Churn | Ort. Bekleme | Ort. Soğuma | Günlük Ödül (Skor) | Durum / Patience |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    
    for entry in history:
        ep = entry["epoch"]
        cum_days = entry["cumulative_train_days"]
        el_time = f"{entry['train_elapsed_sec']:.1f}sn"
        m_comp = f"{entry['eval_metrics']['mean_daily_completed']} sip/gün"
        m_churn = f"{entry['eval_metrics']['mean_daily_churn']} kişi/gün"
        m_wait = f"{entry['eval_metrics']['mean_queue_wait_time']} dk"
        m_cold = f"{entry['eval_metrics']['mean_food_cold_time']} dk"
        m_score = f"{entry['eval_metrics']['eval_score']:+.2f}"
        status = entry["status_label"]
        
        lines.append(f"| **Döngü {ep}** | {cum_days} Gün | {el_time} | {m_comp} | {m_churn} | {m_wait} | {m_cold} | `{m_score}` | {status} |")
        
    lines.extend([
        "\n---\n",
        "## 💡 Model Dosyaları\n",
        f"* **En İyi Model (Best):** `{BEST_MODEL_PATH}` *(Test performansında zirveye ulaşan ağırlıklar)*",
        f"* **Son Model (Latest):** `{DEFAULT_MODEL_PATH}` *(Eğitilen en güncel sürüm)*\n",
        "---\n*Bu rapor run_long_training.py tarafından her 50 günlük döngü sonrasında otomatik güncellenmektedir.*"
    ])
    
    with open(SUMMARY_MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    with open(HISTORY_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def prompt_user_choices(existing_model: bool, cli_layout=None, cli_mode=None, cli_envs=None, cli_max_epochs=None):
    print("\n" + "=" * 80)
    print("🔥 UZUN SÜRELİ RL EĞİTİM YÖNETİCİSİ (LONG TRAIN & EARLY STOPPING)")
    print("=" * 80)
    print("📌 Strateji: 50 Gün Train (72k Adım) -> 10 Gün Test -> En İyiyi Kaydet -> 3 Kötüleşmede Dur")
    print("-" * 80)
    
    # 1. Mod Seçimi
    if cli_mode is not None:
        mode = cli_mode
    elif existing_model:
        print(f"\n[!] Kayıtlı bir RL modeli bulundu.")
        print("  [1] Mevcut kayıtlı modeli yükle ve üstüne eğitmeye devam et (Fine-Tune)")
        print("  [2] Sıfırdan yeni bir model eğit (Kayıtlı modelin üzerine yaz)")
        choice = input("\nSeçiminiz [1/2] (Varsayılan: 1): ").strip()
        mode = "overwrite" if choice == "2" else "continue"
    else:
        print("\n[i] Henüz kayıtlı bir model yok. Sıfırdan eğitim başlatılacak.")
        mode = "new"
        
    # 2. Layout Seçimi
    available = get_available_layouts()
    if cli_layout is not None:
        matched = next((l for l in available if l["filename"] == cli_layout or l["path"] == cli_layout or os.path.basename(cli_layout) == l["filename"]), None)
        selected_layout = matched if matched else available[0]
    else:
        print("\n[ADIM 1/3] Hangi Restoran Düzeni (Layout) üzerinde eğitilsin?")
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
            
    # 3. Paralel Çekirdek (CPU Threads) Seçimi
    if cli_envs is not None:
        selected_envs = cli_envs
    else:
        print("\n[ADIM 2/3] Kaç Paralel CPU Çekirdeği (Environment) Kullanılsın?")
        print("  [1] 4 Çekirdek (Dengeli)")
        print("  [2] 8 Çekirdek (Hızlı - Önerilen) [Varsayılan]")
        print("  [3] 12 Çekirdek (Yüksek Performans)")
        print("  [4] 14 Çekirdek (Full Turbo - Maksimum Hız)")
        env_choice = input("Seçiminiz [1/2/3/4 veya özel çekirdek sayısı] (Varsayılan: 2): ").strip()
        if env_choice == "1":
            selected_envs = 4
        elif env_choice == "2" or env_choice == "":
            selected_envs = 8
        elif env_choice == "3":
            selected_envs = 12
        elif env_choice == "4":
            selected_envs = 14
        else:
            try:
                selected_envs = int(env_choice)
                if selected_envs <= 0: selected_envs = 8
            except ValueError:
                selected_envs = 8
                
    # 4. Maksimum Döngü (Epoch) Sayısı
    if cli_max_epochs is not None:
        max_epochs = cli_max_epochs
    else:
        print("\n[ADIM 3/3] Maksimum kaç döngü (50'şer günlük tur) çalışsın?")
        print("  [1] 10 Döngü (Maksimum 500 Gün / ~720.000 Timestep)")
        print("  [2] 20 Döngü (Maksimum 1.000 Gün / ~1.440.000 Timestep) [Varsayılan]")
        print("  [3] 50 Döngü (Maksimum 2.500 Gün - Derin Eğitim)")
        print("  [4] Sınırsız  (Erken durdurma tetiklenene kadar durma)")
        ep_choice = input("Seçiminiz [1/2/3/4 veya özel döngü sayısı] (Varsayılan: 2): ").strip()
        if ep_choice == "1":
            max_epochs = 10
        elif ep_choice == "2" or ep_choice == "":
            max_epochs = 20
        elif ep_choice == "3":
            max_epochs = 50
        elif ep_choice == "4":
            max_epochs = 999
        else:
            try:
                max_epochs = int(ep_choice)
                if max_epochs <= 0: max_epochs = 20
            except ValueError:
                max_epochs = 20
                
    return mode, selected_layout, selected_envs, max_epochs

def main():
    parser = argparse.ArgumentParser(description="Uzun Süreli RL Eğitimi ve Erken Durdurma Yöneticisi")
    parser.add_argument("--mode", type=str, choices=["continue", "overwrite", "new"], default=None, help="Eğitim modu")
    parser.add_argument("--layout", type=str, default=None, help="Kullanılacak layout dosyası")
    parser.add_argument("--difficulty", type=int, default=3, help="Zorluk seviyesi (1, 2, 3)")
    parser.add_argument("--num-envs", type=int, default=None, help="Paralel simülasyon ortamı (CPU çekirdeği) sayısı")
    parser.add_argument("--max-epochs", type=int, default=None, help="Maksimum 50 günlük döngü sayısı")
    parser.add_argument("--patience", type=int, default=3, help="Gelişme olmadan durdurulacak maksimum döngü sayısı (varsayılan: 3)")
    args = parser.parse_args()
    
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    existing_model = os.path.exists(DEFAULT_MODEL_PATH) or os.path.exists(BEST_MODEL_PATH)
    
    mode, layout_entry, num_envs, max_epochs = prompt_user_choices(
        existing_model, cli_layout=args.layout, cli_mode=args.mode, cli_envs=args.num_envs, cli_max_epochs=args.max_epochs
    )
    
    layout_path = layout_entry["path"]
    train_days_per_epoch = 50
    eval_days = 10
    timesteps_per_epoch = train_days_per_epoch * 1440 # 72,000 timesteps
    patience_limit = args.patience
    
    print("\n" + "=" * 80)
    print("🚀 LONG TRAIN YAPILANDIRMASI")
    print("=" * 80)
    print(f"Layout Dosyası        : {layout_entry['filename']} ({layout_path})")
    print(f"Başlangıç Modu        : {mode.upper()}")
    print(f"Döngü Başına Eğitim   : {train_days_per_epoch} Gün ({timesteps_per_epoch:,} Timestep)")
    print(f"Döngü Başına Doğrulama: {eval_days} Gün (14,400 Tick)")
    print(f"Paralel Çekirdek (CPU): {num_envs}")
    print(f"Maksimum Döngü        : {max_epochs} Tur (Maks. {max_epochs * train_days_per_epoch:,} Gün)")
    print(f"Early Stopping Limiti : {patience_limit} Başarısız Döngü")
    print(f"En İyi Model Kaydı    : {BEST_MODEL_PATH}")
    print(f"Canlı Rapor Dosyası   : {SUMMARY_MD_PATH}")
    print("=" * 80 + "\n")
    
    # Model Yöneticisini Başlat
    rl_agent = OrderSchedulerRLAgent(
        config_path=layout_path,
        num_envs=num_envs,
        difficulty_level=args.difficulty,
        model_path=DEFAULT_MODEL_PATH,
        freeze_ml=True
    )
    
    # Model yükleme
    if mode == "continue":
        source_load_path = BEST_MODEL_PATH if os.path.exists(BEST_MODEL_PATH) else DEFAULT_MODEL_PATH
        if os.path.exists(source_load_path):
            print(f"[YÜKLENİYOR] Mevcut model yükleniyor: {source_load_path}...")
            rl_agent.model_path = source_load_path
            if rl_agent.load():
                print("[OK] Model başarıyla yüklendi. Eğitime devam ediliyor...\n")
                rl_agent.model_path = DEFAULT_MODEL_PATH
            else:
                print("[WARN] Model yüklenemedi, sıfırdan başlanıyor...\n")
                
    history = []
    best_score = -float("inf")
    best_epoch = 0
    patience_counter = 0
    total_cumulative_days = 0
    
    start_total_time = time.time()
    
    for epoch in range(1, max_epochs + 1):
        print("\n" + "=" * 80)
        print(f"🔄 DÖNGÜ {epoch}/{max_epochs} | 50 Günlük Eğitim Başlatılıyor ({timesteps_per_epoch:,} Timestep)...")
        print("=" * 80)
        
        ep_start_time = time.time()
        
        # 1. TRAIN: 50 Gün (72.000 timestep)
        rl_agent.train(total_timesteps=timesteps_per_epoch)
        ep_elapsed = time.time() - ep_start_time
        total_cumulative_days += train_days_per_epoch
        
        print(f"\n[Döngü {epoch} Train Bitti] Süre: {ep_elapsed:.2f} saniye. 10 Günlük Doğrulama Testi Başlıyor...")
        
        # 2. EVAL: 10 Günlük Bağımsız Test
        eval_metrics = evaluate_model_10_days(
            model_path=DEFAULT_MODEL_PATH,
            layout_path=layout_path,
            difficulty=args.difficulty,
            eval_days=eval_days
        )
        
        current_score = eval_metrics["eval_score"]
        print("-" * 80)
        print(f"📊 10 GÜNLÜK DOĞRULAMA SONUCU (Döngü {epoch}):")
        print(f"  * Günlük Ort. Tamamlanan : {eval_metrics['mean_daily_completed']} sipariş/gün (Toplam: {eval_metrics['total_completed']})")
        print(f"  * Günlük Ort. Churn      : {eval_metrics['mean_daily_churn']} müşteri/gün (Toplam: {eval_metrics['total_churned']})")
        print(f"  * Ort. Kuyruk Bekleme    : {eval_metrics['mean_queue_wait_time']:.2f} dk")
        print(f"  * Ort. Yemek Soğuma      : {eval_metrics['mean_food_cold_time']:.2f} dk")
        print(f"  * Günlük Ortalama Ödül   : {eval_metrics['mean_reward_per_day']:+.2f}")
        print("-" * 80)
        
        # 3. Model Karşılaştırma & Early Stopping
        if current_score > best_score:
            score_diff = current_score - best_score if best_score != -float("inf") else 0.0
            best_score = current_score
            best_epoch = epoch
            patience_counter = 0
            
            # En iyi modeli kaydet
            shutil.copyfile(DEFAULT_MODEL_PATH, BEST_MODEL_PATH)
            status_label = f"🏆 YENİ EN İYİ (Skor: {best_score:+.2f})"
            print(f"🏆 [YENİ EN İYİ MODEL KAYDEDİLDİ!] Önceki Rekor Aşıldı ({score_diff:+.2f}). Model: {BEST_MODEL_PATH}")
        else:
            patience_counter += 1
            status_label = f"⚠️ Gelişme Yok (Patience: {patience_counter}/{patience_limit})"
            print(f"⚠️ [GELİŞME YOK] Mevcut Skor: {current_score:+.2f} <= En İyi Skor: {best_score:+.2f} (Döngü {best_epoch})")
            print(f"⏳ Early Stopping Sayacı: {patience_counter}/{patience_limit}")
            
        history_entry = {
            "epoch": epoch,
            "cumulative_train_days": total_cumulative_days,
            "train_elapsed_sec": round(ep_elapsed, 2),
            "eval_metrics": eval_metrics,
            "is_best": (epoch == best_epoch),
            "status_label": status_label
        }
        history.append(history_entry)
        
        # Raporları güncelle
        update_summary_report(history, layout_entry["filename"], layout_path, args.difficulty, best_epoch, best_score)
        print(f"📄 [CANLI RAPOR GÜNCELLENDİ] -> {SUMMARY_MD_PATH}")
        
        # Early Stopping Tetiklendi mi?
        if patience_counter >= patience_limit:
            print("\n" + "=" * 80)
            print(f"🛑 [EARLY STOPPING TETİKLENDİ] Üst üste {patience_limit} döngü boyunca gelişme sağlanamadı!")
            print(f"🏆 En İyi Model Korundu: Döngü {best_epoch} (Skor: {best_score:+.2f})")
            print("=" * 80)
            # En iyi modeli varsayılan model yoluna geri kopyala
            if os.path.exists(BEST_MODEL_PATH):
                shutil.copyfile(BEST_MODEL_PATH, DEFAULT_MODEL_PATH)
                print(f"[GERİ YÜKLEME] En iyi model ana yola aktarıldı: {DEFAULT_MODEL_PATH}")
            break
            
    total_elapsed = time.time() - start_total_time
    print("\n" + "=" * 80)
    print("🎉 UZUN SÜRELİ EĞİTİM (LONG TRAIN) TAMAMLANDI!")
    print("=" * 80)
    print(f"Toplam Geçen Süre     : {total_elapsed / 60:.2f} dakika ({total_elapsed:.1f} saniye)")
    print(f"Toplam Eğitilen Gün   : {total_cumulative_days} Simülasyon Günü")
    print(f"En İyi Döngü          : Döngü {best_epoch}")
    print(f"En İyi Doğrulama Skoru: {best_score:+.2f}")
    print(f"En İyi Model Dosyası  : {BEST_MODEL_PATH}")
    print(f"Detaylı Özet Raporu   : {SUMMARY_MD_PATH}")
    print("=" * 80 + "\n")
    
    try:
        input("Programı kapatmak için Enter tuşuna basın...")
    except Exception:
        pass

if __name__ == "__main__":
    main()
