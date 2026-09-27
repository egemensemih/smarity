SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -58,9 +58,10 @@
 images:
   # Gerçek fotoğraflar: önce şirketin resmi görseli, yoksa kaynak haberin görselleri (kaynağı fotoğrafın altında yazar).
-  # Fotoğraf bulunamazsa aşağıdaki tipografik kapak kullanılır.
+  # Kapak her zaman bizim tasarımımızdır: anlamlı bir fotoğraf varsa üstüne dev rakam / isim / manşet yazılır,
+  # yoksa (ekran görüntüsü, grafik, yazılı paylaşım görseli) tipografik kapak kullanılır. Diğer fotoğraflar
+  # kaydırmalı alanda ve haberin paragrafları arasında, kaynağıyla gösterilir. Fotoğraflar hiç silinmez.
   photos: true
-  photo_limit: 6                  # haber başına en fazla fotoğraf (1 ana + galeri)
+  photo_limit: 6                  # haber başına en fazla fotoğraf
   photo_backfill_per_run: 5       # eski haberlere her turda kaç tanesine fotoğraf eklensin
-  gallery_keep_days: 0            # 0 = fotoğraflar hiç silinmez (kalıcı depolama)
   # kapak: habere özel tipografik kapak (dev rakam / isim / manşet), ücretsiz (önerilen)
   # 3d   : renkli 3D şekiller
@@ -103,4 +104,5 @@
 #  type: rss (varsayılan) | html (RSS'i olmayan sayfalar için)
 #  Bir kaynağı kapatmak için satırlarının başına # koy.
+#  photo_cover: false → kaynağın paylaşım görseline yazı basılıysa o görsel alınmaz, sadece haberdeki fotoğraflar.
 # ─────────────────────────────────────────────────────────────
 sources:
@@ -210,4 +212,5 @@
     url: https://www.donanimhaber.com/rss/tum/
     kind: media
+    photo_cover: false   # paylaşım görsellerine yazı basıyor: yalnızca haber içindeki fotoğraflar alınır
   - name: LOG
     url: https://www.log.com.tr/feed/
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -13,5 +13,5 @@
 from . import photos, policy
 from .config import CATEGORIES, DEFAULT_CATEGORY, Config, category_label, indexnow_key
-from .covers import COVER_VERSION
+from .covers import COVER_VERSION, PHOTO_COVER_VERSION, photo_design
 from .extract import full_text
 from .instagram import Instagram, InstagramError, TokenStore, fingerprint, head_ok
@@ -471,5 +471,5 @@
                    {"text": "❌ Reddet", "callback_data": f"r:{did}"}],
                   [{"text": "📄 Tam metin", "callback_data": f"f:{did}"},
-                   {"text": "🔁 Yeniden yaz", "callback_data": f"w:{did}"}] + self._visual_buttons(d)]
+                   {"text": "🔁 Yeniden yaz", "callback_data": f"w:{did}"}], self._visual_buttons(d)]
             if src:
                 kb.append([{"text": "🔗 Kaynağı aç", "url": src}])
@@ -478,6 +478,6 @@
             return [[{"text": "🔗 Haberi aç", "url": self.cfg.post_url(d["slug"])},
                      {"text": "🗑 Kaldır", "callback_data": f"d:{did}"}],
-                    [{"text": "📄 Tam metin", "callback_data": f"f:{did}"}] + self._visual_buttons(d)
-                    + [{"text": "📱 Instagram", "callback_data": f"s:{did}"}]]
+                    [{"text": "📄 Tam metin", "callback_data": f"f:{did}"},
+                     {"text": "📱 Instagram", "callback_data": f"s:{did}"}], self._visual_buttons(d)]
         if kind == "rejected":
             return [[{"text": "↩️ Geri al", "callback_data": f"u:{did}"}]]
@@ -712,8 +712,17 @@
             if action == "g":
                 local = [r for r in d["photos"] if r.get("file")]
-                if len(local) < 2:
-                    return "Başka fotoğraf yok."
-                self._reorder_photos(d, where, local[1:] + local[:1] + [r for r in d["photos"] if not r.get("file")])
-                msg = "🖼 Fotoğraf değişti"
+                good = [r for r in local if not r.get("graphic")]
+                if d.get("cover_mode") == "type" and any(self._coverable(r) for r in good):
+                    d.pop("cover_mode", None)            # yazılı kapaktan fotoğraflı kapağa dön
+                    self._build_cover(d, where == "draft")
+                    msg = "🖼 Fotoğraflı kapak"
+                else:
+                    coverable = [r for r in good if self._coverable(r)]
+                    if len(coverable) < 2:
+                        return "Kapak olabilecek başka fotoğraf yok."
+                    cur = next((r for r in coverable if r["file"] == (d.get("image") or {}).get("photo")), coverable[0])
+                    rest = [r for r in good if r is not cur]      # grafikler sonda kalır
+                    self._reorder_photos(d, where, rest + [cur] + [r for r in local if r.get("graphic")])
+                    msg = "🖼 Fotoğraf değişti"
             else:
                 self._drop_photos(d, where)
@@ -788,16 +797,16 @@
         if new_visual:
             text = visual_only.strip()
-            if text and len(text) <= 24:   # kısa ifade: kapaktaki büyük yazı olsun
+            if text and len(text) <= 24:   # kısa ifade: kapaktaki büyük yazı olsun (fotoğraflı kapakta da)
                 d["cover_text"] = text
                 d["cover_variant"] = int(d.get("cover_variant", 0)) + 1
             elif text:                      # uzun ifade: yapay zeka görseli sahnesi
                 d["visual_scene"] = text
-            else:                           # "Yeni görsel" düğmesi: yeni renk ve düzen
+                d["cover_mode"] = "type"
+            else:                           # "Yeni kapak" düğmesi: yazılı kapak, yeni renk ve düzen
                 d["cover_variant"] = int(d.get("cover_variant", 0)) + 1
+                d["cover_mode"] = "type"
             d["rewrites"] = (d.get("rewrites") or 0) + 1
             old_kind = "pending" if where == "draft" else ("auto" if d.get("publish_mode") == "auto" else "published")
-            if d.get("photos"):
-                self._drop_photos(d, where)
-            d["image"] = self.vis.make_hero(d, self._hero(d))
+            self._build_cover(d, where == "draft")   # fotoğraflar galeride kalır
             self._image_feedback(d["image"])
             if where == "draft":
@@ -993,5 +1002,5 @@
         todo = [p for p in self.store.posts()
                 if (p.get("image") or {}).get("source") in ("cover", "fallback", None)
-                and (p.get("image") or {}).get("cover_v") != COVER_VERSION and not p.get("photos")][:limit]
+                and (p.get("image") or {}).get("cover_v") != COVER_VERSION][:limit]
         for p in todo:
             try:
@@ -1289,23 +1298,64 @@
 
     # ── gerçek fotoğraflar ──────────────────────────────────
+    # Düzen: fotoğraflar {id}-g0.webp, {id}-g1.webp … ; {id}.webp her zaman tasarımlı kapaktır:
+    # anlamlı bir fotoğraf varsa fotoğraflı kapak, yoksa (ya da cover_mode "type" ise) tipografik kapak.
+    PHOTOS_V = 2
+    COVER_MIN_W = 900          # kapak için en az bu genişlikte gerçek fotoğraf gerekir
+
     def _visual_buttons(self, d: dict) -> list[dict]:
         did = d["id"]
-        if d.get("photos"):
-            out = [{"text": "🚫 Fotoğrafsız", "callback_data": f"n:{did}"}]
-            if len(d["photos"]) > 1:
-                out.insert(0, {"text": "🖼 Başka foto", "callback_data": f"g:{did}"})
-            return out
-        return [{"text": "🎨 Yeni görsel", "callback_data": f"v:{did}"}]
+        if not d.get("photos"):
+            return [{"text": "🎨 Yeni görsel", "callback_data": f"v:{did}"}]
+        good = [r for r in d["photos"] if r.get("file") and not r.get("graphic")]
+        out = []
+        if d.get("cover_mode") == "type" and any(self._coverable(r) for r in good):
+            out.append({"text": "🖼 Fotoğraflı kapak", "callback_data": f"g:{did}"})
+        elif sum(self._coverable(r) for r in good) > 1:
+            out.append({"text": "🖼 Başka foto", "callback_data": f"g:{did}"})
+        photo_cover = (d.get("image") or {}).get("source") == "photo"
+        out.append({"text": "🎨 Yazılı kapak" if photo_cover else "🎨 Yeni kapak", "callback_data": f"v:{did}"})
+        out.append({"text": "🚫 Fotoğrafsız", "callback_data": f"n:{did}"})
+        return out
 
     def _photo_dir(self, draft: bool):
         return self.cfg.drafts_dir if draft else self.cfg.images_dir
 
