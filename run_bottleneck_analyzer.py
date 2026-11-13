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
from simulation.analyzer import BottleneckAnalyzer
from simulation.scheduler_baselines import FIFOScheduler, SPTScheduler, LPTScheduler, MinPatienceScheduler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
LAYOUTS_DIR = os.path.join(BASE_DIR, "layouts")
CONFIG_DIR = os.path.join(BASE_DIR, "config")

def get_available_layouts():
    layouts = []
    seen = set()
    for d in [LAYOUTS_DIR, CONFIG_DIR]:
        if os.path.exists(d):
            for f in sorted(os.listdir(d)):
                if f.endswith(".json") and f not in seen:
                    layouts.append({"filename": f, "path": os.path.join(d, f)})
                    seen.add(f)
    return layouts

def run_analysis(
    layout_path: str,
    difficulty: int = 2,
    days: int = 5,
    algo: str = "FIFO"
) -> dict:
    """Runs a multi-day simulation and produces deep station and staff bottleneck diagnostics."""
    sched_map = {
        "FIFO": FIFOScheduler,
        "SPT": SPTScheduler,
        "LPT": LPTScheduler,
        "MinPatience": MinPatienceScheduler
    }
    SchedClass = sched_map.get(algo, FIFOScheduler)

    print(f"\n[BAŞLATILIYOR] {days} Günlük Derin Darboğaz Analizi...")
    print(f"  Layout      : {os.path.basename(layout_path)}")
    print(f"  Algoritma   : {algo}")
    print(f"  Zorluk      : Seviye {difficulty}")

    engine = SimulationEngine(config_path=layout_path, difficulty_level=difficulty, freeze_ml=True)
    analyzer = BottleneckAnalyzer(engine)

    total_completed = 0
    total_churned = 0
    total_completed_foods = 0
    total_churned_foods = 0
    total_completed_mains = 0
    total_churned_mains = 0
    total_completed_apps = 0
    total_churned_apps = 0
    total_completed_drinks = 0

    all_wait_times = []
    all_cold_times = []

    start_time = time.time()

    for day in range(1, days + 1):
        engine.reset()
        np.random.seed(1000 + day)
        scheduler = SchedClass(engine)

        for tick in range(1, 1441):
            actions = scheduler.step()
            for act in actions:
                if act.get("type") == "ASSIGN":
                    order = next((o for o in engine.order_queue if o.order_id == act.get("order_id")), None)
                    if order:
                        st = engine.grid.stations.get(act.get("station_id"))
                        ch = engine.grid.chefs.get(act.get("chef_id"))
                        if st and ch:
                            engine.assign_order(order, st, ch)
            engine.step(actions=[])
            analyzer.track_tick()

        comp = len(engine.completed_orders)
        churn = engine.churned_customers
        total_completed += comp
        total_churned += churn

        # Food vs Drink categorizations (ADR-034 aligned)
        completed_foods = [o for o in engine.completed_orders if getattr(o, "category", "main_dish") in ["main_dish", "appetizer"]]
        churned_foods = [o for o in engine.churned_orders if getattr(o, "category", "main_dish") in ["main_dish", "appetizer"]]
        
        comp_mains = sum(1 for o in completed_foods if o.category == "main_dish")
        churn_mains = sum(1 for o in churned_foods if o.category == "main_dish")
        comp_apps = sum(1 for o in completed_foods if o.category == "appetizer")
        churn_apps = sum(1 for o in churned_foods if o.category == "appetizer")
        comp_drinks = sum(1 for o in engine.completed_orders if getattr(o, "category", "main_dish") == "beverage")

        total_completed_foods += len(completed_foods)
        total_churned_foods += len(churned_foods)
        total_completed_mains += comp_mains
        total_churned_mains += churn_mains
        total_completed_apps += comp_apps
        total_churned_apps += churn_apps
        total_completed_drinks += comp_drinks

        day_wait = [(o.timestamps["kitchen_start"] - o.timestamps["created_at"]) for o in completed_foods if o.timestamps.get("kitchen_start") and o.timestamps.get("created_at")]
        day_cold = [max(0.0, (o.timestamps.get("delivered_at") or 0.0) - (o.timestamps.get("kitchen_finish") or 0.0) - 5.0) for o in completed_foods if o.timestamps.get("delivered_at") and o.timestamps.get("kitchen_finish")]
        all_wait_times.extend(day_wait)
        all_cold_times.extend(day_cold)

        print(f"  [GÜN {day:2d}/{days:2d}] Tamamlanan: {comp:4d} (Ana Yemek: {comp_mains:3d}, Aperatif: {comp_apps:3d}, İçecek: {comp_drinks:3d}) | Churn: {churn:3d}")

    elapsed = round(time.time() - start_time, 2)
    
    # Calculate ADR-034 rates
    total_food_demand = total_completed_foods + total_churned_foods
    success_rate = round((total_completed_foods / max(1, total_food_demand)) * 100, 1)
    
    total_main_demand = total_completed_mains + total_churned_mains
    main_dish_success_rate = round((total_completed_mains / max(1, total_main_demand)) * 100, 1)

    total_app_demand = total_completed_apps + total_churned_apps
    appetizer_success_rate = round((total_completed_apps / max(1, total_app_demand)) * 100, 1)

    hot_delivery_rate = round((sum(1 for c in all_cold_times if c == 0.0) / max(1, len(all_cold_times))) * 100, 1) if all_cold_times else 100.0

    top_bottlenecks = analyzer.get_top_bottlenecks(top_n=4)
    stage_summary = analyzer.get_stage_queue_summary()
    station_summary = analyzer.get_station_summary()
    dish_summary = analyzer.get_dish_performance_summary()
    interval_summary = analyzer.get_interval_summary()
    staff_summary = analyzer.get_staff_detailed_summary()
    counter_summary = analyzer.get_counter_summary()

    report_data = {
        "layout": os.path.basename(layout_path),
        "difficulty": difficulty,
        "days": days,
        "algorithm": algo,
        "elapsed_seconds": elapsed,
        "total_completed": total_completed,
        "total_churned": total_churned,
        "total_completed_foods": total_completed_foods,
        "total_churned_foods": total_churned_foods,
        "total_completed_mains": total_completed_mains,
        "total_churned_mains": total_churned_mains,
        "total_completed_apps": total_completed_apps,
        "total_churned_apps": total_churned_apps,
        "total_completed_drinks": total_completed_drinks,
        "success_rate": success_rate,
        "main_dish_success_rate": main_dish_success_rate,
        "appetizer_success_rate": appetizer_success_rate,
        "hot_delivery_rate": hot_delivery_rate,
        "mean_daily_completed": round(total_completed / max(1, days), 1),
        "mean_daily_churn": round(total_churned / max(1, days), 1),
        "mean_daily_foods": round(total_completed_foods / max(1, days), 1),
        "mean_daily_mains": round(total_completed_mains / max(1, days), 1),
        "mean_queue_wait_time": round(float(np.mean(all_wait_times)), 2) if all_wait_times else 0.0,
        "mean_food_cold_time": round(float(np.mean(all_cold_times)), 2) if all_cold_times else 0.0,
        "churn_breakdown": analyzer.churn_reasons,
        "churn_by_dish": analyzer.churn_by_dish,
        "churn_by_stage": analyzer.churn_by_stage,
        "top_bottlenecks": top_bottlenecks,
        "dish_summary": dish_summary,
        "interval_summary": interval_summary,
        "stage_summary": stage_summary,
        "station_summary": station_summary,
        "staff_summary": staff_summary,
        "counter_summary": counter_summary
    }

    print_report(report_data)
    save_report(report_data)
    return report_data

