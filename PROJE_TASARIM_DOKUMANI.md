# 📄 PROJE_TASARIM_DOKUMANI.md

# Yapay Zeka Destekli Dinamik Restoran Simülasyonu ve Sipariş Optimizasyon Sistemi

## 1. Proje Özeti (Executive Summary)

Bu proje; modüler ve düzenlenebilir bir restoran simülasyon ortamında, mutfak pişirme sürelerinin ampirik (deneyimsel) olarak öğrenilmesi ve bu güncel veriler ışığında sipariş sıralaması ile garson atamalarının **Pekiştirmeli Öğrenme (Reinforcement Learning)** ve **Makine Öğrenmesi (ML)** teknikleriyle optimize edilmesini amaçlayan bir yazılım mimarisidir.

Klasik otomasyon sistemleri sabitleştirilmiş pişirme süreleri ($T_{teorik}$) ve sabit mantık kuralları (FIFO) ile çalışır. Bu projede geliştirilen sistem, simülasyon adımlarından akan gerçek verilerle ($T_{gerçek}$) mutfak şartlarını zamanla öğrenir ve **Just-In-Time (JIT)** hizmet anlayışıyla müşteri bekleme süresini ve yemek soğuma oranını minimuma indirir.

---

## 2. Sistem Mimarisi (System Architecture)

Sistem, yapay zeka eğitim süreçlerini görselleştirmeden bağımsız kılmak ve yüksek performanslı simülasyon adımları ($step/sec$) elde etmek amacıyla **Ayrık Modüler Mimari (Decoupled Architecture)** ile tasarlanmıştır.

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

## 3. Ortam ve Veri Mimarisi (Environment & Data Schema)

### 3.1. Düzenlenebilir Restoran Ortamı (Grid Environment)

* **Boyut:** $N \times M$ hücreli 2D Izgara (Grid).
* **Bileşenler:**
  * **Mutfak İstasyonları (Stations):** Izgara, Ocak, Fırın, Hazırlık Tezgahı (Kapasite kısıtlı).
  * **Mutfak Bölgesi (Kitchen Zone):** Haritada sürükle-bırak ile seçilen dinamik mutfak alanı (`kitchen_zone: {x, y, w, h}`).
  * **Masalar (Tables):** Konum ($x,y$), kapasite (2, 4, 6, 8 kişilik), ızgara boyutları ($w \times h$) ve müşteri sabır katsayısı ($P_{sabır} \in [0, 100]$).
  * **Aktörler:** Aşçılar ($Chef$) ve Garsonlar ($Waiter$).

### 3.2. Sipariş Durum Şeması (JSON Schema)

```json
{
  "order_id": 104,
  "table_id": 5,
  "dish_type": "Pizza_Margherita",
  "theoretical_time": 15.0,
  "predicted_time": 12.8,
  "status": "QUEUED", 
  "timestamps": {
    "created_at": 120,
    "kitchen_start": null,
    "kitchen_finish": null,
    "delivered_at": null
  },
  "assigned_station": "Oven_1",
  "assigned_waiter": "Waiter_2"
}
```

---

## 4. Entegre Yapay Zeka Modelleri

### 🧠 Model 1: Mutfak Pişirme Süresi Tahminleyicisi (Empirical Cook-Time Predictor)

#### Amacı:
Teoride "15 dakika" olarak tanımlanan bir yemeğin; mutfaktaki anlık yoğunluk, kullanılan istasyon ve aşçı yükü göz önüne alındığında gerçekte kaç dakikada pişeceğini ($\hat{T}_{cook}$) hesaplamak.

#### Öğrenme Süreci (10 Simülasyon Günü):
1. **Faz 1 (Gelişim Sezonu / Day 1 - 10):** Sistem başlangıçta $T_{teorik}$ değerini kullanır. Mutfakta aşçı yemeğe başladığı an ($t_{başlangıç}$) ile tamamladığı an ($t_{bitiş}$) arasındaki süre ölçülür:
   $$T_{gerçek} = t_{bitiş} - t_{başlangıç}$$
   Veriler `(Yemek_Tipi, İstasyon_Tipi, Aktif_İstasyon_Sayısı, Toplam_Mutfak_Yükü, T_gerçek)` formatında bir veri havuzuna kaydedilir.
