SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -77,9 +77,11 @@
 images:
   # Gerçek fotoğraflar: önce şirketin resmi görseli, yoksa kaynak haberin görselleri (kaynağı fotoğrafın altında yazar).
-  # Kapak her zaman bizim tasarımımızdır: anlamlı bir fotoğraf varsa üstüne dev rakam / isim / manşet yazılır,
-  # yoksa (ekran görüntüsü, grafik, yazılı paylaşım görseli) tipografik kapak kullanılır. Diğer fotoğraflar
-  # kaydırmalı alanda ve haberin paragrafları arasında, kaynağıyla gösterilir. Fotoğraflar hiç silinmez.
+  # Sitede görsellerin üstünde yazı yoktur: başlık bir kez, sayfada yazılır. Fotoğrafı olmayan haberde habere özel
+  # yazısız renk ağı görünür. Yazılı kapak yalnızca paylaşım görselinde (Google, WhatsApp, Instagram) kullanılır.
+  # Diğer fotoğraflar haberin paragrafları arasına, kalanlar sondaki galeriye kaynağıyla yerleşir.
   photos: true
-  photo_limit: 6                  # haber başına en fazla fotoğraf
+  photo_limit: 16                 # haber başına en fazla fotoğraf (haberin içine paragraf paragraf yerleşir)
+  photo_local: 4                  # bunların kaçı siteye kopyalanır (kalanlar kaynaktaki adresinden gösterilir)
+  photos_per_source: 12           # bir kaynak sayfasından en fazla kaç fotoğraf
   photo_backfill_per_run: 5       # eski haberlere her turda kaç tanesine fotoğraf eklensin
   # kapak: habere özel tipografik kapak (dev rakam / isim / manşet), ücretsiz (önerilen)
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -22,5 +22,5 @@
 from .sources import fetch_all
 from .store import Store
-from .textfix import Fixer, entity_keys
+from .textfix import Fixer, entity_keys, is_car_story
 from .telegram import MockTelegram, Telegram, TelegramError
 from .util import (clip, hours_since, iso, local, log, now_utc, short_hash, slugify,
@@ -539,5 +539,5 @@
                 p["updated_at"] = p.get("updated_at") or p.get("published_at")
                 self.store.save_post(p)
-                self.queue_indexnow(self.cfg.post_url(p["slug"]))
+                self.queue_indexnow(self.cfg.post_url(p))
                 log.info("Metin düzeltildi: %s (%s)", p["id"], ", ".join(changed))
 
@@ -746,5 +746,5 @@
             new = self.apply_update(d)
             if new:
-                self._send_preview({**d, "slug": new["slug"]}, "updated")
+                self._send_preview({**d, "slug": new["slug"], "path": self.cfg.post_path(new)}, "updated")
         else:
             st.save_draft(d)
@@ -782,5 +782,5 @@
             log.warning("Güncellenen haberin kapağı yenilenemedi (%s): %s", post["id"], e)
         st.save_post(post)
-        self.queue_indexnow(self.cfg.post_url(post["slug"]))
+        self.queue_indexnow(self.cfg.post_url(post))
         st.draft_path(d["id"]).unlink(missing_ok=True)
         st.bump(self.today(), "updated")
@@ -823,5 +823,7 @@
         post = {k: v for k, v in d.items() if k not in ("source_texts", "status", "policy_reason")}
         post.update({"slug": slug, "published_at": iso(now_utc()), "publish_mode": "auto" if auto else "manual"})
-        self.queue_indexnow(self.cfg.post_url(slug))
+        post.pop("path", None)
+        post["path"] = self.cfg.post_path(post)        # kalıcı adres: kategori/yıl/ay/slug
+        self.queue_indexnow(self.cfg.post_url(post))
         st.move_image_to_post(d["id"])
         img = post.get("image") or {}
@@ -835,5 +837,5 @@
         st.bump(self.today(), "published")
         st.bump(self.today(), "auto" if auto else "approved")
-        log.info("Yayınlandı: %s → %s", post["id"], self.cfg.post_url(slug))
+        log.info("Yayınlandı: %s → %s", post["id"], self.cfg.post_url(post))
         return post
 
@@ -874,5 +876,5 @@
             lines.append(f"<i>Neden sordum: {esc(d['policy_reason'])}</i>")
         if kind in ("published", "auto", "updated") and d.get("slug"):
-            lines.append(f'🔗 <a href="{esc(self.cfg.post_url(d["slug"]))}">Sitede aç</a>')
+            lines.append(f'🔗 <a href="{esc(self.cfg.post_url(d))}">Sitede aç</a>')
         cap = "\n".join(lines)
         room = 1024 - len(cap) + len("{SUMMARY}") - 5
@@ -888,5 +890,5 @@
                    {"text": "🔁 Yeniden yaz", "callback_data": f"w:{did}"}]]
             orig = self.store.load_post(d["update_of"])
-            links = ([{"text": "🔗 Mevcut haber", "url": self.cfg.post_url(orig["slug"])}] if orig else []) + \
+            links = ([{"text": "🔗 Mevcut haber", "url": self.cfg.post_url(orig)}] if orig else []) + \
                     ([{"text": "🔗 Yeni kaynak", "url": src}] if src else [])
             if links:
@@ -894,5 +896,5 @@
             return kb
         if kind == "updated":
