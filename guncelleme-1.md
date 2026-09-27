SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -13,5 +13,15 @@
   posts_per_page: 18
   contact_email: "smarityco@gmail.com"   # Hakkında sayfasında görünür
-  instagram: ""            # Instagram kullanıcı adı (boşsa bağlanan hesap kullanılır; site altında bağlantı çıkar)
+  # Takip kanalları: yazılanlar sitede "Takip et" bölümünde ve alt bilgide görünür
+  instagram: ""            # Instagram kullanıcı adı (boşsa bağlanan hesap kullanılır)
+  telegram: ""             # Telegram kanalı kullanıcı adı (örn. smaritytr)
+  whatsapp: ""             # WhatsApp kanalı bağlantısı (https://whatsapp.com/channel/...)
+  x: ""                    # X (Twitter) kullanıcı adı
+
+home:
+  # Ana sayfa seçkisi: her haber ana sayfaya çıkmaz. İlgi puanı (yapay zeka verir) ve tazeliğe göre en dikkat çekiciler
+  # manşete ve "Öne çıkanlar"a girer; diğerleri kategori ve "Tüm haberler" sayfalarında durur.
+  # Telegram'daki "⭐ Manşete al" ve "🙈 Ana sayfada gösterme" düğmeleriyle tek tek yönetebilirsin.
+  featured_count: 5        # manşetteki haber sayısı
 
 seo:
@@ -26,5 +36,4 @@
   # Yeni haberleri Bing ve Yandex'e anında bildir (ücretsiz, hesap gerekmez)
   indexnow: true
-  featured_count: 5        # Ana sayfadaki kaydırmalı manşette kaç haber olsun
 
 schedule:
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -17,8 +17,9 @@
 from .instagram import Instagram, InstagramError, TokenStore, fingerprint, head_ok
 from .llm import LLMError, MockLLM, estimate_cost, make_llm
-from .prompts import (FLAG_LABELS, FLAGS, SEO_SCHEMA, TRIAGE_SCHEMA, WRITE_SCHEMA, seo_system, seo_user,
-                      triage_system, triage_user, write_system, write_user)
+from .prompts import (APPEAL_SCHEMA, FLAG_LABELS, FLAGS, SEO_SCHEMA, TRIAGE_SCHEMA, WRITE_SCHEMA, appeal_system,
+                      appeal_user, seo_system, seo_user, triage_system, triage_user, write_system, write_user)
 from .sources import fetch_all
 from .store import Store
+from .textfix import Fixer
 from .telegram import MockTelegram, Telegram, TelegramError
 from .util import (clip, hours_since, iso, local, log, now_utc, short_hash, slugify,
@@ -56,8 +57,14 @@
 📄 <b>Tam metin</b> — haberin tamamını gösterir
 🔁 <b>Yeniden yaz</b> — yapay zeka metni yeniden yazar
-🎨 <b>Yeni görsel</b> — aynı sahneden yeni bir görsel üretir
-🖼 <b>Kendi sahnen</b> — mesajı yanıtlayıp <code>görsel: kırmızı bir satranç tahtası üzerinde cam piyonlar</code> gibi yaz; görsel buna göre yeniden üretilir
+🖼 <b>Başka foto</b> — kapaktaki fotoğrafı sıradaki fotoğrafla değiştirir
+🎨 <b>Yazılı kapak / Yeni kapak</b> — kapağı bizim yazılı tasarımımıza çevirir ya da yenisini üretir (fotoğraflar haberde kalır)
+🚫 <b>Fotoğrafsız</b> — haberdeki tüm fotoğrafları kaldırır
+🔤 <b>Kapak yazısı</b> — mesajı yanıtlayıp <code>görsel: Galaxy S27</code> gibi kısa bir ifade yazarsan kapakta o yazar
 ✏️ <b>Düzeltme</b> — bir haber mesajını <i>yanıtlayıp</i> talimat yaz: "başlığı kısalt", "ikinci paragrafı çıkar" gibi. Yayınlanmış habere de uygulanır.
 🗑 <b>Kaldır</b> — yayınlanmış haberi siteden kaldırır
+⭐ <b>Manşete al</b> — haberi 36 saat ana sayfa manşetinin en başına koyar
+🙈 <b>Ana sayfada gösterme</b> — haber ana sayfaya çıkmaz, kategoride ve "Tüm haberler"de kalır
+
+<b>Ana sayfa seçkisi:</b> Her haber ana sayfaya çıkmaz. Yapay zeka her habere bir ilgi puanı verir; puan ve tazeliğe göre en dikkat çekiciler manşete ve "Öne çıkanlar"a girer.
 
 <b>Öğrenen mod:</b> Kararların kaynak bazında kaydedilir. Bir kaynak yeterince onay alınca, o kaynaktan gelen net haberler otomatik yayınlanır ve sana sessizce bildirilir. Şüpheli işaretli haberler her zaman sana sorulur.
@@ -309,4 +316,52 @@
 
     # ── 2) YAZIM ────────────────────────────────────────────
+    @property
+    def fixer(self) -> Fixer:
+        """Türkçe metin düzeltici; sözlüğünü yayındaki haberlerin metinlerinden öğrenir (tur başına bir kez)."""
+        if getattr(self, "_fixer", None) is None:
+            self._fixer = Fixer([f"{p.get('summary', '')}\n{p.get('body', '')}" for p in self.store.posts()])
+        return self._fixer
+
+    @staticmethod
+    def _appeal(v) -> int | None:
+        try:
+            return max(1, min(10, int(v)))
+        except (TypeError, ValueError):
+            return None
+
+    def fix_texts(self) -> None:
+        """Yayındaki haberlerde Türkçe karakteri düşmüş sözcükleri ve marka yazımlarını düzelt."""
+        for p in self.store.posts():
+            changed = self.fixer.post(p)
+            if changed:
+                p["updated_at"] = p.get("updated_at") or p.get("published_at")
+                self.store.save_post(p)
+                self.queue_indexnow(self.cfg.post_url(p["slug"]))
+                log.info("Metin düzeltildi: %s (%s)", p["id"], ", ".join(changed))
+
+    def backfill_appeal(self, batch: int = 25) -> None:
+        """İlgi puanı olmayan eski haberleri toplu puanla (ana sayfa seçkisi için)."""
+        if not self.llm:
+            return
+        todo = [p for p in self.store.posts() if p.get("appeal") is None and not p.get("appeal_skip")][:batch]
+        if not todo:
+            return
+        try:
+            out = self.llm.json(self.cfg.get("ai", "triage_model", "gemini-flash-lite-latest"),
+                                appeal_system(self.brand), appeal_user(todo), APPEAL_SCHEMA, max_tokens=3000)
+        except LLMError as e:
+            log.warning("İlgi puanları alınamadı: %s", e)
+            return
+        got = {str(x.get("id")): self._appeal(x.get("appeal")) for x in (out.get("scores") or []) if isinstance(x, dict)}
+        for p in todo:
+            if got.get(p["id"]):
+                p["appeal"] = got[p["id"]]
+            else:
+                p["appeal_tries"] = int(p.get("appeal_tries", 0)) + 1
+                if p["appeal_tries"] >= 3:
+                    p["appeal_skip"] = True
+            self.store.save_post(p)
+        log.info("İlgi puanı verildi: %d haber", sum(1 for p in todo if p.get("appeal")))
+
     def _write(self, sources: list[dict], previous: dict | None = None, instruction: str | None = None) -> dict:
         cfg = self.cfg
@@ -317,5 +372,5 @@
             WRITE_SCHEMA, max_tokens=16000, effort=cfg.get("ai", "writer_effort", "medium"))
         cat = out.get("category") if out.get("category") in CATEGORIES else None
-        return {
+        res = {
             "title": clip((out.get("title") or "").strip().rstrip("."), 120),
             "summary": clip((out.get("summary") or "").strip(), 280),
@@ -339,5 +394,8 @@
             "cover_text": clip((out.get("cover_text") or "").strip(), 24),
             "carousel_points": [clip(x.strip(), 130) for x in (out.get("carousel_points") or []) if x and x.strip()][:4],
+            "appeal": self._appeal(out.get("appeal")),
         }
+        self.fixer.post(res)          # Türkçe karakter ve marka yazımı düzeltmeleri
+        return res
 
     def create_draft(self, story: dict, its: list[dict]) -> dict:
@@ -479,5 +537,8 @@
                      {"text": "🗑 Kaldır", "callback_data": f"d:{did}"}],
                     [{"text": "📄 Tam metin", "callback_data": f"f:{did}"},
-                     {"text": "📱 Instagram", "callback_data": f"s:{did}"}], self._visual_buttons(d)]
+                     {"text": "📱 Instagram", "callback_data": f"s:{did}"}], self._visual_buttons(d),
+                    [{"text": "⭐ Manşetten çıkar" if d.get("home") == "pin" else "⭐ Manşete al", "callback_data": f"m:{did}"},
+                     {"text": "🏠 Ana sayfada göster" if d.get("home") == "hide" else "🙈 Ana sayfada gösterme",
+                      "callback_data": f"h:{did}"}]]
         if kind == "rejected":
             return [[{"text": "↩️ Geri al", "callback_data": f"u:{did}"}]]
@@ -700,4 +761,19 @@
             self.tg.send_message(self.chat_id, body, reply_to=mid, silent=True)
             return ""
+        if action in ("m", "h"):
+            # ana sayfa seçkisi: manşete sabitle (36 saat) ya da ana sayfada hiç gösterme (kategoride kalır)
+            if where != "post":
+                return "Önce yayınlanmalı."
+            cur = d.get("home")
+            new = ("pin" if cur != "pin" else None) if action == "m" else ("hide" if cur != "hide" else None)
+            if new:
+                d["home"], d["home_at"] = new, iso(now_utc())
+            else:
+                d.pop("home", None)
+                d.pop("home_at", None)
+            st.save_post(d)
+            self._update_preview(d, "auto" if d.get("publish_mode") == "auto" else "published")
+            return {"pin": "⭐ Manşete alındı", "hide": "🙈 Ana sayfada gösterilmeyecek (kategoride kalır)",
+                    None: "↩️ Ana sayfada normal sıralamaya döndü"}[new]
         if action == "v":
             if where == "draft" and d.get("status") != "pending":
@@ -1530,4 +1606,9 @@
             self.backfill_seo()
             try:
+                self.fix_texts()
+                self.backfill_appeal()
+            except Exception as e:  # noqa: BLE001
+                log.exception("Metin/ilgi puanı hatası: %s", e)
+            try:
                 self.backfill_photos(int(self.cfg.get("images", "photo_backfill_per_run", 5) or 0))
             except Exception as e:  # noqa: BLE001
--- a/haberbot/llm.py
+++ b/haberbot/llm.py
@@ -326,4 +326,7 @@
         if "stories" in schema.get("properties", {}):
             return self._triage(user)
+        if "scores" in schema.get("properties", {}):     # ilgi puanı
+            return {"scores": [{"id": ln.split(" | ")[0].strip(), "appeal": 6 + len(ln) % 3}
+                               for ln in user.splitlines() if " | " in ln]}
         if "body" not in schema.get("properties", {}):  # yalnızca SEO bilgisi
             t = re.search(r"TITLE: (.+)", user)