+    def _no_cover_sources(self) -> set[str]:
+        """Paylaşım görseline yazı basan kaynaklar (ayarlarda photo_cover: false)."""
+        return {x.get("name") for x in self.cfg.sources if x.get("photo_cover") is False}
+
+    def _coverable(self, r: dict) -> bool:
+        """Kapak olabilecek fotoğraf: gerçek fotoğraf, düz zeminli tanıtım görseli değil, yeterince büyük."""
+        return bool(r.get("file")) and not r.get("graphic") and r.get("cover_ok", True) and (r.get("w") or 0) >= self.COVER_MIN_W
+
+    def _cover_photo(self, d: dict, folder) -> dict | None:
+        if d.get("cover_mode") == "type":
+            return None
+        return next((r for r in d.get("photos") or [] if self._coverable(r) and (folder / r["file"]).exists()), None)
+
+    def _build_cover(self, d: dict, draft: bool) -> None:
+        """Kapağı ({id}.webp) üret: fotoğraflı kapak ya da tipografik kapak."""
+        folder = self._photo_dir(draft)
+        hero = folder / f"{d['id']}.webp"
+        r = self._cover_photo(d, folder)
+        if r:
+            try:
+                self.vis.photo_cover(d, folder / r["file"], hero)
+                d["image"] = {"source": "photo", "photo": r["file"], "credit": r.get("credit", ""),
+                              "page": r.get("page", ""), "src": r.get("src", ""), "layout": photo_design(d)["layout"],
+                              "cover_v": PHOTO_COVER_VERSION}
+                return
+            except Exception as e:  # noqa: BLE001
+                log.warning("Fotoğraflı kapak üretilemedi (%s), yazılı kapak kullanılacak: %s", d.get("id"), e)
+        d["image"] = self.vis.make_hero(d, hero)
+
     def _attach_photos(self, d: dict, draft: bool) -> bool:
-        """Kaynaklardan gerçek fotoğrafları al: ilki ana görsel, diğerleri galeri. Bulunamazsa False."""
+        """Kaynaklardan gerçek fotoğrafları al ve kapağı üret. Bulunamazsa False."""
         cfg = self.cfg
         if not cfg.get("images", "photos", True) or cfg.mock or cfg.fixtures_dir:
             return False
         try:
-            got = photos.gather(d.get("sources") or [], limit=int(cfg.get("images", "photo_limit", 6) or 6))
+            got = photos.gather(d.get("sources") or [], limit=int(cfg.get("images", "photo_limit", 6) or 6),
+                                skip_cover=self._no_cover_sources())
         except Exception as e:  # noqa: BLE001
             log.warning("Fotoğraflar alınamadı (%s): %s", d.get("id"), e)
@@ -1318,10 +1368,13 @@
         recs = []
         for i, p in enumerate(got):
-            name = f"{d['id']}.webp" if i == 0 else f"{d['id']}-g{i}.webp"
-            w, h = photos.save_webp(p["image"], folder / name, 1600 if i == 0 else 1280, 80 if i == 0 else 74)
-            recs.append({"file": name, "src": p["src"], "credit": p["credit"], "page": p["page"],
-                         "alt": p["alt"], "w": w, "h": h})
+            name = f"{d['id']}-g{i}.webp"
+            w, h = photos.save_webp(p["image"], folder / name, 1600, 80 if p.get("graphic") else 78)
+            recs.append({"file": name, "src": p["src"], "credit": p["credit"], "page": p["page"], "alt": p["alt"],
+                         "w": w, "h": h, "kind": p.get("kind", ""), "graphic": bool(p.get("graphic")),
+                         "cover_ok": bool(p.get("cover_ok", not p.get("graphic")))})
         d["photos"] = recs
-        d["image"] = {"source": "photo", "credit": recs[0]["credit"], "page": recs[0]["page"], "src": recs[0]["src"]}
+        d["photos_v"] = self.PHOTOS_V
+        d.pop("cover_mode", None)
+        self._build_cover(d, draft)
         if not draft:
             self._make_og(d)
@@ -1329,27 +1382,24 @@
 
     def _reorder_photos(self, d: dict, where: str, order: list[dict]) -> None:
-        """Fotoğraf sırasını değiştir (ilk sıradaki ana görsel olur); dosya adları sıraya göre yeniden verilir."""
-        from PIL import Image
+        """Fotoğraf sırasını değiştir (dosyalar yeniden adlandırılır, yeniden sıkıştırılmaz) ve kapağı yenile."""
         draft = where == "draft"
         folder = self._photo_dir(draft)
-        loaded = []
-        for rec in order:
+        moved = []
+        for i, rec in enumerate(order):
             f = folder / rec["file"] if rec.get("file") else None
-            loaded.append((rec, Image.open(f).convert("RGB") if f and f.exists() else None))
+            if f and f.exists():
+                t = folder / f"{d['id']}-t{i}.webp"
+                f.rename(t)
+                moved.append((dict(rec), t))
         for f in self.store.gallery_files(d["id"], draft):
             f.unlink(missing_ok=True)
         recs = []
-        for i, (rec, im) in enumerate(loaded):
-            name = f"{d['id']}.webp" if i == 0 else f"{d['id']}-g{i}.webp"
-            rec = dict(rec)
-            if im is not None:
-                photos.save_webp(im, folder / name, 1600, 82)
-                rec["file"] = name
-            else:
-                rec["file"] = None
+        for rec, t in moved:
+            rec["file"] = f"{d['id']}-g{len(recs)}.webp"
+            t.rename(folder / rec["file"])
             recs.append(rec)
-        d["photos"] = [r for r in recs if r.get("file") or r.get("src")]
-        first = d["photos"][0]
-        d["image"] = {"source": "photo", "credit": first["credit"], "page": first["page"], "src": first["src"]}
+        d["photos"] = recs
+        d["photos_v"] = self.PHOTOS_V
+        self._build_cover(d, draft)
 
     def _drop_photos(self, d: dict, where: str) -> None:
@@ -1357,16 +1407,85 @@
             f.unlink(missing_ok=True)
         d.pop("photos", None)
+        d.pop("cover_mode", None)
         d["photos_removed"] = True
         d["image"] = {"source": "cover"}
 
     def _make_og(self, p: dict) -> None:
-        """Paylaşım görseli: fotoğraf varsa fotoğrafın kırpımı, yoksa marka kartı."""
+        """Paylaşım görseli: fotoğraflı kapak (logo, kategori ve fotoğraf kredisiyle) ya da özet kartı."""
         st = self.store
