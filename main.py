import os
from simulation.engine import SimulationEngine

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(base_dir, "config", "custom_layout.json")):
        config_path = os.path.join(base_dir, "config", "custom_layout.json")
    else:
        config_path = os.path.join(base_dir, "config", "default_layout.json")
    print("Yapay Zeka Destekli Dinamik Restoran Simülasyonu başlatılıyor...")
    print(f"Konfigürasyon Yolu: {config_path}")
    
    engine = SimulationEngine(config_path)
    engine.reset()
    
    SIMULATION_TICKS = 1440  # 1 gün (dakika bazında)
    
    print(f"\n[INFO] {SIMULATION_TICKS} tick (1 gün) simülasyon koşturuluyor...\n")
    
    for tick in range(1, SIMULATION_TICKS + 1):
        engine.step()
        
        # Sadece peak saatlerde veya 100 adımda bir ufak bilgi yazdır
        if tick % 100 == 0:
            print(f"--- Tick: {tick} ---")
            print(f"Kuyruktaki Siparişler: {len(engine.order_queue)}")
            print(f"Tamamlanan Siparişler: {len(engine.completed_orders)}")
            print(f"Kaybedilen (Churned) Müşteriler: {engine.churned_customers}")
            
    print("\n--- GÜN SONU ÖZETİ ---")
    print(f"Toplam Tamamlanan Sipariş: {len(engine.completed_orders)}")
    print(f"Toplam Kaybedilen Müşteri (Sabrı Tükenen): {engine.churned_customers}")
    print("Simülasyon Çekirdeği (Faz 1) Başarıyla Çalıştı!")

if __name__ == "__main__":
    main()