def print_report(data: dict):
    print("\n" + "=" * 105)
    print("📊 RESTORAN DERİN DARBOĞAZ VE SİSTEM PERFORMANS RAPORU (ADR-034 / ADR-038 STANDARDI)")
    print("=" * 105)
    print(f"Layout       : {data['layout']} | Zorluk: Seviye {data['difficulty']} | Algoritma: {data['algorithm']} | Süre: {data['days']} Gün")
    print(f"Genel Hacim  : {data['mean_daily_completed']} sip/gün ({data['mean_daily_foods']} pişen yemek + içecekler) | Churn: {data['mean_daily_churn']} müşteri/gün")
    print(f"Başarı Skoru : %{data['success_rate']} Yemek Başarısı | %{data['main_dish_success_rate']} Ana Yemek | %{data['appetizer_success_rate']} Aperatif")
    print(f"Kalite & Süre: %{data['hot_delivery_rate']} Sıcak Teslim | Ort. Bekleme: {data['mean_queue_wait_time']} dk | Ort. Soğuma: {data['mean_food_cold_time']} dk")

    print("\n" + "=" * 105)
    print("🚨 EN KRİTİK DARBOĞAZLAR VE ÇÖZÜM REÇETELERİ (TOP BOTTLENECKS)")
    print("=" * 105)

    if not data["top_bottlenecks"]:
        print("  🟢 Belirgin bir sistem darboğazı tespit edilmedi! Restoran dengeli çalışıyor.")
    else:
        for idx, b in enumerate(data["top_bottlenecks"], 1):
            print(f"\n  [{idx}] {b['category']}: {b['name']}")
            print(f"      📌 Ölçülen Metrik : {b['metric']}")
            print(f"      ⚠️ Sisteme Etkisi : {b['impact']}")
            print(f"      💡 Kesin Çözüm    : {b['recommendation']}")

    print("\n" + "=" * 105)
    print("🍽️ YEMEK BAZLI PERFORMANS, PİŞME VE KAYIP (CHURN) MATRİSİ")
    print("=" * 105)
    print(f"{'Yemek Adı':<16} | {'Kategori':<11} | {'Talep':<7} | {'Tamam':<7} | {'Churn':<7} | {'% Başarı':<9} | {'Ort. Bekleme':<13} | {'Ort. Pişme'}")
    print("-" * 105)
    for d in data.get("dish_summary", []):
        cat_tr = {"main_dish": "Ana Yemek", "appetizer": "Aperatif", "beverage": "İçecek"}.get(d["category"], d["category"])
        print(f"{d['dish_type']:<16} | {cat_tr:<11} | {d['demand_count']:<7} | {d['completed_count']:<7} | {d['churn_count']:<7} | %{d['success_rate']:<8} | {d['avg_queue_wait_minutes']:>4.1f} dk        | {d['avg_cook_minutes']:>4.1f} dk")

    print("\n" + "=" * 105)
    print("⏰ SAAT DİLİMLERİNE GÖRE TALEP YOĞUNLUĞU, TAMAMLANAN VE KAYIP (CHURN) DAĞILIMI")
    print("=" * 105)
    print(f"{'Saat Dilimi / Açıklama':<35} | {'Hedef Doluluk':<14} | {'Pişen Yemek':<12} | {'İçecek':<8} | {'Churn (Kayıp)':<14} | {'Ort. Bekleme'}")
    print("-" * 105)
    for itv in data.get("interval_summary", []):
        print(f"{itv['description']:<35} | %{int(itv['target_occupancy']*100):<12} | {itv['completed_foods']:<12} | {itv['completed_drinks']:<8} | {itv['churn_count']:<14} | {itv['avg_wait_minutes']:>4.1f} dk")

    print("\n" + "=" * 105)
    print("🍳 İSTASYON TİPİ BAZINDA KUYRUK GECİKMESİ & DOYGUNLUK / EKSİKLİK TEŞHİSİ")
    print("=" * 105)
    print(f"{'İstasyon Tipi':<14} | {'Adet':<5} | {'Kapasite':<8} | {'Ort. Bekleme':<14} | {'% Kilitli':<10} | {'Teşhis (Neden Tıkandı?)'}")
    print("-" * 105)
    for st in data["stage_summary"]:
        if st["station_saturation_percentage"] > st["chef_starvation_percentage"]:
            diagnosis = f"İSTASYON YETERSİZ (%{st['station_saturation_percentage']} Doygun)"
        elif st["chef_starvation_percentage"] > 0:
            diagnosis = f"AŞÇI YETERSİZ (%{st['chef_starvation_percentage']} Boş İstasyon/Aşçı Yok)"
        else:
            diagnosis = "Dengeli"
        print(f"{st['station_type']:<14} | {st['station_count']:<5} | {st['total_capacity']:<8} | {st['avg_queue_wait_minutes']:>4.1f} dk (Maks {st['max_queue_wait_minutes']:>4.1f}) | %{st['blocked_percentage']:<8} | {diagnosis}")

    print("\n" + "=" * 105)
    print("👨‍🍳 AŞÇI İŞ YÜKÜ VE ÇOK AŞAMALI TAŞIMA DETAYLARI")
    print("=" * 105)
    chefs = data.get("staff_summary", {}).get("chefs", [])
    print(f"{'Aşçı ID':<10} | {'% Pişirme (Busy)':<18} | {'% Yürüme (Walk)':<16} | {'% Boşta (Idle)':<15} | {'Toplam Yük (%)':<15} | {'Ara Transfer (Taşıma)'}")
    print("-" * 105)
    for c in chefs:
        print(f"{c['id']:<10} | %{c['busy_percentage']:<16} | %{c['walking_percentage']:<14} | %{c['idle_percentage']:<13} | %{c['total_work_load']:<13} | {c.get('stage_transfers', 0)} defa")

    print("\n" + "=" * 105)
    print("🤵 GARSON İŞ YÜKÜ VE SERVİS / TEMİZLİK / İÇECEK TRANSFERİ DETAYLARI")
    print("=" * 105)
    waiters = data.get("staff_summary", {}).get("waiters", [])
    print(f"{'Garson ID':<10} | {'% Yemek Servisi':<16} | {'% Sipariş Alma':<16} | {'% Temizlik':<12} | {'% Boşta':<9} | {'Toplam Yük':<11} | {'Paket İçecek Transfer'}")
    print("-" * 105)
    for w in waiters:
        print(f"{w['id']:<10} | %{w['deliver_percentage']:<14} | %{w['order_percentage']:<14} | %{w['clean_percentage']:<10} | %{w['idle_percentage']:<7} | %{w['total_work_load']:<9} | {w.get('drink_transfers', 0)} defa")

    print("\n" + "=" * 105)
    print("📦 TESLİMAT TEZGAHLARI, PAKET RAFI VE İÇECEK DOLABI DURUMLARI")
    print("=" * 105)
    for cnt in data.get("counter_summary", []):
        print(f"  • Tezgah: {cnt['id']:<16} (Kapasite: {cnt['capacity']:2d}) -> %{cnt['full_percentage']} Süre Doygun | Ortalama Üzerindeki Sipariş: {cnt['avg_dishes_on_counter']}")

    total_churn = sum(data["churn_breakdown"].values())
    if total_churn > 0:
        print("\n" + "=" * 105)
        print("📉 MÜŞTERİ KAYBI (CHURN) KÖK NEDEN DAĞILIMI")
        print("=" * 105)
        for r, cnt in data["churn_breakdown"].items():
            pct = round((cnt / total_churn) * 100, 1)
            print(f"  • Sebep: {r:<18} -> {cnt:4d} müşteri (%{pct})")

    print("=" * 105)