@@ -388,4 +391,5 @@
             "slug": "",
             "image_alt": f"{title[:80]} haberini temsil eden 3D görsel",
+            "appeal": 7 if kind == "official" else 6,
             "carousel_points": [f"{credit} bu gelişmeyi duyurdu (test maddesi).",
                                 "Gerçek kurulumda burada kaynaktan alınan somut bir bilgi yer alır.",
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -141,8 +141,10 @@
         "cover_text": {"type": "string"},
         "carousel_points": {"type": "array", "items": {"type": "string"}},
+        "appeal": {"type": "integer"},
     },
     "required": ["title", "summary", "body", "category", "tags", "confidence", "flags", "editor_note",
                  "short_title", "kicker", "hero_stat", "hero_stat_label", "visual_style", "visual_scene",
-                 "focus_keyword", "seo_title", "meta_description", "slug", "image_alt", "cover_text", "carousel_points"],
+                 "focus_keyword", "seo_title", "meta_description", "slug", "image_alt", "cover_text", "carousel_points",
+                 "appeal"],
     "additionalProperties": False,
 }
@@ -167,5 +169,6 @@
   and why it matters; skip deep technical specs, parameter counts, benchmark scores, version minutiae, financial jargon
   and long lists unless they are the heart of the story. Explain in plain everyday Turkish.
-- Keep product, model, game, car and company names in their original form. Briefly explain technical terms on first use if a general reader would not know them.
+- Always write with correct Turkish characters (ç, ğ, ı, ö, ş, ü, İ) in every field except slug; never write Turkish words in ASCII ("çıkış", not "cikis").
+- Keep product, model, game, car and company names in their original form, including lowercase-first names even at the start of a title or sentence ("iPhone 18 tanıtıldı", never "İPhone"; "eFootball", "iOS"). Briefly explain technical terms on first use if a general reader would not know them.
 - For startup stories, explain in one or two sentences what the company actually does and what problem it solves. For products and cars, include price, availability and the key specs when the sources give them. For games, include platforms and release date when given.
 - Money: "350 milyon dolar". Avoid "bugün/dün"; use explicit dates like "22 Eylül'de" when the sources give them.
@@ -190,4 +193,5 @@
 - flags (zero or more): iddia = based on unconfirmed reports, anonymous sources or rumors; hassas = death, violence, military, elections, allegations against individuals, medical/health claims, minors; yetersiz_bilgi = source text too thin to write reliably; celiski = sources conflict; eski = not actually new; tanitim = primarily promotional/sponsored/event marketing.
 - editor_note: ≤140 characters in Turkish for the human editor explaining any flag or uncertainty; "" if nothing to note.
+- appeal: integer 1–10, how strongly a broad Turkish audience (curious about technology, not specialists) would want to click and share this story. 9–10: huge mainstream news everyone talks about (a new iPhone or PlayStation, GTA 6 date, a major AI launch, big Türkiye tech news); 7–8: notable news about well-known brands, products, games, cars or surprising records; 5–6: interesting but niche; 1–4: specialist or industry-only. Be strict and honest; most stories are 5–7.
 
 Social/visual fields (used on Instagram cards and the site; the design is bold, colourful and premium, like an Apple product page):
@@ -247,5 +251,5 @@
 - meta_description: 140–156 characters, active voice, contains the focus_keyword, tells the reader what they will learn. No quotes, no emojis.
 - image_alt: ≤120 characters, describes the cover image (described in VISUAL) and relates it to the news topic.
-- tags: 3–6 searchable entities (companies, products, models, technologies, places) with official spelling. Never generic words like "teknoloji", "yapay zeka", "oyun", "otomobil", and never news outlet names."""
+- tags: 3–6 searchable entities (companies, products, models, technologies, places) with official spelling and correct Turkish characters. Never generic words like "teknoloji", "yapay zeka", "oyun", "otomobil", and never news outlet names."""
 
 
@@ -259,2 +263,27 @@
         post.get("body", ""),
     ])
+
+
+# ── 4) İlgi puanı (eski haberler için toplu) ──
+APPEAL_SCHEMA = {
+    "type": "object",
+    "properties": {
+        "scores": {"type": "array", "items": {"type": "object", "properties": {
+            "id": {"type": "string"}, "appeal": {"type": "integer"}}, "required": ["id", "appeal"],
+            "additionalProperties": False}},
+    },
+    "required": ["scores"],
+    "additionalProperties": False,
+}
+
+
+def appeal_system(site_name: str) -> str:
+    return f"""You are the homepage editor of "{site_name}", a Turkish technology news site. For each story below give "appeal":
+an integer 1–10 for how strongly a broad Turkish audience (curious about technology, not specialists) would want to click and share it.
+9–10: huge mainstream news everyone talks about (a new iPhone or PlayStation, GTA 6 date, a major AI launch, big Türkiye tech news);
+7–8: notable news about well-known brands, products, games, cars or surprising records; 5–6: interesting but niche;
+1–4: specialist or industry-only. Be strict and consistent; most stories are 5–7. Return one score per id."""
+
+
+def appeal_user(posts: list[dict]) -> str:
+    return "\n".join(f"{p['id']} | {p.get('title', '')} | {p.get('summary', '')}" for p in posts)
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -14,7 +14,8 @@
 from .config import CATEGORIES, DEFAULT_CATEGORY, ROOT, Config, category_color, category_label, category_seo, indexnow_key
 from .store import Store
+from .textfix import tag_display
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "9"
+ASSET_V = "10"
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
 H2_RE = re.compile(r"<h[1-3]>(.*?)</h[1-3]>", re.S)
@@ -63,4 +64,39 @@
     out.append(body_html[last:])
     return "".join(out), figs[len(use):]
+
+
+def follow_links(site: dict) -> list[dict]:
+    """Takip kanalları (ayarlarda yazılı olanlar) + RSS."""
+    out = []
+    ig = (site.get("instagram") or "").lstrip("@").strip()
+    if ig:
+        out.append({"key": "instagram", "label": "Instagram", "handle": "@" + ig, "url": f"https://www.instagram.com/{ig}/"})
+    tg = (site.get("telegram") or "").lstrip("@").strip()
+    if tg:
+        out.append({"key": "telegram", "label": "Telegram", "handle": "@" + tg, "url": f"https://t.me/{tg}"})
+    wa = (site.get("whatsapp") or "").strip()
+    if wa:
+        out.append({"key": "whatsapp", "label": "WhatsApp", "handle": "Kanal", "url": wa})
+    x = (site.get("x") or "").lstrip("@").strip()
+    if x:
+        out.append({"key": "x", "label": "X", "handle": "@" + x, "url": f"https://x.com/{x}"})
+    out.append({"key": "rss", "label": "RSS", "handle": "Besleme", "url": f"{site.get('url', '')}/feed.xml"})
+    return out
+
+
+def hot(p: dict, now=None) -> float:
+    """Ana sayfa sıralaması: ilgi puanı (1–10) × tazelik. Fotoğraflı kapak az öne çıkar; manşete sabitlenen haber
+    36 saat boyunca en üstte durur; "ana sayfada gösterme" denen haber hiç çıkmaz (kategoride kalır)."""
+    home = p.get("home")
+    if home == "hide":
+        return -1.0
+    age = max(0.0, hours_since(p.get("published_at")))
+    base = float(p.get("appeal") or max(5, int(p.get("importance") or 6) - 1))
+    if (p.get("image") or {}).get("source") == "photo":
+        base += 1.0
+    score = base / (age + 4) ** 0.7
+    if home == "pin" and hours_since(p.get("home_at") or p.get("published_at")) < 36:
+        score += 100          # editör manşete sabitledi: 36 saat en üstte
+    return score
 
 
@@ -184,9 +220,12 @@
             ts = tag_slug(t)
             if ts and ts not in self.skip_tags and len(tags) < 6:
-                tags.append({"label": t, "slug": ts, "url": f"{b}/etiket/{ts}/"})
+                tags.append({"label": tag_display(t), "slug": ts, "url": f"{b}/etiket/{ts}/"})
         cat = p.get("category", DEFAULT_CATEGORY)
         return {
             **p,
             "url": f"{b}/haber/{p['slug']}/",
+            "ts": int(dt.timestamp()),
+            "hot": hot(p),
+            "photo_cover": (p.get("image") or {}).get("source") == "photo",
             "title_disp": nobr_hyphen(title),
             "short_disp": nobr_hyphen(short),
@@ -270,14 +309,21 @@
 
     @staticmethod
-    def _featured(posts: list[dict], n: int) -> list[dict]:
-        """Manşet: son 3 günün en önemli haberleri (eşitlikte en yenisi); yetmezse en yeniler."""
-        fresh = [p for p in posts if hours_since(p.get("published_at")) <= 72]
-        pick = sorted(fresh, key=lambda p: (-int(p.get("importance") or 5), -(parse_iso(p.get("published_at")) or now_utc()).timestamp()))[:n]
-        for p in posts:
-            if len(pick) >= n:
-                break
-            if p not in pick:
-                pick.append(p)
-        return pick
+    def _home(posts: list[dict], n_feat: int) -> dict:
+        """Ana sayfa seçkisi. Her onaylanan haber ana sayfaya çıkmaz: en dikkat çekiciler (ilgi × tazelik) seçilir,
+        bir haber sayfada yalnızca bir kez görünür. Tüm haberler kategori ve "Tüm haberler" sayfalarında durur."""
+        visible = [p for p in posts if p["hot"] >= 0]
+        ranked = sorted(visible, key=lambda p: -p["hot"])
+        fresh = [p for p in ranked if hours_since(p.get("published_at")) <= 72 or p["hot"] >= 100]  # sabitlenen her zaman
+        featured = (fresh + [p for p in ranked if p not in fresh])[:n_feat]
+        shown = {p["id"] for p in featured}
+        top = [p for p in ranked if p["id"] not in shown][:6]
+        shown |= {p["id"] for p in top}
+        latest = [p for p in visible if p["id"] not in shown and hours_since(p.get("published_at")) <= 48][:6]
+        shown |= {p["id"] for p in latest}
+        # "Kaçırmış olabilirsin": son iki haftanın ilgi çekici haberlerinden her ziyarette farklı dördü (tarayıcıda seçilir)
+        pool = sorted((p for p in visible if p["id"] not in shown and hours_since(p.get("published_at")) <= 24 * 14),
+                      key=lambda p: (-(p.get("appeal") or 5), -p["ts"]))[:16]
+        return {"featured": featured, "top": top, "latest": latest, "discover": pool, "shown": shown,
+                "ranked": ranked}
 
     def build(self) -> int:
@@ -335,4 +381,5 @@
             "verify": {k: seo.get(k) for k in ("google_site_verification", "bing_site_verification", "yandex_verification")},
         }
+        site["follow"] = follow_links(site)
         ctx = {"site": site}
 
@@ -355,36 +402,41 @@
                     shutil.copy2(src, out / "img" / name)
 
