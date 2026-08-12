---
name: spev-loop
description: >-
  Spec-Plan-Execute-Verify (SPEV) Kapalı Döngü Becerisi.
  Geliştirme sürecini otomatiğe bağlayan, test başarısızlıklarında kendi kendini düzelten (self-healing) kapalı doğrulama döngüsü.
---

# Spec-Plan-Execute-Verify (SPEV) Closed-Loop Skill

SPEV, insan müdahalesini ve mantık hatalarını en aza indiren 4 aşamalı kapalı doğrulama döngüsüdür.

---

## 🔁 SPEV Döngüsü Aşamaları

### 1. Spec (Şartname & Tanım)
- Kullanıcı isteği veya proje ihtiyacı somut giriş/çıkış şartlarına dönüştürülür.
- Değişmezler (invariants) ve kabul kriterleri (acceptance criteria) netleştirilir.

### 2. Plan (Planlama)
- Antigravity Planning Mode kurallarına uygun olarak `implementation_plan.md` hazırlanır.
- Mimari yaklaşım, etkilenen bileşenler ve doğrulama planı kullanıcı onayına sunulur.

### 3. Execute (Uygulama & Kodlama)
- Onaylanan plan adım adım uygulanır.
- Değişiklikler esnasında `SCRATCHPAD.md` güncellenir.
- Gereksiz yan etkilerden kaçınılır.

### 4. Verify & Self-Healing (Doğrulama & Kendi Kendini Düzeltme)
- Otomatik testler ve linter betikleri çalıştırılır (`.agents/hooks.json` veya `.agents/scripts/spev-auto-verify.bat`).
- **TEST BAŞARILI**: `SCRATCHPAD.md` kapatılır, mimari kararlar `MEMORY.md` belgesine işlenir ve kullanıcı bilgilendirilir.
- **TEST BAŞARISIZ (Self-Healing Loop)**:
  1. Hata logu ve stack trace sessizce yutulmadan okunur.
  2. Kök neden analizi (Root Cause Analysis) yapılır.
  3. Kod düzeltilir ve otomatik olarak Adım 4 (Verify) tekrar çalıştırılır.
  4. 3 başarısız denemeden sonra kullanıcıya kök neden raporu sunulur.
