SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -16,5 +16,5 @@ from .store import Store
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "7"
+ASSET_V = "8"
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
 H2_RE = re.compile(r"<h[1-3]>(.*?)</h[1-3]>", re.S)
@@ -164,5 +164,5 @@ class SiteBuilder:
             "cover_image": (p.get("image") or {}).get("source") == "cover",
             "stat_on_cover": (p.get("image") or {}).get("source") == "cover" and (p.get("image") or {}).get("layout") == "sayi",
-            "img_alt": clip(p.get("image_alt") or f"{short}: habere ait temsili görsel", 125),
+            "img_alt": clip(p.get("image_alt") or f"{short}: habere ait görsel", 125),
             "seo_title": seo_title,
             "meta_description": clip(meta, 158),
@@ -190,7 +190,27 @@ class SiteBuilder:
                     for m in re.finditer(r'<h2 id="([^"]+)">(.*?)</h2>', body_html)],
             "key_points": [x for x in (p.get("carousel_points") or []) if x][:4],
+            "photos": self._photos(p, short),
+            "has_photo": (p.get("image") or {}).get("source") == "photo",
             "updated_str": tr_date(p.get("updated_at"), cfg.tz) if p.get("updated_at") else "",
         }
 
+    def _photos(self, p: dict, short: str) -> list[dict]:
+        """Haberin gerçek fotoğrafları (ilki ana görsel). Yerel kopyası silinmiş galeri fotoğrafı kaynaktan gösterilir."""
+        cfg, b = self.cfg, self.base
+        out = []
+        for i, r in enumerate(p.get("photos") or []):
+            local = bool(r.get("file")) and (cfg.images_dir / r["file"]).exists()
+            if not local and (i == 0 or not r.get("src")):
+                continue
+            out.append({
+                "url": f"{b}/img/{r['file']}" if local else r["src"],
+                "remote": not local,
+                "credit": r.get("credit") or "",
+                "page": r.get("page") or "",
+                "alt": clip(r.get("alt") or (p.get("image_alt") if i == 0 else "") or f"{short} ({i + 1})", 125),
+                "w": r.get("w") or 1600, "h": r.get("h") or 900,
+            })
+        return out
+
     def _write(self, rel: str, content: str) -> None:
         path = self.cfg.out_dir / rel
@@ -277,5 +297,7 @@ class SiteBuilder:
         (out / "img").mkdir()
         for p in posts:
-            for name in (f"{p['id']}.webp", f"{p['id']}.jpg", f"{p['id']}-og.jpg"):
+            names = [f"{p['id']}.webp", f"{p['id']}.jpg", f"{p['id']}-og.jpg"]
+            names += [ph["url"].rsplit("/", 1)[-1] for ph in p.get("photos") or [] if not ph.get("remote")]
+            for name in dict.fromkeys(names):
                 src = cfg.images_dir / name
                 if src.exists():
--- a/haberbot/extract.py
+++ b/haberbot/extract.py
@@ -48,15 +48,28 @@ def _fallback_extract(html: str) -> str:
 
 
-def full_text(url: str, max_chars: int = 7000) -> str:
+_html_cache: dict[str, str] = {}
+
+
+def fetch_html(url: str) -> str:
+    """Sayfanın HTML'i (robots.txt'e uyarak; aynı çalışmada ikinci kez indirilmez)."""
+    if url in _html_cache:
+        return _html_cache[url]
+    html = ""
     try:
         if not _allowed(url):
-            log.info("robots.txt izin vermiyor, tam metin atlandı: %s", url)
-            return ""
-        r = requests.get(url, headers={"User-Agent": UA, "Accept": "text/html"}, timeout=15)
-        if r.status_code >= 400 or "html" not in r.headers.get("content-type", "html"):
-            return ""
-        html = r.text[:3_000_000]
+            log.info("robots.txt izin vermiyor, sayfa okunmadı: %s", url)
+        else:
+            r = requests.get(url, headers={"User-Agent": UA, "Accept": "text/html"}, timeout=15)
+            if r.status_code < 400 and "html" in r.headers.get("content-type", "html"):
+                html = r.text[:3_000_000]
     except requests.RequestException as e:
-        log.info("Tam metin okunamadı (%s): %s", type(e).__name__, url)
+        log.info("Sayfa okunamadı (%s): %s", type(e).__name__, url)
+    _html_cache[url] = html
+    return html
+
+
+def full_text(url: str, max_chars: int = 7000) -> str:
+    html = fetch_html(url)
+    if not html:
         return ""
     text = ""
--- a/haberbot/images.py
+++ b/haberbot/images.py
@@ -2,6 +2,6 @@
 bu dosya yalnızca tarayıcı hiç açılamazsa devreye girer.
 