2. **Faz 2 (Model Eğitimi):** 10 günlük veri biriktiğinde **LightGBM / XGBoost Regresyon Modeli** eğitilir.
3. **Öznitelik Vektörü (Feature Vector $X$):**
   * $x_1$: Yemek Türü (One-Hot Encoded)
   * $x_2$: Seçilen İstasyon Kapasite Kullanım Oranı ($\%$)
   * $x_3$: Mutfaktaki Anlık Toplam Aktif Sipariş Sayısı
   * $x_4$: Aşçı Deneyim / Yorgunluk Faktörü
4. **Model Çıktısı ($\hat{Y}$):**
   $$\hat{T}_{cook} = f_{ML}(X)$$

---

### 🧠 Model 2: Akıllı Sipariş Çizelgeleyici & Önceliklendirici (Pekiştirmeli Öğrenme - RL)

#### Amacı:
Model 1'den gelen güncel $\hat{T}_{cook}$ sürelerini kullanarak; hangi siparişin hangi ocağa atanacağını, hangi siparişlerin öne alınacağını veya gruplanacağını (batching) dinamik olarak kararlaştırmak.

#### RL Problem Tanımı (Markov Decision Process - MDP):

* **Durum Uzayı (State Space $S$):**
  * Sipariş Kuyruğundaki Yemeklerin Listesi ve $\hat{T}_{cook}$ Tahminleri
  * Her Masanın Bekleme Süresi ve Kalan Sabır Oranı ($P_{sabır}$)
  * Mutfak İstasyonlarının Doluluk Durumu (Free / Busy, Kalan Süreler)
  * Garsonların Anlık Konumları ve Durumları (`IDLE`, `DELIVERING`)

* **Aksiyon Uzayı (Action Space $A$):**
  * $a_1$: Kuyruktaki $i$. siparişi $j$. istasyona ata.
  * $a_2$: $i$. siparişin önceliğini yükselt (Preempt / Re-order).
  * $a_3$: Aynı tipteki $k$ adet siparişi birleştirerek tek fırında pişir (Batching).
  * $a_4$: Bekle (No-Op).

* **Ödül Fonksiyonu (Reward Function $R$):**
  $$R = - \sum_{i \in Orders} \left( w_1 \cdot t_{wait, i} + w_2 \cdot \max(0, t_{cold, i}) \right) + w_3 \cdot S_{completed} - w_4 \cdot C_{patience\_lost}$$

  * $t_{wait, i}$: Siparişin verilişinden teslime kadar geçen toplam süre.
  * $t_{cold, i}$: Yemeğin tezgahta piştikten sonra garsonu bekleme süresi.
  * $S_{completed}$: Zamanında tamamlanan sipariş bonusu.
  * $C_{patience\_lost}$: Sabrı tükenip restoranı terk eden müşteri cezası.

---

## 5. İş Akışı ve Garson Senkronizasyonu (JIT Waiter Dispatch)

Sistemde yemeklerin tezgahta soğumasını önlemek için **Just-In-Time (JIT)** garson çağırma mekanizması uygulanır.

```text
[Mutfak Pişirme Başlangıcı]
            │
            ▼
   Model 1 Tahmini: T_cook = 12.5 dk
            │
            ▼
   Garson Yürüme Süresi Hesabı (A* Algorithm)
   - Garsonun Mutfak Tezgahına Mesafesi: d_waiter
   - Garson Yürüme Hızı: v_waiter
   - Delta_t_walk = d_waiter / v_waiter  (Örn: 30 saniye)
            │
            ▼
   Tetipleme Zamanı: t_dispatch = T_cook - Delta_t_walk
            │
            ▼
   Süre t_dispatch'e ulaştığında -> Garsona Görev Atanır!
            │
            ▼
   Yemek Hazır Olduğu AN (t_finish) -> Garson Mutfak Tezgahındadır.
```

