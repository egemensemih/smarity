SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -598,2 +598,85 @@
   #   kind: community
   #   credit_linked_site: true
+
+# ── Sürekli güncel rehberler (/rehber/…) ───────────────────
+# Sık aranan fiyat, ücret ve kurallar tek bir kalıcı sayfada. Sitede yayımlanan ilgili haberlerden derlenir; ilgili yeni bir
+# haber gelince yeniden yazılır. Rehberdeki her rakam dayandığı haberlerde birebir geçmek zorunda: geçmeyen varsa yeni
+# sürüm yayımlanmaz. İlgili haberlerin altında rehbere bağlantı çıkar.
+#   match: başlıkta ya da etiketlerde geçmesi gereken sözcükler (biri yeter)
+#   need / need_also: başlıkta ayrıca geçmesi gereken sözcükler (her listeden biri)   skip: geçmemesi gerekenler
+#   categories: yalnızca bu kategorilerdeki haberler   min_posts: rehberin açılması için gereken haber sayısı
+#   match_in: title → match sözcüklerine yalnızca başlıkta bakılır (etiketlerde değil)
+guides:
+  enabled: true
+  lookback_days: 75          # rehbere giren haberlerin en eski tarihi
+  max_posts: 14              # rehber başına en fazla haber
+  min_posts: 2
+  min_hours_between: 24      # aynı rehber en sık günde bir yeniden yazılır
+  list:
+    - slug: togg-fiyat-listesi
+      title: "Togg fiyat listesi"
+      h1: "Togg fiyat listesi: güncel T10X ve T10F fiyatları"
+      about: "Togg T10X ve T10F'nin Türkiye satış fiyatları ve versiyonları, kampanya ve finansman koşulları"
+      category: otomotiv
+      match: ["togg"]
+      need: ["fiyat", "zam", "kampanya"]
+    - slug: elektrikli-otomobil-fiyatlari
+      title: "Elektrikli otomobil fiyatları"
+      h1: "Türkiye'de elektrikli otomobil fiyatları: en ucuz modeller ve güncel liste"
+      about: "Türkiye'de satılan elektrikli otomobillerin güncel fiyatları, en ucuz modeller, ÖTV durumu"
+      category: otomotiv
+      categories: [otomotiv]
+      match: ["elektrikli"]
+      need: ["fiyat", "zam"]
+      need_also: ["türkiye", "en ucuz", "elektrikli otomobil fiyat"]
+      max_posts: 18
+    - slug: elektrikli-arac-sarj-ucretleri
+      title: "Elektrikli araç şarj ücretleri"
+      h1: "Elektrikli araç şarj ücretleri: güncel AC ve DC kWh fiyatları"
+      about: "Türkiye'deki şarj ağlarının (ZES, Eşarj, Trugo, Tesla Supercharger, Voltrun…) güncel AC/DC kWh ücretleri"
+      category: otomotiv
+      match: ["şarj"]
+      need: ["ücret", "fiyat", "tarife", "zam"]
+    - slug: sifir-arac-fiyat-listeleri
+      title: "Sıfır araç fiyat listeleri"
+      h1: "Sıfır araç fiyat listeleri: marka marka güncel fiyatlar"
+      about: "Türkiye'de satılan otomobil markalarının aylık fiyat listeleri: markaların başlangıç fiyatları, en ucuz modeller"
+      category: otomotiv
+      categories: [otomotiv]
+      match: ["fiyat listesi", "en ucuz sıfır", "sıfır araba fiyat", "sıfır araç fiyat"]
+      lookback_days: 45
+      max_posts: 22
+    - slug: imei-kayit-ucreti
+      title: "IMEI kayıt ücreti"
+      h1: "IMEI kayıt ücreti: yurt dışından getirilen telefon için güncel harç"
+      about: "Yurt dışından getirilen telefonların IMEI kayıt ücreti (harç), geçerlilik tarihi ve kayıt kuralları"
+      category: teknoloji
+      match: ["imei"]
+    - slug: apple-turkiye-fiyatlari
+      title: "Apple Türkiye fiyatları"
+      h1: "Apple Türkiye fiyatları: güncel iPhone, iPad, Mac ve AirPods fiyatları"
+      about: "Apple ürünlerinin (iPhone, iPad, Mac, AirPods, Apple Watch, HomePod) Türkiye satış fiyatları ve son zamlar"
+      category: teknoloji
+      match: ["apple", "iphone", "ipad", "mac", "airpods", "homepod", "apple watch"]
+      need: ["fiyat", "zam"]
+      need_also: ["türkiye"]
+      skip: ["abonelik"]
+    - slug: samsung-galaxy-turkiye-fiyatlari
+      title: "Samsung Galaxy Türkiye fiyatları"
+      h1: "Samsung Galaxy Türkiye fiyatları: güncel telefon ve tablet fiyatları"
+      about: "Samsung Galaxy telefon, tablet ve saatlerinin Türkiye satış fiyatları"
+      category: teknoloji
+      match: ["samsung", "galaxy"]
+      need: ["fiyat", "zam"]
+      need_also: ["türkiye"]
+      skip: ["geely"]
+    - slug: dijital-abonelik-fiyatlari
+      title: "Dijital abonelik fiyatları"
+      h1: "Dijital abonelik fiyatları: Netflix, Spotify, YouTube Premium ve diğerleri"
+      about: "Netflix, Spotify, YouTube Premium, Disney+, Amazon Prime, Apple TV, PlayStation Plus, Xbox Game Pass, X gibi servislerin Türkiye abonelik ücretleri ve son zamlar"
+      category: teknoloji
+      match: ["netflix", "spotify", "youtube premium", "disney", "prime video", "amazon prime", "apple tv", "playstation plus",
+              "ps plus", "game pass", "abonelik", "üyelik"]
+      match_in: title
+      need: ["fiyat", "ücret", "zam"]
+      need_also: ["türkiye", " tl"]
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -13,4 +13,5 @@
 import requests
 
