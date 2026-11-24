SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -49,4 +49,10 @@
   bing_site_verification: ""
   yandex_verification: ""
+  # Zayıf sayfa ayıklama: bu tarihten önce yayınlanmış, kısa (thin_words kelimeden az) ve tek kaynaklı, Google'da hiç
+  # gösterim almamış haberler sitede kalır ama arama motorlarına "dizine ekleme" denir ve site haritasından çıkar.
+  # Google'da gösterim almış haberlerin listesi: seo-keep.txt (bunlar dizinde kalır).
+  prune_thin: true
+  prune_before: "2026-11-25"
+  thin_words: 250
   # Yeni haberleri Bing ve Yandex'e anında bildir (ücretsiz, hesap gerekmez)
   indexnow: true
@@ -67,7 +73,9 @@
   min_importance: 7              # 1-10. Haber masasının aday eşiği
   min_must_read: 7               # 1-10. Yayın yönetmeninin yeni haber eşiği (7: sağlam ve yayına değer, 8: geniş kitle için önemli)
+  min_outlets: 2                 # Tek kaynaklı haber, ikinci bir yayın kuruluşu da verene kadar bekler
+                                 # (şirketin kendi resmi duyurusu ya da yönetmen puanı 9+ ise beklemez)
   max_per_company_per_day: 0     # Aynı şirketten 24 saatte en fazla kaç haber (0 = sınır yok)
   max_drafts_per_run: 3          # Bir taramada aynı anda yazılan taslak (fazlası kaybolmaz, bir sonraki taramada gelir)
-  max_drafts_per_day: 0          # Günlük üst sınır (0 = sınır yok)
+  max_drafts_per_day: 10         # Günlük üst sınır (Kasım 2026: az ama dolu haber; Google çekirdek güncellemesi sonrası)
   burst: 2                       # Günlük sınır varsa: günün başında sınırın önüne geçebilecek taslak sayısı
   triage_batch: 100              # Bir turda ayıklanan en fazla öğe (fazlası sonraki tura kalır, kaybolmaz)
@@ -102,4 +110,13 @@
   # Diğer fotoğraflar haberin paragrafları arasına, kalanlar sondaki galeriye kaynağıyla yerleşir.
   photos: true
+  # press: yalnızca şirketlerin basın görselleri (resmi duyurular, basın/haber odası alan adları) ve açık lisanslı
+  # Wikipedia görselleri; haber sitelerinin kendi fotoğrafları kullanılmaz, onların yerine habere özel kapak gelir.
+  # any: kaynak haberin görselleri de kullanılır (eski davranış).
+  photo_policy: press
+  press_hosts: [apple.com, samsung.com, blog.google, googleblog.com, google.com, openai.com, anthropic.com,
+                microsoft.com, nvidia.com, sony.com, playstation.com, xbox.com, nintendo.com, tesla.com, togg.com.tr,
+                bmwgroup.com, mercedes-benz.com, volkswagen-newsroom.com, stellantis.com, hyundai.com, kia.com,
+                byd.com, xiaomi.com, huawei.com, honor.com, oneplus.com, nothing.tech, meta.com, fb.com, amazon.com,
+                aboutamazon.com, spacex.com, wikimedia.org]
   photo_limit: 16                 # haber başına en fazla fotoğraf (haberin içine paragraf paragraf yerleşir)
   photo_local: 4                  # bunların kaçı siteye kopyalanır (kalanlar kaynaktaki adresinden gösterilir)
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -343,7 +343,9 @@
                 self._merge_sources(x["target"], q["items"])
             elif act == "hold":
-                q["holds"] = int(q.get("holds", 0)) + 1
+                # ikinci kaynağı beklenen haber tur sınırına takılmaz; sıradaki süre sınırı (_queue) yine geçerli
+                if not str(x.get("reason", "")).startswith("tek kaynak"):
+                    q["holds"] = int(q.get("holds", 0)) + 1
                 q["held_at"] = iso(now_utc())
-                if q["holds"] <= 8:
+                if q.get("holds", 0) <= 8:
                     keep.append(q)
             self._edit_log(q, act, x)
