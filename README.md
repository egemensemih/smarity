# Smarity — otonom teknoloji haber sistemi

Dünyadan ve Türkiye'den teknoloji, inovasyon, girişim, yapay zeka, yeni ürün, otomobil ve oyun
haberlerini toplar, Türkçe ve kaynak gösteren haberler yazar,
Telegram'dan onayını alır ve web sitesinde yayınlar. Kararlarından öğrenir: güvendiği
kaynaklardan gelen net haberleri zamanla kendisi yayınlamaya başlar.

**Kurulum için:** `KURULUM.md` dosyasına bak (yaklaşık 20 dakika, kod bilgisi gerekmez).

**Maliyet: 0 $.** GitHub Actions + Pages, Telegram ve Google Gemini'nin ücretsiz katmanıyla çalışır.
Claude ve yapay zeka görselleri isteğe bağlı, ücretli eklentilerdir (`config.yaml`).

## Nasıl çalışır?

```
Her 10 dk (GitHub Actions)
 ├─ Telegram: butonlarını ve komutlarını işle
 ├─ 15 dakikada bir: 28 kaynağı tara (RSS + Anthropic haber sayfası)
 │    ├─ Gemini Flash-Lite (ücretsiz): aynı haberleri birleştir, 1–10 önem puanı ver, önemsizleri ele
 │    ├─ Tam metni kaynaktan oku (robots.txt'ye uyarak)
 │    ├─ Gemini Flash (ücretsiz): özgün Türkçe haber + "Neden önemli?" + risk işaretleri
 │    ├─ Kapak: habere özel tipografik kapak — dev rakam, ürün adı ya da manşet (ücretsiz; kaynak fotoğrafı asla kullanılmaz)
 │    │   İsteğe bağlı, ücretli: images.ai: true ile yapay zeka görseli
 │    ├─ Kartlar: Instagram post 1080×1350, story 1080×1920, paylaşım kapağı 1200×630
 │    │   (Smarity logosuyla; renk ve düzen habere göre otomatik seçilir)
 │    └─ Karar: sana sor  |  otomatik yayınla (öğrenen mod)
 ├─ Onaylananları siteye ekle, GitHub Pages'e yayınla
 └─ Akşam: günlük özet
```

## Klasörler

| Yol | Ne var? |
|---|---|
| `config.yaml` | **Tüm ayarlar** — site adı, kaynaklar, otonomi eşikleri, modeller |
| `haberbot/` | Python kodu |
| `templates/`, `static/` | Site tasarımı (apple.com esintili, açık tema) ve logo dosyaları (`static/logo.svg`) |
| `templates/cards/` | Instagram post/story ve paylaşım kapağı şablonları |
| `content/posts/` | Yayınlanan haberler (JSON) |
| `content/images/` | Haber görselleri (`.webp`) ve paylaşım kapakları (`-og.jpg`) |
| `data/` | Bot durumu, taslaklar, kaynak güven istatistikleri, arşiv |

## Telegram komutları

`/durum` · `/bekleyen` · `/mod manuel|ogrenen|tam` · `/topla` · `/duraklat` · `/devam` · `/kaynaklar` · `/yardim`

Bir haberi düzeltmek için o haberin Telegram mesajını **yanıtla** ve talimatını yaz
(ör. "başlığı kısalt", "son paragrafı çıkar").

## Yerel test (isteğe bağlı)

```bash
pip install -r requirements.txt
python tests/test_core.py
python tests/make_fixtures.py
HABERBOT_ROOT=/tmp/smarity HABERBOT_MOCK=1 HABERBOT_FIXTURES=tests/fixtures python -m haberbot run
```

## Sonraki aşama

Instagram'a otomatik paylaşım (post, story, reels). Görsel kartlar ve `/api/latest.json` bu aşama için hazır.

Kartlardaki yazı tipi Instrument Sans'tır (SIL Open Font License, `assets/fonts/OFL-InstrumentSans.txt`).
