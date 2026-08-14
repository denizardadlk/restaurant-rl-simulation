import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def main():
    print("=" * 75)
    print("🍽️ YAPAY ZEKA DESTEKLİ RESTORAN SİMÜLASYONU & OPTİMİZASYON SİSTEMİ")
    print("=" * 75)
    print("Kullanabileceğiniz Ana Çalıştırma Komutları:")
    print("  1. python layout_editor.py       -> Harita düzenleyicisini açar (layouts/ kaydı)")
    print("  2. python run_deterministic_test.py -> FIFO, SPT, LPT, MinPatience 100 gün test eder")
    print("  3. python run_rl_training.py     -> RL Modelini (MaskablePPO) eğitir")
    print("  4. python run_rl_model.py        -> Eğitilmiş RL Modelini 100 gün test eder")
    print("  5. python run_simulator.py       -> Canlı 2D Pygame simülasyonunu başlatır")
    print("  6. python compare_models.py      -> Test sonuçlarını grafik ve tablolara döker")
    print("  7. python compare_models.py --web-> Etkileşimli Streamlit Dashboard'u açar")
    print("=" * 75)
    
    # Hızlı demo için simülasyonu 1 gün koştur
    from simulation.engine import SimulationEngine
    
    layout_path = os.path.join(os.path.dirname(__file__), "layouts", "custom_layout.json")
    if not os.path.exists(layout_path):
        layout_path = os.path.join(os.path.dirname(__file__), "layouts", "default_layout.json")
        
    print(f"\n[INFO] Hızlı 1 Günlük Demo Simülasyonu Başlatılıyor (Layout: {os.path.basename(layout_path)})...")
    engine = SimulationEngine(layout_path)
    engine.reset()
    
    for tick in range(1, 1441):
        engine.step()
        
    print(f"[OK] 1 Günlük Simülasyon Tamamlandı! Tamamlanan: {len(engine.completed_orders)}, Churn: {engine.churned_customers}\n")

if __name__ == "__main__":
    main()