+from . import guides as guidesmod
 from . import photos, policy
 from .config import CATEGORIES, DEFAULT_CATEGORY, Config, category_label, indexnow_key
@@ -25,5 +26,5 @@
                       seo_system, seo_user, triage_system, triage_user, write_system, write_user)
 from .sources import fetch_all
-from .store import Store, write_json
+from .store import Store, read_json, write_json
 from .textfix import Fixer, entity_keys, is_car_story, looks_english, title_words
 from .telegram import MockTelegram, Telegram, TelegramError
@@ -2065,4 +2066,82 @@
             log.warning("IndexNow bildirimi başarısız: %s", e)
 
+    # ── SÜREKLİ GÜNCEL REHBERLER ────────────────────────────
+    def guides_tick(self) -> bool:
+        """Rehberler (/rehber/…): ilgili yeni bir haber yayımlanınca (en sık min_hours_between saatte bir) yeniden
+        yazılır. Bir turda en fazla bir rehber. Rakam doğrulamasından geçmeyen sürüm yayımlanmaz."""
+        specs = guidesmod.guide_list(self.cfg)
+        if not specs or not self.llm:
+            return False
+        gc = self.cfg.raw.get("guides") or {}
+        lookback = float(gc.get("lookback_days", 75) or 75)
+        limit = int(gc.get("max_posts", 14) or 14)
+        gap = float(gc.get("min_hours_between", 24) or 24)
+        posts = self.store.posts()[:1000]
+        tried = self.state.setdefault("guide_tried", {})
+        for spec in specs:
+            rel = guidesmod.related_posts(spec, posts, float(spec.get("lookback_days") or lookback),
+                                          int(spec.get("max_posts") or limit))
+            if len(rel) < int(spec.get("min_posts") or gc.get("min_posts") or 2):
+                continue
+            sig = guidesmod.signature(rel)
+            old = read_json(guidesmod.guide_path(self.cfg, spec["slug"]), None)
+            if (old and old.get("sig") == sig) or tried.get(spec["slug"]) == sig:
+                continue        # yeni bilgi yok ya da bu haberlerle denendi, olmadı: yeni haber gelince tekrar
+            if old and hours_since(old.get("updated_at")) < gap:
+                continue
+            return self._write_guide(spec, rel, old, sig)
+        return False
+
+    def _write_guide(self, spec: dict, rel: list[dict], old: dict | None, sig: list[str]) -> bool:
+        cfg = self.cfg
+        user = guidesmod.guide_user(spec, rel, self.today(), cfg.tz, old)
+        for attempt in range(2):
+            try:
+                out = self.llm.json(cfg.get("ai", "writer_model", "claude-sonnet-5"), guidesmod.guide_system(self.brand),
+                                    user, guidesmod.GUIDE_SCHEMA, max_tokens=12000,
+                                    effort=cfg.get("ai", "writer_effort", "medium"))
+            except LLMError as e:
+                log.warning("Rehber yazılamadı (%s): %s", spec["slug"], str(e)[:160])
+                return False
+            body = (out.get("body") or "").strip()
+            faq = [{"q": clip(str(f.get("q", "")).strip(), 160), "a": clip(str(f.get("a", "")).strip(), 400)}
+                   for f in (out.get("faq") or []) if f.get("q") and f.get("a")][:6]
+            summary = clip((out.get("summary") or "").strip(), 280)
+            bad = guidesmod.unsupported_numbers(" ".join([body, summary, out.get("seo_title") or "",
+                                                          out.get("meta_description") or ""]
+                                                         + [f"{f['q']} {f['a']}" for f in faq]), rel)
+            if not bad or attempt:
+                break
+            # bir kez düzelttir: rakamı haberdeki yazımıyla ver ya da çıkar (hesaplama, dönüştürme yok)
+            user += ("\n\nCORRECTION: your previous draft contained numbers that do not appear in the RELATED ARTICLES "
+                     f"with the same digits: {', '.join(bad[:12])}. Write every number exactly as it is written in the "
+                     "articles, or leave it out. Do not compute, convert or round. Return the full guide again.")
+        if bad or len(body.split()) < 120:
+            self.state.setdefault("guide_tried", {})[spec["slug"]] = sig
+            log.warning("Rehber yayımlanmadı (%s): %s", spec["slug"],
+                        f"haberlerde geçmeyen rakam: {', '.join(bad[:8])}" if bad else "metin çok kısa")
+            return False
+        now = iso(now_utc())
+        ids = {p["id"] for p in rel}
+        used = [i for i in dict.fromkeys(out.get("used") or []) if i in ids] or [p["id"] for p in rel]
+        hist = [{"at": now, "note": clip((out.get("changes") or "").strip() or ("İlk sürüm." if not old else
+                                                                                 "Yeni haberlerle güncellendi."), 200)}]
+        hist += list((old or {}).get("history") or [])
+        g = {"slug": spec["slug"], "title": spec["title"], "h1": spec.get("h1") or spec["title"],
+             "category": spec.get("category") or DEFAULT_CATEGORY,
+             "seo_title": clip((out.get("seo_title") or "").strip() or spec["title"], 70),
+             "meta_description": clip((out.get("meta_description") or "").strip() or summary, 160),
+             "summary": summary, "body": body, "faq": faq, "based_on": used, "sig": sig,
+             "created_at": (old or {}).get("created_at") or now, "updated_at": now, "history": hist[:12]}
+        guidesmod.save_guide(cfg, g)
+        self.state.get("guide_tried", {}).pop(spec["slug"], None)
+        self.store.site_dirty = True
+        url = f"{cfg.site_url}/rehber/{spec['slug']}/"
+        self.queue_indexnow(url)
+        log.info("Rehber %s: %s", "güncellendi" if old else "yayımlandı", spec["slug"])
+        self.notify(f"📘 <b>Rehber {'güncellendi' if old else 'yayında'}</b>: {esc(g['h1'])}\n{esc(hist[0]['note'])}\n{url}",
+                    silent=True)
+        return True
+
     def backfill_seo(self, limit: int = 3) -> None:
         """SEO bilgisi olmayan eski haberlere (metnine dokunmadan) arama başlığı ve açıklaması ekle."""
