SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -123,4 +123,6 @@
 #  Bir kaynağı kapatmak için satırlarının başına # koy.
 #  photo_cover: false → kaynağın paylaşım görseline yazı basılıysa o görsel alınmaz, sadece haberdeki fotoğraflar.
+#  browser_ua: true → kaynak bot kimliğini reddediyorsa (403) normal tarayıcı kimliğiyle okunur.
+#  Üst üste 6 kez okunamayan kaynak otomatik dinlenir, 6 saatte bir yeniden denenir (/kaynaklar ile görebilirsin).
 # ─────────────────────────────────────────────────────────────
 sources:
@@ -304,4 +306,5 @@
     url: https://gizmodo.com/rss
     kind: media
+    browser_ua: true      # bot kimliğini reddediyor
   - name: Tom's Hardware
     url: https://www.tomshardware.com/feeds/all
@@ -313,4 +316,5 @@
     url: https://videocardz.com/feed
     kind: media
+    browser_ua: true      # bot kimliğini reddediyor
   - name: The Next Web
     url: https://thenextweb.com/feed
@@ -398,7 +402,4 @@
     url: https://www.soundguys.com/feed/
     kind: media
-  - name: Wareable
-    url: https://www.wareable.com/rss
-    kind: media
   - name: DC Rainmaker
     url: https://www.dcrainmaker.com/feed
@@ -421,4 +422,5 @@
     url: https://www.autoblog.com/rss.xml
     kind: media
+    browser_ua: true      # bot kimliğini reddediyor
   - name: Teslarati
     url: https://www.teslarati.com/feed/
@@ -460,7 +462,4 @@
 
   # ── Uzay ──
-  - name: Space.com
-    url: https://www.space.com/feeds/all
-    kind: media
   - name: SpaceNews
     url: https://spacenews.com/feed/
@@ -471,7 +470,9 @@
     url: https://teknoseyir.com/feed
     kind: media
+    browser_ua: true      # bot kimliğini reddediyor
   - name: Technopat
     url: https://www.technopat.net/feed/
     kind: media
+    browser_ua: true      # bot kimliğini reddediyor
   - name: Donanım Arşivi
     url: https://donanimarsivi.com/feed/
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -1410,16 +1410,20 @@
 
     def sources_text(self) -> str:
-        lines = ["🧭 <b>Kaynak güveni</b> (✅ = otomatik yayına uygun)"]
         names = [s["name"] for s in self.cfg.sources]
+        health = self.state.get("source_health", {})
+        broken = [n for n in names if health.get(n, {}).get("fails", 0) >= 3]
+        lines = [f"📡 <b>{len(names)} kaynak</b> · {len(names) - len(broken)} okunuyor"
+                 + (f" · ⚠️ okunamayan: {esc(', '.join(broken))}" if broken else ""),
+                 "", "🧭 <b>Kaynak güveni</b> (✅ = otomatik yayına uygun; yalnızca karar verdiğin kaynaklar)"]
+        rows = []
         for name in names:
             ok, n, rate = policy.source_trust(self.cfg, self.stats, name)
-            h = self.state.get("source_health", {}).get(name, {})
-            health = " ⚠️ okunamıyor" if h.get("fails", 0) >= 3 else ""
-            detail = f"{n} karar, %{rate * 100:.0f} onay" if n else "henüz karar yok"
-            lines.append(f"{'✅' if ok else '▫️'} {esc(name)}: {detail}{health}")
+            if n:
+                rows.append((not ok, -n, f"{'✅' if ok else '▫️'} {esc(name)}: {n} karar, %{rate * 100:.0f} onay"))
+        lines += [r[2] for r in sorted(rows)[:40]] or ["Henüz karar yok."]
         need = self.cfg.get("autonomy", "source_min_decisions", 10)
         pct = self.cfg.get("autonomy", "source_min_approval", 0.9) * 100
         lines.append(f"\nGüven için: en az {need} karar ve %{pct:.0f} onay.")
-        return "\n".join(lines)
+        return "\n".join(lines)[:4000]
 
     # ── bakım ───────────────────────────────────────────────
--- a/haberbot/sources.py
+++ b/haberbot/sources.py
@@ -156,6 +156,15 @@
 
 
-def _fetch(url: str, timeout: int = 15) -> bytes:
-    r = requests.get(url, headers={"User-Agent": UA, "Accept": "*/*"}, timeout=timeout)
+# Bot tanıtan tarayıcı kimliğini reddeden (403) kaynaklar için ayarlarda browser_ua: true
+BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
+              "Chrome/128.0 Safari/537.36")
+
+
+def _fetch(url: str, timeout: int = 15, browser: bool = False) -> bytes:
+    headers = {"User-Agent": BROWSER_UA if browser else UA,
+               "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.9, */*;q=0.8"}
+    if browser:
+        headers["Accept-Language"] = "tr-TR,tr;q=0.9,en;q=0.8"
+    r = requests.get(url, headers=headers, timeout=timeout)
     r.raise_for_status()
     return r.content[:5_000_000]
@@ -171,5 +180,5 @@
         raw = path.read_bytes()
     else:
-        raw = _fetch(src["url"])
+        raw = _fetch(src["url"], browser=bool(src.get("browser_ua")))
     if stype == "html":
         return parse_html_listing(raw, src["url"], src.get("link_pattern", "."))
@@@SM@@@ SHA
b0a2fee9432715e90e72931696c61eac58696c01f7ccc1d2a1c3947aa0604083 config.yaml
73cf34ad244d137803beaaf2a5f1ca80e9412bb356141242f8bb67d05e0ede58 haberbot/app.py
4aa59aaacb4b456437236f2784be861d771564af3416e520757cd1fefe7c5dfe haberbot/sources.py
