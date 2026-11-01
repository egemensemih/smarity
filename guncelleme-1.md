SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/templates/_macros.html
+++ b/templates/_macros.html
@@ -54,5 +54,7 @@
       <h2>{{ p.title_disp }}</h2>
       <span class="slide-dek">{{ p.summary }}</span>
-      <span class="slide-meta"><time datetime="{{ p.iso }}" data-rel>{{ p.date_str }}</time> · {{ p.credits|join(', ') }}</span>
+      {# güncellenen haberde son güncelleme zamanı görünür ("Güncellendi" etiketiyle birlikte): manşette eski tarih durmaz #}
+      {% set u = p.update_list[0] if p.update_list else {} %}
+      <span class="slide-meta"><time datetime="{{ u.iso or p.iso }}" data-rel>{{ u.date or p.date_str }}</time> · {{ p.credits|join(', ') }}</span>
       <span class="more">Haberi oku</span>
     </span>
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -468,4 +468,18 @@
 
 
+def test_updated_lead_shows_update_time():
+    with _App() as (cfg, a):
+        upd = iso(now_utc() - timedelta(hours=1))
+        a.store.save_post(_post(1, 70, appeal=9, image={"source": "photo"}, refreshed_at=upd,
+                                updates=[{"at": upd, "note": "Yeni gelişme eklendi"}]))
+        for i in range(2, 6):
+            a.store.save_post(_post(i, i))
+        SiteBuilder(cfg).build()
+        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
+        i = home.index('data-id="p01"')
+        chunk = home[i:i + 2500]
+        assert "Güncellendi" in chunk and f'datetime="{upd}"' in chunk
+
+
 def test_feed_links_must_be_http():
     import haberbot.sources as srcmod
@@@SM@@@ SHA
d8a0b951c62c69f1a16e58478420f37953ef0f98098455135e0289e9b305d588 templates/_macros.html
9482beb3a321da5c1c4bec083083c4da0fab38ef236c767030a3d06d7ec55df6 tests/test_home.py
