import os
import sys
import json
import argparse
import numpy as np
import matplotlib.pyplot as plt

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
DET_JSON_PATH = os.path.join(RESULTS_DIR, "deterministic_results.json")
RL_JSON_PATH = os.path.join(RESULTS_DIR, "rl_results.json")
OUTPUT_PLOT_PATH = os.path.join(RESULTS_DIR, "benchmark_comparison.png")

def load_results():
    data = {}
    if os.path.exists(DET_JSON_PATH):
        try:
            with open(DET_JSON_PATH, "r", encoding="utf-8") as f:
                data["deterministic"] = json.load(f)
        except Exception as e:
            print(f"[WARN] Deterministik sonuçlar okunamadı: {e}")
            
    if os.path.exists(RL_JSON_PATH):
        try:
            with open(RL_JSON_PATH, "r", encoding="utf-8") as f:
                data["rl"] = json.load(f)
        except Exception as e:
            print(f"[WARN] RL sonuçları okunamadı: {e}")
            
    return data

def print_comparison_table(data):
    print("\n" + "=" * 115)
    print(f"{'ALGORİTMA / MODEL GELİŞMİŞ GÜNLÜK BAŞARIM VE KARŞILAŞTIRMA TABLOSU':^115}")
    print("=" * 115)
    header = f"{'Model / Algoritma':<26} | {'Test Süresi':<11} | {'Günlük Sipariş':<16} | {'% Başarı':<10} | {'% Sıcak Teslim':<16} | {'Ort. Bekleme':<14} | {'Yemek Soğuma':<12}"
    print(header)
    print("-" * 115)
    
    rows = []
    
    if "deterministic" in data and "schedulers" in data["deterministic"]:
        det_meta = data["deterministic"].get("benchmark_metadata", {})
        det_days = det_meta.get("days", 50)
        for name, d in data["deterministic"]["schedulers"].items():
            short_name = name.split("(")[0].strip() if "(" in name else name
            days = d.get("total_days", det_days)
            mean_completed = d.get("mean_daily_completed", round(d["total_completed"] / max(1, days), 1))
            mean_churn = d.get("mean_daily_churn", round(d["total_churned"] / max(1, days), 1))
            
            tot_demand = d.get("total_completed", 0) + d.get("total_churned", 0)
            succ_rate = d.get("success_rate", round(d.get("total_completed", 0) / max(1, tot_demand) * 100, 1))
            hot_rate = d.get("hot_delivery_ratio", 0.0)
            
            rows.append({
                "name": short_name,
                "days": days,
                "daily_completed": mean_completed,
                "daily_churn": mean_churn,
                "success_rate": succ_rate,
                "hot_delivery_ratio": hot_rate,
                "wait": d["mean_queue_wait_time"],
                "cold": d["mean_food_cold_time"]
            })
            print(f"{short_name:<26} | {days:2d} Gün     | {mean_completed:6.1f} sip/gün   | %{succ_rate:<8.1f} | %{hot_rate:<14.1f} | {d['mean_queue_wait_time']:<12.2f}dk | {d['mean_food_cold_time']:<10.2f}dk")
            
    if "rl" in data and "rl_agent" in data["rl"]:
        d = data["rl"]["rl_agent"]
        name = "RL Agent (MaskablePPO)"
        days = d.get("total_days", 10)
        mean_completed = d.get("mean_daily_completed", round(d["total_completed"] / max(1, days), 1))
        mean_churn = d.get("mean_daily_churn", round(d["total_churned"] / max(1, days), 1))
        
        tot_demand = d.get("total_completed", 0) + d.get("total_churned", 0)
        succ_rate = d.get("success_rate", round(d.get("total_completed", 0) / max(1, tot_demand) * 100, 1))
        hot_rate = d.get("hot_delivery_ratio", 0.0)
        
        rows.append({
            "name": name,
            "days": days,
            "daily_completed": mean_completed,
            "daily_churn": mean_churn,
            "success_rate": succ_rate,
            "hot_delivery_ratio": hot_rate,
            "wait": d["mean_queue_wait_time"],
            "cold": d["mean_food_cold_time"]
        })
        print(f"{name:<26} | {days:2d} Gün     | {mean_completed:6.1f} sip/gün   | %{succ_rate:<8.1f} | %{hot_rate:<14.1f} | {d['mean_queue_wait_time']:<12.2f}dk | {d['mean_food_cold_time']:<10.2f}dk")
        
    print("=" * 115 + "\n")
    return rows

