# Persistent Project Memory & ADRs (MEMORY.md)

> [!IMPORTANT]
> Bu belge **Yapay Zeka Destekli Dinamik Restoran Simülasyonu ve Sipariş Optimizasyon Sistemi** projesinin kalıcı hafızasıdır. Alınan Mimari Karar Kayıtları (ADR), domain iş kuralları ve teknoloji tercihleri burada tutulur.

---

## 1. Mimari Karar Kayıtları (ADR - Architectural Decision Records)

### ADR-001: Görselleştirmeden Ayrılmış Modüler Mimari (Decoupled Architecture)
- **Tarih**: 2026-08-11
- **Durum**: Accepted
- **Bağlam**: Pekiştirmeli öğrenme (RL) ajanlarının eğitimi saniyede binlerce simülasyon adımı ($step/sec$) gerektirir. Görsel render (Pygame/Godot) ile simülasyon mantığı iç içe geçerse eğitim hızı dramatik şekilde düşer.
- **Karar**: Simülasyon çekirdeği (`SimPy`/Custom Tick Engine) ve Gymnasium arayüzü görselleştirmeden tamamen bağımsız kılınacaktır. Pygame veya Streamlit arayüzleri sadece durum güncellemelerini dinleyen ayrı katmanlar olarak çalışacaktır.
- **Sonuçlar**: RL eğitimi headless modda yüksek hızda gerçekleştirilebilir, arayüz istendiğinde takılıp çıkarılabilir.

### ADR-002: Çift Aşamalı Hibrit Yapay Zeka Mimarisi (Phase 1 ML + Phase 2 RL)
- **Tarih**: 2026-08-11
- **Durum**: Accepted
- **Bağlam**: Teorik pişirme süreleri ($T_{teorik}$) mutfaktaki anlık yoğunluğu ve aşçı yükünü yansıtmaz. Doğrudan RL ajanı eğitmek, mutfak süreleri dinamik olduğu için stabilite kaybına yol açar.
- **Karar**:
  1. **Model 1 (ML):** İlk 10 günlük simülasyon verisi toplanarak `LightGBM` regresyon modeli eğitilecek ve ampirik pişirme süresi tahmini ($\hat{T}_{cook}$) elde edilecektir.
  2. **Model 2 (RL):** RL ajanı (PPO/DQN), Model 1'in ürettiği güncel $\hat{T}_{cook}$ tahminlerini durum (state) bilgisi olarak kullanarak sipariş önceliklendirme ve istasyon ataması yapacaktır.
- **Sonuçlar**: RL ajanı daha doğru zaman tahminleriyle kararlar alır, mutfak gecikmelerine karşı dirençli hale gelir.

### ADR-003: Just-In-Time (JIT) Garson Çağırma ve A* Yol Bulma Entegrasyonu
- **Tarih**: 2026-08-11
- **Durum**: Accepted
- **Bağlam**: Yemek piştikten sonra garson çağrılırsa yemek tezgahta bekler ve soğur ($t_{cold}$).
- **Karar**: Garsonun mutfak tezgahına olan A* yürüme süresi ($\Delta t_{walk} = d / v$) hesaplanarak garson tetikleme zamanı $t_{dispatch} = T_{cook} - \Delta t_{walk}$ formülü ile öne çekilecektir.
- **Sonuçlar**: Yemek piştiği an garson tezgahta hazır olur, soğuma süresi ve müşteri memnuniyetsizliği minimuma iner.

### ADR-004: Web Tabanlı Dinamik Layout Düzenleyici ve Çoklu Hücre Masa Şeması
- **Tarih**: 2026-08-11
- **Durum**: Accepted
- **Bağlam**: Restoran masaları, mutfak alanı ve personel sayılarının `default_layout.json` dosyasında elle girilmesi zor ve kısıtlayıcıdır. Kullanıcının sürükle-bırak yöntemiyle harita üzerinde masa boyutlarını (1x1, 2x1, 2x2, 3x2), sandalyeleri, mutfak alanını ve döndürme açılarını görsel olarak ayarlayabilmesi gerekmektedir.
- **Karar**:
  1. `layout_editor.html`, `layout_editor.js` ve `layout_editor.css` ile HTML5 Canvas + Vanilla JS tabanlı görsel layout düzenleyici geliştirilmiştir.
  2. Yerel Python HTTP sunucusu (`run_layout_editor.py`, port 8080) üzerinden POST `/save_layout` endpoint'i ile üretilen düzen `config/custom_layout.json` dosyasına yazılır.
  3. JSON şemasına `kitchen_zone` ve masalar için `w` (genişlik) ile `h` (yükseklik) hücre boyutları eklenmiştir. `Table` ve `RestaurantGrid` sınıfları çoklu hücre engellerini kapsayacak şekilde güncellenmiştir.