@@ -487,4 +489,5 @@
         sınırı. Günlük adet sınırı yoktur: eşiği geçen her haber gelir, geçemeyen gelmez."""
         cap = int(self.cfg.get("editorial", "max_per_company_per_day", 0) or 0)   # 0 = sınır yok
+        min_out = int(self.cfg.get("editorial", "min_outlets", 0) or 0)            # tek kaynaklı haber bekler
         day_keys: dict[str, int] = {}
         for c in covered:
@@ -537,6 +540,12 @@
                     round_targets.add(dup)
                 continue
+            its = queue[i].get("items") or []
+            outlets = {it.get("credit") for it in its if it.get("credit")}
+            official = any(it.get("kind") == "official" for it in its)
             if mr < min_score:
                 x["action"], x["reason"] = "skip", f"önem {mr}/10, eşik {min_score}"
+            elif min_out and len(outlets) < min_out and not official and mr < 9:
+                # Google tek kaynaktan yeniden yazılmış haberi değersiz sayıyor: ikinci bir yayın da verene kadar bekle
+                x["action"], x["reason"] = "hold", "tek kaynak, ikinci bir yayın bekleniyor"
             elif cap and mr < 9 and any(day_keys.get(k, 0) >= cap for k in keys):
                 x["action"], x["reason"] = "skip", "aynı şirketten son 24 saatte haber var"
@@ -694,11 +703,39 @@
         return bool((p.get("cover_headline") and p.get("cover_line_v") == COVERLINE_V) or p.get("cover_line_skip"))
 
+    def _related_coverage(self, sources: list[dict], previous: dict | None = None, n: int = 3) -> list[dict]:
+        """Sitede daha önce yayınlanmış ilgili haberler (yazara bağlam için): kaynak başlıklarında geçen etiket ve
+        şirket/ürün adlarıyla eşleşen, son 90 günün en ilgili haberleri."""
+        text = " ".join(f"{s.get('title', '')} {(s.get('text') or s.get('summary') or '')[:400]}" for s in sources).lower()
+        if not text.strip():
+            return []
+        skip = (previous or {}).get("id")
+        scored = []
+        for p in self.store.posts()[:600]:
+            if p.get("id") == skip or hours_since(p.get("published_at")) > 24 * 90:
+                continue
+            names = {str(x).strip().lower() for x in list(p.get("tags") or []) + list(p.get("entities") or [])
+                     if len(str(x).strip()) >= 3}
+            score = sum(1 for x in names if re.search(r"(?<![\wçğıöşü])" + re.escape(x) + r"(?![\wçğıöşü])", text))
+            if score:
+                scored.append((score, p.get("published_at") or "", p))
+        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)   # en çok eşleşen, eşitse en yeni
+        out = []
+        for _, _, p in scored[:n]:
+            out.append({"date": tr_date(p.get("published_at"), self.cfg.tz, with_time=False),
+                        "title": p.get("title", ""), "summary": clip(p.get("summary") or "", 220)})
+        return out
+
     def _write(self, sources: list[dict], previous: dict | None = None, instruction: str | None = None,
                _retry: bool = True) -> dict:
         cfg = self.cfg
+        try:
+            related = self._related_coverage(sources, previous)
+        except Exception as e:  # noqa: BLE001
+            log.warning("İlgili eski haberler bulunamadı: %s", e)
+            related = []
         out = self.llm.json(
             cfg.get("ai", "writer_model", "claude-sonnet-5"),
             write_system(self.brand),
-            write_user(sources, self.today(), previous, instruction),
+            write_user(sources, self.today(), previous, instruction, related),
             WRITE_SCHEMA, max_tokens=16000, effort=cfg.get("ai", "writer_effort", "medium"))
         cat = out.get("category") if out.get("category") in CATEGORIES else None
@@ -2879,4 +2916,11 @@
             log.warning("Fotoğraflar alınamadı (%s): %s", d.get("id"), e)
             return False
+        if str(cfg.get("images", "photo_policy", "any") or "any").lower() == "press":
+            # yalnızca şirketlerin basın görselleri ve açık lisanslı görseller: haber sitelerinin fotoğrafları kullanılmaz
+            hosts = list(cfg.get("images", "press_hosts", []) or [])
+            n0 = len(got)
+            got = [g for g in got if photos.press_ok(g, hosts)]
+            if len(got) < n0:
+                log.info("Fotoğraf: %d görsel haber sitesine ait olduğu için kullanılmadı (%s)", n0 - len(got), d.get("id"))
         vetted = self._vet_photos(d, got)
         if not vetted and not any(g.get("credit") == "Wikipedia" for g in got):
--- a/haberbot/photos.py
+++ b/haberbot/photos.py
@@ -319,4 +319,17 @@
                     "kind": "wiki", **classify(im)}
     return None
+
+
+def press_ok(rec: dict, hosts: list[str] | tuple = ()) -> bool:
+    """Basın görseli mi: şirketin kendi duyurusundaki görsel, açık lisanslı Wikipedia görseli ya da görsel adresi bir
+    şirketin basın/haber odası alan adında. Haber sitelerinin kendi fotoğrafları değil."""
+    if rec.get("src_kind") == "official" or rec.get("kind") == "wiki" or rec.get("credit") == "Wikipedia":
+        return True
+    host = urlsplit(rec.get("src") or "").netloc.lower().split(":")[0]
+    if not host:
+        return False
+    if host.startswith(("newsroom.", "press.", "pressroom.")):
+        return True
+    return any(host == h or host.endswith("." + h) for h in (x.lower().strip() for x in hosts) if h)
 
 
@@ -355,5 +368,6 @@
             hashes.append(h)
             picked.append({"image": im, "src": c["url"], "credit": s.get("name") or urlsplit(url).netloc,
-                           "page": url, "alt": c["alt"], "kind": c["kind"], **classify(im)})
+                           "page": url, "alt": c["alt"], "kind": c["kind"], "src_kind": s.get("kind") or "media",
+                           **classify(im)})
             n += 1
         if len(picked) >= limit:
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -100,7 +100,11 @@
         Vodafone moves, internet restrictions); the Turkish startup ecosystem (a Turkish startup's notable round, exit or
         acquisition — Dream Games, Insider, Getir, Peak, Papara, Trendyol… — Turkish founders abroad, big Turkish VC funds)
+        Also 8: what many people in Türkiye will actively SEARCH for on Google: the official Türkiye price, sale date or
+        availability of a well-known phone, computer, console or car (including a car brand's new monthly Türkiye price
+        list), new taxes, fees and rules that hit users' wallets (IMEI registration fee, ÖTV, e-Devlet procedures),
+        price changes of popular services in Türkiye (Netflix, Spotify, YouTube Premium, PlayStation Plus, operators)
    7    noteworthy: notable launches from well-known mid-tier brands sold in Türkiye; credible and detailed leaks about a
-        hugely anticipated flagship (Mark Gurman, certification filings, official teasers); the Türkiye price and
-        availability of a flagship; a smaller Turkish startup round with a clear, interesting idea
+        hugely anticipated flagship (Mark Gurman, certification filings, official teasers); a smaller Turkish startup
+        round with a clear, interesting idea
    ≤6   everything else, in particular:
         - startups and funding OUTSIDE Türkiye: rounds, valuations and acquisitions of foreign startups are ≤5, unless the
@@ -350,5 +354,5 @@
 - title: the H1. ≤90 characters, informative and specific (who did what), starts with or contains the focus_keyword. Sentence case (only first word and proper nouns capitalized). No trailing period, no clickbait.
 - summary: 1–2 plain sentences, ≤180 characters, the core news in everyday language (shown under the headline and on Instagram).
-- body: Markdown, 180–320 words. Structure: a 2–3 sentence lead paragraph that answers who/what/when and contains the focus_keyword; then 2 sections (3 only if really needed), each starting with a "## " subheading (short, informative, natural search-style phrase such as "## iPhone 18 Pro neler sunuyor?", "## Fiyat ve çıkış tarihi" or "## Girişim ne yapıyor?"), each followed by 1–2 short paragraphs. Use a bullet list only for 3+ concrete items from the sources. Bold at most 2 key terms. The LAST paragraph (not under a new heading) must start with "**Neden önemli?** " followed by 1–2 grounded sentences (no speculation beyond what sources support). Do not include a sources list or links; the site adds them. If the sources are thin, write fewer, shorter sections rather than padding — accuracy beats length.
+- body: Markdown, 320–550 words: the reader should not need to open the sources to understand the news. Structure: a 2–3 sentence lead paragraph that answers who/what/when and contains the focus_keyword; then 3–4 sections, each starting with a "## " subheading (short, informative, natural search-style phrase such as "## iPhone 18 Pro neler sunuyor?", "## Önceki modelden farkı ne?", "## Türkiye'de fiyat ve satış tarihi" or "## Girişim ne yapıyor?"), each followed by 1–3 short paragraphs. Cover, when the sources allow: (a) what exactly is new, with the concrete details from the sources (features, specs, availability, numbers); (b) context: how it differs from the previous model, the rivals or the company's earlier moves, using only the sources and the RELATED EARLIER COVERAGE list (never your own memory); (c) Türkiye: the Türkiye price, sale date, availability or rules if the sources give them; for products or services people in Türkiye could buy or use, if the sources say nothing about Türkiye, write one honest sentence that it has not been announced yet. Use a bullet list, or a short Markdown table, for 3+ concrete specs, prices or dates from the sources. Bold at most 2 key terms. The LAST paragraph (not under a new heading) must start with "**Neden önemli?** " followed by 1–2 grounded sentences (no speculation beyond what sources support). Do not include a sources list or links; the site adds them. Length must come from facts, never from padding, repetition or filler: if the sources are genuinely thin, write a shorter article (but at least a lead and 2 sections) rather than inventing anything.
 - category: one of the allowed keys. If the main subject is an AI model, assistant, feature or AI company (ChatGPT, Gemini, Copilot, Claude…), always "super-zeka", even inside a Google/Microsoft/Apple product; a startup's funding round → "girisimcilik"; games and gaming platforms → "gaming"; cars, EVs, car makers, charging and robotaxis → "otomotiv".
 - tags: 3–6 tags that people search for: companies, products, models, games, car models, technologies, places (e.g. "Apple", "iPhone 18", "TOGG", "elektrikli otomobil", "GTA 6", "OpenAI"). Use the official spelling consistently. If the story is mainly about Turkey or a Turkish company, include the tag "Türkiye". Never use generic words like "teknoloji", "yapay zeka", "oyun", "otomobil", "girişim", "haber", and never use the names of news outlets (TechCrunch, The Verge, Webrazzi…).
@@ -392,5 +396,5 @@
 
 def write_user(sources: list[dict], today: str, previous: dict | None = None,
-               instruction: str | None = None) -> str:
+               instruction: str | None = None, related: list[dict] | None = None) -> str:
     parts = [f"TODAY: {today}", "", "SOURCES:"]
     for i, s in enumerate(sources, 1):
@@ -422,4 +426,8 @@
             f"EDITOR INSTRUCTION (follow it, while keeping all accuracy rules): {instruction or 'Metni daha akıcı ve net hale getir.'}",
         ]
+    if related:
+        parts += ["", "RELATED EARLIER COVERAGE ON OUR SITE (already published, sourced facts; use only for brief "
+                      "context such as the previous model or the company's earlier move; never contradict the SOURCES):"]
+        parts += [f"- {r.get('date', '')}: {r.get('title', '')} — {r.get('summary', '')}" for r in related]
     if instruction and (previous is None or previous.get("_update")):
         parts += ["", f"EDITOR INSTRUCTION (follow it, while keeping all accuracy rules): {instruction}"]
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -18,5 +18,5 @@
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "20"
+ASSET_V = "21"
 FOREIGN_PRICE = re.compile(r"(?=.*fiyat)(?=.*(\$|€|£|¥|dolar|euro|avro|sterlin|yuan|yen\b))", re.I)
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
@@ -26,5 +26,5 @@
 def render_body(md: str) -> str:
     safe = htmlmod.escape(md or "", quote=False)
-    out = markdown.markdown(safe, extensions=["sane_lists"], output_format="html")
+    out = markdown.markdown(safe, extensions=["sane_lists", "tables"], output_format="html")
     out = re.sub(r'href="(?!https?://)[^"]*"', 'href="#"', out)
     out = re.sub(r"<img\b[^>]*>", "", out)          # metne dışarıdan görsel gömülmez (fotoğraflar ayrı, kaynaklı eklenir)
@@ -49,4 +49,24 @@
             return rest
     return meta
+
+
+def load_keep() -> set[str]:
+    """Google'da gösterim almış haberlerin adresleri (seo-keep.txt): kısa olsalar da dizinde kalırlar."""
+    f = ROOT / "seo-keep.txt"
+    if not f.exists():
+        return set()
+    return {ln.strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")}
+
+
+def is_thin(p: dict, words: int, seo: dict, keep: set[str]) -> bool:
+    """Zayıf sayfa: eski dönemde yazılmış, kısa ve tek kaynaklı, Google'da hiç gösterim almamış haber. Sitede kalır ama
+    arama motorlarına "dizine ekleme" denir ve site haritasına girmez (Kasım 2026 çekirdek güncellemesi sonrası)."""
+    if not seo.get("prune_thin", True):
+        return False
+    before = str(seo.get("prune_before") or "")
+    if not before or (p.get("published_at") or "") >= before:
+        return False
+    outlets = {s.get("name") for s in p.get("sources") or [] if s.get("name")}
+    return words < int(seo.get("thin_words", 250) or 250) and len(outlets) < 2 and p.get("slug") not in keep
 
 
@@ -249,4 +269,6 @@
         )
         self.env.filters["weburl"] = weburl
