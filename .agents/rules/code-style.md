# Restoran Simülasyonu & AI Kodlama Standartları (code-style.md)

Bu dosya, Yapay Zeka Destekli Dinamik Restoran Simülasyonu ve Sipariş Optimizasyon Sistemi projesindeki kodlama stili, mimari temizlik ve Gymnasium/ML standartlarını içerir.

---

## 1. Temel Python & Mimari Standartları

- **Python Sürümü:** Python 3.10+ standartlarına uygun tip belirteçleri (`typing.Optional`, `typing.Tuple`, `dict[str, Any]`) kullanılmalıdır.
- **PEP 8 Uyumu:** Sınıf isimleri `PascalCase`, fonksiyon ve değişken isimleri `snake_case`, sabitler `UPPER_SNAKE_CASE` olmalıdır.
- **Tek Sorumluluk İlkesi (SRP):**
  - Simülasyon aktörleri (`Chef`, `Waiter`, `Table`, `Station`) sadece kendi durumlarını ve hareketlerini yönetir.
  - Yol bulma (`Pathfinder`) ve zaman kaydı (`CookTimeRecorder`) modülleri ayrık tutulmalıdır.

---

## 2. Gymnasium & RL Ortamı Kuralları

- **Env Standartları:** Gymnasium 0.26+ uyumluluğu sağlanmalıdır:
  - `reset(seed=None, options=None)` metodu `(observation, info)` ikilisi döndürmelidir.
  - `step(action)` metodu 5'li tuple döndürmelidir: `(observation, reward, terminated, truncated, info)`.
- **Observation & Action Spaces:** `Box` ve `Discrete` / `Dict` alanları açıkça tanımlanmalı, `np.float32` veri tipleri tercih edilmelidir.

---

## 3. Hata Yönetimi & Dayanıklılık (Resilience)

- **Sessiz Hata Yutma Yasaktır:** `except` bloklarında hatalar asla boş bırakılamaz; simülasyon event loglarına işlenmelidir.
- **Sınır ve Durum Kontrolleri:** Garson veya aşçı ataması yapmadan önce aktörlerin `IDLE` ve istasyonların kapasitesinin müsait olduğu kontrol edilmelidir (Guard Clauses).
- **Erken Dönüş (Early Return):** Derin `if-else` yapıları yerine erken dönüş kalıpları kullanılmalıdır.
