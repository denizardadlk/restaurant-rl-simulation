# 🍽️ Yapay Zeka Destekli Dinamik Restoran Simülasyonu ve Sipariş Optimizasyon Sistemi

Modüler ve düzenlenebilir bir restoran simülasyon ortamında; mutfak pişirme sürelerinin ampirik (deneyimsel) olarak öğrenilmesi, sipariş sıralamasının **Pekiştirmeli Öğrenme (Reinforcement Learning)** ile optimize edilmesi ve garson atamalarının **Just-In-Time (JIT)** prensibiyle gerçekleştirilmesini sağlayan yapay zeka destekli yazılım mimarisi.

---

## 📌 Proje Hakkında

Klasik restoran otomasyon sistemleri sabit pişirme süreleri ($T_{teorik}$) ve basit FIFO (İlk Gelen İlk İşlenir) mantığıyla çalışır. Bu yaklaşım mutfaktaki anlık yoğunlukları, aşçı yorgunluğunu ve tezgahta yemeklerin soğumasını hesaba katamaz.

Bu projede geliştirilen sistem, simülasyon adımlarından akan ampirik verilerle ($T_{gerçek}$) mutfak şartlarını zamanla öğrenir ve **Just-In-Time (JIT)** servis mantığı ile müşteri bekleme sürelerini ve yemek soğuma oranını minimuma indirir.

---

## 🏗️ Sistem Mimarisi (Decoupled Architecture)

Sistem, yapay zeka eğitim süreçlerini görselleştirmeden bağımsız kılmak ve yüksek performanslı simülasyon adımları ($step/sec$) elde etmek amacıyla **Ayrık Modüler Mimari** ile tasarlanmıştır.

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        1. SIMULATION CORE                              │
│  - Grid & Environment Configurator (Kitchen, Tables, Stations)         │
│  - Event / Tick Loop Manager                                           │
│  - A* Pathfinding & Distance Matrix Engine                             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (State Update / Events)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        2. DATA & LEARNING LAYER                        │
│  - Cook Time Recorder (Empirical Data Collector)                       │
│  - Model 1: Kitchen Cook-Time Predictor (LightGBM / XGBoost)           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Updated Cook Time Predictions: T_est)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        3. AI SCHEDULER LAYER                           │
│  - Gymnasium Environment Wrapper                                       │
│  - Model 2: Order & Resource Scheduler (RL Agent - PPO/DQN)            │
│  - Just-In-Time (JIT) Waiter Dispatcher                                │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Actions: Re-order, Station Assign)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     4. VISUALIZATION & ANALYTICS                       │
│  - 2D Grid Render Engine (Pygame / Godot 2D Engine)                    │
│  - Real-Time Analytics Dashboard (Streamlit / Plotly)                  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🧠 Entegre Yapay Zeka Modelleri

1. **Model 1: Mutfak Pişirme Süresi Tahminleyicisi (Empirical Cook-Time Predictor)**
   * **Teknoloji:** `LightGBM` / `XGBoost` Regresyon
   * **Görevi:** 10 günlük simülasyon çıktılarından elde edilen verilerle mutfaktaki anlık yoğunluk, aşçı durumu ve istasyon kapasitesine göre gerçek pişirme süresini ($\hat{T}_{cook}$) tahmin eder.

2. **Model 2: Akıllı Sipariş Çizelgeleyici & Önceliklendirici (RL Agent)**
   * **Teknoloji:** `Gymnasium` + `Stable-Baselines3` (PPO / DQN)
   * **Görevi:** Sipariş kuyruğunu dinamik olarak önceliklendirir, yemekleri istasyonlara atar ve toplu pişirme (batching) kararları alır.

3. **JIT Garson Çağırma Mekanizması**
   * **Teknoloji:** `NetworkX` A* Yol Bulma Algoritması
   * **Görevi:** Yemeğin bitiş süresi ile garsonun masaya/tezgaha ulaşma süresini senkronize eder ($t_{dispatch} = T_{cook} - \Delta t_{walk}$), yemeğin tezgahta soğumasını önler.

---

## 🛠️ Teknolojik Stack

| Katman | Teknoloji / Kütüphane | Kullanım Amacı |
| --- | --- | --- |
| **Dil** | Python 3.10+ | Tüm simülasyon, ML ve RL süreçleri |
| **Simülasyon Çekirdeği** | `SimPy` veya Custom Tick Engine | Ayrık olay ve zaman adımı yönetimi |
| **Yol Bulma & Graf** | `NetworkX` | A* algoritması ve mesafe matrisi |
| **Model 1 (ML)** | `LightGBM` / `XGBoost` | Mutfak pişirme süresi tahmini |
| **Model 2 (RL)** | `Gymnasium` + `Stable-Baselines3` | Custom Gym Env & PPO/DQN Ajanı |
| **Görselleştirme** | `Pygame` / `Streamlit` | 2D Izgara görselleştirme & Analitik Dashboard |

