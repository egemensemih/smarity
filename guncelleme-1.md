SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -31,5 +31,5 @@
 # verilen koddaki "token" değerini buraya yaz.
 analytics:
-  cloudflare_token: ""
+  cloudflare_token: "33078a5eed17475aac6c1ceb8c7091af"
 
 home:
--- a/templates/base.html
+++ b/templates/base.html
@@ -125,5 +125,5 @@
 {% endif %}
 <script src="{{ site.base }}/static/site.js?v={{ site.asset_v }}" defer></script>
-{% if site.cf_analytics %}<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{"token": "{{ site.cf_analytics }}"}'></script>{% endif %}
+{% if site.cf_analytics %}<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{"token": "{{ site.cf_analytics }}"}'></script>{% endif %}
 </body>
 </html>
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -405,4 +405,5 @@
 def test_legal_pages_and_analytics():
     with _App() as (cfg, a):
+        cfg.raw["analytics"], cfg.raw["legal"] = {"cloudflare_token": ""}, {}
         a.store.save_post(_post(1, 2))
         SiteBuilder(cfg).build()
@@@SM@@@ SHA
44d9d55362473da4cebbeba2f5a0f6a0bc2fe07e34b3ea852c355444080c0478 config.yaml
c13f64e4a40a539dfae5e0f9d2f527a671829b861910a809be7a0fcdbe5ae555 templates/base.html
73a460a1f3bfd22ac5c04599c3ca317746dfabd56ce48a84c3e7906b6bb19cbb tests/test_home.py
