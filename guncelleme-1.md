SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -17,5 +17,6 @@
 from .instagram import Instagram, InstagramError, TokenStore, fingerprint, head_ok
 from .llm import LLMError, MockLLM, estimate_cost, make_llm
-from .prompts import (APPEAL_SCHEMA, COVERLINE_SCHEMA, EDIT_SCHEMA, FLAG_LABELS, FLAGS, SEO_SCHEMA, TRIAGE_SCHEMA,
+from .prompts import (APPEAL_SCHEMA, COVERLINE_SCHEMA, EDIT_SCHEMA, FLAG_LABELS, FLAGS, PHOTO_SCHEMA, SEO_SCHEMA, TRIAGE_SCHEMA,
+                      photo_system, photo_user,
                       WRITE_SCHEMA, appeal_system, appeal_user, coverline_system, coverline_user, edit_system, edit_user,
                       seo_system, seo_user, triage_system, triage_user, write_system, write_user)
@@ -428,4 +429,8 @@
         cap = int(self.cfg.get("editorial", "max_per_company_per_day", 0) or 0)   # 0 = sınır yok
         today_n, target = self.store.count(self.today(), "drafts"), self._daily_target()
+        # Kuraklık kuralı: gündüz 3 saattir hiç haber gelmediyse, eşiğin bir altındaki en iyi aday da yazılır
+        # (seçicilik sürer ama akış tamamen durmaz)
+        last = self.state.get("last_draft_at")
+        drought = not self.quiet() and (last is None or hours_since(last) >= 3) and today_n < target
         day_keys: dict[str, int] = {}
         for c in covered:
@@ -457,4 +462,7 @@
                         round_targets.add(x["target"])
                     continue
+            if (drought and x["action"] in ("skip", "hold") and not x.get("target") and mr >= min_score - 1
+                    and (s.get("duplicate_of") or "").removeprefix("s:") not in published):
+                x["action"] = "publish"          # kuraklık: eşiğin bir altındaki en iyi aday yazılabilir
             if x["action"] != "publish":
                 continue
@@ -466,5 +474,9 @@
                     round_targets.add(dup)
                 continue
-            if mr < min_score:
+            if mr < min_score and drought and mr >= min_score - 1 and used == 0 and x["action"] == "publish":
+                used += 1
+                drought = False
+                x["reason"] = (x.get("reason") or "") + " (uzun süredir haber yoktu)"
+            elif mr < min_score:
                 x["action"], x["reason"] = "skip", f"önem {mr}/10, eşik {min_score}"
             elif mr < 9 and today_n + used >= target:
@@ -704,4 +716,5 @@
             self._image_feedback(d["image"])
         st.bump(self.today(), "drafts")
+        self.state["last_draft_at"] = iso(now_utc())
         decision, reason = policy.decide(cfg, self.state, self.stats, d)
         d["policy_reason"] = reason
@@ -2036,4 +2049,74 @@
         d["image"] = self.vis.make_hero(d, hero)
 
+    def _vet_photos(self, d: dict, got: list[dict]) -> list[dict]:
+        """Yapay zeka fotoğraf editörü: kaynak sayfadan gelen görsellerden habere ait olmayanları (reklam, alışveriş
+        önerisi, başka haberin küçük resmi…) ayıklar ve en iyi görseli başa alır. Yanıt alınamazsa liste olduğu gibi kalır."""
+        if not got or not self.llm or not self.cfg.get("images", "vet_photos", True):
+            return got
+        try:
+            thumbs = [photos.thumb_jpeg(g["image"]) for g in got]
+            out = self.llm.json(self.cfg.get("ai", "triage_model", "gemini-flash-lite-latest"), photo_system(),
+                                photo_user(d.get("title", ""), d.get("summary", ""), len(got)), PHOTO_SCHEMA,
+                                max_tokens=800, images=thumbs)
+        except Exception as e:  # noqa: BLE001
+            log.warning("Fotoğraf editörü yanıt vermedi, fotoğraflar ayıklanmadan kullanılacak: %s", str(e)[:160])
+            return got
+        keep = [int(i) for i in out.get("keep") or [] if str(i).lstrip("-").isdigit() and 0 <= int(i) < len(got)]
+        keep = list(dict.fromkeys(keep))
+        dropped = len(got) - len(keep)
+        if dropped:
+            log.info("Fotoğraf editörü %d görseli habere ait bulmadı (%s)", dropped, d.get("id"))
+        return [got[i] for i in keep]
+
+    def vet_existing_photos(self, per_run: int = 6) -> None:
+        """Son iki haftanın haberlerindeki fotoğrafları fotoğraf editöründen bir kez geçir (reklam / ilgisiz görsel temizliği)."""
+        if self.cfg.mock or not self.llm or not self.cfg.get("images", "vet_photos", True):
+            return
+        from PIL import Image
+        folder = self.cfg.images_dir
+        todo = [p for p in self.store.posts()
+                if p.get("photos") and not p.get("photos_vetted") and hours_since(p.get("published_at")) <= 24 * 14][:per_run]
+        for p in todo:
+            recs, ims = [], []
+            for r in p["photos"]:
+                im = None
+                if r.get("file") and (folder / r["file"]).exists():
+                    try:
+                        im = Image.open(folder / r["file"]).convert("RGB")
+                    except OSError:
+                        im = None
+                elif r.get("src"):
+                    im = photos.fetch_image(r["src"], r.get("page") or "")
+                if im is not None:
+                    recs.append(r)
+                    ims.append({"image": im})
+            if not ims:
+                p["photos_vetted"] = iso(now_utc())
+                self.store.save_post(p)
+                continue
+            before = len(ims)
+            kept = self._vet_photos(p, ims)
+            if kept is ims:                  # editör yanıt vermedi: sonra tekrar denenir
+                return
+            keep_ids = {id(x) for x in kept}
+            new = [r for r, x in zip(recs, ims) if id(x) in keep_ids]
+            p["photos_vetted"] = iso(now_utc())
+            if len(new) < before:
+                gone = {r.get("file") for r in p["photos"] if r not in new and r.get("file")}
+                for f in gone:
+                    (folder / f).unlink(missing_ok=True)
+                p["photos"] = new
+                if not new:
+                    p.pop("photos", None)
+                if (p.get("image") or {}).get("photo") in gone or not new:
+                    try:
+                        self._build_cover(p, draft=False)
+                        self._make_og(p)
+                    except Exception as e:  # noqa: BLE001
+                        log.warning("Kapak yenilenemedi (%s): %s", p["id"], e)
+                p["updated_at"] = iso(now_utc())
+                log.info("İlgisiz fotoğraflar kaldırıldı: %s (%d → %d)", p["id"], before, len(new))
+            self.store.save_post(p)
+
     @staticmethod
     def _photo_names(d: dict) -> list[str]:
@@ -2101,4 +2184,5 @@
             log.warning("Fotoğraflar alınamadı (%s): %s", d.get("id"), e)
             return False
+        got = self._vet_photos(d, got)
         if not got:
             return False
@@ -2296,4 +2380,5 @@
                 log.exception("Metin/ilgi puanı hatası: %s", e)
             try:
+                self.vet_existing_photos()
                 self.more_photos()
                 self.recheck_wiki_photos()
--- a/haberbot/llm.py
+++ b/haberbot/llm.py
@@ -2,4 +2,5 @@
 from __future__ import annotations
 
+import base64
 import json
 import re
@@ -68,6 +69,6 @@
 
     def json(self, model: str, system: str, user: str, schema: dict,
-             max_tokens: int = 4000, effort: str | None = None) -> dict:
-        """Şemaya uyan JSON döndürür. Model/sürüm farklarına karşı kademeli geri çekilir."""
+             max_tokens: int = 4000, effort: str | None = None, images: list[bytes] | None = None) -> dict:
+        """Şemaya uyan JSON döndürür. Model/sürüm farklarına karşı kademeli geri çekilir. images: JPEG baytları."""
         use_effort = bool(effort) and "haiku" not in model
         variants = []
