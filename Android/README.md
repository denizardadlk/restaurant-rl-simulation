# 📱 AI Restoran Sipariş Android Uygulaması (Android Studio Şablonu)

Bu dizin, restoran simülasyonuna anlık sipariş girmek ve mutfaktaki aşçı/istasyon atamalarını telefondan takip etmek için hazırlanmış **Native Android (Kotlin + Jetpack Compose + Retrofit)** projesidir.

---

## 🛠️ Nasıl Açılır ve Çalıştırılır?

1. **Android Studio'yu Açın:**
   * `File -> Open...` seçeneğine tıklayın.
   * `c:\kod\Bitirme Projesi\Android` klasörünü seçip açın.
   * Gradle senkronizasyonunun (`Sync Project with Gradle Files`) tamamlanmasını bekleyin.

2. **Ana Bilgisayar (Host PC) IP Ayarı:**
   * **Emülatörde çalıştırıyorsanız:** Varsayılan URL (`http://10.0.2.2:8000/`) doğrudan PC'nize bağlanır.
   * **Gerçek Android Telefondan bağlanıyorsanız:** Telefon ve PC aynı Wi-Fi ağına bağlı olmalıdır. Uygulama sağ üst köşesindeki ⚙️ (Ayar) butonuna basarak PC'nizin yerel IP'sini girin (örn: `http://192.168.1.105:8000/`).

3. **Uygulama Özellikleri:**
   * **Masa Seçimi:** Masaların kapasitesi, doluluğu ve müşteri sabır durumu.
   * **Menü & Sepet:** Pizza, Burger, Steak, Salata siparişleri ve adet seçimi.
   * **Takeout (Paket Sipariş):** Kurye teslimatlı harici sipariş girişi.
   * **Canlı Takip:** Simülasyon motoruna giren siparişin atandığı istasyon (`OVEN`, `GRILL`, `STOVE`, `PREP`), aşçı (`C1`, `C2`) ve yapay zeka (`Model 1 ML`) tahmini pişirme süresi (ETA).

---

## 📂 Proje Dizin Yapısı

```text
Android/
├── build.gradle.kts           # Root Gradle yapılandırması
├── settings.gradle.kts        # Modül tanımları
├── gradle.properties          # JVM & AndroidX ayarları
└── app/
    ├── build.gradle.kts       # Jetpack Compose, Retrofit, OkHttp bağımlılıkları
    └── src/main/
        ├── AndroidManifest.xml
        └── java/com/restaurant/orderapp/
            ├── MainActivity.kt               # Ana aktivite
            ├── data/
            │   ├── models/Models.kt          # Masa, Menü, Sipariş DTO'ları
            │   └── api/
            │       ├── RestaurantApiService.kt # REST API Sözleşmesi
            │       └── RetrofitClient.kt     # Dinamik IP destekli HTTP istemcisi
            └── ui/
                ├── theme/Theme.kt            # Modern karanlık restoran teması
                └── screens/OrderAppScreen.kt # Masalar, Menü ve Canlı Takip Arayüzü
```
