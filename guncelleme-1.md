SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -18,5 +18,5 @@
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "13"
+ASSET_V = "14"
 FOREIGN_PRICE = re.compile(r"(?=.*fiyat)(?=.*(\$|€|£|¥|dolar|euro|avro|sterlin|yuan|yen\b))", re.I)
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
@@ -308,10 +308,13 @@
         if img.get("source") == "photo" and img.get("photo"):
             pick = next((r for r in recs if r["file"] == img["photo"]), None)
-        if pick is None and p.get("cover_mode") != "type":
-            pick = next((r for r in recs if not r.get("graphic") and r.get("cover_ok", True) and (r.get("w") or 0) >= 900), None)
+        # Yazı basılmayacağı için düz zeminli tanıtım görselleri ve 720 px'lik fotoğraflar da olur; boş renk ağı son çare.
+        # Önce gerçek fotoğraflar (en büyüğü), yoksa ekran görüntüsü / grafik (kırpılmadan, sığdırılarak).
+        if pick is None:
+            big = sorted((r for r in recs if (r.get("w") or 0) >= 600), key=lambda r: (bool(r.get("graphic")), -(r.get("w") or 0)))
+            pick = big[0] if big else None
         if pick:
             return {"kind": "photo", "file": pick["file"], "url": f"{b}/img/{pick['file']}", "w": pick.get("w") or 1600,
                     "h": pick.get("h") or 900, "credit": pick.get("credit") or "", "page": pick.get("page") or "",
-                    "focus": p.get("photo_focus") or "50% 40%"}
+                    "focus": p.get("photo_focus") or "50% 40%", "fit": bool(pick.get("graphic"))}
         if img.get("source") in ("ai", "fallback") and (cfg.images_dir / f"{p['id']}.webp").exists():
             return {"kind": "image", "file": f"{p['id']}.webp", "url": f"{b}/img/{p['id']}.webp", "w": 1280, "h": 960,
--- a/static/style.css
+++ b/static/style.css
@@ -314,4 +314,9 @@
 .ph-art::after { content: ""; position: absolute; inset: 0; opacity: .14; mix-blend-mode: overlay; pointer-events: none;
   background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>"); }
+/* renk ağının ortasında hafif marka işareti: boş değil, bilinçli bir görsel */
+.ph-art::before { content: ""; position: absolute; left: 50%; top: 50%; width: 22%; aspect-ratio: 1; transform: translate(-50%, -50%);
+  opacity: .32; background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M15.6 7.2A4.8 4.8 0 1 0 10.8 12a4.8 4.8 0 1 1-4.8 4.8' fill='none' stroke='%23fff' stroke-width='3.6' stroke-linecap='round'/%3E%3Ccircle cx='19' cy='3.2' r='1.9' fill='%23fff'/%3E%3C/svg%3E") center / contain no-repeat; }
+/* ekran görüntüsü / grafik ana görsel olunca kırpılmaz */
+img.is-fit { object-fit: contain !important; background: #F5F5F7; }
 .slide-media .ph-art, .art-media .ph-art { position: absolute; inset: 0; height: 100%; aspect-ratio: auto; }
 .card .ph-art { transition: transform .8s var(--ease); }
--- a/templates/_macros.html
+++ b/templates/_macros.html
@@ -4,5 +4,5 @@
 <span class="ph-art {{ cls }}" role="img" aria-label="{{ p.img_alt }}" style="{{ p.disp.style }}; view-transition-name: v{{ p.id }}"></span>
 {% else %}
-<img src="{{ p.img }}" alt="{{ p.img_alt }}" width="{{ p.disp.w }}" height="{{ p.disp.h }}"{% if not eager %} loading="lazy"{% endif %}{% if priority %} fetchpriority="high"{% endif %} decoding="async" class="{{ cls }}" style="object-position: {{ p.disp.focus }}; view-transition-name: v{{ p.id }}">
+<img src="{{ p.img }}" alt="{{ p.img_alt }}" width="{{ p.disp.w }}" height="{{ p.disp.h }}"{% if not eager %} loading="lazy"{% endif %}{% if priority %} fetchpriority="high"{% endif %} decoding="async" class="{{ cls }}{{ ' is-fit' if p.disp.fit }}" style="object-position: {{ p.disp.focus }}; view-transition-name: v{{ p.id }}">
 {% endif %}
 {% endmacro %}
--- a/tests/test_photos.py
+++ b/tests/test_photos.py
@@ -192,6 +192,6 @@
         assert a._visual_buttons(p)[0]["text"].endswith("Fotoğraflı kapak")
         view = SiteBuilder(cfg)._post_view(p)
-        assert view["cover_photo"] is None and view["disp"]["kind"] == "art"
-        assert view["body_html"].count('<figure class="inl') == 5
+        assert view["cover_photo"]["file"] == "p1-g0.webp" and view["disp"]["kind"] == "photo"   # sitede yine fotoğraf
+        assert view["body_html"].count('<figure class="inl') == 4
         a._on_button("g", "p1")                                # fotoğraflı kapağa dönüş
         assert a.store.load_post("p1")["image"]["source"] == "photo"
@@ -214,6 +214,11 @@
         from haberbot.site import SiteBuilder
         view = SiteBuilder(cfg)._post_view(p)
-        assert view["disp"]["kind"] == "art" and view["slides"] == []        # küçük fotoğraf ana görsel olmaz
-        assert view["body_html"].count('<figure class="inl') == 2 and 'class="inl graphic"' in view["body_html"]
+        # sitede yazı basılmadığı için 720 px'lik fotoğraf da ana görsel olur (boş renk ağı yerine)
+        assert view["disp"]["kind"] == "photo" and view["disp"]["file"] == "p1-g0.webp" and view["slides"] == []
+        assert view["body_html"].count('<figure class="inl') == 1 and 'class="inl graphic"' in view["body_html"]
+        # yalnızca ekran görüntüsü varsa o gösterilir, kırpılmadan
+        p["photos"] = [r for r in p["photos"] if r.get("graphic")]
+        view = SiteBuilder(cfg)._post_view(p)
+        assert view["disp"]["fit"] and view["disp"]["file"] == p["photos"][0]["file"]
 
 
@@@SM@@@ SHA
5b46ddf5ee3330c3df01d6a1b8c712d84169cb64871663615bb3c89cc27059c1 haberbot/site.py
17fce42d014826817d2ca4d271f9911d8c86f7ca428631c0ff43ac52a92f8224 static/style.css
65b3a2be27034736d9dad3967c31268325f663532013856d1401c35dc3c365e6 templates/_macros.html
3bdcc25291608984cdc9d1f23133d7b74bc6dc7f9e2ea5ae98ec2dd6e0bee8ed tests/test_photos.py
