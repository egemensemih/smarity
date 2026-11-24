SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -2085,5 +2085,8 @@
         posts = self.store.posts()[:1000]
         tried = self.state.setdefault("guide_tried", {})
+        wait = self.state.setdefault("guide_wait", {})
         for spec in specs:
+            if hours_since(wait.get(spec["slug"])) < 3:
+                continue        # az önce hata verdi (ör. yapay zeka kotası): bu arada sıradaki rehberler yazılsın
             rel = guidesmod.related_posts(spec, posts, float(spec.get("lookback_days") or lookback),
                                           int(spec.get("max_posts") or limit))
@@ -2096,6 +2099,16 @@
             if old and hours_since(old.get("updated_at")) < gap:
                 continue
-            return self._write_guide(spec, rel, old, sig)
+            try:
+                return self._write_guide(spec, rel, old, sig)
+            except Exception as e:  # noqa: BLE001
+                log.exception("Rehber hatası (%s): %s", spec["slug"], e)
+                self._guide_failed(spec["slug"], f"{type(e).__name__}: {e}")
+                return False
         return False
+
+    def _guide_failed(self, slug: str, err: str) -> None:
+        """Hata veren rehber 3 saat bekler (diğerlerini tıkamasın); son hata durum dosyasında görünür."""
+        self.state.setdefault("guide_wait", {})[slug] = iso(now_utc())
+        self.state["guide_err"] = {"slug": slug, "at": iso(now_utc()), "err": clip(err, 300)}
 
     def _write_guide(self, spec: dict, rel: list[dict], old: dict | None, sig: list[str]) -> bool:
@@ -2109,4 +2122,5 @@
             except LLMError as e:
                 log.warning("Rehber yazılamadı (%s): %s", spec["slug"], str(e)[:160])
+                self._guide_failed(spec["slug"], str(e))
                 return False
             body = (out.get("body") or "").strip()
@@ -2142,4 +2156,5 @@
         guidesmod.save_guide(cfg, g)
         self.state.get("guide_tried", {}).pop(spec["slug"], None)
+        self.state.get("guide_wait", {}).pop(spec["slug"], None)
         self.store.site_dirty = True
         url = f"{cfg.site_url}/rehber/{spec['slug']}/"
--- a/tests/test_guides.py
+++ b/tests/test_guides.py
@@ -85,2 +85,26 @@
         art = max((f.read_text(encoding="utf-8") for f in cfg.out_dir.rglob("haber-2/index.html")), key=len)
         assert 'class="guide-box"' in art and "/rehber/imei-kayit-ucreti/" in art   # eski haberden güncel rehbere
+
+
+def test_failing_guide_does_not_block_others():
+    from haberbot.llm import LLMError
+    with _App() as (cfg, a):
+        other = {"slug": "togg-fiyat-listesi", "title": "Togg fiyat listesi", "match": ["togg"]}
+        cfg.raw["guides"] = {"enabled": True, "min_posts": 2, "list": [SPEC, other]}
+        _imei_posts(a)
+        a.store.save_post(_post(5, 3, title="Togg fiyatı 1.909.048 TL", tags=["Togg"], body="Togg 1.909.048 TL."))
+        a.store.save_post(_post(6, 4, title="Togg kampanyası", tags=["Togg"], body="Togg kampanya 1.909.048 TL."))
+        seen = []
+
+        class LLM:
+            def json(self, model, system, user, schema, **_k):
+                seen.append("IMEI" in user)
+                if "IMEI" in user:
+                    raise LLMError("HTTP 429 kota")
+                return {"seo_title": "Togg", "meta_description": "Togg.", "summary": "Togg 1.909.048 TL.",
+                        "body": "Togg 1.909.048 TL. " + " ".join(["Togg fiyatı açıklandı."] * 60), "faq": [],
+                        "changes": "İlk sürüm.", "used": []}
+        a.llm = LLM()
+        assert a.guides_tick() is False and a.state["guide_err"]["slug"] == "imei-kayit-ucreti"
+        assert a.guides_tick() is True and seen == [True, False]           # IMEI beklerken Togg yazıldı
+        assert G.guide_path(cfg, "togg-fiyat-listesi").exists()
@@@SM@@@ SHA
34c551eecc28a1a469891da1929a852964c89457a19f39812168f7a349c784bf haberbot/app.py
fe05059730b84dedab83f8a37a07c84b335ddfa49edd223f2b71bc8071874232 tests/test_guides.py
