# Smarity kurulum rehberi (yaklaşık 20 dakika, tamamen ücretsiz)

Kod yazmana gerek yok. YZ Radar'ı kurduğun adımların neredeyse aynısı. Smarity ayrı bir sistemdir: kendi botu, kendi deposu ve kendi sitesi olur, YZ Radar'a dokunmaz.

---

## 1) Yeni bir Telegram botu oluştur (2 dk)

1. Telegram'da **@BotFather**'ı aç (mavi tikli olan).
2. `/newbot` yaz.
3. Bota bir ad ver, örneğin `Smarity Onay`.
4. Bir kullanıcı adı ver; sonu `bot` ile bitmeli. Örneğin `smarity_onay_bot`.
   > YZ Radar'ın botunu kullanma: aynı botu iki sistem birden dinlerse butonlar birbirine karışır.
5. BotFather sana uzun bir **token** verir (`123456789:AA...` gibi). Bir yere kopyala. → Bu **TELEGRAM_BOT_TOKEN**.
6. Oluşan botu aç ve **Başlat**'a (/start) bas.

## 2) Ücretsiz Gemini anahtarını al (3 dk)

Haberleri Google Gemini'nin **ücretsiz katmanı** yazar. Kredi kartı gerekmez.

1. <https://aistudio.google.com/apikey> adresine Google hesabınla gir.
2. **Create API key**'e bas. Proje seçme kutusunda **yeni bir proje oluştur** (adı örneğin `smarity`), sonra **Create key**. Anahtarı kopyala. → Bu **GEMINI_API_KEY**.
   > Neden yeni proje? Ücretsiz günlük sınır anahtar başına değil, **proje başına** işler. YZ Radar'ın projesini kullanırsan iki site aynı sınırı paylaşır.
3. **Set up billing / Upgrade** gibi ödeme düğmelerine **tıklama.** Faturalandırma açılmadığı sürece hiçbir ücret çıkmaz; günlük sınır dolarsa bot sadece bir sonraki taramayı bekler.

> Toplam maliyet: **0 $.** GitHub, Telegram ve Gemini'nin ücretsiz katmanı yeterli.
> Not: Ücretsiz katmanda Google gönderilen metinleri ürünlerini geliştirmek için kullanabilir. Bot yalnızca herkese açık haber metinlerini gönderdiği için sorun değil.

## 3) (İsteğe bağlı, ücretli) Ekstralar

Varsayılan kurulumda bunlara **gerek yok**:
- **Yapay zeka görselleri:** `config.yaml` → `images.ai: true`. Google ödeme yöntemi ister. Kapalıyken her habere özgü, ücretsiz tipografik kapaklar üretilir.
- **Claude ile yazım:** `config.yaml` → `ai.provider: claude` ve `ANTHROPIC_API_KEY` gizli anahtarı. Ücretlidir.

## 4) GitHub deposunu oluştur ve dosyaları yükle (5 dk)

1. <https://github.com/signup> ile ücretsiz hesap aç (varsa giriş yap).
2. <https://github.com/new> adresine git.
   - **Repository name:** `smarity`
   - **Public** seçili olsun (ücretsiz site ve sınırsız otomasyon süresi için gerekli)
   - **Create repository**'ye bas.
3. Açılan sayfada **"uploading an existing file"** bağlantısına tıkla.
4. Masaüstündeki `smarity` klasörünü aç. Klasörün **içindekilerin hepsini** seçip sayfaya sürükle.
   - **Mac kullanıyorsan:** `.github` klasörü gizlidir. Finder'da **Cmd + Shift + .** (nokta) tuşlarına bas, gizli dosyalar görünür. Sonra hepsini seç (Cmd + A) ve sürükle.
   - Yükleme listesinde `.github/workflows/bot.yml` dosyasını gördüğünden emin ol. Bu dosya sistemin motorudur.
5. Aşağıdaki **Commit changes** düğmesine bas.

> Yüklemeden hemen sonra "Actions" sekmesinde kırmızı bir çarpı görebilirsin. Anahtarlar henüz girilmediği için bu normal.

## 5) Siteyi aç (1 dk)

1. Depoda **Settings → Pages** menüsüne git.
2. **Build and deployment → Source** kısmında **GitHub Actions**'ı seç.

## 6) Gizli anahtarları gir (3 dk)

**Settings → Secrets and variables → Actions → New repository secret**. Üç anahtarı tek tek ekle:

| Name (birebir böyle yaz) | Secret (değer) |
|---|---|
| `TELEGRAM_BOT_TOKEN` | 1. adımdaki BotFather token'ı |
| `TELEGRAM_CHAT_ID` | Senin Telegram numaran. YZ Radar'da girdiğin numaranın aynısı. |
| `GEMINI_API_KEY` | 2. adımdaki yeni Google anahtarı |

**TELEGRAM_CHAT_ID'yi öğrenmenin en kolay yolu:** Telegram'da **@userinfobot**'a `/start` yaz. Sana verdiği **Id** numarasını kopyala.
(Diğer yol: İlk ikisini girip 7. adımı çalıştır, sonra kendi botuna `/start` yaz. Bot sana numaranı söyler.)

## 7) İlk çalıştırma (2 dk + bekleme)

1. Depoda **Actions** sekmesine git.
2. Soldan **Haber botu**'nu seç → sağdaki **Run workflow** → **"Kaynakları hemen tara"** kutusunu işaretle → **Run workflow**.
3. 5–8 dakika içinde Telegram'a onay bekleyen haberler, Instagram formatındaki görselleriyle birlikte gelmeye başlar.
4. Siten şu adreste açılır: `https://KULLANICI-ADIN.github.io/smarity/`
   (Adresi ayrıca **Settings → Pages** sayfasında görürsün.)