+        self.seo = dict(cfg.raw.get("seo") or {})
+        self.keep = load_keep()
 
     def _post_view(self, p: dict) -> dict:
@@ -311,5 +333,6 @@
             "credits": list(dict.fromkeys(s["name"] for s in p.get("sources", []))),
             "minutes": reading_minutes(p.get("body", "")),
-            "words": len(plain(p.get("body", "")).split()),
+            "words": (nw := len(plain(p.get("body", "")).split())),
+            "thin": is_thin(p, nw, self.seo, self.keep),
             **(media := self._media(p, short, render_body(p.get("body", "")))),
             "toc": [{"id": m.group(1), "text": re.sub("<[^>]+>", "", m.group(2))}
@@ -482,4 +505,5 @@
                 tag_label.setdefault(t["slug"], Counter())[t["label"]] += 1
         tags = sorted(({"slug": s, "label": tag_label[s].most_common(1)[0][0], "count": len(ps),
+                        "idx_count": sum(1 for q in ps if not q["thin"]),
                         "url": f"{b}/etiket/{s}/", "lastmod": ps[0]["mod_iso"]}
                        for s, ps in tag_posts.items()), key=lambda t: (-t["count"], t["label"].lower()))
@@ -591,5 +615,5 @@
             related = [q for q in related if not nxt or q["id"] != nxt["id"]]
             self._write(f"{p['path']}/index.html", self.env.get_template("article.html").render(
-                **ctx, post=p, related=related, next_post=nxt, canonical=p["abs_url"]))
+                **ctx, post=p, related=related, next_post=nxt, canonical=p["abs_url"], noindex=p["thin"]))
             # eski adres (/haber/slug/) yeni adrese yönlenir
             self._redirect(f"haber/{p['slug']}/index.html", p["abs_url"], p["title"])
