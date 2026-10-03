SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -22,5 +22,5 @@
 from .sources import fetch_all
 from .store import Store
-from .textfix import Fixer, entity_keys, is_car_story
+from .textfix import Fixer, entity_keys, is_car_story, looks_english
 from .telegram import MockTelegram, Telegram, TelegramError
 from .util import (clip, hours_since, iso, local, log, now_utc, short_hash, slugify,
@@ -604,5 +604,6 @@
         return bool((p.get("cover_headline") and p.get("cover_line_v") == COVERLINE_V) or p.get("cover_line_skip"))
 
-    def _write(self, sources: list[dict], previous: dict | None = None, instruction: str | None = None) -> dict:
+    def _write(self, sources: list[dict], previous: dict | None = None, instruction: str | None = None,
+               _retry: bool = True) -> dict:
         cfg = self.cfg
         out = self.llm.json(
@@ -640,6 +641,23 @@
         if res.get("cover_headline"):
             res["cover_line_v"] = COVERLINE_V
+        if _retry and looks_english(res["title"]):   # kaynak başlığı çevrilmeden kalmış: bir kez daha yazdır
+            log.warning("Başlık İngilizce kaldı, yeniden yazılıyor: %s", res["title"])
+            fix = "Başlık ve metnin tamamı Türkçe olmalı; kaynağın İngilizce başlığını olduğu gibi kullanma."
+            return self._write(sources, previous, f"{instruction}\n{fix}" if instruction else fix, _retry=False)
         self.fixer.post(res)          # Türkçe karakter ve marka yazımı düzeltmeleri
         return res
+
+    def fix_english_titles(self) -> None:
+        """Tek seferlik: başlığı İngilizce kalmış yayındaki haberleri Türkçe yeniden yaz (adres değişmez)."""
+        if self.state.get("english_fix_v") == 1 or not self.llm:
+            return
+        self.state["english_fix_v"] = 1
+        for p in [p for p in self.store.posts() if looks_english(p.get("title", ""))][:5]:
+            try:
+                self._rewrite(p, "Başlık ve metnin tamamı Türkçe olmalı; kaynağın İngilizce başlığını olduğu gibi kullanma.",
+                              "post")
+                log.info("İngilizce başlık Türkçeleştirildi: %s → %s", p["id"], p.get("title"))
+            except Exception as e:  # noqa: BLE001
+                log.warning("İngilizce başlık düzeltilemedi (%s): %s", p["id"], e)
 
     @staticmethod
@@ -1501,5 +1519,5 @@
                 got = photos.gather(p.get("sources") or [], limit=int(self.cfg.get("images", "photo_limit", 16) or 16),
                                     per_source=int(self.cfg.get("images", "photos_per_source", 12) or 12),
-                                    skip_cover=self._no_cover_sources())
+                                    skip_cover=self._no_cover_sources(), entities=self._photo_names(p))
             except Exception as e:  # noqa: BLE001
                 log.warning("Fotoğraflar alınamadı (%s): %s", p["id"], e)
@@ -2018,4 +2036,30 @@
         d["image"] = self.vis.make_hero(d, hero)
 
+    @staticmethod
+    def _photo_names(d: dict) -> list[str]:
+        """Kaynaklarda fotoğraf yoksa Wikipedia'da aranacak adlar: haberin şirketi / ürünü / kişisi."""
+        return list(dict.fromkeys((d.get("entities") or []) + (d.get("tags") or [])[:3]))
+
+    @staticmethod
+    def _has_display_photo(p: dict, folder) -> bool:
+        return any(r.get("file") and (r.get("w") or 0) >= 600 and (folder / r["file"]).exists() for r in p.get("photos") or [])
+
+    def fill_missing_photos(self, per_run: int = 8) -> None:
+        """Tek seferlik + sürekli: sitede fotoğrafsız görünen haberler için yeniden fotoğraf ara
+        (kaynak sayfaları, yoksa Wikipedia). Bulunamayan haber 3 gün sonra tekrar denenir."""
+        if self.cfg.mock or self.cfg.fixtures_dir or not self.cfg.get("images", "photos", True):
+            return
+        folder = self.cfg.images_dir
+        todo = [p for p in self.store.posts()
+                if not p.get("photos_removed") and (p.get("image") or {}).get("source") != "ai"
+                and not self._has_display_photo(p, folder) and hours_since(p.get("photos_filled")) > 72][:per_run]
+        for p in todo:
+            p["photos_filled"] = iso(now_utc())
+            before = len(p.get("photos") or [])
+            if self._attach_photos(p, draft=False):
+                p["updated_at"] = p.get("updated_at") or p.get("published_at")
+                log.info("Fotoğrafsız habere fotoğraf bulundu: %s (%d → %d)", p["id"], before, len(p["photos"]))
+            self.store.save_post(p)
+
     def _attach_photos(self, d: dict, draft: bool, got: list[dict] | None = None) -> bool:
         """Kaynaklardan gerçek fotoğrafları al ve kapağı üret. Bulunamazsa False."""
@@ -2027,5 +2071,5 @@
                 got = photos.gather(d.get("sources") or [], limit=int(cfg.get("images", "photo_limit", 16) or 16),
                                     per_source=int(cfg.get("images", "photos_per_source", 12) or 12),
-                                    skip_cover=self._no_cover_sources())
+                                    skip_cover=self._no_cover_sources(), entities=self._photo_names(d))
         except Exception as e:  # noqa: BLE001
             log.warning("Fotoğraflar alınamadı (%s): %s", d.get("id"), e)
