# Ephemeral Scratchpad (SCRATCHPAD.md)

> [!NOTE]
> Bu belge **geçici oturum belleğidir**. Oturum esnasındaki aktif geliştirme adımları, hipotezler ve yapılacaklar listesi burada tutulur.

---

## Aktif Görev (Active Task)
- [x] **Faz 1-3:** Simülasyon Çekirdeği, Veri Toplama, ML/RL Modelleri (Tamamlandı)
- [x] **Faz 4:** Görselleştirme ve Analitik Dashboard (Tamamlandı)
- [x] **Faz 5:** Görsel Layout Düzenleyici (`layout_editor.html`, Port 8080) (Tamamlandı)
- [x] **Faz 6:** Çoklu Sipariş Üretim Modeli (`generator.py`) & Karşılaştırmalı Deneyler (Tamamlandı)
- [x] **Faz 7:** Simülasyon Çekirdeği Modülerleştirme & Kod Sadeleştirme (SRP & DRY) (Tamamlandı - 12/12 Test Passed)
- [x] **Faz 8:** 6 Standart Giriş Betiği Konsolidasyonu & Simülasyon Hızlandırması (Tamamlandı)
- [x] **Faz 9:** Paralel Çoklu Çekirdek RL (`SubprocVecEnv`), Dijkstra Önbelleği & ML Dondurma (Tamamlandı - 13/13 Test Passed, 300+ FPS)

---

## 6 Standart Çalıştırma Komutu
```bash
# 1. Harita Düzenleyiciyi Başlatma (Port 8080 - layouts/ kaydı)
py layout_editor.py

# 2. Deterministik Algoritmalar (FIFO, SPT, LPT, MinPatience) 100 Gün Benchmark
py run_deterministic_test.py --days 100

# 3. Pekiştirmeli Öğrenme (RL) Eğitimi (İnteraktif Mod / Fine-Tune)
py run_rl_training.py

# 4. Eğitilmiş RL Modelini 100 Gün Test Etme
py run_rl_model.py --days 100

# 5. Canlı 2D Pygame Simülatörü
py run_simulator.py --mode rl

# 6. Model Karşılaştırma Grafiği & Tablosu / Web Dashboard
py compare_models.py
py compare_models.py --web
```

