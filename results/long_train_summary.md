# 🚀 Uzun Süreli RL Eğitimi (Long Train) Canlı İlerleme Raporu

**Tarih:** 2026-08-17 09:31:48 | **Harita:** `Büyük_restoran.json` | **Zorluk:** Seviye 3

**Döngü Yapısı:** 50 Gün Eğitim (72.000 Adım) $\to$ 10 Gün Test (14.400 Adım) $\to$ Early Stopping (Patience: 5)

**En İyi Model:** 🏆 **Döngü 2** (Skor / Günlük Ödül: `+4675.84`)

---

## 📊 İterasyon Geçmişi ve Doğrulama Tablosu

| Döngü | Kümülatif Gün | Eğitim Süresi | Günlük Sipariş | % Başarı | % Sıcak Teslim | Aşçı Verim | Ort. Bekleme | Ort. Soğuma | Skor (Ödül) | Durum / Patience |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Döngü 1** | 50 Gün | 513.3sn | 321.6 sip/gün | %90.3 | %0.7 | 21.4 sip/aşçı | 4.1 dk | 55.51 dk | `+3266.46` | 🏆 YENİ EN İYİ (Skor: +3266.46) |
| **Döngü 2** | 100 Gün | 581.3sn | 352.3 sip/gün | %93.0 | %0.7 | 23.5 sip/aşçı | 3.91 dk | 56.61 dk | `+4675.84` | 🏆 YENİ EN İYİ (Skor: +4675.84) |
| **Döngü 3** | 150 Gün | 475.6sn | 343.4 sip/gün | %89.5 | %0.6 | 22.9 sip/aşçı | 4.11 dk | 56.16 dk | `+3058.45` | ⚠️ Gelişme Yok (Patience: 1/5) |
| **Döngü 4** | 200 Gün | 529.1sn | 365.2 sip/gün | %92.6 | %0.6 | 24.3 sip/aşçı | 3.83 dk | 57.46 dk | `+4665.67` | ⚠️ Gelişme Yok (Patience: 2/5) |
| **Döngü 5** | 250 Gün | 540.3sn | 152.6 sip/gün | %47.1 | %1.5 | 10.2 sip/aşçı | 7.86 dk | 49.87 dk | `-22593.84` | ⚠️ Gelişme Yok (Patience: 3/5) |

---

## 💡 Model Dosyaları

* **En İyi Model (Best):** `C:\kod\Bitirme Projesi\models\ppo_order_scheduler_best.zip` *(Test performansında zirveye ulaşan ağırlıklar)*
* **Son Model (Latest):** `C:\kod\Bitirme Projesi\models\ppo_order_scheduler.zip` *(Eğitilen en güncel sürüm)*

---
*Bu rapor run_long_training.py tarafından her 50 günlük döngü sonrasında otomatik güncellenmektedir.*