-        hero = st.post_image(p["id"])
-        if (p.get("image") or {}).get("source") == "photo" and hero.exists():
-            from PIL import Image
-            photos.og_crop(Image.open(hero).convert("RGB"), st.post_og(p["id"]))
+        img = p.get("image") or {}
+        photo = self.cfg.images_dir / img["photo"] if img.get("source") == "photo" and img.get("photo") else None
+        if photo is not None and photo.exists():
+            try:
+                self.vis.photo_cover(p, photo, st.post_og(p["id"]), size=(1200, 630), brand=True, kicker=True,
+                                     credit=img.get("credit", ""))
+                return
+            except Exception as e:  # noqa: BLE001
+                log.warning("Fotoğraflı paylaşım görseli üretilemedi (%s): %s", p["id"], e)
+                from PIL import Image
+                photos.og_crop(Image.open(photo).convert("RGB"), st.post_og(p["id"]))
+                return
+        self.vis.render_card(p, "og", st.post_image(p["id"]), st.post_og(p["id"]))
+
+    def _migrate_photos(self, p: dict) -> None:
+        """Eski düzen (ilk fotoğraf {id}.webp) → yeni düzen ({id}-gN.webp, grafik/fotoğraf ayrımı).
+
+        Paylaşım görseline yazı basan kaynakların (photo_cover: false) ilk fotoğrafı o kaynağın paylaşım
+        görseliydi; o fotoğraf atılır.
+        """
+        from PIL import Image
+        folder, pid = self.cfg.images_dir, p["id"]
+        no_cover, seen, keep = self._no_cover_sources(), set(), []
+        for r in p.get("photos") or []:
+            c = r.get("credit")
+            if c in no_cover and c not in seen:
+                seen.add(c)
+                continue
+            seen.add(c)
+            keep.append(dict(r))
+        tmp = []
+        for i, r in enumerate(keep):
+            f = folder / r["file"] if r.get("file") else None
+            if f and f.exists():
+                t = folder / f"{pid}-t{i}.webp"
+                f.rename(t)
+                with Image.open(t) as im:
+                    r.update(photos.classify(im.convert("RGB")))
+                    r["w"], r["h"] = im.size
+                tmp.append((r, t))
+        for f in self.store.gallery_files(pid, draft=False):
+            f.unlink(missing_ok=True)
+        tmp.sort(key=lambda x: bool(x[0]["graphic"]))
+        recs = []
+        for r, t in tmp:
+            r["file"] = f"{pid}-g{len(recs)}.webp"
+            t.rename(folder / r["file"])
+            recs.append(r)
+        if recs:
+            p["photos"] = recs
         else:
-            self.vis.render_card(p, "og", hero, st.post_og(p["id"]))
+            p.pop("photos", None)
+        p["photos_v"] = self.PHOTOS_V
+
+    def upgrade_photos(self, limit: int = 30) -> None:
+        """Fotoğraflı haberleri yeni düzene geçir; fotoğraflı kapak tasarımı değişince kapakları yenile."""
+        def due(p: dict) -> bool:
+            if not p.get("photos"):
+                return False
+            img = p.get("image") or {}
+            return p.get("photos_v") != self.PHOTOS_V or (img.get("source") == "photo" and img.get("cover_v") != PHOTO_COVER_VERSION)
+        todo = [p for p in self.store.posts() if due(p)][:limit]
+        for p in todo:
+            try:
+                if p.get("photos_v") != self.PHOTOS_V:
+                    self._migrate_photos(p)
+                self._build_cover(p, draft=False)
+                self._make_og(p)
+                self.store.save_post(p)
+            except Exception as e:  # noqa: BLE001
+                log.warning("Fotoğraflı kapak yenilenemedi (%s): %s", p["id"], e)
+                return
+        if todo:
+            log.info("Fotoğraflı kapaklar yenilendi: %d", len(todo))
 
     def backfill_photos(self, limit: int = 5) -> None:
@@ -1383,28 +1502,4 @@
                 log.info("Fotoğraf eklendi: %s (%d)", p["id"], len(p["photos"]))
             self.store.save_post(p)
-
-    def prune_gallery(self) -> None:
-        """Yer kazanmak için eski haberlerin galeri kopyalarını sil (ana görsel kalır, galeri kaynaktan gösterilir)."""
-        if self.state.get("last_prune") == self.today():
-            return
-        self.state["last_prune"] = self.today()
-        keep = float(self.cfg.get("images", "gallery_keep_days", 0) or 0)
-        if keep <= 0:  # 0 = hiçbir fotoğraf silinmez
-            return
-        n = 0
-        for p in self.store.posts():
-            if hours_since(p.get("published_at")) < keep * 24 or not p.get("photos"):
-                continue
-            changed = False
-            for rec in p["photos"][1:]:
-                if rec.get("file"):
-                    (self.cfg.images_dir / rec["file"]).unlink(missing_ok=True)
-                    rec["file"] = None
-                    changed = True
-                    n += 1
-            if changed:
-                self.store.save_post(p)
-        if n:
-            log.info("Eski galeri kopyaları silindi: %d", n)
 
     # ── tek çalışma ─────────────────────────────────────────
@@ -1436,7 +1531,10 @@
             try:
                 self.backfill_photos(int(self.cfg.get("images", "photo_backfill_per_run", 5) or 0))
-                self.prune_gallery()
             except Exception as e:  # noqa: BLE001
                 log.exception("Fotoğraf işlemi hatası: %s", e)
+        try:
+            self.upgrade_photos()
+        except Exception as e:  # noqa: BLE001
+            log.exception("Fotoğraflı kapak hatası: %s", e)
         try:
             self.ig_tick()
--- a/haberbot/covers.py
+++ b/haberbot/covers.py
@@ -210,4 +210,31 @@
         "brand_name": brand_name,
         "caption": (d.get("short_title") or d.get("title", "")) if caption and layout in ("sayi", "isim") else "",
+    }
+
+
+# ── Fotoğraflı kapak ─────────────────────────────────────────
+PHOTO_COVER_VERSION = 1
+
+
+def photo_design(d: dict, brand: bool = False, kicker: str = "", credit: str = "", brand_name: str = "Smarity") -> dict:
+    """Gerçek fotoğrafın üstüne bizim tasarım dilimiz: kategori renginde ışık, altta dev rakam / isim / manşet."""
+    _, pal = palette_for(d)
+    stat = (d.get("hero_stat") or "").strip()
+    word = cover_word(d)
+    if stat and len(stat) <= 12:
+        layout = "sayi"
+    elif word:
+        layout = "isim"
+    else:
+        layout = "manset"
+    kw = d.get("focus_keyword") or ""
+    if kw.lower() in GENERIC or len(kw.split()) > 3 or kw.lower().startswith("yapay zeka"):
+        kw = ""
+    title = d.get("short_title") or d.get("title", "")
+    return {
+        "layout": layout, "pal": pal[:4], "stat": stat, "stat_label": (d.get("hero_stat_label") or "").strip(),
+        "word": word, "headline": _highlight(title, word or kw), "title": title,
+        "kicker": kicker, "brand": brand, "brand_name": brand_name, "credit": credit,
+        "focus": d.get("photo_focus") or "50% 42%",
     }
 
--- a/haberbot/photos.py
+++ b/haberbot/photos.py
@@ -5,6 +5,7 @@
 Küçük/logo/ikon görseller ve aynı fotoğrafın farklı boyutları elenir.
 
