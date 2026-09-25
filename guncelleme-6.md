SMARITY-BUNDLE v1 part 6/6
 H2_RE = re.compile(r"<h[1-3]>(.*?)</h[1-3]>", re.S)
 
@@ -185,7 +185,10 @@
             "credits": list(dict.fromkeys(s["name"] for s in p.get("sources", []))),
             "minutes": reading_minutes(p.get("body", "")),
             "words": len(plain(p.get("body", "")).split()),
-            "body_html": render_body(p.get("body", "")),
+            "body_html": (body_html := render_body(p.get("body", ""))),
+            "toc": [{"id": m.group(1), "text": re.sub("<[^>]+>", "", m.group(2))}
+                    for m in re.finditer(r'<h2 id="([^"]+)">(.*?)</h2>', body_html)],
+            "key_points": [x for x in (p.get("carousel_points") or []) if x][:4],
             "updated_str": tr_date(p.get("updated_at"), cfg.tz) if p.get("updated_at") else "",
         }
 
@@ -252,6 +255,8 @@
             "logo_svg": f"{b}/static/logo.svg" if (ROOT / "static" / "logo.svg").exists() else "",
             "asset_v": ASSET_V,
             "home_h1": seo.get("home_h1") or "Teknoloji haberleri",
+            "today_str": f"{tr_date(now_utc(), cfg.tz, with_time=False)}, "
+                         f"{['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar'][now_l.weekday()]}",
             "home_title": seo.get("home_title") or f"{cfg.site.get('name')}: {cfg.site.get('tagline')}",
             "home_description": seo.get("home_description") or cfg.site.get("description", ""),
             "verify": {k: seo.get(k) for k in ("google_site_verification", "bing_site_verification", "yandex_verification")},
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -120,8 +120,10 @@
         """Şu an yazılabilecek taslak sayısı. Günlük sınır güne yayılır: sabah hepsi birden tükenmez,
         akşam da haber gelmeye devam eder."""
         ed = lambda k, d: self.cfg.get("editorial", k, d)  # noqa: E731
-        cap = int(ed("max_drafts_per_day", 40))
+        cap = int(ed("max_drafts_per_day", 0) or 0)
         used = self.store.count(self.today(), "drafts")
+        if cap <= 0:  # günlük sınır yok: seçim yalnızca önem eşiğine göre yapılır
+            return 10 ** 6
         a, b = (ed("active_hours", [7, 24]) or [0, 24])[:2]
         now_l = local(now_utc(), self.cfg.tz)
         h = now_l.hour + now_l.minute / 60
--- a/config.yaml
+++ b/config.yaml
@@ -38,7 +38,7 @@
 editorial:
   min_importance: 7              # 1-10 arası. Bunun altındaki haberler hiç önüne gelmez (seçici: 7)
   max_drafts_per_run: 2          # Bir taramada en fazla kaç yeni haber taslağı yazılsın (haberler tek tek, düzenli gelsin)
-  max_drafts_per_day: 20         # Günlük üst sınır; gün içine eşit yayılır
+  max_drafts_per_day: 0          # Günlük üst sınır (0 = sınır yok; haberler yalnızca önem eşiğine göre seçilir)
   active_hours: [7, 24]          # Taslakların yayıldığı saatler (gece en fazla birkaç haber gelir, kalanlar sabaha kalır)
   max_item_age_hours: 36         # Bundan eski haberler atlanır
   pending_expire_hours: 36       # Onaylanmayan taslak bu süre sonunda düşer
@@@SM@@@ SHA
c4630f7f5da42fb897c01185ee3188080d95cab5f2c6b1c06dfcf07142d7d5e7 templates/article.html
3525ba6a745c0811ae1100f549a22e713aa7f983c418d8347c047176e3aaec2c templates/index.html
425f492a29a96bde2f99a497a3f2cbe349afe1bdd6376e107ada4d9b05699767 static/style.css
a8610b32a407f0a014e76fae2039bfec0fcc894e03d2eafbd82fc4ba1b37979f haberbot/site.py
a3bbde2a670ca231ad9464015f33f0c1d02486e83e3fb0da28c603fa3c5f6b49 haberbot/app.py
7aef68b8df1243ba2d3ff452fa16362fc07b3a6c3ffa3384a39ea04723fe23fe config.yaml
