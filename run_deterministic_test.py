import os
import sys
import json
import time
import argparse
import numpy as np

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from simulation.engine import SimulationEngine
from simulation.scheduler_baselines import FIFOScheduler, SPTScheduler, LPTScheduler, MinPatienceScheduler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
LAYOUTS_DIR = os.path.join(BASE_DIR, "layouts")
CONFIG_DIR = os.path.join(BASE_DIR, "config")

def get_available_layouts():
    """Tüm mevcut layout dosyalarını bulur ve temel bilgilerini çıkarır."""
    layouts = []
    seen = set()
    
    # 1. layouts/ dizini
    if os.path.exists(LAYOUTS_DIR):
        for f in sorted(os.listdir(LAYOUTS_DIR)):
            if f.endswith(".json") and f not in seen:
                full_p = os.path.join(LAYOUTS_DIR, f)
                info = extract_layout_info(full_p)
                layouts.append({"filename": f, "path": full_p, "info": info})
                seen.add(f)
                
    # 2. config/ dizini (fallback)
    if os.path.exists(CONFIG_DIR):
        for f in sorted(os.listdir(CONFIG_DIR)):
            if f.endswith(".json") and f not in seen:
                full_p = os.path.join(CONFIG_DIR, f)
                info = extract_layout_info(full_p)
                layouts.append({"filename": f, "path": full_p, "info": info})
                seen.add(f)
                
    return layouts

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
            "grid_size": "N/A", "table_count": 0, "total_capacity": 0,
            "station_count": 0, "station_types": [], "waiter_count": 0, "chef_count": 0
        }

def prompt_user_choices(cli_days=None, cli_layout=None):
    """Kullanıcıdan gün (10, 50, 100) ve layout seçimlerini alır."""
    print("\n" + "=" * 75)
    print("📊 DETERMINİSTİK RESTORAN ALGORİTMALARI BENCHMARK SİSTEMİ")
    print("=" * 75)
    
    # 1. GÜN SEÇİMİ
    if cli_days is not None:
        selected_days = cli_days
    else:
        print("\n[ADIM 1/2] Kaç günlük test simülasyonu çalıştırmak istersiniz?")
        print("  [1] 10 Gün  (14.400 simülasyon adımı - Hızlı Doğrulama)")
        print("  [2] 50 Gün  (72.000 simülasyon adımı - Kapsamlı Test)")
        print("  [3] 100 Gün (144.000 simülasyon adımı - Tam Benchmark) [Varsayılan]")
        choice = input("Seçiminiz [1/2/3 veya özel gün sayısı] (Varsayılan: 3): ").strip()
        
        if choice == "1":
            selected_days = 10
        elif choice == "2":
            selected_days = 50
        elif choice == "3" or choice == "":
            selected_days = 100
        else:
            try:
                selected_days = int(choice)
                if selected_days <= 0: selected_days = 100
            except ValueError:
                selected_days = 100

    # 2. LAYOUT SEÇİMİ
    available = get_available_layouts()
    if not available:
        raise FileNotFoundError("Hiçbir layout (.json) dosyası bulunamadı!")
        
    if cli_layout is not None:
        matched = next((l for l in available if l["filename"] == cli_layout or l["path"] == cli_layout or os.path.basename(cli_layout) == l["filename"]), None)
        if matched:
            selected_layout = matched
        elif os.path.exists(cli_layout):
            selected_layout = {"filename": os.path.basename(cli_layout), "path": cli_layout, "info": extract_layout_info(cli_layout)}
        else:
            print(f"[UYARI] '{cli_layout}' bulunamadı, varsayılan layout seçiliyor.")
            selected_layout = available[0]
    else:
        print("\n[ADIM 2/2] Hangi Restoran Düzeni (Layout) üzerinde simüle edilsin?")
        for idx, l in enumerate(available, 1):
            inf = l["info"]
            st_types = ", ".join(inf["station_types"]) if inf["station_types"] else "Yok"
            print(f"  [{idx}] {l['filename']:<22} | Boyut: {inf['grid_size']:<5} | Masalar: {inf['table_count']:2d} ({inf['total_capacity']:2d} kişi) | İstasyon: {inf['station_count']:2d} ({st_types}) | Garson: {inf['waiter_count']} | Aşçı: {inf['chef_count']}")
            
        layout_choice = input(f"\nSeçiminiz [1-{len(available)}] (Varsayılan: 1): ").strip()
        try:
            l_idx = int(layout_choice) - 1
            if 0 <= l_idx < len(available):
                selected_layout = available[l_idx]
            else:
                selected_layout = available[0]
        except ValueError:
            selected_layout = available[0]
            
    return selected_days, selected_layout