@@ -3165,4 +3244,8 @@
             self.backfill_seo()
             try:
+                self.guides_tick()
+            except Exception as e:  # noqa: BLE001
+                log.exception("Rehber hatası: %s", e)
+            try:
                 self.fix_texts()
                 self.backfill_appeal()
--- a/haberbot/llm.py
+++ b/haberbot/llm.py
@@ -335,4 +335,10 @@
         if "stories" in schema.get("properties", {}):
             return self._triage(user)
+        if "faq" in schema.get("properties", {}):          # rehber: ilk haberin başlığı ve özetinden (rakamsız) metin
+            m = re.search(r"--- id: (\w+)", user)
+            return {"seo_title": "Test rehberi", "meta_description": "Test modu rehberi.",
+                    "summary": "Test modu rehberi.", "body": "## Özet\n\n" + " ".join(["Test modu rehber metni."] * 40),
+                    "faq": [{"q": "Test sorusu?", "a": "Test cevabı."}], "changes": "İlk sürüm.",
+                    "used": [m.group(1)] if m else []}
         if "votes" in schema.get("properties", {}):       # sosyal medya masası: ilgi puanı ve fotoğrafa göre
             m = re.search(r"APPEAL \(homepage, 1–10\): (\d+)", user)
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -14,9 +14,11 @@
 from .config import CATEGORIES, DEFAULT_CATEGORY, ROOT, Config, category_color, category_label, category_seo, indexnow_key
 from .covers import art_style
+from .guides import load_guides
+from .guides import matches as guide_matches
 from .store import Store
 from .textfix import primary_key, tag_display
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "21"
+ASSET_V = "22"
 FOREIGN_PRICE = re.compile(r"(?=.*fiyat)(?=.*(\$|€|£|¥|dolar|euro|avro|sterlin|yuan|yen\b))", re.I)
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
@@ -271,4 +273,25 @@
         self.seo = dict(cfg.raw.get("seo") or {})
         self.keep = load_keep()
+
+    def _guide_view(self, g: dict, by_id: dict[str, dict]) -> dict:
+        """Rehber sayfası görünümü (/rehber/slug/)."""
+        cfg, b = self.cfg, self.base
+        cat = g.get("category") if g.get("category") in CATEGORIES else DEFAULT_CATEGORY
+        upd = parse_iso(g.get("updated_at")) or now_utc()
+        based = [by_id[i] for i in g.get("based_on") or [] if i in by_id]
+        return {
+            **g,
+            "url": f"{b}/rehber/{g['slug']}/",
+            "abs_url": f"{cfg.site_url}/rehber/{g['slug']}/",
+            "body_html": render_body(g.get("body", "")),
+            "iso": iso(parse_iso(g.get("created_at")) or upd),
+            "mod_iso": iso(upd),
+            "updated_str": tr_date(upd, cfg.tz, with_time=False),
+            "cat_label": category_label(cat), "cat_color": category_color(cat), "cat_url": f"{b}/{cat}/",
+            "based": sorted(based, key=lambda q: q.get("published_at") or "", reverse=True),
+            "history_list": [{"date": tr_date(h.get("at"), cfg.tz, with_time=False), "note": h.get("note", "")}
+                             for h in (g.get("history") or [])[:8] if h.get("note")],
+            "words": len(plain(g.get("body", "")).split()),
+        }
 
     def _post_view(self, p: dict) -> dict:
@@ -546,4 +569,10 @@
         legal = {k: str(v).strip() for k, v in (cfg.raw.get("legal") or {}).items() if v}
         ctx = {"site": site, "legal": legal}
+        # sürekli güncel rehberler: ilgili haberlerin altında rehbere bağlantı çıkar (eski aylık listeden güncel olana)
+        by_id = {p["id"]: p for p in posts}
+        guides = [self._guide_view(g, by_id) for g in load_guides(cfg)]
+        site["has_guides"] = bool(guides)
+        for p in posts:
+            p["guide"] = next((g for g in guides if guide_matches(g["spec"], p)), None)
 
         # statik dosyalar, logo ve görseller
@@ -644,4 +673,11 @@
                 noindex=t["idx_count"] < 2))
 