-Kaynak sitelerin fotoğrafları KULLANILMAZ (telif). Her haber için markaya ait
-tipografik bir kapak üretilir.
+Gerçek fotoğraflar photos.py ile kaynaklardan alınır; bu dosya yalnızca fotoğraf
+bulunamadığında kullanılan markaya ait tipografik kapağın son yedeğidir.
 """
 from __future__ import annotations
--- a/haberbot/sources.py
+++ b/haberbot/sources.py
@@ -23,5 +23,34 @@ NS = {
     "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
     "rss1": "http://purl.org/rss/1.0/",
+    "media": "http://search.yahoo.com/mrss/",
 }
+IMG_IN_HTML = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.I)
+
+
+def _feed_image(el, html_parts: list[str]) -> str:
+    """Besleme öğesinin görseli: media:content / media:thumbnail / enclosure ya da içerikteki ilk <img>."""
+    best, bw = "", -1
+    for m in el.iter("{http://search.yahoo.com/mrss/}content", "{http://search.yahoo.com/mrss/}thumbnail"):
+        url = m.get("url") or ""
+        typ = (m.get("type") or m.get("medium") or "image").lower()
+        if not url or ("image" not in typ and not re.search(r"\.(jpe?g|png|webp|avif)(\?|$)", url, re.I)):
+            continue
+        try:
+            w = int(m.get("width") or 0)
+        except ValueError:
+            w = 0
+        if w > bw:
+            best, bw = url, w
+    if best:
+        return best
+    for enc in list(el.iter("enclosure")) + [l for l in el.iter("{http://www.w3.org/2005/Atom}link") if l.get("rel") == "enclosure"]:
+        url = enc.get("url") or enc.get("href") or ""
+        if url and (enc.get("type") or "").lower().startswith("image"):
+            return url
+    for h in html_parts:
+        m = IMG_IN_HTML.search(h or "")
+        if m:
+            return m.group(1)
+    return ""
 
 
@@ -71,4 +100,5 @@ def parse_feed(xml_bytes: bytes) -> list[dict]:
                 "summary": strip_html(summary),
                 "published": _parse_date(_text(e, "atom:published") or _text(e, "atom:updated")),
+                "image": _feed_image(e, [_text(e, "atom:content"), _text(e, "atom:summary")]),
             })
         return out
@@ -93,4 +123,5 @@ def parse_feed(xml_bytes: bytes) -> list[dict]:
             "published": _parse_date(_text(it, "pubDate") or _text(it, "dc:date")),
             "comments": comments,
+            "image": _feed_image(it, [_text(it, "content:encoded"), _text(it, "description")]),
         })
     return out
@@ -191,4 +222,5 @@ def fetch_all(cfg: Config, store) -> list[dict]:
                     "published": iso(e["published"]) if e.get("published") else None,
                     "html_source": src.get("type") == "html",
+                    "image": (e.get("image") or "").strip()[:600] or None,
                 })
             log.info("Kaynak %-22s %3d öğe", src["name"], len(entries))
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -11,5 +11,5 @@ from urllib.parse import urlsplit
 import requests
 
-from . import policy
+from . import photos, policy
 from .config import CATEGORIES, DEFAULT_CATEGORY, Config, category_label, indexnow_key
 from .covers import COVER_VERSION
@@ -30,4 +30,6 @@ SLOW_ACTIONS = {
     "p": ("⏳ Yayınlanıyor…", "✅ Yayınlandı"),
     "v": ("⏳ Yeni görsel hazırlanıyor…", "🎨 Yeni görsel hazır"),
+    "g": ("⏳ Fotoğraf değiştiriliyor…", "🖼 Fotoğraf değişti"),
+    "n": ("⏳ Fotoğraflar kaldırılıyor…", "🚫 Fotoğraflar kaldırıldı"),
     "w": ("⏳ Yeniden yazılıyor…", "🔁 Yeniden yazıldı"),
     "s": ("⏳ Görseller hazırlanıyor…", "📱 Gönderildi"),
@@ -303,5 +305,6 @@ class App:
     def _source_entry(it: dict) -> dict:
         return {"name": it["credit"], "url": it["url"], "title": it["title"], "kind": it["kind"],
-                "via": it.get("via"), "via_url": it.get("via_url"), "published": it.get("published")}
+                "via": it.get("via"), "via_url": it.get("via_url"), "published": it.get("published"),
+                "image": it.get("image")}
 
     # ── 2) YAZIM ────────────────────────────────────────────
@@ -364,6 +367,7 @@ class App:
             "telegram": {},
         }
-        d["image"] = self.vis.make_hero(d, st.draft_image(did))
-        self._image_feedback(d["image"])
+        if not self._attach_photos(d, draft=True):
+            d["image"] = self.vis.make_hero(d, st.draft_image(did))
+            self._image_feedback(d["image"])
         st.bump(self.today(), "drafts")
         decision, reason = policy.decide(cfg, self.state, self.stats, d)
@@ -422,5 +426,5 @@ class App:
         elif not st.post_image(d["id"]).exists():
             post["image"] = self.vis.make_hero(post, st.post_image(d["id"]))
-        self.vis.render_card(post, "og", st.post_image(d["id"]), st.post_og(d["id"]))
+        self._make_og(post)
         st.save_post(post)
         st.draft_path(d["id"]).unlink(missing_ok=True)
@@ -467,6 +471,5 @@ class App:
                    {"text": "❌ Reddet", "callback_data": f"r:{did}"}],
                   [{"text": "📄 Tam metin", "callback_data": f"f:{did}"},
-                   {"text": "🔁 Yeniden yaz", "callback_data": f"w:{did}"},
-                   {"text": "🎨 Yeni görsel", "callback_data": f"v:{did}"}]]
+                   {"text": "🔁 Yeniden yaz", "callback_data": f"w:{did}"}] + self._visual_buttons(d)]
             if src:
                 kb.append([{"text": "🔗 Kaynağı aç", "url": src}])
@@ -475,7 +478,6 @@ class App:
             return [[{"text": "🔗 Haberi aç", "url": self.cfg.post_url(d["slug"])},
                      {"text": "🗑 Kaldır", "callback_data": f"d:{did}"}],
-                    [{"text": "📄 Tam metin", "callback_data": f"f:{did}"},
-                     {"text": "🎨 Yeni görsel", "callback_data": f"v:{did}"},
-                     {"text": "📱 Instagram", "callback_data": f"s:{did}"}]]
+                    [{"text": "📄 Tam metin", "callback_data": f"f:{did}"}] + self._visual_buttons(d)
+                    + [{"text": "📱 Instagram", "callback_data": f"s:{did}"}]]
         if kind == "rejected":
             return [[{"text": "↩️ Geri al", "callback_data": f"u:{did}"}]]
@@ -487,5 +489,5 @@ class App:
         st = self.store
         try:
-            img = self._card(d, "post")
+            img = self._hero(d) if d.get("photos") and self._hero(d).exists() else self._card(d, "post")
         except Exception as e:  # noqa: BLE001
             log.warning("Önizleme kartı üretilemedi: %s", e)
@@ -703,4 +705,29 @@ class App:
             self._rewrite(d, None, where, visual_only="")
             return "🎨 Yeni görsel hazır"
+        if action in ("g", "n"):
+            if where == "draft" and d.get("status") != "pending":
+                return "Bu taslak kapanmış."
+            if not d.get("photos"):
+                return "Bu haberde fotoğraf yok."
+            if action == "g":
+                local = [r for r in d["photos"] if r.get("file")]
+                if len(local) < 2:
+                    return "Başka fotoğraf yok."
+                self._reorder_photos(d, where, local[1:] + local[:1] + [r for r in d["photos"] if not r.get("file")])
+                msg = "🖼 Fotoğraf değişti"
+            else:
+                self._drop_photos(d, where)
+                d["image"] = self.vis.make_hero(d, self._hero(d))
+                msg = "🚫 Fotoğraflar kaldırıldı"
+            kind = "pending" if where == "draft" else ("auto" if d.get("publish_mode") == "auto" else "published")
+            if where == "draft":
+                st.save_draft(d)
+            else:
+                d["updated_at"] = iso(now_utc())
+                self._make_og(d)
+                st.save_post(d)
+            self._update_preview(d, "rewritten")
+            self._send_preview(d, kind)
+            return msg
         if action == "s":
             if where != "post":
@@ -770,4 +797,6 @@ class App:
             d["rewrites"] = (d.get("rewrites") or 0) + 1
             old_kind = "pending" if where == "draft" else ("auto" if d.get("publish_mode") == "auto" else "published")
+            if d.get("photos"):
+                self._drop_photos(d, where)
             d["image"] = self.vis.make_hero(d, self._hero(d))
             self._image_feedback(d["image"])
@@ -778,5 +807,5 @@ class App:
             else:
                 d["updated_at"] = iso(now_utc())
-                self.vis.render_card(d, "og", st.post_image(d["id"]), st.post_og(d["id"]))
+                self._make_og(d)
                 st.save_post(d)
                 self._update_preview(d, "rewritten")
@@ -798,5 +827,5 @@ class App:
         else:  # yayındaki haber: yerinde güncelle (adres değişmez)
             d["updated_at"] = iso(now_utc())
-            self.vis.render_card(d, "og", st.post_image(d["id"]), st.post_og(d["id"]))
+            self._make_og(d)
             st.save_post(d)
             self._update_preview(d, "rewritten")
@@ -963,9 +992,10 @@ class App:
             return
         todo = [p for p in self.store.posts()
-                if (p.get("image") or {}).get("source") != "ai" and (p.get("image") or {}).get("cover_v") != COVER_VERSION][:limit]
+                if (p.get("image") or {}).get("source") in ("cover", "fallback", None)
+                and (p.get("image") or {}).get("cover_v") != COVER_VERSION and not p.get("photos")][:limit]
         for p in todo:
             try:
                 p["image"] = {**self.vis.make_hero(p, self.store.post_image(p["id"])), "cover_v": COVER_VERSION}
-                self.vis.render_card(p, "og", self.store.post_image(p["id"]), self.store.post_og(p["id"]))
+                self._make_og(p)
                 self.store.save_post(p)
             except Exception as e:  # noqa: BLE001
@@ -1258,4 +1288,124 @@ class App:
         return "\n".join(lines)
 
+    # ── gerçek fotoğraflar ──────────────────────────────────
+    def _visual_buttons(self, d: dict) -> list[dict]:
+        did = d["id"]
+        if d.get("photos"):
+            out = [{"text": "🚫 Fotoğrafsız", "callback_data": f"n:{did}"}]
+            if len(d["photos"]) > 1:
+                out.insert(0, {"text": "🖼 Başka foto", "callback_data": f"g:{did}"})
+            return out
+        return [{"text": "🎨 Yeni görsel", "callback_data": f"v:{did}"}]
+
+    def _photo_dir(self, draft: bool):
+        return self.cfg.drafts_dir if draft else self.cfg.images_dir
+
+    def _attach_photos(self, d: dict, draft: bool) -> bool:
+        """Kaynaklardan gerçek fotoğrafları al: ilki ana görsel, diğerleri galeri. Bulunamazsa False."""
+        cfg = self.cfg
+        if not cfg.get("images", "photos", True) or cfg.mock or cfg.fixtures_dir:
+            return False
+        try:
+            got = photos.gather(d.get("sources") or [], limit=int(cfg.get("images", "photo_limit", 6) or 6))
+        except Exception as e:  # noqa: BLE001
+            log.warning("Fotoğraflar alınamadı (%s): %s", d.get("id"), e)
+            return False
+        if not got:
+            return False
+        folder = self._photo_dir(draft)
+        for f in self.store.gallery_files(d["id"], draft):
+            f.unlink(missing_ok=True)
+        recs = []
+        for i, p in enumerate(got):
+            name = f"{d['id']}.webp" if i == 0 else f"{d['id']}-g{i}.webp"
+            w, h = photos.save_webp(p["image"], folder / name, 1600 if i == 0 else 1280, 80 if i == 0 else 74)
+            recs.append({"file": name, "src": p["src"], "credit": p["credit"], "page": p["page"],
+                         "alt": p["alt"], "w": w, "h": h})
+        d["photos"] = recs
+        d["image"] = {"source": "photo", "credit": recs[0]["credit"], "page": recs[0]["page"], "src": recs[0]["src"]}
+        if not draft:
+            self._make_og(d)
+        return True
+
+    def _reorder_photos(self, d: dict, where: str, order: list[dict]) -> None:
+        """Fotoğraf sırasını değiştir (ilk sıradaki ana görsel olur); dosya adları sıraya göre yeniden verilir."""
+        from PIL import Image
+        draft = where == "draft"
+        folder = self._photo_dir(draft)
+        loaded = []
+        for rec in order:
+            f = folder / rec["file"] if rec.get("file") else None
+            loaded.append((rec, Image.open(f).convert("RGB") if f and f.exists() else None))
+        for f in self.store.gallery_files(d["id"], draft):
+            f.unlink(missing_ok=True)
+        recs = []
+        for i, (rec, im) in enumerate(loaded):
+            name = f"{d['id']}.webp" if i == 0 else f"{d['id']}-g{i}.webp"
+            rec = dict(rec)
+            if im is not None:
+                photos.save_webp(im, folder / name, 1600, 82)
+                rec["file"] = name
+            else:
+                rec["file"] = None
+            recs.append(rec)
+        d["photos"] = [r for r in recs if r.get("file") or r.get("src")]
+        first = d["photos"][0]
+        d["image"] = {"source": "photo", "credit": first["credit"], "page": first["page"], "src": first["src"]}
+
+    def _drop_photos(self, d: dict, where: str) -> None:
+        for f in self.store.gallery_files(d["id"], where == "draft"):
+            f.unlink(missing_ok=True)
+        d.pop("photos", None)
+        d["photos_removed"] = True
+        d["image"] = {"source": "cover"}
+
+    def _make_og(self, p: dict) -> None:
+        """Paylaşım görseli: fotoğraf varsa fotoğrafın kırpımı, yoksa marka kartı."""
+        st = self.store
+        hero = st.post_image(p["id"])
+        if (p.get("image") or {}).get("source") == "photo" and hero.exists():
+            from PIL import Image
+            photos.og_crop(Image.open(hero).convert("RGB"), st.post_og(p["id"]))
+        else:
+            self.vis.render_card(p, "og", hero, st.post_og(p["id"]))
+
+    def backfill_photos(self, limit: int = 5) -> None:
+        """Eski haberlere gerçek fotoğraf ekle (her turda birkaç tane; bulunamayanlar 3 gün sonra tekrar denenir)."""
+        if not self.cfg.get("images", "photos", True) or self.cfg.mock or self.cfg.fixtures_dir:
+            return
+        todo = [p for p in self.store.posts()
+                if not p.get("photos") and not p.get("photos_removed") and (p.get("image") or {}).get("source") != "ai"
+                and hours_since(p.get("photos_tried")) > 72][:limit]
+        for p in todo:
+            p["photos_tried"] = iso(now_utc())
+            if self._attach_photos(p, draft=False):
+                p["updated_at"] = p.get("updated_at") or p.get("published_at")
+                log.info("Fotoğraf eklendi: %s (%d)", p["id"], len(p["photos"]))
+            self.store.save_post(p)
+
+    def prune_gallery(self) -> None:
+        """Yer kazanmak için eski haberlerin galeri kopyalarını sil (ana görsel kalır, galeri kaynaktan gösterilir)."""
+        if self.state.get("last_prune") == self.today():
+            return
+        self.state["last_prune"] = self.today()
+        keep = float(self.cfg.get("images", "gallery_keep_days", 0) or 0)
+        if keep <= 0:  # 0 = hiçbir fotoğraf silinmez
+            return
+        n = 0
+        for p in self.store.posts():
+            if hours_since(p.get("published_at")) < keep * 24 or not p.get("photos"):
+                continue
+            changed = False
+            for rec in p["photos"][1:]:
+                if rec.get("file"):
+                    (self.cfg.images_dir / rec["file"]).unlink(missing_ok=True)
+                    rec["file"] = None
+                    changed = True
+                    n += 1
+            if changed:
+                self.store.save_post(p)
+        if n:
+            log.info("Eski galeri kopyaları silindi: %d", n)
+
     # ── tek çalışma ─────────────────────────────────────────
     def run(self) -> bool:
@@ -1284,4 +1434,9 @@ class App:
         if not self.state.get("paused"):
             self.backfill_seo()
+            try:
+                self.backfill_photos(int(self.cfg.get("images", "photo_backfill_per_run", 5) or 0))
+                self.prune_gallery()
+            except Exception as e:  # noqa: BLE001
+                log.exception("Fotoğraf işlemi hatası: %s", e)
         try:
             self.ig_tick()
--- a/haberbot/store.py
+++ b/haberbot/store.py
@@ -93,4 +93,9 @@ class Store:
         return self.cfg.drafts_dir / f"{did}.webp"
 
+    def gallery_files(self, did: str, draft: bool) -> list[Path]:
+        """Galeri fotoğrafları: {id}-g1.webp, {id}-g2.webp …"""
+        folder = self.cfg.drafts_dir if draft else self.cfg.images_dir
+        return sorted(folder.glob(f"{did}-g*.webp"), key=lambda p: int(p.stem.rsplit("-g", 1)[-1] or 0))
+
     def load_draft(self, did: str) -> dict | None:
         return read_json(self.draft_path(did), None)
@@ -121,4 +126,6 @@ class Store:
         self.draft_path(d["id"]).unlink(missing_ok=True)
         self.draft_image(d["id"]).unlink(missing_ok=True)
+        for f in self.gallery_files(d["id"], draft=True):
+            f.unlink(missing_ok=True)
 
     # ── yayınlar ─────────────────────────────────────────────
@@ -154,7 +161,9 @@ class Store:
     def move_image_to_post(self, did: str) -> None:
         src = self.draft_image(did)
+        self.cfg.images_dir.mkdir(parents=True, exist_ok=True)
         if src.exists():
-            self.cfg.images_dir.mkdir(parents=True, exist_ok=True)
             shutil.move(str(src), self.post_image(did))
+        for f in self.gallery_files(did, draft=True):
+            shutil.move(str(f), self.cfg.images_dir / f.name)
 
     def delete_post(self, pid: str) -> dict | None:
@@ -165,4 +174,6 @@ class Store:
         self.post_image(pid).unlink(missing_ok=True)
         self.post_og(pid).unlink(missing_ok=True)
+        for f in self.gallery_files(pid, draft=False):
+            f.unlink(missing_ok=True)
         self.site_dirty = True
         return d
--- a/templates/about.html
+++ b/templates/about.html
@@ -16,5 +16,6 @@
     <li><strong>Kopyalama yok.</strong> Kaynak metinler çevrilip aktarılmaz; bilgiler özetlenip kendi cümlelerimizle yazılır.</li>
     <li><strong>Uydurma yok.</strong> Kaynaklarda olmayan rakam, tarih, alıntı ya da iddia eklenmez. Doğrulanmamış bilgiler kaynağına atfedilir.</li>
-    <li><strong>Temsili görseller.</strong> Kaynak sitelerin fotoğrafları kullanılmaz. Haber görselleri habere özel tipografik kapaklar ya da yapay zeka ile üretilmiş temsili görsellerdir; gerçek kişileri, ürünleri ya da olayları göstermez.</li>
+    <li><strong>Fotoğraflar kaynağıyla.</strong> Haberlerdeki fotoğraflar, öncelikle ilgili şirketin basın için yayımladığı görsellerdir; bunlar yoksa haberin kaynağında yayımlanan görseller kullanılır. Her fotoğrafın altında kaynağı ve bağlantısı yer alır. Fotoğraf bulunamayan haberlerde habere özel tipografik kapak kullanılır.</li>
+    <li><strong>Kaldırma talepleri.</strong> Bir fotoğrafın ya da metnin hak sahibiyseniz ve kaldırılmasını istiyorsanız {% if site.contact_email %}<strong>{{ site.contact_email }}</strong> adresine{% else %}bize{% endif %} yazın; talebiniz hızla değerlendirilir.</li>
     <li><strong>İnsan denetimi.</strong> Haberler editör onayından geçer. Güvenilirliği kanıtlanmış kaynaklardan gelen net haberler otomatik yayımlanabilir; bu durum haberin altında belirtilir.</li>
     <li><strong>Düzeltme.</strong> Hatalı bir bilgi fark edersek haberi güncelleriz ya da kaldırırız.</li>
--- a/templates/article.html
+++ b/templates/article.html
@@ -41,7 +41,8 @@
 
 {% block main %}
-{{ crumbs([("Ana sayfa", site.base ~ "/", site.url ~ "/"), (post.cat_label, post.cat_url, post.abs_cat_url), (post.short_title or post.title, post.url, post.abs_url)]) }}
 <article class="art" style="--c:{{ post.cat_color }}">
-  <header class="art-head wrap">
+  <div class="art-col">
+  {{ crumbs([("Ana sayfa", site.base ~ "/", site.url ~ "/"), (post.cat_label, post.cat_url, post.abs_cat_url), (post.short_title or post.title, post.url, post.abs_url)], '') }}
+  <header class="art-head">
     <div class="meta-top">
       <a class="eyebrow" href="{{ post.cat_url }}">{{ post.cat_label }}</a>
@@ -51,72 +52,86 @@
     <h1>{{ post.title_disp }}</h1>
     <p class="dek">{{ post.summary }}</p>
+    <div class="share" aria-label="Paylaş">
+      <a href="https://x.com/intent/post?url={{ post.abs_url|urlencode }}&text={{ post.title|urlencode }}" rel="noopener" target="_blank">X</a>
+      <a href="https://wa.me/?text={{ (post.title ~ ' ' ~ post.abs_url)|urlencode }}" rel="noopener" target="_blank">WhatsApp</a>
+      <a href="https://www.linkedin.com/sharing/share-offsite/?url={{ post.abs_url|urlencode }}" rel="noopener" target="_blank">LinkedIn</a>
+      <button type="button" data-copy="{{ post.abs_url }}">Bağlantıyı kopyala</button>
+    </div>
   </header>
 
-  <figure class="art-media wrap">
-    <div class="ph">{{ img(post, eager=true, sizes='(min-width: 1232px) 1200px, 100vw', priority=true) }}</div>
-    {% if not post.cover_image %}<figcaption>{% if post.ai_image %}Temsili görsel, yapay zeka ile üretilmiştir.{% else %}Temsili görsel.{% endif %}</figcaption>{% endif %}
-  </figure>
-
-  <div class="art-grid wrap">
-    <div class="art-main">
-      {% if post.key_points or (post.hero_stat and not post.stat_on_cover) %}
-      <section class="facts" aria-label="Öne çıkanlar">
-        {% if post.hero_stat and not post.stat_on_cover %}
-        <div class="facts-stat"><span class="stat">{{ post.hero_stat }}</span>{% if post.hero_stat_label %}<span class="stat-label">{{ post.hero_stat_label }}</span>{% endif %}</div>
-        {% endif %}
-        {% if post.key_points %}
-        <div class="facts-list">
-          <h2 class="facts-title">Öne çıkanlar</h2>
-          <ol>{% for t in post.key_points %}<li>{{ t }}</li>{% endfor %}</ol>
+  {% if post.photos %}
+  {% set n = post.photos|length %}
+  <figure class="gal{{ ' single' if n == 1 }}" data-gal aria-label="Haberin fotoğrafları">
+    <div class="gal-view">
+      <div class="gal-track">
+        {% for ph in post.photos %}
+        <div class="gal-slide{{ ' fit' if (ph.w / ph.h) < 1.25 }}" role="group" aria-label="{{ loop.index }} / {{ n }}">
+          <img src="{{ ph.url }}" alt="{{ ph.alt }}" width="{{ ph.w }}" height="{{ ph.h }}" decoding="async"{% if loop.first %} fetchpriority="high"{% else %} loading="lazy"{% endif %}{% if ph.remote %} referrerpolicy="no-referrer" onerror="this.parentNode.remove()"{% endif %} style="{% if loop.first %}view-transition-name: v{{ post.id }}{% endif %}">
+          {% if ph.credit %}<a class="gal-credit" href="{{ ph.page or post.sources[0].url }}" rel="noopener nofollow" target="_blank">Görsel: {{ ph.credit }}</a>{% endif %}
         </div>
-        {% endif %}
-      </section>
+        {% endfor %}
+      </div>
+      {% if n > 1 %}
+      <button type="button" class="gal-btn" data-dir="-1" aria-label="Önceki fotoğraf">‹</button>
+      <button type="button" class="gal-btn" data-dir="1" aria-label="Sonraki fotoğraf">›</button>
+      <span class="gal-count" aria-live="polite"><b>1</b> / {{ n }}</span>
       {% endif %}
+    </div>
+    {% if n > 1 %}
+    <div class="gal-thumbs">
+      {% for ph in post.photos %}
+      <button type="button" data-go="{{ loop.index0 }}" aria-label="{{ loop.index }}. fotoğraf"{% if loop.first %} aria-current="true"{% endif %}><img src="{{ ph.url }}" alt="" loading="lazy" decoding="async"{% if ph.remote %} referrerpolicy="no-referrer" onerror="this.parentNode.remove()"{% endif %}></button>
+      {% endfor %}
+    </div>
+    {% endif %}
+  </figure>
+  {% else %}
+  <figure class="art-media">
+    <div class="ph">{{ img(post, eager=true, sizes='(min-width: 880px) 840px, 100vw', priority=true) }}</div>
+    {% if not post.cover_image %}<figcaption>{% if post.ai_image %}Temsili görsel, yapay zeka ile üretilmiştir.{% else %}Temsili görsel.{% endif %}</figcaption>{% endif %}
+  </figure>
+  {% endif %}
 
-      <div class="art-body">{{ post.body_html|safe }}</div>
+  {% if post.key_points or (post.hero_stat and not post.stat_on_cover) %}
+  <section class="facts" aria-label="Öne çıkanlar">
+    {% if post.hero_stat and not post.stat_on_cover %}
+    <div class="facts-stat"><span class="stat">{{ post.hero_stat }}</span>{% if post.hero_stat_label %}<span class="stat-label">{{ post.hero_stat_label }}</span>{% endif %}</div>
+    {% endif %}
+    {% if post.key_points %}
+    <div class="facts-list">
+      <h2 class="facts-title">Öne çıkanlar</h2>
+      <ol>{% for t in post.key_points %}<li>{{ t }}</li>{% endfor %}</ol>
+    </div>
+    {% endif %}
+  </section>
+  {% endif %}
 
-      {% if post.tag_list %}
-      <nav class="art-tags" aria-label="Konular">
-        <span class="muted">Konular</span>
-        {% for t in post.tag_list %}<a href="{{ t.url }}">{{ t.label }}</a>{% endfor %}
-      </nav>
-      {% endif %}
+  <div class="art-body">{{ post.body_html|safe }}</div>
 
-      <section class="sources" aria-labelledby="kaynaklar">
-        <h2 id="kaynaklar">Kaynaklar</h2>
-        <ol>
-          {% for s in post.sources %}
-          <li><a href="{{ s.url }}" rel="noopener" target="_blank">
-            <span><span class="s-name">{{ s.name }}</span>{% if s.via %} <span class="muted">({{ s.via }} üzerinden)</span>{% endif %}<span class="s-title">{{ s.title }}</span></span>
-            <span class="s-go" aria-hidden="true">↗</span>
-          </a></li>
-          {% endfor %}
-        </ol>
-        <p class="disclosure">
-          Bu haber, yukarıdaki kaynaklardan yapay zeka yardımıyla Türkçe derlenmiş
-          {%- if post.publish_mode == 'auto' %} ve güvenilir kaynak kuralları çerçevesinde otomatik yayımlanmıştır.{% else %} ve editör onayıyla yayımlanmıştır.{% endif %}
-          Ayrıntılar ve orijinal ifadeler için kaynaklara başvurun.{% if post.updated_str %} Son güncelleme: {{ post.updated_str }}.{% endif %}
-          Bir hata görürseniz <a href="{{ site.base }}/hakkinda/">bize bildirin</a>.
-        </p>
-      </section>
-    </div>
+  {% if post.tag_list %}
+  <nav class="art-tags" aria-label="Konular">
+    <span class="muted">Konular</span>
+    {% for t in post.tag_list %}<a href="{{ t.url }}">{{ t.label }}</a>{% endfor %}
+  </nav>
+  {% endif %}
 
-    <aside class="art-side" aria-label="Haber bilgileri">
-      <div class="side-in">
-        {% if post.toc|length > 1 %}
-        <nav class="toc" aria-label="Bu haberde">
-          <p class="side-h">Bu haberde</p>
-          <ol>{% for h in post.toc %}<li><a href="#{{ h.id }}">{{ h.text }}</a></li>{% endfor %}<li><a href="#kaynaklar">Kaynaklar</a></li></ol>
-        </nav>
-        {% endif %}
-        <div class="share">
-          <p class="side-h">Paylaş</p>
-          <a href="https://x.com/intent/post?url={{ post.abs_url|urlencode }}&text={{ post.title|urlencode }}" rel="noopener" target="_blank">X</a>
-          <a href="https://www.linkedin.com/sharing/share-offsite/?url={{ post.abs_url|urlencode }}" rel="noopener" target="_blank">LinkedIn</a>
-          <a href="https://wa.me/?text={{ (post.title ~ ' ' ~ post.abs_url)|urlencode }}" rel="noopener" target="_blank">WhatsApp</a>
-          <button type="button" data-copy="{{ post.abs_url }}">Bağlantıyı kopyala</button>
-        </div>
-      </div>
-    </aside>
+  <section class="sources" aria-labelledby="kaynaklar">
+    <h2 id="kaynaklar">Kaynaklar</h2>
+    <ol>
+      {% for s in post.sources %}
+      <li><a href="{{ s.url }}" rel="noopener" target="_blank">
+        <span><span class="s-name">{{ s.name }}</span>{% if s.via %} <span class="muted">({{ s.via }} üzerinden)</span>{% endif %}<span class="s-title">{{ s.title }}</span></span>
+        <span class="s-go" aria-hidden="true">↗</span>
+      </a></li>
+      {% endfor %}
+    </ol>
+    <p class="disclosure">
+      Bu haber, yukarıdaki kaynaklardan yapay zeka yardımıyla Türkçe derlenmiş
+      {%- if post.publish_mode == 'auto' %} ve güvenilir kaynak kuralları çerçevesinde otomatik yayımlanmıştır.{% else %} ve editör onayıyla yayımlanmıştır.{% endif %}
+      {% if post.has_photo %}Fotoğraflar, altlarında belirtilen kaynaklara aittir.{% endif %}
+      Ayrıntılar ve orijinal ifadeler için kaynaklara başvurun.{% if post.updated_str %} Son güncelleme: {{ post.updated_str }}.{% endif %}
+      Bir hata görürseniz <a href="{{ site.base }}/hakkinda/">bize bildirin</a>.
+    </p>
+  </section>
   </div>
 </article>
--- a/templates/base.html
+++ b/templates/base.html
@@ -70,5 +70,5 @@
   <div class="wrap foot-in">
     <a class="brand" href="{{ site.base }}/">{% if site.logo_svg %}<img class="wordmark" src="{{ site.logo_svg }}?v={{ site.asset_v }}" alt="{{ site.name }}" width="105" height="28" loading="lazy">{% else %}<span class="mark" aria-hidden="true"></span>{{ site.name }}{% endif %}</a>
-    <p>{{ site.name }}, dünyadan ve Türkiye'den teknoloji, inovasyon, girişim, yapay zeka, otomobil ve oyun haberlerini Türkçe ve kaynağıyla aktaran bir haber sitesidir. Her haberde orijinal kaynak adıyla ve bağlantısıyla belirtilir. Haberler kaynaklardan yapay zeka yardımıyla derlenir ve editör denetiminden geçer. Görseller temsilidir.</p>
+    <p>{{ site.name }}, dünyadan ve Türkiye'den teknoloji, inovasyon, girişim, yapay zeka, otomobil ve oyun haberlerini Türkçe ve kaynağıyla aktaran bir haber sitesidir. Her haberde orijinal kaynak adıyla ve bağlantısıyla belirtilir. Haberler kaynaklardan yapay zeka yardımıyla derlenir ve editör denetiminden geçer. Fotoğrafların kaynağı her fotoğrafın altında belirtilir.</p>
     <div class="foot-cats">
       {% for c in site.categories %}<a href="{{ c.url }}">{{ c.label }}</a>{% endfor %}
--- a/templates/_macros.html
+++ b/templates/_macros.html
@@ -54,5 +54,5 @@
     </div>
   </div>
-  <div class="rail" id="r-{{ id }}">
+  <div class="rail wrap" id="r-{{ id }}">
     {% for p in posts %}{{ rcard(p) }}{% endfor %}
   </div>
@@ -60,7 +60,7 @@
 {% endmacro %}
 
-{% macro crumbs(items) %}
+{% macro crumbs(items, cls='wrap') %}
 {# items: [(ad, göreli_url, mutlak_url), ...] #}
-<nav class="crumbs wrap" aria-label="Konum">
+<nav class="crumbs {{ cls }}" aria-label="Konum">
   <ol>
     {% for it in items %}
--- a/static/style.css
+++ b/static/style.css
@@ -10,5 +10,5 @@
   --line: #D2D2D7;
   --link: #2458D6;
-  --glass: rgba(255, 255, 255, .72);
+  --glass: rgba(255, 255, 255, .94);
   --blue: #326EF0;
   --green: #54D59C;
@@ -47,7 +47,8 @@ button { font: inherit; color: inherit; }
 .brand { display: inline-flex; align-items: center; gap: 5px; font-weight: 700; font-size: 19px; letter-spacing: -.03em; }
 .mark { width: 20px; height: 20px; border-radius: 6px; flex: none; background: var(--grad); }
-.brand .wordmark { display: block; width: auto; height: 32px; transition: opacity .2s var(--ease); }
+.brand .wordmark { display: block; width: auto; height: 28px; transform: translateY(1px); transition: opacity .2s var(--ease); }
+@media (max-width: 599px) { .nav .brand .wordmark { height: 25px; } }
 .brand:hover .wordmark { opacity: .82; }
-.foot .brand .wordmark { height: 28px; }
+.foot .brand .wordmark { height: 24px; transform: none; }
 
 /* ── üst menü (buzlu cam) ─────────────── */
@@ -184,8 +185,9 @@ button { font: inherit; color: inherit; }
 .arrows button:disabled { opacity: .35; cursor: default; }
 
-/* ── yatay kaydırmalı şerit ───────────── */
-.rail { display: grid; grid-auto-flow: column; grid-auto-columns: min(78vw, 360px); gap: 20px; overflow-x: auto;
-  scroll-snap-type: x mandatory; scroll-padding-inline: max(16px, (100% - 1200px) / 2); padding: 8px max(16px, (100% - 1200px) / 2) 40px;
-  scrollbar-width: none; }
+/* ── yatay kaydırmalı şerit (sayfa kenarlarıyla hizalı, taşmaz) ── */
+.rail { display: grid; grid-auto-flow: column; grid-auto-columns: calc((100% - 3 * 20px) / 4); gap: 20px; overflow-x: auto;
+  scroll-snap-type: x mandatory; padding-block: 8px 40px; scrollbar-width: none; }
+@media (max-width: 1099px) { .rail { grid-auto-columns: calc((100% - 2 * 20px) / 3); } }
+@media (max-width: 759px) { .rail { grid-auto-columns: 80%; gap: 14px; } }
 .rail::-webkit-scrollbar { display: none; }
 .rcard { scroll-snap-align: start; background: #fff; border-radius: var(--r-md); overflow: hidden; display: flex; flex-direction: column;
@@ -239,22 +241,62 @@ button { font: inherit; color: inherit; }
 /* ── haber sayfası (Newsroom tarzı) ────── */
 .progress { position: fixed; top: 0; left: 0; right: 0; height: 3px; z-index: 60; background: var(--grad); transform-origin: 0 50%; transform: scaleX(0); }
-/* başlık ve görsel aynı hizada; metin görselin sol kenarından başlar */
-.art-head { padding-block: 28px 0; }
-.art-head > * { max-width: 900px; }
+/* tek sütun: başlık, fotoğraf ve metin aynı genişlikte, sayfanın ortasında */
+.art-col { width: min(820px, 100% - 32px); margin-inline: auto; }
+.art-col .crumbs { padding-top: 22px; }
+.art-head { padding-block: 22px 0; }
 .art-head .meta-top { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; font-size: 14px; font-weight: 600; }
-.art-head .meta-top .eyebrow { font-size: 14px; text-transform: uppercase; letter-spacing: .04em; }
+.art-head .meta-top .eyebrow { font-size: 13px; text-transform: uppercase; letter-spacing: .06em; }
 .art-head .meta-top time, .art-head .meta-top .muted { color: var(--muted); font-weight: 400; }
-.art-head h1 { margin: 14px 0 0; font-size: clamp(32px, 5vw, 58px); line-height: 1.06; letter-spacing: -.04em; font-weight: 700; text-wrap: balance; }
-.art-head .dek { margin: 18px 0 0; max-width: 760px; font-size: clamp(19px, 2vw, 24px); line-height: 1.38; color: var(--ink-2); letter-spacing: -.02em; text-wrap: pretty; }
-.art-media { margin-top: 36px; }
-.art-media .ph { border-radius: var(--r-lg); overflow: hidden; background: var(--bg-alt); aspect-ratio: 4 / 3; }
-@media (min-width: 700px) { .art-media .ph { aspect-ratio: 16 / 9; } }
+.art-head h1 { margin: 12px 0 0; font-size: clamp(30px, 4.4vw, 46px); line-height: 1.1; letter-spacing: -.035em; font-weight: 700; text-wrap: balance; }
+.art-head .dek { margin: 16px 0 0; font-size: clamp(18px, 1.9vw, 21px); line-height: 1.45; color: var(--ink-2); letter-spacing: -.015em; text-wrap: pretty; }
+.art-head .share { margin-top: 20px; }
+@media (max-width: 599px) {
+  .art-head .share { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; }
+  .art-head .share::-webkit-scrollbar { display: none; }
+  .art-head .share a, .art-head .share button { flex: none; font-size: 13px; padding: 7px 12px; }
+  .art-body { font-size: 18px; line-height: 1.64; }
+  .art-body > p:first-child { font-size: 19px; }
+  .art-body h2 { font-size: 23px; }
+  .why p { font-size: 18px; }
+  .facts { padding: 22px 20px; }
+  .facts li { font-size: 16px; }
+  .gal-slide, .art-media .ph { aspect-ratio: 4 / 3; }
+}
+.art-media { margin: 28px 0 0; }
+.art-media .ph { border-radius: var(--r-md); overflow: hidden; background: var(--bg-alt); aspect-ratio: 16 / 10; }
 .art-media img { width: 100%; height: 100%; object-fit: cover; }
 .art-media figcaption { margin-top: 10px; font-size: 13px; color: var(--muted); }
 
-.art-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 40px; padding-top: 40px; }
-@media (min-width: 1000px) { .art-grid { grid-template-columns: minmax(0, 720px) 260px; justify-content: space-between; } }
-.art-main { min-width: 0; }
+/* fotoğraf galerisi (kaydırmalı) */
+.gal { margin: 28px 0 0; }
+.gal-view { position: relative; border-radius: var(--r-md); overflow: hidden; background: var(--bg-alt); }
+.gal-track { display: grid; grid-auto-flow: column; grid-auto-columns: 100%; overflow-x: auto; scroll-snap-type: x mandatory;
+  overscroll-behavior-x: contain; scrollbar-width: none; -webkit-overflow-scrolling: touch; }
+.gal-track::-webkit-scrollbar { display: none; }
+.gal-slide { position: relative; scroll-snap-align: start; aspect-ratio: 16 / 10; background: #EDEDF0; }
+.gal-slide img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
+.gal-slide.fit img { object-fit: contain; }
+.gal-credit { position: absolute; left: 12px; bottom: 12px; font-size: 12px; line-height: 1; padding: 7px 10px; border-radius: 999px;
+  background: rgba(0, 0, 0, .55); color: #fff; -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px); max-width: calc(100% - 24px);
+  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
+.gal-credit:hover { background: rgba(0, 0, 0, .75); }
+.gal-btn { position: absolute; top: 50%; width: 44px; height: 44px; margin-top: -22px; border: 0; border-radius: 50%; cursor: pointer;
+  background: rgba(255, 255, 255, .9); color: var(--ink); font-size: 24px; line-height: 1; display: grid; place-items: center;
+  box-shadow: 0 2px 10px rgba(0, 0, 0, .15); transition: opacity .2s, transform .2s; }
+.gal-btn[data-dir="-1"] { left: 12px; } .gal-btn[data-dir="1"] { right: 12px; }
+.gal-btn:disabled { opacity: 0; pointer-events: none; }
+.gal-btn:hover { transform: scale(1.06); }
+.gal-count { position: absolute; right: 12px; bottom: 12px; font-size: 12px; padding: 7px 10px; border-radius: 999px;
+  background: rgba(0, 0, 0, .55); color: #fff; }
+.gal-thumbs { display: flex; gap: 8px; margin-top: 10px; overflow-x: auto; scrollbar-width: none; }
+.gal-thumbs::-webkit-scrollbar { display: none; }
+.gal-thumbs button { flex: none; width: 76px; height: 50px; padding: 0; border: 2px solid transparent; border-radius: 10px; overflow: hidden;
+  cursor: pointer; background: var(--bg-alt); opacity: .6; transition: opacity .2s, border-color .2s; }
+.gal-thumbs button[aria-current="true"] { opacity: 1; border-color: var(--ink); }
+.gal-thumbs button:hover { opacity: 1; }
+.gal-thumbs img { width: 100%; height: 100%; object-fit: cover; }
+@media (hover: none), (max-width: 599px) { .gal-btn { display: none; } }
 
+.facts { margin-top: 32px; }
 /* öne çıkanlar kutusu */
 .facts { display: grid; gap: 22px; padding: 26px 28px; border-radius: var(--r-md);
@@ -272,5 +314,5 @@ button { font: inherit; color: inherit; }
 
 /* metin: ilk paragraf öne çıkar, bölümler ayraçla ayrılır */
-.art-body { font-size: 19px; line-height: 1.62; letter-spacing: -.012em; padding-top: 30px; }
+.art-body { font-size: 19px; line-height: 1.66; letter-spacing: -.012em; padding-top: 30px; }
 .art-body > p:first-child { font-size: 21px; line-height: 1.5; color: var(--ink); letter-spacing: -.018em; }
 .art-body p { margin: 0 0 1.1em; color: #2C2C2E; }
@@ -292,14 +334,6 @@ button { font: inherit; color: inherit; }
 .why p { margin: 8px 0 0; font-size: 21px; line-height: 1.42; letter-spacing: -.02em; font-weight: 600; color: var(--ink); text-wrap: pretty; }
 
-/* yan panel */
-.art-side { display: none; }
-@media (min-width: 1000px) { .art-side { display: block; } }
-.side-in { position: sticky; top: 76px; display: grid; gap: 28px; padding-top: 4px; }
-.side-h { margin: 0 0 8px; font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
-.toc ol { list-style: none; margin: 0; padding: 0; display: grid; border-left: 2px solid var(--line); }
-.toc a { display: block; padding: 7px 0 7px 14px; margin-left: -2px; border-left: 2px solid transparent; font-size: 15px; line-height: 1.35; color: var(--ink-2); }
-.toc a:hover { color: var(--ink); border-left-color: var(--c); }
+/* paylaş */
 .share { display: flex; flex-wrap: wrap; gap: 8px; }
-.share .side-h { flex-basis: 100%; }
 .share a, .share button { font-size: 14px; padding: 8px 14px; border-radius: 999px; background: var(--bg-alt); border: 0; cursor: pointer; transition: background .2s; }
 .share a:hover, .share button:hover { background: #E8E8ED; }
--- a/static/site.js
+++ b/static/site.js
@@ -31,4 +31,28 @@
   });
 
+  // Fotoğraf galerisi: kaydırma, oklar, sayaç, küçük resimler
+  document.querySelectorAll("[data-gal]").forEach(function (g) {
+    var track = g.querySelector(".gal-track");
+    if (!track) return;
+    var prev = g.querySelector('.gal-btn[data-dir="-1"]'), next = g.querySelector('.gal-btn[data-dir="1"]');
+    var count = g.querySelector(".gal-count b");
+    function slides() { return track.querySelectorAll(".gal-slide"); }
+    function idx() { return Math.round(track.scrollLeft / Math.max(1, track.clientWidth)); }
+    function update() {
+      var n = slides().length, i = Math.min(idx(), n - 1);
+      if (count) count.textContent = i + 1;
+      var tot = g.querySelector(".gal-count"); if (tot) { tot.lastChild.nodeValue = " / " + n; tot.hidden = n < 2; }
+      if (prev) prev.disabled = i <= 0;
+      if (next) next.disabled = i >= n - 1;
+      g.querySelectorAll(".gal-thumbs button").forEach(function (b, k) { b.setAttribute("aria-current", k === i ? "true" : "false"); });
+    }
+    function go(i) { track.scrollTo({ left: i * track.clientWidth, behavior: "smooth" }); }
+    [prev, next].forEach(function (b) { if (b) b.addEventListener("click", function () { go(idx() + (+b.getAttribute("data-dir"))); }); });
+    g.querySelectorAll(".gal-thumbs button").forEach(function (b) { b.addEventListener("click", function () { go(+b.getAttribute("data-go")); }); });
+    var t; track.addEventListener("scroll", function () { clearTimeout(t); t = setTimeout(update, 60); }, { passive: true });
+    track.addEventListener("keydown", function (e) { if (e.key === "ArrowRight") go(idx() + 1); if (e.key === "ArrowLeft") go(idx() - 1); });
+    update();
+  });
+
   // Bağlantıyı kopyala
   document.querySelectorAll("[data-copy]").forEach(function (b) {
--- a/config.yaml
+++ b/config.yaml
@@ -57,4 +57,10 @@ autonomy:
 
 images:
+  # Gerçek fotoğraflar: önce şirketin resmi görseli, yoksa kaynak haberin görselleri (kaynağı fotoğrafın altında yazar).
+  # Fotoğraf bulunamazsa aşağıdaki tipografik kapak kullanılır.
+  photos: true
+  photo_limit: 6                  # haber başına en fazla fotoğraf (1 ana + galeri)
+  photo_backfill_per_run: 5       # eski haberlere her turda kaç tanesine fotoğraf eklensin
+  gallery_keep_days: 0            # 0 = fotoğraflar hiç silinmez (kalıcı depolama)
   # kapak: habere özel tipografik kapak (dev rakam / isim / manşet), ücretsiz (önerilen)
   # 3d   : renkli 3D şekiller
@@@SM@@@ FILE haberbot/photos.py
"""Haber fotoğrafları: şirketin resmi görselleri ya da kaynak haberin görselleri, kredisiyle.

