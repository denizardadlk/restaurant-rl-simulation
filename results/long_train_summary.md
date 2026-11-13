# 🚀 Uzun Süreli Sıralı RL Eğitimi (Alternating Co-Training) Canlı İlerleme Raporu

**Tarih:** 2026-08-24 14:31:13 | **Harita:** `default_layout.json` | **Zorluk:** Seviye 3

**Eğitim Stratejisi:** Dönüşümlü Çift Ajanlı (Co-Evolutionary: Şef 🔄 Garson)

**Döngü Yapısı:** Her Döngüde [Şef Eğitimi $\to$ Garson Eğitimi $\to$ Ortak 10 Günlük Sinerji Testi]

**En Başarılı Sinerji:** 🏆 **Döngü 1** (Ortak Skor: `+2500.00`)

---

## 📊 İterasyon Geçmişi ve Ortak Doğrulama Tablosu

| Döngü | Küm. Gün | Şef Süresi | Garson Süresi | Günlük Sipariş | % Başarı | % Sıcak Teslim | Aşçı Verim | Ort. Bekleme | Ort. Soğuma | Skor (Ödül) | Durum / Patience |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Döngü 1** | 50 Gün | 0.0sn | 0.0sn | 310.0 sip/gün | %0.0 | %0.0 | 0.0 sip/aşçı | 8.5 dk | 42.1 dk | `+2500.00` | 🏆 YENİ EN İYİ (Skor: +2500.00) |

---

## 💡 Kayıtlı En İyi Model Ağırlıkları

* **En İyi Mutfak/Şef Modeli :** `C:\kod\Bitirme Projesi\models\ppo_order_scheduler_best.zip`
* **En İyi Garson Modeli      :** `C:\kod\Bitirme Projesi\models\ppo_waiter_policy_best.zip`
* **Güncel Mutfak Modeli      :** `C:\kod\Bitirme Projesi\models\ppo_order_scheduler.zip`
* **Güncel Garson Modeli      :** `C:\kod\Bitirme Projesi\models\ppo_waiter_policy.zip`

---
*Bu rapor run_long_training.py tarafından her dönüşümlü döngü sonrasında otomatik güncellenmektedir.*