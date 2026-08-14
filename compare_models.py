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
    print("\n" + "=" * 95)
    print(f"{'ALGORİTMA / MODEL KARŞILAŞTIRMA TABLOSU':^95}")
    print("=" * 95)
    header = f"{'Model / Algoritma':<28} | {'Tamamlanan':<12} | {'Churn (Kayıp)':<14} | {'Ort. Bekleme':<14} | {'Yemek Soğuma':<12}"
    print(header)
    print("-" * 95)
    
    rows = []
    
    if "deterministic" in data and "schedulers" in data["deterministic"]:
        for name, d in data["deterministic"]["schedulers"].items():
            short_name = name.split("(")[0].strip() if "(" in name else name
            rows.append({
                "name": short_name,
                "completed": d["total_completed"],
                "churn": d["total_churned"],
                "wait": d["mean_queue_wait_time"],
                "cold": d["mean_food_cold_time"]
            })
            print(f"{short_name:<28} | {d['total_completed']:<12d} | {d['total_churned']:<14d} | {d['mean_queue_wait_time']:<12.2f}dk | {d['mean_food_cold_time']:<10.2f}dk")
            
    if "rl" in data and "rl_agent" in data["rl"]:
        d = data["rl"]["rl_agent"]
        name = "RL Agent (MaskablePPO)"
        rows.append({
            "name": name,
            "completed": d["total_completed"],
            "churn": d["total_churned"],
            "wait": d["mean_queue_wait_time"],
            "cold": d["mean_food_cold_time"]
        })
        print(f"{name:<28} | {d['total_completed']:<12d} | {d['total_churned']:<14d} | {d['mean_queue_wait_time']:<12.2f}dk | {d['mean_food_cold_time']:<10.2f}dk")
        
    print("=" * 95 + "\n")
    return rows

def generate_comparison_plots(rows, data):
    if not rows:
        print("[WARN] Çizilecek veri bulunamadı.")
        return
        
    names = [r["name"] for r in rows]
    completed = [r["completed"] for r in rows]
    churn = [r["churn"] for r in rows]
    wait_times = [r["wait"] for r in rows]
    cold_times = [r["cold"] for r in rows]
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Restoran Optimizasyon Sistemleri - Model Karşılaştırma Raporu", fontsize=16, fontweight="bold")
    
    # 1. Tamamlanan Siparişler
    bars1 = ax1.bar(names, completed, color="#4caf50", width=0.5)
    ax1.set_title("Toplam Tamamlanan Sipariş (Yüksek = İyi)", fontweight="bold")
    ax1.set_ylabel("Sipariş Sayısı")
    ax1.grid(axis="y", linestyle="--", alpha=0.7)
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 1, f"{int(yval)}", ha="center", va="bottom", fontweight="bold")
        
    # 2. Kaybedilen Müşteriler (Churn)
    bars2 = ax2.bar(names, churn, color="#f44336", width=0.5)
    ax2.set_title("Toplam Kaybedilen Müşteri (Düşük = İyi)", fontweight="bold")
    ax2.set_ylabel("Müşteri Sayısı")
    ax2.grid(axis="y", linestyle="--", alpha=0.7)
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2.0, yval + 1, f"{int(yval)}", ha="center", va="bottom", fontweight="bold")
        
    # 3. Ortalama Bekleme Süresi
    bars3 = ax3.bar(names, wait_times, color="#2196f3", width=0.5)
    ax3.set_title("Ortalama Kuyruk Bekleme Süresi (dk)", fontweight="bold")
    ax3.set_ylabel("Dakika")
    ax3.grid(axis="y", linestyle="--", alpha=0.7)
    for bar in bars3:
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2.0, yval + 0.1, f"{yval:.1f} dk", ha="center", va="bottom", fontweight="bold")
        
    # 4. Ortalama Yemek Soğuma Süresi (JIT Metriği)
    bars4 = ax4.bar(names, cold_times, color="#ff9800", width=0.5)
    ax4.set_title("Ortalama Tezgahta Soğuma Süresi (dk - Düşük = İyi)", fontweight="bold")
    ax4.set_ylabel("Dakika")
    ax4.grid(axis="y", linestyle="--", alpha=0.7)
    for bar in bars4:
        yval = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2.0, yval + 0.05, f"{yval:.2f} dk", ha="center", va="bottom", fontweight="bold")
        
    plt.tight_layout()
    plt.savefig(OUTPUT_PLOT_PATH, dpi=300)
    print(f"[GRAFİK] Karşılaştırma grafiği kaydedildi: {OUTPUT_PLOT_PATH}")

def launch_web_dashboard():
    dashboard_script = os.path.join(BASE_DIR, "dashboard.py")
    if os.path.exists(dashboard_script):
        print("\n[WEB] Streamlit Dashboard başlatılıyor...")
        os.system(f"streamlit run {dashboard_script}")
    else:
        print("[HATA] dashboard.py bulunamadı.")

def main():
    parser = argparse.ArgumentParser(description="Restoran Simülasyonu Model ve Algoritma Karşılaştırma Aracı")
    parser.add_argument("--web", action="store_true", help="Etkileşimli Streamlit Dashboard'u başlat")
    args = parser.parse_args()
    
    if args.web:
        launch_web_dashboard()
        return
        
    data = load_results()
    if not data:
        print("[!] Henüz kayıtlı bir test sonucu bulunamadı (results/ dizini boş).")
        print("Lütfen önce aşağıdaki testlerden birini çalıştırın:")
        print("  1. python run_deterministic_test.py")
        print("  2. python run_rl_model.py")
        return
        
    rows = print_comparison_table(data)
    generate_comparison_plots(rows, data)

if __name__ == "__main__":
    main()