Sıra: resmi kaynak (şirketin kendi duyurusu) → diğer kaynaklar. Her kaynağın sayfasından
paylaşım görseli (og:image), yapılandırılmış veri görseli ve metin içindeki büyük fotoğraflar alınır.
Küçük/logo/ikon görseller ve aynı fotoğrafın farklı boyutları elenir.

Ana fotoğraf ve galerinin ilk günleri için kopyalar sitede tutulur (hızlı ve güvenilir);
eski galerilerde yer kazanmak için yerel kopya silinip kaynaktaki adres kullanılır.
Hak sahibi talep ederse fotoğraflar Telegram'dan tek tuşla kaldırılır.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from PIL import Image, ImageOps, ImageStat

from .extract import UA, fetch_html
from .util import log

MAX_BYTES = 15_000_000
MIN_W, MIN_H = 600, 320
BAD_URL = re.compile(
    r"(logo|icon|favicon|sprite|avatar|gravatar|/authors?/|profile[-_]?(pic|photo|image)|placeholder|blank\.|"
    r"pixel|spacer|badge|emoji|/ads?/|advert|doubleclick|banner-ad|/share|social[-_]|newsletter|"
    r"default[-_]?(image|og|thumb)|fallback|wp-content/plugins|gstatic\.com/images/branding)", re.I)
