# Task-Oriented Model Routing Guidelines (model-routing.md)

Bu kılavuz, karmaşık projelerde maliyet, hız ve akıl yürütme başarımını optimize etmek üzere model seçim ve subagent delegasyon stratejisini belirler.

---

## 1. Görev Bazlı Model Katmanları

| Görev Tipi | Önerilen Model Karakteri | Antigravity Subagent `Model` Parametresi |
| :--- | :--- | :--- |
| **Planlama, SPEV Spec/Plan, Mimari Tasarım, Kompleks Refactoring** | Yüksek Akıl Yürütme (High Reasoning) | `pro` / `inherit` |
| **Hızlı Kodlama, Birim Test Yazımı, Linter & Format Hata Düzeltme** | Hızlı Kodlama (Fast Coding) | `flash` |
| **Monorepo Taraması, Kapsamlı Bağımlılık Grafiği Çıkarma** | Geniş Bağlam Penceresi (Large Context Window) | `flash` veya `pro` |

---

## 2. Alt Ajan (Subagent) Delegasyon Protokolü

Antigravity üzerinde `invoke_subagent` veya `define_subagent` kullanılırken:

1. **Araştırma ve İnceleme**:
   - `TypeName: 'research'`, `Model: 'flash'`
   - Ana sohbet bağlamını doldurmadan hızlıca dosya arama, web araması veya log inceleme yapar.

2. **Ağır Akıl Yürütme ve Kök Neden Analizi**:
   - `TypeName: 'self'`, `Model: 'pro'`
   - Karmaşık mantık hatalarını ve mimari tıkanıklıkları çözer.

3. **Paralel Görev Yürütme**:
   - Bağımsız modüllerin geliştirilmesinde concurrent subagent'lar başlatılarak `Model: 'inherit'` veya `Model: 'flash'` ile işlem yapılır.
