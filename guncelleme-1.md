SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -8,5 +8,5 @@
   name: "Smarity"
   tagline: "Teknolojide yeni olan her şey, kaynağıyla."
-  description: "Dünyadan ve Türkiye'den yeni ürünleri, girişim hikâyelerini, ilk kez denenen teknolojileri, yapay zeka, otomobil ve oyun dünyasını her haberde orijinal kaynağıyla aktaran Türkçe teknoloji haber sitesi."
+  description: "Dünyadan ve Türkiye'den yeni ürünler, yapay zeka, otomobil, oyun ve girişim haberleri. Her haber kaynağıyla, sade bir Türkçeyle."
   # Sitenin adresi (boş bırakırsan GitHub Pages adresi otomatik kullanılır)
   url: "https://smarity.com.tr"
@@ -43,6 +43,6 @@
   # Ana sayfanın büyük başlığı ve Google'da görünen başlığı ve açıklaması
   home_h1: "Teknoloji haberleri"
-  home_title: "Teknoloji Haberleri: Yapay Zeka, İnovasyon, Girişimcilik, Gaming"
-  home_description: "Dünyadan ve Türkiye'den yapay zeka, yeni teknoloji ürünleri, inovasyon, girişim hikâyeleri ve oyun dünyası haberleri. Kaynağıyla, Türkçe, her gün güncel."
+  home_title: "Teknoloji Haberleri: Yapay Zeka, Otomobil, Oyun"
+  home_description: "Yapay zeka, yeni ürünler, otomobil, oyun ve girişim dünyasından günün teknoloji haberleri. Dünyadan ve Türkiye'den, her haber kaynağıyla."
   # Arama motoru doğrulama kodları (Search Console / Bing / Yandex'in verdiği "content" değeri)
   google_site_verification: "ChTcddRF_YOMXdFjpyGX4IbkbxC2lXSjJkQSMRd_Dqs"
@@ -142,8 +142,44 @@
     - ["671d0ac58e", "9976fc4746"]   # OpenAI en gelişmiş modellerinin eğitimini durdurdu (28 Eyl, aynı gün iki haber)
     - ["7f88f8a5fd", "d901a6a000"]   # ChatGPT Pro 500 Türkiye fiyatı (30 Eyl ↔ 27 Eyl)
+    # 1 Kasım yayın öncesi denetim: aynı haberin ikinci kez yayımlanmış hâlleri
+    - ["b4b9d9047e", "f0f00e7363"]   # iPad mini OLED + A20 Pro (28 Eki ↔ 26 Eki)
+    - ["be585a47e8", "cffe0d965c"]   # Gemini 4 Argon tanıtıldı (1 Eki ↔ 13 Eki, resmi kaynaklı olan kalır)
+    - ["50fdfe4c79", "3cd1956194"]   # Meta Muse Wonder (13 Eki ↔ 12 Eki)
+    - ["41727050c7", "ac77027a3a"]   # ChatGPT sanal kıyafet deneme (5 Eki ↔ 2 Eki)
+    - ["3bf4a255f6", "ff53f9557d"]   # Volvo ES90 Türkiye fiyatı (7 Eki ↔ 30 Eyl)
+    - ["c70726c28f", "b99febacda"]   # GTA 6 lansman fragmanı (19 Eki ↔ 15 Eki)
+    - ["346e3cd8ab", "b99febacda"]   # GTA 6 lansman fragmanı (23 Eki ↔ 15 Eki)
   relaunch:                          # ön izleme olarak açılıp asıl gelişmeyle güncellenen haber: yeni haber olarak yeniden yayınla
     - "248dd99ad3"                   # Tesla Roadster tanıtıldı (14 Eki "tanıtım tarihi" haberi olarak açılmıştı)
   retitle:
     "95a0ae8187": "Uygun fiyatlı elektrikli Dacia Hipster 2027'de geliyor"   # başlıkta yurtdışı fiyatı vardı
