import os
import sys
import time
import pandas as pd
import numpy as np
from simulation.engine import SimulationEngine

def run_long_simulation():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    elif os.path.exists(os.path.join(base_dir, "config", "custom_layout.json")):
        config_path = os.path.join(base_dir, "config", "custom_layout.json")
    else:
        config_path = os.path.join(base_dir, "config", "default_layout.json")

    print("=" * 60)
    print("YAPAY ZEKA DESTEKLI RESTORAN SIMULASYONU UZUN SURELI EGITIMI")
    print("=" * 60)
    print(f"Konfigürasyon: {config_path}")
    
    engine = SimulationEngine(config_path)
    engine.reset()
    
    TOTAL_DAYS = 10
    TICKS_PER_DAY = 1440
    TOTAL_TICKS = TOTAL_DAYS * TICKS_PER_DAY
    
    print(f"Hedef: {TOTAL_DAYS} Gun ({TOTAL_TICKS} adimlik simulasyon)\n")
    
    start_time = time.time()
    
    daily_stats = []
    
    for tick in range(1, TOTAL_TICKS + 1):
        engine.step()
        
        # Gün sonunda istatistikleri topla
        if tick % TICKS_PER_DAY == 0:
            current_day = tick // TICKS_PER_DAY
            
            # Tamamlanan siparişlerdeki tahmin hatalarını hesapla (o gün tamamlananlar)
            completed_so_far = len(engine.completed_orders)
            prev_completed = daily_stats[-1]["total_completed_orders"] if daily_stats else 0
            day_orders = engine.completed_orders[prev_completed:completed_so_far]
            
            if day_orders:
                theoretical_errors = [abs(o.theoretical_time - o.actual_target_time) for o in day_orders if o.actual_target_time]
                predicted_errors = [abs((o.predicted_time if o.predicted_time is not None else o.theoretical_time) - o.actual_target_time) for o in day_orders if o.actual_target_time]
                
                mae_theoretical = np.mean(theoretical_errors) if theoretical_errors else 0.0
                mae_predicted = np.mean(predicted_errors) if predicted_errors else 0.0
            else:
                mae_theoretical, mae_predicted = 0.0, 0.0
                
            trained_status = "EGITILDI (ML Aktif)" if engine.predictor.is_trained else "Cold Start (Teorik)"
            
            print(f"GÜN {current_day:2d} / {TOTAL_DAYS} | "
                  f"Gunluk Siparis: {len(day_orders):3d} (Toplam: {completed_so_far:4d}) | "
                  f"Churn: {engine.churned_customers:2d} | "
                  f"ML Durumu: {trained_status:<22} | "
                  f"Teorik Hata: {mae_theoretical:.2f} dk | "
                  f"ML Hata: {mae_predicted:.2f} dk")
            
            daily_stats.append({
                "day": current_day,
                "total_completed_orders": completed_so_far,
                "total_churned": engine.churned_customers,
                "is_ml_trained": engine.predictor.is_trained,
                "mae_theoretical": mae_theoretical,
                "mae_predicted": mae_predicted
            })

    elapsed_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("10 GÜNLÜK EĞİTİM VE SİMÜLASYON SONUÇ ÖZETİ")
    print("=" * 60)
    print(f"Toplam Calisma Suresi: {elapsed_time:.2f} saniye")
    print(f"Toplam Servis Edilen Siparis: {len(engine.completed_orders)}")
    print(f"Toplam Kaybedilen Musteri (Churn): {engine.churned_customers}")
    print(f"ML Modeli Toplam Veri Sayisi: {engine.predictor.training_count}")
    
    if daily_stats:
        first_day = daily_stats[0]
        last_day = daily_stats[-1]
        print(f"İlk Gün ML Hata Orani (MAE): {first_day['mae_predicted']:.2f} dk")
        print(f"10. Gün ML Hata Orani (MAE): {last_day['mae_predicted']:.2f} dk")
        
        improvement = ((first_day['mae_predicted'] - last_day['mae_predicted']) / first_day['mae_predicted']) * 100 if first_day['mae_predicted'] > 0 else 0
        print(f"Tahmin Basarisi İyilesme Orani: %{improvement:.1f}")

if __name__ == "__main__":
    run_long_simulation()
