SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -55,4 +55,5 @@
 COMMANDS_VERSION = 4
 COVERLINE_V = 3               # kapak başlığı yazım kuralları değişince eski haberlerin kapak başlıkları yeniden yazılır
+PHOTO_VET_V = 2               # fotoğraf editörü ölçütleri değişince artır: son iki haftanın fotoğrafları yeniden denetlenir
 RESELECT_V = 1                # seçki ölçütleri değişince artır: onay bekleyen yığın bir kez yeniden elden geçer
 KEYBOARD_VERSION = 4          # yayındaki haber mesajlarının düğmeleri bu sürüme göre bir kez yenilenir
@@ -2026,5 +2027,6 @@
     def _vet_photos(self, d: dict, got: list[dict]) -> list[dict]:
         """Yapay zeka fotoğraf editörü: kaynak sayfadan gelen görsellerden habere ait olmayanları (reklam, alışveriş
-        önerisi, başka haberin küçük resmi…) ayıklar ve en iyi görseli başa alır. Yanıt alınamazsa liste olduğu gibi kalır."""
+        önerisi, başka haberin küçük resmi…) ve üstüne başlık / yazı basılmış olanları ayıklar, en iyi görseli başa alır.
+        Yanıt alınamazsa liste olduğu gibi kalır."""
         if not got or not self.llm or not self.cfg.get("images", "vet_photos", True):
             return got
@@ -2037,13 +2039,15 @@
             log.warning("Fotoğraf editörü yanıt vermedi, fotoğraflar ayıklanmadan kullanılacak: %s", str(e)[:160])
             return got
-        keep = [int(i) for i in out.get("keep") or [] if str(i).lstrip("-").isdigit() and 0 <= int(i) < len(got)]
-        keep = list(dict.fromkeys(keep))
-        dropped = len(got) - len(keep)
-        if dropped:
-            log.info("Fotoğraf editörü %d görseli habere ait bulmadı (%s)", dropped, d.get("id"))
+        idx = lambda xs: [int(i) for i in xs or [] if str(i).lstrip("-").isdigit() and 0 <= int(i) < len(got)]  # noqa: E731
+        texty, wanted = set(idx(out.get("text"))), list(dict.fromkeys(idx(out.get("keep"))))
+        keep = [i for i in wanted if i not in texty]
+        if len(keep) < len(got):
+            log.info("Fotoğraf editörü %d görseli ayıkladı: %d ilgisiz, %d üzerinde yazı var (%s)", len(got) - len(keep),
+                     len(set(range(len(got))) - set(wanted) - texty), len(texty), d.get("id"))
         return [got[i] for i in keep]
 
-    def vet_existing_photos(self, per_run: int = 6) -> None:
-        """Son iki haftanın haberlerindeki fotoğrafları fotoğraf editöründen bir kez geçir (reklam / ilgisiz görsel temizliği)."""
+    def vet_existing_photos(self, per_run: int = 10) -> None:
+        """Son iki haftanın haberlerindeki fotoğrafları fotoğraf editöründen bir kez geçir (reklam / ilgisiz / yazılı görsel
+        temizliği). En yeni haberler önce. Yazısız fotoğrafı kalmayan habere Wikipedia'da fotoğraf aranır."""
         if self.cfg.mock or not self.llm or not self.cfg.get("images", "vet_photos", True):
             return
@@ -2051,6 +2055,10 @@
         folder = self.cfg.images_dir
         todo = [p for p in self.store.posts()
-                if p.get("photos") and not p.get("photos_vetted") and hours_since(p.get("published_at")) <= 24 * 14][:per_run]
+                if p.get("photos") and int(p.get("photos_vet_v") or 0) < PHOTO_VET_V
+                and hours_since(p.get("published_at")) <= 24 * 14][:per_run]
+        t0 = time.monotonic()
         for p in todo:
+            if time.monotonic() - t0 > 150:      # turu uzatmasın; kalanlar sonraki turda
+                break
             recs, ims = [], []
             for r in p["photos"]:
@@ -2067,5 +2075,5 @@
                     ims.append({"image": im})
             if not ims:
-                p["photos_vetted"] = iso(now_utc())
+                p["photos_vetted"], p["photos_vet_v"] = iso(now_utc()), PHOTO_VET_V
                 self.store.save_post(p)
                 continue
