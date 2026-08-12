# Antigravity Universal Project & Agent Guidelines (AGENTS.md)

Bu dosya, bu projedeki tüm AI kodlama asistanları (Antigravity 2.0, AGY CLI, Antigravity IDE, Cursor vb.) için **evrensel kural ve iş akışı standardını** belirler.

---

## 1. Mimari İkili: Olasılıksal ve Deterministik Yapılar

Projelerimizdeki görevler strictly aşağıdaki ayrım çerçevesinde yönetilir:

- **Olasılıksal Katman (Kurallar & Beceriler / Rules & Skills)**:
  - Kod stili, mimari desenler, refactoring fikirleri ve açık uçlu çözümler **Kurallarda (`.agents/rules/`)** veya **Becerilerde (`.agents/skills/`)** tanımlanır.
  - LLM'e yol gösterir ancak esneklik sunar.

- **Deterministik Katman (Kancalar & Betikler / Hooks & Scripts)**:
  - Syntax kontrolü, linter, kod formatlama, güvenlik kapıları (secrets/keys taraması) ve birim testler **Kancalar (`.agents/hooks.json`)** ve **Betiklere (`.agents/scripts/`)** devredilir.
  - LLM'in inisiyatifine bırakılmaz, otomatik çalıştırılır ve başarısızlık durumunda LLM durdurulur / uyarması sağlanır.

---

## 2. Bellek Yönetimi Protokolü

Her çalışma oturumunda ve uzun soluklu projelerde 2 seviyeli bellek disiplini uygulanır:

1. **Geçici Bellek Katmanı (`SCRATCHPAD.md`)**:
   - O anki oturuma ait aktif görev checklist'i, anlık hipotezler ve uncommitted fikirler burada tutulur.
   - Oturum bitiminde veya görev tamamlandığında temizlenebilir.

2. **Kalıcı Bellek Katmanı (`MEMORY.md`)**:
   - Zaman içinde alınan Mimari Karar Kayıtları (ADR), domain iş kuralları, teknoloji seçimleri ve geçmişte yaşanan krizlerden öğrenilen dersler buraya işlenir.
   - Projenin evrimsel hafızasıdır.

---

## 3. Bağlamsal Test Mimarısı (TDAD - Test Driven Architecture & Design)

Kod geliştirmeden önce prosedürel TDD yerine **Bağlamsal TDAD** uygulanır:
- Etkilenen bileşenlerin bağımlılık grafiği çıkarılır.
- Değişikliğin sınır (boundary) ve yan etki (side-effect) alanları belirlenir.
- Testler sadece kodun doğrulanması için değil, mimari sözleşmelerin korunması için yazılır.
- TDAD sürecinde `.agents/skills/tdad/SKILL.md` becerisi aktif edilir.

---

## 4. Kapalı Doğrulama Döngüsü (SPEV - Spec-Plan-Execute-Verify)

Kodlama süreci 4 kapalı adımdan oluşur:
1. **Spec (Şartname)**: Giriş/Çıkış sözleşmeleri ve değişmezlerin (invariants) netleştirilmesi.
2. **Plan (Planlama)**: `implementation_plan.md` artifact'ı üzerinden mimari onay alınması.
3. **Execute (Uygulama)**: Artırımlı ve modüler kod yazımı.
4. **Verify (Doğrulama)**: Otomatik test ve lint çalıştırması. Test hatasında **kendi kendini düzeltme (self-healing)** mekanizması devreye girer.
- SPEV sürecinde `.agents/skills/spev-loop/SKILL.md` becerisi aktif edilir.

---

## 5. Görev Odaklı Model Seçim Matrisi

Model seçimi görevin karmaşıklığına göre hibrit olarak yapılandırılır:
- **Yüksek Akıl Yürütme (High Reasoning)** -> Planlama, Mimari Tasarım, Karmaşık Refactoring, SPEV Spec & Plan aşamaları.
- **Hızlı Kodlama (Fast Coding)** -> Küçük kod düzenlemeleri, rutin unit testler, linter hatalarını giderme.
- **Geniş Bağlam Penceresi (Large Context)** -> Monorepo taramaları, bağımlılık haritalama, kapsamlı kod incelemeleri.

Subagent kullanımında `invoke_subagent` çağrılarına `Model: 'pro'`, `Model: 'flash'` veya `Model: 'inherit'` parametreleri görevin doğasına göre atanır.

	