-            return [[{"text": "🔗 Haberi aç", "url": self.cfg.post_url(d["slug"])}]] if d.get("slug") else []
+            return [[{"text": "🔗 Haberi aç", "url": self.cfg.post_url(d)}]] if d.get("slug") else []
         if kind == "pending":
             kb = [[{"text": "✅ Yayınla", "callback_data": f"p:{did}"},
@@ -905,5 +907,5 @@
             return kb
         if kind in ("published", "auto"):
-            return [[{"text": "🔗 Haberi aç", "url": self.cfg.post_url(d["slug"])},
+            return [[{"text": "🔗 Haberi aç", "url": self.cfg.post_url(d)},
                      {"text": "🗑 Kaldır", "callback_data": f"d:{did}"}],
                     [{"text": "📄 Tam metin", "callback_data": f"f:{did}"}], self._visual_buttons(d),
@@ -977,5 +979,5 @@
         if not force and not self.cfg.get("social", "send_to_telegram", True):
             return
-        url = self.cfg.post_url(post["slug"])
+        url = self.cfg.post_url(post)
         try:
             kinds = self.vis.CAROUSEL if self.vis.summary_style else ["post"]
@@ -1101,5 +1103,5 @@
                 return "Asıl haber artık yayında değil."
             policy.record(self.stats, d, ok=True)
-            self._update_preview({**d, "slug": post["slug"]}, "updated")
+            self._update_preview({**d, "slug": post["slug"], "path": self.cfg.post_path(post)}, "updated")
             return "🔄 Haber güncellendi"
         if action == "P":                     # yayınla ve manşete al
@@ -1455,4 +1457,48 @@
                 st.archive_draft(d, "rejected")
 
+    URL_V = 1
+
+    def migrate_urls(self) -> None:
+        """Tek seferlik: otomotiv kategorisi ve yeni adres yapısı (kategori/yıl/ay/slug).
+
+        Araba haberleri otomotive taşınır; her habere kalıcı adres yazılır, eski /haber/slug/ adresi yeni adrese yönlenir."""
+        st = self.state
+        if st.get("url_v") == self.URL_V:
+            return
+        moved = 0
+        for p in self.store.posts():
+            if p.get("category") in ("teknoloji", "inovasyon") and is_car_story(p):
+                p["category"] = "otomotiv"
+                moved += 1
+            if not p.get("path"):
+                p["path"] = self.cfg.post_path(p)
+                self.queue_indexnow(self.cfg.post_url(p))
+            self.store.save_post(p)
+        for d in self.store.drafts("pending"):
+            if d.get("category") in ("teknoloji", "inovasyon") and is_car_story(d):
+                d["category"] = "otomotiv"
+                self.store.save_draft(d)
+        st["url_v"] = self.URL_V
+        self.store.site_dirty = True
+        log.info("Yeni adres yapısı: tüm haberlere kalıcı adres yazıldı, %d haber otomotive taşındı", moved)
+
+    def more_photos(self, per_run: int = 3) -> None:
+        """Tek seferlik: son 6 habere daha çok fotoğraf (haberin içine paragraf paragraf yerleşir)."""
+        if self.cfg.mock or self.cfg.fixtures_dir or not self.cfg.get("images", "photos", True):
+            return
+        done = self.state.setdefault("more_photos", [])
+        if len(done) >= 6:
+            return
+        for p in self.store.posts()[:6]:
+            if p["id"] in done or per_run <= 0:
+                continue
+            done.append(p["id"])
+            per_run -= 1
+            if p.get("photos_removed") or (p.get("image") or {}).get("source") == "ai":
+                continue
+            if self._attach_photos(p, draft=False):
+                log.info("Daha çok fotoğraf: %s (%d)", p["id"], len(p["photos"]))
+                self.store.save_post(p)
+
     def reselect_pending(self) -> None:
         """Seçki ölçütleri değişince (tek seferlik): onay bekleyen yığını yeni ölçütlerle yeniden elden geçir;
@@ -1566,5 +1612,5 @@
             self.store.save_post(p)
             self.store.site_dirty = True
-            self.queue_indexnow(self.cfg.post_url(p["slug"]))
+            self.queue_indexnow(self.cfg.post_url(p))
             log.info("SEO bilgisi eklendi: %s → %s", p["id"], p["seo_title"])
 
@@ -1968,5 +2014,6 @@
             return False
         try:
-            got = photos.gather(d.get("sources") or [], limit=int(cfg.get("images", "photo_limit", 6) or 6),
+            got = photos.gather(d.get("sources") or [], limit=int(cfg.get("images", "photo_limit", 16) or 16),
+                                per_source=int(cfg.get("images", "photos_per_source", 12) or 12),
                                 skip_cover=self._no_cover_sources())
         except Exception as e:  # noqa: BLE001
@@ -1978,11 +2025,20 @@
         for f in self.store.gallery_files(d["id"], draft):
             f.unlink(missing_ok=True)
+        # İlk birkaç fotoğraf siteye kopyalanır (kapak, Telegram, Instagram bunlardan); kalanlar haberin içinde
+        # kaynaktaki adresinden gösterilir (depo ve site boyutu şişmesin).
+        keep = int(cfg.get("images", "photo_local", 4) or 4)
         recs = []
         for i, p in enumerate(got):
-            name = f"{d['id']}-g{i}.webp"
-            w, h = photos.save_webp(p["image"], folder / name, 1600, 80 if p.get("graphic") else 78)
-            recs.append({"file": name, "src": p["src"], "credit": p["credit"], "page": p["page"], "alt": p["alt"],
-                         "w": w, "h": h, "kind": p.get("kind", ""), "graphic": bool(p.get("graphic")),
-                         "cover_ok": bool(p.get("cover_ok", not p.get("graphic")))})
+            rec = {"src": p["src"], "credit": p["credit"], "page": p["page"], "alt": p["alt"], "kind": p.get("kind", ""),
+                   "graphic": bool(p.get("graphic")), "cover_ok": bool(p.get("cover_ok", not p.get("graphic")))}
+            if len([r for r in recs if r.get("file")]) < keep:
+                name = f"{d['id']}-g{len([r for r in recs if r.get('file')])}.webp"
+                w, h = photos.save_webp(p["image"], folder / name, 1600, 80 if p.get("graphic") else 78)
+                rec["file"] = name
+            else:
+                w, h = p["image"].size
+                rec["remote"] = True
+            rec.update({"w": w, "h": h})
+            recs.append(rec)
         d["photos"] = recs
         d["photos_v"] = self.PHOTOS_V
@@ -1997,4 +2053,5 @@
         draft = where == "draft"
         folder = self._photo_dir(draft)
+        remote = [r for r in d.get("photos") or [] if not r.get("file")]
         moved = []
         for i, rec in enumerate(order):
@@ -2011,5 +2068,5 @@
             t.rename(folder / rec["file"])
             recs.append(rec)
-        d["photos"] = recs
+        d["photos"] = recs + remote
         d["photos_v"] = self.PHOTOS_V
         self._build_cover(d, draft)
@@ -2132,4 +2189,8 @@
         self.expire()
         try:
+            self.migrate_urls()
+        except Exception as e:  # noqa: BLE001
+            log.exception("Adres geçişi hatası: %s", e)
+        try:
             self.reselect_pending()
         except Exception as e:  # noqa: BLE001
@@ -2153,4 +2214,5 @@
                 log.exception("Metin/ilgi puanı hatası: %s", e)
             try:
+                self.more_photos()
                 self.backfill_photos(int(self.cfg.get("images", "photo_backfill_per_run", 5) or 0))
             except Exception as e:  # noqa: BLE001
--- a/haberbot/config.py
+++ b/haberbot/config.py
@@ -15,4 +15,5 @@
     "super-zeka":   ("Süper Zeka",   "#7C5CFF"),
     "teknoloji":    ("Teknoloji",    "#326EF0"),
+    "otomotiv":     ("Otomotiv",     "#E5332A"),
     "inovasyon":    ("İnovasyon",    "#10B981"),
     "girisimcilik": ("Girişimcilik", "#F59E0B"),
@@ -26,5 +27,7 @@
                    "ChatGPT, Gemini, Claude ve yeni çıkan yapay zeka modelleri; yapay zekanın yeni özellikleri, şirketleri ve hayatımıza giren yeni kullanım alanları."),
     "teknoloji": ("Teknoloji haberleri",
-                  "Yeni tanıtılan telefonlar, bilgisayarlar, giyilebilir cihazlar ve otomobiller; Apple, Samsung, Google gibi teknoloji devleri, internet ve siber güvenlik."),
+                  "Yeni tanıtılan telefonlar, bilgisayarlar, kameralar, kulaklıklar ve giyilebilir cihazlar; Apple, Samsung, Google gibi teknoloji devleri, internet ve siber güvenlik."),
+    "otomotiv": ("Otomotiv haberleri",
+                 "Yeni otomobiller ve elektrikli araçlar, TOGG ve Türkiye'ye gelen modeller, fiyatlar, şarj ağları, otonom sürüş ve robotaksiler."),
     "inovasyon": ("İnovasyon ve bilim haberleri",
                   "İlk kez denenen teknolojiler, prototipler, robotik, uzay, enerji, batarya, otonom sürüş ve sağlık alanındaki buluşlar."),
@@ -113,6 +116,20 @@
         return bool(self.instagram_token) and bool(self.get("social", "instagram_auto", True))
 
-    def post_url(self, slug: str) -> str:
-        return f"{self.site_url}/haber/{slug}/"
+    def post_path(self, p: dict) -> str:
+        """Haberin kalıcı adresi: kategori/yıl/ay/slug (ör. teknoloji/2026/10/iphone-duo-tanitildi).
+
+        Yayında bir kez belirlenir ve post["path"] olarak saklanır; kategori sonradan değişse bile adres değişmez."""
+        if p.get("path"):
+            return p["path"]
+        from .util import local, now_utc
+        dt = local(p.get("published_at"), self.tz) or local(now_utc(), self.tz)
+        cat = p.get("category") if p.get("category") in CATEGORIES else DEFAULT_CATEGORY
+        return f"{cat}/{dt:%Y}/{dt:%m}/{p['slug']}"
+
+    def post_url(self, p) -> str:
+        """Haberin tam adresi. Eski kullanım (yalnızca slug) eski adresi verir; o adres yeni adrese yönlendirir."""
+        if isinstance(p, str):
+            return f"{self.site_url}/haber/{p}/"
+        return f"{self.site_url}/{self.post_path(p)}/"
 
 
--- a/haberbot/covers.py
+++ b/haberbot/covers.py
@@ -113,4 +113,9 @@
         ["#FEF08A", "#FACC15", "#CA8A04", "#FDE047", "#141002", "#FFFBE6"],
     ],
+    "otomotiv": [     # kırmızı
+        ["#FECACA", "#EF4444", "#B91C1C", "#FCA5A5", "#160505", "#FFF1F1"],
+        ["#FED7AA", "#F2542D", "#C2410C", "#FDBA74", "#170804", "#FFF3EC"],
+        ["#FFE4E6", "#DC2626", "#7F1D1D", "#F87171", "#0F0707", "#FFF2F2"],
+    ],
     "gaming": [       # pembe / magenta
         ["#FBCFE8", "#EC4899", "#BE185D", "#F9A8D4", "#16060F", "#FFF0F7"],
@@ -127,4 +132,16 @@
     i = _seed(d) % len(scales)
     return f"{cat or 'teknoloji'}-{i + 1}", scales[i]
+
+
+def art_style(d: dict) -> tuple[str, str]:
+    """Fotoğrafı olmayan haberler için sitede yazısız, habere özel renk ağı: (CSS arka planı, kenar rengi).
+
+    Başlık sitede HTML olarak yazılır; görselin üstünde ikinci bir başlık olmaz."""
+    _, pal = palette_for(d)
+    rnd = random.Random(_seed(d) + 7)
+    spots = [(rnd.randint(0, 35), rnd.randint(0, 40), pal[0], 55), (rnd.randint(65, 100), rnd.randint(0, 45), pal[3], 60),
+             (rnd.randint(25, 75), rnd.randint(60, 100), pal[1], 70)]
+    layers = [f"radial-gradient(circle at {x}% {y}%, {c} 0, {c}00 {r}%)" for x, y, c, r in spots]
+    return f"background:{', '.join(layers)}, linear-gradient(135deg, {pal[2]}, {pal[4]})", pal[4]
 
 
--- a/haberbot/photos.py
+++ b/haberbot/photos.py
@@ -94,5 +94,5 @@
 
 
-def candidates(html: str, base_url: str, limit: int = 14) -> list[dict]:
+def candidates(html: str, base_url: str, limit: int = 48) -> list[dict]:
     """Sayfadaki fotoğraf adayları: paylaşım görseli, yapılandırılmış veri, metin içi fotoğraflar."""
     from bs4 import BeautifulSoup
@@ -243,5 +243,5 @@
 
 
-def gather(sources: list[dict], limit: int = 6, per_source: int = 4, pages: int = 3,
+def gather(sources: list[dict], limit: int = 16, per_source: int = 12, pages: int = 3,
            skip_cover: set[str] | frozenset = frozenset()) -> list[dict]:
     """Kaynaklardan fotoğraf topla. Dönen her öğe: {'image': PIL, 'src', 'credit', 'page', 'alt', 'kind', 'graphic'}
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -8,8 +8,10 @@
     "super-zeka = artificial intelligence: AI models, AI products and features, AI companies, AI research, AI chips, AI policy and new real-world uses of AI; "
     "teknoloji = consumer tech and big tech: newly unveiled phones, computers, tablets, wearables, cameras and lenses, drones, "
-    "headphones and audio systems, TVs and home entertainment, smart home and home appliances, apps; new car and EV models; "
+    "headphones and audio systems, TVs and home entertainment, smart home and home appliances, apps; "
     "big-tech company news, platforms, internet, social media, cybersecurity, telecom, tech regulation (use when the story is not mainly about AI); "
+    "otomotiv = cars and mobility: new car and EV models, car makers (TOGG, Tesla's cars, BYD, Toyota, BMW…), car prices and "
+    "availability in Türkiye, charging networks, autonomous driving and robotaxis, motorcycles and e-scooters; "
     "inovasyon = technologies tried or demonstrated for the first time, prototypes, science breakthroughs, robotics, space, energy, batteries, "
-    "autonomous driving milestones, health tech; "
+    "health tech; "
     "girisimcilik = startups and entrepreneurship: founding stories, founders, funding rounds, valuations, acquisitions of startups, unusual new business ideas "
     "(an AI startup's funding round also goes here); "
@@ -125,5 +127,6 @@
    Copilot, Claude, Meta AI, OpenAI, Anthropic, an AI video tool…), the category is ALWAYS "super-zeka", even when it is a
    feature inside a product of Google, Microsoft or Apple. A startup's funding round is "girisimcilik" (even an AI startup).
-   A game or gaming platform is "gaming". Military and defence technology is "inovasyon" only if it is a genuine
+   A game or gaming platform is "gaming". Cars, EVs, car makers, charging, autonomous driving and robotaxis are
+   "otomotiv" (Tesla's humanoid robot Optimus is "inovasyon"; an EV startup's funding round is "girisimcilik"). Military and defence technology is "inovasyon" only if it is a genuine
    first-of-its-kind technology; otherwise it is off topic for our readers.
 6. entities: the 1–3 main companies, brands or products the story is about, most important first, in their official
@@ -307,5 +310,5 @@
 - summary: 1–2 plain sentences, ≤180 characters, the core news in everyday language (shown under the headline and on Instagram).
 - body: Markdown, 180–320 words. Structure: a 2–3 sentence lead paragraph that answers who/what/when and contains the focus_keyword; then 2 sections (3 only if really needed), each starting with a "## " subheading (short, informative, natural search-style phrase such as "## iPhone 18 Pro neler sunuyor?", "## Fiyat ve çıkış tarihi" or "## Girişim ne yapıyor?"), each followed by 1–2 short paragraphs. Use a bullet list only for 3+ concrete items from the sources. Bold at most 2 key terms. The LAST paragraph (not under a new heading) must start with "**Neden önemli?** " followed by 1–2 grounded sentences (no speculation beyond what sources support). Do not include a sources list or links; the site adds them. If the sources are thin, write fewer, shorter sections rather than padding — accuracy beats length.
-- category: one of the allowed keys. If the main subject is an AI model, assistant, feature or AI company (ChatGPT, Gemini, Copilot, Claude…), always "super-zeka", even inside a Google/Microsoft/Apple product; a startup's funding round → "girisimcilik"; games and gaming platforms → "gaming".
+- category: one of the allowed keys. If the main subject is an AI model, assistant, feature or AI company (ChatGPT, Gemini, Copilot, Claude…), always "super-zeka", even inside a Google/Microsoft/Apple product; a startup's funding round → "girisimcilik"; games and gaming platforms → "gaming"; cars, EVs, car makers, charging and robotaxis → "otomotiv".
 - tags: 3–6 tags that people search for: companies, products, models, games, car models, technologies, places (e.g. "Apple", "iPhone 18", "TOGG", "elektrikli otomobil", "GTA 6", "OpenAI"). Use the official spelling consistently. If the story is mainly about Turkey or a Turkish company, include the tag "Türkiye". Never use generic words like "teknoloji", "yapay zeka", "oyun", "otomobil", "girişim", "haber", and never use the names of news outlets (TechCrunch, The Verge, Webrazzi…).
 - focus_keyword: as described above.
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -13,9 +13,10 @@
 
 from .config import CATEGORIES, DEFAULT_CATEGORY, ROOT, Config, category_color, category_label, category_seo, indexnow_key
+from .covers import art_style
 from .store import Store
 from .textfix import primary_key, tag_display
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "12"
+ASSET_V = "13"
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
 H2_RE = re.compile(r"<h[1-3]>(.*?)</h[1-3]>", re.S)
@@ -47,6 +48,7 @@
 
 
-def inline_figures(body_html: str, figs: list[dict], first: int = 1, every: int = 3) -> tuple[str, list[dict]]:
-    """Fotoğrafları metnin paragrafları arasına yerleştir (2. paragraftan sonra, sonra her 3 paragrafta bir).
+def inline_figures(body_html: str, figs: list[dict], first: int = 0, every: int = 1) -> tuple[str, list[dict]]:
+    """Fotoğrafları metnin paragrafları arasına yerleştir (ilk paragraftan sonra başlayarak her paragrafın ardına bir
+    fotoğraf; haber görsellerle akar).
 
     Liste, alıntı ve "Neden önemli?" kutularının içine girmez. Yer kalmazsa artanlar geri döner.
@@ -207,5 +209,4 @@
         dt = parse_iso(pub) or now_utc()
         mod = parse_iso(p.get("updated_at")) or dt
-        ext = "webp" if (cfg.images_dir / f"{p['id']}.webp").exists() else "jpg"
         has_og = (cfg.images_dir / f"{p['id']}-og.jpg").exists()
         title = p.get("title", "")
@@ -222,7 +223,11 @@
                 tags.append({"label": tag_display(t), "slug": ts, "url": f"{b}/etiket/{ts}/"})
         cat = p.get("category", DEFAULT_CATEGORY)
+        disp = self._display(p)
+        disp_url = disp.get("url") or ""
         return {
             **p,
-            "url": f"{b}/haber/{p['slug']}/",
+            "url": f"{b}/{cfg.post_path(p)}/",
+            "path": cfg.post_path(p),
+            "disp": disp,
             "ts": int(dt.timestamp()),
             "hot": hot(p),
@@ -236,5 +241,5 @@
             "cover_image": (p.get("image") or {}).get("source") == "cover",
             # rakam kapakta yazıyorsa "öne çıkanlar" kutusunda tekrar edilmez
-            "stat_on_cover": (p.get("image") or {}).get("source") in ("cover", "photo") and (p.get("image") or {}).get("layout") == "sayi",
+            "stat_on_cover": False,   # sitede görsellerin üstünde yazı yok: rakam "öne çıkanlar" kutusunda görünür
             "img_alt": clip(p.get("image_alt") or f"{short}: habere ait görsel", 125),
             "seo_title": seo_title,
@@ -242,8 +247,8 @@
             "focus_keyword": p.get("focus_keyword", ""),
             "tag_list": tags,
-            "abs_url": cfg.post_url(p["slug"]),
-            "img": f"{b}/img/{p['id']}.{ext}",
-            "abs_img": f"{cfg.site_url}/img/{p['id']}.{ext}",
-            "abs_og": f"{cfg.site_url}/img/{p['id']}-og.jpg" if has_og else f"{cfg.site_url}/static/og-default.jpg",
+            "abs_url": cfg.post_url(p),
+            "img": disp_url,
+            "abs_og": (og := f"{cfg.site_url}/img/{p['id']}-og.jpg" if has_og else f"{cfg.site_url}/static/og-default.jpg"),
+            "abs_img": f"{cfg.site_url}{disp_url[len(b):]}" if disp_url else og,
             "date_str": tr_date(pub, cfg.tz),
             "date_short": tr_date(pub, cfg.tz, with_time=False),
@@ -254,6 +259,6 @@
             "cat_seo": category_seo(cat)[0],
             "cat_color": category_color(cat),
-            "cat_url": f"{b}/kategori/{cat}/",
-            "abs_cat_url": f"{cfg.site_url}/kategori/{cat}/",
+            "cat_url": f"{b}/{cat}/",
+            "abs_cat_url": f"{cfg.site_url}/{cat}/",
             "credits": list(dict.fromkeys(s["name"] for s in p.get("sources", []))),
             "minutes": reading_minutes(p.get("body", "")),
@@ -291,18 +296,48 @@
         return out
 
+    def _display(self, p: dict) -> dict:
+        """Sitede görünen görsel — üstünde yazı yok, başlık sayfada HTML olarak durur (tek parça görünüm):
+        haberin gerçek fotoğrafı; yoksa yapay zeka görseli; o da yoksa habere özel renk ağı (CSS)."""
+        cfg, b = self.cfg, self.base
+        img = p.get("image") or {}
+        recs = [r for r in p.get("photos") or [] if r.get("file") and (cfg.images_dir / r["file"]).exists()]
+        pick = None
+        if img.get("source") == "photo" and img.get("photo"):
+            pick = next((r for r in recs if r["file"] == img["photo"]), None)
+        if pick is None and p.get("cover_mode") != "type":
+            pick = next((r for r in recs if not r.get("graphic") and r.get("cover_ok", True) and (r.get("w") or 0) >= 900), None)
+        if pick:
+            return {"kind": "photo", "file": pick["file"], "url": f"{b}/img/{pick['file']}", "w": pick.get("w") or 1600,
+                    "h": pick.get("h") or 900, "credit": pick.get("credit") or "", "page": pick.get("page") or "",
+                    "focus": p.get("photo_focus") or "50% 40%"}
+        if img.get("source") in ("ai", "fallback") and (cfg.images_dir / f"{p['id']}.webp").exists():
+            return {"kind": "image", "file": f"{p['id']}.webp", "url": f"{b}/img/{p['id']}.webp", "w": 1280, "h": 960,
+                    "credit": "", "page": "", "focus": "50% 50%"}
+        style, base = art_style(p)
+        return {"kind": "art", "style": style, "base": base, "url": ""}
+
     def _media(self, p: dict, short: str, body_html: str) -> dict:
-        """Kapak (ilk kare) + kaydırınca gelen fotoğraflar + metnin içine yerleşen fotoğraflar.
-
-        Kapakta kullanılan fotoğraf tekrar gösterilmez. Kaydırmalı alana en fazla 2 gerçek fotoğraf konur;
-        kalan fotoğraflar ve grafikler (ekran görüntüsü, tablo) paragrafların arasına yerleşir.
-        """
+        """Ana görsel (yazısız) + metnin içine paragraf paragraf yerleşen fotoğraflar + sona kalanlar için galeri.
+
+        Ana görselde kullanılan fotoğraf tekrar gösterilmez."""
         ph = self._photos(p, short)
-        img = p.get("image") or {}
-        cover = next((x for x in ph if x["file"] and x["file"] == img.get("photo")), None) if img.get("source") == "photo" else None
+        disp = self._display(p)
+        cover = next((x for x in ph if x["file"] and x["file"] == disp.get("file")), None)
         rest = [x for x in ph if x is not cover]
         good = [x for x in rest if not x["graphic"]]
         graphics = [x for x in rest if x["graphic"]]
-        body_html, left = inline_figures(body_html, good[2:] + graphics)
-        return {"body_html": body_html, "cover_photo": cover, "slides": good[:2] + left}
+        body_html, left = inline_figures(body_html, good + graphics)
+        return {"body_html": body_html, "cover_photo": cover, "slides": left}
+
+    def _redirect(self, rel: str, target: str, title: str) -> None:
+        """GitHub Pages'te sunucu yönlendirmesi yok: anında yenileme + kanonik adres (Google bunu kalıcı yönlendirme sayar)."""
+        if (self.cfg.out_dir / rel).exists():
+            return
+        t = htmlmod.escape(target, quote=True)
+        name = htmlmod.escape(title or "Smarity")
+        self._write(rel, f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>{name}</title>'
+                         f'<link rel="canonical" href="{t}"><meta http-equiv="refresh" content="0; url={t}">'
+                         f'<script>location.replace({json.dumps(target)} + location.hash)</script></head>'
+                         f'<body><a href="{t}">{name}</a></body></html>')
 
     def _write(self, rel: str, content: str) -> None:
@@ -360,5 +395,6 @@
         cats = [{"slug": k, "label": v[0], "color": v[1], "count": counts.get(k, 0),
                  "seo_title": category_seo(k)[0], "intro": category_seo(k)[1],
-                 "url": f"{b}/kategori/{k}/", "lastmod": latest_by_cat.get(k)} for k, v in CATEGORIES.items()]
+                 "url": f"{b}/{k}/", "abs_url": f"{cfg.site_url}/{k}/", "lastmod": latest_by_cat.get(k)}
+                for k, v in CATEGORIES.items()]
 
         # etiketler (konular)
@@ -413,5 +449,7 @@
         (out / "img").mkdir()
         for p in posts:
-            names = [f"{p['id']}.webp", f"{p['id']}.jpg", f"{p['id']}-og.jpg"]
+            # yazılı kapak ({id}.webp) sitede kullanılmaz (paylaşım görseli -og.jpg ayrı); yalnızca görünen görsel kopyalanır
+            names = [p["disp"]["file"]] if p["disp"].get("file") else []
+            names += [f"{p['id']}-og.jpg"]
             names += [ph["file"] for ph in p.get("photos") or [] if ph.get("file") and not ph.get("remote")]
             for name in dict.fromkeys(names):
@@ -425,6 +463,8 @@
         featured = home["featured"]
         for p in featured:
-            src = cfg.images_dir / p["img"].rsplit("/", 1)[-1]
-            p["slide_bg"], p["slide_dark"] = edge_color(src)
+            if p["disp"].get("file"):
+                p["slide_bg"], p["slide_dark"] = edge_color(cfg.images_dir / p["disp"]["file"])
+            else:
+                p["slide_bg"], p["slide_dark"] = p["disp"]["base"], True
         shown = set(home["shown"])
         rails = []
@@ -468,13 +508,27 @@
             nxt = next((q for q in pool if q["category"] == p["category"]), pool[0] if pool else None)
             related = [q for q in related if not nxt or q["id"] != nxt["id"]]
-            self._write(f"haber/{p['slug']}/index.html", self.env.get_template("article.html").render(
+            self._write(f"{p['path']}/index.html", self.env.get_template("article.html").render(
                 **ctx, post=p, related=related, next_post=nxt, canonical=p["abs_url"]))
-
-        # kategoriler
+            # eski adres (/haber/slug/) yeni adrese yönlenir
+            self._redirect(f"haber/{p['slug']}/index.html", p["abs_url"], p["title"])
+            for old in p.get("old_paths") or []:
+                if old != p["path"]:
+                    self._redirect(f"{old}/index.html", p["abs_url"], p["title"])
+
+        # kategoriler: /teknoloji/ ; yıl ve ay adresleri (/teknoloji/2026/10/) kategori sayfasına yönlenir
+        months: set[str] = set()
+        for p in posts:
+            parts = p["path"].split("/")
+            if len(parts) == 4:
+                months |= {"/".join(parts[:2]), "/".join(parts[:3])}
         for c in cats:
             cp = [p for p in posts if p["category"] == c["slug"]][:120]
-            self._write(f"kategori/{c['slug']}/index.html", self.env.get_template("category.html").render(
-                **ctx, cat=c, posts=cp, active_cat=c["slug"], canonical=f"{cfg.site_url}/kategori/{c['slug']}/",
-                noindex=not cp))
+            self._write(f"{c['slug']}/index.html", self.env.get_template("category.html").render(
+                **ctx, cat=c, posts=cp, active_cat=c["slug"], canonical=c["abs_url"], noindex=not cp))
+            self._redirect(f"kategori/{c['slug']}/index.html", c["abs_url"], c["seo_title"])
+        for m in sorted(months):
+            cat = m.split("/")[0]
+            if cat in CATEGORIES:
+                self._redirect(f"{m}/index.html", f"{cfg.site_url}/{cat}/", category_seo(cat)[0])
 
         # konu (etiket) sayfaları: tek haberlik konular dizine eklenmez (ince içerik)
--- a/haberbot/textfix.py
+++ b/haberbot/textfix.py
@@ -191,2 +191,31 @@
     names = list(p.get("entities") or []) or list(p.get("tags") or [])[:1]
     return {k for k in (entity_key(e) for e in names) if k}
+
+
+# ── Otomotiv: araba haberini tanı (kategori geçişi için) ─────
+CAR_BRANDS = {
+    "toyota", "lexus", "honda", "acura", "nissan", "infiniti", "mazda", "subaru", "mitsubishi", "suzuki", "hyundai", "kia",
+    "genesis", "bmw", "mini cooper", "rolls-royce", "mercedes", "mercedes-benz", "mercedes-amg", "maybach", "audi", "volkswagen",
+    "vw", "porsche", "lamborghini", "bentley", "bugatti", "skoda", "škoda", "seat", "cupra", "ferrari", "maserati",
+    "alfa romeo", "fiat", "lancia", "jeep", "chrysler", "dodge", "chevrolet", "cadillac", "gmc", "buick",
+    "general motors", "ford", "lincoln", "tesla", "rivian", "lucid", "lucid motors", "polestar", "volvo", "renault",
+    "dacia", "peugeot", "citroën", "citroen", "opel", "ds automobiles", "stellantis", "jaguar", "land rover",
+    "range rover", "aston martin", "mclaren", "lotus", "byd", "nio", "xpeng", "li auto", "zeekr", "geely", "chery",
+    "omoda", "jaecoo", "mg motor", "togg", "waymo", "zoox", "leapmotor", "lynk & co", "denza", "yangwang",
+    "aito", "rimac", "koenigsegg", "pagani", "alpine", "abarth", "isuzu", "scout", "fisker", "vinfast",
+}
+CAR_WORDS = re.compile(r"\b(otomobil|elektrikli araç|elektrikli otomobil|elektrikli suv|suv\b|sedan|hatchback|pikap|"
+                       r"motosiklet|robotaksi|şarj istasyon|menzilli|beygir|model y\b|model 3\b|cybertruck|su7|yu7)", re.I)
+NOT_CAR = re.compile(r"optimus|insansı robot|humanoid|starlink|spacex|carplay|android auto", re.I)
+
+
+def is_car_story(d: dict) -> bool:
+    """Haber bir araba / elektrikli araç / araç üreticisi haberi mi? (Tesla'nın robotu, CarPlay vb. hariç)"""
+    text = f"{d.get('title', '')} {d.get('summary', '')}"
+    if NOT_CAR.search(text):
+        return False
+    names = {str(x).strip().lower() for x in (d.get("entities") or []) + (d.get("tags") or [])}
+    first = {n.split()[0] for n in names if n}
+    if names & CAR_BRANDS or first & (CAR_BRANDS - {"seat", "scout", "alpine", "genesis", "lotus", "smart"}):
+        return True
+    return bool(CAR_WORDS.search(d.get("title", "")))
--- a/haberbot/visuals.py
+++ b/haberbot/visuals.py
@@ -42,5 +42,5 @@
 BACKDROPS = {
     "super-zeka": "soft lavender white", "teknoloji": "cool silver white", "inovasyon": "pale mint white",
-    "girisimcilik": "warm ivory", "gaming": "soft pink-violet white",
+    "girisimcilik": "warm ivory", "gaming": "soft pink-violet white", "otomotiv": "warm light grey",
 }
 
@@ -151,5 +151,5 @@
 ACCENTS = {
     "super-zeka": ("#7C5CFF", "#FF8FB1"), "teknoloji": ("#326EF0", "#54D59C"), "inovasyon": ("#10B981", "#0EA5E9"),
-    "girisimcilik": ("#F59E0B", "#3B82F6"), "gaming": ("#EC4899", "#8B5CF6"),
+    "girisimcilik": ("#F59E0B", "#3B82F6"), "gaming": ("#EC4899", "#8B5CF6"), "otomotiv": ("#E5332A", "#F59E0B"),
 }
 
--- a/static/site.js
+++ b/static/site.js
@@ -247,4 +247,62 @@
   });
 
+  // Bugünün tarihi (sayfa daha önce üretilmiş olabilir; tarih ziyaretçinin saatine göre yazılır)
+  var today = document.querySelector("[data-today]");
+  if (today && window.Intl) {
+    try {
+      var dNow = new Date(), tz = { timeZone: "Europe/Istanbul" };
+      today.textContent = new Intl.DateTimeFormat("tr-TR", Object.assign({ day: "numeric", month: "long", year: "numeric" }, tz)).format(dNow) +
+        ", " + new Intl.DateTimeFormat("tr-TR", Object.assign({ weekday: "long" }, tz)).format(dNow);
+    } catch (e) {}
+  }
+
+  // Canlı piyasa şeridi: dolar, euro, sterlin, gram altın, BIST 100, bitcoin (dakikada bir yenilenir; veri gelmezse gizli kalır)
+  var mkt = document.querySelector("[data-mkt]");
+  if (mkt && window.fetch && window.Promise) {
+    var nf = function (v, d) { return new Intl.NumberFormat("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d }).format(v); };
+    var num = function (x) {
+      if (typeof x === "number") return x;
+      x = String(x || "").replace(/[^0-9,.-]/g, "");
+      return parseFloat(x.indexOf(",") >= 0 ? x.replace(/\./g, "").replace(",", ".") : x);   // "6.542,72" ya da "84812.33"
+    };
+    var put = function (k, val, ch, dec, pre) {
+      var li = mkt.querySelector('[data-k="' + k + '"]');
+      if (!li || !isFinite(val) || val <= 0) return false;
+      li.querySelector("b").textContent = (pre || "") + nf(val, dec);
+      var i = li.querySelector("i");
+      if (isFinite(ch)) {
+        i.textContent = (ch > 0.004 ? "▲" : ch < -0.004 ? "▼" : "") + "%" + nf(Math.abs(ch), 2);
+        i.className = ch > 0.004 ? "up" : ch < -0.004 ? "dn" : "eq";
+      } else { i.textContent = ""; }
+      li.hidden = false;
+      return true;
+    };
+    var get = function (u) {
+      var c = window.AbortController ? new AbortController() : null;
+      if (c) setTimeout(function () { c.abort(); }, 8000);
+      return fetch(u, { cache: "no-store", signal: c ? c.signal : undefined }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
+    };
+    var loadMkt = function () {
+      var any = false;
+      var fx = get("https://finans.truncgil.com/v4/today.json?t=" + Date.now()).then(function (j) {
+        [["USD", 2], ["EUR", 2], ["GBP", 2], ["GRA", 0], ["XU100", 0]].forEach(function (x) {
+          var o = j[x[0]];
+          if (o && put(x[0], num(o.Selling) || num(o.Buying), num(o.Change), x[1])) any = true;
+        });
+      }).catch(function () {
+        return get("https://api.frankfurter.dev/v1/latest?base=TRY&symbols=USD,EUR,GBP").then(function (j) {
+          ["USD", "EUR", "GBP"].forEach(function (k) { if (j.rates && j.rates[k] && put(k, 1 / j.rates[k], NaN, 2)) any = true; });
+        }).catch(function () {});
+      });
+      var btc = get("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT").then(function (j) {
+        if (put("BTC", num(j.lastPrice), num(j.priceChangePercent), 0, "$")) any = true;
+      }).catch(function () {});
+      Promise.all([fx, btc]).then(function () { if (any) mkt.hidden = false; });
+    };
+    mkt.querySelectorAll("li").forEach(function (li) { li.hidden = true; });
+    loadMkt();
+    setInterval(function () { if (!document.hidden) loadMkt(); }, 60000);
+  }
+
   // Menü: bir bağlantıya basınca kapansın
   document.querySelectorAll(".menu-panel a").forEach(function (a) {
--- a/static/style.css
+++ b/static/style.css
@@ -80,5 +80,21 @@
 /* ── ana sayfa başlığı ─────────────────── */
 .home-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px 20px; padding-block: 22px 16px; }
-.home-date { margin: 0; font-size: 15px; font-weight: 600; color: var(--ink-2); letter-spacing: -.01em; }
+.home-date { margin: 0; font-size: 15px; font-weight: 600; color: var(--ink-2); letter-spacing: -.01em; white-space: nowrap; }
+.home-day { display: flex; align-items: center; gap: 8px 18px; flex-wrap: wrap; min-width: 0; }
+/* canlı piyasa şeridi: tarihin yanında */
+.mkt { list-style: none; margin: 0; padding: 0; display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; min-width: 0;
+  font-size: 13px; font-variant-numeric: tabular-nums; }
+.mkt::-webkit-scrollbar { display: none; }
+.mkt[hidden] { display: none; }
+.mkt li { flex: none; display: inline-flex; align-items: baseline; gap: 5px; padding: 5px 10px; border-radius: 999px; background: var(--bg-alt); }
+.mkt li[hidden] { display: none; }
+.mkt span { color: var(--muted); }
+.mkt b { font-weight: 600; color: var(--ink); }
+.mkt i { font-style: normal; font-size: 12px; font-weight: 600; }
+.mkt i.up { color: #0B8A3A; } .mkt i.dn { color: #D12F2F; } .mkt i.eq { color: var(--muted); }
+@media (max-width: 799px) {
+  .home-day { width: 100%; }
+  .mkt { width: calc(100% + 16px); margin-right: -16px; padding-right: 16px; }
+}
 .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
 .home-head h1 { margin: 0; font-size: clamp(28px, 4vw, 44px); letter-spacing: -.04em; line-height: 1.05; font-weight: 700; }
@@ -99,5 +115,5 @@
 .slide-in { display: grid; grid-template-columns: minmax(0, 1fr); color: var(--ink); height: 100%; }
 .slide-media { position: relative; order: -1; aspect-ratio: 4 / 3; overflow: hidden; }
-/* Kapak görseli solmaz: üstündeki kapak başlığı her zaman tam okunur */
+/* Görsellerin üstünde yazı yok: başlık bir kez, sayfada HTML olarak yazılır */
 .slide-img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover;
   transition: transform 1.2s var(--ease); }
@@ -122,4 +138,17 @@
 .slide.dark .stat-chip, .slide.dark .upd-chip { background: rgba(255,255,255,.16); color: #fff; }
 @media (max-width: 599px) { .slide-dek { display: none; } }
+/* Telefonda manşet tek parça: görsel tüm kartı kaplar, başlık altta görselin üstünde */
+@media (max-width: 799px) {
+  .slide-in { position: relative; display: block; aspect-ratio: 4 / 5; max-height: 76vh; color: #fff; }
+  .slide-media { position: absolute; inset: 0; aspect-ratio: auto; }
+  .slide-media::after { content: ""; position: absolute; inset: 0; pointer-events: none;
+    background: linear-gradient(to top, rgba(0,0,0,.88) 0%, rgba(0,0,0,.62) 34%, rgba(0,0,0,.12) 62%, rgba(0,0,0,0) 78%); }
+  .slide-txt { position: absolute; left: 0; right: 0; bottom: 0; z-index: 2; padding: 0 20px 22px; gap: 8px; align-content: end; }
+  .slide h2 { font-size: clamp(23px, 6.6vw, 30px); line-height: 1.12; text-shadow: 0 1px 12px rgba(0,0,0,.25); }
+  .slide-meta { color: rgba(255,255,255,.78); font-size: 13px; }
+  .slide .more { display: none; }
+  .slide .upd-chip, .slide .stat-chip { background: rgba(255,255,255,.18); color: #fff; }
+  .slide .chip { -webkit-backdrop-filter: blur(6px); backdrop-filter: blur(6px); }
+}
 @media (min-width: 800px) {
   .slide-in { grid-template-columns: minmax(0, 1fr) auto; height: clamp(400px, 40vw, 520px); }
@@ -281,6 +310,16 @@
 .art-media .ph { position: relative; }
 .gal-slide.cover .gal-credit, .art-media .gal-credit { left: auto; bottom: auto; top: 12px; right: 12px; }
+/* fotoğrafı olmayan haber: yazısız, habere özel renk ağı */
+.ph-art { display: block; width: 100%; aspect-ratio: 4 / 3; position: relative; overflow: hidden; }
+.ph-art::after { content: ""; position: absolute; inset: 0; opacity: .14; mix-blend-mode: overlay; pointer-events: none;
+  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>"); }
+.slide-media .ph-art, .art-media .ph-art { position: absolute; inset: 0; height: 100%; aspect-ratio: auto; }
+.card .ph-art { transition: transform .8s var(--ease); }
+/* haberin sonundaki galeri (metne yerleşmeyen fotoğraflar) */
+.gal-end { margin-top: 40px; }
+.gal-title { margin: 0 0 14px; font-size: 22px; font-weight: 700; letter-spacing: -.02em; }
+.gal-title span { margin-left: 6px; font-size: 15px; font-weight: 500; color: var(--muted); letter-spacing: 0; }
 /* metnin içindeki fotoğraflar */
-.art-body figure.inl { margin: 34px 0; }
+.art-body figure.inl { margin: 28px 0; }
 .art-body figure.inl img { display: block; width: 100%; height: auto; border-radius: var(--r-md); background: var(--bg-alt); }
 .art-body figure.inl.graphic img { border: 1px solid var(--line); background: #fff; }
@@ -412,5 +451,5 @@
 .slide-top .badge { font-size: 12px; padding: 6px 10px; }
 .slide.dark .badge.new { background: rgba(48, 209, 88, .22); color: #7CF0A0; }
-.is-read .ph img, .is-read > img, .is-read .row-img img { filter: saturate(.55); opacity: .72; }
+.is-read .ph img, .is-read .ph .ph-art, .is-read > img, .is-read > .ph-art, .is-read .row-img img, .is-read .row-img .ph-art { filter: saturate(.55); opacity: .72; }
 .is-read h2 a, .is-read h3 a, .is-read h3, .is-read .row-title { color: var(--ink-2); }
 .since { display: flex; align-items: center; gap: 8px; margin-block: -4px 14px; font-size: 14px; color: var(--ink-2); }
--- a/templates/_macros.html
+++ b/templates/_macros.html
@@ -1,4 +1,9 @@
+{# Haberin görseli: yazısız gerçek fotoğraf; fotoğraf yoksa habere özel renk ağı (başlık her zaman HTML olarak yazılır) #}
 {% macro img(p, cls='', eager=false, sizes='(min-width: 1000px) 400px, 100vw', priority=false) %}
-<img src="{{ p.img }}" alt="{{ p.img_alt }}" width="1280" height="960"{% if not eager %} loading="lazy"{% endif %}{% if priority %} fetchpriority="high"{% endif %} decoding="async" class="{{ cls }}" style="view-transition-name: v{{ p.id }}">
+{% if p.disp.kind == 'art' %}
+<span class="ph-art {{ cls }}" role="img" aria-label="{{ p.img_alt }}" style="{{ p.disp.style }}; view-transition-name: v{{ p.id }}"></span>
+{% else %}
+<img src="{{ p.img }}" alt="{{ p.img_alt }}" width="{{ p.disp.w }}" height="{{ p.disp.h }}"{% if not eager %} loading="lazy"{% endif %}{% if priority %} fetchpriority="high"{% endif %} decoding="async" class="{{ cls }}" style="object-position: {{ p.disp.focus }}; view-transition-name: v{{ p.id }}">
+{% endif %}
 {% endmacro %}
 
--- a/templates/article.html
+++ b/templates/article.html
@@ -21,5 +21,5 @@
 {% endblock %}
 {% block head %}
-<link rel="preload" as="image" href="{{ post.img }}" fetchpriority="high">
+{% if post.img %}<link rel="preload" as="image" href="{{ post.img }}" fetchpriority="high">{% endif %}
 <script type="application/ld+json">{{ {
   "@context": "https://schema.org", "@type": "NewsArticle",
@@ -27,5 +27,5 @@
   "headline": post.title[:110], "alternativeHeadline": post.seo_title,
   "description": post.meta_description,
-  "image": [post.abs_og, post.abs_img],
+  "image": ([post.abs_img] if post.img else []) + [post.abs_og],
   "datePublished": post.iso, "dateModified": post.mod_iso,
   "inLanguage": "tr-TR", "articleSection": post.cat_label,
@@ -67,37 +67,10 @@
 
   {% set cp = post.cover_photo %}
-  {% if post.slides %}
-  {% set n = post.slides|length + 1 %}
-  <figure class="gal" data-gal aria-label="Haberin görselleri">
-    <div class="gal-view">
-      <div class="gal-track">
-        <div class="gal-slide cover" role="group" aria-label="1 / {{ n }}">
-          <img src="{{ post.img }}" alt="{{ post.img_alt }}" width="1280" height="960" decoding="async" fetchpriority="high" style="view-transition-name: v{{ post.id }}">
-          {% if cp and cp.credit %}<a class="gal-credit" href="{{ cp.page or post.sources[0].url }}" rel="noopener nofollow" target="_blank">Görsel: {{ cp.credit }}</a>{% endif %}
-        </div>
-        {% for ph in post.slides %}
-        <div class="gal-slide{{ ' fit' if ph.graphic or (ph.w / ph.h) < 1.25 }}" role="group" aria-label="{{ loop.index + 1 }} / {{ n }}">
-          <img src="{{ ph.url }}" alt="{{ ph.alt }}" width="{{ ph.w }}" height="{{ ph.h }}" decoding="async" loading="lazy"{% if ph.remote %} referrerpolicy="no-referrer" onerror="this.parentNode.remove()"{% endif %}>
-          {% if ph.credit %}<a class="gal-credit" href="{{ ph.page or post.sources[0].url }}" rel="noopener nofollow" target="_blank">Görsel: {{ ph.credit }}</a>{% endif %}
-        </div>
-        {% endfor %}
-      </div>
-      <button type="button" class="gal-btn" data-dir="-1" aria-label="Önceki görsel">‹</button>
-      <button type="button" class="gal-btn" data-dir="1" aria-label="Sonraki görsel">›</button>
-      <span class="gal-count" aria-live="polite"><b>1</b> / {{ n }}</span>
-    </div>
-    <div class="gal-thumbs">
-      <button type="button" data-go="0" aria-label="Kapak" aria-current="true"><img src="{{ post.img }}" alt="" loading="lazy" decoding="async"></button>
-      {% for ph in post.slides %}
-      <button type="button" data-go="{{ loop.index }}" aria-label="{{ loop.index + 1 }}. görsel"><img src="{{ ph.url }}" alt="" loading="lazy" decoding="async"{% if ph.remote %} referrerpolicy="no-referrer" onerror="this.parentNode.remove()"{% endif %}></button>
-      {% endfor %}
-    </div>
-  </figure>
-  {% else %}
+  {% if post.disp.kind != 'art' %}
   <figure class="art-media">
     <div class="ph">{{ img(post, eager=true, sizes='(min-width: 880px) 840px, 100vw', priority=true) }}
       {% if cp and cp.credit %}<a class="gal-credit" href="{{ cp.page or post.sources[0].url }}" rel="noopener nofollow" target="_blank">Görsel: {{ cp.credit }}</a>{% endif %}
     </div>
-    {% if not post.cover_image and not cp %}<figcaption>{% if post.ai_image %}Temsili görsel, yapay zeka ile üretilmiştir.{% else %}Temsili görsel.{% endif %}</figcaption>{% endif %}
+    {% if post.ai_image %}<figcaption>Temsili görsel, yapay zeka ile üretilmiştir.</figcaption>{% endif %}
   </figure>
   {% endif %}
@@ -118,4 +91,31 @@
 
   <div class="art-body">{{ post.body_html|safe }}</div>
+
+  {% if post.slides %}
+  {% set n = post.slides|length %}
+  <figure class="gal gal-end" data-gal aria-label="Fotoğraf galerisi">
+    <figcaption class="gal-title">Galeri <span>{{ n }} fotoğraf</span></figcaption>
+    <div class="gal-view">
+      <div class="gal-track">
+        {% for ph in post.slides %}
+        <div class="gal-slide{{ ' fit' if ph.graphic or (ph.w / ph.h) < 1.25 }}" role="group" aria-label="{{ loop.index }} / {{ n }}">
+          <img src="{{ ph.url }}" alt="{{ ph.alt }}" width="{{ ph.w }}" height="{{ ph.h }}" decoding="async" loading="lazy"{% if ph.remote %} referrerpolicy="no-referrer" onerror="this.parentNode.remove()"{% endif %}>
+          {% if ph.credit %}<a class="gal-credit" href="{{ ph.page or post.sources[0].url }}" rel="noopener nofollow" target="_blank">Görsel: {{ ph.credit }}</a>{% endif %}
+        </div>
+        {% endfor %}
+      </div>
+      <button type="button" class="gal-btn" data-dir="-1" aria-label="Önceki görsel">‹</button>
+      <button type="button" class="gal-btn" data-dir="1" aria-label="Sonraki görsel">›</button>
+      <span class="gal-count" aria-live="polite"><b>1</b> / {{ n }}</span>
+    </div>
+    {% if n > 1 %}
+    <div class="gal-thumbs">
+      {% for ph in post.slides %}
+      <button type="button" data-go="{{ loop.index0 }}" aria-label="{{ loop.index }}. görsel"{% if loop.first %} aria-current="true"{% endif %}><img src="{{ ph.url }}" alt="" loading="lazy" decoding="async"{% if ph.remote %} referrerpolicy="no-referrer" onerror="this.parentNode.remove()"{% endif %}></button>
+      {% endfor %}
+    </div>
+    {% endif %}
+  </figure>
+  {% endif %}
 
   {% if post.tag_list %}
--- a/templates/category.html
+++ b/templates/category.html
@@ -4,5 +4,5 @@
 {% block description %}{{ cat.seo_title }}: {{ cat.intro }} Güncel ve kaynağıyla, Türkçe.{% endblock %}
 {% block main %}
-{{ crumbs([("Ana sayfa", site.base ~ "/", site.url ~ "/"), (cat.label, cat.url, site.url ~ "/kategori/" ~ cat.slug ~ "/")]) }}
+{{ crumbs([("Ana sayfa", site.base ~ "/", site.url ~ "/"), (cat.label, cat.url, cat.abs_url)]) }}
 <header class="page-head wrap" style="--c:{{ cat.color }}">
   <span class="eyebrow">{{ cat.label }}</span>
--- a/templates/index.html
+++ b/templates/index.html
@@ -3,5 +3,5 @@
 
 {% block head %}
-{% if featured %}<link rel="preload" as="image" href="{{ featured[0].img }}" fetchpriority="high">{% endif %}
+{% if featured and featured[0].img %}<link rel="preload" as="image" href="{{ featured[0].img }}" fetchpriority="high">{% endif %}
 {% set org = {"@type": "NewsMediaOrganization", "@id": site.url ~ "/#org", "name": site.name, "url": site.url ~ "/",
      "logo": {"@type": "ImageObject", "url": site.logo, "width": 512, "height": 512},
@@ -24,5 +24,15 @@
 <header class="home-head wrap">
   <h1 class="sr-only">{{ site.home_h1 }}</h1>
-  <p class="home-date"><time datetime="{{ site.built_iso[:10] }}">{{ site.today_str }}</time></p>
+  <div class="home-day">
+    <p class="home-date"><time datetime="{{ site.built_iso[:10] }}" data-today>{{ site.today_str }}</time></p>
+    <ul class="mkt" data-mkt aria-label="Piyasalar" hidden>
+      <li data-k="USD"><span>Dolar</span><b></b><i></i></li>
+      <li data-k="EUR"><span>Euro</span><b></b><i></i></li>
+      <li data-k="GBP"><span>Sterlin</span><b></b><i></i></li>
+      <li data-k="GRA"><span>Gram altın</span><b></b><i></i></li>
+      <li data-k="XU100"><span>BIST 100</span><b></b><i></i></li>
+      <li data-k="BTC"><span>Bitcoin</span><b></b><i></i></li>
+    </ul>
+  </div>
   {% if featured %}
   <p class="live" role="status"><span class="dot" aria-hidden="true"></span>Son haber <b><time datetime="{{ latest_iso }}" data-rel data-live>{{ latest_str }}</time></b>{% if site.today_count %} · Bugün <b>{{ site.today_count }}</b> gelişme{% endif %}</p>
--- a/templates/sitemap.xml
+++ b/templates/sitemap.xml
@@ -8,5 +8,5 @@
   {% endfor %}
   {% for c in cats %}
-  <url><loc>{{ site.url }}/kategori/{{ c.slug }}/</loc>{% if c.lastmod %}<lastmod>{{ c.lastmod }}</lastmod>{% endif %}</url>
+  <url><loc>{{ c.abs_url }}</loc>{% if c.lastmod %}<lastmod>{{ c.lastmod }}</lastmod>{% endif %}</url>
   {% endfor %}
   {% for t in tags %}
--- a/tests/test_editor.py
+++ b/tests/test_editor.py
@@ -80,5 +80,5 @@
         sb = SiteBuilder(cfg)
         sb.build()
-        art = (cfg.out_dir / "haber" / "haber-1" / "index.html").read_text(encoding="utf-8")
+        art = (cfg.out_dir / cfg.post_path(p) / "index.html").read_text(encoding="utf-8")
         assert 'class="upd"' in art and "Güncellendi" in art
 
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -91,8 +91,20 @@
         assert "haberler/" in (cfg.out_dir / "sayfa" / "2" / "index.html").read_text(encoding="utf-8")
         assert (cfg.out_dir / "manifest.webmanifest").exists()
-        art = (cfg.out_dir / "haber" / "haber-5" / "index.html").read_text(encoding="utf-8")
+        p5 = a.store.load_post("p05")
+        path = cfg.post_path(p5)                                      # kategori/yıl/ay/slug
+        assert re.fullmatch(r"[a-z-]+/20\d\d/\d\d/haber-5", path) and path.startswith(p5["category"] + "/")
+        art = (cfg.out_dir / path / "index.html").read_text(encoding="utf-8")
         assert "Sıradaki haber" in art and 'data-read="p05"' in art and "t.me/share" in art
+        assert f'<link rel="canonical" href="https://smarity.com.tr/{path}/">' in art
+        assert f'href="/{p5["category"]}/"' in art                    # kategori sayfası /teknoloji/
+        old = (cfg.out_dir / "haber" / "haber-5" / "index.html").read_text(encoding="utf-8")
+        assert f"url=https://smarity.com.tr/{path}/" in old and 'rel="canonical"' in old   # eski adres yönlenir
+        assert "teknoloji/" in (cfg.out_dir / "kategori" / "teknoloji" / "index.html").read_text(encoding="utf-8")
+        assert (cfg.out_dir / "teknoloji" / "index.html").exists()
+        ym = "/".join(path.split("/")[:3])
+        assert "url=https://smarity.com.tr/" in (cfg.out_dir / ym / "index.html").read_text(encoding="utf-8")
         sm = (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")
-        assert "/haberler/" in sm and "smarity.com.tr/sayfa/" not in sm
+        assert "/haberler/" in sm and "smarity.com.tr/sayfa/" not in sm and f"/{path}/" in sm and "/kategori/" not in sm
+        assert ">Süper Zeka<" in home and not re.search(r"Süper Zeka<span>\d", home)   # kategori çiplerinde sayı yok
 
 
@@ -137,4 +149,6 @@
         p = a.store.load_post("p02")
         assert p["home"] == "pin" and hot(p) >= 100
+        assert p["path"].startswith("teknoloji/") and p["path"].endswith("/" + p["slug"])   # kalıcı adres yayında yazılır
+        assert cfg.post_url(p) in a._caption(p, "published") and cfg.post_url(p) in str(a._keyboard(p, "published"))
         # /manset: son haberler düğmeleriyle; listeden basınca liste yenilenir
         a._on_command("manset", "")
@@ -158,4 +172,26 @@
 
 
+def test_url_migration_and_otomotiv():
+    with _App() as (cfg, a):
+        a.store.save_post(_post(1, 2, title="2027 Lexus TZ menzili açıklandı", tags=["Lexus", "Lexus TZ"]))
+        a.store.save_post(_post(2, 3, tags=["Apple"]))
+        a.store.save_post(_post(3, 4, cat="inovasyon", title="Tesla Optimus yürüdü", tags=["Tesla", "Optimus"]))
+        d = {**_post(4, 0, title="TOGG T10F Almanya'da", tags=["TOGG"]), "status": "pending", "created_at": iso(now_utc())}
+        a.store.save_draft(d)
+        a.migrate_urls()
+        p1, p2, p3 = (a.store.load_post(f"p0{i}") for i in (1, 2, 3))
+        assert p1["category"] == "otomotiv" and p1["path"].startswith("otomotiv/") and p2["category"] == "teknoloji"
+        assert p3["category"] == "inovasyon"                                # robot haberi otomotive gitmez
+        assert a.store.load_draft("p04")["category"] == "otomotiv"
+        assert cfg.post_url(p1) in a.state["indexnow_queue"]
+        a.store.save_post({**p2, "category": "gaming"})                      # kategori sonradan değişse de adres sabit
+        a.migrate_urls()
+        assert cfg.post_url(a.store.load_post("p02")) == cfg.post_url(p2)
+        SiteBuilder(cfg).build()
+        assert (cfg.out_dir / p1["path"] / "index.html").exists() and (cfg.out_dir / "otomotiv" / "index.html").exists()
+        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
+        assert 'class="ph-art' in home and 'data-mkt' in home                  # fotoğrafsız haber: yazısız renk ağı; piyasa şeridi
+
+
 if __name__ == "__main__":
     for name, fn in list(globals().items()):
--- a/tests/test_photos.py
+++ b/tests/test_photos.py
@@ -157,5 +157,7 @@
         p = a.store.load_post("p1")
         assert len(p["photos"]) == 5 and p["photos_v"] == 2
-        assert [r["file"] for r in p["photos"]] == [f"p1-g{i}.webp" for i in range(5)]
+        # ilk 4 fotoğraf siteye kopyalanır, kalanlar kaynaktaki adresinden gösterilir
+        assert [r.get("file") for r in p["photos"]] == [f"p1-g{i}.webp" for i in range(4)] + [None]
+        assert p["photos"][4]["remote"] and p["photos"][4]["src"] == "https://x/doc.jpg" and p["photos"][4]["w"]
         assert p["image"]["source"] == "photo" and p["image"]["photo"] == "p1-g0.webp"
         hero = cfg.images_dir / "p1.webp"
@@ -167,15 +169,15 @@
         from PIL import ImageChops, ImageStat
         assert ImageStat.Stat(ImageChops.difference(ph.crop((0, 36, 64, 48)), cv.crop((0, 36, 64, 48)))).mean[0] > 20
-        # site: ilk kare kapak, kaydırınca 2 fotoğraf, kalanlar ve grafik metnin içinde
+        # site: ana görsel yazısız fotoğrafın kendisi; diğer fotoğraflar ve grafik paragraf paragraf metnin içinde
         from haberbot.site import SiteBuilder
         view = SiteBuilder(cfg)._post_view(p)
-        assert view["cover_photo"]["file"] == "p1-g0.webp"
-        assert [x["file"] for x in view["slides"]] == ["p1-g1.webp", "p1-g2.webp"]
-        assert view["body_html"].count('<figure class="inl') == 2 and 'class="inl graphic"' in view["body_html"]
+        assert view["cover_photo"]["file"] == "p1-g0.webp" and view["disp"]["file"] == "p1-g0.webp"
+        assert view["img"] == "/img/p1-g0.webp" and view["slides"] == []
+        assert view["body_html"].count('<figure class="inl') == 4 and 'class="inl graphic"' in view["body_html"]
         SiteBuilder(cfg).build()
-        assert (cfg.out_dir / "img" / "p1-g4.webp").exists()
-        html = (cfg.out_dir / "haber" / "ornek" / "index.html").read_text(encoding="utf-8")
-        assert 'class="gal-slide cover"' in html and "/img/p1-g3.webp" in html and "Görsel: Marka" in html
-        assert html.index("/img/p1-g1.webp") < html.index('class="art-body"') < html.index("/img/p1-g3.webp")
+        assert not (cfg.out_dir / "img" / "p1.webp").exists()            # yazılı kapak sitede kullanılmıyor
+        html = (cfg.out_dir / cfg.post_path(p) / "index.html").read_text(encoding="utf-8")
+        assert "/img/p1-g3.webp" in html and "Görsel: Marka" in html and "https://x/doc.jpg" in html
+        assert html.index("/img/p1-g0.webp") < html.index('class="art-body"') < html.index("/img/p1-g1.webp")
         # düğmeler: başka foto, yazılı kapak, fotoğrafsız
         assert [b["callback_data"][0] for b in a._visual_buttons(p)] == ["g", "v", "n"]
@@ -189,5 +191,6 @@
         assert a._visual_buttons(p)[0]["text"].endswith("Fotoğraflı kapak")
         view = SiteBuilder(cfg)._post_view(p)
-        assert view["cover_photo"] is None and len(view["slides"]) >= 2
+        assert view["cover_photo"] is None and view["disp"]["kind"] == "art"
+        assert view["body_html"].count('<figure class="inl') == 5
         a._on_button("g", "p1")                                # fotoğraflı kapağa dönüş
         assert a.store.load_post("p1")["image"]["source"] == "photo"
@@ -210,5 +213,6 @@
         from haberbot.site import SiteBuilder
         view = SiteBuilder(cfg)._post_view(p)
-        assert [x["file"] for x in view["slides"]] == ["p1-g0.webp"] and 'class="inl graphic"' in view["body_html"]
+        assert view["disp"]["kind"] == "art" and view["slides"] == []        # küçük fotoğraf ana görsel olmaz
+        assert view["body_html"].count('<figure class="inl') == 2 and 'class="inl graphic"' in view["body_html"]
 
 
@@@SM@@@ SHA
b63e5da4ca782fe1fe3f03f3f31c5c4418232ee39c37de651765a3befb151d4c config.yaml
72ddef34abd0002d6d517cc458b482eea98e35b71ca7ca48e93449f8fd5a2ecb haberbot/app.py
8657f000233d528523c000b007cdf63ca40f7d8ab24328b792ae500c462fe445 haberbot/config.py
e995c57aeca352d9e182c60f5b2b1a94a844964f2212d09d8bf029a6165d05b8 haberbot/covers.py
d6aee6172b48e927363fcb86e5e882e3479cc9aed7502407ddc89610c25d222c haberbot/photos.py
36c4b22b7ddbf035a9a3df839276d608aeefc6eab41a9457adceb137c890e1f3 haberbot/prompts.py
b83abc1a4ffac9fa69a7465c22aa692f2cd249ad559ea2eeb1c8cce72fa98bd4 haberbot/site.py
4d8ee748bf057d8535826a433aabf70ac29d1d4f6457e82700cd102121554a6b haberbot/textfix.py
5b09b488f0536fb197018148020ef3122db4794280a8b732d81bb35c3a1a7be1 haberbot/visuals.py
779d855c956d934cfd2fd5f699acad8cd3a2538b441cd9a97c5df6c8177e6f3f static/site.js
6eeb9c51121cd4101682444e3a56e7c5b0f4c1d6869c4db58990127a01851111 static/style.css
a95a114d7af39a873cc6b6e5cfdd19a18e5e4993c37742d5beabdd5ad8584f4e templates/_macros.html
09bfa262e0c38fa1b66bac6290d1e82f8f5bb9078e6d057abc97129a5affe3bf templates/article.html
8c442a43c28ac7f3df2a82cada8e0be3b283c12fea04545675d9a5807c9fdf0a templates/category.html
3c9497b3f02e84a90df838ad11c51c5c4104985b703e205d1c5c7c90a27ca223 templates/index.html
d10c300ab9c77ccfa74e4162336fd30f538e9b26b6370e24efc0778bad1a4fad templates/sitemap.xml
efc9c0bf81353168a37a49fd7e3e2d8432b20e2abd917c190957dfa23a70ca69 tests/test_editor.py
a40c26eadc017e1531db4063c8e5422438bec5d19ea0333035c9ff905053f612 tests/test_home.py
8870cf965707ab856b580f61be33abf6019afdda2de324514480cec1052bfbc4 tests/test_photos.py
