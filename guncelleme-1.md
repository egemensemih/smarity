SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -73,9 +73,9 @@
   min_importance: 7              # 1-10. Haber masasının aday eşiği
   min_must_read: 7               # 1-10. Yayın yönetmeninin yeni haber eşiği (7: sağlam ve yayına değer, 8: geniş kitle için önemli)
-  min_outlets: 2                 # Tek kaynaklı haber, ikinci bir yayın kuruluşu da verene kadar bekler
-                                 # (şirketin kendi resmi duyurusu ya da yönetmen puanı 9+ ise beklemez)
+  min_outlets: 0                 # 2: tek kaynaklı haber ikinci bir yayın da verene kadar bekler (Kasım 2026'da kapatıldı:
+                                 # Türkiye'ye özel haberlerin çoğunu yayından alıkoyuyordu)
   max_per_company_per_day: 0     # Aynı şirketten 24 saatte en fazla kaç haber (0 = sınır yok)
-  max_drafts_per_run: 3          # Bir taramada aynı anda yazılan taslak (fazlası kaybolmaz, bir sonraki taramada gelir)
-  max_drafts_per_day: 10         # Günlük üst sınır (Kasım 2026: az ama dolu haber; Google çekirdek güncellemesi sonrası)
+  max_drafts_per_run: 4          # Bir taramada aynı anda yazılan taslak (fazlası kaybolmaz, bir sonraki taramada gelir)
+  max_drafts_per_day: 40         # Günlük üst sınır (Webtekno / ShiftDelete / LOG benzeri akış: günde 25-40 haber)
   big_news_extra: 3              # Sınır dolsa da yayımlanan büyük haber sayısı (önem 9+, ya da herkesin bildiği bir markada 8+;
                                  # ör. Apple'ın sürpriz yeni ürünü). Diğer haberler sırada bekler.
@@ -87,5 +87,9 @@
   taste_days: 21                 # Yönetmen, son bu kadar günde reddettiğin / kaldırdığın haberlerden zevkini öğrenir
   taste_examples: 40             # ...en fazla bu kadar örnekle
-  confirmed_only: true           # Yalnızca doğrulanmış haber: söylenti, sızıntı, "iddia ediliyor" haberleri yönetmen baştan eler
+  confirmed_only: false          # true: söylenti / sızıntı hiç yayınlanmaz. false: güvenilir sızıntılar (bilinen sızdırıcılar,
+                                 # sertifika belgeleri, saygın yayınların haberleri) "iddia" olarak açıkça belirtilerek yayınlanır
+  allow_leaks: true              # tam otonomda "iddia" işaretli taslak düşürülmez (güven "düşük" değilse); sitede "İddia" etiketi çıkar
+  tr_press_boost: true           # Webtekno, ShiftDelete, LOG, DonanımHaber, Webrazzi, Chip'ten en az ikisinin verdiği haber
+                                 # eşiğin bir altındaysa da yayınlanır (Türk okurun gündemindeki konu)
   fetch_full_text: true          # Haberin tam metnini kaynağından okuyup daha doğru özet çıkar
 
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -105,4 +105,20 @@
 # bakım listesiyle (maintenance.fix_posts) düzeltilebilen alanlar
 FIXABLE = {"title", "short_title", "seo_title", "summary", "meta_description", "category", "carousel_points"}
+
+
+# Türk teknoloji basınının ana siteleri: en az ikisinin verdiği konu Türk okurun gündemindedir
+TR_PRESS = {"Webtekno", "ShiftDelete.Net", "LOG", "DonanımHaber", "Webrazzi", "Chip Online", "Technopat",
+            "Donanım Arşivi", "Teknoseyir", "Egirisim", "Swipeline"}
+
+
+def photos_by_quality(got: list[dict]) -> list[dict]:
+    """Fotoğraf editörünün sırasını koruyarak kaliteye göre diz: önce büyük ve net gerçek fotoğraflar (kapak bunlardan
+    olur), sonra küçük ama net olanlar, sonra bulanıklar, en son ekran görüntüleri. Belirgin biçimde bulanık görseller
+    (videodan alınmış kare, büyütülmüş küçük görsel) başka seçenek varsa hiç kullanılmaz."""
+    rank = lambda g: photos.hero_rank({**g, "w": g["image"].width if g.get("image") is not None else g.get("w")})  # noqa: E731
+    clear = [g for g in got if g.get("graphic") or g.get("sharp") is None or g["sharp"] >= photos.SHARP_BAD]
+    if clear:
+        got = clear
+    return sorted(got, key=rank)
 
 
@@ -530,4 +546,5 @@
         cap = int(self.cfg.get("editorial", "max_per_company_per_day", 0) or 0)   # 0 = sınır yok
         min_out = int(self.cfg.get("editorial", "min_outlets", 0) or 0)            # tek kaynaklı haber bekler