Bundan sonra her şey kendiliğinden çalışır. Sistem her 10 dakikada bir uyanır, 15 dakikada bir 28 kaynağı tarar ve akşam 21:00'de günün özetini gönderir.

---

## Günlük kullanım

- Telegram'a gelen her haberde: **✅ Yayınla**, **❌ Reddet**, **📄 Tam metin**, **🔁 Yeniden yaz**, **🎨 Yeni görsel** düğmeleri var.
- **Kapağı sen yönet:** Haber mesajını yanıtlayıp `görsel: TOGG T10F` gibi kısa bir ifade yazarsan kapaktaki büyük yazı bu olur. **🎨 Yeni görsel** renk ve düzeni değiştirir.
- **Instagram gönderisi (carousel):** Yayınlanan her haber için 3 görsel gelir: 1) vurgulu başlık ve kısa özet, 2) öne çıkan 3 madde, 3) "Neden önemli?" ve "Haberin tamamı profildeki bağlantıda" yönlendirmesi. Açıklama metni ve etiketler de hazır gelir; dokunup kopyalayabilirsin. Renkler habere göre değişir.
- **Instagram hikâyesi:** Ayrı bir hikâye görseli ve haberin adresi gelir. Instagram'da hikâyeye **Bağlantı** çıkartması ekle, adresi yapıştır ve çıkartmayı oktaki boşluğa koy. (Instagram bağlantı çıkartmasının otomatik eklenmesine izin vermiyor; bu adım otomasyonda da elle yapılır.)
- Dev rakamlı kapak tarzını istersen `config.yaml` → `social.card_style: kapak`. Otomatik paylaşım 2. aşamada eklenecek; o zamana kadar bunları indirip elle paylaşabilirsin. Yapay zeka görsellerini açarsan Instagram bunlar için "AI info" etiketi isteyebilir.
- **Düzeltme:** Haber mesajını yanıtla ve talimat yaz (ör. "başlığı kısalt").
- Butona bastıktan sonra işlem genellikle birkaç dakikada, en geç ~15 dakikada gerçekleşir; mesaj güncellenir.
- **Öğrenen mod:** Önce 30 karar vermen gerekir. Ardından en az 10 kararda %90 onay verdiğin kaynaklardan gelen net haberler otomatik yayınlanır. Bunlar sana sessiz bildirim olarak gelir ve **🗑 Kaldır** düğmesiyle geri alınabilir.
- Komutlar: `/durum`, `/bekleyen`, `/mod`, `/topla`, `/duraklat`, `/devam`, `/kaynaklar`.

## Konular ve kaynaklar

5 kategori: **Süper Zeka** (yapay zeka), **Teknoloji** (yeni ürünler, otomobiller, teknoloji devleri), **İnovasyon** (ilk kez denenen teknolojiler, bilim, robotik, uzay, enerji), **Girişimcilik** (girişim hikâyeleri ve yatırımlar), **Gaming** (oyun dünyası).
Türkiye'den haberler kendi konusunun kategorisine girer ve "Türkiye" etiketiyle ayrıca listelenir.

28 kaynak: Apple, Samsung, Google, OpenAI, Anthropic (resmi duyurular); TechCrunch, The Verge, Engadget, WIRED,
Ars Technica, GSMArena; MIT Technology Review, New Atlas, Interesting Engineering; Electrek, Carscoops, Autocar;
IGN, Polygon, VGC, GamesIndustry.biz; Webrazzi, Egirisim, Webtekno, ShiftDelete.Net, DonanımHaber, LOG, Anadolu Ajansı (Türkiye).
Uzman okura yönelik birkaç kaynak (NVIDIA, IEEE Spectrum, Crunchbase News, EU-Startups, Hacker News) `config.yaml` içinde kapalı durur.

**Seçicilik:** Sistem "genel okur" testini uygular: teknoloji meraklısı ama uzman olmayan biri bu haberi bir cümlede anlayıp
bir arkadaşına anlatır mı? Anlatmazsa haber önüne gelmez. Önem eşiği 7, günlük üst sınır 20 haberdir (`config.yaml` → `editorial`).

**Renkler:** Her kategorinin kendi renk ailesi var: Süper Zeka mor, Teknoloji mavi, İnovasyon yeşil, Girişimcilik turuncu, Gaming pembe.
Kapaklar ve Instagram görselleri bu ailenin içinde habere göre ton değiştirir.

Okunamayan bir kaynak olursa `/durum` komutunda "⚠️ Okunamayan kaynaklar" olarak görünür; sistemi durdurmaz.

## Ayar değiştirmek

GitHub'da `config.yaml` dosyasını aç → kalem simgesi → değiştir → **Commit changes**. Burada şunları değiştirebilirsin:
- Site sloganı (`site:`) ve ana sayfa başlıkları (`seo:`)
- Kaynak ekleme/çıkarma (`sources:`)
- Önem eşiği (`min_importance`) ve günlük sınır
- Otonomi eşikleri

## Bilmende fayda var

- **Depo herkese açık.** Bekleyen taslaklar da depoda görünür, ama anahtarların GitHub'ın gizli kasasında durur ve görünmez.
- **Kendi alan adın:** İleride `smarity.com` gibi bir alan adı bağlamak istersen `config.yaml` içindeki `site.url` alanını değiştirip Settings → Pages'den alan adını eklemen yeterli.
- **GitHub kuralları:** GitHub Actions, depodaki projeyi derleyip yayınlamak içindir. Bu sistem bir web sitesini düzenli güncelleyip yayınladığı için bu kullanıma uyuyor. Ama sistem büyürse ya da GitHub itiraz ederse, aynı kod değişmeden küçük bir sunucuda da çalışır (`python -m haberbot run` komutunu 10 dakikada bir çalıştırmak yeterli).