-Ana fotoğraf ve galerinin ilk günleri için kopyalar sitede tutulur (hızlı ve güvenilir);
-eski galerilerde yer kazanmak için yerel kopya silinip kaynaktaki adres kullanılır.
+Her fotoğraf "fotoğraf" ya da "grafik" (ekran görüntüsü, tablo, belge) diye sınıflanır: kapakta yalnızca
+gerçek fotoğraf kullanılır, grafikler haberin içine yerleşir. Paylaşım görsellerine yazı basan kaynaklar
+(ayarlarda photo_cover: false) için yalnızca haber metnindeki fotoğraflar alınır.
 Hak sahibi talep ederse fotoğraflar Telegram'dan tek tuşla kaldırılır.
 """
@@ -18,5 +19,5 @@
 
 import requests
-from PIL import Image, ImageOps, ImageStat
+from PIL import Image, ImageChops, ImageOps, ImageStat
 
 from .extract import UA, fetch_html
@@ -197,4 +198,41 @@
 
 
+def _stats(im: Image.Image) -> tuple[float, float]:
+    """(düz zemin oranı, ince çizgi yoğunluğu) — 480 px genişlikte ölçülür."""
+    w = 480
+    small = im.convert("RGB").resize((w, max(2, round(im.height * w / im.width))), Image.BILINEAR)
+    px = small.tobytes()
+    counts: dict[int, int] = {}
+    for i in range(0, len(px), 3):
+        k = (px[i] >> 4) << 8 | (px[i + 1] >> 4) << 4 | (px[i + 2] >> 4)
+        counts[k] = counts.get(k, 0) + 1
+    n = len(px) // 3
+    flat = sum(sorted(counts.values(), reverse=True)[:2]) / n
+    g = small.convert("L")
+    gw, gh = g.size
+    base = g.crop((0, 0, gw - 1, gh - 1))
+    dx = ImageChops.difference(base, g.crop((1, 0, gw, gh - 1)))
+    dy = ImageChops.difference(base, g.crop((0, 1, gw - 1, gh)))
+    hist = ImageChops.add(dx, dy).histogram()      # 255'te doyar; eşik 80 olduğu için sorun değil
+    return flat, sum(hist[81:]) / n
+
+
+def classify(im: Image.Image) -> dict:
+    """Fotoğrafın türü.
+
+    graphic : ekran görüntüsü, tablo, harita, belge (zeminin çoğu tek renk + yoğun ince çizgi/yazı).
+              Kapak ya da kaydırmalı alan yerine haberin içine yerleşir.
+    cover_ok: kapak olabilir mi? Düz zeminli tanıtım görsellerinde (üstünde çoğu zaman kendi yazısı olur)
+              bizim yazımız kalabalık durur; bunlarda kapak yazılı olur, fotoğraf galeride gösterilir.
+    """
+    flat, edge = _stats(im)
+    graphic = flat >= 0.62 and edge >= 0.025
+    return {"graphic": graphic, "cover_ok": not graphic and flat < 0.7}
+
+
+def is_graphic(im: Image.Image) -> bool:
+    return classify(im)["graphic"]
+
+
 def usable(im: Image.Image) -> bool:
     w, h = im.size
@@ -205,6 +243,11 @@
 
 
-def gather(sources: list[dict], limit: int = 6, per_source: int = 4, pages: int = 3) -> list[dict]:
-    """Kaynaklardan fotoğraf topla. Dönen her öğe: {'image': PIL, 'src', 'credit', 'page', 'alt', 'kind'}"""
+def gather(sources: list[dict], limit: int = 6, per_source: int = 4, pages: int = 3,
+           skip_cover: set[str] | frozenset = frozenset()) -> list[dict]:
+    """Kaynaklardan fotoğraf topla. Dönen her öğe: {'image': PIL, 'src', 'credit', 'page', 'alt', 'kind', 'graphic'}
+
+    skip_cover: paylaşım görseline yazı basan kaynakların adları (bunlarda besleme/og görseli alınmaz).
+    Sıra: resmi kaynak önce; aynı sırada gerçek fotoğraflar grafiklerden önce gelir.
+    """
     order = sorted(sources, key=lambda s: 0 if s.get("kind") == "official" else 1)[:pages]
     picked: list[dict] = []
@@ -212,12 +255,14 @@
     for s in order:
         url = s.get("url") or ""
+        no_cover = (s.get("name") or "") in skip_cover
         cands: list[dict] = []
         feed_img = _abs(s.get("image") or "", url or "https://x/")
-        if feed_img and not BAD_URL.search(feed_img):
+        if feed_img and not BAD_URL.search(feed_img) and not no_cover:
             cands.append({"url": feed_img, "kind": "feed", "alt": ""})
         html = fetch_html(url) if url else ""
         if html:
             known = {_key(c["url"]) for c in cands}
-            cands += [c for c in candidates(html, url) if _key(c["url"]) not in known]
+            cands += [c for c in candidates(html, url) if _key(c["url"]) not in known
+                      and not (no_cover and c["kind"] != "body")]
         n = 0
         for c in cands:
@@ -232,9 +277,11 @@
             hashes.append(h)
             picked.append({"image": im, "src": c["url"], "credit": s.get("name") or urlsplit(url).netloc,
-                           "page": url, "alt": c["alt"], "kind": c["kind"]})
+                           "page": url, "alt": c["alt"], "kind": c["kind"], **classify(im)})
             n += 1
         if len(picked) >= limit:
             break
-    log.info("Fotoğraf: %d bulundu (%s)", len(picked), ", ".join(dict.fromkeys(p["credit"] for p in picked)) or "-")
+    picked.sort(key=lambda p: p["graphic"])  # kararlı sıralama: kaynak sırası korunur
+    log.info("Fotoğraf: %d bulundu, %d grafik (%s)", len(picked), sum(p["graphic"] for p in picked),
+             ", ".join(dict.fromkeys(p["credit"] for p in picked)) or "-")
     return picked
 
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -16,5 +16,5 @@
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "8"
+ASSET_V = "9"
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
 H2_RE = re.compile(r"<h[1-3]>(.*?)</h[1-3]>", re.S)
@@ -30,4 +30,37 @@
     out = H2_RE.sub(lambda m: f'<h2 id="{slugify(re.sub("<[^>]+>", "", m.group(1)), 60)}">{m.group(1)}</h2>', out)
     return out
+
+
+BLOCK_RE = re.compile(r"<(aside|blockquote|ul|ol|table|pre|figure)\b.*?</\1>", re.S)
+
+
+def figure_html(ph: dict) -> str:
+    """Haberin içine yerleşen fotoğraf: kaynağı altında."""
+    e = lambda v: htmlmod.escape(str(v or ""), quote=True)  # noqa: E731
+    remote = ' referrerpolicy="no-referrer" onerror="this.closest(\'figure\').remove()"' if ph.get("remote") else ""
+    cap = (f'<figcaption><a href="{e(ph.get("page"))}" rel="noopener nofollow" target="_blank">Görsel: {e(ph.get("credit"))}</a>'
+           f'</figcaption>' if ph.get("credit") else "")
+    return (f'<figure class="inl{" graphic" if ph.get("graphic") else ""}"><img src="{e(ph["url"])}" alt="{e(ph.get("alt"))}" '
+            f'width="{int(ph.get("w") or 1600)}" height="{int(ph.get("h") or 900)}" loading="lazy" decoding="async"{remote}>'
+            f'{cap}</figure>')
+
+
+def inline_figures(body_html: str, figs: list[dict], first: int = 1, every: int = 3) -> tuple[str, list[dict]]:
+    """Fotoğrafları metnin paragrafları arasına yerleştir (2. paragraftan sonra, sonra her 3 paragrafta bir).
+
+    Liste, alıntı ve "Neden önemli?" kutularının içine girmez. Yer kalmazsa artanlar geri döner.
+    """
+    if not figs:
+        return body_html, []
+    blocked = [m.span() for m in BLOCK_RE.finditer(body_html)]
+    ends = [m.end() for m in re.finditer(r"</p>", body_html) if not any(a <= m.start() < b for a, b in blocked)]
+    slots = ends[first::every]
+    use = figs[:len(slots)]
+    out, last = [], 0
+    for pos, ph in zip(slots, use):
+        out += [body_html[last:pos], "\n", figure_html(ph)]
+        last = pos
+    out.append(body_html[last:])
+    return "".join(out), figs[len(use):]
 
 
@@ -163,5 +196,6 @@
             "ai_image": (p.get("image") or {}).get("source") == "ai",
             "cover_image": (p.get("image") or {}).get("source") == "cover",
-            "stat_on_cover": (p.get("image") or {}).get("source") == "cover" and (p.get("image") or {}).get("layout") == "sayi",
+            # rakam kapakta yazıyorsa "öne çıkanlar" kutusunda tekrar edilmez
+            "stat_on_cover": (p.get("image") or {}).get("source") in ("cover", "photo") and (p.get("image") or {}).get("layout") == "sayi",
             "img_alt": clip(p.get("image_alt") or f"{short}: habere ait görsel", 125),
             "seo_title": seo_title,
@@ -186,30 +220,47 @@
             "minutes": reading_minutes(p.get("body", "")),
             "words": len(plain(p.get("body", "")).split()),
-            "body_html": (body_html := render_body(p.get("body", ""))),
+            **(media := self._media(p, short, render_body(p.get("body", "")))),
             "toc": [{"id": m.group(1), "text": re.sub("<[^>]+>", "", m.group(2))}
-                    for m in re.finditer(r'<h2 id="([^"]+)">(.*?)</h2>', body_html)],
+                    for m in re.finditer(r'<h2 id="([^"]+)">(.*?)</h2>', media["body_html"])],
             "key_points": [x for x in (p.get("carousel_points") or []) if x][:4],
             "photos": self._photos(p, short),
-            "has_photo": (p.get("image") or {}).get("source") == "photo",
+            "has_photo": bool(p.get("photos")),
             "updated_str": tr_date(p.get("updated_at"), cfg.tz) if p.get("updated_at") else "",
         }
 
     def _photos(self, p: dict, short: str) -> list[dict]:
-        """Haberin gerçek fotoğrafları (ilki ana görsel). Yerel kopyası silinmiş galeri fotoğrafı kaynaktan gösterilir."""
+        """Haberin gerçek fotoğrafları. Yerel kopyası olmayan fotoğraf kaynaktaki adresinden gösterilir."""
         cfg, b = self.cfg, self.base
         out = []
         for i, r in enumerate(p.get("photos") or []):
             local = bool(r.get("file")) and (cfg.images_dir / r["file"]).exists()
-            if not local and (i == 0 or not r.get("src")):
+            if not local and not r.get("src"):
                 continue
             out.append({
+                "file": r.get("file") or "",
                 "url": f"{b}/img/{r['file']}" if local else r["src"],
                 "remote": not local,
+                "graphic": bool(r.get("graphic")),
                 "credit": r.get("credit") or "",
                 "page": r.get("page") or "",
-                "alt": clip(r.get("alt") or (p.get("image_alt") if i == 0 else "") or f"{short} ({i + 1})", 125),
+                "alt": clip(r.get("alt") or f"{short}: {r.get('credit') or 'habere ait'} fotoğrafı ({i + 1})", 125),
                 "w": r.get("w") or 1600, "h": r.get("h") or 900,
             })
         return out
+
+    def _media(self, p: dict, short: str, body_html: str) -> dict:
+        """Kapak (ilk kare) + kaydırınca gelen fotoğraflar + metnin içine yerleşen fotoğraflar.
+
+        Kapakta kullanılan fotoğraf tekrar gösterilmez. Kaydırmalı alana en fazla 2 gerçek fotoğraf konur;
+        kalan fotoğraflar ve grafikler (ekran görüntüsü, tablo) paragrafların arasına yerleşir.
+        """
+        ph = self._photos(p, short)
+        img = p.get("image") or {}
+        cover = next((x for x in ph if x["file"] and x["file"] == img.get("photo")), None) if img.get("source") == "photo" else None
+        rest = [x for x in ph if x is not cover]
+        good = [x for x in rest if not x["graphic"]]
+        graphics = [x for x in rest if x["graphic"]]
+        body_html, left = inline_figures(body_html, good[2:] + graphics)
+        return {"body_html": body_html, "cover_photo": cover, "slides": good[:2] + left}
 
     def _write(self, rel: str, content: str) -> None:
@@ -298,5 +349,5 @@
         for p in posts:
             names = [f"{p['id']}.webp", f"{p['id']}.jpg", f"{p['id']}-og.jpg"]
-            names += [ph["url"].rsplit("/", 1)[-1] for ph in p.get("photos") or [] if not ph.get("remote")]
+            names += [ph["file"] for ph in p.get("photos") or [] if ph.get("file") and not ph.get("remote")]
             for name in dict.fromkeys(names):
                 src = cfg.images_dir / name
--- a/haberbot/visuals.py
+++ b/haberbot/visuals.py
@@ -210,4 +210,18 @@
         self.renderer.html_to_image("cover.html", ctx, size, tmp, quality=95)
         return Image.open(tmp).convert("RGB")
+
+    def photo_cover(self, d: dict, photo: Path, out: Path, size=HERO_SIZE, brand: bool = False,
+                    kicker: bool = False, credit: str = "") -> Path:
+        """Gerçek fotoğrafın üstüne kapak tasarımı (dev rakam / isim / manşet). .webp çıktı WEBP, diğerleri JPEG."""
+        ctx = covers.photo_design(d, brand=brand, kicker=category_label(d.get("category", "teknoloji")) if kicker else "",
+                                  credit=credit, brand_name=self.brand)
+        ctx["photo"] = photo.resolve().as_uri()
+        if out.suffix.lower() != ".webp":
+            return self.renderer.html_to_image("photo.html", ctx, size, out, quality=86)
+        tmp = self.renderer.cache / "_photo_cover.jpg"
+        self.renderer.html_to_image("photo.html", ctx, size, tmp, quality=95)
+        out.parent.mkdir(parents=True, exist_ok=True)
+        Image.open(tmp).convert("RGB").save(out, "WEBP", quality=82, method=6)
+        return out
 
     def make_hero(self, d: dict, out: Path) -> dict:
--- a/static/style.css
+++ b/static/style.css
@@ -267,4 +267,13 @@
 .art-media img { width: 100%; height: 100%; object-fit: cover; }
 .art-media figcaption { margin-top: 10px; font-size: 13px; color: var(--muted); }
+.art-media .ph { position: relative; }
+.gal-slide.cover .gal-credit, .art-media .gal-credit { left: auto; bottom: auto; top: 12px; right: 12px; }
+/* metnin içindeki fotoğraflar */
+.art-body figure.inl { margin: 34px 0; }
+.art-body figure.inl img { display: block; width: 100%; height: auto; border-radius: var(--r-md); background: var(--bg-alt); }
+.art-body figure.inl.graphic img { border: 1px solid var(--line); background: #fff; }
+.art-body figure.inl figcaption { margin-top: 10px; font-size: 13px; line-height: 1.4; color: var(--muted); }
+.art-body figure.inl figcaption a { color: inherit; text-decoration: none; }
+.art-body figure.inl figcaption a:hover { color: var(--ink, #1D1D1F); text-decoration: underline; }
 
 /* fotoğraf galerisi (kaydırmalı) */
--- a/templates/article.html
+++ b/templates/article.html
@@ -60,34 +60,38 @@
   </header>
 
-  {% if post.photos %}
-  {% set n = post.photos|length %}
-  <figure class="gal{{ ' single' if n == 1 }}" data-gal aria-label="Haberin fotoğrafları">
+  {% set cp = post.cover_photo %}
+  {% if post.slides %}
+  {% set n = post.slides|length + 1 %}
+  <figure class="gal" data-gal aria-label="Haberin görselleri">
     <div class="gal-view">
       <div class="gal-track">
-        {% for ph in post.photos %}
-        <div class="gal-slide{{ ' fit' if (ph.w / ph.h) < 1.25 }}" role="group" aria-label="{{ loop.index }} / {{ n }}">
-          <img src="{{ ph.url }}" alt="{{ ph.alt }}" width="{{ ph.w }}" height="{{ ph.h }}" decoding="async"{% if loop.first %} fetchpriority="high"{% else %} loading="lazy"{% endif %}{% if ph.remote %} referrerpolicy="no-referrer" onerror="this.parentNode.remove()"{% endif %} style="{% if loop.first %}view-transition-name: v{{ post.id }}{% endif %}">
+        <div class="gal-slide cover" role="group" aria-label="1 / {{ n }}">
+          <img src="{{ post.img }}" alt="{{ post.img_alt }}" width="1280" height="960" decoding="async" fetchpriority="high" style="view-transition-name: v{{ post.id }}">
+          {% if cp and cp.credit %}<a class="gal-credit" href="{{ cp.page or post.sources[0].url }}" rel="noopener nofollow" target="_blank">Görsel: {{ cp.credit }}</a>{% endif %}
+        </div>
+        {% for ph in post.slides %}
+        <div class="gal-slide{{ ' fit' if ph.graphic or (ph.w / ph.h) < 1.25 }}" role="group" aria-label="{{ loop.index + 1 }} / {{ n }}">
+          <img src="{{ ph.url }}" alt="{{ ph.alt }}" width="{{ ph.w }}" height="{{ ph.h }}" decoding="async" loading="lazy"{% if ph.remote %} referrerpolicy="no-referrer" onerror="this.parentNode.remove()"{% endif %}>
           {% if ph.credit %}<a class="gal-credit" href="{{ ph.page or post.sources[0].url }}" rel="noopener nofollow" target="_blank">Görsel: {{ ph.credit }}</a>{% endif %}
         </div>
         {% endfor %}
       </div>
-      {% if n > 1 %}
-      <button type="button" class="gal-btn" data-dir="-1" aria-label="Önceki fotoğraf">‹</button>
-      <button type="button" class="gal-btn" data-dir="1" aria-label="Sonraki fotoğraf">›</button>
+      <button type="button" class="gal-btn" data-dir="-1" aria-label="Önceki görsel">‹</button>
+      <button type="button" class="gal-btn" data-dir="1" aria-label="Sonraki görsel">›</button>
       <span class="gal-count" aria-live="polite"><b>1</b> / {{ n }}</span>
-      {% endif %}
     </div>
-    {% if n > 1 %}
     <div class="gal-thumbs">
-      {% for ph in post.photos %}
-      <button type="button" data-go="{{ loop.index0 }}" aria-label="{{ loop.index }}. fotoğraf"{% if loop.first %} aria-current="true"{% endif %}><img src="{{ ph.url }}" alt="" loading="lazy" decoding="async"{% if ph.remote %} referrerpolicy="no-referrer" onerror="this.parentNode.remove()"{% endif %}></button>
+      <button type="button" data-go="0" aria-label="Kapak" aria-current="true"><img src="{{ post.img }}" alt="" loading="lazy" decoding="async"></button>
+      {% for ph in post.slides %}
+      <button type="button" data-go="{{ loop.index }}" aria-label="{{ loop.index + 1 }}. görsel"><img src="{{ ph.url }}" alt="" loading="lazy" decoding="async"{% if ph.remote %} referrerpolicy="no-referrer" onerror="this.parentNode.remove()"{% endif %}></button>
       {% endfor %}
     </div>
-    {% endif %}
   </figure>
   {% else %}
   <figure class="art-media">
-    <div class="ph">{{ img(post, eager=true, sizes='(min-width: 880px) 840px, 100vw', priority=true) }}</div>
-    {% if not post.cover_image %}<figcaption>{% if post.ai_image %}Temsili görsel, yapay zeka ile üretilmiştir.{% else %}Temsili görsel.{% endif %}</figcaption>{% endif %}
+    <div class="ph">{{ img(post, eager=true, sizes='(min-width: 880px) 840px, 100vw', priority=true) }}
+      {% if cp and cp.credit %}<a class="gal-credit" href="{{ cp.page or post.sources[0].url }}" rel="noopener nofollow" target="_blank">Görsel: {{ cp.credit }}</a>{% endif %}
+    </div>
+    {% if not post.cover_image and not cp %}<figcaption>{% if post.ai_image %}Temsili görsel, yapay zeka ile üretilmiştir.{% else %}Temsili görsel.{% endif %}</figcaption>{% endif %}
   </figure>
   {% endif %}
--- a/tests/test_photos.py
+++ b/tests/test_photos.py
@@ -82,50 +82,158 @@
 
 
-def test_attach_backfill_and_buttons():
-    with tempfile.TemporaryDirectory() as t:
+def _doc(size=(1600, 900)):
+    """Belge / ekran görüntüsü benzeri: beyaz zemin, sık yazı satırları."""
+    import random
+    rnd = random.Random(3)
+    im = Image.new("RGB", size, "white")
+    d = ImageDraw.Draw(im)
+    d.rectangle([0, 0, size[0], 70], fill=(36, 41, 47))                  # üst menü çubuğu
+    for y in range(110, size[1] - 40, 34):
+        x = 60 + rnd.randrange(0, 40)
+        while x < size[0] - 200:
+            w = rnd.randrange(30, 110)
+            d.rectangle([x, y, x + w, y + 14], fill=(40, 40, 40))       # sözcükler
+            x += w + 12
+    return im
+
+
+def test_is_graphic():
+    assert photos.is_graphic(_doc())
+    assert not photos.is_graphic(_photo("#335"))
+    plain = Image.new("RGB", (1600, 900), "white")                   # düz zeminde ürün: fotoğraf sayılır
+    ImageDraw.Draw(plain).ellipse([500, 200, 1100, 700], fill=(120, 90, 200))
+    assert not photos.is_graphic(plain)
+
+
+def test_gather_skip_cover_and_graphics_last():
+    pages = {"https://tr.com/a": HTML.replace("cdn.site.com", "cdn.tr.com")}
+    imgs = {}
+
+    def fake_fetch(url, referer="", timeout=20):
+        if url not in imgs:
+            imgs[url] = _doc() if "rear" in url else _photo("#553", seed=len(imgs) + 10)
+        return imgs[url]
+
+    photos.fetch_html, photos.fetch_image = (lambda u: pages.get(u, "")), fake_fetch
+    got = photos.gather([{"name": "TR Site", "url": "https://tr.com/a", "kind": "media",
+                          "image": "https://cdn.tr.com/feed-card.jpg"}], limit=6, per_source=6, skip_cover={"TR Site"})
+    kinds = [g["kind"] for g in got]
+    assert kinds and set(kinds) == {"body"}                            # besleme/og görseli alınmadı
+    assert got[-1]["graphic"] and not got[0]["graphic"]                # grafik en sona
+
+
+class _App:
+    """Geçici klasörde uygulama; çıkışta tarayıcıyı kapatır (bir sonraki test yeniden açabilsin)."""
+    def __enter__(self):
+        self.tmp = tempfile.TemporaryDirectory()
         raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
-        cfg = Config(raw=raw, root=Path(t), site_url="https://smarity.com.tr")
-        a = appmod.App(cfg)
-        post = {"id": "p1", "slug": "ornek", "title": "Örnek araba tanıtıldı", "summary": "Özet", "category": "teknoloji",
-                "tags": [], "body": "Metin.", "published_at": iso(now_utc()), "image": {"source": "cover"},
-                "sources": [{"name": "Marka", "url": "https://brand.com/press", "kind": "official"}]}
-        a.store.save_post(post)
-        shots = [{"image": _photo("#446", seed=i), "src": f"https://x/{i}.jpg", "credit": "Marka",
-                  "page": "https://brand.com/press", "alt": "", "kind": "og"} for i in range(4)]
+        self.cfg = Config(raw=raw, root=Path(self.tmp.name), site_url="https://smarity.com.tr")
+        self.app = appmod.App(self.cfg)
+        return self.cfg, self.app
+
+    def __exit__(self, *exc):
+        if self.app._vis:
+            self.app._vis.close()
+        self.tmp.cleanup()
+
+
+def _post(**kw):
+    return {"id": "p1", "slug": "ornek", "title": "Örnek araba 15 bin euroya tanıtıldı", "short_title": "Örnek araba tanıtıldı",
+            "summary": "Özet", "category": "teknoloji", "tags": ["Dacia Hipster"], "hero_stat": "15 bin €",
+            "hero_stat_label": "başlangıç fiyatı",
+            "body": "\n\n".join(f"Paragraf {i} metni." for i in range(1, 9)), "published_at": iso(now_utc()),
+            "image": {"source": "cover"}, "sources": [{"name": "Marka", "url": "https://brand.com/press", "kind": "official"}], **kw}
+
+
+def test_attach_cover_slides_inline_and_buttons():
+    with _App() as (cfg, a):
+        a.store.save_post(_post())
+        shots = [{"image": _photo("#446", seed=i), "src": f"https://x/{i}.jpg", "credit": "Marka", "page": "https://brand.com/press",
+                  "alt": "", "kind": "og" if i == 0 else "body", "graphic": False} for i in range(4)]
+        shots.append({"image": _doc(), "src": "https://x/doc.jpg", "credit": "Marka", "page": "https://brand.com/press",
+                      "alt": "", "kind": "body", "graphic": True})
         appmod.photos.gather = lambda *a_, **k: shots
         a.backfill_photos(5)
         p = a.store.load_post("p1")
-        assert p["image"]["source"] == "photo" and len(p["photos"]) == 4
-        assert (cfg.images_dir / "p1.webp").exists() and (cfg.images_dir / "p1-g3.webp").exists()
-        assert (cfg.images_dir / "p1-og.jpg").exists() and Image.open(cfg.images_dir / "p1-og.jpg").size == (1200, 630)
-        # başka fotoğraf: sıra döner, ilk fotoğraf galeriye geçer
-        first_src = p["photos"][0]["src"]
-        a._reorder_photos(p, "post", p["photos"][1:] + p["photos"][:1])
-        assert p["photos"][0]["src"] == "https://x/1.jpg" and p["photos"][-1]["src"] == first_src
-        # site görünümü: yerel dosyalar, kredi
+        assert len(p["photos"]) == 5 and p["photos_v"] == 2
+        assert [r["file"] for r in p["photos"]] == [f"p1-g{i}.webp" for i in range(5)]
+        assert p["image"]["source"] == "photo" and p["image"]["photo"] == "p1-g0.webp"
+        hero = cfg.images_dir / "p1.webp"
+        assert hero.exists() and Image.open(hero).size == (1280, 960)
+        assert Image.open(cfg.images_dir / "p1-og.jpg").size == (1200, 630)
+        # kapak fotoğrafın kendisi değil, tasarım: alt kısım (yazı ve karartma) fotoğraftan farklı
+        ph = Image.open(cfg.images_dir / "p1-g0.webp").convert("L").resize((64, 48))
+        cv = Image.open(hero).convert("L").resize((64, 48))
+        from PIL import ImageChops, ImageStat
+        assert ImageStat.Stat(ImageChops.difference(ph.crop((0, 36, 64, 48)), cv.crop((0, 36, 64, 48)))).mean[0] > 20
+        # site: ilk kare kapak, kaydırınca 2 fotoğraf, kalanlar ve grafik metnin içinde
         from haberbot.site import SiteBuilder
         view = SiteBuilder(cfg)._post_view(p)
-        assert view["photos"][0]["url"] == "/img/p1.webp" and view["photos"][0]["credit"] == "Marka"
-        # site üretilince galeri dosyaları da yayına kopyalanır
+        assert view["cover_photo"]["file"] == "p1-g0.webp"
+        assert [x["file"] for x in view["slides"]] == ["p1-g1.webp", "p1-g2.webp"]
+        assert view["body_html"].count('<figure class="inl') == 2 and 'class="inl graphic"' in view["body_html"]
         SiteBuilder(cfg).build()
-        assert (cfg.out_dir / "img" / "p1-g2.webp").exists()
+        assert (cfg.out_dir / "img" / "p1-g4.webp").exists()
         html = (cfg.out_dir / "haber" / "ornek" / "index.html").read_text(encoding="utf-8")
-        assert 'class="gal' in html and "Görsel: Marka" in html and "/img/p1-g1.webp" in html
-        # eski galeri kopyaları silinir, kaynaktan gösterilir
-        p["published_at"] = "2020-01-01T00:00:00+00:00"
-        a.store.save_post(p)
-        a.prune_gallery()                                   # varsayılan 0: hiçbir şey silinmez
-        assert a.store.load_post("p1")["photos"][1]["file"]
-        a.cfg.raw["images"]["gallery_keep_days"] = 30
-        a.state["last_prune"] = None
-        a.prune_gallery()
-        p = a.store.load_post("p1")
-        assert p["photos"][1]["file"] is None and not (cfg.images_dir / "p1-g1.webp").exists()
+        assert 'class="gal-slide cover"' in html and "/img/p1-g3.webp" in html and "Görsel: Marka" in html
+        assert html.index("/img/p1-g1.webp") < html.index('class="art-body"') < html.index("/img/p1-g3.webp")
+        # düğmeler: başka foto, yazılı kapak, fotoğrafsız
+        assert [b["callback_data"][0] for b in a._visual_buttons(p)] == ["g", "v", "n"]
+        a._on_button("g", "p1")                                # sonraki fotoğraf kapak olur
+        p = a.store.load_post("p1")
+        assert p["image"]["photo"] == "p1-g0.webp" and p["photos"][0]["src"] == "https://x/1.jpg"
+        assert p["photos"][3]["src"] == "https://x/0.jpg" and p["photos"][4]["graphic"]
+        a._on_button("v", "p1")                                # yazılı kapak: fotoğraflar kalır
+        p = a.store.load_post("p1")
+        assert p["image"]["source"] == "cover" and len(p["photos"]) == 5 and p["cover_mode"] == "type"
+        assert a._visual_buttons(p)[0]["text"].endswith("Fotoğraflı kapak")
         view = SiteBuilder(cfg)._post_view(p)
-        assert view["photos"][1]["remote"] and view["photos"][1]["url"].startswith("https://x/")
-        assert [b["callback_data"][0] for b in a._visual_buttons(p)] == ["g", "n"]
-        # fotoğrafsız
-        a._drop_photos(p, "post")
+        assert view["cover_photo"] is None and len(view["slides"]) >= 2
+        a._on_button("g", "p1")                                # fotoğraflı kapağa dönüş
+        assert a.store.load_post("p1")["image"]["source"] == "photo"
+        a._on_button("n", "p1")                                # fotoğrafsız
+        p = a.store.load_post("p1")
         assert "photos" not in p and a._visual_buttons(p)[0]["callback_data"].startswith("v:")
+        assert not list(cfg.images_dir.glob("p1-g*.webp"))
+
+
+def test_small_or_graphic_photos_get_type_cover():
+    with _App() as (cfg, a):
+        a.store.save_post(_post())
+        shots = [{"image": _photo("#446", size=(720, 480), seed=1), "src": "https://x/s.jpg", "credit": "Site", "page": "https://s",
+                  "alt": "", "kind": "body", "graphic": False},
+                 {"image": _doc(), "src": "https://x/d.jpg", "credit": "Site", "page": "https://s", "alt": "", "kind": "og", "graphic": True}]
+        appmod.photos.gather = lambda *a_, **k: shots
+        a.backfill_photos(5)
+        p = a.store.load_post("p1")
+        assert p["image"]["source"] == "cover" and len(p["photos"]) == 2    # küçük fotoğraf ve grafik kapak olmaz
+        from haberbot.site import SiteBuilder
+        view = SiteBuilder(cfg)._post_view(p)
+        assert [x["file"] for x in view["slides"]] == ["p1-g0.webp"] and 'class="inl graphic"' in view["body_html"]
+
+
+def test_migrate_old_layout():
+    with _App() as (cfg, a):
+        cfg.images_dir.mkdir(parents=True, exist_ok=True)
+        # eski düzen: ilk fotoğraf {id}.webp; DonanımHaber'in ilk fotoğrafı yazılı paylaşım görseli
+        _photo("#a55", seed=1).save(cfg.images_dir / "p1.webp", "WEBP")
+        _doc().save(cfg.images_dir / "p1-g1.webp", "WEBP")
+        _photo("#5a5", seed=2).save(cfg.images_dir / "p1-g2.webp", "WEBP")
+        _photo("#55a", seed=3).save(cfg.images_dir / "p1-g3.webp", "WEBP")
+        recs = [{"file": "p1.webp", "src": "https://log/og.jpg", "credit": "LOG", "page": "https://log", "w": 1600, "h": 900},
+                {"file": "p1-g1.webp", "src": "https://log/doc.jpg", "credit": "LOG", "page": "https://log", "w": 1600, "h": 900},
+                {"file": "p1-g2.webp", "src": "https://dh/card.jpg", "credit": "DonanımHaber", "page": "https://dh", "w": 1600, "h": 900},
+                {"file": "p1-g3.webp", "src": "https://dh/body.jpg", "credit": "DonanımHaber", "page": "https://dh", "w": 1600, "h": 900}]
+        a.store.save_post(_post(photos=recs, image={"source": "photo", "credit": "LOG"}))
+        a.upgrade_photos()
+        p = a.store.load_post("p1")
+        assert p["photos_v"] == 2
+        assert [r["src"] for r in p["photos"]] == ["https://log/og.jpg", "https://dh/body.jpg", "https://log/doc.jpg"]
+        assert [r["graphic"] for r in p["photos"]] == [False, False, True]
+        assert sorted(f.name for f in cfg.images_dir.glob("p1-g*.webp")) == ["p1-g0.webp", "p1-g1.webp", "p1-g2.webp"]
+        assert p["image"]["source"] == "photo" and p["image"]["photo"] == "p1-g0.webp"
+        assert (cfg.images_dir / "p1.webp").exists() and (cfg.images_dir / "p1-og.jpg").exists()
+        a.upgrade_photos()                                    # ikinci kez: dokunmaz
+        assert a.store.load_post("p1")["photos"] == p["photos"]
 
 
@@@SM@@@ FILE templates/cards/photo.html
{# Fotoğraflı kapak: gerçek fotoğraf + bizim tasarım dilimiz (kategori renginde ışık, dev rakam / isim / manşet).
   Değişkenler: photo (dosya adresi), focus (object-position), layout (sayi|isim|manset), pal, stat, stat_label, word,
   headline, kicker, brand (bool), credit, W, H #}
<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<style>
@font-face { font-family: "IS"; src: url("{{ font_dir }}/InstrumentSans-Regular.ttf"); font-weight: 400; }
@font-face { font-family: "IS"; src: url("{{ font_dir }}/InstrumentSans-Bold.ttf"); font-weight: 700; }
:root {
  --u: {{ [W, H]|min / 100 }}px;
  --c1: {{ pal[0] }}; --c2: {{ pal[1] }}; --c3: {{ pal[2] }}; --c4: {{ pal[3] }};
  --shade: 7, 8, 13;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: {{ W }}px; height: {{ H }}px; overflow: hidden; }
body { font-family: "IS", system-ui, sans-serif; background: #07080D; color: #fff; -webkit-font-smoothing: antialiased;
  position: relative; isolation: isolate; }
.photo { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: {{ focus }}; z-index: -4; }
.scrim { position: absolute; inset: 0; z-index: -3;
  background: linear-gradient(to top, rgba(var(--shade), .95) 0%, rgba(var(--shade), .80) 22%, rgba(var(--shade), .42) 44%, rgba(var(--shade), 0) 64%); }
.l-manset .scrim { background: linear-gradient(to top, rgba(var(--shade), .96) 0%, rgba(var(--shade), .84) 28%, rgba(var(--shade), .45) 52%, rgba(var(--shade), 0) 72%); }
.top { position: absolute; inset: 0 0 auto; height: 30%; z-index: -3; background: linear-gradient(to bottom, rgba(var(--shade), .55), rgba(var(--shade), 0)); }
.tint { position: absolute; z-index: -2; border-radius: 50%; mix-blend-mode: screen; filter: blur(calc(var(--u) * 9)); }
.tint.a { left: -18%; bottom: -34%; width: 72%; height: 78%; background: var(--c2); opacity: .55; }
.tint.b { right: -20%; bottom: -40%; width: 60%; height: 60%; background: var(--c3); opacity: .35; }
.grain { position: absolute; inset: 0; z-index: -1; opacity: .08; mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='220' height='220'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>"); }

.txt { position: absolute; left: calc(var(--u) * 6); right: calc(var(--u) * 6); bottom: calc(var(--u) * 8.5);
  display: flex; flex-direction: column; align-items: flex-start; gap: calc(var(--u) * 1.6); }
.bar { width: calc(var(--u) * 7); height: calc(var(--u) * .9); border-radius: 99px;
  background: linear-gradient(90deg, var(--c1), var(--c2) 55%, var(--c4)); box-shadow: 0 0 calc(var(--u) * 3) color-mix(in srgb, var(--c2) 70%, transparent); }
.grad { background: linear-gradient(100deg, #FFFFFF 0%, var(--c1) 36%, color-mix(in oklab, var(--c2) 62%, #fff) 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent; }
.num { font-weight: 700; font-size: calc(var(--u) * 25); line-height: .9; letter-spacing: -.06em; white-space: nowrap;
  padding: 0 .04em .06em 0; max-width: 100%; }
.lab { font-weight: 700; font-size: calc(var(--u) * 4.4); letter-spacing: -.02em; color: rgba(255,255,255,.84); max-width: 26ch; text-wrap: balance; }
.word { font-weight: 700; font-size: calc(var(--u) * 15.5); line-height: .96; letter-spacing: -.055em; text-wrap: balance; max-width: 100%;
  padding-bottom: .04em; }
.head { font-weight: 700; font-size: calc(var(--u) * 7.4); line-height: 1.03; letter-spacing: -.04em; text-wrap: balance; max-width: 100%;
  text-shadow: 0 calc(var(--u) * .3) calc(var(--u) * 3) rgba(0,0,0,.35); }
.head em { font-style: normal; }
.head .grad-text { background: linear-gradient(100deg, var(--c1) 0%, color-mix(in oklab, var(--c2) 55%, #fff) 60%, var(--c4) 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent; text-shadow: none; }

.kicker { position: absolute; left: calc(var(--u) * 6); top: calc(var(--u) * 5.5); display: inline-flex; align-items: center; gap: calc(var(--u) * 1.2);
  padding: calc(var(--u) * 1.1) calc(var(--u) * 2.2); border-radius: 999px; font-weight: 700; font-size: calc(var(--u) * 3.1); letter-spacing: -.01em;
  background: rgba(12,12,18,.42); border: 1px solid rgba(255,255,255,.2); -webkit-backdrop-filter: blur(18px); backdrop-filter: blur(18px); }
.kicker i { width: calc(var(--u) * 1.6); height: calc(var(--u) * 1.6); border-radius: 50%; background: linear-gradient(135deg, var(--c1), var(--c2)); }
.brand { position: absolute; right: calc(var(--u) * 6); top: calc(var(--u) * 5.6); height: calc(var(--u) * 5); width: calc(var(--u) * 18.7);
  background: url("{{ logo_light_uri }}") right center / contain no-repeat; }
.credit { position: absolute; right: calc(var(--u) * 6); bottom: calc(var(--u) * 3); font-size: calc(var(--u) * 2.1); font-weight: 400;
  color: rgba(255,255,255,.66); letter-spacing: .01em; }
</style></head>
<body class="l-{{ layout }}">
<img class="photo" src="{{ photo }}" alt="">
<div class="scrim"></div>
{% if kicker or brand %}<div class="top"></div>{% endif %}
<div class="tint a"></div><div class="tint b"></div>
<div class="grain"></div>

{% if kicker %}<div class="kicker"><i></i>{{ kicker }}</div>{% endif %}
{% if brand and logo_light_uri %}<div class="brand" role="img" aria-label="{{ brand_name }}"></div>{% endif %}

<div class="txt">
  <span class="bar"></span>
  {% if layout == 'sayi' %}
    {% if stat_label %}<div class="lab">{{ stat_label }}</div>{% endif %}
    <div class="num grad" data-fitw>{{ stat }}</div>
  {% elif layout == 'isim' %}
    <div class="word grad" data-fitw data-maxh="{{ (H * 0.36)|int }}">{{ word }}</div>
  {% else %}
    <div class="head" data-maxh="{{ (H * 0.34)|int }}">{{ headline|safe }}</div>
  {% endif %}
</div>
{% if credit %}<div class="credit">Görsel: {{ credit }}</div>{% endif %}

<script>
function fitW(el){ const max = el.parentElement.clientWidth - 4; const r = document.createRange(); r.selectNodeContents(el);
  let fs = parseFloat(getComputedStyle(el).fontSize); while (r.getBoundingClientRect().width > max && fs > 20) { fs -= 3; el.style.fontSize = fs + "px"; } }
function fitH(el, max){ let fs = parseFloat(getComputedStyle(el).fontSize); while (el.scrollHeight > max && fs > 18) { fs -= 2; el.style.fontSize = fs + "px"; } }
document.fonts.ready.then(function(){
  document.querySelectorAll("[data-fitw]").forEach(fitW);
  document.querySelectorAll("[data-maxh]").forEach(function(e){ fitH(e, +e.dataset.maxh); });
  var im = document.querySelector(".photo");
  (im.complete ? Promise.resolve() : new Promise(function(r){ im.onload = im.onerror = r; })).then(function(){ window.__ready = true; });
});
</script>
</body></html>
@@@SM@@@ SHA
c7cfd88c89620629f762defff0bcc09a6a275e2b67c5ace43829132187ac0313 config.yaml
6fa247854eacd1e2fcc3ea75508bca9b8b4287408e2ae380dfb0ffd482f15138 haberbot/app.py
38129e765a6d2664fd1198c2ab56cc8bb46b8da663ec41b1b14c22b123133c8d haberbot/covers.py
e8c829d0f36d76ea2fc5084fa7bf4fd005da6807304ed6fa7b976f5581f63217 haberbot/photos.py
482390e3f743c6529b2bcf1fe93dfaf9eb8cd6054eb63216cd69bf4f926825e7 haberbot/site.py
ed8de2c72a02f1e2690ec6578376ee73a8f17c09d6e82924d3ddae1695fae922 haberbot/visuals.py
b05534f725153d3f5c7f1adf8716f28e885dd39c5c38e00689dac18253d227f3 static/style.css
90a5002d8ab1db221cac35cfd21e3adf7ef654b69435d962a93ddf2e6d456cb0 templates/article.html
80ec61aff874be70899454adc0285406fb260a15e4dad6e8ad6cc447d0defd42 tests/test_photos.py
5cb2e5335cb7c4d2dd39743eeb3c578cdcfb9ca849601e19db4a5de9eb1312b6 templates/cards/photo.html