-        # ana sayfa: manşet + son haberler; devamı arşiv sayfalarında
-        n_feat = int(seo.get("featured_count", 5) or 5)
-        featured = self._featured(posts, n_feat)
+        # ana sayfa: seçki (manşet, öne çıkanlar, son dakika, kaçırmış olabilirsin, kategori şeritleri)
+        n_feat = int((cfg.raw.get("home") or {}).get("featured_count") or seo.get("featured_count", 5) or 5)
+        home = self._home(posts, n_feat)
+        featured = home["featured"]
         for p in featured:
             src = cfg.images_dir / p["img"].rsplit("/", 1)[-1]
             p["slide_bg"], p["slide_dark"] = edge_color(src)
-        rest = [p for p in posts if p not in featured]
-        latest = rest[:12] if len(rest) >= 3 else posts[:6]
-        if len(latest) > 3:
-            latest = latest[:len(latest) - len(latest) % 3]
-        shown = {p["id"] for p in featured} | {p["id"] for p in latest}
-        archive = [p for p in posts if p["id"] not in shown]
-        per = int(cfg.site.get("posts_per_page", 18))
-        pages = 1 + (len(archive) + per - 1) // per
+        shown = set(home["shown"])
         rails = []
         for c in sorted(cats, key=lambda c: -c["count"]):
-            cp = [p for p in posts if p["category"] == c["slug"]]
-            if len(cp) >= 4 and len(rails) < 3:
-                rails.append({"cat": c, "posts": cp[:10]})
+            cp = [p for p in home["ranked"] if p["category"] == c["slug"] and p["id"] not in shown][:8]
+            if len(cp) >= 3 and len(rails) < 3:
+                rails.append({"cat": c, "posts": cp})
+        per = int(cfg.site.get("posts_per_page", 18))
+        pages = max(1, (len(posts) + per - 1) // per)
         self._write("index.html", self.env.get_template("index.html").render(
-            **ctx, featured=featured, latest=latest, rails=rails, tags=site["top_tags"],
+            **ctx, featured=featured, top=home["top"], latest=home["latest"], discover=home["discover"],
+            rails=rails, tags=site["top_tags"],
             latest_iso=max((q["iso"] for q in posts), default=site["built_iso"]),
             latest_str=tr_date(max((q.get("published_at") or "" for q in posts), default=None), cfg.tz),
-            page=1, pages=pages, next_url=f"{b}/sayfa/2/" if pages > 1 else None,
-            canonical=cfg.site_url + "/"))
-        for n in range(2, pages + 1):
-            chunk = archive[(n - 2) * per:(n - 1) * per]
-            self._write(f"sayfa/{n}/index.html", self.env.get_template("archive.html").render(
-                **ctx, posts=chunk, page=n, pages=pages,
-                prev_url=f"{b}/" if n == 2 else f"{b}/sayfa/{n - 1}/",
-                next_url=f"{b}/sayfa/{n + 1}/" if n < pages else None,
-                canonical=f"{cfg.site_url}/sayfa/{n}/"))
+            all_url=f"{b}/haberler/", canonical=cfg.site_url + "/"))
+        # tüm haberler (kronolojik, sayfalı): /haberler/, /haberler/sayfa/2/ …
+        for n in range(1, pages + 1):
+            chunk = posts[(n - 1) * per:n * per]
+            url = lambda k: f"{b}/haberler/" if k == 1 else f"{b}/haberler/sayfa/{k}/"  # noqa: E731
+            rel = "haberler/index.html" if n == 1 else f"haberler/sayfa/{n}/index.html"
+            self._write(rel, self.env.get_template("archive.html").render(
+                **ctx, posts=chunk, page=n, pages=pages, total=len(posts),
+                prev_url=url(n - 1) if n > 1 else None, next_url=url(n + 1) if n < pages else None,
+                canonical=cfg.site_url + url(n)[len(b):]))
+        # eski arşiv adresleri (/sayfa/N/) yeni sayfalara yönlenir
+        for n in range(2, pages + 2):
+            target = f"{cfg.site_url}/haberler/" if n - 1 <= 1 else f"{cfg.site_url}/haberler/sayfa/{n - 1}/"
+            self._write(f"sayfa/{n}/index.html",
+                        f'<!doctype html><meta charset="utf-8"><title>Tüm haberler</title><meta name="robots" content="noindex">'
+                        f'<link rel="canonical" href="{target}"><meta http-equiv="refresh" content="0; url={target}">'
+                        f'<a href="{target}">Tüm haberler</a>')
 
         # haber sayfaları
@@ -394,6 +446,10 @@
                              key=lambda q: (-(len(same_tag & {t["slug"] for t in q["tag_list"]}) * 2
                                               + (q["category"] == p["category"])), posts.index(q)))[:8]
+            # sıradaki haber: aynı kategoriden en dikkat çekici güncel haber, yoksa genel seçkiden
+            pool = [q for q in home["ranked"][:24] if q["id"] != p["id"]]
+            nxt = next((q for q in pool if q["category"] == p["category"]), pool[0] if pool else None)
+            related = [q for q in related if not nxt or q["id"] != nxt["id"]]
             self._write(f"haber/{p['slug']}/index.html", self.env.get_template("article.html").render(
-                **ctx, post=p, related=related, canonical=p["abs_url"]))
+                **ctx, post=p, related=related, next_post=nxt, canonical=p["abs_url"]))
 
         # kategoriler
@@ -421,4 +477,12 @@
             **ctx, posts=posts, cats=[c for c in cats if c["count"]], tags=[t for t in tags if t["count"] >= 2],
             pages=pages))