BAD_EXT = (".svg", ".gif", ".ico", ".bmp")
SIZE_SUFFIX = re.compile(r"-\d{2,4}x\d{2,4}(?=\.\w{3,4}$)")
RESIZE_KEYS = {"w", "h", "width", "height", "resize", "fit", "quality", "q", "crop", "strip", "ssl", "format", "auto"}
LD_TYPES = {"newsarticle", "article", "blogposting", "reportagenewsarticle", "product", "webpage", "report",
            "techarticle", "analysisnewsarticle"}


# ── adaylar ───────────────────────────────────────────────
def _abs(u: str, base: str) -> str:
    u = (u or "").strip().split(" ")[0]
    if not u or u.startswith("data:"):
        return ""
    u = urljoin(base, u)
    if u.startswith("//"):
        u = "https:" + u
    if u.startswith("http://"):
        u = "https://" + u[7:]
    return u if u.startswith("https://") else ""


def _key(u: str) -> str:
    """Aynı fotoğrafın farklı boyut/parametre sürümlerini birleştirmek için anahtar."""
    p = urlsplit(u)
    path = SIZE_SUFFIX.sub("", p.path.lower())
    q = "&".join(x for x in p.query.split("&") if x and x.split("=")[0].lower() not in RESIZE_KEYS)
    return urlunsplit(("", p.netloc.lower(), path, q, ""))


