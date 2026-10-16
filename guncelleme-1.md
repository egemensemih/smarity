SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -22,5 +22,5 @@
                       seo_system, seo_user, triage_system, triage_user, write_system, write_user)
 from .sources import fetch_all
-from .store import Store
+from .store import Store, write_json
 from .textfix import Fixer, entity_keys, is_car_story, looks_english, title_words
 from .telegram import MockTelegram, Telegram, TelegramError
@@ -295,4 +295,6 @@
                         merged += 1
                         continue
+                    if did in posted:
+                        self._note_coverage(did, its)   # aynı haberi veren başka siteler: büyüklük + fotoğraf adayı
                     # yayındaki bir haberin devamı: önemliyse yönetmen "güncelle" ya da "geç" der
                     if did in posted and int(s.get("importance", 0)) >= min_imp and s.get("on_topic", True):
@@ -555,4 +557,25 @@
         return added
 
+    def _note_coverage(self, pid: str, its: list[dict]) -> bool:
+        """Yayındaki bir haberi sonradan veren siteleri kaydet (metne kaynak olarak eklenmez): manşet sıralamasında
+        haberin büyüklüğünü, fotoğrafsız haberde de fotoğraf adayını verir. Site yeniden üretimini tetiklemez."""
+        post = self.store.load_post(pid)
+        if not post:
+            return False
+        cov = post.setdefault("coverage", [])
+        known = {s.get("url") for s in (post.get("sources") or []) + cov}
+        added = 0
+        for it in its:
+            if not it.get("url") or it["url"] in known:
+                continue
+            known.add(it["url"])
+            cov.append({"name": it.get("credit"), "url": it["url"], "title": clip(it.get("title") or "", 140),
+                        "kind": it.get("kind"), "image": it.get("image"), "at": iso(now_utc())})
+            added += 1
+        if added:
+            del cov[:-20]
+            write_json(self.store.post_path(pid), post)
+        return bool(added)
+
     @staticmethod
     def _source_entry(it: dict) -> dict:
@@ -888,6 +911,21 @@
         if d.get("entities") and not post.get("entities"):
             post["entities"] = d["entities"]
+        if (not post.get("photos_removed") and (post.get("image") or {}).get("source") != "ai"
+                and not self._has_display_photo(post, self.cfg.images_dir)):
+            # fotoğrafsız habere yeni kaynaklarla fotoğraf (ör. etkinlik duyurusu fotoğrafsızdı, tanıtım fotoğraflı geldi)
+            post["photos_filled"] = iso(now_utc())
+            try:
+                attached = self._attach_photos(post, draft=False)       # kapak ve paylaşım görseli de üretilir
+                if attached:
+                    log.info("Güncellenen habere fotoğraf bulundu: %s (%d)", post["id"], len(post["photos"]))
+            except Exception as e:  # noqa: BLE001
+                attached = False
+                log.warning("Güncellenen habere fotoğraf eklenemedi (%s): %s", post["id"], e)
+        else:
+            attached = False
         try:
-            if post.get("photos") and (post.get("image") or {}).get("source") == "photo":
+            if attached:
+                pass
+            elif post.get("photos") and (post.get("image") or {}).get("source") == "photo":
                 self._build_cover(post, draft=False)
             elif (post.get("image") or {}).get("source") in ("cover", "fallback", None):
@@ -2300,4 +2338,18 @@
 
     @staticmethod
+    def _photo_sources(d: dict, draft: bool) -> list[dict]:
+        """Fotoğraf aranacak sayfalar. Yayındaki haberde (yeniden deneme) resmi kaynak, sonra en yeni eklenen kaynaklar
+        ve haberi sonradan veren siteler önce gelir: ilk kaynakta uygun fotoğraf yoksa aynı sayfalara tekrar bakılmaz."""
+        src = list(d.get("sources") or [])
+        if draft:
+            return src
+        seen, out = set(), []
+        for s in ([s for s in src if s.get("kind") == "official"] + src[::-1] + (d.get("coverage") or [])[::-1]):
+            if s.get("url") and s["url"] not in seen:
+                seen.add(s["url"])
+                out.append(s)
+        return out
+
+    @staticmethod
     def _has_display_photo(p: dict, folder) -> bool:
         return any(r.get("file") and (r.get("w") or 0) >= 600 and (folder / r["file"]).exists() for r in p.get("photos") or [])
@@ -2334,7 +2386,13 @@
             return
         folder = self.cfg.images_dir