---

## 🚀 Kurulum ve Başlangıç

### Gereksinimler
- Python 3.10 veya üzeri
- `pip` paket yöneticisi

### Adımlar

1. **Depoyu Klonlayın veya Klasöre Gidin:**
   ```bash
   cd "c:/kod/Bitirme Projesi"
   ```

2. **Sanal Ortam Oluşturun ve Aktifleştirin:**
   ```bash
   python -m venv venv
   # Windows PowerShell:
   .\venv\Scripts\Activate.ps1
   ```

3. **Bağımlılıkları Yükleyin:**
   ```bash
   pip install simpy networkx lightgbm xgboost gymnasium stable-baselines3 pygame streamlit matplotlib pandas plotly
   ```

4. **Standart Çalıştırma Komutları:**
   ```bash
   # 1. Web Tabanlı İnteraktif Layout Düzenleyici (Port 8080 - layouts/ kaydı):
   python layout_editor.py
   
   # 2. Deterministik Algoritmalar 100 Gün Benchmark Testi (FIFO, SPT, LPT, MinPatience):
   python run_deterministic_test.py --days 100
   
   # 3. Pekiştirmeli Öğrenme (RL - MaskablePPO) Eğitimi & Fine-Tuning (Çoklu Çekirdek Destekli):
   python run_rl_training.py --num-envs 4
   
   # 4. Eğitilmiş RL Modelini 100 Gün Test Etme:
   python run_rl_model.py --days 100
   
   # 5. Canlı 2D Pygame Simülasyon Arayüzü:
   python run_simulator.py --mode rl
   
   # 6. Model Karşılaştırma Grafiği & Tablosu / Web Dashboard:
   python compare_models.py
   python compare_models.py --web
   ```

---

## 🛠️ İnteraktif Layout Düzenleyici (Layout Editor)

Kendi restoran düzeninizi görsel olarak tasarlamak için:
1. Terminalde `python layout_editor.py` çalıştırın.
2. Tarayıcınızda otomatik açılan **http://localhost:8080/layout_editor.html** adresine gidin.
3. Fare ile mutfak alanını sürükleyerek seçin, 2-8 kişilik masalar ekleyin (Sağ tık veya **'R'** tuşu ile masayı yerinde 90° döndürün).
4. **"Projeye Kaydet"** butonuna basarak düzeninizi `layouts/custom_layout.json` dosyasına kaydedin.

### ❓ Sık Karşılaşılan Sorunlar ve Çözümleri (Troubleshooting)
- **"Sunucuya bağlanılamadı" / Projeye Kaydedilemiyor:** Arka planda `python layout_editor.py` betiğinin çalıştığından emin olun (Port 8080).
- **Sayfada Döndürme ('R' / Sağ tık) Çalışmıyor:** Tarayıcı önbelleğini temizlemek için `Ctrl + F5` ile sayfayı sert yenileyin.

---

## 🗺️ Geliştirme Yol Haritası (Implementation Roadmap)

- [x] **Faz 1: Simülasyon Çekirdeği ve Grid Yapısı (Hafta 1 - 3)**
  - $N \times M$ Restoran izgarası, masa, aşçı, garson ve istasyon sınıfları, A* yol bulma.
- [x] **Faz 2: Veri Toplama & Model 1 Entegrasyonu (Hafta 4 - 6)**
  - Ampirik veri kayıtlayıcı, 10 günlük simülasyon veri havuzu, LightGBM regresyon modeli.
- [x] **Faz 3: Gymnasium Environment & Model 2 (RL) Eğitimi (Hafta 7 - 10)**
  - Gym Env sarmalayıcısı (`reset`, `step`, `reward`), PPO ajanı eğitimi, FIFO/SPT karşılaştırması.
- [x] **Faz 4: JIT Garson Çağrısı ve Arayüz/Sunum (Hafta 11 - 12)**
  - JIT garson çağırma zamanlaması, Pygame/Streamlit canlı görselleştirme ve raporlama.
- [x] **Faz 5: Web Tabanlı Layout Düzenleyici (HTML5 Canvas & Python Server)**
  - Sürükle-bırak mutfak seçimi, çoklu hücre masa boyutları (1x1, 2x1, 2x2, 3x2), renkli sandalye göstergeleri ve in-place 90° masa döndürme.

---

## 📄 Lisans ve Dokümantasyon

Ayrıntılı teknik şartname ve mimari detaylar için [`PROJE_TASARIM_DOKUMANI.md`](file:///c:/kod/Bitirme%20Projesi/PROJE_TASARIM_DOKUMANI.md) belgesini inceleyebilirsiniz.