def _largest_src(srcset: str) -> tuple[str, int]:
    best, bw = "", -1
    for part in (srcset or "").split(","):
        bits = part.strip().split()
        if not bits:
            continue
        w = 0
        if len(bits) > 1:
            m = re.match(r"(\d+(?:\.\d+)?)([wx])", bits[1])
            if m:
                w = int(float(m.group(1)) * (1 if m.group(2) == "w" else 1000))
        if w > bw:
            best, bw = bits[0], w
    return best, max(bw, 0)


def _ld_images(obj, out: list[str]) -> None:
    if isinstance(obj, list):
        for x in obj:
            _ld_images(x, out)
        return
    if not isinstance(obj, dict):
        return
    if "@graph" in obj:
        _ld_images(obj["@graph"], out)
    t = obj.get("@type")
    types = {str(x).lower() for x in (t if isinstance(t, list) else [t])}
    if types & LD_TYPES:
        img = obj.get("image") or obj.get("thumbnailUrl")
        for it in (img if isinstance(img, list) else [img]):
            if isinstance(it, str):
                out.append(it)
            elif isinstance(it, dict):
                out.append(it.get("url") or it.get("contentUrl") or "")


def candidates(html: str, base_url: str, limit: int = 14) -> list[dict]:
    """Sayfadaki fotoğraf adayları: paylaşım görseli, yapılandırılmış veri, metin içi fotoğraflar."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    seen: set[str] = set()

    def add(u: str, kind: str, alt: str = "", w: int = 0) -> None:
        u = _abs(u, base_url)
        if not u:
            return
        low = urlsplit(u).path.lower()
        if low.endswith(BAD_EXT) or BAD_URL.search(u):
            return
        if w and w < 400:
            return
        k = _key(u)
        if k in seen:
            return
        seen.add(k)
        out.append({"url": u, "kind": kind, "alt": (alt or "").strip()[:160]})

    metas = [("property", "og:image:secure_url"), ("property", "og:image"), ("property", "og:image:url"),
             ("name", "twitter:image"), ("name", "twitter:image:src"), ("property", "twitter:image")]
    og_alt = ""
    tag = soup.find("meta", attrs={"property": "og:image:alt"})
    if tag:
        og_alt = tag.get("content") or ""
    for attr, val in metas:
        for tag in soup.find_all("meta", attrs={attr: val}):
            add(tag.get("content") or "", "og", og_alt)
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(s.string or s.get_text() or "")
        except (ValueError, TypeError):
            continue
        found: list[str] = []
        _ld_images(data, found)
        for u in found:
            add(u, "ld")

    root = (soup.find(attrs={"itemprop": "articleBody"}) or soup.find("article")
            or soup.find(class_=re.compile(r"(entry|post|article|story)[-_]?(content|body)", re.I))
            or soup.find("main") or soup.body)
    if root is not None:
        for bad in root.find_all(["header", "footer", "nav", "aside", "form"]):
            bad.decompose()
        for img in root.find_all(["img", "source"]):
            if img.find_parent(class_=re.compile(r"(author|avatar|related|recommend|share|comment|newsletter|promo|sponsor|widget)", re.I)):
                continue
            srcset = img.get("data-srcset") or img.get("srcset") or img.get("data-lazy-srcset") or ""
            u, sw = _largest_src(srcset)
            if not u:
                u = (img.get("data-src") or img.get("data-lazy-src") or img.get("data-original")
                     or img.get("data-full-url") or img.get("src") or "")
            try:
                w = int(str(img.get("width") or "0").rstrip("px") or 0)
            except ValueError:
                w = 0
            add(u, "body", img.get("alt") or "", max(w, sw) if (w or sw) else 0)
            if len(out) >= limit:
                break
    return out[:limit]


# ── indirme ve eleme ───────────────────────────────────────
def _dhash(im: Image.Image) -> int:
    g = im.convert("L").resize((9, 8), Image.BILINEAR)
    px = list(g.tobytes())
    bits = 0
    for r in range(8):
        for c in range(8):
            bits = (bits << 1) | (px[r * 9 + c] > px[r * 9 + c + 1])
    return bits


def _similar(a: int, b: int) -> bool:
    return bin(a ^ b).count("1") <= 8


def fetch_image(url: str, referer: str = "", timeout: int = 20) -> Image.Image | None:
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Referer": referer or url,
                                       "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"},
                         timeout=timeout, stream=True)
        if r.status_code >= 400 or not r.headers.get("content-type", "image").startswith("image"):
            return None
        data = r.raw.read(MAX_BYTES + 1, decode_content=True)
        if len(data) > MAX_BYTES:
            return None
        im = Image.open(io.BytesIO(data))
        im.load()
    except (requests.RequestException, OSError, Image.DecompressionBombError, ValueError):
        return None
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg
    return im.convert("RGB")


def usable(im: Image.Image) -> bool:
    w, h = im.size
    if w < MIN_W or h < MIN_H or not (0.5 <= w / h <= 2.4):
        return False
    st = ImageStat.Stat(im.resize((64, 64)).convert("L"))
    return st.stddev[0] >= 14  # düz/boş görseller (logo zemini, yer tutucu) elenir


def gather(sources: list[dict], limit: int = 6, per_source: int = 4, pages: int = 3) -> list[dict]:
    """Kaynaklardan fotoğraf topla. Dönen her öğe: {'image': PIL, 'src', 'credit', 'page', 'alt', 'kind'}"""
    order = sorted(sources, key=lambda s: 0 if s.get("kind") == "official" else 1)[:pages]
    picked: list[dict] = []
    hashes: list[int] = []
    for s in order:
        url = s.get("url") or ""
        cands: list[dict] = []
        feed_img = _abs(s.get("image") or "", url or "https://x/")
        if feed_img and not BAD_URL.search(feed_img):
            cands.append({"url": feed_img, "kind": "feed", "alt": ""})
        html = fetch_html(url) if url else ""
        if html:
            known = {_key(c["url"]) for c in cands}
            cands += [c for c in candidates(html, url) if _key(c["url"]) not in known]
        n = 0
        for c in cands:
            if len(picked) >= limit or n >= per_source:
                break
            im = fetch_image(c["url"], url)
            if im is None or not usable(im):
                continue
            h = _dhash(im)
            if any(_similar(h, x) for x in hashes):
                continue
            hashes.append(h)
            picked.append({"image": im, "src": c["url"], "credit": s.get("name") or urlsplit(url).netloc,
                           "page": url, "alt": c["alt"], "kind": c["kind"]})
            n += 1
        if len(picked) >= limit:
            break
    log.info("Fotoğraf: %d bulundu (%s)", len(picked), ", ".join(dict.fromkeys(p["credit"] for p in picked)) or "-")
    return picked


# ── kaydetme ──────────────────────────────────────────────
def save_webp(im: Image.Image, out: Path, max_w: int, quality: int) -> tuple[int, int]:
    out.parent.mkdir(parents=True, exist_ok=True)
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    im.save(out, "WEBP", quality=quality, method=6)
    return im.size


def og_crop(im: Image.Image, out: Path, size=(1200, 630)) -> None:
    """Paylaşım görseli: fotoğrafın ortasından (hafif yukarıdan) 1200x630 kırpım."""
    tw, th = size
    w, h = im.size
    scale = max(tw / w, th / h)
    nw, nh = round(w * scale), round(h * scale)
    im = im.resize((nw, nh), Image.LANCZOS)
    x = (nw - tw) // 2
    y = max(0, min(nh - th, round((nh - th) * 0.4)))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.crop((x, y, x + tw, y + th)).save(out, "JPEG", quality=84, optimize=True, progressive=True)
@@@SM@@@ FILE tests/test_photos.py
"""Gerçek fotoğraf hattı testleri (ağ yok: sayfa ve görseller sahte)."""
import sys
import tempfile
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haberbot import app as appmod  # noqa: E402
from haberbot import photos  # noqa: E402
from haberbot.config import ROOT, Config  # noqa: E402
from haberbot.util import iso, now_utc  # noqa: E402

HTML = """<html><head>
<meta property="og:image" content="https://cdn.site.com/2026/09/car-1200x675.jpg">
<meta name="twitter:image" content="https://cdn.site.com/2026/09/car.jpg?w=800">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"NewsArticle","image":["https://cdn.site.com/2026/09/car-side.jpg"]}</script>
</head><body><header><img src="/logo.png"></header>
<article><h1>T</h1>
<img src="/wp-content/uploads/interior-300x200.jpg" srcset="/wp-content/uploads/interior-300x200.jpg 300w, /wp-content/uploads/interior-1600x900.jpg 1600w" alt="İç mekan">
<img data-src="https://cdn.site.com/rear.webp" width="1200">
<img src="https://cdn.site.com/icon-share.png" width="24">
<img src="https://cdn.site.com/tiny.jpg" width="120">
<div class="author-box"><img src="https://cdn.site.com/me.jpg"></div>
<img src="data:image/gif;base64,xx">
</article><aside><img src="https://cdn.site.com/ad.jpg"></aside></body></html>"""


def test_candidates():
    c = photos.candidates(HTML, "https://site.com/news/x")
    urls = [x["url"] for x in c]
    assert urls[0] == "https://cdn.site.com/2026/09/car-1200x675.jpg"          # paylaşım görseli önce
    assert "https://cdn.site.com/2026/09/car.jpg?w=800" not in urls            # aynı fotoğrafın başka boyutu
    assert "https://cdn.site.com/2026/09/car-side.jpg" in urls                 # yapılandırılmış veri
    assert "https://site.com/wp-content/uploads/interior-1600x900.jpg" in urls  # srcset'in en büyüğü
    assert "https://cdn.site.com/rear.webp" in urls                            # tembel yükleme
    assert not any(k in u for u in urls for k in ("logo", "icon-share", "tiny", "me.jpg", "ad.jpg", "data:"))
    assert next(x for x in c if "interior" in x["url"])["alt"] == "İç mekan"


def _photo(color, size=(1600, 900), seed=0):
    import random
    rnd = random.Random(seed)
    im = Image.new("RGB", size, color)
    d = ImageDraw.Draw(im)
    for _ in range(40):
        x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
        d.ellipse([x, y, x + rnd.randint(80, 500), y + rnd.randint(80, 400)],
                  fill=(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)))
    return im


def test_usable_and_dedupe():
    assert photos.usable(_photo("#335"))
    assert not photos.usable(Image.new("RGB", (1600, 900), "white"))     # düz zemin
    assert not photos.usable(_photo("#335", (400, 300)))                 # küçük
    assert not photos.usable(_photo("#335", (3000, 800)))                # çok geniş şerit
    a, b = _photo("#335", seed=1), _photo("#335", seed=1).resize((800, 450))
    assert photos._similar(photos._dhash(a), photos._dhash(b))


def test_gather_prefers_official_and_feed_image():
    pages = {"https://brand.com/press": HTML, "https://news.com/a": HTML.replace("cdn.site.com", "cdn.news.com")}
    imgs = {}

    def fake_fetch(url, referer="", timeout=20):
        if url not in imgs:
            imgs[url] = _photo("#%02x%02x55" % (len(imgs) * 30 % 255, 90), seed=len(imgs))
        return imgs[url]

    photos.fetch_html, photos.fetch_image = (lambda u: pages.get(u, "")), fake_fetch
    got = photos.gather([
        {"name": "Haber Sitesi", "url": "https://news.com/a", "kind": "media", "image": "https://cdn.news.com/feed-hero.jpg"},
        {"name": "Marka", "url": "https://brand.com/press", "kind": "official"},
    ], limit=6, per_source=3)
    assert got[0]["credit"] == "Marka"                     # resmi kaynak önce
    assert [g["credit"] for g in got].count("Marka") == 3
    news = [g for g in got if g["credit"] == "Haber Sitesi"]
    assert news[0]["src"] == "https://cdn.news.com/feed-hero.jpg"   # beslemedeki görsel o kaynağın ilk adayı


def test_attach_backfill_and_buttons():
    with tempfile.TemporaryDirectory() as t:
        raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
        cfg = Config(raw=raw, root=Path(t), site_url="https://smarity.com.tr")
        a = appmod.App(cfg)
        post = {"id": "p1", "slug": "ornek", "title": "Örnek araba tanıtıldı", "summary": "Özet", "category": "teknoloji",
                "tags": [], "body": "Metin.", "published_at": iso(now_utc()), "image": {"source": "cover"},
                "sources": [{"name": "Marka", "url": "https://brand.com/press", "kind": "official"}]}
        a.store.save_post(post)
        shots = [{"image": _photo("#446", seed=i), "src": f"https://x/{i}.jpg", "credit": "Marka",
                  "page": "https://brand.com/press", "alt": "", "kind": "og"} for i in range(4)]
        appmod.photos.gather = lambda *a_, **k: shots
        a.backfill_photos(5)
        p = a.store.load_post("p1")
        assert p["image"]["source"] == "photo" and len(p["photos"]) == 4
        assert (cfg.images_dir / "p1.webp").exists() and (cfg.images_dir / "p1-g3.webp").exists()
        assert (cfg.images_dir / "p1-og.jpg").exists() and Image.open(cfg.images_dir / "p1-og.jpg").size == (1200, 630)
        # başka fotoğraf: sıra döner, ilk fotoğraf galeriye geçer
        first_src = p["photos"][0]["src"]
        a._reorder_photos(p, "post", p["photos"][1:] + p["photos"][:1])
        assert p["photos"][0]["src"] == "https://x/1.jpg" and p["photos"][-1]["src"] == first_src
        # site görünümü: yerel dosyalar, kredi
        from haberbot.site import SiteBuilder
        view = SiteBuilder(cfg)._post_view(p)
        assert view["photos"][0]["url"] == "/img/p1.webp" and view["photos"][0]["credit"] == "Marka"
        # site üretilince galeri dosyaları da yayına kopyalanır
        SiteBuilder(cfg).build()
        assert (cfg.out_dir / "img" / "p1-g2.webp").exists()
        html = (cfg.out_dir / "haber" / "ornek" / "index.html").read_text(encoding="utf-8")
        assert 'class="gal' in html and "Görsel: Marka" in html and "/img/p1-g1.webp" in html
        # eski galeri kopyaları silinir, kaynaktan gösterilir
        p["published_at"] = "2020-01-01T00:00:00+00:00"
        a.store.save_post(p)
        a.prune_gallery()                                   # varsayılan 0: hiçbir şey silinmez
        assert a.store.load_post("p1")["photos"][1]["file"]
        a.cfg.raw["images"]["gallery_keep_days"] = 30
        a.state["last_prune"] = None
        a.prune_gallery()
        p = a.store.load_post("p1")
        assert p["photos"][1]["file"] is None and not (cfg.images_dir / "p1-g1.webp").exists()
        view = SiteBuilder(cfg)._post_view(p)
        assert view["photos"][1]["remote"] and view["photos"][1]["url"].startswith("https://x/")
        assert [b["callback_data"][0] for b in a._visual_buttons(p)] == ["g", "n"]
        # fotoğrafsız
        a._drop_photos(p, "post")
        assert "photos" not in p and a._visual_buttons(p)[0]["callback_data"].startswith("v:")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
@@@SM@@@ SHA
ba0c0cdffe594cc03aa880efa2f4326576caa96d81562338722effea4bf53b2b haberbot/site.py
d8f8800ec92224b4515b95d7fcf4e50f6d6f57012e0a329ccfedb03d15502224 haberbot/extract.py
1e9cb863a7be04a5f58c2e1a40f5ef08e1023f7295f58b3f7a1eaf76efacabe0 haberbot/images.py
128d81275dd3badbe3b507f275181c0308f2bf869a8d47502d83f2da61054568 haberbot/sources.py
a06159ecf33844f62d598869d30fe6bbdd7a7a5a9b968f21d4719533fa973c95 haberbot/app.py
a2f019178584aa34b89ae4a14f7bd239894d4070effda8c29d2033ddfc23ed77 haberbot/store.py
85c5ff87c743d819bb89c421a858758c67a6b49a3a866eff61cc75e2cb2407ec templates/about.html
1321f30dd57997c10983d45cb1cd808162418ed3736ae74e5a1d0ec6f235c176 templates/article.html
1367ebda2e53b0f0c6ec69257700caff6f7241b1884837ca77c569b70c30b291 templates/base.html
1f981bd5d14201a389e71a30a44465dd10f504495cf321402c9aba5eb9f8890c templates/_macros.html
73f9fba2378282c2aed46f46b32c58428bd3f32a17c95cb99a778f4fd6be3767 static/style.css
10cb41ddb7a40927e71870629f28d8bdea035a7c5c9cb6c19af912e13fe9ccd6 static/site.js
6620f2671b9eefdd6059dcac1efc6dc85bbdf1a44eb558d82ddb43aac100f4a7 config.yaml
71e75ba3cbc3707271dcc285d1bde37c5b25da35e8a76dbcea547e91a9b94d73 haberbot/photos.py
9836868a22b6f626d33bf7d3f26b7c8af75dd977654a5a3b50623f7ed2218b3d tests/test_photos.py