+
+        def due(p: dict) -> bool:
+            # son 2 günün haberi (ya da yeni güncellenen) 2 saatte bir, eskiler 3 günde bir yeniden denenir
+            fresh = hours_since(p.get("refreshed_at") or p.get("published_at")) <= 48
+            return hours_since(p.get("photos_filled")) > (2 if fresh else 72)
         todo = [p for p in self.store.posts()
                 if not p.get("photos_removed") and (p.get("image") or {}).get("source") != "ai"
-                and not self._has_display_photo(p, folder) and hours_since(p.get("photos_filled")) > 72][:per_run]
+                and not self._has_display_photo(p, folder) and due(p)]
+        todo = sorted(todo, key=lambda p: -int(p.get("importance") or 0))[:per_run]   # önce büyük haberler
         for p in todo:
             p["photos_filled"] = iso(now_utc())
@@ -2352,6 +2410,7 @@
         try:
             if got is None:
-                got = photos.gather(d.get("sources") or [], limit=int(cfg.get("images", "photo_limit", 16) or 16),
+                got = photos.gather(self._photo_sources(d, draft), limit=int(cfg.get("images", "photo_limit", 16) or 16),
                                     per_source=int(cfg.get("images", "photos_per_source", 12) or 12),
+                                    pages=3 if draft else 4,
                                     skip_cover=self._no_cover_sources(), entities=self._photo_names(d))
         except Exception as e:  # noqa: BLE001
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -98,4 +98,9 @@
     if (p.get("image") or {}).get("source") == "photo":
         base += 1.0
+    # haberin büyüklüğü: kaç ayrı yayın kuruluşu aynı haberi verdi (kaynaklar + aynı haberi sonradan veren siteler)
+    outlets = len({s.get("name") for s in (p.get("sources") or []) + (p.get("coverage") or []) if s.get("name")})
+    base += min(2.0, 0.5 * max(0, outlets - 2))
+    if int(p.get("importance") or 0) >= 9:
+        base += 0.5
     score = base / (age + 4) ** 0.7
     if home == "pin" and hours_since(p.get("home_at") or p.get("published_at")) < 36:
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -379,4 +379,28 @@
 
 
+def test_big_stories_rank_higher_and_get_photos_from_later_sources():
+    src = lambda n: {"name": n, "url": f"https://{n.lower()}.com/x", "kind": "media", "image": f"https://{n}.com/a.jpg"}  # noqa: E731
+    one = _post(1, 3, appeal=9)
+    many = {**_post(2, 3, appeal=9), "sources": [src("Electrek")], "coverage": [src(n) for n in ("Verge", "NYT", "Engadget", "InsideEVs")]}
+    assert hot(many) > hot(one) * 1.15                                 # 5 ayrı site haberi verdi: büyük haber
+    with _App() as (cfg, a):
+        post = {**_post(3, 30), "sources": [src("Electrek")], "importance": 9, "telegram": {"message_id": 9}}
+        a.store.save_post(post)
+        a.store.site_dirty = False
+        it = lambda n: {"credit": n, "url": f"https://{n.lower()}.com/y", "title": "Roadster", "kind": "media",  # noqa: E731
+                        "image": f"https://{n}.com/b.jpg", "source": n}
+        assert a._note_coverage("p03", [it("Verge"), it("Verge"), it("NYT")])
+        assert not a._note_coverage("p03", [it("NYT")])                 # aynı adres iki kez eklenmez
+        p = a.store.load_post("p03")
+        assert [c["name"] for c in p["coverage"]] == ["Verge", "NYT"] and not a.store.site_dirty
+        assert [x["name"] for x in a._photo_sources(p, draft=False)] == ["Electrek", "NYT", "Verge"]
+        # güncelleme gelince fotoğrafsız habere yeni kaynaklarla fotoğraf aranır
+        tried = []
+        a._attach_photos = lambda d, draft, got=None: tried.append(d["id"]) or False
+        upd = {"id": "u1", "update_of": "p03", "title": "Tesla Roadster tanıtıldı", "summary": "s", "body": "b",
+               "sources": [src("Engadget")], "source_keys": ["Engadget"], "importance": 9}
+        assert a.apply_update(upd) and tried == ["p03"]
+        assert a.store.load_post("p03")["photos_filled"]
+
 if __name__ == "__main__":
     for name, fn in list(globals().items()):
@@@SM@@@ SHA
ee06744c255a733299cd72906107751ca4a26f94d0d2f863566869b158f959d7 haberbot/app.py
2c9658d4f7d1fabf323e1d43b81ae946c3dc547c9a7ad00977a6aee9172da3a1 haberbot/site.py
5bcd30c8219d6172baa02442df2e226ba51513fa2fc0e5e28d6c660c5ce6bb37 tests/test_home.py