@@ -2205,4 +2249,5 @@
         try:
             self.reselect_pending()
+            self.fix_english_titles()
         except Exception as e:  # noqa: BLE001
             log.exception("Bekleyen taslak seçkisi hatası: %s", e)
@@ -2226,4 +2271,5 @@
             try:
                 self.more_photos()
+                self.fill_missing_photos()
                 self.backfill_photos(int(self.cfg.get("images", "photo_backfill_per_run", 5) or 0))
             except Exception as e:  # noqa: BLE001
--- a/haberbot/photos.py
+++ b/haberbot/photos.py
@@ -16,5 +16,5 @@
 import re
 from pathlib import Path
-from urllib.parse import urljoin, urlsplit, urlunsplit
+from urllib.parse import quote, urljoin, urlsplit, urlunsplit
 
 import requests
@@ -175,7 +175,7 @@
 
 
-def fetch_image(url: str, referer: str = "", timeout: int = 20) -> Image.Image | None:
+def fetch_image(url: str, referer: str = "", timeout: int = 20, ua: str = "") -> Image.Image | None:
     try:
-        r = requests.get(url, headers={"User-Agent": UA, "Referer": referer or url,
+        r = requests.get(url, headers={"User-Agent": ua or UA, "Referer": referer or url,
                                        "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"},
                          timeout=timeout, stream=True)
@@ -243,6 +243,52 @@
 
 
+# ── yedek: Wikipedia'daki ürün / şirket / kişi görseli ─────
+WIKI_UA = "SmarityBot/1.0 (https://smarity.com.tr; haber sitesi gorsel arama)"
+GENERIC_NAMES = {"türkiye", "turkey", "yapay zeka", "ai", "elektrikli otomobil", "abd", "avrupa", "çin"}
+
+
+def _wiki_names(names: list[str]) -> list[str]:
+    """Aranacak adlar: özel adlar (büyük harf içeren), en belirgin olan önce (ürün adı şirket adından önce)."""
+    out = []
+    for n in names:
+        n = (n or "").strip()
+        if n and n.lower() not in GENERIC_NAMES and any(c.isupper() for c in n) and n not in out:
+            out.append(n)
+    return sorted(out[:5], key=lambda n: -len(n.split()))
+
+
+def wiki_photo(names: list[str]) -> dict | None:
+    """Kaynaklarda hiç fotoğraf yoksa: haberin ürününün / şirketinin / kişisinin Wikipedia görseli (kaynağıyla)."""
+    for name in _wiki_names(names):
+        for lang in ("tr", "en"):
+            try:
+                r = requests.get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(name.replace(' ', '_'))}",
+                                 headers={"User-Agent": WIKI_UA}, timeout=10)
+                if r.status_code != 200:
+                    continue
+                j = r.json()
+            except (requests.RequestException, ValueError):
+                continue
+            if j.get("type") == "disambiguation":
+                continue
+            org = j.get("originalimage") or {}
+            src = org.get("source") or ""
+            if not src or src.lower().endswith(".svg") or (org.get("width") or 0) > 2400:
+                th = (j.get("thumbnail") or {}).get("source") or ""
+                src = re.sub(r"/\d+px-", "/960px-", th) if "/thumb/" in th else src
+            if not src or src.lower().endswith(".svg"):
+                continue
+            im = fetch_image(src, "https://wikipedia.org/", ua=WIKI_UA)
+            if im is None or not usable(im):
+                continue
+            page = ((j.get("content_urls") or {}).get("desktop") or {}).get("page") or f"https://{lang}.wikipedia.org/"
+            log.info("Fotoğraf: kaynaklarda yok, Wikipedia görseli kullanıldı (%s)", name)
+            return {"image": im, "src": src, "credit": "Wikipedia", "page": page, "alt": j.get("title") or name,
+                    "kind": "wiki", **classify(im)}
+    return None
+
+
 def gather(sources: list[dict], limit: int = 16, per_source: int = 12, pages: int = 3,
-           skip_cover: set[str] | frozenset = frozenset()) -> list[dict]:
+           skip_cover: set[str] | frozenset = frozenset(), entities: list[str] | None = None) -> list[dict]:
     """Kaynaklardan fotoğraf topla. Dönen her öğe: {'image': PIL, 'src', 'credit', 'page', 'alt', 'kind', 'graphic'}
 
@@ -281,4 +327,8 @@
         if len(picked) >= limit:
             break
+    if not picked and entities:
+        w = wiki_photo(entities)
+        if w:
+            picked.append(w)
     picked.sort(key=lambda p: p["graphic"])  # kararlı sıralama: kaynak sırası korunur
     log.info("Fotoğraf: %d bulundu, %d grafik (%s)", len(picked), sum(p["graphic"] for p in picked),
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -381,4 +381,6 @@
             f"EDITOR INSTRUCTION (follow it, while keeping all accuracy rules): {instruction or 'Metni daha akıcı ve net hale getir.'}",
         ]
+    if instruction and (previous is None or previous.get("_update")):
+        parts += ["", f"EDITOR INSTRUCTION (follow it, while keeping all accuracy rules): {instruction}"]
     return "\n".join(parts)
 
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -18,5 +18,5 @@
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "14"
+ASSET_V = "15"
 FOREIGN_PRICE = re.compile(r"(?=.*fiyat)(?=.*(\$|€|£|¥|dolar|euro|avro|sterlin|yuan|yen\b))", re.I)
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
--- a/haberbot/textfix.py
+++ b/haberbot/textfix.py
@@ -220,2 +220,24 @@
         return True
     return bool(CAR_WORDS.search(d.get("title", "")))
+
+
+# ── Dil denetimi: başlık İngilizce mi kalmış? ─────────────────
+EN_WORDS = {"the", "of", "for", "on", "in", "to", "with", "and", "its", "is", "are", "a", "an", "from", "by", "at", "as",
+            "after", "says", "gets", "launches", "announces", "reveals", "adds", "pins", "focus", "reboot", "new", "will",
+            "could", "over", "into", "how", "why", "what", "customers", "business", "about", "this", "that", "now"}
+
+
+def looks_english(text: str) -> bool:
+    """Türkçe harf hiç yok ve en az iki İngilizce bağlaç/sözcük var → İngilizce."""
+    if not text or re.search(r"[çğıöşüÇĞİÖŞÜ]", text):
+        return False
+    words = re.findall(r"[a-z']+", text.lower().replace("’", "'"))
+    if set(words) & TR_WORDS:
+        return False
+    hits = [w for w in words if w in EN_WORDS or w.endswith("'s")]
+    strong = [w for w in hits if w not in {"the", "of", "a", "an"}]   # "The Last of Us" gibi adlar sayılmaz
+    return len(hits) >= 3 or (len(hits) >= 2 and bool(strong))
+
+
+TR_WORDS = {"ve", "ile", "bir", "yeni", "icin", "oldu", "geliyor", "tanitildi", "aciklandi", "sezon", "tarihi", "fiyati",
+            "fiyat", "satis", "ozellikleri", "cikti", "duyurdu", "geldi", "artik"}
--- a/static/site.js
+++ b/static/site.js
@@ -257,5 +257,6 @@
   }
 
-  // Canlı piyasa şeridi: dolar, euro, sterlin, gram altın, BIST 100, bitcoin (dakikada bir yenilenir; veri gelmezse gizli kalır)
+  // Canlı piyasalar: dolar, euro, sterlin, gram altın, BIST 100, bitcoin. Dakikada bir yenilenir;
+  // veri gelmeyen kalem gizlenir, hiç veri gelmezse şerit tamamen kaybolur.
   var mkt = document.querySelector("[data-mkt]");
   if (mkt && window.fetch && window.Promise) {
@@ -266,14 +267,20 @@
       return parseFloat(x.indexOf(",") >= 0 ? x.replace(/\./g, "").replace(",", ".") : x);   // "6.542,72" ya da "84812.33"
     };
+    var seenK = {};
     var put = function (k, val, ch, dec, pre) {
-      var li = mkt.querySelector('[data-k="' + k + '"]');
-      if (!li || !isFinite(val) || val <= 0) return false;
-      li.querySelector("b").textContent = (pre || "") + nf(val, dec);
-      var i = li.querySelector("i");
+      var it = mkt.querySelector('[data-k="' + k + '"]');
+      if (!it || !isFinite(val) || val <= 0) return false;
+      var b = it.querySelector("b"), txt = (pre || "") + nf(val, dec);
+      if (b.textContent !== txt) {
+        if (seenK[k]) { b.classList.remove("flash"); void b.offsetWidth; b.classList.add("flash"); }
+        b.textContent = txt;
+      }
+      seenK[k] = 1;
+      var i = it.querySelector("i");
       if (isFinite(ch)) {
-        i.textContent = (ch > 0.004 ? "▲" : ch < -0.004 ? "▼" : "") + "%" + nf(Math.abs(ch), 2);
+        i.textContent = (ch > 0.004 ? "▲ " : ch < -0.004 ? "▼ " : "") + "%" + nf(Math.abs(ch), 2);
         i.className = ch > 0.004 ? "up" : ch < -0.004 ? "dn" : "eq";
       } else { i.textContent = ""; }
-      li.hidden = false;
+      it.hidden = false;
       return true;
     };
@@ -284,21 +291,24 @@
     };
     var loadMkt = function () {
-      var any = false;
       var fx = get("https://finans.truncgil.com/v4/today.json?t=" + Date.now()).then(function (j) {
         [["USD", 2], ["EUR", 2], ["GBP", 2], ["GRA", 0], ["XU100", 0]].forEach(function (x) {
           var o = j[x[0]];
-          if (o && put(x[0], num(o.Selling) || num(o.Buying), num(o.Change), x[1])) any = true;
+          if (o) put(x[0], num(o.Selling) || num(o.Buying), num(o.Change), x[1]);
         });
       }).catch(function () {
         return get("https://api.frankfurter.dev/v1/latest?base=TRY&symbols=USD,EUR,GBP").then(function (j) {
-          ["USD", "EUR", "GBP"].forEach(function (k) { if (j.rates && j.rates[k] && put(k, 1 / j.rates[k], NaN, 2)) any = true; });
+          ["USD", "EUR", "GBP"].forEach(function (k) { if (j.rates && j.rates[k]) put(k, 1 / j.rates[k], NaN, 2); });
         }).catch(function () {});
       });
       var btc = get("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT").then(function (j) {
-        if (put("BTC", num(j.lastPrice), num(j.priceChangePercent), 0, "$")) any = true;
+        put("BTC", num(j.lastPrice), num(j.priceChangePercent), 0, "$");
       }).catch(function () {});
-      Promise.all([fx, btc]).then(function () { if (any) mkt.hidden = false; });
+      Promise.all([fx, btc]).then(function () {
+        if (!mkt.classList.contains("loading")) return;
+        mkt.classList.remove("loading");
+        mkt.querySelectorAll("[data-k]").forEach(function (it) { if (!seenK[it.getAttribute("data-k")]) it.hidden = true; });
+        if (!Object.keys(seenK).length) mkt.classList.add("gone");
+      });
     };
-    mkt.querySelectorAll("li").forEach(function (li) { li.hidden = true; });
     loadMkt();
     setInterval(function () { if (!document.hidden) loadMkt(); }, 60000);
--- a/static/style.css
+++ b/static/style.css
@@ -79,21 +79,44 @@
 
 /* ── ana sayfa başlığı ─────────────────── */
-.home-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px 20px; padding-block: 22px 16px; }
+.home-head { padding-block: 22px 18px; }
+.home-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px 20px; }
 .home-date { margin: 0; font-size: 15px; font-weight: 600; color: var(--ink-2); letter-spacing: -.01em; white-space: nowrap; }
-.home-day { display: flex; align-items: center; gap: 8px 18px; flex-wrap: wrap; min-width: 0; }
-/* canlı piyasa şeridi: tarihin yanında */
-.mkt { list-style: none; margin: 0; padding: 0; display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; min-width: 0;
-  font-size: 13px; font-variant-numeric: tabular-nums; }
-.mkt::-webkit-scrollbar { display: none; }
-.mkt[hidden] { display: none; }
-.mkt li { flex: none; display: inline-flex; align-items: baseline; gap: 5px; padding: 5px 10px; border-radius: 999px; background: var(--bg-alt); }
-.mkt li[hidden] { display: none; }
-.mkt span { color: var(--muted); }
-.mkt b { font-weight: 600; color: var(--ink); }
-.mkt i { font-style: normal; font-size: 12px; font-weight: 600; }
-.mkt i.up { color: #0B8A3A; } .mkt i.dn { color: #D12F2F; } .mkt i.eq { color: var(--muted); }
-@media (max-width: 799px) {
-  .home-day { width: 100%; }
-  .mkt { width: calc(100% + 16px); margin-right: -16px; padding-right: 16px; }
+/* ── canlı piyasalar: tek parça şerit, ince ayraçlar, simgeli kalemler ── */
+.mkt { margin-top: 14px; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); padding: 6px; border-radius: 18px;
+  background: var(--bg-alt); font-variant-numeric: tabular-nums; }
+.mkt.gone { display: none; }
+.mkt-item { position: relative; display: flex; align-items: center; gap: 10px; min-width: 0; padding: 9px 12px; border-radius: 13px;
+  transition: background .2s; }
+.mkt-item:hover { background: #fff; }
+.mkt-item + .mkt-item::before { content: ""; position: absolute; left: 0; top: 22%; bottom: 22%; width: 1px; background: #DCDCE1; }
+.mkt-item:hover::before, .mkt-item:hover + .mkt-item::before { opacity: 0; }
+.mkt-item[hidden] { display: none; }
+.mkt-ic { flex: none; width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; color: #fff; font-size: 14px;
+  font-weight: 700; letter-spacing: -.02em; background: linear-gradient(145deg, color-mix(in srgb, var(--ic) 78%, #fff), var(--ic));
+  box-shadow: inset 0 -1px 0 rgba(0,0,0,.12); }
+.mkt-tx { display: grid; gap: 1px; min-width: 0; }
+.mkt-n { font-size: 12px; font-weight: 500; color: var(--muted); white-space: nowrap; }
+.mkt-v { display: flex; align-items: baseline; gap: 6px; white-space: nowrap; }
+.mkt-v b { font-size: 16px; font-weight: 650; letter-spacing: -.015em; color: var(--ink); }
+.mkt-v i { font-style: normal; font-size: 11.5px; font-weight: 600; padding: 2px 6px; border-radius: 999px; line-height: 1.3; }
+.mkt-v i:empty { display: none; }
+.mkt-v i.up { color: #0A7A35; background: rgba(16, 185, 129, .14); }
+.mkt-v i.dn { color: #C92A2A; background: rgba(239, 68, 68, .12); }
+.mkt-v i.eq { color: var(--muted); background: rgba(0, 0, 0, .05); }
+.mkt-v b.flash { animation: mktflash 1.2s var(--ease); }
+@keyframes mktflash { 0% { color: var(--link); } 100% { color: var(--ink); } }
+.mkt.loading .mkt-v b { color: transparent; border-radius: 6px; background: linear-gradient(90deg, #E6E6EB 0%, #F2F2F5 50%, #E6E6EB 100%);
+  background-size: 200% 100%; animation: shimmer 1.3s linear infinite; }
+@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
+@media (max-width: 1099px) {
+  .mkt { display: flex; overflow-x: auto; scroll-snap-type: x proximity; scrollbar-width: none; gap: 0;
+    -webkit-mask-image: linear-gradient(90deg, #000 88%, transparent); mask-image: linear-gradient(90deg, #000 88%, transparent); }
+  .mkt::-webkit-scrollbar { display: none; }
+  .mkt-item { flex: none; scroll-snap-align: start; padding-right: 16px; }
+}
+@media (max-width: 599px) {
+  .mkt { margin-inline: -16px; border-radius: 0; padding-inline: 10px; }
+  .mkt-ic { width: 28px; height: 28px; font-size: 13px; }
+  .mkt-v b { font-size: 15px; }
 }
 .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
--- a/templates/index.html
+++ b/templates/index.html
@@ -24,18 +24,20 @@
 <header class="home-head wrap">
   <h1 class="sr-only">{{ site.home_h1 }}</h1>
-  <div class="home-day">
+  <div class="home-row">
     <p class="home-date"><time datetime="{{ site.built_iso[:10] }}" data-today>{{ site.today_str }}</time></p>
-    <ul class="mkt" data-mkt aria-label="Piyasalar" hidden>
-      <li data-k="USD"><span>Dolar</span><b></b><i></i></li>
-      <li data-k="EUR"><span>Euro</span><b></b><i></i></li>
-      <li data-k="GBP"><span>Sterlin</span><b></b><i></i></li>
-      <li data-k="GRA"><span>Gram altın</span><b></b><i></i></li>
-      <li data-k="XU100"><span>BIST 100</span><b></b><i></i></li>
-      <li data-k="BTC"><span>Bitcoin</span><b></b><i></i></li>
-    </ul>
+    {% if featured %}
+    <p class="live" role="status"><span class="dot" aria-hidden="true"></span>Son haber <b><time datetime="{{ latest_iso }}" data-rel data-live>{{ latest_str }}</time></b>{% if site.today_count %} · Bugün <b>{{ site.today_count }}</b> gelişme{% endif %}</p>
+    {% endif %}
   </div>
-  {% if featured %}
-  <p class="live" role="status"><span class="dot" aria-hidden="true"></span>Son haber <b><time datetime="{{ latest_iso }}" data-rel data-live>{{ latest_str }}</time></b>{% if site.today_count %} · Bugün <b>{{ site.today_count }}</b> gelişme{% endif %}</p>
-  {% endif %}
+  {# Canlı piyasalar: veri gelene kadar iskelet görünür (sayfa kaymaz), hiç veri gelmezse kaybolur #}
+  <div class="mkt loading" data-mkt role="list" aria-label="Piyasalar">
+    {% for k, name, sym, col in [("USD", "Dolar", "$", "#16A34A"), ("EUR", "Euro", "€", "#2563EB"), ("GBP", "Sterlin", "£", "#7C3AED"),
+                                 ("GRA", "Gram altın", "Au", "#C9930A"), ("XU100", "BIST 100", "B", "#E11D48"), ("BTC", "Bitcoin", "₿", "#F7931A")] %}
+    <div class="mkt-item" role="listitem" data-k="{{ k }}" style="--ic:{{ col }}">
+      <span class="mkt-ic" aria-hidden="true">{{ sym }}</span>
+      <span class="mkt-tx"><span class="mkt-n">{{ name }}</span><span class="mkt-v"><b>00,00</b><i></i></span></span>
+    </div>
+    {% endfor %}
+  </div>
 </header>
 
--- a/tests/test_photos.py
+++ b/tests/test_photos.py
@@ -13,4 +13,6 @@
 from haberbot.config import ROOT, Config  # noqa: E402
 from haberbot.util import iso, now_utc  # noqa: E402
+
+_REAL_GATHER = photos.gather          # bazı testler gather'ı geçici olarak değiştiriyor
 
 HTML = """<html><head>