+  unpublish:                         # doğrulanmamış söylenti (tam otonomda yayımlanmamalıydı)
+    - "1ede6986ae"                   # "Yenilenen MacBook Pro tasarımı ortaya çıktı" (27 Eki, sızıntı)
+  fix_posts:                         # yazım, büyük-küçük harf, kategori düzeltmeleri (bir kez uygulanır; adres değişmez)
+    "73c7bf9f15": {title: "Mercedes-AMG GT SUV tanıtıldı: 1.153 beygir gücünde elektrikli SUV", seo_title: "Mercedes-AMG GT SUV tanıtıldı: 1.153 beygirlik elektrikli"}
+    "787a9bdf1d": {title: "iPhone Duo tamir ücretleri açıklandı"}
+    "21a6c2a8ef": {title: "SpaceX Starship yörünge testi için hazırlıkları tamamladı", seo_title: "Starship yörünge testi 28 Eylül'de yapılacak"}
+    "fc10b745fd": {title: "Togg T10F'e bölgesel kararabilen akıllı cam tavan", seo_title: "Togg T10F akıllı cam tavan teknolojisi tanıtıldı"}
+    "78194275fd": {seo_title: "Jaguar Type 01 New York'ta tanıtıldı"}
+    "90c6631ac7": {summary: "Google, farklı mağazalardaki ürünleri tek bir yerde toplamanızı sağlayan yapay zeka destekli Universal Cart aracını ABD'de kullanıma sundu."}
+    "63c8283d28": {title: "Galaxy S27 Ultra kamera sızıntısı: 3x zoom kalkıyor mu?", seo_title: "Galaxy S27 Ultra kamera sızıntısı: 3x zoom kalkıyor mu?", meta_description: "Android Authority aktarımına göre Galaxy S27 Ultra modelinde 3x zoom kamerası kaldırılarak doğrudan 5x telefoto lense geçilebilir."}
+    "54c909b79f": {carousel_points: ["Unitree, H2-X Kung Fu Legend Guardian adlı yeni insansı robotunu tanıttı.", "Robot yaklaşık sekiz saat pil ömrü sunuyor ve dört metreden atlayabiliyor.", "Genel satışa çıkması beklenmeyen robot şimdilik bir teknoloji gösterisi olarak sergileniyor."]}
+    "c47acb3791": {carousel_points: ["MB.EA platformu üzerinde geliştirilen model 94 kWh batarya taşıyor.", "Araç, 800 volt mimarisiyle yüzde 10'dan yüzde 80 şarja 22 dakikada ulaşıyor.", "İç mekânda Hyperscreen ekran ve yapay zekâ destekli asistan yer alıyor."]}
+    "02bf4090a3": {carousel_points: ["Call of Duty: Modern Warfare 4 oyununda Itaewon faciası görüntülerine yer verilmişti.", "Faciadan kurtulanların ve hayatını kaybedenlerin ailelerinin tepkisi üzerine Activision özür diledi.", "Sorunlu görüntüler 12 Kasım'da yayınlanacak güncellemeyle oyundan kaldırılacak."]}
+    "643ca04634": {title: "Aston Martin Valhalla Spider tanıtıldı: Tavanı açıkken 349 km/s hıza ulaşıyor", summary: "Aston Martin, 1.079 beygir gücündeki hibrit süper otomobili Valhalla Spider'ı duyurdu. Model, tavanı açıkken de saatte 349 kilometre hıza ulaşabiliyor.", meta_description: "Aston Martin Valhalla Spider duyuruldu. 1.079 beygirlik hibrit süper otomobil, tavanı açıkken 349 km/s hızla markanın en hızlı üstü açık modeli oldu.", seo_title: "Aston Martin Valhalla Spider tanıtıldı: 1.079 beygir, 349 km/s"}
+    "0c162953d5": {title: "Jensen Huang: Nvidia, güvenli olmayan yapay zeka geliştirenlere çip tedarikini kesebilir", seo_title: "Jensen Huang: Güvensiz yapay zekaya çip tedariki kesilebilir"}
+    "3ba08c4da9": {title: "iPhone Duo ekran çatlakları: Söküm, menteşedeki bir parçayı işaret ediyor", seo_title: "iPhone Duo ekran çatlakları: Söküm menteşeyi işaret ediyor"}
+    "ab987ccf38": {title: "Volkswagen, Türkiye'de üretim için Doğuş Otomotiv ile niyet mektubu imzaladı", seo_title: "Volkswagen Türkiye'de üretim için niyet mektubu imzaladı"}
+    "aee5729954": {title: "ASUS ProArt P16 Türkiye'de ön siparişe açıldı: RTX Spark ve Blackwell bir arada", seo_title: "ASUS ProArt P16 Türkiye'de ön siparişe açıldı"}
+    "4ba411ee1d": {title: "GTA 6, Rockstar tarihinin en yüksek satın alma niyetine ulaştı", seo_title: "GTA 6 satın alma niyetinde Circana rekorunu kırdı"}
+    "e072bedb01": {title: "Apple, iPad mini'nin ardından iMac ve MacBook Pro sinyali verdi", seo_title: "Apple'dan iPad mini sonrası iMac ve MacBook Pro sinyali"}
+    "b99febacda": {title: "GTA 6'nın lansman fragmanı yayınlandı: Oyun 19 Kasım'da çıkıyor", seo_title: "GTA 6 lansman fragmanı yayınlandı: Çıkış 19 Kasım"}
+    "e1bc99d753": {category: "gaming"}
+    "7a56fb18bc": {category: "otomotiv"}
+    "786bf7382a": {category: "super-zeka"}
+    "b58951c070": {category: "teknoloji"}
+    "4624a73fba": {category: "otomotiv"}
+    "93bde74dd2": {category: "teknoloji"}
+    "0251d12963": {category: "teknoloji"}
 
 ai:
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -3,4 +3,5 @@
 
 import html
+import json
 import os
 import re