def save_report(data: dict):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    json_path = os.path.join(RESULTS_DIR, "bottleneck_report.json")
    txt_path = os.path.join(RESULTS_DIR, "bottleneck_detailed_report.txt")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 105 + "\n")
        f.write("RESTORAN DERİN DARBOĞAZ VE SİSTEM PERFORMANS RAPORU (ADR-034 / ADR-038 STANDARDI)\n")
        f.write("=" * 105 + "\n")
        f.write(f"Layout       : {data['layout']} | Zorluk: Seviye {data['difficulty']} | Algoritma: {data['algorithm']} | Süre: {data['days']} Gün\n")
        f.write(f"Genel Hacim  : {data['mean_daily_completed']} sip/gün ({data['mean_daily_foods']} pişen yemek + içecekler) | Churn: {data['mean_daily_churn']} müşteri/gün\n")
        f.write(f"Başarı Skoru : %{data['success_rate']} Yemek Başarısı | %{data['main_dish_success_rate']} Ana Yemek | %{data['appetizer_success_rate']} Aperatif\n")
        f.write(f"Kalite & Süre: %{data['hot_delivery_rate']} Sıcak Teslim | Ort. Bekleme: {data['mean_queue_wait_time']} dk | Ort. Soğuma: {data['mean_food_cold_time']} dk\n\n")

        f.write("=" * 105 + "\n")
        f.write("🚨 EN KRİTİK DARBOĞAZLAR VE ÇÖZÜM REÇETELERİ\n")
        f.write("=" * 105 + "\n")
        for idx, b in enumerate(data["top_bottlenecks"], 1):
            f.write(f"[{idx}] {b['category']}: {b['name']}\n")
            f.write(f"    Ölçülen Metrik : {b['metric']}\n")
            f.write(f"    Sisteme Etkisi : {b['impact']}\n")
            f.write(f"    Kesin Çözüm    : {b['recommendation']}\n\n")

        f.write("=" * 105 + "\n")
        f.write("🍽️ YEMEK BAZLI PERFORMANS, PİŞME VE KAYIP (CHURN) MATRİSİ\n")
        f.write("=" * 105 + "\n")
        f.write(f"{'Yemek Adı':<16} | {'Kategori':<11} | {'Talep':<7} | {'Tamam':<7} | {'Churn':<7} | {'% Başarı':<9} | {'Ort. Bekleme':<13} | {'Ort. Pişme'}\n")
        f.write("-" * 105 + "\n")
        for d in data.get("dish_summary", []):
            cat_tr = {"main_dish": "Ana Yemek", "appetizer": "Aperatif", "beverage": "İçecek"}.get(d["category"], d["category"])
            f.write(f"{d['dish_type']:<16} | {cat_tr:<11} | {d['demand_count']:<7} | {d['completed_count']:<7} | {d['churn_count']:<7} | %{d['success_rate']:<8} | {d['avg_queue_wait_minutes']:>4.1f} dk        | {d['avg_cook_minutes']:>4.1f} dk\n")

        f.write("\n" + "=" * 105 + "\n")
        f.write("⏰ SAAT DİLİMLERİNE GÖRE TALEP YOĞUNLUĞU, TAMAMLANAN VE KAYIP (CHURN) DAĞILIMI\n")
        f.write("=" * 105 + "\n")
        f.write(f"{'Saat Dilimi / Açıklama':<35} | {'Hedef Doluluk':<14} | {'Pişen Yemek':<12} | {'İçecek':<8} | {'Churn (Kayıp)':<14} | {'Ort. Bekleme'}\n")
        f.write("-" * 105 + "\n")
        for itv in data.get("interval_summary", []):
            f.write(f"{itv['description']:<35} | %{int(itv['target_occupancy']*100):<12} | {itv['completed_foods']:<12} | {itv['completed_drinks']:<8} | {itv['churn_count']:<14} | {itv['avg_wait_minutes']:>4.1f} dk\n")

        f.write("\n" + "=" * 105 + "\n")
        f.write("🍳 İSTASYON TİPİ BAZINDA KUYRUK GECİKMESİ & DOYGUNLUK / EKSİKLİK TEŞHİSİ\n")
        f.write("=" * 105 + "\n")
        f.write(f"{'İstasyon Tipi':<14} | {'Adet':<5} | {'Kapasite':<8} | {'Ort. Bekleme':<14} | {'% Kilitli':<10}\n")
        f.write("-" * 105 + "\n")
        for st in data["stage_summary"]:
            f.write(f"{st['station_type']:<14} | {st['station_count']:<5} | {st['total_capacity']:<8} | {st['avg_queue_wait_minutes']:>4.1f} dk (Maks {st['max_queue_wait_minutes']:>4.1f}) | %{st['blocked_percentage']:<8}\n")

        f.write("\n" + "=" * 105 + "\n")
        f.write("👨‍🍳 AŞÇI İŞ YÜKÜ VE ÇOK AŞAMALI TAŞIMA DETAYLARI\n")
        f.write("=" * 105 + "\n")
        chefs = data.get("staff_summary", {}).get("chefs", [])
        f.write(f"{'Aşçı ID':<10} | {'% Pişirme (Busy)':<18} | {'% Yürüme (Walk)':<16} | {'% Boşta (Idle)':<15} | {'Toplam Yük (%)':<15} | {'Ara Transfer (Taşıma)'}\n")
        f.write("-" * 105 + "\n")
        for c in chefs:
            f.write(f"{c['id']:<10} | %{c['busy_percentage']:<16} | %{c['walking_percentage']:<14} | %{c['idle_percentage']:<13} | %{c['total_work_load']:<13} | {c.get('stage_transfers', 0)} defa\n")

        f.write("\n" + "=" * 105 + "\n")
        f.write("🤵 GARSON İŞ YÜKÜ VE SERVİS / TEMİZLİK / İÇECEK TRANSFERİ DETAYLARI\n")
        f.write("=" * 105 + "\n")
        waiters = data.get("staff_summary", {}).get("waiters", [])
        f.write(f"{'Garson ID':<10} | {'% Yemek Servisi':<16} | {'% Sipariş Alma':<16} | {'% Temizlik':<12} | {'% Boşta':<9} | {'Toplam Yük':<11} | {'Paket İçecek Transfer'}\n")
        f.write("-" * 105 + "\n")
        for w in waiters:
            f.write(f"{w['id']:<10} | %{w['deliver_percentage']:<14} | %{w['order_percentage']:<14} | %{w['clean_percentage']:<10} | %{w['idle_percentage']:<7} | %{w['total_work_load']:<9} | {w.get('drink_transfers', 0)} defa\n")

        total_churn = sum(data["churn_breakdown"].values())
        if total_churn > 0:
            f.write("\n" + "=" * 105 + "\n")
            f.write("📉 MÜŞTERİ KAYBI (CHURN) VE YEMEK DAĞILIMI\n")
            f.write("=" * 105 + "\n")
            for r, cnt in data["churn_breakdown"].items():
                f.write(f"  • Sebep: {r} -> {cnt} müşteri\n")
            if data.get("churn_by_dish"):
                f.write("\n  En Çok Kayıp Yaşanan Yemekler:\n")
                for d, cnt in sorted(data["churn_by_dish"].items(), key=lambda x: x[1], reverse=True):
                    f.write(f"    - {d}: {cnt} iptal\n")

    print(f"\n[KAYIT] Detaylı rapor kaydedildi: {txt_path} ve {json_path}")