@@ -2076,5 +2084,5 @@
             keep_ids = {id(x) for x in kept}
             new = [r for r, x in zip(recs, ims) if id(x) in keep_ids]
-            p["photos_vetted"] = iso(now_utc())
+            p["photos_vetted"], p["photos_vet_v"] = iso(now_utc()), PHOTO_VET_V
             if len(new) < before:
                 gone = {r.get("file") for r in p["photos"] if r not in new and r.get("file")}
@@ -2084,5 +2092,8 @@
                 if not new:
                     p.pop("photos", None)
-                if (p.get("image") or {}).get("photo") in gone or not new:
+                    if self._attach_photos(p, draft=False, got=[]):     # yazısız fotoğraf kalmadı: Wikipedia'da ara
+                        log.info("Yazılı görsellerin yerine Wikipedia fotoğrafı: %s", p["id"])
+                        gone = set()
+                if (p.get("image") or {}).get("photo") in gone or not p.get("photos"):
                     try:
                         self._build_cover(p, draft=False)
@@ -2091,5 +2102,5 @@
                         log.warning("Kapak yenilenemedi (%s): %s", p["id"], e)
                 p["updated_at"] = iso(now_utc())
-                log.info("İlgisiz fotoğraflar kaldırıldı: %s (%d → %d)", p["id"], before, len(new))
+                log.info("İlgisiz / yazılı fotoğraflar kaldırıldı: %s (%d → %d)", p["id"], before, len(p.get("photos") or []))
             self.store.save_post(p)
 
@@ -2159,5 +2170,14 @@
             log.warning("Fotoğraflar alınamadı (%s): %s", d.get("id"), e)
             return False
-        got = self._vet_photos(d, got)
+        vetted = self._vet_photos(d, got)
+        if not vetted and not any(g.get("credit") == "Wikipedia" for g in got):
+            # kaynaklardaki fotoğrafların hepsi ilgisiz ya da üstü yazılı: haberin konusunun Wikipedia fotoğrafı
+            try:
+                w = photos.wiki_photo(self._photo_names(d))
+            except Exception as e:  # noqa: BLE001
+                log.warning("Wikipedia fotoğrafı alınamadı (%s): %s", d.get("id"), e)
+                w = None
+            vetted = self._vet_photos(d, [w]) if w else []
+        got = vetted
         if not got:
             return False