@@ -90,4 +91,8 @@
 
 Komutlar: /manset /secki /durum /bekleyen /mod /topla /duraklat /devam /kaynaklar /instagram"""
+
+
+# bakım listesiyle (maintenance.fix_posts) düzeltilebilen alanlar
+FIXABLE = {"title", "short_title", "seo_title", "summary", "meta_description", "category", "carousel_points"}
 
 
@@ -735,5 +740,8 @@
         retitle: {haber_id: "Yeni başlık"} → başlık düzeltilir (adres değişmez).
         relaunch: [haber_id, …] → ön izleme olarak açılıp asıl gelişmeyle güncellenen haber yeni haber olarak yeniden
-                  yayınlanır (yeni adres, eski adres yönlenir); bir kez uygulanır."""
+                  yayınlanır (yeni adres, eski adres yönlenir); bir kez uygulanır.
+        fix_posts: {haber_id: {alan: değer}} → yazım/kategori düzeltmesi (title, short_title, seo_title, summary,
+                   meta_description, category, carousel_points); adres değişmez.
+        unpublish: [haber_id, …] → haber yayından kaldırılır (ör. sonradan doğrulanamayan söylenti)."""
         m = self.cfg.raw.get("maintenance") or {}
         st = self.store
@@ -758,4 +766,34 @@
             if p and not p.get("relaunched"):
                 self._relaunch(p)
+        for pid in m.get("unpublish") or []:
+            if st.load_post(str(pid)):
+                st.delete_post(str(pid))
+                self._ig_drop(str(pid), "🗑 Haber yayından kaldırıldı; Instagram'a gönderilmeyecek")
+                log.info("Haber yayından kaldırıldı (bakım listesi): %s", pid)
+        done = self.state.setdefault("fixes_done", [])
+        for pid, fields in (m.get("fix_posts") or {}).items():
+            p = st.load_post(str(pid))
+            if not p or not isinstance(fields, dict):
+                continue
+            # bir kez uygulanır: haber sonra güncellenirse (yeni başlık vb.) eski düzeltme geri yazılmaz
+            key = f"{pid}:{short_hash(json.dumps(fields, ensure_ascii=False, sort_keys=True), n=8)}"
+            if key in done:
+                continue
+            done.append(key)
+            del done[:-300]
+            ch = {k: v for k, v in fields.items()
+                  if k in FIXABLE and v not in (None, "", []) and p.get(k) != v
+                  and not (k == "category" and v not in CATEGORIES)}
+            if not ch:
+                continue
+            p.update(ch)
+            if "title" in ch:
+                p.pop("cover_line_v", None)            # kapak başlığı da yeni başlıkla yeniden yazılsın
+                try:
+                    self._make_og(p)                   # paylaşım görselindeki başlık da yenilensin
+                except Exception as e:  # noqa: BLE001
+                    log.warning("Paylaşım görseli yenilenemedi (%s): %s", p["id"], e)
+            st.save_post(p)
+            log.info("Haber düzeltildi: %s (%s)", p["id"], ", ".join(ch))
         for pid, title in (m.get("retitle") or {}).items():
             p = st.load_post(str(pid))
@@ -1317,5 +1355,6 @@
             return
         self.state["last_activity"] = iso(now_utc())
-        log.info("Telegram mesajı: %s", clip(text, 40))
+        # depo herkese açık, çalışma kayıtları da öyle: mesajın içeriği değil yalnızca türü yazılır
+        log.info("Telegram mesajı: %s", text.split()[0].split("@")[0][:20] if text.startswith("/") else "metin")
         self.tg.typing(chat)
 
--- a/haberbot/extract.py
+++ b/haberbot/extract.py
@@ -56,11 +56,22 @@
         return _html_cache[url]
     html = ""
+    if not url.lower().startswith(("http://", "https://")):
+        return html
     try:
         if not _allowed(url):
             log.info("robots.txt izin vermiyor, sayfa okunmadı: %s", url)
         else:
-            r = requests.get(url, headers={"User-Agent": UA, "Accept": "text/html"}, timeout=15)
+            r = requests.get(url, headers={"User-Agent": UA, "Accept": "text/html"}, timeout=15, stream=True)
             if r.status_code < 400 and "html" in r.headers.get("content-type", "html"):
-                html = r.text[:3_000_000]
+                raw = b""
+                for chunk in r.iter_content(64 * 1024):      # en fazla 3 MB: dev ya da bitmeyen sayfa belleği doldurmasın
+                    raw += chunk
+                    if len(raw) >= 3_000_000:
+                        break
+                try:
+                    html = raw[:3_000_000].decode(r.encoding or "utf-8", errors="replace")
+                except LookupError:                           # tanınmayan karakter kümesi adı
+                    html = raw[:3_000_000].decode("utf-8", errors="replace")
+            r.close()
     except requests.RequestException as e:
         log.info("Sayfa okunamadı (%s): %s", type(e).__name__, url)
--- a/haberbot/photos.py
+++ b/haberbot/photos.py
@@ -20,4 +20,7 @@
 import requests
 from PIL import Image, ImageChops, ImageOps, ImageStat
+
+# Küçük dosyada dev çözünürlük ("sıkıştırma bombası") belleği doldurmasın: 40 MP üstü uyarı, 80 MP üstü reddedilir
+Image.MAX_IMAGE_PIXELS = 40_000_000
 
 from .extract import UA, fetch_html
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -354,6 +354,6 @@
 - tags: 3–6 tags that people search for: companies, products, models, games, car models, technologies, places (e.g. "Apple", "iPhone 18", "TOGG", "elektrikli otomobil", "GTA 6", "OpenAI"). Use the official spelling consistently. If the story is mainly about Turkey or a Turkish company, include the tag "Türkiye". Never use generic words like "teknoloji", "yapay zeka", "oyun", "otomobil", "girişim", "haber", and never use the names of news outlets (TechCrunch, The Verge, Webrazzi…).
 - focus_keyword: as described above.
-- seo_title: ≤58 characters, the title shown in Google results. Starts with the focus_keyword or puts it near the start; specific and compelling but not clickbait; may differ from title. Sentence case. No site name, no trailing period.
-- meta_description: 140–156 characters, one or two sentences in active voice that contain the focus_keyword and tell the reader exactly what they will learn. No quotes, no emojis.
+- seo_title: ≤58 characters, the title shown in Google results. Starts with the focus_keyword or puts it near the start; specific and compelling but not clickbait; may differ from title. Sentence case. A complete phrase with its verb: never cut a word or end with "…". No site name, no trailing period.
+- meta_description: 140–156 characters, one or two sentences in active voice that contain the focus_keyword and tell the reader exactly what they will learn. No quotes, no emojis. Never end with filler such as "Detaylar haberimizde." or "İşte detaylar.": every sentence must carry information.
 - slug: URL slug in lowercase ASCII (convert ç→c, ğ→g, ı→i, ö→o, ş→s, ü→u), words separated by hyphens, 3–7 words, ≤60 characters, based on the focus_keyword plus the key action (e.g. "togg-t10f-avrupa-satis-fiyati-aciklandi"). No stop-word padding, no dates.
 - image_alt: ≤120 characters Turkish alt text for the cover image: briefly describe the visual metaphor from visual_scene and relate it to the news topic (e.g. "Buzlu cam küplerden yükselen grafik: girişimin 25 milyon dolarlık yatırımını temsil eden görsel").
@@ -446,6 +446,6 @@
 Do NOT change the article. Produce search metadata in natural Türkiye Türkçesi that is faithful to the article — never add facts that are not in it.
 - focus_keyword: the 2–4 word Turkish phrase a reader would most likely type into Google to find this news, built around the main entity.
-- seo_title: ≤58 characters, starts with or contains the focus_keyword near the start, specific, sentence case (only first word and proper nouns capitalized), no clickbait, no site name, no trailing period.
-- meta_description: 140–156 characters, active voice, contains the focus_keyword, tells the reader what they will learn. No quotes, no emojis.
+- seo_title: ≤58 characters, starts with or contains the focus_keyword near the start, specific, sentence case (only first word and proper nouns capitalized), no clickbait, a complete phrase (never cut a word or end with "…"), no site name, no trailing period.
+- meta_description: 140–156 characters, active voice, contains the focus_keyword, tells the reader what they will learn. No quotes, no emojis, no filler such as "Detaylar haberimizde." or "İşte detaylar.".
 - image_alt: ≤120 characters, describes the cover image (described in VISUAL) and relates it to the news topic.
 - tags: 3–6 searchable entities (companies, products, models, technologies, places) with official spelling and correct Turkish characters. Never generic words like "teknoloji", "yapay zeka", "oyun", "otomobil", and never news outlet names."""
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -18,5 +18,5 @@
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "19"
+ASSET_V = "20"
 FOREIGN_PRICE = re.compile(r"(?=.*fiyat)(?=.*(\$|€|£|¥|dolar|euro|avro|sterlin|yuan|yen\b))", re.I)
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
@@ -28,5 +28,6 @@
     out = markdown.markdown(safe, extensions=["sane_lists"], output_format="html")
     out = re.sub(r'href="(?!https?://)[^"]*"', 'href="#"', out)
-    out = out.replace('<a href="http', '<a rel="noopener" target="_blank" href="http')
+    out = re.sub(r"<img\b[^>]*>", "", out)          # metne dışarıdan görsel gömülmez (fotoğraflar ayrı, kaynaklı eklenir)
+    out = out.replace('<a href="http', '<a rel="noopener nofollow" target="_blank" href="http')
     out = WHY_RE.sub(r'<aside class="why"><strong>Neden önemli?</strong><p>\1</p></aside>', out)
     # Metindeki başlıklar sayfanın H1'i ile yarışmasın: hepsi H2, bağlantılanabilir
