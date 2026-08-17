# 🚀 Uzun Süreli RL Eğitimi (Long Train) Canlı İlerleme Raporu

**Tarih:** 2026-08-16 15:24:37 | **Harita:** `Büyük_restoran.json` | **Zorluk:** Seviye 3

**Döngü Yapısı:** 50 Gün Eğitim (72.000 Adım) $\to$ 10 Gün Test (14.400 Adım) $\to$ Early Stopping (Patience: 3)

**En İyi Model:** 🏆 **Döngü 1** (Skor / Günlük Ödül: `-2440.29`)

---

## 📊 İterasyon Geçmişi ve Doğrulama Tablosu

| Döngü | Kümülatif Gün | Eğitim Süresi | Günlük Tamamlanan | Günlük Churn | Ort. Bekleme | Ort. Soğuma | Günlük Ödül (Skor) | Durum / Patience |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Döngü 1** | 50 Gün | 580.0sn | 338.9 sip/gün | 94.0 kişi/gün | 4.53 dk | 52.23 dk | `-2440.29` | 🏆 YENİ EN İYİ (Skor: -2440.29) |
| **Döngü 2** | 100 Gün | 578.5sn | 320.2 sip/gün | 100.4 kişi/gün | 7.43 dk | 51.41 dk | `-3979.56` | ⚠️ Gelişme Yok (Patience: 1/3) |
| **Döngü 3** | 150 Gün | 589.7sn | 323.6 sip/gün | 103.4 kişi/gün | 4.25 dk | 50.82 dk | `-3665.30` | ⚠️ Gelişme Yok (Patience: 2/3) |
| **Döngü 4** | 200 Gün | 569.8sn | 303.9 sip/gün | 101.8 kişi/gün | 4.24 dk | 48.8 dk | `-3857.45` | ⚠️ Gelişme Yok (Patience: 3/3) |

---

## 💡 Model Dosyaları

* **En İyi Model (Best):** `C:\kod\Bitirme Projesi\models\ppo_order_scheduler_best.zip` *(Test performansında zirveye ulaşan ağırlıklar)*
* **Son Model (Latest):** `C:\kod\Bitirme Projesi\models\ppo_order_scheduler.zip` *(Eğitilen en güncel sürüm)*

---
*Bu rapor run_long_training.py tarafından her 50 günlük döngü sonrasında otomatik güncellenmektedir.*