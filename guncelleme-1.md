SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -1497,6 +1497,16 @@
             if p.get("photos_removed") or (p.get("image") or {}).get("source") == "ai":
                 continue
-            if self._attach_photos(p, draft=False):
-                log.info("Daha çok fotoğraf: %s (%d)", p["id"], len(p["photos"]))
+            before = len(p.get("photos") or [])
+            try:
+                got = photos.gather(p.get("sources") or [], limit=int(self.cfg.get("images", "photo_limit", 16) or 16),
+                                    per_source=int(self.cfg.get("images", "photos_per_source", 12) or 12),
+                                    skip_cover=self._no_cover_sources())
+            except Exception as e:  # noqa: BLE001
+                log.warning("Fotoğraflar alınamadı (%s): %s", p["id"], e)
+                continue
+            if len(got) <= before:          # yeni fotoğraf yoksa mevcutlar korunur
+                continue
+            if self._attach_photos(p, draft=False, got=got):
+                log.info("Daha çok fotoğraf: %s (%d → %d)", p["id"], before, len(p["photos"]))
                 self.store.save_post(p)
 
@@ -2008,5 +2018,5 @@
         d["image"] = self.vis.make_hero(d, hero)
 
-    def _attach_photos(self, d: dict, draft: bool) -> bool:
+    def _attach_photos(self, d: dict, draft: bool, got: list[dict] | None = None) -> bool:
         """Kaynaklardan gerçek fotoğrafları al ve kapağı üret. Bulunamazsa False."""
         cfg = self.cfg
@@ -2014,7 +2024,8 @@
             return False
         try:
-            got = photos.gather(d.get("sources") or [], limit=int(cfg.get("images", "photo_limit", 16) or 16),
-                                per_source=int(cfg.get("images", "photos_per_source", 12) or 12),
-                                skip_cover=self._no_cover_sources())
+            if got is None:
+                got = photos.gather(d.get("sources") or [], limit=int(cfg.get("images", "photo_limit", 16) or 16),
+                                    per_source=int(cfg.get("images", "photos_per_source", 12) or 12),
+                                    skip_cover=self._no_cover_sources())
         except Exception as e:  # noqa: BLE001
             log.warning("Fotoğraflar alınamadı (%s): %s", d.get("id"), e)
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -19,4 +19,5 @@
 
 ASSET_V = "13"
+FOREIGN_PRICE = re.compile(r"(?=.*fiyat)(?=.*(\$|€|£|¥|dolar|euro|avro|sterlin|yuan|yen\b))", re.I)
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
 H2_RE = re.compile(r"<h[1-3]>(.*?)</h[1-3]>", re.S)
@@ -236,5 +237,7 @@
             "short_disp": nobr_hyphen(short),
             "kicker_disp": p.get("kicker") or category_label(cat),
-            "hero_stat": (p.get("hero_stat") or "").strip(),
+            # yurtdışı fiyatı öne çıkarılmaz (Türkiye'ye haber yapıyoruz): "64.050 $" gibi rakamlar kutuda gösterilmez
+            "hero_stat": "" if FOREIGN_PRICE.search(f"{p.get('hero_stat') or ''} {p.get('hero_stat_label') or ''}")
+            else (p.get("hero_stat") or "").strip(),
             "hero_stat_label": (p.get("hero_stat_label") or "").strip(),
             "ai_image": (p.get("image") or {}).get("source") == "ai",
--- a/tests/test_photos.py
+++ b/tests/test_photos.py
@@ -172,4 +172,5 @@
         from haberbot.site import SiteBuilder
         view = SiteBuilder(cfg)._post_view(p)
+        assert view["hero_stat"] == ""                                     # "15 bin €" yurtdışı fiyatı öne çıkarılmaz
         assert view["cover_photo"]["file"] == "p1-g0.webp" and view["disp"]["file"] == "p1-g0.webp"
         assert view["img"] == "/img/p1-g0.webp" and view["slides"] == []
@@ -215,4 +216,22 @@
         assert view["disp"]["kind"] == "art" and view["slides"] == []        # küçük fotoğraf ana görsel olmaz
         assert view["body_html"].count('<figure class="inl') == 2 and 'class="inl graphic"' in view["body_html"]
+
+
+def test_more_photos_only_when_more_found():
+    with _App() as (cfg, a):
+        a.store.save_post(_post())
+        shot = lambda i: {"image": _photo("#446", seed=i), "src": f"https://x/{i}.jpg", "credit": "Marka",  # noqa: E731
+                          "page": "https://brand.com/press", "alt": "", "kind": "body", "graphic": False}
+        appmod.photos.gather = lambda *a_, **k: [shot(0), shot(1)]
+        a.backfill_photos(5)
+        assert len(a.store.load_post("p1")["photos"]) == 2
+        appmod.photos.gather = lambda *a_, **k: [shot(5)]                 # daha az fotoğraf: dokunma
+        a.more_photos()
+        assert [r["src"] for r in a.store.load_post("p1")["photos"]] == ["https://x/0.jpg", "https://x/1.jpg"]
+        a.state["more_photos"] = []
+        appmod.photos.gather = lambda *a_, **k: [shot(i) for i in range(7)]   # daha çok: 4'ü yerel, 3'ü kaynaktan
+        a.more_photos()
+        ph = a.store.load_post("p1")["photos"]
+        assert len(ph) == 7 and sum(1 for r in ph if r.get("file")) == 4 and sum(1 for r in ph if r.get("remote")) == 3
 
 
@@@SM@@@ SHA
5814cb773c220ede9f495768b71170ac36924a02d605a4811e5133ca4536d80c haberbot/app.py
a6d4b00be003eb9d235b133a18000d86f3f07f920175522f6937f94ae6befadc haberbot/site.py
1195497a5fe3f858046cf972e9e31fee0fa6dffc599a77b9dd40ad8e8d128210 tests/test_photos.py