@@ -35,4 +36,41 @@
 
 
+FILLER_RE = re.compile(r"^(?:(?:tüm |bütün )?(?:detaylar|ayrıntılar)\b.*haberimizde|.*\bhaberimizde|[İi]şte detaylar)[.!]?$", re.I)
+CUT_END = re.compile(r"[\wçğıöşüÇĞİÖŞÜ]+$")
+
+
+def clean_meta(meta: str) -> str:
+    """Açıklamanın sonundaki "Detaylar haberimizde." gibi boş cümleyi at (kalan metin yeterince uzunsa)."""
+    meta = re.sub(r"\s+", " ", meta or "").strip()
+    parts = re.split(r"(?<=[.!?])\s+", meta)
+    if len(parts) > 1 and FILLER_RE.match(parts[-1].strip()):
+        rest = " ".join(parts[:-1]).strip()
+        if len(rest) >= 80:
+            return rest
+    return meta
+
+
+def seo_title_of(p: dict, title: str, short: str) -> str:
+    """Arama sonucu başlığı: yazarın SEO başlığı yarım kalmışsa ("…hazırlan", "…" ile biten) haber başlığına dönülür."""
+    s = re.sub(r"\s+", " ", p.get("seo_title") or "").strip()
+    words = set(re.findall(r"[\wçğıöşü]+", f"{title} {short}".lower()))
+    last = (CUT_END.findall(s.lower()) or [""])[0]
+    cut = (not s or s.endswith(("…", "...")) or len(s) > 62
+           or (last and last not in words and any(w.startswith(last) and w != last for w in words)))
+    if not cut:
+        return s
+    for cand in (title, short):
+        cand = (cand or "").strip()
+        if cand and len(cand) <= 62:
+            return cand
+    return clip(short or title, 62)
+
+
+def weburl(u) -> str:
+    """Dış bağlantı yalnızca http(s) olabilir (javascript: gibi adresler bağlantıya dönüşmez)."""
+    u = str(u or "").strip()
+    return u if re.match(r"https?://", u, re.I) else "#"
+
+
 BLOCK_RE = re.compile(r"<(aside|blockquote|ul|ol|table|pre|figure)\b.*?</\1>", re.S)
 
@@ -41,5 +79,6 @@
     """Haberin içine yerleşen fotoğraf: kaynağı altında."""
     e = lambda v: htmlmod.escape(str(v or ""), quote=True)  # noqa: E731
-    remote = ' referrerpolicy="no-referrer" onerror="this.closest(\'figure\').remove()"' if ph.get("remote") else ""
+    # kaynağından gösterilen fotoğraf açılmazsa site.js figürü kaldırır (satır içi betik yok: içerik güvenlik politikası)
+    remote = ' referrerpolicy="no-referrer" data-remote' if ph.get("remote") else ""
     cap = (f'<figcaption><a href="{e(ph.get("page"))}" rel="noopener nofollow" target="_blank">Görsel: {e(ph.get("credit"))}</a>'
            f'</figcaption>' if ph.get("credit") else "")
@@ -209,4 +248,5 @@
             trim_blocks=True, lstrip_blocks=True,
         )
+        self.env.filters["weburl"] = weburl
 
     def _post_view(self, p: dict) -> dict:
@@ -219,6 +259,6 @@
         short = p.get("short_title") or title
         summary = p.get("summary", "")
-        seo_title = clip(p.get("seo_title") or short or title, 62)
-        meta = p.get("meta_description") or ""
+        seo_title = seo_title_of(p, title, short)
+        meta = clean_meta(p.get("meta_description") or "")
         if len(meta) < 70:  # yedek: özet + ilk paragraf
             meta = summary if len(summary) >= 110 else f"{summary} {plain(p.get('body', ''))}"
@@ -250,5 +290,5 @@
             # rakam kapakta yazıyorsa "öne çıkanlar" kutusunda tekrar edilmez
             "stat_on_cover": False,   # sitede görsellerin üstünde yazı yok: rakam "öne çıkanlar" kutusunda görünür
-            "img_alt": clip(p.get("image_alt") or f"{short}: habere ait görsel", 125),
+            "img_alt": self._alt(p, disp, short),
             "seo_title": seo_title,
             "meta_description": clip(meta, 158),
@@ -304,4 +344,20 @@
         return out
 
