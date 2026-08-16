# 🚀 Uzun Süreli RL Eğitimi (Long Train) Canlı İlerleme Raporu

**Tarih:** 2026-08-16 14:00:42 | **Harita:** `default_layout.json` | **Zorluk:** Seviye 3

**Döngü Yapısı:** 50 Gün Eğitim (72.000 Adım) $\to$ 10 Gün Test (14.400 Adım) $\to$ Early Stopping (Patience: 3)

**En İyi Model:** 🏆 **Döngü 1** (Skor / Günlük Ödül: `+2500.00`)

---

## 📊 İterasyon Geçmişi ve Doğrulama Tablosu

| Döngü | Kümülatif Gün | Eğitim Süresi | Günlük Tamamlanan | Günlük Churn | Ort. Bekleme | Ort. Soğuma | Günlük Ödül (Skor) | Durum / Patience |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Döngü 1** | 50 Gün | 45.2sn | 310.0 sip/gün | 45.0 kişi/gün | 8.5 dk | 42.1 dk | `+2500.00` | 🏆 YENİ EN İYİ (Skor: +2500.00) |

---

## 💡 Model Dosyaları

* **En İyi Model (Best):** `C:\kod\Bitirme Projesi\models\ppo_order_scheduler_best.zip` *(Test performansında zirveye ulaşan ağırlıklar)*
* **Son Model (Latest):** `C:\kod\Bitirme Projesi\models\ppo_order_scheduler.zip` *(Eğitilen en güncel sürüm)*

---
*Bu rapor run_long_training.py tarafından her 50 günlük döngü sonrasında otomatik güncellenmektedir.*