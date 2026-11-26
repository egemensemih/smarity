SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -115,5 +115,6 @@
   # Wikipedia görselleri; haber sitelerinin kendi fotoğrafları kullanılmaz, onların yerine habere özel kapak gelir.
   # any: kaynak haberin görselleri de kullanılır (eski davranış).
-  photo_policy: press
+  photo_policy: any                # Kasım 2026: kullanıcı kararıyla kaynak fotoğraflarına geri dönüldü
+  photo_redo_since: "2026-11-24"  # bu tarihten beri yayımlanan fotoğrafsız / Wikipedia görselli haberler bir kez yeniden denenir
   press_hosts: [apple.com, samsung.com, blog.google, googleblog.com, google.com, openai.com, anthropic.com,
                 microsoft.com, nvidia.com, sony.com, playstation.com, xbox.com, nintendo.com, tesla.com, togg.com.tr,
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -3094,4 +3094,36 @@
             log.info("Konuyla eşleşmeyen Wikipedia görseli kaldırıldı: %s (%s)", p["id"], ph[0].get("alt"))
 
+    def redo_recent_photos(self, per_run: int = 6) -> None:
+        """Tek seferlik: "yalnızca basın görseli" kuralının açık olduğu dönemde (24 Kasım 2026'dan beri) fotoğrafsız kalan
+        ya da Wikipedia yedeğiyle (logo, şirket binası…) yayımlanan haberlerin görselleri kaynaklarından yeniden seçilir."""
+        if self.cfg.mock or self.cfg.fixtures_dir or not self.cfg.get("images", "photos", True):
+            return
+        since = str(self.cfg.get("images", "photo_redo_since", "") or "")
+        if not since:
+            return
+        done = self.state.setdefault("photo_redo", [])
+        todo = [p for p in self.store.posts()
+                if (p.get("published_at") or "") >= since and p["id"] not in done and not p.get("photos_removed")
+                and (p.get("image") or {}).get("source") != "ai"
+                and all(r.get("credit") == "Wikipedia" for r in p.get("photos") or [])][:per_run]
+        for p in todo:
+            done.append(p["id"])
+            old = list(p.get("photos") or [])
+            if self._attach_photos(p, draft=False):
+                p["updated_at"] = p.get("updated_at") or p.get("published_at")
+                log.info("Görsel yeniden seçildi: %s (%d fotoğraf)", p["id"], len(p["photos"]))
+            elif old and any(photos.wiki_bad(r.get("src", ""), r.get("alt", "")) for r in old):
+                for f in self.store.gallery_files(p["id"], draft=False):
+                    f.unlink(missing_ok=True)
+                p.pop("photos", None)
+                p["image"] = {"source": "cover"}
+                try:
+                    self._make_og(p)
+                except Exception as e:  # noqa: BLE001
+                    log.warning("Paylaşım görseli yenilenemedi (%s): %s", p["id"], e)
+                log.info("Uygunsuz Wikipedia görseli kaldırıldı: %s", p["id"])
+            self.store.save_post(p)
+        del done[:-400]
+
     def fill_missing_photos(self, per_run: int = 8) -> None:
         """Tek seferlik + sürekli: sitede fotoğrafsız görünen haberler için yeniden fotoğraf ara
@@ -3358,4 +3390,5 @@
                 self.more_photos()
                 self.recheck_wiki_photos()
+                self.redo_recent_photos()
                 self.fill_missing_photos()
                 self.backfill_photos(int(self.cfg.get("images", "photo_backfill_per_run", 5) or 0))
--- a/haberbot/photos.py
+++ b/haberbot/photos.py
@@ -280,4 +280,15 @@
 
 
+# Haber görseli olmaz: logo / simge, şirket binası, yapay zeka ile çizilmiş görsel (dosya adına ya da sayfa başlığına göre)
+WIKI_BAD = re.compile(r"(?<![a-z])(?:logo|icon|wordmark|emblem|hq|bina)(?![a-z])|logotype|headquart|headquater|"
+                      r"building|campus|genel[_ ]merkez|dall[-_ ]?e(?![a-z])|midjourney|stable[_ ]diffusion|"
+                      r"ai[-_ ]generated|generated[_ ]by[_ ]ai|yapay[_ ]zeka[_ ]ile", re.I)
+
+
+def wiki_bad(src: str, title: str = "") -> bool:
+    name = re.sub(r"%[0-9A-Fa-f]{2}", "_", (src or "").rsplit("/", 1)[-1])
+    return bool(WIKI_BAD.search(name) or WIKI_BAD.search(title or ""))
+
+
 def _wiki_names(names: list[str]) -> list[str]:
     """Aranacak adlar: özel adlar (büyük harf içeren), en belirgin olan önce (ürün adı şirket adından önce)."""
@@ -310,4 +321,7 @@
                 src = re.sub(r"/\d+px-", "/960px-", th) if "/thumb/" in th else src
             if not src or src.lower().endswith(".svg"):
+                continue
+            if wiki_bad(org.get("source") or src) or wiki_bad(src):
+                log.info("Wikipedia görseli kullanılmadı (logo / bina / yapay zeka görseli): %s", src.rsplit("/", 1)[-1][:80])
                 continue
             im = fetch_image(src, "https://wikipedia.org/", ua=WIKI_UA)
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -552,5 +552,9 @@
 Drop everything else, in particular: advertisements and shopping/deal promos (unrelated products such as keychains,
 mice, scales, gadgets for sale), thumbnails of other articles, unrelated products or cars, logos and banners of the news
-outlet, author photos, app-store badges, generic stock images that do not show the subject. When unsure, drop it.
+outlet, author photos, app-store badges, generic stock images that do not show the subject. Also drop: a company's
+headquarters, office building or store front (unless the story is about that building), a bare logo or app icon on a
+plain background, AI-generated illustrations and clip-art (circuit-board brains, glowing robots), and pictures of a
+different company or product than the one the story is about (e.g. Sony's building for a CD Projekt game).
+When unsure, drop it.
 Return in "text" the numbers of ALL images (kept or not) that have words ADDED ON TOP of the picture by a publisher: a
 headline or title, a caption, a slogan, "NEW" / "LEAKED" / "BREAKING" style banners, price tags, big outlet logos, or a
--- a/templates/about.html
+++ b/templates/about.html
@@ -16,5 +16,5 @@
     <li><strong>Kopyalama yok.</strong> Kaynak metinler çevrilip aktarılmaz; bilgiler özetlenip kendi cümlelerimizle yazılır.</li>
     <li><strong>Uydurma yok.</strong> Kaynaklarda olmayan rakam, tarih, alıntı ya da iddia eklenmez. Doğrulanmamış bilgiler kaynağına atfedilir.</li>
-    <li><strong>Fotoğraflar kaynağıyla.</strong> Haberlerdeki fotoğraflar, ilgili şirketin basın için yayımladığı görseller ya da açık lisanslı (Wikipedia) görsellerdir; haber sitelerinin kendi fotoğraflarını kullanmayız (Kasım 2026'dan önceki bazı haberlerde kaynak yayının görselleri, kaynağıyla birlikte yer alır). Her fotoğrafın altında kaynağı ve bağlantısı yer alır. Fotoğraf bulunamayan haberlerde habere özel renkli bir zemin kullanılır; yapay zeka ile üretilmiş temsili görseller altında belirtilir.</li>
+    <li><strong>Fotoğraflar kaynağıyla.</strong> Haberlerdeki fotoğraflar, öncelikle ilgili şirketin basın için yayımladığı görsellerdir; bunlar yoksa haberin kaynağında yayımlanan görseller kullanılır. Her fotoğrafın altında kaynağı ve bağlantısı yer alır. Fotoğraf bulunamayan haberlerde habere özel renkli bir zemin kullanılır; yapay zeka ile üretilmiş temsili görseller altında belirtilir.</li>
     <li><strong>Kaldırma talepleri.</strong> Bir fotoğrafın ya da metnin hak sahibiysen ve kaldırılmasını istiyorsan {% if site.contact_email %}<strong>{{ site.contact_email }}</strong> adresine{% else %}bize{% endif %} yaz; talebini hızla değerlendiririz.</li>
     <li><strong>Yapay zeka destekli yayın masası.</strong> Haberler yapay zeka destekli yayın masasında seçilir ve yazılır; bu durum her haberin altında belirtilir. Doğrulanmamış iddialar, söylentiler ve kaynakları çelişen haberler yayımlanmaz; resmi olmayan bilgiler ancak kaynağına açıkça atfedilerek aktarılır. Editör, yayındaki haberleri izler; hatalı bulunanları düzeltir ya da kaldırır.</li>
--- a/tests/test_photos.py
+++ b/tests/test_photos.py
@@ -423,2 +423,34 @@
             fn()
             print("ok", name)
+
+
+def test_wiki_fallback_rejects_logos_buildings_and_ai_art():
+    from haberbot.photos import wiki_bad
+    for bad in ("Sony_headquaters_2.jpg", "Instagram_logo_2022.svg.png", "Microsoft_Outlook_Icon_2025.png",
+                "Dall-e_3_%28jan_%2724%29_artificial_intelligence_icon.png", "Apple_Park_campus.jpg"):
+        assert wiki_bad(bad), bad
+    for good in ("PlayStation_5_and_DualSense.jpg", "Silicon_Valley.jpg", "1Password_login_screen.png"):
+        assert not wiki_bad(good), good
+
+
+def test_recent_posts_get_their_photos_reselected(monkeypatch):
+    with _App() as (cfg, a):
+        cfg.raw["images"]["photo_redo_since"] = "2000-01-01"
+        bad_wiki = [{"src": "https://upload.wikimedia.org/x/Sony_headquaters_2.jpg", "credit": "Wikipedia",
+                     "page": "https://tr.wikipedia.org/wiki/Sony", "alt": "Sony", "kind": "wiki", "file": "p1-g0.webp",
+                     "w": 800, "h": 600}]
+        a.store.save_post(_post(photos=bad_wiki, image={"source": "photo", "photo": "p1-g0.webp"}))
+        a.store.save_post(_post(id="p2", slug="iki", photos=[dict(bad_wiki[0], file="p2-g0.webp")],
+                                image={"source": "photo", "photo": "p2-g0.webp"}))
+        shots = [{"image": _photo("#446", seed=1), "src": "https://cdn.ign.com/ps-plus.jpg", "credit": "IGN",
+                  "page": "https://ign.com/a", "alt": "", "kind": "og", "graphic": False, "src_kind": "media"}]
+        monkeypatch.setattr(appmod.photos, "gather",
+                            lambda srcs, *a_, **k: shots if any("brand.com" in s.get("url", "") for s in srcs) else [])
+        monkeypatch.setattr(appmod.photos, "wiki_photo", lambda names: None)
+        a.store.save_post({**a.store.load_post("p2"), "sources": [{"name": "X", "url": "https://x.com/a", "kind": "media"}]})
+        a.redo_recent_photos()
+        p1, p2 = a.store.load_post("p1"), a.store.load_post("p2")
+        assert [r["src"] for r in p1["photos"]] == ["https://cdn.ign.com/ps-plus.jpg"]      # kaynak fotoğrafı geldi
+        assert not p2.get("photos") and p2["image"]["source"] == "cover"                     # bina görseli kalktı
+        a.redo_recent_photos()                                                               # bir kez çalışır
+        assert sorted(a.state["photo_redo"]) == ["p1", "p2"]
@@@SM@@@ SHA
a69c4a1733f1101dcfd4f3ad5d5b0db9bfa8ffcd42e60eae043f666298bc1a43 config.yaml
5303df449a0608e174fca987b5ab70b3ddd4d5184e445358e58a8c57838eb3f0 haberbot/app.py
6d191421a4a58d173653959b0f29c31fd0096e231d05cd69cb697a9c88e55d6d haberbot/photos.py
b4c3b41dbdb2deaacfe6df3e5765bfd7a0e788f37e4a7a3d70020c5fd8c531c9 haberbot/prompts.py
6a5d467c4bc48558810c452c1370ed5a8246d9cbadc461cade453c590fb48914 templates/about.html
62359ff2dbbcca27cd1329bc7d66bebe3c04b21fa136d6945db8a4899553b88e tests/test_photos.py