+        tr_boost = bool(self.cfg.get("editorial", "tr_press_boost", False))
         day_keys: dict[str, int] = {}
         for c in covered:
@@ -554,4 +571,13 @@
                                        (f": {x['reason']}" if x.get("reason") else ""), 120)
                     retiring.add(tgt)
+            its = queue[i].get("items") or []
+            outlets = {it.get("credit") for it in its if it.get("credit")}
+            # Türk teknoloji basınının en az iki büyük sitesi vermişse konu okurun gündeminde: eşiğin bir altı da yayınlanır
+            if (tr_boost and x["action"] in ("skip", "publish") and not x.get("target") and mr == min_score - 1
+                    and not (s.get("duplicate_of") or "") and len(outlets & TR_PRESS) >= 2):
+                mr = x["must_read"] = min_score
+                s["importance"] = max(int(s.get("importance") or 0), min_score)
+                x["action"], x["reason"] = "publish", clip("Türk teknoloji basınında geniş yer aldı" +
+                                                           (f"; {x['reason']}" if x.get("reason") else ""), 120)
             if x["action"] == "update":
                 if x["target"] in pending:
@@ -580,6 +606,4 @@
                     round_targets.add(dup)
                 continue
-            its = queue[i].get("items") or []
-            outlets = {it.get("credit") for it in its if it.get("credit")}
             official = any(it.get("kind") == "official" for it in its)
             if mr < min_score:
@@ -3102,9 +3126,9 @@
         if not since:
             return
-        done = self.state.setdefault("photo_redo", [])
+        done = self.state.setdefault("photo_redo2", [])      # 2: bulanık kapaklar da (netlik ölçümü eklendi)
         todo = [p for p in self.store.posts()
                 if (p.get("published_at") or "") >= since and p["id"] not in done and not p.get("photos_removed")
                 and (p.get("image") or {}).get("source") != "ai"
-                and all(r.get("credit") == "Wikipedia" for r in p.get("photos") or [])][:per_run]
+                and (all(r.get("credit") == "Wikipedia" for r in p.get("photos") or []) or self._cover_blurry(p))][:per_run]
         for p in todo:
             done.append(p["id"])
@@ -3125,4 +3149,16 @@
             self.store.save_post(p)
         del done[:-400]
+
+    def _cover_blurry(self, p: dict) -> bool:
+        """Sitedeki kapak fotoğrafı bulanık ya da küçük mü (kayıtlı dosyadan ölçülür)."""
+        f = (p.get("image") or {}).get("photo")
+        if not f or not (self.cfg.images_dir / f).exists():
+            return False
+        try:
+            from PIL import Image
+            with Image.open(self.cfg.images_dir / f) as im:
+                return im.width < photos.HERO_W or photos.sharpness(im) < photos.SHARP_MIN
+        except Exception:  # noqa: BLE001
+            return False
 
     def fill_missing_photos(self, per_run: int = 8) -> None:
@@ -3179,5 +3215,5 @@
                 w = None
             vetted = self._vet_photos(d, [w]) if w else []
-        got = vetted
+        got = photos_by_quality(vetted)
         if not got:
             return False
@@ -3191,5 +3227,6 @@
         for i, p in enumerate(got):
             rec = {"src": p["src"], "credit": p["credit"], "page": p["page"], "alt": p["alt"], "kind": p.get("kind", ""),
-                   "graphic": bool(p.get("graphic")), "cover_ok": bool(p.get("cover_ok", not p.get("graphic")))}
+                   "graphic": bool(p.get("graphic")), "cover_ok": bool(p.get("cover_ok", not p.get("graphic"))),
+                   "sharp": p.get("sharp"), "src_w": p["image"].width}
             if len([r for r in recs if r.get("file")]) < keep:
                 name = f"{d['id']}-g{len([r for r in recs if r.get('file')])}.webp"
--- a/haberbot/photos.py
+++ b/haberbot/photos.py
@@ -19,5 +19,5 @@
 
 import requests
-from PIL import Image, ImageChops, ImageOps, ImageStat
+from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat
 
 # Küçük dosyada dev çözünürlük ("sıkıştırma bombası") belleği doldurmasın: 40 MP üstü uyarı, 80 MP üstü reddedilir
@@ -29,4 +29,7 @@
 MAX_BYTES = 15_000_000
 MIN_W, MIN_H = 600, 320
