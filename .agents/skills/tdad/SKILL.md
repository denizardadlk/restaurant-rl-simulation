---
name: tdad
description: >-
  Bağlamsal Test-Driven Architecture & Design (TDAD) Becerisi.
  Kod yazmadan önce kod ile testler arasındaki bağımlılık haritalarını çıkararak etki analizi temelli doğrulama sağlar.
---

# Contextual Test-Driven Architecture & Design (TDAD) Skill

Prosedürel TDD ("önce test yaz, sonra kod yaz") yaklaşımını mimari bağlam ile zenginleştiren **TDAD** protokolüdür.

---

## 🛠️ TDAD İş Akışı (4 Adım)

### Adım 1: Etki Alanı ve Bağımlılık Haritalama (Dependency Graph & Impact Analysis)
Kod geliştirmeye veya refactoring yapmaya başlamadan önce:
1. Değişecek dosyanın bağımlı olduğu üst modüller ve bağımlı kılınan alt modüller listelenir.
2. Bu bileşenleri kapsayan mevcut test dosyaları (`*.test.*`, `*_test.*`, `spec.*`) tespit edilir.
3. Herhangi bir eksik test kapsamı (coverage gap) veya mimari kırılma riski not edilir.

### Adım 2: Mimari Sözleşme ve Sınır Testleri (Architectural Contract & Boundary Tests)
Sadece mutlu yol (happy path) değil, aşağıdaki sözleşmeler için test senaryoları tanımlanır:
- **Veri Sözleşmeleri**: Girdi ve çıktı veri yapılarının doğruluğu (Schema & Invariants).
- **Sınır Durumları (Edge Cases)**: Boş girdiler, null/undefined, aşırı yük ve zaman aşımı durumları.
- **Yan Etki Yalıtımı (Side-effect Isolation)**: Yan etkilerin (DB yazma, dış API çağrısı) taklit edilmesi (mock/stub).

### Adım 3: Artırımlı Doğrulama (Incremental Verification)
- Değişiklikler küçük parçalar halinde uygulanır.
- Her parçada yalnızca ilgili modüle ait spesifik test çalıştırılır:
  ```bash
  npm test -- path/to/specific.test.js
  # veya
  pytest tests/test_module.py
  ```

### Adım 4: Etki Alanı Regresyon Kontrolü (Regression Check)
- Yerel testler başarılı olduğunda, etkilenen üst/yan modüllerin testleri çalıştırılarak regresyon oluşmadığı doğrulanır.