def main():
    parser = argparse.ArgumentParser(description="Restoran Derin Darboğaz ve Sistem Performans Analiz Aracı")
    parser.add_argument("--layout", type=str, default=None, help="Restoran layout JSON dosyası")
    parser.add_argument("--difficulty", type=int, default=2, help="Zorluk seviyesi (1, 2, 3)")
    parser.add_argument("--days", type=int, default=5, help="Simülasyon gün sayısı")
    parser.add_argument("--algo", type=str, default="FIFO", choices=["FIFO", "SPT", "LPT", "MinPatience"], help="Test algoritması")
    args = parser.parse_args()

    layouts = get_available_layouts()
    layout_path = None

    if args.layout:
        if os.path.isabs(args.layout) and os.path.exists(args.layout):
            layout_path = args.layout
        else:
            for l in layouts:
                if l["filename"] == os.path.basename(args.layout):
                    layout_path = l["path"]
                    break
            if not layout_path:
                layout_path = os.path.join(LAYOUTS_DIR, args.layout)
    else:
        # Interactive layout choice if available
        if layouts:
            print("\n[DARBOĞAZ ANALİZİ] Restoran Düzeni Seçin:")
            for i, l in enumerate(layouts, 1):
                print(f"  [{i}] {l['filename']}")
            try:
                ch = input(f"Seçiminiz [1-{len(layouts)}] (Varsayılan: 1): ").strip()
                idx = int(ch) - 1 if ch.isdigit() else 0
                layout_path = layouts[idx]["path"]
            except Exception:
                layout_path = layouts[0]["path"]
        else:
            layout_path = "config/default_layout.json"

    run_analysis(
        layout_path=layout_path,
        difficulty=args.difficulty,
        days=args.days,
        algo=args.algo
    )

if __name__ == "__main__":
    main()