---

## 6. Teknolojik Stack ve Kütüphaneler

| Katman | Teknoloji / Kütüphane | Kullanım Amacı |
| --- | --- | --- |
| **Dil** | Python 3.10+ | Tüm simülasyon, ML ve RL süreçleri |
| **Simülasyon Çekirdeği** | `SimPy` veya Custom Tick-Engine | Ayrık olay ve adım tabanlı zaman yönetimi |
| **Yol Bulma & Graf** | `NetworkX` | A* algoritması ve masa-mutfak mesafe matrisi |
| **Model 1 (ML)** | `LightGBM` / `XGBoost` / `scikit-learn` | Mutfak pişirme süresi regresyon modeli |
| **Model 2 (RL)** | `Gymnasium` + `Stable-Baselines3` | Custom Gym Environment ve PPO/DQN Ajanı |
| **Layout Düzenleyici** | HTML5 Canvas, Vanilla JS/CSS, Python `http.server` | Sürükle-bırak interaktif restoran mimarisi düzenleyici |
| **Görselleştirme** | `Pygame` veya `Godot Engine 2D` | Izgara üstü 2D simülasyon gösterimi |
| **Veri Analizi** | `Pandas`, `Matplotlib`, `Streamlit` | 10 günlük performans ve verimlilik grafikleri |

---

## 7. Proje Geliştirme Yol Haritası (Implementation Roadmap)

### Faz 1: Simülasyon Çekirdeği ve Grid Yapısı (Hafta 1 - 3)
* [x] $N \times M$ Grid restoran ortamının kodlanması.
* [x] Masa, Garson, Aşçı ve Mutfak İstasyon sınıflarının oluşturulması.
* [x] A* yol bulma algoritması ile mesafe matrisinin çıkarılması.

### Faz 2: Veri Toplama & Model 1 Entegrasyonu (Hafta 4 - 6)
* [x] Mutfak başlama-bitiş sürelerini kaydeden zamanlayıcı yapısının kurulması.
* [x] 10 günlük simülasyon koşturularak ampirik veri kümesinin oluşturulması.
* [x] LightGBM modelinin eğitilmesi ve $T_{teorik} \rightarrow \hat{T}_{cook}$ dönüşümünün sağlanması.

### Faz 3: Gymnasium Environment & Model 2 (RL) Eğitimi (Hafta 7 - 10)
* [x] Simülasyonun `Gymnasium.Env` arabirimine dönüştürülmesi (`reset`, `step`, `reward`).
* [x] Stable-Baselines3 (PPO) ile RL ajanının eğitilmesi.
* [x] Base-line algoritmalar (FIFO, SPT) ile RL ajanının performans karşılaştırması.

### Faz 4: JIT Garson Çağrısı ve Arayüz/Sunum Hazırlığı (Hafta 11 - 12)
* [x] Just-In-Time garson çağırma metriğinin sisteme eklenmesi.
* [x] Pygame / Streamlit arayüzü ile simülasyonun canlı görselleştirilmesi.
* [x] Proje raporu ve akademik sunumun hazırlanması.

### Faz 5: Web Tabanlı Dinamik Layout Düzenleyici (Layout Editor)
* [x] HTML5 Canvas + JS yerleşim düzenleyicisinin kodlanması.
* [x] Sürükle-bırak mutfak alanı seçimi, çoklu hücre masa boyutları (1x1, 2x1, 2x2, 3x2) ve renkli sandalye göstergeleri.
* [x] Sağ tık ve 'R' kısayolu ile masada 90° yerinde (in-place) döndürme desteği.
* [x] REST API sunucusu (`run_layout_editor.py`) ve `config/custom_layout.json` entegrasyonu.