@@ -84,5 +85,8 @@
                 "max_tokens": max_tokens,
                 "system": system,
-                "messages": [{"role": "user", "content": user}],
+                "messages": [{"role": "user", "content": user if not images else (
+                    [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
+                                                  "data": base64.b64encode(b).decode()}} for b in images]
+                    + [{"type": "text", "text": user}])}],
             }
             if oc_variant is not None:
@@ -206,8 +210,9 @@
 
     def json(self, model: str, system: str, user: str, schema: dict,
-             max_tokens: int = 4000, effort: str | None = None) -> dict:
+             max_tokens: int = 4000, effort: str | None = None, images: list[bytes] | None = None) -> dict:
+        parts = [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(b).decode()}} for b in images or []]
         base = {
             "systemInstruction": {"parts": [{"text": system}]},
-            "contents": [{"role": "user", "parts": [{"text": user}]}],
+            "contents": [{"role": "user", "parts": parts + [{"text": user}]}],
         }
         gen = {"responseMimeType": "application/json", "maxOutputTokens": max(max_tokens, 8192)}
@@ -321,7 +326,9 @@
         self.usage_cb = k.get("usage_cb")
 
-    def json(self, model, system, user, schema, max_tokens=4000, effort=None) -> dict:
+    def json(self, model, system, user, schema, max_tokens=4000, effort=None, images=None) -> dict:
         if self.usage_cb:
             self.usage_cb(model, len(user) // 4, 300)
+        if "keep" in schema.get("properties", {}):        # fotoğraf editörü: hepsi ilgili
+            return {"keep": list(range(len(images or [])))}
         if "stories" in schema.get("properties", {}):
             return self._triage(user)
--- a/haberbot/photos.py
+++ b/haberbot/photos.py
@@ -94,4 +94,33 @@
 
 
+# reklam / alışveriş / öneri bloklarının sınıf adlarında geçen sözcükler (bu blokların içindeki görseller habere ait değil)
+BAD_BLOCK = {"ad", "ads", "advert", "adverts", "advertisement", "adsbygoogle", "reklam", "banner", "sponsor", "sponsored",
+             "promo", "promotion", "affiliate", "commerce", "ecommerce", "shop", "shopping", "product", "products", "deal",
+             "deals", "kampanya", "campaign", "teaser", "outbrain", "taboola", "related", "recommended", "recommend",
+             "popular", "trending", "widget", "newsletter", "author", "avatar", "share", "comments", "subscribe", "firsat",
+             "alisveris", "indirim", "partner", "native"}
+
+
+def _bad_block(el, stop=None) -> bool:
+    """Görsel, haber metninin içindeki bir reklam / alışveriş / öneri bloğunda mı? (metin kökünün üstüne bakılmaz)"""
+    for anc in [el, *el.parents]:
+        if anc is stop or getattr(anc, "name", None) in (None, "[document]", "body", "html"):
+            break
+        names = " ".join([*(anc.get("class") or []), anc.get("id") or "", anc.get("data-ad") and "ad" or ""]).lower()
+        if set(re.split(r"[^a-z0-9]+", names)) & BAD_BLOCK:
+            return True
+    return False
+
+
+def _foreign_link(el, base_url: str) -> bool:
+    """Görsel başka bir siteye giden bir bağlantının içindeyse (alışveriş / reklam bağlantısı) habere ait değildir."""
+    a = el.find_parent("a")
+    href = (a.get("href") or "") if a else ""
+    if not href.startswith("http") or re.search(r"\.(jpe?g|png|webp|avif)(\?|$)", href, re.I):
+        return False
+    host = lambda u: ".".join(urlsplit(u).netloc.lower().split(".")[-2:])  # noqa: E731
+    return host(href) != host(base_url)
+
+
 def candidates(html: str, base_url: str, limit: int = 48) -> list[dict]:
     """Sayfadaki fotoğraf adayları: paylaşım görseli, yapılandırılmış veri, metin içi fotoğraflar."""
@@ -143,5 +172,5 @@
             bad.decompose()
         for img in root.find_all(["img", "source"]):
-            if img.find_parent(class_=re.compile(r"(author|avatar|related|recommend|share|comment|newsletter|promo|sponsor|widget)", re.I)):
+            if _bad_block(img, root) or _foreign_link(img, base_url):
                 continue
             srcset = img.get("data-srcset") or img.get("srcset") or img.get("data-lazy-srcset") or ""
@@ -357,2 +386,11 @@
     out.parent.mkdir(parents=True, exist_ok=True)
     im.crop((x, y, x + tw, y + th)).save(out, "JPEG", quality=84, optimize=True, progressive=True)
+
+
+def thumb_jpeg(im: Image.Image, size: int = 384) -> bytes:
+    """Yapay zeka fotoğraf editörüne gönderilecek küçük kopya."""
+    t = im.convert("RGB").copy()
+    t.thumbnail((size, size))
+    buf = io.BytesIO()
+    t.save(buf, "JPEG", quality=72)
+    return buf.getvalue()
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -483,2 +483,26 @@
     return "\n".join(f"{p['id']} | {p.get('title', '')} | {p.get('summary', '')} "
                      f"{' '.join((p.get('carousel_points') or [])[:3])}".rstrip() for p in posts)
+
+
+# ── Fotoğraf editörü: kaynak sayfadan gelen fotoğraflar habere mi ait? ──
+PHOTO_SCHEMA = {
+    "type": "object",
+    "properties": {"keep": {"type": "array", "items": {"type": "integer"}}},
+    "required": ["keep"],
+    "additionalProperties": False,
+}
+
+
+def photo_system() -> str:
+    return """You are the photo editor of a Turkish tech news site. You receive candidate images scraped from the source
+pages of ONE news story, numbered in the order they are attached (0, 1, 2, …), and the story's title and summary.
+Return in "keep" the numbers of the images that clearly belong to THIS story: the product, car, device, game, company,
+people, place or event the story is about, or a screenshot / chart / document of it. Order "keep" from the best image to
+show at the top of the article (a clear, attractive photo of the main subject) to the least important.
+Drop everything else, in particular: advertisements and shopping/deal promos (unrelated products such as keychains,
+mice, scales, gadgets for sale), thumbnails of other articles, unrelated products or cars, logos and banners of the news
+outlet, author photos, app-store badges, generic stock images that do not show the subject. When unsure, drop it."""
+
+
+def photo_user(title: str, summary: str, n: int) -> str:
+    return f"STORY TITLE: {title}\nSUMMARY: {summary}\nNUMBER OF IMAGES: {n} (numbered 0 to {n - 1} in order)"
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -18,5 +18,5 @@
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "15"
+ASSET_V = "16"
 FOREIGN_PRICE = re.compile(r"(?=.*fiyat)(?=.*(\$|€|£|¥|dolar|euro|avro|sterlin|yuan|yen\b))", re.I)
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
@@ -468,9 +468,6 @@
         home = self._home(posts, n_feat)
         featured = home["featured"]
-        for p in featured:
-            if p["disp"].get("file"):
-                p["slide_bg"], p["slide_dark"] = edge_color(cfg.images_dir / p["disp"]["file"])
-            else:
-                p["slide_bg"], p["slide_dark"] = p["disp"]["base"], True
+        for p in featured:   # manşette tek, sakin bir zemin: görselden renk alınmaz (her slaytta başka renk olmasın)
+            p["slide_bg"], p["slide_dark"] = "#F5F5F7", False
         shown = set(home["shown"])
         rails = []
--- a/static/style.css
+++ b/static/style.css
@@ -92,7 +92,8 @@
 .mkt-item:hover::before, .mkt-item:hover + .mkt-item::before { opacity: 0; }
 .mkt-item[hidden] { display: none; }
-.mkt-ic { flex: none; width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; color: #fff; font-size: 14px;
-  font-weight: 700; letter-spacing: -.02em; background: linear-gradient(145deg, color-mix(in srgb, var(--ic) 78%, #fff), var(--ic));
-  box-shadow: inset 0 -1px 0 rgba(0,0,0,.12); }
+/* simgeler tek renk (sakin görünüm); renk yalnızca artış / düşüşte */
+.mkt-ic { flex: none; width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; color: var(--ink); font-size: 14px;
+  font-weight: 700; letter-spacing: -.02em; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,.08); }
+.mkt-item:hover .mkt-ic { background: var(--bg-alt); }
 .mkt-tx { display: grid; gap: 1px; min-width: 0; }
 .mkt-n { font-size: 12px; font-weight: 500; color: var(--muted); white-space: nowrap; }
@@ -160,4 +161,8 @@
 .slide.dark .more { color: #6CB4FF; }
 .slide.dark .stat-chip, .slide.dark .upd-chip { background: rgba(255,255,255,.16); color: #fff; }
+/* manşette kategori etiketi sade: beyaz zemin, kategori rengi yalnızca küçük bir noktada */
+.slide .chip { background: #fff; color: var(--ink); font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,.06); }
+.slide .chip::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--c); }
+.slide .upd-chip::before { display: none; }
 @media (max-width: 599px) { .slide-dek { display: none; } }
 /* Telefonda manşet tek parça: görsel tüm kartı kaplar, başlık altta görselin üstünde */
@@ -171,5 +176,5 @@
   .slide-meta { color: rgba(255,255,255,.78); font-size: 13px; }
   .slide .more { display: none; }
-  .slide .upd-chip, .slide .stat-chip { background: rgba(255,255,255,.18); color: #fff; }
+  .slide .chip, .slide .upd-chip, .slide .stat-chip { background: rgba(255,255,255,.18); color: #fff; box-shadow: none; }
   .slide .chip { -webkit-backdrop-filter: blur(6px); backdrop-filter: blur(6px); }
 }
--- a/tests/test_editor.py
+++ b/tests/test_editor.py
@@ -123,4 +123,19 @@
 
 
+def test_drought_lets_best_near_miss_through():
+    with _App() as (cfg, a):
+        a.quiet = lambda: False
+        queue = [_q("Notable gadget launch", 7, ["Foo"]), _q("Another one", 7, ["Bar"]), _q("Dup story", 7, ["Baz"])]
+        dec = lambda: {0: {"action": "skip", "target": "", "must_read": 7, "reason": ""},  # noqa: E731
+                       1: {"action": "hold", "target": "", "must_read": 7, "reason": ""},
+                       2: {"action": "skip", "target": "p01", "must_read": 7, "reason": ""}}
+        a.state["last_draft_at"] = iso(now_utc())                    # az önce haber geldi: kural devrede değil
+        out = a._guard(queue, dec(), slots=2, min_score=8, covered=a._covered(48))
+        assert [out[i]["action"] for i in range(3)] == ["skip", "hold", "skip"]
+        a.state["last_draft_at"] = iso(now_utc() - timedelta(hours=4))  # 4 saattir haber yok
+        out = a._guard(queue, dec(), slots=2, min_score=8, covered=a._covered(48))
+        assert sum(out[i]["action"] == "publish" for i in range(3)) == 1 and out[2]["action"] == "skip"
+
+
 def test_daily_target_and_backlog_reselection():
     with _App() as (cfg, a):
--- a/tests/test_photos.py
+++ b/tests/test_photos.py
@@ -297,4 +297,43 @@
 
 
+def test_photo_editor_drops_unrelated_images():
+    # sayfadaki reklam / alışveriş bloğu ve başka siteye giden bağlantıdaki görseller aday olmaz
+    html = """<html><body><article class="post-content">
+      <p><img src="https://site.com/byd-seal-07.jpg" width="1200"></p>
+      <div class="wt-shopping-box"><img src="https://site.com/anahtarlik-mouse.jpg" width="1200"></div>
+      <a href="https://www.hepsiburada.com/x"><img src="https://site.com/kampanya.jpg" width="1200"></a>
+      <a href="https://site.com/byd-big.jpg"><img src="https://site.com/byd-2.jpg" width="1200"></a>
+    </article></body></html>"""
+    urls = [c["url"] for c in photos.candidates(html, "https://site.com/haber")]
+    assert urls == ["https://site.com/byd-seal-07.jpg", "https://site.com/byd-2.jpg"]
+    with _App() as (cfg, a):
+        class Editor:
+            seen = []
+
+            def json(self, model, system, user, schema, max_tokens=0, effort=None, images=None):
+                Editor.seen.append(len(images or []))
+                return {"keep": [2, 0, 9]}                    # 1 numara ilgisiz; 9 yok sayılır
+        a.llm = Editor()
+        got = [{"image": _photo("#446", seed=i), "src": f"https://x/{i}.jpg"} for i in range(3)]
+        kept = a._vet_photos({"id": "d1", "title": "BYD Seal 07", "summary": "s"}, got)
+        assert [g["src"] for g in kept] == ["https://x/2.jpg", "https://x/0.jpg"] and Editor.seen == [3]
+        # yayındaki haberin fotoğrafları da bir kez denetlenir; ilgisiz olan silinir
+        a.store.save_post(_post())
+        appmod.photos.gather = lambda *a_, **k: [{"image": _photo("#446", seed=i), "src": f"https://x/{i}.jpg", "credit": "M",
+                                                  "page": "https://p", "alt": "", "kind": "body", "graphic": False}
+                                                 for i in range(3)]
+        a.llm = None
+        a.backfill_photos(5)
+        assert len(a.store.load_post("p1")["photos"]) == 3
+        a.llm = Editor()
+        a.vet_existing_photos()
+        p = a.store.load_post("p1")
+        assert [r["src"] for r in p["photos"]] == ["https://x/0.jpg", "https://x/2.jpg"] and p["photos_vetted"]
+        assert not (cfg.images_dir / "p1-g1.webp").exists()
+        a.vet_existing_photos()                                    # ikinci kez denetlenmez
+        assert Editor.seen == [3, 3]
+        appmod.photos.gather = _REAL_GATHER
+
+
 def test_migrate_old_layout():
     with _App() as (cfg, a):
@@@SM@@@ SHA
f6e62fed7d7d56fa6f37eb9332ada6235bb509bb4b7550cd72eeb8efa5efd49d haberbot/app.py
933de4cb588c99a1034d16be479f2dbbcba7c6391a63cefb36892e3a77c8f777 haberbot/llm.py
98da61f5a1a73f78b8531e3842cf161813379e67cb78c5ac4bd3d5e8fa9b0ecf haberbot/photos.py
a86d2360ec9030fb85930aca401849c65cb192e9f7628504556be65172d502e0 haberbot/prompts.py
2f4cfbf497e4bf0706c42e3e97dc7c579c325792bcdac0d31c67b4a3d97350da haberbot/site.py
9fc190ccd8b16624ecc339b28f63757c9a1490eab55abdb1ee731f9b979e090d static/style.css
ed4f042ab42b0ba884398cf4e4da1948da9f28109b444dd4793d1a0fe2c9c4c7 tests/test_editor.py
b5d2d96cc367b5c6e11f8008f3fe745067e15e25c2b86876d700d4055404d941 tests/test_photos.py
