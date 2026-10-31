SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -581,4 +581,16 @@
             "i": p["disp"].get("url") if p["disp"].get("kind") in ("photo", "image") else "",
         } for p in posts], ensure_ascii=False, separators=(",", ":")))
+        # eski adresler için kalıcı (301) yönlendirme listesi: Cloudflare → Bulk Redirects listesine yüklenir
+        # (sayfa içi yönlendirmeler de durur; Cloudflare önde olduğunda Google gerçek 301 görür)
+        host = cfg.site_url.split("://", 1)[-1].rstrip("/")
+        rows, seen = [], set()
+        for p in posts:
+            for old in [f"haber/{p['slug']}", *(p.get("old_paths") or [])]:
+                old = old.strip("/")
+                src = f"{host}/{old}/"
+                if old and old != p["path"] and src not in seen:
+                    seen.add(src)
+                    rows.append(f"{src},{p['abs_url']},301,TRUE,FALSE,FALSE,FALSE")
+        self._write("api/redirects.csv", "\n".join(sorted(rows)) + "\n")
 
         # besleme, site haritaları, robots, IndexNow anahtarı, json
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -416,4 +416,7 @@
         sm = (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")
         assert "/gizlilik/" in sm and "/iletisim/" in sm
+        red = (cfg.out_dir / "api" / "redirects.csv").read_text(encoding="utf-8").splitlines()
+        p01 = a.store.load_post("p01")
+        assert f"smarity.com.tr/haber/{p01['slug']}/,https://smarity.com.tr/{cfg.post_path(p01)}/,301,TRUE,FALSE,FALSE,FALSE" in red
         cfg.raw["analytics"] = {"cloudflare_token": "abc123"}
         cfg.raw["legal"] = {"owner": "Örnek Medya", "address": "İstanbul"}
@@@SM@@@ SHA
0740f1ae4d278303b55c600fe5d042a0bda17c4b229ed2947785c470e6eea062 haberbot/site.py
f498d21f20251072570808e6be72884ee3b7cf8f75293c5124f63b33026cc138 tests/test_home.py
