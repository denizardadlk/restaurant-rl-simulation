# Ephemeral Scratchpad (SCRATCHPAD.md)

> [!NOTE]
> Bu belge **geçici oturum belleğidir**. Oturum esnasındaki aktif geliştirme adımları, hipotezler ve yapılacaklar listesi burada tutulur.

---

## Aktif Görev (Active Task)
- [x] **Faz 1-3:** Simülasyon Çekirdeği, Veri Toplama, ML/RL Modelleri (Tamamlandı)
- [x] **Faz 4:** Görselleştirme (`gui_pygame.py`) ve Analitik Dashboard (`dashboard.py`) (Tamamlandı)
- [x] **Faz 5:** Görsel Layout Düzenleyici (`layout_editor.html`, Port 8080) (Tamamlandı)
- [x] **Faz 6:** Çoklu Sipariş Üretim Modeli (`generator.py`) & Karşılaştırmalı Deneyler (Tamamlandı)
- [ ] **Gelecek Oturum:** Mutfak istasyonu/aşçı kapasitesi artırımı veya PPO RL Ajanının 100k+ adım ile çoklu sipariş ortamında yeniden eğitilmesi.

---

## Anlık Hipotezler & Mimari Yapı (Hypotheses & Architecture)
- Grid boyutu varsayılan $10 \times 10$ veya özel `$14 \times 11$` (`custom_layout.json`).
- A* mesafe matrisi `Pathfinder` sınıfı ile tek seferde pre-compute edilerek önbelleğe alınır.
- **Çoklu Sipariş Sistemi:** `OrderGenerator` masaya oturan her müşteri (masa kapasitesi kadar) için bağımsız sipariş üretir.
- **Layout Algılama:** Tüm betikler `config/custom_layout.json` dosyasını otomatik olarak öncelikli yükler.
- **Hata Düzeltmeleri:** `gui_pygame.py` ve `dashboard.py` içerisindeki `table.status` referansı `table.customers > 0` ve `table.is_empty` ile değiştirilmiştir.

---

## Oturum Yapılacaklar Listesi (Session Checklist)
- [x] **Adım 1:** Pygame 2D (`gui_pygame.py`) ve Streamlit (`dashboard.py`) görselleştirme araçlarının hazırlanması.
- [x] **Adım 2:** Python 3.14 uyumluluğu için `pygame-ce` entegrasyonu.
- [x] **Adım 3:** `custom_layout.json` desteğinin tüm betiklere eklenmesi.
- [x] **Adım 4:** Yeni çoklu sipariş sisteminde 10 günlük ML ve PPO RL eğitimi/karşılaştırması.
- [x] **Adım 5:** Arayüz çökme hatalarının (`table.status` AttributeError) giderilmesi ve test edilmesi (8/8 test passed).

---

## Test & Doğrulama İpuçları (Quick Commands for Agents)
```bash
# Layout Düzenleyici Sunucusunu Başlatma (Port 8080)
python run_layout_editor.py

# Tarayıcıda Açma
# http://localhost:8080/layout_editor.html

# Tüm Birim Testleri Çalıştırma
python -m pytest tests/

# Simülasyonu Çalıştırma
python main.py

# Analitik Dashboard'u Başlatma
streamlit run dashboard.py
```