- **Sonuçlar**: Kullanıcı istediği büyüklükte ve yönde masalar oluşturabilir, mutfağı seçebilir ve doğrudan simülasyona aktarabilir.

### ADR-005: Çoklu Sipariş Üretim Modeli ve Otomatik Layout Algılama Mimarisi
- **Tarih**: 2026-08-12
- **Durum**: Accepted
- **Bağlam**: Masaya tek bir sipariş atanması gerçekçi restoran dinamiklerini yansıtmaz. Her müşterinin bağımsız sipariş vermesi mutfakta eşzamanlı yük oluşturur. Ayrıca kullanıcı tarafından oluşturulan `config/custom_layout.json` düzeninin tüm simülasyon ve görselleştirme araçlarınca otomatik algılanması gerekmektedir.
- **Karar**:
  1. `OrderGenerator`: Masaya grup oturduğunda `table.capacity` adet bağımsız sipariş nesnesi aynı anda üretilir.
  2. Tüm betikler (`gui_pygame.py`, `dashboard.py`, `run_long_simulation.py`, `run_rl_training.py`) varsa `config/custom_layout.json` dosyasını otomatik algılayıp varsayılan olarak seçer.
### ADR-007: Betik Konsolidasyonu ve 6 Standart Giriş Noktası
- **Tarih**: 2026-08-14
- **Durum**: Accepted
- **Bağlam**: Projede çok sayıda dağınık betik mevcuttu. Kullanıcının iş akışını standartlaştırmak için 6 ana giriş noktası tanımlanması kararlaştırıldı.
- **Karar**:
  1. `layout_editor.py` -> Port 8080 harita düzenleyici (`layouts/` kaydı).
  2. `run_deterministic_test.py` -> FIFO, SPT, LPT, MinPatience 100 gün benchmark.
  3. `run_rl_training.py` -> İnteraktif RL eğitimi ve fine-tuning.
  4. `run_rl_model.py` -> 100 gün RL benchmark testi.
  5. `run_simulator.py` -> Canlı 2D Pygame simülasyonu.
  6. `compare_models.py` -> Raporlama, metin tablosu, PNG grafik ve `--web` Streamlit paneli.

### ADR-008: Gymnasium Observation Önbellekleme ve Simülasyon Hızlandırması
- **Tarih**: 2026-08-14
- **Durum**: Accepted
- **Bağlam**: `RestaurantGymEnv._get_obs()` içinde her tickte 15 kez çağrılan `pd.DataFrame` ve LightGBM `predict` çağrıları simülasyon hızını 15 FPS'e düşürmekteydi.
- **Karar**: Siparişlerin tahmini pişirme süreleri ve ceza metrikleri önbelleğe alındı. Ham simülasyon hızı 22.000+ FPS'e, MaskablePPO rollout hızı ise 200+ FPS'e çıkarıldı. 2 günlük RL eğitimi 16 saniyede tamamlanabilir hale geldi.

### ADR-009: LightGBM Eğitilme Sıklığı ve Disk I/O Optimizasyonu
- **Tarih**: 2026-08-14
- **Durum**: Accepted
- **Bağlam**: Simülasyonda her 50 tamamlanan siparişte bir LightGBM modelinin kümülatif veriyle baştan eğitilmesi (`fit`) ve her seferinde diske kaydedilmesi RL eğitiminde gereksiz CPU ve disk I/O darboğazı yaratmaktaydı.
- **Karar**:
  1. `kitchen.py` içindeki yeniden eğitilme sıklığı kademelendirildi: İlk 200 siparişte ısınma için 50'de bir, ardından her 200 siparişte bir (2000 sipariş sonrası 1000'de bir) eğitilecek şekilde ayarlandı.
  2. Periyodik adımlarda gereksiz `pickle.dump` disk yazımı engellendi (`auto_save=False`).
  3. `LGBMRegressor` parametreleri `n_estimators=50`, `learning_rate=0.08`, `min_child_samples=5`, `verbosity=-1` ve `force_col_wise=True` ile optimize edilerek hem log kirliliği önlendi hem de fit süresi hızlandırıldı.