@@ -618,5 +642,5 @@
             self._write(f"etiket/{t['slug']}/index.html", self.env.get_template("tag.html").render(
                 **ctx, tag=t, posts=tag_posts[t["slug"]][:120], canonical=f"{cfg.site_url}/etiket/{t['slug']}/",
-                noindex=t["count"] < 2))
+                noindex=t["idx_count"] < 2))
 
         self._write("hakkinda/index.html", self.env.get_template("about.html").render(
@@ -658,6 +682,6 @@
             **ctx, posts=posts[:40], now_rfc=format_datetime(now_utc())))
         self._write("sitemap.xml", self.env.get_template("sitemap.xml").render(
-            **ctx, posts=posts, cats=[c for c in cats if c["count"]], tags=[t for t in tags if t["count"] >= 2],
-            pages=pages))
+            **ctx, posts=[p for p in posts if not p["thin"]], cats=[c for c in cats if c["count"]],
+            tags=[t for t in tags if t["idx_count"] >= 2], pages=pages))
         # ana ekrana eklenebilir site (PWA bildirimi)
         self._write("manifest.webmanifest", json.dumps({
@@ -668,5 +692,5 @@
                       {"src": f"{b}/static/logo.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}]},
             ensure_ascii=False, indent=1))
-        news = [p for p in posts if hours_since(p.get("published_at")) <= 48][:1000]
+        news = [p for p in posts if hours_since(p.get("published_at")) <= 48 and not p["thin"]][:1000]
         self._write("news-sitemap.xml", self.env.get_template("news-sitemap.xml").render(**ctx, posts=news))
         self._write("robots.txt", "User-agent: *\nAllow: /\nDisallow: /api/\n\n"
--- a/static/style.css
+++ b/static/style.css
@@ -354,4 +354,7 @@
 .gal-title span { margin-left: 6px; font-size: 15px; font-weight: 500; color: var(--muted); letter-spacing: 0; }
 /* metnin içindeki fotoğraflar */
+.art-body table { width: 100%; border-collapse: collapse; margin: 22px 0; font-size: 16px; display: block; overflow-x: auto; }
+.art-body th, .art-body td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line, rgba(0,0,0,.1)); vertical-align: top; }
+.art-body th { font-weight: 600; background: var(--bg-alt); }
 .art-body figure.inl { margin: 28px 0; }
 .art-body figure.inl img { display: block; width: 100%; height: auto; border-radius: var(--r-md); background: var(--bg-alt); }
--- a/templates/about.html
+++ b/templates/about.html
@@ -16,9 +16,14 @@
     <li><strong>Kopyalama yok.</strong> Kaynak metinler çevrilip aktarılmaz; bilgiler özetlenip kendi cümlelerimizle yazılır.</li>
     <li><strong>Uydurma yok.</strong> Kaynaklarda olmayan rakam, tarih, alıntı ya da iddia eklenmez. Doğrulanmamış bilgiler kaynağına atfedilir.</li>
-    <li><strong>Fotoğraflar kaynağıyla.</strong> Haberlerdeki fotoğraflar, öncelikle ilgili şirketin basın için yayımladığı görsellerdir; bunlar yoksa haberin kaynağında yayımlanan görseller kullanılır. Her fotoğrafın altında kaynağı ve bağlantısı yer alır. Fotoğraf bulunamayan haberlerde habere özel renkli bir zemin kullanılır; yapay zeka ile üretilmiş temsili görseller altında belirtilir.</li>
+    <li><strong>Fotoğraflar kaynağıyla.</strong> Haberlerdeki fotoğraflar, ilgili şirketin basın için yayımladığı görseller ya da açık lisanslı (Wikipedia) görsellerdir; haber sitelerinin kendi fotoğraflarını kullanmayız (Kasım 2026'dan önceki bazı haberlerde kaynak yayının görselleri, kaynağıyla birlikte yer alır). Her fotoğrafın altında kaynağı ve bağlantısı yer alır. Fotoğraf bulunamayan haberlerde habere özel renkli bir zemin kullanılır; yapay zeka ile üretilmiş temsili görseller altında belirtilir.</li>
     <li><strong>Kaldırma talepleri.</strong> Bir fotoğrafın ya da metnin hak sahibiysen ve kaldırılmasını istiyorsan {% if site.contact_email %}<strong>{{ site.contact_email }}</strong> adresine{% else %}bize{% endif %} yaz; talebini hızla değerlendiririz.</li>
     <li><strong>Yapay zeka destekli yayın masası.</strong> Haberler yapay zeka destekli yayın masasında seçilir ve yazılır; bu durum her haberin altında belirtilir. Doğrulanmamış iddialar, söylentiler ve kaynakları çelişen haberler yayımlanmaz; resmi olmayan bilgiler ancak kaynağına açıkça atfedilerek aktarılır. Editör, yayındaki haberleri izler; hatalı bulunanları düzeltir ya da kaldırır.</li>
-    <li><strong>Düzeltme.</strong> Hatalı bir bilgi fark edersek haberi güncelleriz ya da kaldırırız.</li>
+    <li id="duzeltme"><strong>Düzeltme.</strong> Hatalı bir bilgi fark edersek haberi güncelleriz ya da kaldırırız; güncellenen haberlerde neyin değiştiği ve tarihi haberin başında yazar. Hata bildirimlerini {% if site.contact_email %}<strong>{{ site.contact_email }}</strong> adresinden{% else %}iletişim sayfasından{% endif %} alırız.</li>
+    <li><strong>Az ama dolu.</strong> Her gelişmeyi değil, okurlarımızın gerçekten bilmek isteyeceği haberleri yayımlarız. Tek bir yayının iddiasına dayanan haberler, başka bir kaynak da doğrulayana kadar beklenir; şirketlerin resmi duyuruları bunun dışındadır.</li>
   </ul>
+  {% if legal.owner %}
+  <h2>Sorumlu editör</h2>
+  <p>{{ site.name }}'nin yayın ilkelerini belirleyen ve yayımlanan haberlerden sorumlu olan editör <strong>{{ legal.owner }}</strong>'dir. Yayın masasının seçtiği ve yazdığı haberler bu ilkelere göre yayımlanır; editör yayındaki haberleri izler, gerektiğinde düzeltir ya da kaldırır.</p>
+  {% endif %}
   <h2>Takip ettiğimiz kaynaklar</h2>
   <p>{% for s in sources %}{{ s.name }}{{ ', ' if not loop.last }}{% endfor %}.</p>
--- a/templates/article.html
+++ b/templates/article.html
@@ -33,5 +33,8 @@
   "wordCount": post.words, "isAccessibleForFree": true,
   "author": {"@type": "Organization", "name": site.name ~ " Haber Masası", "url": site.url ~ "/hakkinda/"},
+  "editor": ({"@type": "Person", "name": legal.owner} if legal.owner else none),
   "publisher": {"@type": "NewsMediaOrganization", "@id": site.url ~ "/#org", "name": site.name,
+                "publishingPrinciples": site.url ~ "/hakkinda/#ilkeler",
+                "correctionsPolicy": site.url ~ "/hakkinda/#duzeltme",
                 "logo": {"@type": "ImageObject", "url": site.logo, "width": 512, "height": 512}},
   "isBasedOn": post.sources|map(attribute='url')|list
@@ -143,4 +146,5 @@
       {% if post.has_photo %}Fotoğraflar, altlarında belirtilen kaynaklara aittir.{% endif %}
       Ayrıntılar ve orijinal ifadeler için kaynaklara bakabilirsin.{% if post.updated_str %} Son güncelleme: {{ post.updated_str }}.{% endif %}
+      {% if legal.owner %}Sorumlu editör: {{ legal.owner }}. {% endif %}<a href="{{ site.base }}/hakkinda/#ilkeler">Yayın ilkelerimiz</a> ·
       Bir hata görürsen <a href="{{ site.base }}/iletisim/">bize bildir</a>.
     </p>
--- a/tests/test_editor.py
+++ b/tests/test_editor.py
@@ -23,4 +23,5 @@
 def test_guard_rules():
     with _App() as (cfg, a):
+        cfg.raw.setdefault("editorial", {})["min_outlets"] = 0   # tek kaynak kuralı ayrıca sınanır
         a.store.save_post(_post(1, 3, tags=["Honor"], entities=["Honor", "Honor Magic9"]))
         queue = [_q("Honor Watch 6 Pro launched", 8, ["Honor"]),           # aynı şirketten ikinci haber: sorun değil
@@ -47,4 +48,32 @@
         out = a._guard(queue, dec(), slots=3, min_score=7, covered=a._covered(48))
         assert out[0]["action"] == "skip" and "24 saat" in out[0]["reason"]
+
+
+def test_single_source_waits_for_second_outlet():
+    with _App() as (cfg, a):
+        cfg.raw.setdefault("editorial", {})["min_outlets"] = 2
+        two = _q("Galaxy S27 Türkiye fiyatı", 8, ["Samsung"])
+        two["items"].append({**two["items"][0], "url": "https://b.com/1", "credit": "Başka Yayın"})
+        off = _q("Apple iOS 27.2 yayınlandı", 8, ["Apple"])
+        off["items"][0]["kind"] = "official"
+        queue = [_q("Tek kaynaklı söylenti", 8, ["Foo"]), two, off, _q("Dev tanıtım", 9, ["Bar"])]
+        dec = {i: {"action": "publish", "target": "", "must_read": q["story"]["importance"], "reason": ""}
+               for i, q in enumerate(queue)}
+        out = a._guard(queue, dec, slots=5, min_score=7, covered=a._covered(48))
+        assert out[0]["action"] == "hold" and out[0]["reason"].startswith("tek kaynak")
+        assert out[1]["action"] == "publish"     # iki ayrı yayın
+        assert out[2]["action"] == "publish"     # şirketin kendi duyurusu
+        assert out[3]["action"] == "publish"     # 9+ önemli haber beklemez
+
+
+def test_related_coverage_finds_earlier_posts():
+    with _App() as (cfg, a):
+        a.store.save_post(_post(1, 30, tags=["Togg"], entities=["Togg", "Togg T10F"], title="Togg T10F satışa çıktı"))
+        a.store.save_post(_post(2, 40, tags=["Apple"], entities=["Apple"], title="Apple yeni iPad'i tanıttı"))
+        src = [{"title": "Togg T10F fiyatı güncellendi", "text": "Togg T10F için yeni fiyat listesi yayımlandı.",
+                "url": "https://x.com/a", "name": "X"}]
+        rel = a._related_coverage(src)
+        assert rel and rel[0]["title"] == "Togg T10F satışa çıktı"
+        assert all("Apple" not in r["title"] for r in rel)
 
 
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -54,4 +54,6 @@
         raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
         raw.setdefault("autonomy", {})["mode"] = "kural"     # testler canlı moddan bağımsız (tam otonom ayrıca sınanır)
+        raw.setdefault("editorial", {})["min_outlets"] = 0      # tek kaynak kuralı ve zayıf sayfa ayıklaması
+        raw.setdefault("seo", {})["prune_thin"] = False         # test_recovery / test_editor'da ayrıca sınanır
         self.cfg = Config(raw=raw, root=Path(self.tmp.name), site_url="https://smarity.com.tr", mock=True,
                           telegram_chat_id="1")
--- a/tests/test_photos.py
+++ b/tests/test_photos.py
@@ -130,4 +130,5 @@
         self.tmp = tempfile.TemporaryDirectory()
         raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
+        raw.setdefault("images", {})["photo_policy"] = "any"   # basın görseli kuralı ayrıca sınanır
         self.cfg = Config(raw=raw, root=Path(self.tmp.name), site_url="https://smarity.com.tr")
         self.app = appmod.App(self.cfg)
@@ -146,4 +147,19 @@
             "body": "\n\n".join(f"Paragraf {i} metni." for i in range(1, 9)), "published_at": iso(now_utc()),
             "image": {"source": "cover"}, "sources": [{"name": "Marka", "url": "https://brand.com/press", "kind": "official"}], **kw}
+
+
+def test_press_policy_drops_news_site_photos():
+    with _App() as (cfg, a):
+        cfg.raw["images"]["photo_policy"] = "press"
+        a.store.save_post(_post())
+        shots = [{"image": _photo("#446", seed=i), "src": f"https://cdn.newssite.com/{i}.jpg", "credit": "Haber Sitesi",
+                  "page": "https://newssite.com/a", "alt": "", "kind": "body", "graphic": False, "src_kind": "media"}
+                 for i in range(3)]
+        shots.append({"image": _photo("#644", seed=9), "src": "https://brand.com/press/a.jpg", "credit": "Marka",
+                      "page": "https://brand.com/press", "alt": "", "kind": "og", "graphic": False, "src_kind": "official"})
+        appmod.photos.gather = lambda *a_, **k: shots
+        a.backfill_photos(5)
+        p = a.store.load_post("p1")
+        assert [r["src"] for r in p.get("photos") or []] == ["https://brand.com/press/a.jpg"]
 
 
@@@SM@@@ FILE seo-keep.txt
# Google'da gösterim almış haberlerin adresleri (Search Console, 25 Eyl–22 Kas 2026).
# Bunlar kısa / tek kaynaklı olsa da dizinde kalır (site.py → zayıf sayfa ayıklama).
2027-bmw-3-series-tanitildi
2027-hyundai-tucson-ozellikleri
2027-jeep-cherokee-trailhawk-tanitildi
2027-lexus-tz-fiyati-ve-menzili-aciklandi
2027-mercedes-g-580-ev-nacs-portu-menzil
airpods-5-tamir-edilebilirlik-puani
alpine-a110-yeni-tasarimi-paris-otomobil-fuarinda
amazon-alexa-alisveris-asistani-yeni-yetenekler
amazon-fire-tv-stick-4k-tanitildi
amazon-yeni-kindle-serisi-tanitildi
amerika-gov-yapay-zeka-asistani
amp-yapay-zeka-ajani-ve-ozellikleri
android-automotive-arka-planda-youtube-destegi
android-sms-of-death-acigi
anker-solix-s2000-turkiyede
anthropic-claude-for-government-yayinda
anthropic-claude-modellerine-ahlak-kazandirmak-istiyor
anthropic-sonnet-5-5-tanitildi
anyps5-projesi-ps5-oyunlarini-pce-tasiyor
apple-akilli-ev-etkinligi-duzenleniyor
apple-akilli-ev-etkinligi-uc-yeni-urun
apple-akilli-ev-pazari
apple-akilli-ev-urunleri-13-ekim
apple-akilli-gozluk-2027-sonu
apple-bagimsiz-oyunlar-haftasi-basladi
apple-ceo-su-john-ternus-yapay-zeka
apple-ekim-ayi-urun-lansmani
apple-etkinlik-13-ekim-welcome-home
apple-homeview-ve-siri-ai-ozellikleri
apple-music-yenilenen-tasarimi-ve-logosu
apple-openai-ticari-sir-davasi
apple-smart-home-hub-tasarimi
apple-tv-4k-dortlu-homepod-destegi
apple-vision-pro-gelecegi-belirsizlesti
apple-watch-series-12-ve-ultra-4-icin-yeni-ozellikler
applein-yeni-ceosu-john-ternus-tasarim-odakli-donemi-baslatti
aselsan-deringoz-firat-nehrinde-kesif-yapti
aselsan-ogulbey-teknoloji-ussunde-ilk-uretim-basladi
aselsan-turk-telekom-yerli-telefon-cikis-tarihi
avrupa-akilli-telefon-pazarinda-apple-liderligi-devraldi
beats-360-tanitildi-moduler-tasarimli-kulaklik
bentley-torcal-tanitildi-ozellikleri-fiyati
bim-aktuel-urunler-dji-neo-drone
binance-tr-gram-ve-ceyrek-altin-kripto-islem-donemi
bmw-i3-m60-duyuruldu
bmw-ix4-gorselleri-sizdirildi
bmw-maps-with-driver-assistance-tanitildi
bmw-yapay-zeka-yonetici-azaltma
booking-com-turkiye-erisim-duzenlemesi
booking-com-yapay-zeka-seyahat-asistani-lola
bose-kablolu-kulaklik
bose-quietcomfort-ultra-auracast-guncellemesi
boston-dynamics-atlas-robotlari-fabrikada
bouncewatch-pib-fintech-germany-programina-secildi
bucked-games-yatirim-aldi
byd-atto-8-tanitildi
byd-calisan-sayisi-1-milyon-esigini-asti
byd-fang-cheng-bao-ti9-sovrumlarda
byd-kati-hal-batarya-2027
byd-luks-sedan-bae-lansmani
byd-seagull-yeni-nesli-tanitildi
byd-seagull-yenileniyor-boyutlar-ve-ozellikler
byd-seal-07-ozellikleri-aciklandi
byd-tang-ucuncu-nesli-tanitildi
byd-yeni-luks-elektrikli-sedan
call-of-duty-modern-warfare-4-detaylari
chatgpt-haritalar-ozelligi-web-surumune-eklendi
chatgpt-is-birligi-araclari-tanitildi
chatgpt-kilitli-sohbetler-ozelligi
chatgpt-pro-max-aboneligi-hazirlaniyor
chatgpt-sanal-kiyafet-deneme-ozelligi-2
chery-icaur-v27-erev-satis-fiyati
citroen-2cv-elektrikli-konsepti-tanitildi
claude-code-hatasi-binlerce-dosya-sildi
claude-erisim-sorunu-yasaniyor
claude-yeni-enzim-sistemi-kesfetti
cukur-vartolu-filmi-amazona-satildi
dacia-hipster-fiyati-ve-ozellikleri
dacia-striker-avrupada-siparise-acildi
dell-xps-16-tanitildi
dell-xps-16-yeni-nesil-ozellikleri
denza-z9-gt-avrupada-gods-eye-sistemi
detectifai-akilli-telefon-ses-guvenligi
ea-sports-fc-27-dunya-genelinde-cikti
efootball-turkiye-sunucusu-acildi
egaranti-seri-a-oncesi-yatirim-aldi
ekim-2026-elektrikli-otomobil-fiyatlari
elektrikli-arac-sarj-ucretleri-kasim-2026
elektrikli-mercedes-c-serisi-turkiye-fiyati
elevenlabs-elevenai-toplanti-ve-dikte-uygulamasi
eliseai-4-milyar-dolar-degerleme-ile-yatirim-aldi
elon-musk-grok-rakiplerinin-gerisinde
enervenue-su-bazli-batarya-uretimine-basladi
epic-games-store-yapay-zeka-ile-yenilendi
fairbuds-2-fiyati-ve-cikis-tarihi
fiat-egea-efsane-serisi-fiyati-ozellikleri
fiat-ekim-2026-fiyat-listesi
fiat-fastback-turkiye-cikis-tarihi-ve-ozellikleri
firefox-157-guncellemesi-yayinda
florida-basvurusundan-openai-icin-acil-durdurma-talebi
flourish-1-ev-robotu-tanitildi
flow-games-yatirim
flowtica-verso-tanitildi
flux-3-image-duyuruldu
football-manager-27-cikis-tarihi-aciklandi
formula-1-yayinlari-dolby-atmos
fortnite-five-nights-at-freddys-is-birligi-duyuruldu
fujifilm-instax-mini-evo-2-tanitildi
fujifilm-instax-square-2-tanitildi
galaxy-smarttag-3-tanitildi
galaxy-tab-s12-ve-smarttag-3-satis-cikti
garmin-marq-3-akilli-saat-ailesi-tanitildi
geely-galaxy-battleship-700-cikis-tarihi-ve-ozellikleri
geely-ultra-short-blade-battery-tanitildi
gemini-3-8-live-live-avatar-ozelligi
gemini-4-argon-tanitildi
gemini-android-autoda-kisisel-veri-destegi
gemini-call-for-me-ozelligi-isletmeleri-ariyor
gemini-prompt-arena-yarismasi
gemini-skills-ozelligi-tanitildi
gezgin-1-mikro-uydusu-2028de-firlatilacak
giris-seviyesi-ipad-2027de-bekleniyor
global-expansion-day-basvurulari-basladi
god-of-war-laufey-cikis-tarihi-ve-on-siparis-detaylari
gokceada-ozdemir-bayraktar-meslek-yuksekokulu-kurulacak
golden-joystick-awards-2026-adaylari-aciklandi
google-ai-edge-foresight-mac
google-assistant-yerini-gemini-aliyor
google-chrome-erken-uyari-sistemi
google-deepmind-gemini-4-carbon
google-drive-akilli-ozellikleri-dosya-icerikleri
google-fitbit-edge-tanitim-tarihi
google-fitbit-edge-ve-flo-health-ortakligi
google-gemini-gmail-gelen-kutusu-yonetimi
google-gemini-kullanicilar-adina-arama-yapabilecek
google-gemini-shop-this-ozelligi
google-gemini-ucretsiz-surum-sinirlamasi-9-ekim
google-gemini-yapay-zeka-avatarlari-sosyal-oldu
google-synthid-detector-herkesin-kullanimina-acildi
googlebook-on-siparise-acildi
gran-turismo-7-spec-iv-guncellemesi
grand-theft-auto-6-arka-plan-karakteri
grand-theft-auto-6-dosya-boyutu
gta-6-gelistirme-surecinin-detaylari
gta-6-haritasi-gta-5in-iki-kati-buyuklugunde
gta-6-karakterleri-hakkinda-yeni-detaylar
gta-6-oyunculara-sinirsiz-guc-vermeyecek
gta-6-siyaset-ve-gercek-kisilere-odaklanmayacak
gta-6-yeni-ahlak-sistemi-detaylari
gurgencler-google-reklam-cezasi
hepsiburada-veri-ihlali-bildirimi
homepod-27-2-guncellemesi-yayinlandi
homepod-mini-2-satista-cikti
honda-prelude-limited-edition-avrupaya-geliyor
honor-magic-9-pro-max-tanitildi
honor-magic9-ve-super-edition-tanitildi
honor-watch-6-pro-tanitildi
honor-watch-6-turkiye-fiyati-ve-ozellikleri
huawei-mate-90-serisi-1-ekimde-tanitiliyor
huawei-matepad-air-turkiye-fiyati-ve-ozellikleri
huawei-matepad-air-turkiyede-satisa-cikti
huawei-t3-vakfi-yapay-zeka-is-birligi
hurjet-icin-ispanya-ile-isbirligi-aciklandi
hyundai-ioniq-4-ve-7-modelleri-tanitiliyor
hyundai-ioniq-v-cinde-satisa-cikti
insta360-spatial-capture-3d-video
instagram-edits-uygulamasina-yapay-zeka-asistani-eklendi
instagram-uzun-ve-yatay-video-features
instinct-yapay-zeka-1-milyar-dolar-yatirim-aldi
iphone-18-pro-max-gta-5-performansi
iphone-18-pro-renk-solmasi-iddiasi
iphone-air-2-ozellikleri-ve-cikis-tarihi
iphone-duo-magaza-deneyim-planlari
iphone-duo-tamir-ucretleri-aciklandi
jaguar-type-01-tanitildi
jeep-renegade-geri-donuyor
jensen-huang-guvenli-olmayan-yapay-zeka-cip
kayseride-park-halindeki-togg-t10x-alev-aldi
kia-ev4-gt-tanitildi
kia-seltos-turkiyede-satisa-cikti
koc-holding-cinli-ureticilerle-ortaklik-planliyor
kompakt-elektrikli-smart-2-tanitildi
kristal-piksel-2026-odulleri-sahiplerini-buldu
kuantum-bilgisayar-uzayda-calistirildi
kucuk-g-serisi-24-ay-icinde-cikiyor
lego-playstation-seti-satisa-cikti
lexus-tz-ilk-kez-goruntulendi
loewe-leo-bluetooth-hoparlor-tanitildi
logitech-yeti-2-tanitildi
loops-ai-yatirim-aldi
mac-mini-m6-tanitildi-ozellikleri-fiyati
mac-studio-m5-ultra-incelemesi
makyajli-volkswagen-caddy-turkiye-fiyati-aciklandi
marshall-bromley-150-ozellikleri-fiyati
mercedes-benz-seramik-batarya-testleri
mercedes-benz-ve-nvidia-ortakligi-genisliyor
meta-akilli-gozluk-modelleri-ve-ozellikleri
meta-enterprise-platform-tanitildi
meta-horizon-create-ve-horizon-studio
meta-muse-akilli-gozlugue-geliyor
meta-muse-for-small-business-duyuruldu
meta-muse-uygulamasi-milyonlarca-indirmeye-ulasti
mg-hs-turkiye-yeni-versiyonlar-fiyat
mg-ismart-uzaktan-kontrol-sistemi-turkiyede
microagi-100-milyon-dolar-arr-asti
microsoft-ai-ses-modelleri-tanitildi
microsoft-copilot-uygulamasina-office-entegre-edildi
microsoft-copilot-yenilendi-tek-uygulamada-birlesti
microsoft-windows-11-copilot-ozelliklerini-kaldiriyor
minecraft-the-sift-boyutu-duyuruldu
mobge-10-milyon-dolar-degerleme-uzerinden-yatirim-aldi
modal-labs-750-milyon-dolar-yatirim
modern-warfare-4-counter-strike-modu
motorola-razr-fold-turkiyede-satisa-sunuldu
motorola-signature-27-tanitildi
nasa-teledyne-ayda-enerji-uretimi
naughty-dog-yeni-the-last-of-us-projeleri
nikon-z5iic-duyuruldu-vizorsuz-tam-kare-kamera
ning-service-turkiyeye-geliyor
nintendo-switch-2-fiziksel-oyun-uretimi-devam-edecek
nintendo-switch-2-v2-donanim-degisiklikleri-belli-oldu
nintendo-switch-2-zelda-ozel-surum
nissan-primastar-turkiyede-satisa-sunuldu
nissan-rogue-e-power-abd-satis-fiyati
nothing-headphone-1-pro-tanitildi
nothing-headphone-1-pro-tanitildi-2
nothing-os-5-0-guncellemesi-basladi
now-nudge-turkce-dil-destegi
nvidia-dlss-5-performansi-iki-katina-cikti
oneplus-16-tanitim-tarihi-ve-ozellikleri-aciklandi
opel-corsa-gse-ve-yeni-modelleri-tanitildi
opel-ekim-2026-fiyat-listesi-aciklandi
openai-abu-dhabi-is-birligi-anlasmalari
openai-codex-yeni-bulut-ortamlari-ve-guvenlik-araclari
openai-decisions-api-duyuruldu
openai-devday-2026-basladi
openai-dot-yapay-zeka-ajanlari-ve-ofis-araclari
openai-gelir-beklentileri-guncellendi
openai-gpt-6-1-sol-modelini-duyurdu
openai-model-egitimini-durdurdu
openai-o-asistani-ve-chatgpt-pro-max
openai-pro-500-paketi-duyuruldu
openai-yillik-geliri-70-milyar-dolara-yaklasiyor
paidax-1-milyon-dolar-yatirim-aldi
path-of-exile-2-cikis-tarihi-duyuruldu
patientdesk-ai-alania-2-ses-modeli
patientdesk-ai-turkce-ses-modelleri-alania-duyu
peugeot-e-208-gti-turkiye-cikis-tarihi
peugeot-e-t16-tanitildi
peugeot-hypersquare-kare-direksiyon-2027de-yollarda
philips-the-one-100-inc-ambilight-televizyon
playstation-plus-kasim-ayi-oyunlari-aciklandi
polaroid-mod-tanitildi-fiyati-ve-ozellikleri
polaroid-mod-yaratici-cekim-kadraniyla-tanitildi
polis-kilitli-iphone-erisim-yontemi
porsche-pccm-plus-eski-modeller
ps-plus-ekim-2026-oyunlari-aciklandi
ps-plus-ekim-2026-ucretsiz-oyunlari
ps5-pro-anti-stokcu-cekilis-sistemi
pubg-mobile-global-championship-istanbula-geliyor
range-rover-sport-electric-tanitildi
ray-ban-meta-akilli-gozluk-guncellemesi
renault-gordini-8-elektrikli-konsept
robomarti-istanbul-surucusuz-taksi
roborock-f25-ultra-steam-gen-2-turkiyede
roborock-qrevo-edge-3-pro-turkiyede-satisa-cikiyor
samsung-akilli-gozluk-kasim-ayi-cikis
samsung-android-17-guncellemesi-galaxy-s26
samsung-galaxy-a08-tanitildi-fiyati-ve-ozellikleri
samsung-galaxy-a08-turkiye-fiyati-aciklandi
samsung-galaxy-a18-4g-turkiyede-satisa-sunuldu
samsung-galaxy-s27-ultra-ozellikleri-sizdirildi
samsung-galaxy-tab-s12-serisi-tanitildi
seatin-gelecegi-markus-haupt-aciklamasi
sigorta-hasar-kusur-bilgileri-e-devlette
sima-ai-150-milyon-dolar-yatirim-aldi
siri-ai-turkce-dil-destegi-gelecek
skoda-octavia-hibrit-modeli-tanitildi
snapdragon-islemcili-telefonlara-pc-oyunlari-geliyor
sony-inzone-h6-air-incelemesi
sony-mdr-3r-kulaklik-nostaljik-tasarim
sony-wh-1000xm4c-duyuruldu
sosyal-medya-yas-siniri-resmi-gazete-duzenlemesi
spacex-ayni-gun-uclu-roket-firlatmasi
spacex-starship-flight-15-cift-yakalama-deneyecek
spacex-starship-yorunge-testi-hazirliklari-tamamlandi
spacex-super-intelligence-x-aboneligi-paketi
spacex-yeni-nesil-starlink-uydulari
spotify-aile-plani-qr-kod-dogrulama
spotify-coktu-mu-muzik-platformunda-kesinti
spotify-sesli-kitap-turkiye-hizmeti-aciliyor
starship-flight-15-firlatma-tarihi-belli-oldu
steam-erisim-engeli-ve-paradox-ataturk-krizi
stellantis-1-2-puretech-motor-ozru
strava-google-gemini-entegrasyonu
suno-yapay-zeka-konusma-ve-muzik-ozelligi
tcl-csot-500-nit-inkjet-oled-panel
tcl-designer-televizyon-serisi-tanitildi
tech-istanbul-on-kulucka-basvurulari
terminal-istanbul-acilis-2030-hedefleri
tesla-amasya-supercharger-acildi
tesla-avrupada-full-self-driving-adini-degistirdi
tesla-cybercab-paris-motor-show
tesla-ikinci-el-turkiye-garantili-satis-takas
tesla-model-3-v2l-guncellemesi
tesla-model-y-turkiye-fiyatlarina-zam
tesla-optimus-uretim-sorunlari
tesla-roadster-tanitimi-ertelendi
tesla-semi-yuksek-hacimli-uretime-basladi
tesla-supercharger-trabzon-istasyonu-acildi
tesla-ve-spacex-birlesme-gorusmeleri
the-witcher-3-remastered-cikis-tarihi
tiktok-genc-kullanicilar-2-saat-siniri
togg-ekim-2026-fiyat-listesi
togg-gunluk-uretim-kapasitesi
togg-ota-guncellemesi-yayinlandi
togg-t10f-ayder-renk-secenegi
togg-t10f-kaldirim-tipi-sarj-sistemi
tokyo-mahkemesinden-yapay-zeka-ses-kopyalama-karari
toyota-century-kuresel-pazara-aciliyor
toyota-yeni-nesil-hibrit-motoru-verimlilik
trump-super-intelligence-kararnamesi
turk-mobil-oyun-sektoru-2-76-milyar-dolara-ulasarak-rekor-kirdi
turkiye-mobil-internet-hizi-aciklandi
turkiyede-yapay-zekali-otonom-ciftlik-donemi
tuvturk-istasyonlari-turka-devir-gorusmeleri
uber-turkiye-yatirimini-500-milyon-dolara-cikardi
ulusal-dijital-kimlik-cuzdani-prototipi-2027de-gelistirilecek
unitree-dex5-s-robot-eli-tanitildi
uzun-sasili-volkswagen-id-buzz-cargo-tanitildi
vivo-x500-pro-max-kutu-acilisi
vivo-x500-pro-max-ve-g2-ultra-lens-tanitildi
volkswagen-elektrikli-id-golf-askiya-aldi
volkswagen-id-tiguan-id4-ve-id5in-yerini-aliyor
volkswagen-m6-on-satisa-cikti
volkswagen-turkiye-elektrikli-model
volvo-es90-turkiye-fiyati-aciklandi
volvo-es90-turkiyede-satis-sunuldu
volvo-ex60-turkiye-satis-tarihi-belli-oldu
volvo-otonom-kamyon-madende-uc-milyon-ton-tasidi
waymo-las-vegas-robotaksi-hizmeti
whatsapp-android-sohbet-onizleme-ozelligi
whatsapp-aramalarina-hesapsiz-katilim-donemi
whatsapp-misafir-arama-ozelligi
windows-11-26h2-guncellemesi-yayinlandi
windows-ekim-guncellemesi-1400-acigi-kapatti
wordpress-jetpack-gorsel-alt-alan-adi-engellendi
world-of-warcraft-forever-cikis-tarihi-duyuruldu
xbox-game-pass-ekim-2026-oyunlari
xbox-nano-controller-duyuruldu
xiaomi-18-pro-serisi-tanitildi
xiaomi-mimo-v2-6-yapay-zeka-modeli-tanitildi
xiaomi-robot-vacuum-6-turkiye-fiyati
xiaomi-smart-band-11-avrupa-satisina-basladi
xreal-aura-akilli-gozluk-fiyati-ve-cikisi
yamaha-nmax-e-tanitildi
yangwang-u9-xtreme-500-km-h-hiz-sinirini-asti
yapay-zeka-ajanlari-guvenli-sistemlere-saldirdi
yeni-apple-tv-4k-ozellikleri-ve-cikis-tarihi
yeni-bmw-3-series-tanitim-tarihi-ve-ozellikleri
yeni-bmw-f-450-gs-turkiyede-satisa-sunuldu
yeni-elektrikli-mercedes-c-serisi-tanitildi
yeni-hyundai-ioniq-3-tanitildi
yeni-hyundai-tucson-turkiye-cikis-tarihi
yeni-kia-seltos-turkiyede-satisa-cikti
yeni-nesil-hyundai-bayon-tanitildi
yeni-tesla-roadster-tanitim-etkinligi-tarihi
youtube-ask-youtube-mobil-uygulamaya-geliyor
youtube-hacklenen-kanallar-kisitlama
youtube-shorts-oneri-sistemi-guncellendi
youtube-yorumlarina-gif-ve-gorsel-destegi
zorlu-enerji-zes-sarj-agi-paylarini-devrediyor
@@@SM@@@ FILE tests/test_recovery.py
"""Google toparlanma planı: zayıf eski sayfalara noindex, basın görseli kuralı."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haberbot import site as sitemod  # noqa: E402
from haberbot.photos import press_ok  # noqa: E402
from haberbot.site import SiteBuilder, is_thin  # noqa: E402
from tests.test_home import _App, _post  # noqa: E402

SEO = {"prune_thin": True, "prune_before": "2026-11-25", "thin_words": 250}


def test_is_thin_rules():
    old = {"slug": "eski", "published_at": "2026-10-01T10:00:00+00:00",
           "sources": [{"name": "A", "url": "https://a.com/1"}]}
    assert is_thin(old, 180, SEO, set())
    assert not is_thin(old, 180, SEO, {"eski"})                                       # Google'da gösterim almış
    assert not is_thin(old, 400, SEO, set())                                          # dolu haber
    two = {**old, "sources": old["sources"] + [{"name": "B", "url": "https://b.com/1"}]}
    assert not is_thin(two, 180, SEO, set())                                          # iki ayrı yayın
    assert not is_thin({**old, "published_at": "2026-11-26T08:00:00+00:00"}, 180, SEO, set())   # yeni dönem
    assert not is_thin(old, 180, {**SEO, "prune_thin": False}, set())


def test_thin_pages_get_noindex_and_leave_sitemap(monkeypatch):
    with _App() as (cfg, a):
        cfg.raw.setdefault("seo", {}).update(SEO)
        monkeypatch.setattr(sitemod, "load_keep", lambda: {"haber-2"})
        # _post: 2 kısa paragraf, tek kaynak → zayıf; haber-2 Google'da gösterim almış, haber-3 yeni dönemde
        for i in (1, 2, 3):
            a.store.save_post(_post(i, 24 * 90 if i < 3 else 1, tags=["Apple"]))
        sb = SiteBuilder(cfg)
        sb.build()
        page = lambda slug: max((f.read_text(encoding="utf-8") for f in cfg.out_dir.rglob(f"{slug}/index.html")),  # noqa: E731
                                key=len)   # eski adreslerdeki yönlendirme sayfaları değil, haberin kendisi
        thin, kept = page("haber-1"), page("haber-2")
        assert 'content="noindex, follow"' in thin
        assert "noindex" not in kept
        sm = (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")
        assert "haber-1" not in sm and "haber-2" in sm


def test_press_photo_rule():
    hosts = ["apple.com", "togg.com.tr"]
    assert press_ok({"src_kind": "official", "src": "https://cdn.x.com/a.jpg"}, hosts)
    assert press_ok({"kind": "wiki", "src": "https://upload.wikimedia.org/a.jpg"}, hosts)
    assert press_ok({"src_kind": "media", "src": "https://www.apple.com/newsroom/images/a.jpg"}, hosts)
    assert press_ok({"src_kind": "media", "src": "https://newsroom.example.com/a.jpg"}, hosts)
    assert not press_ok({"src_kind": "media", "src": "https://www.theverge.com/a.jpg"}, hosts)
    assert not press_ok({"src_kind": "media", "src": "https://notapple.com/a.jpg"}, hosts)
    assert not press_ok({"src_kind": "media", "src": ""}, hosts)
@@@SM@@@ SHA
8b861fcf59a563566905e32e6519707175e6f4e0a2f8816dbb826e9e17142ebf config.yaml
2afefd3673b73ef655bda835f2b1da1892be7a29c029e3a2f4c39f199e693337 haberbot/app.py
a94aa52be1b64661d485c97b66f2299fc6ac3fc2599e2a33501770100e7b9907 haberbot/photos.py
511ec040e23f11f9288b971ea3980b1770705cbc297ef54bc6058c55b24044b3 haberbot/prompts.py
94a0b38b5072ba72db294bf4785d7d41e72ca3e7d0fa4915cc3a1d33c716cf34 haberbot/site.py
7a9fb7c8a7722531ededa811d1a3d97aee5539530a0d147784cda1e9fe8ef848 static/style.css
40573a88c60dea773fb4212379e4c74d91f5918dbc14e0b38d07e4472e22020b templates/about.html
2ae923f8e648e8ec460fe70ca413b13744526157c6ec49c37df2521c3d92013f templates/article.html
5f684c0a18eef6f366becad0faa1ac106ad8d82a2615724c16532fa760a88fd6 tests/test_editor.py
f0a769b2abade3902f0c2a49667e3c6925143b988a3a4c63c446eb40f2f15572 tests/test_home.py
7e8d16a4135fe2c9988d4fa478fb57ef8db3914040d74e7fb792fa38609c21a1 tests/test_photos.py
a7298d8836f1f417a003113171ae8a48c26f0c7da7282bf66f8311cea4ac3ca0 seo-keep.txt
bcc37f5ddcd2776f01975d19b7179961a429fc7bf662b62901eff183f6158a01 tests/test_recovery.py
