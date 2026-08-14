# 🔍 RL Eğitim ve Simülasyon Detaylı Hata Ayıklama (Debug) Raporu

**Tarih:** Cum 14.08.2026 | **Yapılandırma:** `C:\kod\Bitirme Projesi\config\default_layout.json` | **Zorluk Seviyesi:** 3

---

## 1. 🎯 Aksiyon Seçim Dağılımı ve Politika Eğilimleri

* **Toplam Alınan Karar Adımı:** `1,536`
* **Geçerli Sipariş Atamaları (`ASSIGN`):** `679` (%44.21)
* **Boşta Bekleme (`No-Op`):** `857` (%55.79)
* **Geçersiz/Engellenmiş Hamle Girişimleri:** `0` (%0.00)

> [!NOTE]

> Ajan kararlarının %44.2'inde mutfağa aktif sipariş atamış, %55.8'inde ise mutfağın pişirmesini beklemiştir.

---

## 2. 💰 Ödül ve Ceza Dağılım Bileşenleri

| Ödül/Ceza Kalemi | Toplam Puan | Etki Yönü | Açıklama |
| :--- | :--- | :--- | :--- |
| **Tamamlanan Sipariş Bonusu** | `+4960.0` | Pozitif 🟢 | Masaya/kuryeye başarıyla teslim edilen siparişler |
| **Sub-tick Atama Bonusu** | `+679.0` | Pozitif 🟢 | Aynı dakika içinde seri aşçı doldurma teşviki |
| **Müşteri Kaybı (Churn) Cezası** | `-9000.0` | Negatif 🔴 | Sabrı tükenip restorandan ayrılan müşteriler |
| **Kuyrukta Bekleme Cezası** | `-293.1` | Negatif 🔴 | Siparişlerin mutfağa alınmadan beklediği süre |
| **Soğuk Yemek Cezası (Group Sync)** | `-1024.0` | Negatif 🔴 | Aynı masanın diğer yemeklerini beklerken soğuyan tabaklar |
| **Kurye Gecikme Cezası** | `-18.0` | Negatif 🔴 | Paket servis kuryesinin kapıda bekletilme cezası |

---

## 3. 🍳 İstasyon Yükü ve Darboğaz Analizi

| İstasyon ID | Meşgul Olduğu Adım | Tam Dolu Olduğu Adım | Arıza Yaşanan Adım | Durum Değerlendirmesi |
| :--- | :--- | :--- | :--- | :--- |
| `S_OVEN_1` | 378 (%24.6) | 295 (%19.2) | 173 | Dengeli 🟢 |
| `S_GRILL_1` | 485 (%31.6) | 139 (%9.0) | 139 | Dengeli 🟢 |
| `S_STOVE_1` | 309 (%20.1) | 52 (%3.4) | 40 | Dengeli 🟢 |
| `S_PREP_1` | 548 (%35.7) | 149 (%9.7) | 57 | Dengeli 🟢 |

---

## 4. ⚠️ Olay ve Anomali Kayıtları

* **Toplam Churn Olay Sayısı:** `16` kez müşteri sabır tükenmesi gerçekleşti.
* **Tamamlanan Sipariş Sayısı:** `31` sipariş.
* **Kalan Kuyruk Uzunluğu:** `1` sipariş.

### 🚨 Churn Olay Zaman Çizelgesi (Örnek İlk 10 Kayıt):
| Simülasyon Dakikası (Tick) | Kaçan Müşteri Sayısı |
| :--- | :--- |
| Dakika 445 | 6 Müşteri |
| Dakika 656 | 6 Müşteri |
| Dakika 819 | 4 Müşteri |
| Dakika 839 | 4 Müşteri |
| Dakika 906 | 10 Müşteri |
| Dakika 1019 | 4 Müşteri |
| Dakika 1043 | 4 Müşteri |
| Dakika 1107 | 2 Müşteri |
| Dakika 1128 | 2 Müşteri |
| Dakika 1254 | 6 Müşteri |

---
*Bu rapor Detaylı Debug Modu tarafından otomatik üretilmiştir.*