+        for g in guides:
+            self._write(f"rehber/{g['slug']}/index.html", self.env.get_template("guide.html").render(
+                **ctx, guide=g, others=[x for x in guides if x["slug"] != g["slug"]], canonical=g["abs_url"]))
+        if guides:
+            self._write("rehber/index.html", self.env.get_template("guides.html").render(
+                **ctx, guides=guides, canonical=f"{cfg.site_url}/rehber/"))
+
         self._write("hakkinda/index.html", self.env.get_template("about.html").render(
             **ctx, canonical=f"{cfg.site_url}/hakkinda/",
@@ -683,5 +719,5 @@
         self._write("sitemap.xml", self.env.get_template("sitemap.xml").render(
             **ctx, posts=[p for p in posts if not p["thin"]], cats=[c for c in cats if c["count"]],
-            tags=[t for t in tags if t["idx_count"] >= 2], pages=pages))
+            tags=[t for t in tags if t["idx_count"] >= 2], pages=pages, guides=guides))
         # ana ekrana eklenebilir site (PWA bildirimi)
         self._write("manifest.webmanifest", json.dumps({
--- a/static/style.css
+++ b/static/style.css
@@ -612,2 +612,27 @@
 @keyframes srchfade { from { opacity: 0; } to { opacity: 1; } }
 @media (prefers-reduced-motion: reduce) { .srch-back, .srch-panel { animation: none; } }
+/* sürekli güncel rehberler */
+.guide-box { margin: 32px 0 8px; }
+.guide-box a { display: grid; gap: 6px; padding: 18px 20px; border-radius: var(--r-md, 16px); background: var(--bg-alt);
+  border-left: 4px solid var(--c, var(--ink)); color: inherit; text-decoration: none; }
+.guide-box a:hover .gb-title { text-decoration: underline; }
+.gb-title { font-size: 20px; font-weight: 700; letter-spacing: -.02em; line-height: 1.25; }
+.gb-dek { font-size: 16px; color: var(--ink-2); line-height: 1.45; }
+.gb-meta { font-size: 14px; color: var(--muted); }
+.prose table { width: 100%; border-collapse: collapse; margin: 22px 0; font-size: 16px; display: block; overflow-x: auto; }
+.prose th, .prose td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line, rgba(0,0,0,.1)); vertical-align: top; }
+.prose th { font-weight: 600; background: var(--bg-alt); }
+.guide-faq h3 { font-size: 19px; letter-spacing: -.01em; margin: 22px 0 6px; }
+.guide-hist { margin-top: 32px; font-size: 15px; color: var(--ink-2); }
+.guide-hist h2, .guide-others h2 { font-size: 13px; font-weight: 700; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); margin: 0 0 10px; }
+.guide-hist ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 6px; }
+.guide-hist time { font-weight: 600; margin-right: 8px; color: var(--ink); }
+.guide-others { margin-top: 36px; display: grid; gap: 8px; }
+.guide-others a, .guide-list a { display: grid; gap: 4px; padding: 14px 16px; border-radius: 14px; background: var(--bg-alt); color: inherit; text-decoration: none; }
+.guide-others a span { font-size: 14px; color: var(--muted); }
+.guide-list { display: grid; gap: 12px; padding-bottom: 56px; }
+.guide-list a { padding: 18px 20px; border-left: 4px solid var(--c, var(--ink)); }
+.guide-list b { font-size: 21px; letter-spacing: -.02em; line-height: 1.25; }
+.gl-dek { color: var(--ink-2); font-size: 16px; line-height: 1.45; }
+.guide-list .muted { font-size: 14px; }
+@media (min-width: 700px) { .art-body table, .prose table { display: table; } }
--- a/templates/article.html
+++ b/templates/article.html
@@ -95,4 +95,16 @@
   <div class="art-body">{{ post.body_html|safe }}</div>
 
+  {% if post.guide %}
+  {% set g = post.guide %}
+  <aside class="guide-box" aria-label="Sürekli güncel rehber">
+    <a href="{{ g.url }}">
+      <span class="eyebrow sm">Sürekli güncel rehber</span>
+      <span class="gb-title">{{ g.h1 }}</span>
+      <span class="gb-dek">{{ g.summary }}</span>
+      <span class="gb-meta">Son güncelleme: {{ g.updated_str }} <span aria-hidden="true">→</span></span>
+    </a>
+  </aside>
+  {% endif %}
+
   {% if post.slides %}
   {% set n = post.slides|length %}
--- a/templates/base.html
+++ b/templates/base.html
@@ -90,4 +90,5 @@
     <nav class="foot-col" aria-label="Smarity">
       <h2>{{ site.name }}</h2>
+      {% if site.has_guides %}<a href="{{ site.base }}/rehber/">Güncel rehberler</a>{% endif %}
       <a href="{{ site.base }}/hakkinda/">Hakkında</a>
       <a href="{{ site.base }}/hakkinda/#ilkeler">Yayın ilkeleri</a>
--- a/templates/sitemap.xml
+++ b/templates/sitemap.xml
@@ -9,4 +9,10 @@
   <url><loc>{{ site.url }}/haberler/sayfa/{{ n }}/</loc></url>
   {% endfor %}
+  {% if guides %}
+  <url><loc>{{ site.url }}/rehber/</loc><lastmod>{{ guides|map(attribute='mod_iso')|max }}</lastmod></url>
+  {% for g in guides %}
+  <url><loc>{{ g.abs_url }}</loc><lastmod>{{ g.mod_iso }}</lastmod></url>
+  {% endfor %}
+  {% endif %}
   {% for c in cats %}
   <url><loc>{{ c.abs_url }}</loc>{% if c.lastmod %}<lastmod>{{ c.lastmod }}</lastmod>{% endif %}</url>
@@@SM@@@ FILE haberbot/guides.py
"""Sürekli güncel rehber sayfaları (/rehber/…): Togg fiyat listesi, IMEI kayıt ücreti, şarj ücretleri gibi.

Rehber, sitede yayımlanmış ilgili haberlerden (onların kaynaklarından) derlenir; yeni ilgili bir haber gelince
yeniden yazılır. Uydurma rakam olmasın diye rehberdeki her rakam dayandığı haberlerde birebir geçmek zorundadır;
geçmeyen varsa yeni sürüm yayımlanmaz, eskisi kalır.
"""
from __future__ import annotations