def run_single_scheduler(scheduler_cls, scheduler_name: str, config_path: str, total_days: int = 100, difficulty: int = 3):
    ticks_per_day = 1440
    total_ticks = total_days * ticks_per_day
    
    print(f"\n[{scheduler_name}] {total_days} Günlük Vardiya Testi Başlatılıyor ({total_ticks} adım)...")
    start_time = time.time()
    
    daily_logs = []
    total_completed = 0
    total_churned = 0
    all_wait_times = []
    all_cold_times = []
    
    # Her günü bağımsız bir restoran iş günü (1440 ticklik vardiya) olarak koştur
    for day in range(1, total_days + 1):
        engine = SimulationEngine(config_path=config_path, difficulty_level=difficulty)
        engine.reset()
        np.random.seed(1000 + day) # Tutarlı ve tekrarlanabilir rastgelelik
        scheduler = scheduler_cls(engine)
        
        for tick in range(1, ticks_per_day + 1):
            actions = scheduler.step()
            for act in actions:
                if act["type"] == "ASSIGN":
                    order = next((o for o in engine.order_queue if o.order_id == act["order_id"]), None)
                    if order:
                        station = engine.grid.stations.get(act["station_id"])
                        chef = engine.grid.chefs.get(act["chef_id"])
                        if station and chef:
                            engine.assign_order(order, station, chef)
                            
            engine.step(actions=[])
            
        # Gün sonu metrikleri
        day_completed = len(engine.completed_orders)
        day_churn = engine.churned_customers
        total_completed += day_completed
        total_churned += day_churn
        
        # Günlük bekleme ve soğuma süreleri
        completed = engine.completed_orders
        day_wait = [(o.timestamps["kitchen_start"] - o.timestamps["created_at"]) for o in completed if o.timestamps.get("kitchen_start") and o.timestamps.get("created_at")]
        day_cold = [max(0.0, o.timestamps["delivered_at"] - o.timestamps["kitchen_finish"] - 5.0) for o in completed if o.timestamps.get("delivered_at") and o.timestamps.get("kitchen_finish")]
        
        all_wait_times.extend(day_wait)
        all_cold_times.extend(day_cold)
        
        daily_logs.append({
            "day": day,
            "day_completed": day_completed,
            "cumulative_completed": total_completed,
            "day_churn": day_churn,
            "cumulative_churn": total_churned
        })
        
        if day % 10 == 0 or day == total_days or day == 1:
            print(f"  -> Gün {day:3d}/{total_days} | Günlük Tamamlanan: {day_completed:3d} (Kümülatif: {total_completed:5d}) | Günlük Churn: {day_churn:3d} (Toplam: {total_churned:5d})")
            
    elapsed = time.time() - start_time
    
    mean_wait = float(np.mean(all_wait_times)) if all_wait_times else 0.0
    mean_cold = float(np.mean(all_cold_times)) if all_cold_times else 0.0
    
    return {
        "name": scheduler_name,
        "total_days": total_days,
        "elapsed_seconds": round(elapsed, 2),
        "total_completed": total_completed,
        "total_churned": total_churned,
        "mean_daily_completed": round(total_completed / max(1, total_days), 2),
        "mean_daily_churn": round(total_churned / max(1, total_days), 2),
        "mean_queue_wait_time": round(mean_wait, 2),
        "mean_food_cold_time": round(mean_cold, 2),
        "daily_progression": daily_logs
    }