def generate_comparison_plots(rows, data):
    if not rows:
        print("[WARN] Çizilecek veri bulunamadı.")
        return
        
    names = [r["name"] for r in rows]
    completed = [r["daily_completed"] for r in rows]
    success_rates = [r["success_rate"] for r in rows]
    wait_times = [r["wait"] for r in rows]
    hot_ratios = [r["hot_delivery_ratio"] for r in rows]
    churn = [r["daily_churn"] for r in rows]
    cold_times = [r["cold"] for r in rows]
    
    fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6)) = plt.subplots(3, 2, figsize=(15, 14))
    fig.suptitle("Restoran Optimizasyon Sistemleri - Kapsamlı Karşılaştırma Raporu", fontsize=16, fontweight="bold")
    
    # 1. Günlük Tamamlanan Siparişler
    bars1 = ax1.bar(names, completed, color="#4caf50", width=0.5)
    ax1.set_title("1. Günlük Ort. Tamamlanan Sipariş (Yüksek = İyi)", fontweight="bold")
    ax1.set_ylabel("Sipariş / Gün")
    ax1.grid(axis="y", linestyle="--", alpha=0.7)
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 2, f"{yval:.1f}", ha="center", va="bottom", fontweight="bold")
        
    # 2. Hizmet Başarı Oranı (% Success)
    bars2 = ax2.bar(names, success_rates, color="#009688", width=0.5)
    ax2.set_title("2. Hizmet Başarı Oranı (% - Yüksek = İyi)", fontweight="bold")
    ax2.set_ylabel("Yüzde (%)")
    ax2.set_ylim(0, 100)
    ax2.grid(axis="y", linestyle="--", alpha=0.7)
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2.0, yval + 1, f"%{yval:.1f}", ha="center", va="bottom", fontweight="bold")
        
    # 3. Ortalama Kuyruk Bekleme Süresi
    bars3 = ax3.bar(names, wait_times, color="#2196f3", width=0.5)
    ax3.set_title("3. Ortalama Kuyruk Bekleme Süresi (Düşük = İyi)", fontweight="bold")
    ax3.set_ylabel("Dakika")
    ax3.grid(axis="y", linestyle="--", alpha=0.7)
    for bar in bars3:
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2.0, yval + 0.2, f"{yval:.2f}dk", ha="center", va="bottom", fontweight="bold")
        
    # 4. Sıcak Teslimat Oranı (JIT Başarısı)
    bars4 = ax4.bar(names, hot_ratios, color="#e91e63", width=0.5)
    ax4.set_title("4. Sıcak Teslimat Oranı (% JIT Kalitesi - Yüksek = İyi)", fontweight="bold")
    ax4.set_ylabel("Yüzde (%)")
    ax4.set_ylim(0, 100)
    ax4.grid(axis="y", linestyle="--", alpha=0.7)
    for bar in bars4:
        yval = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2.0, yval + 1, f"%{yval:.1f}", ha="center", va="bottom", fontweight="bold")

    # 5. Günlük Kaybedilen Müşteriler (Churn)
    bars5 = ax5.bar(names, churn, color="#f44336", width=0.5)
    ax5.set_title("5. Günlük Ort. Kaybedilen Müşteri (Düşük = İyi)", fontweight="bold")
    ax5.set_ylabel("Kişi / Gün")
    ax5.grid(axis="y", linestyle="--", alpha=0.7)
    for bar in bars5:
        yval = bar.get_height()
        ax5.text(bar.get_x() + bar.get_width()/2.0, yval + 1, f"{yval:.1f}", ha="center", va="bottom", fontweight="bold")
        
    # 6. Ortalama Yemek Soğuma Süresi
    bars6 = ax6.bar(names, cold_times, color="#ff9800", width=0.5)
    ax6.set_title("6. Ortalama Yemek Soğuma Süresi (Düşük = İyi)", fontweight="bold")
    ax6.set_ylabel("Dakika")
    ax6.grid(axis="y", linestyle="--", alpha=0.7)
    for bar in bars6:
        yval = bar.get_height()
        ax6.text(bar.get_x() + bar.get_width()/2.0, yval + 0.5, f"{yval:.2f}dk", ha="center", va="bottom", fontweight="bold")
        
    plt.tight_layout(rect=[0, 0.02, 1, 0.96])
    os.makedirs(RESULTS_DIR, exist_ok=True)
    plt.savefig(OUTPUT_PLOT_PATH, dpi=200)
    print(f"[GRAFİK] 6 Panelli Kapsamlı Karşılaştırma Grafiği Kaydedildi: {OUTPUT_PLOT_PATH}")

def main():
    parser = argparse.ArgumentParser(description="Restoran Karşılaştırmalı Performans Analizi")
    parser.add_argument("--web", action="store_true", help="Streamlit Web Dashboard arayüzünü başlat")
    args = parser.parse_args()
    
    if args.web:
        print("[WEB] Streamlit Dashboard başlatılıyor...")
        os.system("streamlit run dashboard/app.py")
        return
        
    data = load_results()
    if not data:
        print("[HATA] Henüz hiçbir benchmark sonucu bulunamadı!")
        print("Lütfen önce 'python run_deterministic_test.py' ve 'python run_rl_model.py' komutlarını çalıştırın.")
        return
        
    rows = print_comparison_table(data)
    generate_comparison_plots(rows, data)

if __name__ == "__main__":
    main()
