SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -414,4 +414,7 @@
                         "url": f"{b}/etiket/{s}/", "lastmod": ps[0]["mod_iso"]}
                        for s, ps in tag_posts.items()), key=lambda t: (-t["count"], t["label"].lower()))
+        for p in posts:   # tek haberlik konu sayfası noindex: haberden ona bağlantı verilmez (Google boşuna taramasın)
+            for t in p["tag_list"]:
+                t["linked"] = len(tag_posts.get(t["slug"], [])) >= 2
 
         now_l = local(now_utc(), cfg.tz)
--- a/templates/article.html
+++ b/templates/article.html
@@ -119,8 +119,10 @@
   {% endif %}
 
-  {% if post.tag_list %}
+  {# yalnızca birden çok haberi olan konular bağlanır: tek haberlik konu sayfaları dizine eklenmez, Google'a gösterilmez #}
+  {% set linked_tags = post.tag_list|selectattr('linked')|list %}
+  {% if linked_tags %}
   <nav class="art-tags" aria-label="Konular">
     <span class="muted">Konular</span>
-    {% for t in post.tag_list %}<a href="{{ t.url }}">{{ t.label }}</a>{% endfor %}
+    {% for t in linked_tags %}<a href="{{ t.url }}">{{ t.label }}</a>{% endfor %}
   </nav>
   {% endif %}
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -194,4 +194,19 @@
 
 
+
+def test_single_post_tags_are_not_linked():
+    # tek haberlik konu sayfası noindex; haberden ona bağlantı verilmez (Search Console'da "noindex" uyarısı birikmesin)
+    with _App() as (cfg, a):
+        a.store.save_post(_post(1, 2, tags=["Apple", "Grok Bot"]))
+        a.store.save_post(_post(2, 3, tags=["Apple"]))
+        a.migrate_urls()
+        SiteBuilder(cfg).build()
+        art = (cfg.out_dir / a.store.load_post("p01")["path"] / "index.html").read_text(encoding="utf-8")
+        assert "/etiket/apple/" in art and "/etiket/grok-bot/" not in art
+        lone = (cfg.out_dir / "etiket" / "grok-bot" / "index.html").read_text(encoding="utf-8")
+        assert 'content="noindex' in lone                                  # eski bağlantılar için sayfa durur, dizine eklenmez
+        assert "/etiket/grok-bot/" not in (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")
+
+
 if __name__ == "__main__":
     for name, fn in list(globals().items()):
@@@SM@@@ SHA
2da93697260c1f40d06d3af2df49006fc45b283832f84bf99c6389e0244ded52 haberbot/site.py
14911e05aabefc481783e3f06d0e2735805c80915542874a7340820a3020b676 templates/article.html
cb7d7d1a131d37f173ab4f8bebc69e2ef6e8c326c01ddecce9b81ecc792c8372 tests/test_home.py