def main():
    parser = argparse.ArgumentParser(description="Deterministik Restoran Çizelgeleme Algoritmaları Benchmark Test Aracı")
    parser.add_argument("--days", type=int, default=None, help="Test edilecek gün sayısı (10, 50, 100)")
    parser.add_argument("--layout", type=str, default=None, help="Özel layout dosya adı veya yolu")
    parser.add_argument("--difficulty", type=int, default=3, help="Zorluk seviyesi (1, 2, 3)")
    args = parser.parse_args()
    
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    # 1. Seçimleri al
    total_days, layout_entry = prompt_user_choices(args.days, args.layout)
    layout_path = layout_entry["path"]
    layout_info = layout_entry["info"]
    
    print("\n" + "=" * 75)
    print("TEST YAPILANDIRMASI (GÜNLÜK VARDİYA MİMARİSİ)")
    print("=" * 75)
    print(f"Layout Dosyası  : {layout_entry['filename']} ({layout_path})")
    print(f"Izgara Boyutu   : {layout_info['grid_size']}")
    print(f"Masa Durumu     : {layout_info['table_count']} Masa ({layout_info['total_capacity']} Sandalye Kapasitesi)")
    print(f"İstasyonlar     : {layout_info['station_count']} İstasyon ({', '.join(layout_info['station_types'])})")
    print(f"Personel        : {layout_info['waiter_count']} Garson | {layout_info['chef_count']} Aşçı")
    print(f"Test Süresi     : {total_days} Gün ({total_days * 1440:,} Simülasyon Adımı)")
    print(f"Zorluk Seviyesi : Seviye {args.difficulty}")
    print("Test Algoritması: FIFO, SPT, LPT, MinPatience")
    print("=" * 75)
    
    schedulers = [
        (FIFOScheduler, "FIFO (First-In-First-Out)"),
        (SPTScheduler, "SPT (Shortest Processing Time)"),
        (LPTScheduler, "LPT (Longest Processing Time)"),
        (MinPatienceScheduler, "MinPatience (En Düşük Sabır)")
    ]
    
    results = {
        "benchmark_metadata": {
            "test_type": "Deterministic Baselines Benchmark (Daily Shifts)",
            "days": total_days,
            "total_simulation_ticks": total_days * 1440,
            "difficulty": args.difficulty,
            "layout_filename": layout_entry["filename"],
            "layout_path": layout_path,
            "layout_details": layout_info,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "schedulers": {}
    }
    
    for s_cls, s_name in schedulers:
        res = run_single_scheduler(s_cls, s_name, layout_path, total_days=total_days, difficulty=args.difficulty)
        results["schedulers"][s_name] = res
        
    # 1. JSON Kaydı
    json_path = os.path.join(RESULTS_DIR, "deterministic_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    # 2. Detaylı Metin Raporu (TXT)
    txt_path = os.path.join(RESULTS_DIR, "deterministic_results.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 90 + "\n")
        f.write(f"DETERMİNİSTİK ALGORİTMALAR BENCHMARK TEST RAPORU (GÜNLÜK VARDİYA)\n")
        f.write("=" * 90 + "\n\n")
        f.write(f"Test Tarihi        : {results['benchmark_metadata']['timestamp']}\n")
        f.write(f"Simülasyon Süresi  : {total_days} Gün ({total_days * 1440:,} Simülasyon Adımı / Tick)\n")
        f.write(f"Zorluk Seviyesi    : Seviye {args.difficulty}\n\n")
        f.write("-" * 90 + "\n")
        f.write("RESTORAN DÜZENİ (LAYOUT) DETAYLARI\n")
        f.write("-" * 90 + "\n")
        f.write(f"Layout Dosyası     : {layout_entry['filename']}\n")
        f.write(f"Dosya Yolu         : {layout_path}\n")
        f.write(f"Izgara Boyutu      : {layout_info['grid_size']}\n")
        f.write(f"Masa Sayısı        : {layout_info['table_count']} Masa\n")
        f.write(f"Toplam Kapasite    : {layout_info['total_capacity']} Müşteri / Sandalye\n")
        f.write(f"İstasyon Sayısı    : {layout_info['station_count']} İstasyon ({', '.join(layout_info['station_types'])})\n")
        f.write(f"Personel Kadrosu   : {layout_info['waiter_count']} Garson, {layout_info['chef_count']} Aşçı\n\n")
        
        f.write("=" * 90 + "\n")
        f.write("ALGORİTMA KARŞILAŞTIRMA VE BAŞARIM SONUÇLARI\n")
        f.write("=" * 90 + "\n")
        header = f"{'Algoritma':<32} | {'Tamamlanan':<12} | {'Churn (Kayıp)':<14} | {'Ort. Bekleme':<14} | {'Soğuma':<10}\n"
        f.write(header)
        f.write("-" * 90 + "\n")
        
        print("\n" + "=" * 90)
        print("GENEL SONUÇ TABLOSU")
        print("=" * 90)
        print(header, end="")
        print("-" * 90)
        
        for name, data in results["schedulers"].items():
            line = f"{name:<32} | {data['total_completed']:<12d} | {data['total_churned']:<14d} | {data['mean_queue_wait_time']:<12.2f}dk | {data['mean_food_cold_time']:<8.2f}dk\n"
            f.write(line)
            print(line, end="")
            
        f.write("=" * 90 + "\n")
        print("=" * 90)
        
    print(f"\n[KAYIT] JSON sonuçları kaydedildi : {json_path}")
    print(f"[KAYIT] Detaylı rapor kaydedildi : {txt_path}\n")

if __name__ == "__main__":
    main()