+    @staticmethod
+    def _alt(p: dict, disp: dict, short: str) -> str:
+        """Görselin alt metni gösterilen görsele göre: image_alt yalnızca yapay zeka görselini anlatır (çizim tarifinden
+        yazılır); gerçek fotoğrafta kaynağın kendi açıklaması (makulse) ya da haber + fotoğraf sahibi; renk zemininde
+        başlık (zemin süs, okuyucuya bir şey anlatmaz)."""
+        kind = disp.get("kind")
+        if kind == "image":
+            return clip(p.get("image_alt") or f"{short}: temsili görsel", 125)
+        if kind == "photo":
+            rec = next((r for r in p.get("photos") or [] if r.get("file") == disp.get("file")), {})
+            a = re.sub(r"\s+", " ", str(rec.get("alt") or "")).strip()
+            if 20 <= len(a) <= 125 and a.count(",") <= 2 and not re.search(r"\.(jpe?g|png|webp)\b", a, re.I):
+                return a
+            return clip(f"{short}: {disp.get('credit') or 'habere ait'} fotoğrafı", 125)
+        return clip(short, 125)
+
     def _display(self, p: dict) -> dict:
         """Sitede görünen görsel — üstünde yazı yok, başlık sayfada HTML olarak durur (tek parça görünüm):
@@ -349,5 +405,5 @@
         self._write(rel, f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>{name}</title>'
                          f'<link rel="canonical" href="{t}"><meta http-equiv="refresh" content="0; url={t}">'
-                         f'<script>location.replace({json.dumps(target)} + location.hash)</script></head>'
+                         f'<script src="{self.base}/static/go.js"></script></head>'
                          f'<body><a href="{t}">{name}</a></body></html>')
 
--- a/haberbot/sources.py
+++ b/haberbot/sources.py
@@ -161,4 +161,18 @@
 
 
+MAX_FEED_BYTES = 5_000_000
+
+
+def read_capped(r, limit: int) -> bytes:
+    """Yanıtı parça parça oku, sınırı aşınca dur (çok büyük ya da bitmeyen yanıt belleği doldurmasın)."""
+    buf = bytearray()
+    for chunk in r.iter_content(64 * 1024):
+        buf += chunk
+        if len(buf) >= limit:
+            break
+    r.close()
+    return bytes(buf[:limit])
+
+
 def _fetch(url: str, timeout: int = 15, browser: bool = False) -> bytes:
     headers = {"User-Agent": BROWSER_UA if browser else UA,
@@ -166,7 +180,7 @@
     if browser:
         headers["Accept-Language"] = "tr-TR,tr;q=0.9,en;q=0.8"
-    r = requests.get(url, headers=headers, timeout=timeout)
+    r = requests.get(url, headers=headers, timeout=timeout, stream=True)
     r.raise_for_status()
-    return r.content[:5_000_000]
+    return read_capped(r, MAX_FEED_BYTES)
 
 
@@ -226,4 +240,6 @@
                     continue
                 link = e["link"].strip()
+                if not re.match(r"https?://", link, re.I):   # javascript:, data: vb. adresler haber bağlantısı olamaz
+                    continue
                 credit, credit_url = src["name"], link
                 via = None
--- a/static/site.js
+++ b/static/site.js
@@ -156,5 +156,26 @@
     var t; track.addEventListener("scroll", function () { clearTimeout(t); t = setTimeout(update, 60); }, { passive: true });
     track.addEventListener("keydown", function (e) { if (e.key === "ArrowRight") go(idx() + 1); if (e.key === "ArrowLeft") go(idx() - 1); });
+    g.addEventListener("gal:update", update);
     update();
+  });
+
+  // Kaynağından gösterilen fotoğraf açılmazsa yeri boş kalmasın: fotoğraf (galeride küçük resmiyle birlikte) kaldırılır
+  function dropImg(img) {
+    var src = img.getAttribute("src"), gal = img.closest("[data-gal]");
+    if (!gal) { var f = img.closest("figure") || img.parentNode; if (f) f.remove(); return; }
+    gal.querySelectorAll("img").forEach(function (o) {
+      if (o.getAttribute("src") === src) { var w = o.closest(".gal-slide, .gal-thumbs button"); if (w) w.remove(); }
+    });
+    if (!gal.querySelector(".gal-slide")) { gal.remove(); return; }
+    var th = gal.querySelector(".gal-thumbs");
+    if (th) { Array.prototype.forEach.call(th.children, function (b, k) { b.setAttribute("data-go", k); b.setAttribute("aria-label", (k + 1) + ". görsel"); }); if (th.children.length < 2) th.remove(); }
+    var n = gal.querySelectorAll(".gal-slide").length, t = gal.querySelector(".gal-title span");
+    if (t) t.textContent = n + " fotoğraf";
+    gal.dispatchEvent(new Event("gal:update"));
+  }
+  document.querySelectorAll("img[data-remote]").forEach(function (img) {
+    // tembel yüklenen görselde "complete" güvenilir değil: onlar için yalnızca hata olayı dinlenir
+    if (img.loading !== "lazy" && img.complete && img.naturalWidth === 0 && img.getAttribute("src")) dropImg(img);
+    else img.addEventListener("error", function () { dropImg(img); }, { once: true });
   });
 
--- a/templates/_macros.html
+++ b/templates/_macros.html
@@ -2,5 +2,5 @@
 {% macro img(p, cls='', eager=false, sizes='(min-width: 1000px) 400px, 100vw', priority=false) %}
 {% if p.disp.kind == 'art' %}
-<span class="ph-art {{ cls }}" role="img" aria-label="{{ p.img_alt }}" style="{{ p.disp.style }}; view-transition-name: v{{ p.id }}"></span>
+<span class="ph-art {{ cls }}" aria-hidden="true" style="{{ p.disp.style }}; view-transition-name: v{{ p.id }}"></span>
 {% else %}
 <img src="{{ p.img }}" alt="{{ p.img_alt }}" width="{{ p.disp.w }}" height="{{ p.disp.h }}"{% if not eager %} loading="lazy"{% endif %}{% if priority %} fetchpriority="high"{% endif %} decoding="async" class="{{ cls }}{{ ' is-fit' if p.disp.fit }}" style="object-position: {{ p.disp.focus }}; view-transition-name: v{{ p.id }}">
--- a/templates/article.html
+++ b/templates/article.html
@@ -70,5 +70,5 @@
   <figure class="art-media">
     <div class="ph">{{ img(post, eager=true, sizes='(min-width: 880px) 840px, 100vw', priority=true) }}
-      {% if cp and cp.credit %}<a class="gal-credit" href="{{ cp.page or post.sources[0].url }}" rel="noopener nofollow" target="_blank">Görsel: {{ cp.credit }}</a>{% endif %}
+      {% if cp and cp.credit %}<a class="gal-credit" href="{{ (cp.page or post.sources[0].url)|weburl }}" rel="noopener nofollow" target="_blank">Görsel: {{ cp.credit }}</a>{% endif %}
     </div>
     {% if post.ai_image %}<figcaption>Temsili görsel, yapay zeka ile üretilmiştir.</figcaption>{% endif %}
@@ -100,6 +100,6 @@
         {% for ph in post.slides %}
         <div class="gal-slide{{ ' fit' if ph.graphic or (ph.w / ph.h) < 1.25 }}" role="group" aria-label="{{ loop.index }} / {{ n }}">
-          <img src="{{ ph.url }}" alt="{{ ph.alt }}" width="{{ ph.w }}" height="{{ ph.h }}" decoding="async" loading="lazy"{% if ph.remote %} referrerpolicy="no-referrer" onerror="this.parentNode.remove()"{% endif %}>
-          {% if ph.credit %}<a class="gal-credit" href="{{ ph.page or post.sources[0].url }}" rel="noopener nofollow" target="_blank">Görsel: {{ ph.credit }}</a>{% endif %}
+          <img src="{{ ph.url }}" alt="{{ ph.alt }}" width="{{ ph.w }}" height="{{ ph.h }}" decoding="async" loading="lazy"{% if ph.remote %} referrerpolicy="no-referrer" data-remote{% endif %}>
+          {% if ph.credit %}<a class="gal-credit" href="{{ (ph.page or post.sources[0].url)|weburl }}" rel="noopener nofollow" target="_blank">Görsel: {{ ph.credit }}</a>{% endif %}
         </div>
         {% endfor %}
@@ -112,5 +112,5 @@
     <div class="gal-thumbs">
       {% for ph in post.slides %}
-      <button type="button" data-go="{{ loop.index0 }}" aria-label="{{ loop.index }}. görsel"{% if loop.first %} aria-current="true"{% endif %}><img src="{{ ph.url }}" alt="" loading="lazy" decoding="async"{% if ph.remote %} referrerpolicy="no-referrer" onerror="this.parentNode.remove()"{% endif %}></button>
+      <button type="button" data-go="{{ loop.index0 }}" aria-label="{{ loop.index }}. görsel"{% if loop.first %} aria-current="true"{% endif %}><img src="{{ ph.url }}" alt="" loading="lazy" decoding="async"{% if ph.remote %} referrerpolicy="no-referrer" data-remote{% endif %}></button>
       {% endfor %}
     </div>
@@ -132,5 +132,5 @@
     <ol>
       {% for s in post.sources %}
-      <li><a href="{{ s.url }}" rel="noopener" target="_blank">
+      <li><a href="{{ s.url|weburl }}" rel="noopener" target="_blank">
         <span><span class="s-name">{{ s.name }}</span>{% if s.via %} <span class="muted">({{ s.via }} üzerinden)</span>{% endif %}<span class="s-title">{{ s.title }}</span></span>
         <span class="s-go" aria-hidden="true">↗</span>
@@ -142,6 +142,6 @@
       {%- if post.publish_mode == 'auto' %} ve yayın masasının doğruluk kuralları çerçevesinde otomatik yayımlanmıştır.{% else %} ve editör onayıyla yayımlanmıştır.{% endif %}
       {% if post.has_photo %}Fotoğraflar, altlarında belirtilen kaynaklara aittir.{% endif %}
-      Ayrıntılar ve orijinal ifadeler için kaynaklara başvurun.{% if post.updated_str %} Son güncelleme: {{ post.updated_str }}.{% endif %}
-      Bir hata görürseniz <a href="{{ site.base }}/iletisim/">bize bildirin</a>.
+      Ayrıntılar ve orijinal ifadeler için kaynaklara bakabilirsin.{% if post.updated_str %} Son güncelleme: {{ post.updated_str }}.{% endif %}
+      Bir hata görürsen <a href="{{ site.base }}/iletisim/">bize bildir</a>.
     </p>
   </section>
--- a/templates/base.html
+++ b/templates/base.html
@@ -77,5 +77,5 @@
       <a class="brand" href="{{ site.base }}/">{% if site.logo_svg %}<img class="wordmark" src="{{ site.logo_svg }}?v={{ site.asset_v }}" alt="{{ site.name }}" width="105" height="28" loading="lazy">{% else %}<span class="mark" aria-hidden="true"></span>{{ site.name }}{% endif %}</a>
       <p>{{ site.tagline }}</p>
-      <p class="foot-note">Haberler, dayandığı kaynaklardan yapay zeka yardımıyla Türkçe derlenir ve editör denetiminden geçer. Her haberde kaynak adıyla ve bağlantısıyla, her fotoğrafta sahibi belirtilir.</p>
+      <p class="foot-note">Haberler, dayandığı kaynaklardan yapay zeka destekli yayın masasında Türkçe derlenir; yayındaki haberler editör tarafından izlenir, hatalılar düzeltilir. Her haberde kaynak adıyla ve bağlantısıyla, her fotoğrafta sahibi belirtilir.</p>
     </div>
     <nav class="foot-col" aria-label="Kategoriler">
--- a/templates/index.html
+++ b/templates/index.html
@@ -121,5 +121,5 @@
   <section class="about-note wrap" aria-labelledby="h-hakkinda">
     <h2 id="h-hakkinda">{{ site.name }} nedir?</h2>
-    <p>{{ site.name }}, dünyada ve Türkiye'de yeni olan her şeyi Türkçe olarak takip eden bir teknoloji haber sitesidir. Apple, Samsung, Google ve OpenAI gibi şirketlerin resmi duyurularını; teknoloji, otomobil ve oyun dünyasının saygın yayınlarını ve Türkiye'nin teknoloji basınını düzenli olarak tarar. Yeni tanıtılan ürünleri, girişim hikâyelerini, ilk kez denenen teknolojileri, yapay zekanın yeni özelliklerini, otomobil ve oyun dünyasındaki gelişmeleri sade bir dille, her zaman orijinal kaynağıyla aktarır. <a href="{{ site.base }}/hakkinda/">Yayın ilkelerimiz</a></p>
+    <p>{{ site.name }}, dünyadan ve Türkiye'den teknolojideki önemli gelişmeleri Türkçe ve kaynağıyla aktaran bir haber sitesidir. Apple, Samsung, Google ve OpenAI gibi şirketlerin resmi duyurularını; teknoloji, otomobil ve oyun dünyasının saygın yayınlarını ve Türkiye'nin teknoloji basınını düzenli olarak tarar. Yeni ürünleri, yapay zeka gelişmelerini, girişim haberlerini, otomobil ve oyun dünyasını sade bir dille anlatır; her haberde orijinal kaynağı adıyla ve bağlantısıyla gösterir. <a href="{{ site.base }}/hakkinda/">Yayın ilkelerimiz</a></p>
   </section>
 {% endif %}
--- a/templates/privacy.html
+++ b/templates/privacy.html
@@ -22,9 +22,10 @@
   <p>Hangi haberlerin okunduğunu görmek için Cloudflare Web Analytics kullanıyoruz. Bu hizmet çerez kullanmaz, cihazında bilgi saklamaz ve ziyaretçileri tek tek tanımlamaz; yalnızca toplam sayıları (sayfa görüntüleme, ülke, cihaz türü, siteye nereden gelindiği, sayfa hızı) gösterir.</p>
   <h3>3. Cihazında tutulan bilgiler</h3>
-  <p>Okuduğun haberleri "Okundu" diye işaretlemek, son ziyaretinden beri kaç yeni haber çıktığını göstermek ve manşette daha önce gördüğün haberleri geriye almak için tarayıcının yerel depolama alanında haber kimlikleri ve son ziyaret zamanın tutulur. Bu bilgiler cihazından çıkmaz, bize ya da başka birine gönderilmez. Tarayıcının site verilerini silerek istediğin zaman kaldırabilirsin.</p>
+  <p>Okuduğun haberleri "Okundu" diye işaretlemek, son ziyaretinden beri kaç yeni haber çıktığını göstermek ve manşette daha önce gördüğün haberleri sona almak için tarayıcının yerel depolama alanında haber kimlikleri ve son ziyaret zamanın tutulur. Bu bilgiler cihazından çıkmaz, bize ya da başka birine gönderilmez. Tarayıcının site verilerini silerek istediğin zaman kaldırabilirsin.</p>
   <h3>4. Başka sitelerden yüklenen içerikler</h3>
   <ul>
     <li><strong>Yazı tipi:</strong> Sitenin yazı tipi Google Fonts'tan yüklenir; bu sırada IP adresin Google'a iletilir.</li>
     <li><strong>Fotoğraflar:</strong> Haberlerdeki bazı fotoğraflar, haberin kaynağı olan sitelerden doğrudan gösterilir; bu sitelere IP adresin iletilebilir.</li>
+    <li><strong>Piyasa verileri:</strong> Üst banttaki döviz, altın, BIST 100 ve Bitcoin verileri tarayıcın tarafından doğrudan Truncgil Finans, Frankfurter ve Binance hizmetlerinden alınır; bu sırada IP adresin bu hizmetlere iletilir.</li>
     <li><strong>Paylaşım:</strong> Paylaş bağlantıları yalnızca tıklarsan ilgili platforma (Telegram, WhatsApp, X vb.) gider.</li>
   </ul>
@@ -34,5 +35,5 @@
 
   <h2>Yurt dışındaki hizmet sağlayıcılar</h2>
-  <p>Yukarıda adı geçen hizmet sağlayıcıların (GitHub, Cloudflare, Google) sunucuları Türkiye dışında bulunabilir. Teknik kayıtlar bu sağlayıcılar tarafından, hizmetin sunulması amacıyla ve kendi gizlilik politikaları çerçevesinde işlenir.</p>
+  <p>Yukarıda adı geçen hizmet sağlayıcıların (GitHub, Cloudflare, Google ve piyasa verisi sağlayıcıları) sunucuları Türkiye dışında bulunabilir. Teknik kayıtlar bu sağlayıcılar tarafından, hizmetin sunulması amacıyla ve kendi gizlilik politikaları çerçevesinde işlenir.</p>
 
   <h2>Hakların</h2>
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -427,4 +427,59 @@
         assert "Yayın sahibi" in cont and "Örnek Medya" in cont and "İstanbul" in cont
 
+def test_launch_audit_fixes():
+    from haberbot.site import clean_meta, figure_html, render_body, seo_title_of, weburl
+    from haberbot.sources import _load_source  # noqa: F401  (modül yüklenebiliyor)
+    long = "Apple yeni Mac serisini duyurdu; fiyatlar, ön sipariş tarihi ve teslimat takvimi de açıklandı."
+    assert clean_meta(long + " Detaylar haberimizde.") == long
+    assert clean_meta(long + " İşte detaylar.") == long
+    assert clean_meta("Kısa açıklama. Detaylar haberimizde.") == "Kısa açıklama. Detaylar haberimizde."
+    assert seo_title_of({"seo_title": "OpenAI Apple'a dava açtı: Bilgiler sızdırıldı iddi"},
+                        "OpenAI Apple'a dava açtı: Gizli bilgilerin sızdırıldığı iddiası", "OpenAI Apple davası") == \
+        "OpenAI Apple davası"                                        # başlık 62'yi aşıyor: kısa başlık
+    assert seo_title_of({"seo_title": "Apple yeni iPad tanıttı"}, "Apple yeni iPad'i tanıttı", "") == "Apple yeni iPad tanıttı"
+    assert weburl("javascript:alert(1)") == "#" and weburl("https://a.com/x") == "https://a.com/x"
+    body = render_body("Metin ![x](https://kotu.com/takip.png) ve [bağlantı](https://a.com) [kötü](javascript:alert(1))")
+    assert "<img" not in body and 'rel="noopener nofollow"' in body and "javascript:" not in body
+    fig = figure_html({"url": "https://k.com/a.jpg", "remote": True, "credit": "K", "page": "https://k.com"})
+    assert "data-remote" in fig and "onerror" not in fig
+    with _App() as (cfg, a):
+        a.store.save_post(_post(1, 3, title="İphone Duo tamir ücretleri açıklandı"))
+        a.store.save_post(_post(2, 4, title="Yeni MacBook Pro tasarımı ortaya çıktı"))
+        a.store.save_post(_post(3, 5, photos=[{"file": "p03-g0.webp", "src": "https://k.com/a.jpg", "remote": True,
+                                                "credit": "K", "page": "https://k.com", "w": 1600, "h": 900}]))
+        cfg.raw["maintenance"] = {"unpublish": ["p02"],
+                                  "fix_posts": {"p01": {"title": "iPhone Duo tamir ücretleri açıklandı",
+                                                        "category": "gaming", "url": "https://kotu.com"},
+                                                "p03": {"category": "olmayan-kategori"}}}
+        a.apply_maintenance()
+        p1 = a.store.load_post("p01")
+        assert a.store.load_post("p02") is None
+        assert p1["title"] == "iPhone Duo tamir ücretleri açıklandı" and p1["category"] == "gaming" and "url" not in p1
+        assert a.store.load_post("p03")["category"] == "teknoloji"
+        p1["title"] = "Bot sonradan güncelledi"
+        a.store.save_post(p1)
+        a.apply_maintenance()                                       # düzeltme bir kez uygulanır, güncellemeyi ezmez
+        assert a.store.load_post("p01")["title"] == "Bot sonradan güncelledi"
+        SiteBuilder(cfg).build()
+        html = "".join(f.read_text(encoding="utf-8") for f in cfg.out_dir.rglob("*.html"))
+        assert "onerror=" not in html                                # içerik güvenlik politikasına uygun: satır içi betik yok
+        import re as _re
+        assert not _re.search(r"<script(?![^>]*(src=|application/ld\+json))", html)
+
+
+def test_feed_links_must_be_http():
+    import haberbot.sources as srcmod
+    with _App() as (cfg, a):
+        cfg.raw["sources"] = [{"name": "Deneme", "url": "https://d.com/rss", "kind": "media"}]
+        old = srcmod._load_source
+        srcmod._load_source = lambda c, s: [
+            {"title": "Zararlı bağlantılı başlık burada", "link": "javascript:alert(1)", "summary": "", "published": None},
+            {"title": "Normal bağlantılı haber başlığı", "link": "https://d.com/haber", "summary": "", "published": None}]
+        try:
+            items = srcmod.fetch_all(cfg, a.store)
+        finally:
+            srcmod._load_source = old
+        assert [i["url"] for i in items] == ["https://d.com/haber"]
+
 if __name__ == "__main__":
     for name, fn in list(globals().items()):
@@@SM@@@ FILE templates/about.html
{% extends "base.html" %}
{% block title %}Hakkında ve yayın ilkeleri | {{ site.name }}{% endblock %}
{% block description %}{{ site.name }} nasıl çalışır? Kaynak gösterme, doğruluk ve düzeltme ilkelerimiz, takip ettiğimiz teknoloji kaynakları.{% endblock %}
{% block main %}
<header class="page-head wrap" style="--c:#6E6E73">
  <span class="eyebrow">Hakkında</span>
  <h1>Kaynağıyla,<br>sakin ve net.</h1>
  <p>{{ site.description }}</p>
</header>
<article class="narrow prose">
  <h2>Nasıl çalışıyoruz?</h2>
  <p>{{ site.name }}, teknoloji şirketlerinin resmi duyurularını; dünyanın ve Türkiye'nin saygın teknoloji, girişim, otomobil ve oyun yayınlarını düzenli olarak tarar. Gerçekten yeni ve önemli olan gelişmeler yapay zeka destekli yayın masasında seçilir ve Türkçe olarak özgün biçimde yazılır. Haberlerin bir kısmı doğruluk kurallarına göre otomatik, bir kısmı editör onayıyla yayımlanır; hangisi olduğu her haberin altında yazar.</p>
  <h2 id="ilkeler">Yayın ilkelerimiz</h2>
  <ul>
    <li><strong>Her haberde kaynak.</strong> Haberin dayandığı tüm kaynaklar adıyla ve bağlantısıyla belirtilir.</li>
    <li><strong>Kopyalama yok.</strong> Kaynak metinler çevrilip aktarılmaz; bilgiler özetlenip kendi cümlelerimizle yazılır.</li>
    <li><strong>Uydurma yok.</strong> Kaynaklarda olmayan rakam, tarih, alıntı ya da iddia eklenmez. Doğrulanmamış bilgiler kaynağına atfedilir.</li>
    <li><strong>Fotoğraflar kaynağıyla.</strong> Haberlerdeki fotoğraflar, öncelikle ilgili şirketin basın için yayımladığı görsellerdir; bunlar yoksa haberin kaynağında yayımlanan görseller kullanılır. Her fotoğrafın altında kaynağı ve bağlantısı yer alır. Fotoğraf bulunamayan haberlerde habere özel renkli bir zemin kullanılır; yapay zeka ile üretilmiş temsili görseller altında belirtilir.</li>
    <li><strong>Kaldırma talepleri.</strong> Bir fotoğrafın ya da metnin hak sahibiysen ve kaldırılmasını istiyorsan {% if site.contact_email %}<strong>{{ site.contact_email }}</strong> adresine{% else %}bize{% endif %} yaz; talebini hızla değerlendiririz.</li>
    <li><strong>Yapay zeka destekli yayın masası.</strong> Haberler yapay zeka destekli yayın masasında seçilir ve yazılır; bu durum her haberin altında belirtilir. Doğrulanmamış iddialar, söylentiler ve kaynakları çelişen haberler yayımlanmaz; resmi olmayan bilgiler ancak kaynağına açıkça atfedilerek aktarılır. Editör, yayındaki haberleri izler; hatalı bulunanları düzeltir ya da kaldırır.</li>
    <li><strong>Düzeltme.</strong> Hatalı bir bilgi fark edersek haberi güncelleriz ya da kaldırırız.</li>
  </ul>
  <h2>Takip ettiğimiz kaynaklar</h2>
  <p>{% for s in sources %}{{ s.name }}{{ ', ' if not loop.last }}{% endfor %}.</p>
  <h2>İletişim</h2>
  <p>{% if site.contact_email %}Hata bildirimi, öneri ve telif talepleri için: <strong>{{ site.contact_email }}</strong>. {% endif %}Künye ve ayrıntılar: <a href="{{ site.base }}/iletisim/">İletişim ve künye</a> · <a href="{{ site.base }}/gizlilik/">Gizlilik ve çerez politikası</a>.</p>
</article>
{% endblock %}
@@@SM@@@ FILE static/go.js
// Eski adres sayfası: kanonik adrese hemen geç (#bölüm korunur). Satır içi betik yok: içerik güvenlik politikası.
location.replace(document.querySelector('link[rel="canonical"]').href + location.hash);
@@@SM@@@ SHA
ceb932a60f078778f0e5e187119b593a76bf86916ba584473adcd2caa57fd645 config.yaml
d7665536b07d6e02d16ed3e0bcccc3af57b5092507e7c5174c852f514c5063a4 haberbot/app.py
80162037db1b5bdb946cd95a6cc7ac5be20df91cd3d6478a2d928387eeaaec4a haberbot/extract.py
454ce1b28cded2f1e32595ed2af5a7b876a4e39c4941d7c582da828dd71f8984 haberbot/photos.py
2b7a7637a773bffef3da85fec9f0fc74989e38acbc8cd5742c45b7814f5de182 haberbot/prompts.py
a22f828637831b107cc9a6ed72a8f87fab19111ff6efc78002223cbdb108c6d5 haberbot/site.py
7936ba8ef6d16f585fc7773c4fd513453ded3b785e925979eda2a6583bfa26aa haberbot/sources.py
86d79ed7c8d2a73a56982a3e4f373ffd91b9f5b112d97bc4238d57a2f057f3e7 static/site.js
986784f33383e87767b5e0813a30b7dc1f03b4986ef80ebc446d17beb2d57bbe templates/_macros.html
1288d45696bb84b9d54b9b65117015653a359874656bf43e6f695e8e8ae43ee2 templates/about.html
3423db173f35be4b87ba008cd9a2fd136983b2ebc950ec769316a8a1894f9388 templates/article.html
c7d24f914e2c02158bcca32e9eb4d14b7bb049a4cbc2c0925d5cea31707fe968 templates/base.html
82991c273f71114096353a169721f92bf62b8bccf5474e8a3b63821ab3ef9201 templates/index.html
633debe6db4d711dbda0697805c23a9cc2c5b4318622e05f97aaa07601f55f08 templates/privacy.html
9f2780379389a4e641d5215bde2fca1b7d3164f56790ec94e10d659a5cdabe41 tests/test_home.py
5a6b8cd1f021afb937a80e127cb08d9eb8fdd4bb62b6c630e9e68cba8766b4a4 static/go.js
