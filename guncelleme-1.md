SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -2039,9 +2039,35 @@
     def _photo_names(d: dict) -> list[str]:
         """Kaynaklarda fotoğraf yoksa Wikipedia'da aranacak adlar: haberin şirketi / ürünü / kişisi."""
-        return list(dict.fromkeys((d.get("entities") or []) + (d.get("tags") or [])[:3]))
+        ents = [e for e in d.get("entities") or [] if e]      # yalnızca haberin asıl konusu (etiketteki yan şirketler değil)
+        return ents or list((d.get("tags") or [])[:3])
 
     @staticmethod
     def _has_display_photo(p: dict, folder) -> bool:
         return any(r.get("file") and (r.get("w") or 0) >= 600 and (folder / r["file"]).exists() for r in p.get("photos") or [])
+
+    def recheck_wiki_photos(self) -> None:
+        """Tek seferlik: Wikipedia görseli haberin asıl konusuyla eşleşmiyorsa (ör. Manus haberine Tencent logosu) kaldır."""
+        if self.state.get("wiki_fix_v") == 1:
+            return
+        self.state["wiki_fix_v"] = 1
+        for p in self.store.posts():
+            ph = p.get("photos") or []
+            ents = [e.lower() for e in p.get("entities") or [] if e]
+            if not ph or not ents or any(r.get("credit") != "Wikipedia" for r in ph):
+                continue
+            alt = (ph[0].get("alt") or "").lower()
+            if any(e in alt or alt in e for e in ents):
+                continue
+            for f in self.store.gallery_files(p["id"], draft=False):
+                f.unlink(missing_ok=True)
+            p.pop("photos", None)
+            p["image"] = {"source": "cover"}
+            p["photos_filled"] = iso(now_utc())
+            try:
+                self._make_og(p)                       # paylaşım görselinde de eski fotoğraf kalmasın
+            except Exception as e:  # noqa: BLE001
+                log.warning("Paylaşım görseli yenilenemedi (%s): %s", p["id"], e)
+            self.store.save_post(p)
+            log.info("Konuyla eşleşmeyen Wikipedia görseli kaldırıldı: %s (%s)", p["id"], ph[0].get("alt"))
 
     def fill_missing_photos(self, per_run: int = 8) -> None:
@@ -2271,4 +2297,5 @@
             try:
                 self.more_photos()
+                self.recheck_wiki_photos()
                 self.fill_missing_photos()
                 self.backfill_photos(int(self.cfg.get("images", "photo_backfill_per_run", 5) or 0))
--- a/tests/test_photos.py
+++ b/tests/test_photos.py
@@ -264,4 +264,10 @@
             a.fill_missing_photos()                                       # artık fotoğraflı: tekrar denenmez
             assert a.store.load_post("p1")["photos"] == p["photos"]
+            # konuyla eşleşmeyen Wikipedia görseli (haber X değil başka bir şirketle ilgili) kaldırılır
+            a.store.save_post({**a.store.load_post("p1"), "entities": ["Manus"]})
+            a.recheck_wiki_photos()
+            q = a.store.load_post("p1")
+            assert "photos" not in q and not q.get("photos_removed") and q["image"]["source"] == "cover"
+            assert a._photo_names({"entities": ["Manus"], "tags": ["Manus", "Tencent"]}) == ["Manus"]
     finally:
         photos.gather, photos.wiki_photo = real_gather, real_wiki
@@@SM@@@ SHA
04c4ab92c943c819d1f74045fc2fc379e92d1ed0ebc8b7e2a70400a948afac87 haberbot/app.py
eb9ba2a1eca10c27a1cb19e6dc669d86770b296f597be76759b53493e0c58492 tests/test_photos.py