- **Sonuçlar**: RL eğitim adımları LightGBM fitting beklemesi olmadan çok daha akıcı ve hızlı ilerler.

---


## 2. Proje Domain Kuralları & Sözleşmeler

1. **Restoran Izgarası (Grid):** Ortam $N \times M$ boyutlu 2D grid üzerindedir. Mutfak istasyonları (Izgara, Fırın, Ocak, Hazırlık), masalar, aşçılar ve garsonlar grid hücrelerini kaplar.
2. **Çoklu Hücre Masalar:** 2 kişilik (1x1), 4 kişilik (2x1 / 1x2), 6 kişilik (2x2), 8 kişilik (3x2 / 2x3) masalar $w \times h$ hücre işgal eder.
3. **Müşteri Sabır Katsayısı:** Her masanın anlık sabır değeri $P_{sabır} \in [0, 100]$ arasındadır. Bekleme süresi arttıkça düşer; 0 olduğunda müşteri restoranı terk eder ($C_{patience\_lost}$ cezası).
4. **Sipariş Yaşam Döngüsü & Geçişleri:**
   `QUEUED` ➔ `PREPARING` ➔ `READY` ➔ `DELIVERING` ➔ `SERVED`
5. **RL Ödül Fonksiyonu Dengesi:**
   $$R = - \sum_{i \in Orders} \left( w_1 \cdot t_{wait, i} + w_2 \cdot \max(0, t_{cold, i}) \right) + w_3 \cdot S_{completed} - w_4 \cdot C_{patience\_lost}$$

---

## 3. Teknoloji Stack & Kullanılan Kütüphaneler

- **Core Simülasyon**: Python 3.10+, `SimPy` (veya Custom Tick Loop Engine)
- **Graf & Yol Bulma**: `NetworkX` (A* Algoritması)
- **Model 1 (ML - Tahminleyici)**: `LightGBM`, `XGBoost`, `scikit-learn`
- **Model 2 (RL - Çizelgeleyici)**: `Gymnasium`, `Stable-Baselines3` (PPO / DQN)
- **Görselleştirme & Dashboard**: `Pygame`, `Streamlit`, `Matplotlib`, `Plotly`
- **Layout Düzenleyici (Editor)**: HTML5 Canvas, Vanilla JS/CSS3, Python `http.server` (Port 8080)

---

## 4. Öğrenilen Dersler & Mevcut Sorunlar / Riskler (Troubleshooting & Known Issues)

- **A* Matris Ön-Hesaplaması (Pre-computation):** Her simülasyon adımında A* çalıştırmak performansı düşürebilir. Grid sabit kaldığı sürece tüm masa-mutfak mesafe matrisinin simülasyon başında bir kez hesaplanıp önbelleğe alınması (caching) performansı ciddi oranda artırır.
- **[KRİTİK - SORUN 1] Sunucu Bağlantısı / Port Çakışması ("Sunucuya Bağlanılamadı"):**
  - **Neden:** Layout Düzenleyicide *"Projeye Kaydet"* butonuna basıldığında `/save_layout` endpoint'ine POST isteği atılır. Eğer arka planda `python run_layout_editor.py` betiği çalışmıyorsa veya 8080 portu başka bir uygulama tarafından işgal edilmişse tarayıcı uyarı verir.
  - **Çözüm:** Arka planda `python run_layout_editor.py` komutunun açık olduğundan emin olunmalıdır.
- **[SORUN 2] Tarayıcı Önbelleği (Browser Cache):**
  - **Neden:** `layout_editor.js` veya `layout_editor.css` dosyalarında yapılan güncellemeler tarayıcı önbelleği (cache) sebebiyle eski sürümde kalabilir ve döndürme ('R' / sağ tık) veya masa ekleme adımları yanıt vermeyebilir.
  - **Çözüm:** Sayfada `Ctrl + F5` veya `Ctrl + Shift + R` ile tam yenileme yapılmalıdır.
- **[SORUN 3] Sınır Aşımı ve Çakışan Döndürmeler:**
  - **Neden:** Haritanın en sağında veya mutfak alanına sıfır masalar döndürülmek istendiğinde (örneğin 2x1 masayı 1x2 dikey yapmak) harita dışına taşma veya mutfakla çakışma oluşur.
  - **Çözüm:** Uygulama çakışmayı engeller ve uyarı verir. Masanın etrafında döndürme için boş hücre bulunmalıdır.