--- a/haberbot/llm.py
+++ b/haberbot/llm.py
@@ -330,5 +330,5 @@
             self.usage_cb(model, len(user) // 4, 300)
         if "keep" in schema.get("properties", {}):        # fotoğraf editörü: hepsi ilgili
-            return {"keep": list(range(len(images or [])))}
+            return {"keep": list(range(len(images or []))), "text": []}
         if "stories" in schema.get("properties", {}):
             return self._triage(user)
--- a/haberbot/photos.py
+++ b/haberbot/photos.py
@@ -388,5 +388,5 @@
 
 
-def thumb_jpeg(im: Image.Image, size: int = 384) -> bytes:
+def thumb_jpeg(im: Image.Image, size: int = 512) -> bytes:
     """Yapay zeka fotoğraf editörüne gönderilecek küçük kopya."""
     t = im.convert("RGB").copy()
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -489,6 +489,7 @@
 PHOTO_SCHEMA = {
     "type": "object",
-    "properties": {"keep": {"type": "array", "items": {"type": "integer"}}},
-    "required": ["keep"],
+    "properties": {"keep": {"type": "array", "items": {"type": "integer"}},
+                   "text": {"type": "array", "items": {"type": "integer"}}},
+    "required": ["keep", "text"],
     "additionalProperties": False,
 }
@@ -503,5 +504,11 @@
 Drop everything else, in particular: advertisements and shopping/deal promos (unrelated products such as keychains,
 mice, scales, gadgets for sale), thumbnails of other articles, unrelated products or cars, logos and banners of the news
-outlet, author photos, app-store badges, generic stock images that do not show the subject. When unsure, drop it."""
+outlet, author photos, app-store badges, generic stock images that do not show the subject. When unsure, drop it.
+Return in "text" the numbers of ALL images (kept or not) that have words ADDED ON TOP of the picture by a publisher: a
+headline or title, a caption, a slogan, "NEW" / "LEAKED" / "BREAKING" style banners, price tags, big outlet logos, or a
+thumbnail / collage designed with words. Our site prints its own headline next to the image, so such images look like a
+second, clashing headline and are never shown. Text that is naturally part of the scene does NOT count (a sign, a license
+plate, a brand name or model badge on the product, an app on a phone screen, a slide on a stage behind a speaker, a
+screenshot of the product's own interface), and neither does a small, unobtrusive watermark in a corner."""
 
 
--- a/tests/test_photos.py
+++ b/tests/test_photos.py
@@ -336,4 +336,45 @@
 
 
+def test_photo_editor_drops_images_with_headline_text():
+    # üstüne başlık basılmış görseller (ör. "TESLA SUPERCHARGER İSTASYONU AÇILDI") hiç gösterilmez
+    real_wiki = photos.wiki_photo
+    with _App() as (cfg, a):
+        class Editor:
+            def json(self, model, system, user, schema, max_tokens=0, effort=None, images=None):
+                assert "text" in schema["properties"]
+                n = len(images or [])
+                return {"keep": list(range(n)), "text": [0] if n > 1 else []}   # 0 numaranın üstünde başlık yazısı var
+        a.llm = Editor()
+        got = [{"image": _photo("#446", seed=i), "src": f"https://x/{i}.jpg"} for i in range(3)]
+        assert [g["src"] for g in a._vet_photos({"id": "d1", "title": "T", "summary": ""}, got)] == \
+            ["https://x/1.jpg", "https://x/2.jpg"]
+        # yayındaki haber: kapak yazılı görseldi → yazısız fotoğraf kapak olur
+        a.store.save_post(_post())
+        appmod.photos.gather = lambda *a_, **k: [{"image": _photo("#446", seed=i), "src": f"https://x/{i}.jpg", "credit": "M",
+                                                  "page": "https://p", "alt": "", "kind": "og" if i == 0 else "body",
+                                                  "graphic": False} for i in range(2)]
+        a.llm = None
+        a.backfill_photos(5)
+        assert a.store.load_post("p1")["image"]["photo"] == "p1-g0.webp"
+        a.llm = Editor()
+        a.vet_existing_photos()
+        p = a.store.load_post("p1")
+        assert [r["src"] for r in p["photos"]] == ["https://x/1.jpg"] and p["photos_vet_v"] == appmod.PHOTO_VET_V
+        assert p["image"]["source"] == "photo" and p["image"]["src"] == "https://x/1.jpg"
+        # bütün fotoğrafları yazılıysa haberin konusunun Wikipedia fotoğrafı aranır
+        class AllText(Editor):
+            def json(self, model, system, user, schema, max_tokens=0, effort=None, images=None):
+                n = len(images or [])
+                return {"keep": list(range(n)), "text": list(range(n)) if n > 1 else []}
+        a.llm = AllText()
+        photos.wiki_photo = lambda names: {"image": _photo("#335", seed=7), "src": "https://upload.wikimedia.org/t.jpg",
+                                           "credit": "Wikipedia", "page": "https://tr.wikipedia.org/wiki/T", "alt": "T",
+                                           "kind": "wiki", "graphic": False, "cover_ok": True}
+        assert a._attach_photos(p, draft=False)
+        assert [r["credit"] for r in p["photos"]] == ["Wikipedia"]
+        appmod.photos.gather = _REAL_GATHER
+    photos.wiki_photo = real_wiki
+
+
 def test_migrate_old_layout():
     with _App() as (cfg, a):
@@@SM@@@ SHA
67dcf0afd6216ed71a6554a0e846cdc8fadae06ce483bd63fb5f57b10d8441b8 haberbot/app.py
350b511d61766c565d8489628c787375160fac183872c548871761a0f865327f haberbot/llm.py
f9730ed25d74bd4b7b65f239a15f787008201ca1504c820ba74f8a7047e7c5ec haberbot/photos.py
3525ee709d5167b3928669e0485f2d03e143b9b25bf4f0416f7ee0b02a123e28 haberbot/prompts.py
273de17572d5f172e9b5651ae3093ce13b271c9650ca9fb43a7e4ce0b0242342 tests/test_photos.py