+HERO_W = 1000          # manşet / kapak için en az genişlik (daha küçükler büyük ekranda yumuşak görünür)
+SHARP_MIN = 19.5       # netlik eşiği: altı bulanık (videodan alınmış kare, büyütülmüş küçük görsel)
+SHARP_BAD = 12.0       # bunun altı belirgin biçimde bulanık: başka seçenek varsa hiç kullanılmaz
 BAD_URL = re.compile(
     r"(logo|icon|favicon|sprite|avatar|gravatar|/authors?/|profile[-_]?(pic|photo|image)|placeholder|blank\.|"
@@ -250,4 +253,27 @@
 
 
+def sharpness(im: Image.Image) -> float:
+    """Netlik: 800 px genişlikte Laplace kenar enerjisinin en keskin 5 bölgedeki ortalaması (8×6 ızgara).
+    Arka planı bulanık ama konusu net fotoğraflar yüksek, videodan alınmış / büyütülmüş görseller düşük çıkar."""
+    g = im.convert("L")
+    if g.width > 800:
+        g = g.resize((800, max(6, round(g.height * 800 / g.width))), Image.LANCZOS)
+    e = g.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], 1, 128))
+    tw, th = max(1, e.width // 8), max(1, e.height // 6)
+    tiles = sorted((ImageStat.Stat(e.crop((i * tw, j * th, (i + 1) * tw, (j + 1) * th))).stddev[0]
+                    for i in range(8) for j in range(6)), reverse=True)
+    return round(sum(tiles[:5]) / 5, 1)
+
+
+def hero_rank(rec: dict) -> int:
+    """Kapak / manşet sırası: 0 büyük ve net gerçek fotoğraf · 1 net ama küçük · 2 bulanık · 3 ekran görüntüsü / grafik."""
+    if rec.get("graphic"):
+        return 3
+    sharp = rec.get("sharp")
+    if sharp is not None and sharp < SHARP_MIN:
+        return 2
+    return 0 if (rec.get("w") or 0) >= HERO_W and rec.get("cover_ok", True) else 1
+
+
 def classify(im: Image.Image) -> dict:
     """Fotoğrafın türü.
@@ -260,5 +286,5 @@
     flat, edge = _stats(im)
     graphic = flat >= 0.62 and edge >= 0.025
-    return {"graphic": graphic, "cover_ok": not graphic and flat < 0.7}
+    return {"graphic": graphic, "cover_ok": not graphic and flat < 0.7, "sharp": sharpness(im), "w": im.width}
 
 
--- a/haberbot/policy.py
+++ b/haberbot/policy.py
@@ -105,6 +105,10 @@
 def hard_reason(cfg: Config, draft: dict) -> str | None:
     """Otomatik yayınlanamayacak haber: şüpheli (uyarı işareti), listedeki marka, güveni düşük ya da önemsiz."""
-    if draft.get("flags"):
-        return "Şüpheli içerik: " + ", ".join(FLAG_LABELS.get(f, f) for f in draft["flags"])
+    flags = list(draft.get("flags") or [])
+    # güvenilir sızıntı / iddia haberi: açıkça "iddia" olarak yazıldıysa ve güven düşük değilse yayınlanabilir
+    if flags == ["iddia"] and cfg.get("editorial", "allow_leaks", False) and draft.get("confidence") != "dusuk":
+        flags = []
+    if flags:
+        return "Şüpheli içerik: " + ", ".join(FLAG_LABELS.get(f, f) for f in flags)
     brand = never_auto_brand(cfg, draft)
     if brand:
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -64,8 +64,10 @@
 Turkish startup ecosystem and the biggest names in gaming. We follow the global giants and premium brands closely (Apple,
 Samsung, Google, Microsoft, Sony, Meta, Amazon, NVIDIA, OpenAI, Anthropic, Tesla, SpaceX, BYD, Xiaomi and Huawei flagships,
-Nintendo, Canon, Nikon, Fujifilm, Leica, DJI, Bose, Sonos, Dyson, LG, the big car makers sold in Türkiye, TOGG…). We have a
-premium, quality feel and we are highly selective (quality, not quantity — there is no quota): only what many Turkish
-readers would actually click and talk about. We
-never publish the same development twice. You receive a batch of NEW ITEMS fetched from RSS feeds and a list of RECENT
+Nintendo, Canon, Nikon, Fujifilm, Leica, DJI, Bose, Sonos, Dyson, LG, the big car makers sold in Türkiye, TOGG…). Our
+benchmark is the daily flow of Türkiye's leading tech news sites — Webtekno, ShiftDelete.Net, LOG, DonanımHaber and
+Webrazzi — and of their international counterparts (The Verge, Engadget, 9to5Mac, Android Authority, GSMArena, IGN…): a
+lively flow of roughly 25–40 stories a day about phones and gadgets, apps and social media, games, cars, AI, Türkiye's tech
+agenda and curious science, written accurately with sources. A story that several of those Turkish sites would run is
+worth running. We never publish the same development twice. You receive a batch of NEW ITEMS fetched from RSS feeds and a list of RECENT
 STORIES (published, pending, queued, and recently rejected or expired ones).
 
@@ -88,5 +90,6 @@
    teaser, leak, rumor or "what to expect" story about it is in RECENT STORIES.
 4. importance (integer 1–10). THE TEST: would MANY ordinary Turkish readers who like technology want to click this today
-   and tell a friend about it? Not "would a specialist find it interesting" — most items fail this test. Be strict.
+   and tell a friend about it? Not "would a specialist find it interesting". Ask: would Webtekno, ShiftDelete.Net or LOG
+   run it today?
    9–10 the day's defining stories: frontier AI model releases or major ChatGPT/Gemini/Claude capability jumps; flagship
         launches (iPhone, Galaxy S/Z, Pixel, new PlayStation/Xbox/Nintendo hardware); landmark regulation or court rulings
@@ -104,7 +107,21 @@
         list), new taxes, fees and rules that hit users' wallets (IMEI registration fee, ÖTV, e-Devlet procedures),
         price changes of popular services in Türkiye (Netflix, Spotify, YouTube Premium, PlayStation Plus, operators)
-   7    noteworthy: notable launches from well-known mid-tier brands sold in Türkiye; credible and detailed leaks about a
-        hugely anticipated flagship (Mark Gurman, certification filings, official teasers); a smaller Turkish startup
-        round with a clear, interesting idea
+   7    a typical front-page story on Webtekno / ShiftDelete.Net / LOG:
+        - new features and changes in apps and services many Turks use (WhatsApp, Instagram, YouTube, X, TikTok, Telegram,
+          Spotify, Netflix, Google apps, ChatGPT/Gemini), iOS / Android / One UI / HyperOS / Windows updates and features
+        - launches, prices and software updates of phones, tablets, laptops, watches and earbuds from brands sold in
+          Türkiye (Apple, Samsung, Xiaomi, Huawei, Honor, OPPO, vivo, OnePlus, realme, Nothing, Google, Casper…)
+        - credible leaks, renders, certifications and reports about upcoming popular products and events (Galaxy S/Z,
+          iPhone, Pixel, consoles, big games) from well-known leakers or reputable outlets — written as claims
+        - games most people know: release dates and prices, free games (Epic, PlayStation Plus, Game Pass), big updates,
+          records, mods and controversies around very popular titles (GTA 6…), console problems and prices
+        - cars: launches of new models from well-known makers (also global debuts of interesting cars and EVs from BYD,
+          Chery, Hyundai, VW, Porsche, Tesla…), new Türkiye launches and prices, new charging and battery tech, rules
+        - Türkiye's tech agenda: Rekabet Kurumu / BTK / KVKK decisions and investigations, operators, Turkish tech
+          companies and their licences (e.g. a fintech's SPK licence), phones made in Türkiye, TÜİK / BTK data
+        - security and privacy news that affects ordinary users (malicious apps or extensions, breaches of known services)
+        - widely curious science and space news (a black hole discovery, a battery breakthrough), market changes people
+          feel (RAM/SSD and phone prices, market shares of phone brands)
+        - a smaller Turkish startup round with a clear, interesting idea
    ≤6   everything else, in particular:
         - startups and funding OUTSIDE Türkiye: rounds, valuations and acquisitions of foreign startups are ≤5, unless the
@@ -125,8 +142,10 @@
         - niche gadgets from little-known brands, very cheap or entry-level products, minor accessories
         - research papers, lab and university research, AI safety studies, robotics demos without a product
-        - vague rumors and unsourced leaks, teasers without details, unboxings, hands-ons, reviews, benchmarks
-        - executive opinions and interviews, recalls, awards, events, stock and market moves, deals and discounts, guides
+        - vague rumors from unknown accounts and unsourced leaks, teasers without details, unboxings, hands-ons, reviews,
+          benchmarks
+        - executive opinions and interviews, recalls, awards, events, stock moves, deals and discounts, buying guides and
+          "best X" lists, store campaigns and sponsored brand events, defence and weapons news
    Several stories about the same company on the same day are fine when each is a distinct, newsworthy development.
-   Be strict and honest; do not inflate scores. Most items should score ≤6.
+   Be honest; do not inflate scores. Roughly a third of the items in a typical batch are 7 or more.
 5. category: one of {CATEGORY_KEYS}. Guide: {CATEGORY_HELP}.
    Stories about Turkey go to their topical category (a Turkish game studio's funding round → girisimcilik or gaming).
@@ -197,7 +216,8 @@
 TURKISH AUDIENCE: ordinary people in Türkiye who like technology, not industry insiders. We cover AI, consumer tech (phones,
 computers, cameras, audio, TVs, smart home, wearables), cars/EVs, innovation, the Turkish startup ecosystem and the biggest
-names in gaming. We are highly selective — we publish only what many Turkish readers would click and talk about — with a
-premium, quality feel: no very cheap or entry-level products, never two stories about the same thing. Several stories about the
-same company are fine when each is a distinct, newsworthy development (e.g. Apple's new iPhone and new Apple Watch).
+names in gaming. Our benchmark is the daily flow of Webtekno, ShiftDelete.Net, LOG, DonanımHaber and Webrazzi and of their
+international counterparts: about 25–40 stories a day that Turkish tech readers click and share — never two stories about
+the same thing. Several stories about the same company are fine when each is a distinct, newsworthy development (e.g.
+Apple's new iPhone and new Apple Watch). Ask for every candidate: would Webtekno, ShiftDelete.Net or LOG run it today?
 
 You receive COVERED stories (what we already published, what is waiting for approval, and what the editor rejected) and
@@ -218,10 +238,15 @@
 Turkish startup ecosystem's notable rounds, exits and founders; major corporate moves of household-name tech companies —
 a merger, a rename, a new CEO, big layoffs at Apple, Google, Meta, Microsoft, OpenAI, xAI, Tesla…); 7 solid and worth
-publishing (a notable launch or refresh from a well-known brand sold in Türkiye — a new Kindle, AirPods, Galaxy Watch,
-mid-tier phones from big brands —; a new feature in an app or service many Turks use daily — WhatsApp, Instagram,
-YouTube, Netflix, Spotify, Google Maps, iOS, Android —; credible, detailed reports about upcoming launches or events of
-household brands — Mark Gurman, Bloomberg, certification filings, official teasers, e.g. the date of Apple's next event —;
-a flagship's Türkiye price; Turkish tech data and reports such as TÜİK or BTK figures; a smaller Turkish startup round
-with a clear, interesting idea); ≤6 routine — in particular: foreign startups' funding rounds and
+publishing — a typical Webtekno / ShiftDelete.Net / LOG front-page story: a launch, price or software update of a phone,
+tablet, laptop, watch or earbuds from a brand sold in Türkiye (also Xiaomi, Huawei, Honor, OPPO, vivo, OnePlus, Nothing);
+a new feature in an app or service many Turks use (WhatsApp, Instagram, YouTube, X, TikTok, Netflix, Spotify, Google
+apps, ChatGPT, iOS, Android, One UI, Windows); credible leaks, renders, certifications and reports about upcoming popular
+products and events (well-known leakers, Mark Gurman, Bloomberg, filings, official teasers) — published as claims; news
+about very popular games (release dates, prices, free games on Epic / PS Plus / Game Pass, records, big mods and
+controversies) and console problems or prices; a new car or EV from a well-known maker (also its global debut), new
+charging or battery tech; Türkiye's tech agenda (Rekabet Kurumu or BTK decisions and investigations, operators, licences
+of Turkish tech companies, phones made in Türkiye, TÜİK or BTK figures); security and privacy news that affects ordinary
+users; widely curious science and space news; price and market changes people feel (RAM, SSD, phones); a smaller
+Turkish startup round with a clear, interesting idea; ≤6 routine — in particular: foreign startups' funding rounds and
 acquisitions (unless a household name and a huge deal), games outside the biggest franchises (GTA, Call of Duty, EA Sports
 FC, Minecraft, Fortnite, Pokémon, Mario, Zelda, The Witcher, Elden Ring, Counter-Strike, Valorant, LoL…) and console
@@ -229,6 +254,7 @@
 or tax matters, trucks and fleet orders, trims, concepts), local news from other countries, B2B/enterprise (data centres,
 supercomputers, chip supply, factories, R&D centres, partnerships), niche gadgets from little-known brands, research
-papers and AI safety studies, thin rumors and early leaks from unknown sources (accessory or case leaks, "might" stories),
-reviews, opinions and minor updates.
+papers and AI safety studies, thin rumors from unknown accounts (accessory or case leaks, vague "might" stories), reviews,
+opinions, buying guides and "best X" lists, store campaigns and sponsored brand events, defence and weapons news, minor
+updates.
 Rules:
 - There is NO daily quota: judge every candidate only on its own merits, never by how many stories we already have
@@ -325,4 +351,5 @@
 - Use only facts stated in the sources. Never add numbers, dates, names, quotes, capabilities, prices or claims that are not in the sources. If something is unclear, leave it out.
 - Attribute claims: "OpenAI'ın duyurusuna göre…", "TechCrunch'ın aktardığına göre…". Claims from secondary reports must always be attributed.
+- Leaks and reports about products or plans that are not officially announced: make it clear in the title (e.g. "…sızdı", "…ortaya çıktı", "…olabilir", "…iddiası") and in the lead who claims it, never state it as fact, and set the flag "iddia".
 - If sources conflict, say so briefly and attribute each version.
 
@@ -354,5 +381,5 @@
 - title: the H1. ≤90 characters, informative and specific (who did what), starts with or contains the focus_keyword. Sentence case (only first word and proper nouns capitalized). No trailing period, no clickbait.
 - summary: 1–2 plain sentences, ≤180 characters, the core news in everyday language (shown under the headline and on Instagram).
-- body: Markdown, 320–550 words: the reader should not need to open the sources to understand the news. Structure: a 2–3 sentence lead paragraph that answers who/what/when and contains the focus_keyword; then 3–4 sections, each starting with a "## " subheading (short, informative, natural search-style phrase such as "## iPhone 18 Pro neler sunuyor?", "## Önceki modelden farkı ne?", "## Türkiye'de fiyat ve satış tarihi" or "## Girişim ne yapıyor?"), each followed by 1–3 short paragraphs. Cover, when the sources allow: (a) what exactly is new, with the concrete details from the sources (features, specs, availability, numbers); (b) context: how it differs from the previous model, the rivals or the company's earlier moves, using only the sources and the RELATED EARLIER COVERAGE list (never your own memory); (c) Türkiye: the Türkiye price, sale date, availability or rules if the sources give them; for products or services people in Türkiye could buy or use, if the sources say nothing about Türkiye, write one honest sentence that it has not been announced yet. Use a bullet list, or a short Markdown table, for 3+ concrete specs, prices or dates from the sources. Bold at most 2 key terms. The LAST paragraph (not under a new heading) must start with "**Neden önemli?** " followed by 1–2 grounded sentences (no speculation beyond what sources support). Do not include a sources list or links; the site adds them. Length must come from facts, never from padding, repetition or filler: if the sources are genuinely thin, write a shorter article (but at least a lead and 2 sections) rather than inventing anything.
+- body: Markdown, 260–480 words: the reader should not need to open the sources to understand the news. Structure: a 2–3 sentence lead paragraph that answers who/what/when and contains the focus_keyword; then 2–4 sections, each starting with a "## " subheading (short, informative, natural search-style phrase such as "## iPhone 18 Pro neler sunuyor?", "## Önceki modelden farkı ne?", "## Türkiye'de fiyat ve satış tarihi" or "## Girişim ne yapıyor?"), each followed by 1–3 short paragraphs. Cover, when the sources allow: (a) what exactly is new, with the concrete details from the sources (features, specs, availability, numbers); (b) context: how it differs from the previous model, the rivals or the company's earlier moves, using only the sources and the RELATED EARLIER COVERAGE list (never your own memory); (c) Türkiye: the Türkiye price, sale date, availability or rules if the sources give them; for products or services people in Türkiye could buy or use, if the sources say nothing about Türkiye, write one honest sentence that it has not been announced yet. Use a bullet list, or a short Markdown table, for 3+ concrete specs, prices or dates from the sources. Bold at most 2 key terms. The LAST paragraph (not under a new heading) must start with "**Neden önemli?** " followed by 1–2 grounded sentences (no speculation beyond what sources support). Do not include a sources list or links; the site adds them. Length must come from facts, never from padding, repetition or filler: if the sources are genuinely thin, write a shorter article (but at least a lead and 2 sections) rather than inventing anything.
 - category: one of the allowed keys. If the main subject is an AI model, assistant, feature or AI company (ChatGPT, Gemini, Copilot, Claude…), always "super-zeka", even inside a Google/Microsoft/Apple product; a startup's funding round → "girisimcilik"; games and gaming platforms → "gaming"; cars, EVs, car makers, charging and robotaxis → "otomotiv".
 - tags: 3–6 tags that people search for: companies, products, models, games, car models, technologies, places (e.g. "Apple", "iPhone 18", "TOGG", "elektrikli otomobil", "GTA 6", "OpenAI"). Use the official spelling consistently. If the story is mainly about Turkey or a Turkish company, include the tag "Türkiye". Never use generic words like "teknoloji", "yapay zeka", "oyun", "otomobil", "girişim", "haber", and never use the names of news outlets (TechCrunch, The Verge, Webrazzi…).
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -20,5 +20,5 @@
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "22"
+ASSET_V = "23"
 FOREIGN_PRICE = re.compile(r"(?=.*fiyat)(?=.*(\$|€|£|¥|dolar|euro|avro|sterlin|yuan|yen\b))", re.I)
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
--- a/static/style.css
+++ b/static/style.css
@@ -346,5 +346,10 @@
   opacity: .32; background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M15.6 7.2A4.8 4.8 0 1 0 10.8 12a4.8 4.8 0 1 1-4.8 4.8' fill='none' stroke='%23fff' stroke-width='3.6' stroke-linecap='round'/%3E%3Ccircle cx='19' cy='3.2' r='1.9' fill='%23fff'/%3E%3C/svg%3E") center / contain no-repeat; }
 /* ekran görüntüsü / grafik ana görsel olunca kırpılmaz */
-img.is-fit { object-fit: contain !important; background: #F5F5F7; }
+img.is-fit { object-fit: contain !important; background: transparent !important; position: relative; z-index: 1; }
+/* sığdırılan görselin (ekran görüntüsü, koyu ekran fotoğrafı) arkasında kendi bulanık hâli: boş kenar kalmaz */
+.fit-bg { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; transform: scale(1.2);
+  filter: blur(28px) saturate(1.1) brightness(.9); pointer-events: none; }
+.card .ph, .next-img, .row-img { position: relative; }
+.slide-media img.is-fit { position: absolute; }
 .slide-media .ph-art, .art-media .ph-art { position: absolute; inset: 0; height: 100%; aspect-ratio: auto; }
 .card .ph-art { transition: transform .8s var(--ease); }
@@ -637,2 +642,4 @@
 .guide-list .muted { font-size: 14px; }
 @media (min-width: 700px) { .art-body table, .prose table { display: table; } }
+.meta-top .claim { font-size: 12px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; padding: 3px 8px;
+  border-radius: 999px; background: #FFF4D6; color: #8A5A00; }
--- a/templates/_macros.html
+++ b/templates/_macros.html
@@ -4,4 +4,5 @@
 <span class="ph-art {{ cls }}" aria-hidden="true" style="{{ p.disp.style }}; view-transition-name: v{{ p.id }}"></span>
 {% else %}
+{% if p.disp.fit %}<img class="fit-bg" src="{{ p.img }}" alt="" aria-hidden="true" loading="lazy" decoding="async">{% endif %}
 <img src="{{ p.img }}" alt="{{ p.img_alt }}" width="{{ p.disp.w }}" height="{{ p.disp.h }}"{% if not eager %} loading="lazy"{% endif %}{% if priority %} fetchpriority="high"{% endif %} decoding="async" class="{{ cls }}{{ ' is-fit' if p.disp.fit }}" style="object-position: {{ p.disp.focus }}; view-transition-name: v{{ p.id }}">
 {% endif %}
@@ -51,4 +52,5 @@
         <span class="chip">{{ p.cat_label }}</span>
         {% if p.update_list %}<span class="chip upd-chip">Güncellendi</span>{% endif %}
+        {% if 'iddia' in (p.flags or []) %}<span class="chip upd-chip">İddia</span>{% endif %}
       </span>
       <h2>{{ p.title_disp }}</h2>
--- a/templates/article.html
+++ b/templates/article.html
@@ -52,4 +52,5 @@
       <time datetime="{{ post.iso }}">{{ post.date_str }}</time>
       <span class="muted">{{ post.minutes }} dk okuma</span>
+      {% if 'iddia' in (post.flags or []) %}<span class="claim" title="Resmî olarak doğrulanmamış; kaynağına atfedilen bilgi">İddia</span>{% endif %}
     </div>
     <h1>{{ post.title_disp }}</h1>
--- a/tests/test_editor.py
+++ b/tests/test_editor.py
@@ -264,2 +264,22 @@
             fn()
             print("ok", name)
+
+
+def test_turkish_press_boost_and_credible_leaks():
+    from haberbot import policy
+    with _App() as (cfg, a):
+        cfg.raw.setdefault("editorial", {}).update({"tr_press_boost": True, "allow_leaks": True})
+        q = _q("Opel Combo Türkiye'de satışa sunuldu", 7, ["Opel"])
+        q["items"] = [{**q["items"][0], "credit": "LOG"}, {**q["items"][0], "url": "https://sdn/1", "credit": "ShiftDelete.Net"}]
+        lone = _q("Yerel bir duyuru", 7, ["Foo"])
+        dec = {0: {"action": "skip", "target": "", "must_read": 6, "reason": "rutin"},
+               1: {"action": "skip", "target": "", "must_read": 6, "reason": "rutin"}}
+        out = a._guard([q, lone], dec, slots=4, min_score=7, covered=a._covered(48))
+        assert out[0]["action"] == "publish" and "Türk teknoloji basını" in out[0]["reason"]
+        assert out[1]["action"] == "skip"                                  # tek ve yabancı kaynak: yükseltilmez
+        leak = {"flags": ["iddia"], "confidence": "orta", "importance": 8}
+        assert policy.hard_reason(cfg, leak) is None                       # güvenilir sızıntı yayınlanabilir
+        assert policy.hard_reason(cfg, {**leak, "confidence": "dusuk"})    # güveni düşük: yayınlanmaz
+        assert policy.hard_reason(cfg, {**leak, "flags": ["iddia", "hassas"]})
+        cfg.raw["editorial"]["allow_leaks"] = False
+        assert policy.hard_reason(cfg, leak)
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -55,4 +55,5 @@
         raw.setdefault("autonomy", {})["mode"] = "kural"     # testler canlı moddan bağımsız (tam otonom ayrıca sınanır)
         raw.setdefault("editorial", {})["min_outlets"] = 0      # tek kaynak kuralı ve zayıf sayfa ayıklaması
+        raw["editorial"].update({"allow_leaks": False, "tr_press_boost": False})   # ayrıca sınanır (test_editor)
         raw.setdefault("seo", {})["prune_thin"] = False         # test_recovery / test_editor'da ayrıca sınanır
         self.cfg = Config(raw=raw, root=Path(self.tmp.name), site_url="https://smarity.com.tr", mock=True,
--- a/tests/test_photos.py
+++ b/tests/test_photos.py
@@ -454,3 +454,21 @@
         assert not p2.get("photos") and p2["image"]["source"] == "cover"                     # bina görseli kalktı
         a.redo_recent_photos()                                                               # bir kez çalışır
-        assert sorted(a.state["photo_redo"]) == ["p1", "p2"]
+        assert sorted(a.state["photo_redo2"]) == ["p1", "p2"]
+
+
+def test_sharp_large_photos_lead_and_blurry_ones_drop():
+    from PIL import ImageFilter
+    from haberbot.app import photos_by_quality
+    from haberbot.photos import SHARP_BAD, SHARP_MIN, classify, sharpness
+    crisp = _photo("#446", (1600, 900), seed=3)
+    for i in range(0, 1600, 16):                       # ince ayrıntı (yazı, doku) olan net bir fotoğraf
+        ImageDraw.Draw(crisp).line([(i, 0), (i + 200, 900)], fill=(255, 255, 255), width=1)
+    blurry = crisp.resize((320, 180)).resize((1600, 900)).filter(ImageFilter.GaussianBlur(4))   # büyütülmüş video karesi
+    small = crisp.resize((720, 405))
+    assert sharpness(crisp) >= SHARP_MIN > sharpness(blurry)
+    rec = lambda im, name: {"image": im, "src": name, **classify(im)}  # noqa: E731
+    got = photos_by_quality([rec(blurry, "bulanik"), rec(small, "kucuk"), rec(crisp, "net")])
+    assert [g["src"] for g in got][:2] == ["net", "kucuk"]
+    if sharpness(blurry) < SHARP_BAD:
+        assert "bulanik" not in [g["src"] for g in got]                # başka seçenek varken bulanık hiç kullanılmaz
+    assert [g["src"] for g in photos_by_quality([rec(blurry, "bulanik")])] == ["bulanik"]   # tek seçenekse kalır
@@@SM@@@ SHA
f2df531e99fc039cbc799507b8f9b47fd012a781cdb8c418b0c94025c4feaab1 config.yaml
9d4fca24a5cb39675d675324efba09c6124dc7924a47ad742d012866bf61a5bf haberbot/app.py
5d88be71401c5e741b4f95f9fcdd656733ac7c2f9a2864338ecd42e4341a59ff haberbot/photos.py
123d8fcb03904d218463c4688d44d7567b81aca1faa1b68cead2d8a71cd79397 haberbot/policy.py
1b57e1474030988fc74488f27d3845178fcf76d67fb085e31a7229cde7a8b734 haberbot/prompts.py
0fa67b536e95dad8623a050ea878fea6226e2ec963a0dfa292683dec390a455c haberbot/site.py
cd77cecdc58e467525fdbf1eff50be251150e70a1e54356cffc898d52dce74c7 static/style.css
f00fbbf835ee4df929395f8b98d41b6b59e9680b570a1db2cf82b55a93339149 templates/_macros.html
4c8b8fc6a28f332029f39f26c9638ec5978d7743d60d22aa51b5bee91f9c3c31 templates/article.html
ed51037bc5ab32d4184f650d4f1cc392e11e2c4d0b4c5e4faf8477b0a067dbec tests/test_editor.py
7b2b78191391b5406321b17261741e7bdf32fa9b34d410bc63d56c6a2a52c46b tests/test_home.py
8c7c6cdfffa848c9c518d948f928f412225b92dc7c605f66526cee31e26cb124 tests/test_photos.py
