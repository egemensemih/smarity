SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -21,5 +21,5 @@ seo:
   home_description: "Dünyadan ve Türkiye'den yapay zeka, yeni teknoloji ürünleri, inovasyon, girişim hikâyeleri ve oyun dünyası haberleri. Kaynağıyla, Türkçe, her gün güncel."
   # Arama motoru doğrulama kodları (Search Console / Bing / Yandex'in verdiği "content" değeri)
-  google_site_verification: ""
+  google_site_verification: "ChTcddRF_YOMXdFjpyGX4IbkbxC2lXSjJkQSMRd_Dqs"
   bing_site_verification: ""
   yandex_verification: ""
--- a/templates/index.html
+++ b/templates/index.html
@@ -4,4 +4,10 @@
 {% block head %}
 {% if featured %}<link rel="preload" as="image" href="{{ featured[0].img }}" fetchpriority="high">{% endif %}
+{% set org = {"@type": "NewsMediaOrganization", "@id": site.url ~ "/#org", "name": site.name, "url": site.url ~ "/",
+     "logo": {"@type": "ImageObject", "url": site.logo, "width": 512, "height": 512},
+     "publishingPrinciples": site.url ~ "/hakkinda/", "ethicsPolicy": site.url ~ "/hakkinda/",
+     "correctionsPolicy": site.url ~ "/hakkinda/", "areaServed": "TR", "knowsLanguage": "tr"} %}
+{% if site.instagram %}{% set _ = org.update({"sameAs": ["https://www.instagram.com/" ~ site.instagram ~ "/"]}) %}{% endif %}
+{% if site.contact_email %}{% set _ = org.update({"email": site.contact_email}) %}{% endif %}
 <script type="application/ld+json">{{ {
   "@context": "https://schema.org",
@@ -10,7 +16,5 @@
      "url": site.url ~ "/", "inLanguage": "tr-TR", "description": site.home_description,
      "publisher": {"@id": site.url ~ "/#org"}},
-    {"@type": "NewsMediaOrganization", "@id": site.url ~ "/#org", "name": site.name, "url": site.url ~ "/",
-     "logo": {"@type": "ImageObject", "url": site.logo, "width": 512, "height": 512},
-     "publishingPrinciples": site.url ~ "/hakkinda/"}
+    org
   ]
 }|tojson }}</script>
@@@SM@@@ SHA
02eaef42e4131e1af8e510a518cb5785411c6db7fe52f26ed586ccbf7eef6728 config.yaml
384f8a2948c95a727e5b884b4740326ec1edb877fb0e939cbf6e83d91e15340d templates/index.html
