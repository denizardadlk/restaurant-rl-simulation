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
from simulation.waiter_gym_env import WaiterGymEnv
from simulation.rl_agent import OrderSchedulerRLAgent, WaiterRLAgent
from simulation.engine import SimulationEngine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAYOUTS_DIR = os.path.join(BASE_DIR, "layouts")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
MODELS_DIR = os.path.join(BASE_DIR, "models")
RESULTS_DIR = os.path.join(BASE_DIR, "results")

# Kitchen / Chef Models
DEFAULT_KITCHEN_MODEL = os.path.join(MODELS_DIR, "ppo_order_scheduler.zip")
BEST_KITCHEN_MODEL = os.path.join(MODELS_DIR, "ppo_order_scheduler_best.zip")

# Waiter Models
DEFAULT_WAITER_MODEL = os.path.join(MODELS_DIR, "ppo_waiter_policy.zip")
BEST_WAITER_MODEL = os.path.join(MODELS_DIR, "ppo_waiter_policy_best.zip")

HISTORY_JSON_PATH = os.path.join(RESULTS_DIR, "long_train_history.json")
SUMMARY_MD_PATH = os.path.join(RESULTS_DIR, "long_train_summary.md")

def extract_layout_info(path: str) -> dict:
    """Layout JSON dosyasından masa, istasyon, garson, aşçı ve tezgah detaylarını okur."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "grid_size" not in data or "tables" not in data:
            return None
        grid_w = data.get("grid_size", {}).get("width", 0)
        grid_h = data.get("grid_size", {}).get("height", 0)
        tables = data.get("tables", [])
        stations = data.get("stations", [])
        waiters = data.get("waiters", [])
        chefs = data.get("chefs", [])
        delivery_counters = data.get("delivery_counters", [])
        if not delivery_counters and "delivery_counter" in data:
            delivery_counters = [data["delivery_counter"]]
        
        total_capacity = sum(t.get("capacity", 4) for t in tables)
        station_types = list(set(s.get("type", "UNKNOWN") for s in stations))
        
        return {
            "grid_size": f"{grid_w}x{grid_h}",
            "table_count": len(tables),
            "total_capacity": total_capacity,
            "station_count": len(stations),
            "station_types": station_types,
            "waiter_count": len(waiters),
            "chef_count": len(chefs),
            "counter_count": len(delivery_counters)
        }
    except Exception:
        return None

def get_available_layouts():
    layouts = []
    seen = set()
    for d in [LAYOUTS_DIR, CONFIG_DIR]:
        if os.path.exists(d):
            for f in sorted(os.listdir(d)):
                if f.endswith(".json") and f not in seen and not f.endswith("config.json"):
                    full_p = os.path.join(d, f)
                    info = extract_layout_info(full_p)
                    if info:
                        layouts.append({"filename": f, "path": full_p, "info": info})
                        seen.add(f)
    return layouts

def evaluate_co_models_10_days(
    kitchen_model_path: str,
    waiter_model_path: str,
    layout_path: str,
    difficulty: int = 3,
    eval_days: int = 10
) -> dict:
    """
    Hem eğitilen Mutfak/Şef modelini hem de Garson modelini birlikte 10 günlük
    simülasyonda test eder; sinerji ve ortak performans metriklerini hesaplar.
    """
    from sb3_contrib import MaskablePPO
    from stable_baselines3 import PPO
    from sb3_contrib.common.wrappers import ActionMasker

    def mask_fn(e):
        return e.action_masks()

    # Ortamları başlat
    k_env = RestaurantGymEnv(config_path=layout_path, difficulty_level=difficulty, freeze_ml=True)
    wrapped_k_env = ActionMasker(k_env, mask_fn)

    # Mutfak modelini yükle
    k_model = None
    if os.path.exists(kitchen_model_path):
        try:
            k_model = MaskablePPO.load(kitchen_model_path, env=wrapped_k_env)
        except Exception as e:
            print(f"[UYARI] Mutfak modeli yüklenemedi: {e}")
            k_model = None

    # Garson modelini yükle
    w_env = WaiterGymEnv(config_path=layout_path, difficulty_level=difficulty)
    w_model = None
    if os.path.exists(waiter_model_path):
        try:
            w_model = PPO.load(waiter_model_path, env=w_env)
        except Exception as e:
            print(f"[UYARI] Garson modeli yüklenemedi: {e}")
            w_model = None

    total_rewards = 0.0
    total_completed = 0
    total_churned = 0
    all_wait_times = []
    all_cold_times = []

    for day in range(1, eval_days + 1):
        obs, info = wrapped_k_env.reset(seed=3000 + day)
        engine = k_env.engine
        w_env.engine = engine
        engine.enable_rl_waiter = (w_model is not None)
        done = False
        day_reward = 0.0

        while not done:
            # 1. Garson RL Aksiyonları (Sub-tick: boşta garson ve iş kaldıkça seri ata)
            if w_model is not None:
                for _ in range(len(engine.grid.waiters)):
                    w_masks = w_env.action_masks()
                    if not np.any(w_masks[1:] > 0):
                        break
                    w_obs = w_env._get_obs()
                    w_action, _ = w_model.predict(w_obs, deterministic=True)
                    if int(w_action) == 0:
                        break
                    assigned = w_env._execute_waiter_action(int(w_action))
                    if not assigned:
                        break

            # 2. Mutfak RL Aksiyonu
            if k_model is not None:
                action_masks = wrapped_k_env.action_masks()
                k_action, _ = k_model.predict(obs, action_masks=action_masks, deterministic=True)
                obs, reward, terminated, truncated, info = wrapped_k_env.step(k_action)
                day_reward += reward
                done = terminated or truncated
            else:
                # Standart adım
                engine.step(actions=None)
                done = engine.tick >= 1440

        total_rewards += day_reward
        completed_foods = [o for o in engine.completed_orders if getattr(o, "category", "main_dish") in ["main_dish", "appetizer"]]
        churned_foods = [o for o in engine.churned_orders if getattr(o, "category", "main_dish") in ["main_dish", "appetizer"]]

        day_wait = [(o.timestamps["kitchen_start"] - o.timestamps["created_at"]) for o in completed_foods if o.timestamps.get("kitchen_start") is not None and o.timestamps.get("created_at") is not None]
        day_cold = [max(0.0, (o.timestamps.get("delivered_at") or 0.0) - (o.timestamps.get("kitchen_finish") or 0.0) - 5.0) for o in completed_foods if o.timestamps.get("delivered_at") is not None and o.timestamps.get("kitchen_finish") is not None]

        total_completed += len(engine.completed_orders)
        total_churned += engine.churned_customers
        total_completed_foods = locals().get("total_completed_foods", 0) + len(completed_foods)
        total_churned_foods = locals().get("total_churned_foods", 0) + len(churned_foods)
        all_wait_times.extend(day_wait)
        all_cold_times.extend(day_cold)

    mean_wait = float(np.mean(all_wait_times)) if all_wait_times else 0.0
    mean_cold = float(np.mean(all_cold_times)) if all_cold_times else 0.0
    mean_daily_completed = round(total_completed / max(1, eval_days), 2)
    mean_daily_churn = round(total_churned / max(1, eval_days), 2)
    mean_reward = round(total_rewards / max(1, eval_days), 2)

    food_demand = total_completed_foods + total_churned_foods
    success_rate = round((total_completed_foods / max(1, food_demand)) * 100, 1) if food_demand > 0 else 0.0
    hot_count = sum(1 for c in all_cold_times if c <= 0.001)
    hot_delivery_ratio = round((hot_count / max(1, len(all_cold_times))) * 100, 1) if all_cold_times else 0.0

    chef_count = len(k_env.engine.grid.chefs)
    table_count = len(k_env.engine.grid.tables)
    chef_productivity = round(mean_daily_completed / max(1, chef_count), 1)
    table_turnover = round((mean_daily_completed / max(1, table_count)), 1)

    eval_score = mean_reward

    return {
        "eval_days": eval_days,
        "total_completed": total_completed,
        "total_churned": total_churned,
        "total_completed_foods": total_completed_foods,
        "total_churned_foods": total_churned_foods,
        "mean_daily_completed": mean_daily_completed,
        "mean_daily_churn": mean_daily_churn,
        "success_rate": success_rate,
        "hot_delivery_ratio": hot_delivery_ratio,
        "chef_productivity": chef_productivity,
        "table_turnover": table_turnover,
        "mean_queue_wait_time": round(mean_wait, 2),
        "mean_food_cold_time": round(mean_cold, 2),
        "mean_reward_per_day": mean_reward,
        "eval_score": eval_score
    }

def update_summary_report(
    history: list,
    layout_filename: str,
    *args,
    **kwargs
):
    """results/long_train_summary.md dosyasını anlık günceller."""
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Argument resolution for backward compatibility
    if len(args) == 4 and isinstance(args[0], str):
        # Legacy signature: (history, layout_filename, layout_path, difficulty, best_epoch, best_score)
        difficulty = args[1]
        best_epoch = args[2]
        best_score = args[3]
        mode_type = kwargs.get("mode_type", "co-train")
    elif len(args) >= 3:
        difficulty = args[0]
        best_epoch = args[1]
        best_score = args[2]
        mode_type = args[3] if len(args) > 3 and isinstance(args[3], str) else kwargs.get("mode_type", "co-train")
    else:
        difficulty = kwargs.get("difficulty", 3)
        best_epoch = kwargs.get("best_epoch", 1)
        best_score = kwargs.get("best_score", 0.0)
        mode_type = kwargs.get("mode_type", "co-train")

    mode_title = "Dönüşümlü Çift Ajanlı (Co-Evolutionary: Şef 🔄 Garson)" if mode_type == "co-train" else f"Tekil Ajan ({str(mode_type).upper()})"

    lines = [
        "# 🚀 Uzun Süreli Sıralı RL Eğitimi (Alternating Co-Training) Canlı İlerleme Raporu\n",
        f"**Tarih:** {time.strftime('%Y-%m-%d %H:%M:%S')} | **Harita:** `{layout_filename}` | **Zorluk:** Seviye {difficulty}\n",
        f"**Eğitim Stratejisi:** {mode_title}\n",
        f"**Döngü Yapısı:** Her Döngüde [Şef Eğitimi $\\to$ Garson Eğitimi $\\to$ Ortak 10 Günlük Sinerji Testi]\n",
        f"**En Başarılı Sinerji:** 🏆 **Döngü {best_epoch}** (Ortak Skor: `{best_score:+.2f}`)\n",
        "---\n",
        "## 📊 İterasyon Geçmişi ve Ortak Doğrulama Tablosu\n",
        "| Döngü | Küm. Gün | Şef Süresi | Garson Süresi | Günlük Sipariş | % Başarı | % Sıcak Teslim | Aşçı Verim | Ort. Bekleme | Ort. Soğuma | Skor (Ödül) | Durum / Patience |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    for entry in history:
        ep = entry["epoch"]
        cum_days = entry["cumulative_train_days"]
        k_time = f"{entry.get('kitchen_elapsed_sec', 0.0):.1f}sn"
        w_time = f"{entry.get('waiter_elapsed_sec', 0.0):.1f}sn"
        m_comp = f"{entry['eval_metrics']['mean_daily_completed']} sip/gün"
        m_succ = f"%{entry['eval_metrics'].get('success_rate', 0.0)}"
        m_hot = f"%{entry['eval_metrics'].get('hot_delivery_ratio', 0.0)}"
        m_prod = f"{entry['eval_metrics'].get('chef_productivity', 0.0)} sip/aşçı"
        m_wait = f"{entry['eval_metrics']['mean_queue_wait_time']} dk"
        m_cold = f"{entry['eval_metrics']['mean_food_cold_time']} dk"
        m_score = f"{entry['eval_metrics']['eval_score']:+.2f}"
        status = entry["status_label"]

        lines.append(f"| **Döngü {ep}** | {cum_days} Gün | {k_time} | {w_time} | {m_comp} | {m_succ} | {m_hot} | {m_prod} | {m_wait} | {m_cold} | `{m_score}` | {status} |")

    lines.extend([
        "\n---\n",
        "## 💡 Kayıtlı En İyi Model Ağırlıkları\n",
        f"* **En İyi Mutfak/Şef Modeli :** `{BEST_KITCHEN_MODEL}`",
        f"* **En İyi Garson Modeli      :** `{BEST_WAITER_MODEL}`",
        f"* **Güncel Mutfak Modeli      :** `{DEFAULT_KITCHEN_MODEL}`",
        f"* **Güncel Garson Modeli      :** `{DEFAULT_WAITER_MODEL}`\n",
        "---\n*Bu rapor run_long_training.py tarafından her dönüşümlü döngü sonrasında otomatik güncellenmektedir.*"
    ])

    with open(SUMMARY_MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    with open(HISTORY_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def prompt_user_choices(existing_models: bool, cli_layout=None, cli_mode=None, cli_envs=None, cli_max_epochs=None, cli_train_type=None):
    print("\n" + "=" * 80)
    print("🔥 UZUN SÜRELİ DÖNÜŞÜMLÜ RL EĞİTİM YÖNETİCİSİ (CO-EVOLUTIONARY TRAIN)")
    print("=" * 80)
    print("📌 Strateji: Şef Eğit -> Garson Eğit -> Ortak Test (10 Gün) -> En İyiyi Kaydet")
    print("-" * 80)

    # 1. Eğitim Tipi Seçimi
    if cli_train_type is not None:
        train_type = cli_train_type
    else:
        print("\n[ADIM 1/4] Hangi Ajan(lar) Eğitilsin?")
        print("  [1] 🔄 Dönüşümlü Çift Eğitim (Şef + Garson Sırayla Gelişsin) [Varsayılan]")
        print("  [2] 🧑‍🍳 Sadece Mutfak / Şef Ajanı (Garson Sabit)")
        print("  [3] 🍽️ Sadece Garson Ajanı (Mutfak Sabit)")
        t_choice = input("\nSeçiminiz [1/2/3] (Varsayılan: 1): ").strip()
        if t_choice == "2":
            train_type = "kitchen-only"
        elif t_choice == "3":
            train_type = "waiter-only"
        else:
            train_type = "co-train"

    # 2. Mod Seçimi (Continue / Overwrite)
    if cli_mode is not None:
        mode = cli_mode
    elif existing_models:
        print(f"\n[!] Kayıtlı RL modelleri bulundu.")
        print("  [1] Mevcut modelleri yükle ve üstüne eğitmeye devam et (Fine-Tune) [Varsayılan]")
        print("  [2] Sıfırdan yeni model eğit (Kayıtlı modellerin üzerine yaz)")
        choice = input("\nSeçiminiz [1/2] (Varsayılan: 1): ").strip()
        mode = "overwrite" if choice == "2" else "continue"
    else:
        print("\n[i] Henüz kayıtlı model yok. Sıfırdan eğitim başlatılacak.")
        mode = "new"

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
            print(f"  [{idx}] {l['filename']:<22} | Boyut: {inf.get('grid_size', '?'):<5} | Masalar: {inf.get('table_count', 0):2d} | İstasyon: {inf.get('station_count', 0):2d} ({st_types}) | Garson: {inf.get('waiter_count', 0)} | Aşçı: {inf.get('chef_count', 0)} | Tezgah: {inf.get('counter_count', 0)}")
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

    # 5. Maksimum Döngü (Epoch) Sayısı
    if cli_max_epochs is not None:
        max_epochs = cli_max_epochs
    else:
        print("\n[ADIM 4/4] Maksimum kaç döngü (Dönüşümlü Tur) çalışsın?")
        print("  [1] 5 Döngü   (Hızlı Deneme / ~360k Timestep)")
        print("  [2] 10 Döngü  (Standart / ~720k Timestep) [Varsayılan]")
        print("  [3] 20 Döngü  (Kapsamlı Sinerji Eğitimi / ~1.44M Timestep)")
        print("  [4] Sınırsız  (Erken durdurma tetiklenene kadar durma)")
        ep_choice = input("Seçiminiz [1/2/3/4 veya özel döngü sayısı] (Varsayılan: 2): ").strip()
        if ep_choice == "1":
            max_epochs = 5
        elif ep_choice == "2" or ep_choice == "":
            max_epochs = 10
        elif ep_choice == "3":
            max_epochs = 20
        elif ep_choice == "4":
            max_epochs = 999
        else:
            try:
                max_epochs = int(ep_choice)
                if max_epochs <= 0: max_epochs = 10
            except ValueError:
                max_epochs = 10

    return train_type, mode, selected_layout, selected_envs, max_epochs

def main():
    parser = argparse.ArgumentParser(description="Uzun Süreli Sıralı RL Eğitimi ve Sinerji Yöneticisi")
    parser.add_argument("--train-type", type=str, choices=["co-train", "kitchen-only", "waiter-only"], default=None, help="Eğitim türü")
    parser.add_argument("--mode", type=str, choices=["continue", "overwrite", "new"], default=None, help="Eğitim modu")
    parser.add_argument("--layout", type=str, default=None, help="Kullanılacak layout dosyası")
    parser.add_argument("--difficulty", type=int, default=3, help="Zorluk seviyesi (1, 2, 3)")
    parser.add_argument("--num-envs", type=int, default=None, help="Paralel simülasyon ortamı sayısı")
    parser.add_argument("--max-epochs", type=int, default=None, help="Maksimum döngü sayısı")
    parser.add_argument("--days-per-turn", type=int, default=50, help="Her aşamada eğitilecek simülasyon günü (varsayılan: 50)")
    parser.add_argument("--patience", type=int, default=5, help="Gelişme olmadan durdurulacak döngü sayısı (varsayılan: 5)")
    args = parser.parse_args()

    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    existing_models = os.path.exists(DEFAULT_KITCHEN_MODEL) or os.path.exists(DEFAULT_WAITER_MODEL)

    train_type, mode, layout_entry, num_envs, max_epochs = prompt_user_choices(
        existing_models,
        cli_layout=args.layout,
        cli_mode=args.mode,
        cli_envs=args.num_envs,
        cli_max_epochs=args.max_epochs,
        cli_train_type=args.train_type
    )

    layout_path = layout_entry["path"]
    days_per_turn = args.days_per_turn
    eval_days = 10
    timesteps_per_turn = days_per_turn * 1440  # 72,000 timesteps per agent turn
    patience_limit = args.patience

    lr_init = 1e-4 if mode == "continue" else 3e-4

    print("\n" + "=" * 80)
    print("🚀 DÖNÜŞÜMLÜ CO-TRAINING YAPILANDIRMASI")
    print("=" * 80)
    print(f"Eğitim Tipi           : {train_type.upper()}")
    print(f"Layout Dosyası        : {layout_entry['filename']} ({layout_path})")
    print(f"Mod                   : {mode.upper()} (Öğrenme Oranı: {lr_init:.1e})")
    print(f"Tur Başına Gün/Adım   : {days_per_turn} Gün ({timesteps_per_turn:,} Timestep)")
    print(f"Değerlendirme Testi   : {eval_days} Gün (14,400 Tick Ortak Simülasyon)")
    print(f"Paralel Çekirdek      : {num_envs} CPU Thread")
    print(f"Maksimum Tur Sayısı   : {max_epochs} Tur")
    print(f"Early Stopping Limiti : {patience_limit} Başarısız Döngü")
    print(f"En İyi Şef Modeli     : {BEST_KITCHEN_MODEL}")
    print(f"En İyi Garson Modeli  : {BEST_WAITER_MODEL}")
    print(f"Canlı Rapor Dosyası   : {SUMMARY_MD_PATH}")
    print("=" * 80 + "\n")

    # 1. Ajan Nesnelerini Başlat
    kitchen_agent = None
    if train_type in ["co-train", "kitchen-only"]:
        kitchen_agent = OrderSchedulerRLAgent(
            config_path=layout_path,
            num_envs=num_envs,
            difficulty_level=args.difficulty,
            model_path=DEFAULT_KITCHEN_MODEL,
            freeze_ml=True,
            learning_rate=lr_init,
            ent_coef=0.01
        )
        if mode == "continue":
            load_p = BEST_KITCHEN_MODEL if os.path.exists(BEST_KITCHEN_MODEL) else DEFAULT_KITCHEN_MODEL
            if os.path.exists(load_p):
                kitchen_agent.model_path = load_p
                if kitchen_agent.load():
                    print(f"[YÜKLENDİ] Mutfak Modeli: {load_p}")
                kitchen_agent.model_path = DEFAULT_KITCHEN_MODEL

    waiter_agent = None
    if train_type in ["co-train", "waiter-only"]:
        waiter_agent = WaiterRLAgent(
            config_path=layout_path,
            difficulty_level=args.difficulty,
            model_path=DEFAULT_WAITER_MODEL,
            learning_rate=lr_init
        )
        if mode == "continue":
            load_p = BEST_WAITER_MODEL if os.path.exists(BEST_WAITER_MODEL) else DEFAULT_WAITER_MODEL
            if os.path.exists(load_p):
                waiter_agent.model_path = load_p
                if waiter_agent.load():
                    print(f"[YÜKLENDİ] Garson Modeli: {load_p}")
                waiter_agent.model_path = DEFAULT_WAITER_MODEL

    history = []
    best_score = -float("inf")
    best_epoch = 0
    patience_counter = 0
    total_cumulative_days = 0

    start_total_time = time.time()

    for epoch in range(1, max_epochs + 1):
        print("\n" + "=" * 80)
        print(f"🔄 DÖNGÜ {epoch}/{max_epochs} | Dönüşümlü İkili Eğitim Başlatılıyor...")
        print("=" * 80)

        k_elapsed = 0.0
        w_elapsed = 0.0

        # FAZ 1: Şef / Mutfak Eğitimi (Garson Sabit)
        if kitchen_agent is not None:
            print(f"\n[Döngü {epoch} - FAZ 1] 🧑‍🍳 ŞEF / MUTFAK RL Ajanı Eğitiliyor ({timesteps_per_turn:,} Timestep)...")
            k_start = time.time()
            kitchen_agent.train(total_timesteps=timesteps_per_turn, lr_initial=lr_init, lr_final=1e-5)
            k_elapsed = time.time() - k_start
            print(f"[FAZ 1 Bitti] Şef Eğitimi Süresi: {k_elapsed:.1f} sn")

        # FAZ 2: Garson Eğitimi (Mutfak Sabit)
        if waiter_agent is not None:
            print(f"\n[Döngü {epoch} - FAZ 2] 🍽️ GARSON RL Ajanı Eğitiliyor ({timesteps_per_turn:,} Timestep)...")
            w_start = time.time()
            waiter_agent.train(total_timesteps=timesteps_per_turn, save_path=DEFAULT_WAITER_MODEL)
            w_elapsed = time.time() - w_start
            print(f"[FAZ 2 Bitti] Garson Eğitimi Süresi: {w_elapsed:.1f} sn")

        total_cumulative_days += days_per_turn

        # FAZ 3: Ortak Sinerji Değerlendirmesi (10 Günlük Birlikte Simülasyon)
        print(f"\n[Döngü {epoch} - FAZ 3] 📊 Şef + Garson Ortak Değerlendirme Testi Başlıyor (10 Gün)...")
        eval_metrics = evaluate_co_models_10_days(
            kitchen_model_path=DEFAULT_KITCHEN_MODEL,
            waiter_model_path=DEFAULT_WAITER_MODEL,
            layout_path=layout_path,
            difficulty=args.difficulty,
            eval_days=eval_days
        )

        current_score = eval_metrics["eval_score"]
        print("-" * 80)
        print(f"📊 10 GÜNLÜK ORTAK SİNERJİ SONUCU (Döngü {epoch}):")
        print(f"  * Günlük Ort. Tamamlanan : {eval_metrics['mean_daily_completed']} sipariş/gün (Toplam: {eval_metrics['total_completed']})")
        print(f"  * Hizmet Başarı Oranı    : %{eval_metrics['success_rate']} (Churn: {eval_metrics['mean_daily_churn']} kişi/gün)")
        print(f"  * Sıcak Teslimat Oranı   : %{eval_metrics['hot_delivery_ratio']} (Tezgahta soğumadan teslim)")
        print(f"  * Aşçı Başına Verim      : {eval_metrics['chef_productivity']} sipariş/aşçı/gün")
        print(f"  * Ort. Kuyruk Bekleme    : {eval_metrics['mean_queue_wait_time']:.2f} dk")
        print(f"  * Ort. Yemek Soğuma      : {eval_metrics['mean_food_cold_time']:.2f} dk")
        print(f"  * Günlük Ortalama Ödül   : {eval_metrics['mean_reward_per_day']:+.2f}")
        print("-" * 80)

        # FAZ 4: Karşılaştırma & Checkpoint Kaydı
        if current_score > best_score:
            score_diff = current_score - best_score if best_score != -float("inf") else 0.0
            best_score = current_score
            best_epoch = epoch
            patience_counter = 0

            # En iyi modelleri kaydet
            if os.path.exists(DEFAULT_KITCHEN_MODEL):
                shutil.copyfile(DEFAULT_KITCHEN_MODEL, BEST_KITCHEN_MODEL)
            if os.path.exists(DEFAULT_WAITER_MODEL):
                shutil.copyfile(DEFAULT_WAITER_MODEL, BEST_WAITER_MODEL)

            status_label = f"🏆 YENİ EN İYİ (Skor: {best_score:+.2f})"
            print(f"🏆 [YENİ EN İYİ SİNERJİ KAYDEDİLDİ!] Önceki Rekor Aşıldı ({score_diff:+.2f}). Modeller: BEST_*.zip")
        else:
            patience_counter += 1
            status_label = f"⚠️ Gelişme Yok (Patience: {patience_counter}/{patience_limit})"
            print(f"⚠️ [GELİŞME YOK] Mevcut Skor: {current_score:+.2f} <= En İyi Skor: {best_score:+.2f} (Döngü {best_epoch})")
            print(f"⏳ Early Stopping Sayacı: {patience_counter}/{patience_limit}")

        history_entry = {
            "epoch": epoch,
            "cumulative_train_days": total_cumulative_days,
            "kitchen_elapsed_sec": round(k_elapsed, 2),
            "waiter_elapsed_sec": round(w_elapsed, 2),
            "eval_metrics": eval_metrics,
            "is_best": (epoch == best_epoch),
            "status_label": status_label
        }
        history.append(history_entry)

        # Raporları güncelle
        update_summary_report(history, layout_entry["filename"], args.difficulty, best_epoch, best_score, mode_type=train_type)
        print(f"📄 [CANLI RAPOR GÜNCELLENDİ] -> {SUMMARY_MD_PATH}")

        # Early Stopping Kontrolü
        if patience_counter >= patience_limit:
            print("\n" + "=" * 80)
            print(f"🛑 [EARLY STOPPING TETİKLENDİ] Üst üste {patience_limit} döngü boyunca gelişme sağlanamadı!")
            print(f"🏆 En İyi Modeller Korundu: Döngü {best_epoch} (Skor: {best_score:+.2f})")
            print("=" * 80)
            if os.path.exists(BEST_KITCHEN_MODEL):
                shutil.copyfile(BEST_KITCHEN_MODEL, DEFAULT_KITCHEN_MODEL)
            if os.path.exists(BEST_WAITER_MODEL):
                shutil.copyfile(BEST_WAITER_MODEL, DEFAULT_WAITER_MODEL)
            break

    total_elapsed = time.time() - start_total_time
    print("\n" + "=" * 80)
    print("🎉 DÖNÜŞÜMLÜ UZUN SÜRELİ EĞİTİM (CO-TRAIN) TAMAMLANDI!")
    print("=" * 80)
    print(f"Toplam Geçen Süre     : {total_elapsed / 60:.2f} dakika ({total_elapsed:.1f} saniye)")
    print(f"Toplam Eğitilen Gün   : {total_cumulative_days} Simülasyon Günü")
    print(f"En İyi Sinerji Döngüsü: Döngü {best_epoch}")
    print(f"En İyi Doğrulama Skoru: {best_score:+.2f}")
    print(f"En İyi Şef Modeli     : {BEST_KITCHEN_MODEL}")
    print(f"En İyi Garson Modeli  : {BEST_WAITER_MODEL}")
    print(f"Detaylı Özet Raporu   : {SUMMARY_MD_PATH}")
    print("=" * 80 + "\n")

    try:
        input("Programı kapatmak için Enter tuşuna basın...")
    except Exception:
        pass

if __name__ == "__main__":
    main()