import re
from pathlib import Path

from .store import read_json, write_json
from .util import hours_since, tr_date

GUIDE_SCHEMA = {
    "type": "object",
    "properties": {
        "seo_title": {"type": "string"},
        "meta_description": {"type": "string"},
        "summary": {"type": "string"},
        "body": {"type": "string"},
        "faq": {"type": "array", "items": {"type": "object", "properties": {
            "q": {"type": "string"}, "a": {"type": "string"}}, "required": ["q", "a"]}},
        "changes": {"type": "string"},
        "used": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["seo_title", "meta_description", "summary", "body", "faq", "changes", "used"],
}

_NUM = re.compile(r"\d[\d.,]*\d|\d")


def _low(s: str) -> str:
    """Karşılaştırma için küçük harf; i/ı/İ/I farkı yok sayılır (IMEI = imei, İPHONE = iphone, ışık = isik)."""
    return (s or "").replace("İ", "i").replace("I", "i").lower().replace("ı", "i")


def guide_list(cfg) -> list[dict]:
    g = cfg.raw.get("guides") or {}
    if not g.get("enabled", True):
        return []
    return [x for x in (g.get("list") or []) if x and x.get("slug") and x.get("title") and x.get("match")]


def guide_path(cfg, slug: str) -> Path:
    return cfg.root / "content" / "guides" / f"{slug}.json"


def load_guides(cfg) -> list[dict]:
    """Yayımlanmış rehberler (ayarlardaki sırayla)."""
    out = []
    for spec in guide_list(cfg):
        g = read_json(guide_path(cfg, spec["slug"]), None)
        if g and g.get("body"):
            out.append({**g, "spec": spec})
    return out


def matches(spec: dict, post: dict) -> bool:
    """Haber bu rehbere girer mi: başlıkta ya da etiketlerde `match` sözcüklerinden biri; başlıkta (varsa) `need`
    sözcüklerinden biri ve (varsa) `need_also` sözcüklerinden biri geçmeli; `skip` sözcükleri geçmemeli; `categories`
    verilmişse haber o kategorilerden birinde olmalı. `match_in: title` ise etiketlere bakılmaz."""
    if spec.get("categories") and post.get("category") not in spec["categories"]:
        return False
    title = _low(post.get("title", ""))
    hay = title + " | " + _low(" ".join(list(post.get("tags") or []) + list(post.get("entities") or [])))
    if spec.get("match_in") == "title":
        hay = title
    if not any(_low(m) in hay for m in spec.get("match") or []):
        return False
    for key in ("need", "need_also"):
        if spec.get(key) and not any(_low(n) in title for n in spec[key]):
            return False
    if any(_low(s) in hay for s in spec.get("skip") or []):
        return False
    return True


def related_posts(spec: dict, posts: list[dict], lookback_days: float, limit: int) -> list[dict]:
    out = []
    for p in posts:   # yeniden eskiye
        if hours_since(p.get("published_at")) > lookback_days * 24:
            break
        if matches(spec, p):
            out.append(p)
            if len(out) >= limit:
                break
    return out


def numbers(text: str) -> set[str]:
    """Metindeki 3+ haneli rakamlar (nokta/virgül ayırıcıları atılmış). Yıllar (2000–2039) sayılmaz."""
    out = set()
    for m in _NUM.findall(text or ""):
        d = re.sub(r"\D", "", m)
        if len(d) >= 3 and not (len(d) == 4 and 2000 <= int(d) <= 2039):
            out.add(d)
    return out


def unsupported_numbers(body: str, posts: list[dict]) -> list[str]:
    """Rehberde geçip dayandığı haberlerin hiçbirinde birebir geçmeyen rakamlar (uydurma ya da hesaplanmış)."""
    have = set()
    for p in posts:
        have |= numbers(" ".join([p.get("title", ""), p.get("summary", ""), p.get("body", "")]))
    return sorted(numbers(body) - have)


def signature(posts: list[dict]) -> list[str]:
    return [f"{p['id']}@{p.get('refreshed_at') or p.get('published_at') or ''}" for p in posts]


def guide_system(site_name: str) -> str:
    return f"""You are the senior editor of "{site_name}", a Turkish technology news site. You maintain an evergreen
GUIDE page in Türkiye Türkçesi that people find on Google when they search for the current Türkiye price, fee or
rule of something (for example "Togg fiyat listesi", "IMEI kayıt ücreti", "elektrikli araç şarj ücretleri").
You write the guide ONLY from the RELATED ARTICLES, which our newsroom has already published with sources.

Accuracy rules (most important):
- Every number in the guide (prices, fees, percentages, capacities, dates) must appear in the RELATED ARTICLES and
  must be written with exactly the same digits as there (1.328.000 TL stays 1.328.000 TL). Never compute, convert,
  round, add up, average or estimate numbers, and never use your own memory.
- The newest article wins: when two articles give different values for the same thing, use the newest one and,
  if useful, mention the previous value as "önceki fiyat" with its month.
- Say for which month/date each price or fee is valid ("Kasım 2026 fiyat listesine göre"). If the newest information
  is older than about two months, say clearly that it is the last announced value.
- If the articles do not contain something a reader would expect (a model's price, a campaign), do not invent it;
  leave it out or say in one short sentence that it has not been announced.

Form:
- body: Markdown, 300–900 words. Start with a 2–3 sentence answer paragraph: the current key numbers and the date
  they are valid for (this is what searchers want). Then "## " sections; use Markdown tables for prices and fees
  (columns such as Model / Versiyon / Fiyat / Geçerlilik). Group logically (by model, brand or type). Add a short
  section on what changed recently. Do not add links, a sources list or a "last updated" line; the site adds them.
- summary: 1–2 sentences, ≤180 characters, the current headline numbers with their date.
- seo_title: ≤60 characters, natural search phrase with the current month and year if prices are monthly
  (e.g. "Togg fiyat listesi Kasım 2026: güncel T10X ve T10F fiyatları").
- meta_description: ≤155 characters.
- faq: 3–5 short questions people search for, each answered in 1–2 sentences from the articles (same number rules).
- changes: one short Turkish sentence on what changed compared to the PREVIOUS VERSION ("İlk sürüm." if none).
- used: the ids of the articles you actually used.
Tone: calm, clear, helpful; no hype, no clickbait, no advice on whether to buy."""


def guide_user(spec: dict, posts: list[dict], today: str, tz: str, previous: dict | None) -> str:
    parts = [f"TODAY: {today}", "",
             f"GUIDE: {spec.get('h1') or spec['title']}",
             f"COVERS: {spec.get('about') or spec['title']}", "", "RELATED ARTICLES (newest first):"]
    for p in posts:
        parts += [f"--- id: {p['id']} | published: {tr_date(p.get('published_at'), tz, with_time=False)}"
                  + (f" | updated: {tr_date(p.get('refreshed_at'), tz, with_time=False)}" if p.get("refreshed_at") else ""),
                  f"title: {p.get('title', '')}", f"summary: {p.get('summary', '')}",
                  f"sources: {', '.join(s.get('name', '') for s in p.get('sources') or [])}",
                  (p.get("body") or "")[:5000], ""]
    if previous and previous.get("body"):
        parts += ["PREVIOUS VERSION OF THE GUIDE (keep its useful structure; update the numbers from the articles):",
                  previous["body"][:6000]]
    return "\n".join(parts)


def save_guide(cfg, g: dict) -> None:
    write_json(guide_path(cfg, g["slug"]), g)
@@@SM@@@ FILE templates/guide.html
{% extends "base.html" %}
{% from "_macros.html" import crumbs %}
{% set active_cat = guide.category %}
{% block title %}{{ guide.seo_title or guide.h1 }} | {{ site.name }}{% endblock %}
{% block description %}{{ guide.meta_description or guide.summary }}{% endblock %}
{% block og %}
<meta property="og:type" content="article">
<meta property="og:title" content="{{ guide.seo_title or guide.h1 }}">
<meta property="og:description" content="{{ guide.meta_description or guide.summary }}">
<meta property="og:url" content="{{ guide.abs_url }}">
<meta property="og:image" content="{{ site.og_image }}">
<meta name="twitter:image" content="{{ site.og_image }}">
<meta property="article:published_time" content="{{ guide.iso }}">
<meta property="article:modified_time" content="{{ guide.mod_iso }}">
{% endblock %}
{% block head %}
<script type="application/ld+json">{{ {
  "@context": "https://schema.org", "@type": "Article",
  "mainEntityOfPage": {"@type": "WebPage", "@id": guide.abs_url},
  "headline": guide.h1[:110], "alternativeHeadline": guide.seo_title,
  "description": guide.meta_description or guide.summary,
  "image": [site.og_image],
  "datePublished": guide.iso, "dateModified": guide.mod_iso,
  "inLanguage": "tr-TR", "wordCount": guide.words, "isAccessibleForFree": true,
  "author": {"@type": "Organization", "name": site.name ~ " Haber Masası", "url": site.url ~ "/hakkinda/"},
  "editor": ({"@type": "Person", "name": legal.owner} if legal.owner else none),
  "publisher": {"@type": "NewsMediaOrganization", "@id": site.url ~ "/#org", "name": site.name,
                "publishingPrinciples": site.url ~ "/hakkinda/#ilkeler",
                "correctionsPolicy": site.url ~ "/hakkinda/#duzeltme",
                "logo": {"@type": "ImageObject", "url": site.logo, "width": 512, "height": 512}},
  "isBasedOn": guide.based|map(attribute='abs_url')|list
}|tojson }}</script>
{% endblock %}

{% block main %}
<article class="art guide" style="--c:{{ guide.cat_color }}">
  <div class="art-col">
  {{ crumbs([("Ana sayfa", site.base ~ "/", site.url ~ "/"), ("Rehberler", site.base ~ "/rehber/", site.url ~ "/rehber/"), (guide.title, guide.url, guide.abs_url)], '') }}
  <header class="art-head">
    <div class="meta-top">
      <a class="eyebrow" href="{{ site.base }}/rehber/">Sürekli güncel rehber</a>
      <span class="muted">Son güncelleme: <time datetime="{{ guide.mod_iso }}">{{ guide.updated_str }}</time></span>
    </div>
    <h1>{{ guide.h1 }}</h1>
    <p class="dek">{{ guide.summary }}</p>
  </header>

  <div class="art-body">{{ guide.body_html|safe }}</div>

  {% if guide.faq %}
  <section class="art-body guide-faq" aria-labelledby="sss">
    <h2 id="sss">Sık sorulanlar</h2>
    {% for f in guide.faq %}<h3>{{ f.q }}</h3>
    <p>{{ f.a }}</p>
    {% endfor %}
  </section>
  {% endif %}

  <section class="sources" aria-labelledby="dayanak">
    <h2 id="dayanak">Bu rehberin dayandığı haberler</h2>
    <ol>
      {% for p in guide.based %}
      <li><a href="{{ p.url }}">
        <span><span class="s-name">{{ p.date_short }}</span><span class="s-title">{{ p.title }}</span></span>
        <span class="s-go" aria-hidden="true">→</span>
      </a></li>
      {% endfor %}
    </ol>
    <p class="disclosure">
      Bu rehber, {{ site.name }}'de kaynaklarıyla yayımlanan haberlerden yapay zeka yardımıyla derlenir ve ilgili yeni
      bir haber yayımlandığında güncellenir. Rakamlar dayandığı haberlerdekiyle birebir aynıdır; fiyatlar kampanyaya,
      bayiye ve tarihe göre değişebilir, satın almadan önce resmi kaynaktan doğrulamanı öneririz.
      {% if legal.owner %}Sorumlu editör: {{ legal.owner }}. {% endif %}<a href="{{ site.base }}/hakkinda/#ilkeler">Yayın ilkelerimiz</a> ·
      Bir hata görürsen <a href="{{ site.base }}/iletisim/">bize bildir</a>.
    </p>
  </section>

  {% if guide.history_list %}
  <section class="guide-hist" aria-labelledby="gecmis">
    <h2 id="gecmis">Güncelleme geçmişi</h2>
    <ul>{% for h in guide.history_list %}<li><time>{{ h.date }}</time><span>{{ h.note }}</span></li>{% endfor %}</ul>
  </section>
  {% endif %}

  {% if others %}
  <nav class="guide-others" aria-label="Diğer rehberler">
    <h2>Diğer güncel rehberler</h2>
    {% for g in others %}<a href="{{ g.url }}"><b>{{ g.title }}</b><span>{{ g.updated_str }}</span></a>{% endfor %}
  </nav>
  {% endif %}
  </div>
</article>
{% endblock %}
@@@SM@@@ FILE templates/guides.html
{% extends "base.html" %}
{% from "_macros.html" import crumbs %}
{% block title %}Güncel rehberler: fiyat listeleri, ücretler ve kurallar | {{ site.name }}{% endblock %}
{% block description %}Türkiye'deki güncel otomobil ve telefon fiyatları, IMEI kayıt ücreti, şarj ücretleri gibi sık aranan bilgiler; her yeni gelişmede güncellenir.{% endblock %}
{% block main %}
<header class="page-head wrap" style="--c:#6E6E73">
  <span class="eyebrow">Rehberler</span>
  <h1>Sürekli güncel<br>rehberler</h1>
  <p>Sık aranan fiyatlar, ücretler ve kurallar tek sayfada. İlgili yeni bir haber yayımlandığında güncellenir.</p>
</header>
{{ crumbs([("Ana sayfa", site.base ~ "/", site.url ~ "/"), ("Rehberler", site.base ~ "/rehber/", site.url ~ "/rehber/")], 'narrow') }}
<div class="narrow guide-list">
  {% for g in guides %}
  <a href="{{ g.url }}" style="--c:{{ g.cat_color }}">
    <span class="eyebrow sm">{{ g.cat_label }}</span>
    <b>{{ g.h1 }}</b>
    <span class="gl-dek">{{ g.summary }}</span>
    <span class="muted">Son güncelleme: {{ g.updated_str }}</span>
  </a>
  {% endfor %}
</div>
{% endblock %}
@@@SM@@@ FILE tests/test_guides.py
"""Sürekli güncel rehberler: eşleşme, uydurma rakam engeli, yazım turu ve site sayfaları."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haberbot import guides as G  # noqa: E402
from haberbot.site import SiteBuilder  # noqa: E402
from tests.test_home import _App, _post  # noqa: E402

SPEC = {"slug": "imei-kayit-ucreti", "title": "IMEI kayıt ücreti", "h1": "IMEI kayıt ücreti: güncel harç",
        "category": "teknoloji", "match": ["imei"]}


def test_matching_rules():
    p = {"title": "IMEI kayıt ücreti 2027 yılında 69.358 TL olacak", "tags": ["IMEI"], "category": "teknoloji"}
    assert G.matches(SPEC, p)                                                     # IMEI = imei (I/ı farkı yok)
    apple = {"match": ["iphone"], "need": ["fiyat", "zam"], "need_also": ["türkiye"]}
    assert G.matches(apple, {"title": "iPhone 17e Türkiye fiyatı açıklandı"})
    assert not G.matches(apple, {"title": "iPhone Duo tamir ücretleri açıklandı"})   # fiyat/zam yok
    assert not G.matches(apple, {"title": "iPhone 18 fiyatı ABD'de açıklandı"})      # Türkiye yok
    sam = {"match": ["galaxy"], "need": ["fiyat"], "skip": ["geely"]}
    assert not G.matches(sam, {"title": "Geely Galaxy E5 fiyatı", "tags": ["Geely"]})
    car = {"match": ["fiyat listesi"], "categories": ["otomotiv"]}
    assert G.matches(car, {"title": "Fiat Kasım 2026 fiyat listesi", "category": "otomotiv"})
    assert not G.matches(car, {"title": "Apple fiyat listesi", "category": "teknoloji"})
    sub = {"match": ["apple tv"], "match_in": "title", "need": ["ücret"]}
    assert not G.matches(sub, {"title": "HomePod mini ücreti", "tags": ["Apple TV"]})  # yalnızca başlık


def test_unsupported_numbers():
    posts = [{"title": "IMEI kayıt ücreti 69.358 TL", "summary": "", "body": "Ücret 2027'de 69.358 TL; 2026'da 45.614 TL."}]
    assert G.unsupported_numbers("Güncel ücret 69.358 TL, önceki 45.614 TL (2027).", posts) == []
    assert G.unsupported_numbers("Ücret 70.000 TL civarında.", posts) == ["70000"]          # uydurma rakam
    assert G.unsupported_numbers("Artış 23.744 TL oldu.", posts) == ["23744"]                # hesaplanmış rakam


def _imei_posts(a):
    a.store.save_post(_post(1, 30, title="2027 IMEI kayıt ücreti belli oldu: 69.358 TL", tags=["IMEI"],
                            body="## Ücret\n\nYurt dışından getirilen telefonlar için IMEI kayıt ücreti 69.358 TL oldu."))
    a.store.save_post(_post(2, 50, title="IMEI kayıt ücreti 2026 yılında 45.614 TL", tags=["IMEI"],
                            body="## Ücret\n\n2026 yılı IMEI kayıt ücreti 45.614 TL olarak uygulanıyor."))


def test_guide_written_checked_and_published(monkeypatch):
    with _App() as (cfg, a):
        cfg.raw["guides"] = {"enabled": True, "min_posts": 2, "list": [SPEC]}
        _imei_posts(a)
        calls = []
        long = " ".join(["Yurt dışından getirilen telefonlar için kayıt kuralları geçerlidir."] * 20)

        class LLM:
            def __init__(self, fee):
                self.fee = fee

            def json(self, model, system, user, schema, **_k):
                calls.append(user)
                return {"seo_title": "IMEI kayıt ücreti 2027", "meta_description": "Güncel IMEI kayıt ücreti.",
                        "summary": f"IMEI kayıt ücreti {self.fee} TL.",
                        "body": f"IMEI kayıt ücreti {self.fee} TL oldu; 2026'da 45.614 TL idi.\n\n## Kurallar\n\n{long}\n\n"
                                "| Yıl | Ücret |\n|---|---|\n| 2027 | 69.358 TL |\n| 2026 | 45.614 TL |",
                        "faq": [{"q": "IMEI ücreti ne kadar?", "a": f"{self.fee} TL."}],
                        "changes": "İlk sürüm.", "used": ["p01", "p02", "uydurma"]}

        a.llm = LLM("70.000")                                    # haberlerde olmayan rakam → bir kez düzelttirilir
        assert a.guides_tick() is False                          # yine olmuyor → yayımlanmaz
        assert len(calls) == 2 and "CORRECTION" in calls[1] and "70000" in calls[1]
        assert not G.guide_path(cfg, SPEC["slug"]).exists() and a.state["guide_tried"][SPEC["slug"]]
        assert a.guides_tick() is False and len(calls) == 2      # aynı haberlerle tekrar denenmez
        a.store.save_post(_post(3, 1, title="IMEI kayıt ücreti için e-Devlet dönemi", tags=["IMEI"],
                                body="IMEI kaydı için ücret 69.358 TL olarak e-Devlet'ten ödenebilecek."))
        a.llm = LLM("69.358")
        assert a.guides_tick() is True and len(calls) == 3
        g = G.load_guides(cfg)[0]
        assert g["based_on"] == ["p01", "p02"] and g["history"][0]["note"] == "İlk sürüm."
        assert a.guides_tick() is False                          # yeni haber yok: yeniden yazılmaz

        SiteBuilder(cfg).build()
        page = (cfg.out_dir / "rehber" / SPEC["slug"] / "index.html").read_text(encoding="utf-8")
        assert "IMEI kayıt ücreti: güncel harç" in page and "<table>" in page and "Son güncelleme" in page
        assert "noindex" not in page and "Bu rehberin dayandığı haberler" in page
        assert (cfg.out_dir / "rehber" / "index.html").exists()
        sm = (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")
        assert "/rehber/imei-kayit-ucreti/" in sm
        art = max((f.read_text(encoding="utf-8") for f in cfg.out_dir.rglob("haber-2/index.html")), key=len)
        assert 'class="guide-box"' in art and "/rehber/imei-kayit-ucreti/" in art   # eski haberden güncel rehbere
@@@SM@@@ SHA
2819705e49aab276245f33609b5a699b193464b2238a0f3ec004cc8095bbbcce config.yaml
ae45a4560a43dbf88aefcbd0cebf348f03d3749be762727d90894f1facb1f0af haberbot/app.py
fec09ae210084a9188dd39e60e035459de6107596988c415ccc81d5400d1fc23 haberbot/llm.py
39fe58c7ab9a727ebf95a238ef0848942f97aa7f2727ff5d54e5f7b6195f17b1 haberbot/site.py
8e757a36e83c649b7e9d3990beb7b9a4fcadb67c2e53f0458e275750a6dc7146 static/style.css
fbbd9b4e74d5ef8374754ad3dbae5c6c3976d73f3203cec576c4fee520469a4b templates/article.html
a03ee57f650c15828c18eb93b9e9feef123da7ef4c7eb8a2dc03d82cdea09a87 templates/base.html
f39872f82567f139f7638e7f977bf5e9dafde007c834bb419c4ba3a2f5a13e44 templates/sitemap.xml
614a0736b9a768636d6b33a026b9e02cbf92b891639937114fe516c307af3d75 haberbot/guides.py
4938b420c017e7fb3aacbaab52bb7992b8b72e64ca4eaf413ad6624f9ee1861f templates/guide.html
cd078c172b11f0249bf64535e5ebdb3f2c8a86a0c7fbc4c2ac8134a01f2b83a0 templates/guides.html
40c21c61f4400b15808ac2d85bfd83c8ce1120b678c32a236a364a5137cb0486 tests/test_guides.py