@@ -241,4 +243,52 @@
 
 
+def test_wikipedia_fallback_and_missing_photo_fill():
+    assert photos._wiki_names(["Apple", "MacBook Pro", "Türkiye", "yapay zeka"]) == ["MacBook Pro", "Apple"]
+    real_gather, real_wiki = _REAL_GATHER, photos.wiki_photo
+    photos.gather = _REAL_GATHER
+    try:
+        photos.wiki_photo = lambda names: {"image": _photo("#335", seed=3), "src": "https://upload.wikimedia.org/x.jpg",
+                                           "credit": "Wikipedia", "page": "https://tr.wikipedia.org/wiki/X", "alt": "X",
+                                           "kind": "wiki", "graphic": False, "cover_ok": True}
+        got = _REAL_GATHER([], entities=["MacBook Pro"])               # kaynaklarda fotoğraf yok → Wikipedia
+        assert len(got) == 1 and got[0]["credit"] == "Wikipedia"
+        assert _REAL_GATHER([], entities=None) == []
+        with _App() as (cfg, a):
+            a.store.save_post(_post(photos_tried=iso(now_utc())))        # yakın zamanda denenmiş, yine de doldurulur
+            appmod.photos.gather = lambda *a_, **k: [photos.wiki_photo(k.get("entities"))]
+            a.fill_missing_photos()
+            p = a.store.load_post("p1")
+            assert p["photos"][0]["credit"] == "Wikipedia" and p["photos_filled"]
+            from haberbot.site import SiteBuilder
+            assert SiteBuilder(cfg)._post_view(p)["disp"]["kind"] == "photo"
+            a.fill_missing_photos()                                       # artık fotoğraflı: tekrar denenmez
+            assert a.store.load_post("p1")["photos"] == p["photos"]
+    finally:
+        photos.gather, photos.wiki_photo = real_gather, real_wiki
+        appmod.photos.gather = real_gather
+
+
+def test_english_title_is_rewritten():
+    from haberbot.textfix import looks_english
+    assert looks_english("Microsoft's Copilot reboot pins focus on business customers")
+    assert not looks_english("The Last of Us 3. sezon tarihi") and not looks_english("iPhone 18 Pro tanıtıldı")
+    with _App() as (cfg, a):
+        from haberbot.llm import MockLLM
+        a.llm = MockLLM()
+        calls = []
+        real = a.llm.json
+
+        def fake(model, system, user, schema, **k):
+            out = real(model, system, user, schema, **k)
+            calls.append(user)
+            if "body" in schema.get("properties", {}) and len(calls) == 1:
+                out["title"] = "Microsoft's Copilot reboot pins focus on business customers"
+            return out
+        a.llm.json = fake
+        res = a._write([{"credit": "Bloomberg", "kind": "media", "title": "Copilot reboot", "url": "https://b.com/x",
+                         "published": iso(now_utc()), "summary": "s", "text": "t"}])
+        assert len(calls) == 2 and "Türkçe olmalı" in calls[1] and not looks_english(res["title"])
+
+
 def test_migrate_old_layout():
     with _App() as (cfg, a):
@@@SM@@@ SHA
e99529afa64223033b6831cc322aff6927d4ee91f295cf509e9c41239f9fe992 haberbot/app.py
79ba86e70052e0ed532088000dca0cacbb7ca911f59052b8e283f987074d5253 haberbot/photos.py
929736cbeb8b34b4c79165b338390529202982912fe76394a6a8bbdd6591b01a haberbot/prompts.py
9fb4e4dc1f580b661291ce70729ac3c7bc32d7792421b985809ca3178a44a00d haberbot/site.py
19d1fde78fa0017aace98cc808877b66a724a5cfdf3055b9abf10bc39d737d31 haberbot/textfix.py
9a1a8b4d4114313bcbb13c37bd48af5fb865f195466efd5a7f3e2f699b1ec189 static/site.js
cfea8bdce5082d2a6c324974831f4a97ce89e63add596e1c00f062c7b0eb4c4d static/style.css
2a83c892f6876dd0484596a3a57ca3f38c5065a90e720b8cb3322f4b1f7d814e templates/index.html
6f087068579e83b17f3a8e6cdb4c77f1882b7d5990af93e1cd3442af31a464f9 tests/test_photos.py