+        # ana ekrana eklenebilir site (PWA bildirimi)
+        self._write("manifest.webmanifest", json.dumps({
+            "name": cfg.site.get("name", "Smarity"), "short_name": cfg.site.get("name", "Smarity"),
+            "description": cfg.site.get("tagline", ""), "lang": "tr", "start_url": f"{b}/?kaynak=uygulama",
+            "scope": f"{b}/", "display": "standalone", "background_color": "#FFFFFF", "theme_color": "#FFFFFF",
+            "icons": [{"src": f"{b}/static/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
+                      {"src": f"{b}/static/logo.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}]},
+            ensure_ascii=False, indent=1))
         news = [p for p in posts if hours_since(p.get("published_at")) <= 48][:1000]
         self._write("news-sitemap.xml", self.env.get_template("news-sitemap.xml").render(**ctx, posts=news))
--- a/static/site.js
+++ b/static/site.js
@@ -1,3 +1,104 @@
 (function () {
+  // ── Kişisel hafıza (yalnızca bu tarayıcıda): son ziyaret, okunan haberler, görülen manşetler ──
+  function load(k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
+  function save(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
+  var NOW = Math.floor(Date.now() / 1000);
+  var read = load("sm_read", {});          // {id: zaman}
+  var seen = load("sm_seen", {});          // manşette gösterilenler {id: zaman}
+  function prune(o, max) { var ks = Object.keys(o).sort(function (a, b) { return o[b] - o[a]; }); ks.slice(max).forEach(function (k) { delete o[k]; }); return o; }
+
+  // Haber sayfası: okundu olarak işaretle
+  var art = document.querySelector("[data-read]");
+  if (art) { read[art.getAttribute("data-read")] = NOW; save("sm_read", prune(read, 400)); }
+
+  // Son ziyaret: 30 dakikadan uzun aradan sonra gelinirse "yeni" sayılır
+  var visit = load("sm_visit", null), since = 0;
+  if (visit && NOW - visit.last > 1800) { since = visit.last; visit = { last: NOW, prev: visit.last }; }
+  else if (visit) { since = visit.prev || 0; visit.last = NOW; }
+  else { visit = { last: NOW, prev: 0 }; }
+  save("sm_visit", visit);
+
+  var isHome = !!document.querySelector(".car");
+  var items = document.querySelectorAll("[data-id][data-ts]");
+  var newIds = {};
+  items.forEach(function (el) {
+    var id = el.getAttribute("data-id"), ts = +el.getAttribute("data-ts");
+    var top = el.querySelector(".card-top, .row-cat, .slide-top");
+    if (read[id]) {
+      el.classList.add("is-read");
+      if (top) top.insertAdjacentHTML("beforeend", '<span class="badge read">Okundu</span>');
+    } else if (since && ts > since) {
+      newIds[id] = 1;
+      el.classList.add("is-new");
+      if (top) top.insertAdjacentHTML("beforeend", '<span class="badge new">Yeni</span>');
+    }
+  });
+  var nNew = Object.keys(newIds).length;
+  var banner = document.querySelector("[data-since]");
+  if (banner && nNew) {
+    banner.querySelector("[data-since-text]").textContent = "Son ziyaretinden beri " + nNew + " yeni haber";
+    banner.hidden = false;
+  }
+
+  if (isHome) {
+    // Öne çıkanlar: okunanlar sona
+    var grid = document.querySelector("[data-top]");
+    if (grid) Array.prototype.slice.call(grid.children).filter(function (c) { return c.classList.contains("is-read"); })
+      .forEach(function (c) { grid.appendChild(c); });
+    // Kaçırmış olabilirsin: her ziyarette okunmamışlardan farklı dört haber
+    var disc = document.querySelector("[data-discover]");
+    if (disc) {
+      var all = Array.prototype.slice.call(disc.querySelectorAll(".disc-item"));
+      var unread = all.filter(function (d) { return !d.querySelector(".is-read"); });
+      var rest = all.filter(function (d) { return unread.indexOf(d) < 0; });
+      function shuffle(a) { for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
+      var pick = shuffle(unread).concat(shuffle(rest)).slice(0, 4);
+      all.forEach(function (d) { d.hidden = pick.indexOf(d) < 0; });
+      pick.forEach(function (d) {
+        disc.appendChild(d);
+        // aynı haber aşağıdaki kategori şeritlerinde tekrar görünmesin
+        var id = d.querySelector("[data-id]").getAttribute("data-id");
+        document.querySelectorAll('.rail [data-id="' + id + '"]').forEach(function (r) { r.remove(); });
+      });
+    }
+    // Manşet: okunmamış ve son 12 saatte görülmemiş haberler önce (her girişte aynı manşet görünmesin)
+    var track = document.getElementById("car-track");
+    if (track) {
+      var sl = Array.prototype.slice.call(track.querySelectorAll(".slide"));
+      function rank(s) { var id = s.getAttribute("data-id"); return read[id] ? 2 : (seen[id] && NOW - seen[id] < 43200) ? 1 : 0; }
+      var ordered = sl.map(function (s, i) { return [rank(s), i, s]; }).sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
+      if (ordered.some(function (x, k) { return x[1] !== k; })) {
+        var dots = document.querySelector(".car-dots"), db = dots ? Array.prototype.slice.call(dots.children) : [];
+        ordered.forEach(function (x, k) {
+          track.appendChild(x[2]);
+          x[2].setAttribute("aria-label", (k + 1) + " / " + sl.length);
+          x[2].querySelector(".slide-img") && (x[2].querySelector(".slide-img").loading = k === 0 ? "eager" : "lazy");
+          if (db[x[1]]) dots.appendChild(db[x[1]]);
+        });
+        if (dots) Array.prototype.slice.call(dots.children).forEach(function (b, k) { b.setAttribute("data-go", k); if (k === 0) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current"); });
+      }
+      window.__smSeen = function (id) { seen[id] = Math.floor(Date.now() / 1000); save("sm_seen", prune(seen, 120)); };
+    }
+  }
+
+  // Yerel paylaşım (telefonlarda paylaş menüsü)
+  document.querySelectorAll("[data-share]").forEach(function (b) {
+    if (!navigator.share) return;
+    b.hidden = false;
+    b.addEventListener("click", function () {
+      navigator.share({ title: b.getAttribute("data-title"), url: b.getAttribute("data-url") }).catch(function () {});
+    });
+  });
+
+  // Ana ekrana ekle (destekleyen tarayıcılarda)
+  var installEvt = null;
+  window.addEventListener("beforeinstallprompt", function (e) {
+    e.preventDefault(); installEvt = e;
+    document.querySelectorAll("[data-install]").forEach(function (b) { b.hidden = false; });
+  });
+  document.querySelectorAll("[data-install]").forEach(function (b) {
+    b.addEventListener("click", function () { if (installEvt) { installEvt.prompt(); installEvt = null; b.hidden = true; } });
+  });
+
   // Göreli zaman: "12 dk önce"
   var now = Date.now();
@@ -6,5 +107,7 @@
     if (!d) return;
     var m = Math.round((now - d) / 60000);
-    var s = m < 1 ? "az önce" : m < 60 ? m + " dk önce" : m < 1440 ? Math.round(m / 60) + " saat önce" : m < 10080 ? Math.round(m / 1440) + " gün önce" : null;
+    var sh = t.getAttribute("data-rel") === "short";
+    var s = m < 1 ? "az önce" : m < 60 ? m + " dk" + (sh ? "" : " önce") : m < 1440 ? Math.round(m / 60) + (sh ? " sa" : " saat önce")
+      : m < 10080 ? Math.round(m / 1440) + " gün" + (sh ? "" : " önce") : null;
     if (s) { t.title = t.textContent; t.textContent = s; }
     if (t.hasAttribute("data-live") && m > 180) { var l = t.closest(".live"); if (l) l.classList.add("stale"); }
@@ -74,5 +177,5 @@
     var dots = Array.prototype.slice.call(car.querySelectorAll(".car-dots button"));
     var play = car.querySelector(".car-play");
-    if (!track || slides.length < 2) { if (slides[0]) slides[0].classList.add("on"); return; }
+    if (!track || slides.length < 2) { if (slides[0]) { slides[0].classList.add("on"); if (window.__smSeen) window.__smSeen(slides[0].getAttribute("data-id")); } return; }
     var dur = +car.getAttribute("data-interval") || 6500;
     car.style.setProperty("--dur", dur + "ms");
@@ -83,4 +186,5 @@
       if (i === cur && slides[i].classList.contains("on")) return;
       cur = i;
+      if (window.__smSeen) { var sid = slides[i].getAttribute("data-id"); clearTimeout(car.__seenT); car.__seenT = setTimeout(function () { window.__smSeen(sid); }, 2500); }
       slides.forEach(function (s, k) { s.classList.toggle("on", k === i); s.setAttribute("aria-hidden", k === i ? "false" : "true");
         s.querySelector("a").tabIndex = k === i ? 0 : -1; });
--- a/static/style.css
+++ b/static/style.css
@@ -24,5 +24,5 @@
 html { -webkit-text-size-adjust: 100%; scroll-behavior: smooth; }
 body { margin: 0; background: var(--bg); color: var(--ink); font: 400 17px/1.47 var(--font);
-  letter-spacing: -.012em; -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }
+  letter-spacing: -.006em; -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; font-kerning: normal; }
 a { color: inherit; text-decoration: none; }
 img { max-width: 100%; height: auto; display: block; }
@@ -74,5 +74,6 @@
   -webkit-backdrop-filter: blur(20px); backdrop-filter: blur(20px); padding: 20px 24px 32px; display: grid; gap: 4px;
   border-bottom: 1px solid var(--line); box-shadow: 0 30px 60px rgba(0,0,0,.08); }
-.menu-panel a { font-size: 26px; font-weight: 600; letter-spacing: -.02em; padding: 6px 0; }
+.menu-panel a { font-size: 26px; font-weight: 600; letter-spacing: -.02em; padding: 6px 0; display: flex; align-items: center; gap: 12px; }
+.menu-panel a i { width: 10px; height: 10px; border-radius: 50%; background: var(--c); }
 @media (min-width: 900px) { .nav-links { display: flex; } .menu { display: none; } }
 
@@ -108,5 +109,5 @@
 .stat-chip { background: rgba(255,255,255,.72); color: var(--ink); font-weight: 500; }
 .stat-chip b { font-weight: 700; }
-.slide h2 { margin: 0; font-size: clamp(26px, 3.3vw, 46px); line-height: 1.08; letter-spacing: -.035em; font-weight: 700; text-wrap: balance; }
+.slide h2 { margin: 0; font-size: clamp(26px, 3.3vw, 46px); line-height: 1.08; letter-spacing: -.03em; font-weight: 700; text-wrap: balance; }
 .slide-dek { font-size: 17px; line-height: 1.45; color: var(--ink-2); max-width: 46ch;
   overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; }
@@ -158,4 +159,8 @@
 .chip-link span { color: var(--muted); font-size: 13px; }
 .chip-link:hover { background: #E8E8ED; }
+.chip-link.all { background: none; color: var(--link); padding-inline: 6px; }
+.chip-link.all span { color: var(--link); font-size: 17px; line-height: 1; }
+.chips.center { justify-content: center; padding-block: 0 36px; }
+.sec-tight { padding-top: 4px; }
 .tags { display: flex; flex-wrap: wrap; gap: 10px; }
 .tags a { display: inline-flex; gap: 8px; align-items: baseline; padding: 10px 16px; border-radius: 999px; border: 1px solid var(--line); font-size: 16px; font-weight: 500; }
@@ -196,5 +201,5 @@
 .rcard img { aspect-ratio: 4 / 3; object-fit: cover; width: 100%; }
 .rcard-body { padding: 18px 22px 24px; display: grid; gap: 6px; }
-.rcard h3 { margin: 0; font-size: 21px; line-height: 1.2; letter-spacing: -.025em; font-weight: 700; text-wrap: pretty; }
+.rcard h3 { margin: 0; font-size: 20px; line-height: 1.24; letter-spacing: -.016em; font-weight: 700; text-wrap: pretty; }
 .rcard .t { font-size: 14px; color: var(--muted); }
 .bg-alt { background: var(--bg-alt); }
@@ -209,5 +214,5 @@
 .card img { aspect-ratio: 4 / 3; object-fit: cover; width: 100%; transition: transform .8s var(--ease); }
 .card:hover img { transform: scale(1.04); }
-.card h2, .card h3 { margin: 0; font-size: 21px; line-height: 1.22; letter-spacing: -.025em; font-weight: 700; text-wrap: pretty; }
+.card h2, .card h3 { margin: 0; font-size: 21px; line-height: 1.24; letter-spacing: -.016em; font-weight: 700; text-wrap: pretty; }
 .card h2 a:hover, .card h3 a:hover { color: var(--link); }
 .card-dek { margin: 0; font-size: 15px; line-height: 1.45; color: var(--ink-2); overflow: hidden;
@@ -221,6 +226,6 @@
   .card .ph { grid-area: ph; align-self: start; border-radius: 14px; }
   .card img { aspect-ratio: 4 / 3; }
-  .card .eyebrow { grid-area: eb; }
-  .card h2, .card h3 { grid-area: h; font-size: 18px; line-height: 1.25; }
+  .card .card-top { grid-area: eb; }
+  .card h2, .card h3 { grid-area: h; font-size: 17.5px; line-height: 1.28; letter-spacing: -.008em; }
   .card-dek { display: none; }
   .card .t { grid-area: t; font-size: 13px; }
@@ -229,4 +234,6 @@
 .pager { display: flex; justify-content: center; align-items: center; gap: 20px; margin-top: 64px; font-size: 17px; }
 .pager a { color: var(--link); }
+.more.back::after { content: none; }
+.more.back::before { content: "‹"; font-size: 1.25em; line-height: 1; transform: translateY(-1px); }
 
 /* ── konum (breadcrumb) ───────────────── */
@@ -246,5 +253,6 @@
 .art-head { padding-block: 22px 0; }
 .art-head .meta-top { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; font-size: 14px; font-weight: 600; }
-.art-head .meta-top .eyebrow { font-size: 13px; text-transform: uppercase; letter-spacing: .06em; }
+.art-head .meta-top .eyebrow { font-size: 13px; text-transform: uppercase; letter-spacing: .07em; font-kerning: none; }
+.facts-title, .why strong, .sources h2, .next-label { font-kerning: none; }
 .art-head .meta-top time, .art-head .meta-top .muted { color: var(--muted); font-weight: 400; }
 .art-head h1 { margin: 12px 0 0; font-size: clamp(30px, 4.4vw, 46px); line-height: 1.1; letter-spacing: -.035em; font-weight: 700; text-wrap: balance; }
@@ -376,12 +384,93 @@
 
 /* ── alt bilgi ─────────────────────────── */
-.foot { background: var(--bg-alt); margin-top: 96px; padding-block: 36px 48px; font-size: 12px; line-height: 1.5; color: var(--muted); }
-.foot-in { display: grid; gap: 14px; }
+.foot { background: var(--bg-alt); margin-top: 96px; padding-block: 48px 40px; font-size: 14px; line-height: 1.5; color: var(--muted); }
+.foot-in { display: grid; gap: 32px 24px; grid-template-columns: 1fr 1fr; }
+.foot-brand { grid-column: 1 / -1; display: grid; gap: 10px; max-width: 46ch; }
+.foot-brand p { margin: 0; color: var(--ink-2); font-size: 15px; }
+.foot-brand .foot-note { font-size: 13px; color: var(--muted); }
 .foot .brand { font-size: 15px; color: var(--ink); }
-.foot-cats { display: flex; flex-wrap: wrap; gap: 8px 20px; padding-block: 14px; border-block: 1px solid var(--line); }
-.foot-cats a { color: var(--ink-2); }
-.foot-tags { border-top: 0; padding-top: 0; }
-.foot-cats a:hover, .foot a:hover { text-decoration: underline; }
-.foot p { margin: 0; }
+.foot-col { display: grid; gap: 8px; align-content: start; }
+.foot-col h2 { margin: 0 0 4px; font-size: 13px; font-weight: 600; color: var(--ink); letter-spacing: 0; }
+.foot-col a { color: var(--ink-2); width: fit-content; }
+.foot-tags { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 6px 18px; padding-top: 20px; border-top: 1px solid var(--line); font-size: 13px; }
+.foot-tags a { color: var(--muted); }
+.foot-copy { grid-column: 1 / -1; margin: 0; font-size: 12px; }
+.foot a:hover { color: var(--ink); text-decoration: underline; text-underline-offset: 3px; }
+@media (min-width: 800px) { .foot-in { grid-template-columns: 2fr 1fr 1fr 1fr; } .foot-brand { grid-column: auto; } }
+
+/* ── yeni / okundu işaretleri ──────────── */
+.card-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
+.badge { display: inline-flex; align-items: center; font-size: 11px; font-weight: 700; line-height: 1; padding: 4px 7px; border-radius: 999px;
+  letter-spacing: .02em; }
+.badge.new { background: #E6F9EC; color: #0B7A33; }
+.badge.read { background: var(--bg-alt); color: var(--muted); font-weight: 600; }
+.row-cat .badge { margin-left: 4px; font-size: 10px; padding: 3px 6px; }
+.slide-top .badge { font-size: 12px; padding: 6px 10px; }
+.slide.dark .badge.new { background: rgba(48, 209, 88, .22); color: #7CF0A0; }
+.is-read .ph img, .is-read > img, .is-read .row-img img { filter: saturate(.55); opacity: .72; }
+.is-read h2 a, .is-read h3 a, .is-read h3, .is-read .row-title { color: var(--ink-2); }
+.since { display: flex; align-items: center; gap: 8px; margin-block: -4px 14px; font-size: 14px; color: var(--ink-2); }
+.since[hidden] { display: none; }
+.since a { color: var(--link); }
+.since-dot { width: 8px; height: 8px; border-radius: 50%; background: #30D158; }
+
+/* ── son dakika listesi ─────────────────── */
+.rows { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: 1fr; column-gap: 40px; }
+@media (min-width: 900px) { .rows { grid-template-columns: 1fr 1fr; } }
+.row a { display: grid; grid-template-columns: 64px minmax(0, 1fr) 92px; gap: 14px; align-items: center; padding: 16px 0; border-bottom: 1px solid #E8E8ED; }
+.row time { font-size: 13px; color: var(--muted); font-variant-numeric: tabular-nums; }
+.row-main { display: grid; gap: 4px; min-width: 0; }
+.row-cat { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: color-mix(in srgb, var(--c) 78%, #000); }
+.row-cat i { width: 7px; height: 7px; border-radius: 50%; background: var(--c); }
+.row-title { font-size: 17px; font-weight: 600; line-height: 1.3; letter-spacing: -.01em; overflow: hidden;
+  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
+.row a:hover .row-title { color: var(--link); }
+.row-img { border-radius: 12px; overflow: hidden; background: var(--bg-alt); }
+.row-img img { aspect-ratio: 4 / 3; object-fit: cover; width: 100%; }
+@media (max-width: 599px) { .row a { grid-template-columns: minmax(0, 1fr) 84px; } .row time { grid-column: 1 / -1; order: -1; margin-bottom: -8px; } }
+
+/* ── kaçırmış olabilirsin (4'lü) ────────── */
+@media (min-width: 1000px) { .grid-4 { grid-template-columns: repeat(4, 1fr); } .grid-4 .card h3 { font-size: 18.5px; } }
+.disc-item[hidden] { display: none; }
+.disc-item { display: contents; }
+
+/* ── takip et ───────────────────────────── */
+.follow { margin-top: 72px; padding: 32px; border-radius: var(--r-lg); display: grid; gap: 22px; align-items: center;
+  background: radial-gradient(120% 140% at 0% 0%, #EAF2FF 0%, #F2FBF7 55%, #F5F5F7 100%); border: 1px solid #E6EAF2; }
+@media (min-width: 900px) { .follow { grid-template-columns: minmax(0, 1fr) auto; padding: 40px 44px; } }
+.follow h2 { margin: 0; font-size: clamp(26px, 3vw, 36px); letter-spacing: -.035em; line-height: 1.08; }
+.follow p { margin: 8px 0 0; color: var(--ink-2); max-width: 48ch; }
+.follow-links { display: flex; flex-wrap: wrap; gap: 10px; }
+.fl { display: inline-flex; align-items: center; gap: 10px; padding: 12px 18px 12px 14px; border-radius: 16px; background: #fff; border: 1px solid #E3E6EC;
+  box-shadow: 0 2px 8px rgba(0,0,0,.04); cursor: pointer; font: inherit; transition: transform .2s var(--ease), box-shadow .2s var(--ease); }
+.fl:hover { transform: translateY(-1px); box-shadow: 0 6px 18px rgba(0,0,0,.08); }
+.fl[hidden] { display: none; }
+.fl-ic { width: 10px; height: 10px; border-radius: 50%; background: var(--grad); flex: none; }
+.fl-t { display: grid; line-height: 1.2; text-align: left; }
+.fl-t b { font-size: 15px; font-weight: 700; color: var(--ink); }
+.fl-t span { font-size: 12.5px; color: var(--muted); }
+.fl-t::after { content: none; }
+.follow.compact { margin-top: 40px; padding: 26px 28px; }
+.follow.compact h2 { font-size: 24px; }
+.follow.compact p { font-size: 15px; }
+
+/* ── sıradaki haber ─────────────────────── */
+.next { margin-top: 40px; }
+.next-label { display: block; font-size: 13px; font-weight: 700; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); margin-bottom: 12px; }
+.next-in { display: grid; gap: 18px; padding: 16px; border-radius: var(--r-md); background: #fff; border: 1px solid #E8E8ED;
+  box-shadow: 0 4px 20px rgba(0,0,0,.05); transition: box-shadow .3s var(--ease), transform .3s var(--ease); }
+.next-in:hover { box-shadow: 0 10px 30px rgba(0,0,0,.09); transform: translateY(-2px); }
+@media (min-width: 640px) { .next-in { grid-template-columns: 44% minmax(0, 1fr); align-items: center; } }
+.next-img { border-radius: 14px; overflow: hidden; }
+.next-img img { aspect-ratio: 4 / 3; object-fit: cover; width: 100%; }
+.next-txt { display: grid; gap: 8px; }
+.next-title { font-size: 23px; font-weight: 700; line-height: 1.2; letter-spacing: -.02em; text-wrap: pretty; }
+.next-dek { font-size: 15px; color: var(--ink-2); overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; }
+.next-in:hover .next-title { color: var(--link); }
+
+/* paylaş: yerel paylaşım düğmesi öne çıkar */
+.share .sh-native { background: var(--ink); color: #fff; }
+.share .sh-native:hover { background: #000; }
+.share .sh-native[hidden] { display: none; }
 
 /* ── hareket: kaydırmaya bağlı (destekleyen tarayıcılarda) ── */
--- a/templates/_macros.html
+++ b/templates/_macros.html
@@ -3,8 +3,9 @@
 {% endmacro %}
 
+{# Kart: kategori etiketi her yerde aynı (kategori adı), data-id/data-ts "yeni" ve "okundu" işaretleri için #}
 {% macro card(p, dek=true, heading='h3') %}
-<article class="card reveal" style="--c:{{ p.cat_color }}">
+<article class="card reveal" style="--c:{{ p.cat_color }}" data-id="{{ p.id }}" data-ts="{{ p.ts }}">
   <a class="ph" href="{{ p.url }}" tabindex="-1" aria-hidden="true">{{ img(p) }}</a>
-  <a class="eyebrow sm" href="{{ p.cat_url }}">{{ p.cat_label }}</a>
+  <div class="card-top"><a class="eyebrow sm" href="{{ p.cat_url }}">{{ p.cat_label }}</a></div>
   <{{ heading }}><a href="{{ p.url }}">{{ p.title_disp }}</a></{{ heading }}>
   {% if dek %}<p class="card-dek">{{ p.summary }}</p>{% endif %}
@@ -14,8 +15,8 @@
 
 {% macro rcard(p) %}
-<a class="rcard" href="{{ p.url }}" style="--c:{{ p.cat_color }}">
+<a class="rcard" href="{{ p.url }}" style="--c:{{ p.cat_color }}" data-id="{{ p.id }}" data-ts="{{ p.ts }}">
   {{ img(p) }}
   <div class="rcard-body">
-    <span class="eyebrow sm">{{ p.kicker_disp }}</span>
+    <span class="card-top"><span class="eyebrow sm">{{ p.cat_label }}</span></span>
     <h3>{{ p.title_disp }}</h3>
     <span class="t"><time datetime="{{ p.iso }}" data-rel>{{ p.date_str }}</time> · {{ p.credits|join(', ') }}</span>
@@ -24,10 +25,24 @@
 {% endmacro %}
 
+{# Son dakika satırı: saat, kategori noktası, başlık #}
+{% macro row(p) %}
+<li class="row" style="--c:{{ p.cat_color }}" data-id="{{ p.id }}" data-ts="{{ p.ts }}">
+  <a href="{{ p.url }}">
+    <time datetime="{{ p.iso }}" data-rel="short">{{ p.date_str }}</time>
+    <span class="row-main">
+      <span class="row-cat"><i aria-hidden="true"></i>{{ p.cat_label }}</span>
+      <span class="row-title">{{ p.title_disp }}</span>
+    </span>
+    <span class="row-img" aria-hidden="true">{{ img(p) }}</span>
+  </a>
+</li>
+{% endmacro %}
+
 {% macro slide(p, i, n) %}
-<article class="slide{{ ' dark' if p.slide_dark }}" role="group" aria-roledescription="slayt" aria-label="{{ i }} / {{ n }}" style="--c:{{ p.cat_color }}; --sbg:{{ p.slide_bg or '#F5F5F7' }}" data-i="{{ i - 1 }}">
+<article class="slide{{ ' dark' if p.slide_dark }}" role="group" aria-roledescription="slayt" aria-label="{{ i }} / {{ n }}" style="--c:{{ p.cat_color }}; --sbg:{{ p.slide_bg or '#F5F5F7' }}" data-i="{{ i - 1 }}" data-id="{{ p.id }}" data-ts="{{ p.ts }}">
   <a class="slide-in" href="{{ p.url }}">
     <span class="slide-txt">
       <span class="slide-top">
-        <span class="chip">{{ p.kicker_disp }}</span>
+        <span class="chip">{{ p.cat_label }}</span>
         {% if p.hero_stat and not p.stat_on_cover %}<span class="chip stat-chip"><b>{{ p.hero_stat }}</b>{% if p.hero_stat_label %} {{ p.hero_stat_label }}{% endif %}</span>{% endif %}
       </span>
@@ -60,4 +75,23 @@
 {% endmacro %}
 
+{# Takip bölümü: ayarlarda yazılı kanallar + RSS #}
+{% macro follow(site, compact=false) %}
+{% set ch = site.follow|default([]) %}
+<section class="follow{{ ' compact' if compact }}" aria-labelledby="h-takip{{ '-c' if compact }}">
+  <div class="follow-txt">
+    <h2 id="h-takip{{ '-c' if compact }}">{{ site.name }}'yi takip et.</h2>
+    <p>Yeni ürünler, yapay zeka ve oyun dünyasından önemli gelişmeler, her gün kaynağıyla ve Türkçe.</p>
+  </div>
+  <div class="follow-links">
+    {% for f in ch %}
+    <a class="fl fl-{{ f.key }}" href="{{ f.url }}"{% if f.key != 'rss' %} rel="noopener" target="_blank"{% endif %}>
+      <span class="fl-ic" aria-hidden="true"></span><span class="fl-t"><b>{{ f.label }}</b><span>{{ f.handle }}</span></span>
+    </a>
+    {% endfor %}
+    <button type="button" class="fl fl-app" data-install hidden><span class="fl-ic" aria-hidden="true"></span><span class="fl-t"><b>Ana ekrana ekle</b><span>Uygulama gibi aç</span></span></button>
+  </div>
+</section>
+{% endmacro %}
+
 {% macro crumbs(items, cls='wrap') %}
 {# items: [(ad, göreli_url, mutlak_url), ...] #}
--- a/templates/about.html
+++ b/templates/about.html
@@ -11,5 +11,5 @@
   <h2>Nasıl çalışıyoruz?</h2>
   <p>{{ site.name }}, teknoloji şirketlerinin resmi duyurularını; dünyanın ve Türkiye'nin saygın teknoloji, girişim, otomobil ve oyun yayınlarını düzenli olarak tarar. Gerçekten yeni ve önemli olan gelişmeler seçilir, yapay zeka yardımıyla Türkçe olarak özgün biçimde derlenir ve editör onayıyla yayımlanır.</p>
-  <h2>Yayın ilkelerimiz</h2>
+  <h2 id="ilkeler">Yayın ilkelerimiz</h2>
   <ul>
     <li><strong>Her haberde kaynak.</strong> Haberin dayandığı tüm kaynaklar adıyla ve bağlantısıyla belirtilir.</li>
--- a/templates/archive.html
+++ b/templates/archive.html
@@ -1,6 +1,6 @@
 {% extends "base.html" %}
-{% from "_macros.html" import card %}
-{% block title %}Teknoloji haberleri arşivi, sayfa {{ page }} | {{ site.name }}{% endblock %}
-{% block description %}Teknoloji haberleri arşivi, sayfa {{ page }}: süper zeka, teknoloji, inovasyon, girişimcilik ve gaming haberleri, kaynağıyla.{% endblock %}
+{% from "_macros.html" import card, crumbs %}
+{% block title %}Tüm teknoloji haberleri{% if page > 1 %}, sayfa {{ page }}{% endif %} | {{ site.name }}{% endblock %}
+{% block description %}Smarity'de yayımlanan tüm haberler, en yeniden eskiye{% if page > 1 %} (sayfa {{ page }}){% endif %}: süper zeka, teknoloji, inovasyon, girişimcilik ve gaming haberleri, kaynağıyla.{% endblock %}
 {% block head %}
 {% if prev_url %}<link rel="prev" href="{{ prev_url }}">{% endif %}
@@ -8,10 +8,16 @@
 {% endblock %}
 {% block main %}
-<header class="page-head wrap"><span class="eyebrow" style="--c:#6E6E73">Arşiv</span><h1>Teknoloji haberleri.</h1><p>Sayfa {{ page }} / {{ pages }}</p></header>
-<section class="wrap"><div class="grid">{% for p in posts %}{{ card(p, heading='h2') }}{% endfor %}</div></section>
+{{ crumbs([("Ana sayfa", site.base ~ "/", site.url ~ "/"), ("Tüm haberler", site.base ~ "/haberler/", site.url ~ "/haberler/")]) }}
+<header class="page-head wrap"><span class="eyebrow" style="--c:#6E6E73">Arşiv</span><h1>Tüm haberler.</h1><p>En yeniden eskiye, {{ total }} haber{% if pages > 1 %} · Sayfa {{ page }} / {{ pages }}{% endif %}</p></header>
+<nav class="chips wrap center" aria-label="Kategoriler">
+  {% for c in site.categories if c.count %}<a class="chip-link" href="{{ c.url }}" style="--c:{{ c.color }}"><i aria-hidden="true"></i>{{ c.label }}<span>{{ c.count }}</span></a>{% endfor %}
+</nav>
+<section class="wrap sec-tight"><div class="grid">{% for p in posts %}{{ card(p, heading='h2') }}{% endfor %}</div></section>
+{% if pages > 1 %}
 <nav class="pager wrap" aria-label="Sayfalar">
-  {% if prev_url %}<a class="more" href="{{ prev_url }}">Daha yeni</a>{% endif %}
+  {% if prev_url %}<a class="more back" href="{{ prev_url }}">Daha yeni</a>{% endif %}
   <span class="muted">{{ page }} / {{ pages }}</span>
   {% if next_url %}<a class="more" href="{{ next_url }}">Daha eski</a>{% endif %}
 </nav>
+{% endif %}
 {% endblock %}
--- a/templates/article.html
+++ b/templates/article.html
@@ -1,4 +1,4 @@
 {% extends "base.html" %}
-{% from "_macros.html" import rail, img, crumbs %}
+{% from "_macros.html" import rail, img, crumbs, follow %}
 {% set active_cat = post.category %}
 {% block title %}{{ post.seo_title }} | {{ site.name }}{% endblock %}
@@ -41,5 +41,5 @@
 
 {% block main %}
-<article class="art" style="--c:{{ post.cat_color }}">
+<article class="art" style="--c:{{ post.cat_color }}" data-read="{{ post.id }}">
   <div class="art-col">
   {{ crumbs([("Ana sayfa", site.base ~ "/", site.url ~ "/"), (post.cat_label, post.cat_url, post.abs_cat_url), (post.short_title or post.title, post.url, post.abs_url)], '') }}
@@ -53,6 +53,8 @@
     <p class="dek">{{ post.summary }}</p>
     <div class="share" aria-label="Paylaş">
+      <button type="button" class="sh-native" data-share data-title="{{ post.title }}" data-url="{{ post.abs_url }}" hidden>Paylaş</button>
+      <a href="https://wa.me/?text={{ (post.title ~ ' ' ~ post.abs_url)|urlencode }}" rel="noopener" target="_blank">WhatsApp</a>
       <a href="https://x.com/intent/post?url={{ post.abs_url|urlencode }}&text={{ post.title|urlencode }}" rel="noopener" target="_blank">X</a>
-      <a href="https://wa.me/?text={{ (post.title ~ ' ' ~ post.abs_url)|urlencode }}" rel="noopener" target="_blank">WhatsApp</a>
+      <a href="https://t.me/share/url?url={{ post.abs_url|urlencode }}&text={{ post.title|urlencode }}" rel="noopener" target="_blank">Telegram</a>
       <a href="https://www.linkedin.com/sharing/share-offsite/?url={{ post.abs_url|urlencode }}" rel="noopener" target="_blank">LinkedIn</a>
       <button type="button" data-copy="{{ post.abs_url }}">Bağlantıyı kopyala</button>
@@ -138,4 +140,22 @@
     </p>
   </section>
+
+  {% if site.follow|length > 1 %}{{ follow(site, compact=true) }}{% endif %}
+
+  {% if next_post %}
+  {% set n = next_post %}
+  <aside class="next" aria-label="Sıradaki haber" style="--c:{{ n.cat_color }}">
+    <span class="next-label">Sıradaki haber</span>
+    <a class="next-in" href="{{ n.url }}">
+      <span class="next-img">{{ img(n) }}</span>
+      <span class="next-txt">
+        <span class="eyebrow sm">{{ n.cat_label }}</span>
+        <span class="next-title">{{ n.title_disp }}</span>
+        <span class="next-dek">{{ n.summary }}</span>
+        <span class="more">Oku</span>
+      </span>
+    </a>
+  </aside>
+  {% endif %}
   </div>
 </article>
--- a/templates/base.html
+++ b/templates/base.html
@@ -32,4 +32,6 @@
 <link rel="apple-touch-icon" href="{{ site.base }}/static/apple-touch-icon.png">
 <meta name="theme-color" content="#FFFFFF">
+<link rel="manifest" href="{{ site.base }}/manifest.webmanifest">
+<meta name="apple-mobile-web-app-title" content="{{ site.name }}">
 <link rel="preconnect" href="https://fonts.googleapis.com">
 <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
@@ -49,10 +51,12 @@
     </div>
     <div class="nav-end">
+      <a href="{{ site.base }}/haberler/" class="hide-sm">Tüm haberler</a>
       <a href="{{ site.base }}/hakkinda/" class="hide-sm">Hakkında</a>
       <details class="menu">
         <summary aria-label="Menüyü aç"><span></span></summary>
         <div class="menu-panel">
-          <a href="{{ site.base }}/">Tüm haberler</a>
-          {% for c in site.nav_categories %}<a href="{{ c.url }}">{{ c.label }}</a>{% endfor %}
+          <a href="{{ site.base }}/">Ana sayfa</a>
+          {% for c in site.nav_categories %}<a href="{{ c.url }}" style="--c:{{ c.color }}"><i aria-hidden="true"></i>{{ c.label }}</a>{% endfor %}
+          <a href="{{ site.base }}/haberler/">Tüm haberler</a>
           <a href="{{ site.base }}/hakkinda/">Hakkında</a>
         </div>
@@ -69,15 +73,30 @@
 <footer class="foot">
   <div class="wrap foot-in">
-    <a class="brand" href="{{ site.base }}/">{% if site.logo_svg %}<img class="wordmark" src="{{ site.logo_svg }}?v={{ site.asset_v }}" alt="{{ site.name }}" width="105" height="28" loading="lazy">{% else %}<span class="mark" aria-hidden="true"></span>{{ site.name }}{% endif %}</a>
-    <p>{{ site.name }}, dünyadan ve Türkiye'den teknoloji, inovasyon, girişim, yapay zeka, otomobil ve oyun haberlerini Türkçe ve kaynağıyla aktaran bir haber sitesidir. Her haberde orijinal kaynak adıyla ve bağlantısıyla belirtilir. Haberler kaynaklardan yapay zeka yardımıyla derlenir ve editör denetiminden geçer. Fotoğrafların kaynağı her fotoğrafın altında belirtilir.</p>
-    <div class="foot-cats">
+    <div class="foot-brand">
+      <a class="brand" href="{{ site.base }}/">{% if site.logo_svg %}<img class="wordmark" src="{{ site.logo_svg }}?v={{ site.asset_v }}" alt="{{ site.name }}" width="105" height="28" loading="lazy">{% else %}<span class="mark" aria-hidden="true"></span>{{ site.name }}{% endif %}</a>
+      <p>{{ site.tagline }}</p>
+      <p class="foot-note">Haberler, dayandığı kaynaklardan yapay zeka yardımıyla Türkçe derlenir ve editör denetiminden geçer. Her haberde kaynak adıyla ve bağlantısıyla, her fotoğrafta sahibi belirtilir.</p>
+    </div>
+    <nav class="foot-col" aria-label="Kategoriler">
+      <h2>Kategoriler</h2>
       {% for c in site.categories %}<a href="{{ c.url }}">{{ c.label }}</a>{% endfor %}
-    </div>
+      <a href="{{ site.base }}/haberler/">Tüm haberler</a>
+    </nav>
+    <nav class="foot-col" aria-label="Takip et">
+      <h2>Takip et</h2>
+      {% for f in site.follow|default([]) %}<a href="{{ f.url }}"{% if f.key != 'rss' %} rel="noopener" target="_blank"{% endif %}>{{ f.label }}</a>{% endfor %}
+    </nav>
+    <nav class="foot-col" aria-label="Smarity">
+      <h2>{{ site.name }}</h2>
+      <a href="{{ site.base }}/hakkinda/">Hakkında</a>
+      <a href="{{ site.base }}/hakkinda/#ilkeler">Yayın ilkeleri</a>
+      {% if site.contact_email %}<a href="mailto:{{ site.contact_email }}">İletişim</a>{% endif %}
+    </nav>
     {% if site.top_tags %}
-    <div class="foot-cats foot-tags" aria-label="Popüler konular">
-      {% for t in site.top_tags %}<a href="{{ t.url }}">{{ t.label }}</a>{% endfor %}
+    <div class="foot-tags" aria-label="Popüler konular">
+      {% for t in site.top_tags[:10] %}<a href="{{ t.url }}">{{ t.label }}</a>{% endfor %}
     </div>
     {% endif %}
-    <p>© {{ site.year }} {{ site.name }} · <a href="{{ site.base }}/hakkinda/">Hakkında ve yayın ilkeleri</a> · <a href="{{ site.base }}/feed.xml">RSS</a>{% if site.instagram %} · <a href="https://instagram.com/{{ site.instagram }}" rel="noopener" target="_blank">Instagram</a>{% endif %}</p>
+    <p class="foot-copy">© {{ site.year }} {{ site.name }}</p>
   </div>
 </footer>
--- a/templates/index.html
+++ b/templates/index.html
@@ -1,4 +1,4 @@
 {% extends "base.html" %}
-{% from "_macros.html" import card, slide, rail %}
+{% from "_macros.html" import card, slide, rail, row, follow %}
 
 {% block head %}
@@ -35,5 +35,7 @@
   </section>
 {% else %}
-  <section class="car" aria-roledescription="carousel" aria-label="Öne çıkan haberler" data-interval="6500">
+  <p class="since wrap" data-since hidden><span class="since-dot" aria-hidden="true"></span><span data-since-text></span> <a href="#h-son">Göster</a></p>
+
+  <section class="car" aria-roledescription="carousel" aria-label="Manşet" data-interval="6500">
     <div class="car-view wrap">
       <div class="car-track" id="car-track">
@@ -61,13 +63,34 @@
     <a class="chip-link" href="{{ c.url }}" style="--c:{{ c.color }}"><i aria-hidden="true"></i>{{ c.label }}<span>{{ c.count }}</span></a>
     {% endfor %}
+    <a class="chip-link all" href="{{ all_url }}">Tüm haberler<span>›</span></a>
   </nav>
 
+  {% if top %}
+  <section class="sec wrap" aria-labelledby="h-one">
+    <div class="sec-head"><h2 id="h-one">Öne çıkanlar.</h2></div>
+    <div class="grid" data-top>{% for p in top %}{{ card(p) }}{% endfor %}</div>
+  </section>
+  {% endif %}
+
+  {% if latest %}
   <section class="sec wrap" aria-labelledby="h-son">
-    <div class="sec-head"><h2 id="h-son">Son gelişmeler.</h2></div>
-    <div class="grid">{% for p in latest %}{{ card(p) }}{% endfor %}</div>
-    {% if next_url %}
-    <nav class="pager" aria-label="Sayfalar"><a class="more" href="{{ next_url }}">Daha eski haberler</a></nav>
-    {% endif %}
+    <div class="sec-head">
+      <h2 id="h-son">Son haberler.</h2>
+      <div class="sec-tools"><a class="more" href="{{ all_url }}">Tüm haberler</a></div>
+    </div>
+    <ol class="rows">{% for p in latest %}{{ row(p) }}{% endfor %}</ol>
   </section>
+  {% endif %}
+
+  {% if site.follow|length > 1 %}<div class="wrap">{{ follow(site) }}</div>{% endif %}
+
+  {% if discover|length >= 4 %}
+  <section class="sec wrap disc" aria-labelledby="h-kacir">
+    <div class="sec-head"><h2 id="h-kacir">Kaçırmış olabilirsin.</h2></div>
+    <div class="grid grid-4" data-discover>
+      {% for p in discover %}<div class="disc-item"{% if loop.index > 4 %} hidden{% endif %}>{{ card(p, dek=false) }}</div>{% endfor %}
+    </div>
+  </section>
+  {% endif %}
 
   {% for r in rails %}
--- a/templates/sitemap.xml
+++ b/templates/sitemap.xml
@@ -3,6 +3,7 @@
   <url><loc>{{ site.url }}/</loc><lastmod>{{ site.built_iso }}</lastmod></url>
   <url><loc>{{ site.url }}/hakkinda/</loc></url>
+  <url><loc>{{ site.url }}/haberler/</loc><lastmod>{{ site.built_iso }}</lastmod></url>
   {% for n in range(2, pages + 1) %}
-  <url><loc>{{ site.url }}/sayfa/{{ n }}/</loc></url>
+  <url><loc>{{ site.url }}/haberler/sayfa/{{ n }}/</loc></url>
   {% endfor %}
   {% for c in cats %}
@@@SM@@@ FILE haberbot/textfix.py
"""Türkçe metin düzeltmeleri (yapay zekaya gerek kalmadan, kurallı ve güvenli).

1) Türkçe karakteri düşmüş sözcükler: "cikis tarihi aciklandi" → "çıkış tarihi açıklandı".
   Sözlük, sitedeki haberlerin metinlerinden kendiliğinden öğrenilir (+ sık sözcüklerden oluşan çekirdek liste).
   Yalnızca Türkçe karakterli hâli bilinen ve düz hâli ayrı bir sözcük olmayan kelimeler düzeltilir; cümle ortasında
   büyük harfle başlayan (özel ad olabilecek) sözcüklere, sözlükte de özel ad olarak geçmiyorsa dokunulmaz.
2) Küçük harfle başlayan marka adları: "İPhone" → "iPhone", "EFlyer 2" → "eFlyer 2".
3) Etiketlerin görünen adı: "elektrikli otomobil" → "Elektrikli otomobil" (içinde büyük harf varsa olduğu gibi).
"""
from __future__ import annotations

import re
from collections import Counter

TR_LETTERS = "çğıöşüÇĞİÖŞÜ"
FOLD = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
                      "Ç": "C", "Ğ": "G", "İ": "I", "Ö": "O", "Ş": "S", "Ü": "U", "â": "a", "Â": "A", "î": "i", "û": "u"})
WORD = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşüÂâÎîÛû]+")

SEED = """
açıkladı açıklandı açıklama açıklamada açıklamasına açık açıklığı çıkış çıkışı çıktı çıkıyor çıkacak çıkarıyor çıkardı
erişim erişimi erişimini kararı kararları kararlar karşı karşısında Atatürk Türkiye Türkiye'de Türk Türkçe İstanbul Ankara İzmir
özellik özellikleri özelliği özelliğini özel güncelleme güncellemesi güncellendi şirket şirketi şirketin şirketler şirketleri
üretim üretimi üretti üretiyor üretici kullanıcı kullanıcılar kullanıcıların kullanım kullanılıyor ücretsiz ücret ücreti
oyuncu oyuncular oyuncuların sürüm sürümü sürümünü donanım donanımı yazılım yazılımı öğrenme öğrendi büyük büyüme küçük
çok göre önce sonra dünya dünyanın geliştirdi geliştirme geliştiriyor geliştirici güç gücü gücünü hız hızı hızlı ürün ürünü
ürünleri ürünler satış satışa satışları tanıttı tanıtıldı tanıtım başladı başlıyor başlattı başarı başarılı akıllı gözlük
gözlüğü şarj güvenlik güvenliği düşük düşüş yüksek artış artırdı yatırım yatırımı girişim girişimi işlemci işlemcisi çip çipi
sürücü sürücüsüz aracı araç araçlar çalıştı çalıştırıldı çalışıyor çalışma iş işbirliği ortaklık müşteri müşteriler abonelik
üyelik gösterdi gösteriyor görüntü görüntülü sesli yenilik yenilikleri yeniliği gün günü günü Eylül Ekim Kasım Aralık Şubat
Mayıs Ağustos tarihi tarihinde çıkış tarihi ilgili ilgi dikkat değişiklik değişti dönüşüm döneminde dönem hâlâ şu anda
şimdi şöyle böyle üzere üzerinde içinde için içerik içeriği ağ ağı bağlantı bağlantısı uygulama uygulaması uygulamasının
ülke ülkede ülkeler bölge bölgesinde önemli öne öncelik ödeme ödül ölçek ölçüde örnek örneğin ücretli üst ünlü ünvanı
güncel güney kuzey doğu batı ışık işık süre süreç sürecinde süresi sürdürülebilir sağlık sağlıyor sağladı sağlayacak
Çin Çinli Japonya Güney Kore Avrupa Birliği yapımcı yapımı yönetici yönetim yöntem yöntemi çözüm çözümü çözümler
"""
SHORT_OK = {"cok": "çok", "uc": "üç", "guc": "güç", "hiz": "hız", "ise": None, "ic": "iç", "dis": "dış"}
LOWER_BRANDS = """iPhone iPad iPadOS iOS iMac iCloud iMessage iTunes iPod macOS watchOS visionOS tvOS eSIM eFootball eVTOL eBay
iRobot xAI eFlyer eGolf eMobility iX iQOO""".split()


def fold(s: str) -> str:
    return s.translate(FOLD)


def tr_lower(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


def tr_upper_first(s: str) -> str:
    if not s:
        return s
    c = s[0]
    c = "İ" if c == "i" else "I" if c == "ı" else c.upper()
    return c + s[1:]


class Fixer:
    """Sözlüğü haber metinlerinden öğrenen düzeltici."""

    def __init__(self, texts: list[str] | None = None):
        orig: dict[str, Counter] = {}
        plain: set[str] = set()
        for text in [SEED] + list(texts or []):
            for w in WORD.findall(text or ""):
                if any(ch in TR_LETTERS for ch in w):
                    key = tr_lower(fold(w)) if w[0].isupper() else fold(w).lower()
                    orig.setdefault(key, Counter())[w] += 1
                else:
                    plain.add(w.lower())
        self.map: dict[str, str] = {}
        for key, c in orig.items():
            if key in plain or (len(key) < 4 and key not in SHORT_OK):
                continue
            # en sık görülen yazım; küçük harfli hâli varsa o esas alınır (cümle başı büyük harfi sayılmaz)
            lows = Counter({w: n for w, n in c.items() if not w[0].isupper()})
            best = (lows or c).most_common(1)[0][0]
            self.map[key] = best
        for k, v in SHORT_OK.items():
            if v:
                self.map.setdefault(k, v)
        self.brands = {b.lower(): b for b in LOWER_BRANDS}
        for text in texts or []:
            for w in re.findall(r"\b[a-z]{1,2}[A-Z][A-Za-z0-9]*\b", text or ""):
                self.brands.setdefault(w.lower(), w)

    # ── sözcük düzeltme ──
    def _word(self, w: str, sentence_start: bool) -> str:
        if any(ch in TR_LETTERS for ch in w):
            return w
        lw = w.lower()
        rep = self.map.get(lw)
        if not rep:
            return w
        if w.isupper() and len(w) > 1:
            return rep.replace("i", "İ").replace("ı", "I").upper()
        if w[0].isupper():
            if rep[0].isupper():          # sözlükte de özel ad: Ataturk → Atatürk
                return rep
            return tr_upper_first(rep) if sentence_start else w   # cümle ortasında büyük harf: özel ad olabilir
        return rep if not rep[0].isupper() else w

    def diacritics(self, text: str) -> str:
        if not text:
            return text
        out, last, start = [], 0, True
        for m in WORD.finditer(text):
            gap = text[last:m.start()]
            if re.search(r"[.!?:\n]\s*$", gap) or (last == 0 and not gap.strip()):
                start = True
            out.append(gap)
            out.append(self._word(m.group(), start))
            start = False
            last = m.end()
        out.append(text[last:])
        return "".join(out)

    def brands_case(self, text: str) -> str:
        """İPhone / IPhone / EFlyer → iPhone / eFlyer (cümle başında büyütülmüş küçük harfli markalar)."""
        def fix(m):
            w = m.group(0)
            key = tr_lower(w[0]) + w[1:].lower() if w[0] in "İI" else w.lower()
            b = self.brands.get(key)
            return b if b and w != b and w[1:] == b[1:] else w
        return re.sub(r"\b[A-ZİÇĞÖŞÜ][A-Z][A-Za-z0-9]*\b", fix, text or "")

    def text(self, s: str) -> str:
        return self.brands_case(self.diacritics(s)) if s else s

    def post(self, p: dict) -> list[str]:
        """Bir haberin metin alanlarını düzelt; değişen alan adlarını döndür."""
        changed = []
        for k in ("title", "short_title", "summary", "body", "seo_title", "meta_description", "kicker",
                  "hero_stat_label", "image_alt", "cover_text", "focus_keyword"):
            v = p.get(k)
            if isinstance(v, str) and v:
                nv = self.text(v)
                if nv != v:
                    p[k] = nv
                    changed.append(k)
        for k in ("tags", "carousel_points"):
            v = p.get(k)
            if isinstance(v, list):
                nv = [self.text(x) if isinstance(x, str) else x for x in v]
                if nv != v:
                    p[k] = nv
                    changed.append(k)
        return changed


def missing_turkish(text: str) -> bool:
    """Uzun bir Türkçe metinde hiç Türkçe karakter yoksa (büyük olasılıkla karakterler düşmüş)."""
    words = [w for w in WORD.findall(text or "") if w[0].islower()]
    return len(words) >= 6 and not any(ch in TR_LETTERS for ch in text)


def tag_display(tag: str) -> str:
    """Etiketin görünen adı: tamamı küçük harfse ilk harf büyür (Türkçe kurallarıyla)."""
    t = (tag or "").strip()
    if not t or any(ch.isupper() for ch in t):
        return t
    return tr_upper_first(t)
@@@SM@@@ FILE tests/test_home.py
"""Ana sayfa seçkisi, metin düzeltmeleri ve manşet düğmeleri testleri."""
import re
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haberbot import app as appmod  # noqa: E402
from haberbot.config import ROOT, Config  # noqa: E402
from haberbot.site import SiteBuilder, hot  # noqa: E402
from haberbot.textfix import Fixer, missing_turkish, tag_display  # noqa: E402
from haberbot.util import iso, now_utc  # noqa: E402


def test_textfix():
    fx = Fixer(["Oyunun çıkış tarihi açıklandı. Erişim kararları ve Atatürk.", "Yeni özellikler için güncelleme."])
    assert fx.text("The Witcher 3 cikis tarihi ve yenilikleri aciklandi") == "The Witcher 3 çıkış tarihi ve yenilikleri açıklandı"
    assert fx.text("Steam erisim kararlari ve Ataturk") == "Steam erişim kararları ve Atatürk"
    assert fx.text("Galaxy S27 icin yeni ozellikler") == "Galaxy S27 için yeni özellikler"
    assert fx.text("İPhone 18 Pro tanıtıldı") == "iPhone 18 Pro tanıtıldı"
    assert fx.text("EFootball 2027 duyuruldu") == "eFootball 2027 duyuruldu"
    assert fx.text("Al Gore konuştu, one more thing") == "Al Gore konuştu, one more thing"   # özel ad ve İngilizce dokunulmaz
    assert fx.text("Cikis tarihi belli oldu") == "Çıkış tarihi belli oldu"                        # cümle başı büyük harf
    p = {"title": "Oyun cikis tarihi aciklandi", "tags": ["akilli gozluk", "Apple"], "body": "Metin."}
    assert set(fx.post(p)) == {"title", "tags"} and p["tags"][0] == "akıllı gözlük"
    assert missing_turkish("Bu oyun yarin tum platformlarda cikiyor ve fiyati belli oldu")
    assert not missing_turkish("World of Warcraft Forever duyuruldu")
    assert [tag_display(t) for t in ("elektrikli otomobil", "iPhone 18", "ısı pompası")] == \
        ["Elektrikli otomobil", "iPhone 18", "Isı pompası"]


def _post(i, hours, appeal=6, cat="teknoloji", **kw):
    return {"id": f"p{i:02d}", "slug": f"haber-{i}", "title": f"Haber {i} başlığı", "summary": "Özet cümlesi.",
            "category": cat, "tags": ["Apple"], "body": "Birinci paragraf.\n\nİkinci paragraf.", "appeal": appeal,
            "published_at": iso(now_utc() - timedelta(hours=hours)), "image": {"source": "cover"},
            "sources": [{"name": "Kaynak", "url": "https://k.com/a", "kind": "media"}], **kw}


def test_hot_ranking():
    fresh_low, fresh_high, old_high = _post(1, 1, 5), _post(2, 2, 9), _post(3, 60, 9)
    assert hot(fresh_high) > hot(fresh_low) and hot(fresh_high) > hot(old_high)
    assert hot(_post(4, 1, 6, image={"source": "photo"})) > hot(_post(5, 1, 6))
    assert hot(_post(6, 20, 5, home="pin", home_at=iso(now_utc()))) > hot(fresh_high)
    assert hot(_post(7, 1, 10, home="hide")) < 0


class _App:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
        self.cfg = Config(raw=raw, root=Path(self.tmp.name), site_url="https://smarity.com.tr", mock=True,
                          telegram_chat_id="1")
        self.app = appmod.App(self.cfg)
        return self.cfg, self.app

    def __exit__(self, *exc):
        if self.app._vis:
            self.app._vis.close()
        self.tmp.cleanup()


def test_home_is_curated_and_everything_stays_reachable():
    with _App() as (cfg, a):
        cats = ["teknoloji", "gaming", "super-zeka", "inovasyon"]
        for i in range(40):
            extra = {"home": "hide"} if i == 3 else {"home": "pin", "home_at": iso(now_utc())} if i == 30 else {}
            a.store.save_post(_post(i, hours=i * 3, appeal=[5, 6, 7, 9][i % 4], cat=cats[i % 4], **extra))
        sb = SiteBuilder(cfg)
        sb.build()
        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
        ids = re.findall(r'data-id="(p\d+)"', home)
        slider = re.findall(r'class="slide[^"]*"[^>]*data-id="(p\d+)"', home)
        assert slider[0] == "p30"                                     # manşete sabitlenen en üstte
        assert "p03" not in ids                                       # "ana sayfada gösterme"
        assert len(set(ids)) < 40                                     # her haber ana sayfaya çıkmaz
        top = re.search(r'data-top>(.*?)</div>\s*</section>', home, re.S).group(1)
        top_ids = re.findall(r'data-id="(p\d+)"', top)
        assert len(top_ids) == 6 and not set(top_ids) & set(slider)   # bölümler arasında tekrar yok
        for sec in ("Öne çıkanlar.", "Son haberler.", "Kaçırmış olabilirsin."):
            assert sec in home
        # tüm haberler sayfalarında her şey var (gizlenen dahil), eski adresler yönlenir
        pages = [cfg.out_dir / "haberler" / "index.html"] + sorted((cfg.out_dir / "haberler" / "sayfa").glob("*/index.html"))
        all_ids = set()
        for pg in pages:
            all_ids |= set(re.findall(r'data-id="(p\d+)"', pg.read_text(encoding="utf-8")))
        assert len(all_ids) == 40
        assert "haberler/" in (cfg.out_dir / "sayfa" / "2" / "index.html").read_text(encoding="utf-8")
        assert (cfg.out_dir / "manifest.webmanifest").exists()
        art = (cfg.out_dir / "haber" / "haber-5" / "index.html").read_text(encoding="utf-8")
        assert "Sıradaki haber" in art and 'data-read="p05"' in art and "t.me/share" in art
        sm = (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")
        assert "/haberler/" in sm and "smarity.com.tr/sayfa/" not in sm


def test_pin_and_hide_buttons():
    with _App() as (cfg, a):
        a.store.save_post(_post(1, 2, publish_mode="manual"))
        kb = a._keyboard(a.store.load_post("p01"), "published")
        assert [b["callback_data"][0] for b in kb[-1]] == ["m", "h"]
        assert a._on_button("m", "p01").startswith("⭐")
        p = a.store.load_post("p01")
        assert p["home"] == "pin" and a._keyboard(p, "published")[-1][0]["text"].endswith("Manşetten çıkar")
        assert a._on_button("h", "p01").startswith("🙈")
        assert a.store.load_post("p01")["home"] == "hide" and hot(a.store.load_post("p01")) < 0
        assert a._on_button("h", "p01").startswith("↩️")
        assert "home" not in a.store.load_post("p01")


def test_write_fixes_text_and_scores_appeal():
    with _App() as (cfg, a):
        a.store.save_post(_post(1, 2, body="Oyunun çıkış tarihi açıklandı."))
        w = a._write([{"credit": "IGN", "kind": "media", "title": "GTA 6 cikis tarihi aciklandi", "url": "https://ign.com/x",
                       "summary": "", "text": ""}])
        assert "çıkış tarihi açıklandı" in w["title"] and 1 <= w["appeal"] <= 10
        a.store.save_post(_post(2, 3, appeal=None))
        a.backfill_appeal()
        assert a.store.load_post("p02")["appeal"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
@@@SM@@@ SHA
99d98fc133229366f5ef7d1b2dcc0cb4f152f401d51c47bd54a1e07a771bc71d config.yaml
dbde3ad3a94b2529b50851e1678e91334947471040e7ab67be9c57084971dfa3 haberbot/app.py
634ec4a97713e0ca2dd90f6576e018f0a4ae4996d51adb26972524193510d3bc haberbot/llm.py
217899a1df4cd622e0812e865ca19ca26c0e2554237a3591036c6c71a104ce79 haberbot/prompts.py
59d1b9a2db71b8274e9968715dce17c756891d55a8759d764ac05b54be71cbc5 haberbot/site.py
1fe423f9fb2ed78845b8b32348392d1eee0ca409fc0a5e3b6284d9ea2059fa95 static/site.js
a5532cc8d9b2486d697fbfa300ba59d9830da53320f474cbc1501c89756e70ad static/style.css
4f16a53832d7a3e14e590734676c5ee35dd4e8c80583390bda4c00a307ec4568 templates/_macros.html
eb93e761e3bebe4045a8b16382aa1089a4fe3005a51706b358d78c12704e5b20 templates/about.html
fbcffe5fe1fc472fd1edc4c84d445ea86c9db3d23553445a76aa6be32ea01a75 templates/archive.html
1869982ad800043a612c2489ce8097bf416589b66c3674879ed172d6095a3285 templates/article.html
a62aa094d515c4ea9daa10c781de8ea2a6285f666817065b82a49dc499beaa60 templates/base.html
17e256d5ddac3f568dc993038dc8a33532d4892a7398a0b05a55c9408aef6339 templates/index.html
62bc2a6b7141245db23cb84870255cb81c5ab3d904a526b5db4bc50e7dc51dc0 templates/sitemap.xml
834084f71f1d0ac6e2a9c951430213d27a6a68a82e39e87e51fc73a4d54de472 haberbot/textfix.py
b94a2d1e2d32f4a47f6a63d0d4998c056a584a29097a5d165080a91dd0a84950 tests/test_home.py
