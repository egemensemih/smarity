SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -47,11 +47,13 @@
   # Seçki iki aşamalı: haber masası kaynakları ayıklar ve aynı olayı tek habere toplar (min_importance), ardından
   # yayın yönetmeni o güne kadar yayınlananları görerek karar verir: yeni haber / mevcut haberi güncelle / geç / beklet.
-  # Ölçüt: "Bu alanı yakından takip eden biri bunu bugünün kaçırılmaması gereken gelişmelerinden sayar mı?"
+  # Ölçüt: "Bu alanı yakından takip eden biri bunu bugün görmek ister mi?" Dünya devleri ve premium markalar yakından
+  # izlenir; çok ucuz / giriş seviyesi ürünler, söylentiler, kutu açılışları vb. elenir.
   min_importance: 7              # 1-10. Haber masasının aday eşiği
-  min_must_read: 8               # 1-10. Yayın yönetmeninin yeni haber eşiği (seçici: 8)
-  max_per_company_per_day: 1     # Aynı şirketten 24 saatte en fazla kaç haber (günün en büyük haberleri, 9+, hariç)
-  max_drafts_per_run: 2          # Bir taramada en fazla kaç yeni haber taslağı yazılsın (haberler tek tek, düzenli gelsin)
-  max_drafts_per_day: 12         # Günlük üst sınır; gün boyuna yayılır (sabah hepsi birden tükenmez)
-  burst: 2                       # Günün başında sınırın önüne geçebilecek taslak sayısı
+  min_must_read: 7               # 1-10. Yayın yönetmeninin yeni haber eşiği (daha seçici: 8)
+  max_per_company_per_day: 0     # Aynı şirketten 24 saatte en fazla kaç haber (0 = sınır yok)
+  max_drafts_per_run: 3          # Bir taramada en fazla kaç yeni haber taslağı yazılsın (haberler tek tek, düzenli gelsin)
+  max_drafts_per_day: 0          # Günlük üst sınır (0 = sınır yok)
+  burst: 2                       # Günlük sınır varsa: günün başında sınırın önüne geçebilecek taslak sayısı
+  triage_batch: 100              # Bir turda ayıklanan en fazla öğe (fazlası sonraki tura kalır, kaybolmaz)
   active_hours: [7, 24]          # Taslakların yayıldığı saatler (gece en fazla birkaç haber gelir, kalanlar sabaha kalır)
   max_item_age_hours: 36         # Bundan eski haberler atlanır
@@ -179,8 +181,8 @@
     kind: media
 
-  # ── Girişimler (uzman okura hitap eden kaynaklar kapalı; istersen # işaretini kaldır) ──
-  # - name: Crunchbase News
-  #   url: https://news.crunchbase.com/feed/
-  #   kind: media
+  # ── Girişimler ──
+  - name: Crunchbase News
+    url: https://news.crunchbase.com/feed/
+    kind: media
   # - name: EU-Startups
   #   url: https://www.eu-startups.com/feed/
@@ -234,4 +236,250 @@
   - name: Anadolu Ajansı
     url: https://www.aa.com.tr/tr/rss/default?cat=bilim-teknoloji
+    kind: media
+
+  # ── Resmi duyurular (ek) ──
+  - name: Microsoft
+    url: https://blogs.microsoft.com/feed/
+    kind: official
+  - name: Meta
+    url: https://about.fb.com/feed/
+    kind: official
+  - name: Google DeepMind
+    url: https://deepmind.google/blog/rss.xml
+    kind: official
+  - name: PlayStation Blog
+    url: https://blog.playstation.com/feed/
+    kind: official
+  - name: Xbox Wire
+    url: https://news.xbox.com/en-us/feed/
+    kind: official
+  - name: NASA
+    url: https://www.nasa.gov/news-release/feed/
+    kind: official
+
+  # ── Dünya: teknoloji ve ürünler (ek) ──
+  - name: 9to5Mac
+    url: https://9to5mac.com/feed/
+    kind: media
+  - name: MacRumors
+    url: https://feeds.macrumors.com/MacRumors-All
+    kind: media
+  - name: AppleInsider
+    url: https://appleinsider.com/rss/news/
+    kind: media
+  - name: 9to5Google
+    url: https://9to5google.com/feed/
+    kind: media
+  - name: Android Authority
+    url: https://www.androidauthority.com/feed/
+    kind: media
+  - name: Android Police
+    url: https://www.androidpolice.com/feed/
+    kind: media
+  - name: Android Central
+    url: https://www.androidcentral.com/feed
+    kind: media
+  - name: SamMobile
+    url: https://www.sammobile.com/feed/
+    kind: media
+  - name: XDA
+    url: https://www.xda-developers.com/feed/
+    kind: media
+  - name: Tom's Guide
+    url: https://www.tomsguide.com/feeds/all
+    kind: media
+  - name: TechRadar
+    url: https://www.techradar.com/rss
+    kind: media
+  - name: Digital Trends
+    url: https://www.digitaltrends.com/feed/
+    kind: media
+  - name: CNET
+    url: https://www.cnet.com/rss/news/
+    kind: media
+  - name: ZDNET
+    url: https://www.zdnet.com/news/rss.xml
+    kind: media
+  - name: Gizmodo
+    url: https://gizmodo.com/rss
+    kind: media
+  - name: Tom's Hardware
+    url: https://www.tomshardware.com/feeds/all
+    kind: media
+  - name: Wccftech
+    url: https://wccftech.com/feed/
+    kind: media
+  - name: VideoCardz
+    url: https://videocardz.com/feed
+    kind: media
+  - name: The Next Web
+    url: https://thenextweb.com/feed
+    kind: media
+  - name: Pocket-lint
+    url: https://www.pocket-lint.com/feed/
+    kind: media
+  - name: Stuff
+    url: https://www.stuff.tv/feed/
+    kind: media
+  - name: T3
+    url: https://www.t3.com/feeds/all
+    kind: media
+
+  # ── Dünya: büyük haber kuruluşlarının teknoloji bölümleri ──
+  - name: BBC Teknoloji
+    url: https://feeds.bbci.co.uk/news/technology/rss.xml
+    kind: media
+  - name: The Guardian Teknoloji
+    url: https://www.theguardian.com/uk/technology/rss
+    kind: media
+  - name: New York Times Teknoloji
+    url: https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml
+    kind: media
+  - name: Bloomberg Teknoloji
+    url: https://feeds.bloomberg.com/technology/news.rss
+    kind: media
+  - name: CNBC Teknoloji
+    url: https://www.cnbc.com/id/19854910/device/rss/rss.html
+    kind: media
+
+  # ── Tasarım ve yeni ürünler ──
+  - name: Yanko Design
+    url: https://www.yankodesign.com/feed/
+    kind: media
+  - name: Dezeen Teknoloji
+    url: https://www.dezeen.com/technology/feed/
+    kind: media
+  - name: designboom Teknoloji
+    url: https://www.designboom.com/technology/feed/
+    kind: media
+
+  # ── Fotoğraf makinesi, objektif ve drone ──
+  - name: DPReview
+    url: https://www.dpreview.com/feeds/news.xml
+    kind: media
+  - name: PetaPixel
+    url: https://petapixel.com/feed/
+    kind: media
+  - name: Digital Camera World
+    url: https://www.digitalcameraworld.com/feeds/all
+    kind: media
+  - name: Fstoppers
+    url: https://fstoppers.com/rss.xml
+    kind: media
+  - name: DIY Photography
+    url: https://www.diyphotography.net/feed/
+    kind: media
+  - name: DroneDJ
+    url: https://dronedj.com/feed/
+    kind: media
+
+  # ── Sızıntılar (yalnızca güvenilir ve ayrıntılı olanlar haber olur) ──
+  - name: Photo Rumors
+    url: https://photorumors.com/feed/
+    kind: community
+  - name: Sony Alpha Rumors
+    url: https://www.sonyalpharumors.com/feed/
+    kind: community
+  - name: Canon Rumors
+    url: https://www.canonrumors.com/feed/
+    kind: community
+  - name: Nikon Rumors
+    url: https://nikonrumors.com/feed/
+    kind: community
+  - name: Fuji Rumors
+    url: https://www.fujirumors.com/feed/
+    kind: community
+
+  # ── Ses sistemleri, TV, giyilebilir ──
+  - name: What Hi-Fi
+    url: https://www.whathifi.com/feeds/all
+    kind: media
+  - name: SoundGuys
+    url: https://www.soundguys.com/feed/
+    kind: media
+  - name: Wareable
+    url: https://www.wareable.com/rss
+    kind: media
+  - name: DC Rainmaker
+    url: https://www.dcrainmaker.com/feed
+    kind: media
+
+  # ── Otomobil ve elektrikli araç (ek) ──
+  - name: Motor1
+    url: https://www.motor1.com/rss/news/all/
+    kind: media
+  - name: InsideEVs
+    url: https://insideevs.com/rss/news/all/
+    kind: media
+  - name: Car and Driver
+    url: https://www.caranddriver.com/rss/all.xml/
+    kind: media
+  - name: The Drive
+    url: https://www.thedrive.com/feed
+    kind: media
+  - name: Autoblog
+    url: https://www.autoblog.com/rss.xml
+    kind: media
+  - name: Teslarati
+    url: https://www.teslarati.com/feed/
+    kind: media
+  - name: CarNewsChina
+    url: https://carnewschina.com/feed/
+    kind: media
+
+  # ── Oyun (ek) ──
+  - name: Eurogamer
+    url: https://www.eurogamer.net/feed
+    kind: media
+  - name: PC Gamer
+    url: https://www.pcgamer.com/rss/
+    kind: media
+  - name: Kotaku
+    url: https://kotaku.com/rss
+    kind: media
+  - name: GameSpot
+    url: https://www.gamespot.com/feeds/news/
+    kind: media
+  - name: Rock Paper Shotgun
+    url: https://www.rockpapershotgun.com/feed
+    kind: media
+  - name: Nintendo Life
+    url: https://www.nintendolife.com/feeds/latest
+    kind: media
+  - name: Game Developer
+    url: https://www.gamedeveloper.com/rss.xml
+    kind: media
+
+  # ── Yapay zeka (ek) ──
+  - name: The Decoder
+    url: https://the-decoder.com/feed/
+    kind: media
+  - name: VentureBeat
+    url: https://venturebeat.com/category/ai/feed/
+    kind: media
+
+  # ── Uzay ──
+  - name: Space.com
+    url: https://www.space.com/feeds/all
+    kind: media
+  - name: SpaceNews
+    url: https://spacenews.com/feed/
+    kind: media
+
+  # ── Türkiye (ek) ──
+  - name: Teknoseyir
+    url: https://teknoseyir.com/feed
+    kind: media
+  - name: Technopat
+    url: https://www.technopat.net/feed/
+    kind: media
+  - name: Donanım Arşivi
+    url: https://donanimarsivi.com/feed/
+    kind: media
+  - name: Chip Online
+    url: https://www.chip.com.tr/rss
+    kind: media
+  - name: Swipeline
+    url: https://swipeline.co/feed/
     kind: media
 
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -72,5 +72,5 @@
 🙈 <b>Ana sayfada gösterme</b> — haber ana sayfaya çıkmaz, kategoride ve "Tüm haberler"de kalır
 
-<b>Seçki:</b> Sitede aynı gün her şey yer almaz. Haber masası aynı olayı tek habere toplar; yayın yönetmeni o güne kadar yayınlananları görerek karar verir: bu alanı takip eden biri için günün kaçırılmaması gereken gelişmesi mi? Aynı şirketten 24 saatte bir haber (günün en büyük haberleri hariç), yayındaki bir haberin devamı gelirse yeni haber yerine 🔄 <b>güncelleme önerisi</b> gelir; onaylarsan mevcut haber yeni gelişmeyle güncellenir, adresi değişmez. Neyin neden elendiğini /secki gösterir.
+<b>Seçki:</b> Sitede aynı gün her şey yer almaz. Haber masası aynı olayı tek habere toplar; yayın yönetmeni o güne kadar yayınlananları görerek karar verir: bu alanı takip eden biri için günün kaçırılmaması gereken gelişmesi mi? Aynı olay tek haber olur; yayındaki bir haberin devamı gelirse yeni haber yerine 🔄 <b>güncelleme önerisi</b> gelir; onaylarsan mevcut haber yeni gelişmeyle güncellenir, adresi değişmez. Neyin neden elendiğini /secki gösterir.
 
 <b>Ana sayfa seçkisi:</b> Her haber ana sayfaya çıkmaz. Yapay zeka her habere bir ilgi puanı verir; puan ve tazeliğe göre en dikkat çekiciler manşete ve "Öne çıkanlar"a girer.
@@ -199,17 +199,28 @@
         seeded = set(self.state.get("seeded_sources", []))
         max_age = ed("max_item_age_hours", 36)
-        fresh = []
+        fresh, keys = [], set()
         for it in items:
-            if it["key"] in st.seen:
+            if it["key"] in st.seen or it["key"] in keys:
                 continue
-            st.seen[it["key"]] = iso(now_utc())
-            if it["source"] not in seeded and (it["html_source"] or not it["published"]):
-                continue  # tarihsiz kaynağın ilk taraması: sadece "görüldü" olarak işaretle
+            keys.add(it["key"])
+            if it["source"] not in seeded and (it["html_source"] or not it["published"]
+                                               or hours_since(it["published"]) > 6):
+                st.seen[it["key"]] = iso(now_utc())   # yeni eklenen kaynağın ilk taraması: eski haberleri yığma
+                continue
             if it["published"] and hours_since(it["published"]) > max_age:
+                st.seen[it["key"]] = iso(now_utc())
                 continue
             fresh.append(it)
         self.state["seeded_sources"] = sorted(seeded | {it["source"] for it in items})
         self.state["last_collect"] = iso(now_utc())
-        log.info("Yeni öğe: %d (toplam okunan %d)", len(fresh), len(items))
+        # Bir turda en fazla N öğe ayıklanır; kalanlar "görülmedi" sayılır ve sonraki turda sıraya girer (kaybolmaz)
+        batch = int(ed("triage_batch", 100) or 100)
+        fresh.sort(key=lambda x: (KIND_ORDER.get(x["kind"], 3), hours_since(x["published"]) if x["published"] else 0))
+        later = len(fresh) - batch
+        fresh = fresh[:batch]
+        for it in fresh:
+            st.seen[it["key"]] = iso(now_utc())
+        log.info("Yeni öğe: %d (toplam okunan %d%s)", len(fresh), len(items),
+                 f", {later} tanesi sonraki tura kaldı" if later > 0 else "")
         queue = self._queue(max_age)
         if not fresh and not queue:
@@ -219,6 +230,4 @@
         new_stories, merged, skipped = [], 0, 0
         if fresh:
-            fresh.sort(key=lambda x: (KIND_ORDER.get(x["kind"], 3), hours_since(x["published"]) if x["published"] else 0))
-            fresh = fresh[:80]
             by_tid = {}
             for i, it in enumerate(fresh, 1):
@@ -242,5 +251,5 @@
                 tri = self.llm.json(cfg.get("ai", "triage_model", "claude-haiku-4-5-20251001"),
                                     triage_system(self.brand), triage_user(fresh, recent[:150], today),
-                                    TRIAGE_SCHEMA, max_tokens=8000)
+                                    TRIAGE_SCHEMA, max_tokens=12000)
             except LLMError as e:
                 if self._transient(e):
@@ -409,6 +418,6 @@
     def _guard(self, queue: list[dict], decisions: dict[int, dict], slots: int, min_score: int,
                covered: list[dict]) -> dict[int, dict]:
-        """Yönetmen kararlarına kurallı emniyet: eşik, günlük şirket sınırı, tur başına yer, aynı turda aynı şirket yok."""
-        cap = int(self.cfg.get("editorial", "max_per_company_per_day", 1) or 1)
+        """Yönetmen kararlarına kurallı emniyet: eşik, tur başına yer, aynı habere tek güncelleme, (isteğe bağlı) şirket sınırı."""
+        cap = int(self.cfg.get("editorial", "max_per_company_per_day", 0) or 0)   # 0 = sınır yok
         day_keys: dict[str, int] = {}
         for c in covered:
@@ -420,5 +429,5 @@
         pending = {c["id"] for c in covered if c["status"] == "pending"}
         refreshed = {c["id"] for c in covered if c["status"] == "published" and c.get("updated") and c["hours"] < 6}
-        used, round_keys, round_targets = 0, set(), set()
+        used, round_targets = 0, set()
         for i in sorted(decisions, key=lambda i: -decisions[i]["must_read"]):
             x, s = decisions[i], queue[i]["story"]
@@ -451,7 +460,5 @@
             if mr < min_score:
                 x["action"], x["reason"] = "skip", f"önem {mr}/10, eşik {min_score}"
-            elif keys & round_keys:
-                x["action"] = "hold"
-            elif mr < 9 and any(day_keys.get(k, 0) >= cap for k in keys):
+            elif cap and mr < 9 and any(day_keys.get(k, 0) >= cap for k in keys):
                 x["action"], x["reason"] = "skip", "aynı şirketten son 24 saatte haber var"
             elif used >= slots:
@@ -459,5 +466,4 @@
             else:
                 used += 1
-                round_keys |= keys
         return decisions
 
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -7,5 +7,6 @@
 CATEGORY_HELP = (
     "super-zeka = artificial intelligence: AI models, AI products and features, AI companies, AI research, AI chips, AI policy and new real-world uses of AI; "
-    "teknoloji = consumer tech and big tech: newly unveiled phones, computers, wearables, TVs, smart home, apps; new car and EV models; "
+    "teknoloji = consumer tech and big tech: newly unveiled phones, computers, tablets, wearables, cameras and lenses, drones, "
+    "headphones and audio systems, TVs and home entertainment, smart home and home appliances, apps; new car and EV models; "
     "big-tech company news, platforms, internet, social media, cybersecurity, telecom, tech regulation (use when the story is not mainly about AI); "
     "inovasyon = technologies tried or demonstrated for the first time, prototypes, science breakthroughs, robotics, space, energy, batteries, "
@@ -59,13 +60,20 @@
 consumer tech, cars/EVs, innovation, startups and the gaming world, covering both the world and Turkey.
 Our readers follow these fields closely and open the site every day to see the developments that matter in THEIR field.
-We are not a news aggregator: we publish only about 10 carefully chosen stories a day across all verticals, and we never
-publish the same development twice. You receive a batch of NEW ITEMS fetched from RSS feeds and a list of RECENT STORIES
-(published, pending, queued, and recently rejected or expired ones).
+We cover the whole world of technology people use — phones and computers, but also cameras and lenses, headphones and
+audio systems, TVs, smart home and home appliances, wearables, drones, e-mobility, cars, consoles and games, AI and
+startups. We follow the global giants and premium brands closely (Apple, Samsung, Google, Microsoft, Sony, Meta, Amazon,
+NVIDIA, OpenAI, Anthropic, Tesla, SpaceX, BYD, Xiaomi and Huawei flagships, Nintendo, Canon, Nikon, Fujifilm, Leica, DJI,
+GoPro, Bose, Sonos, Bang & Olufsen, Sennheiser, Dyson, LG, Garmin, the big car makers, TOGG…). We have a premium, quality
+feel: we do not cover very cheap or entry-level products. We never publish the same development twice. You receive a batch
+of NEW ITEMS fetched from RSS feeds and a list of RECENT STORIES (published, pending, queued, and recently rejected or
+expired ones).
 
 Do the following:
-1. Group items that report the same underlying event into ONE story. Same event includes: a company's own announcement and
-   media coverage of it; English and Turkish reports; and everything announced at the same launch event or in the same
-   announcement wave (a phone, watch and tablet unveiled together by one brand = ONE story). Every item id must appear in
-   exactly one story.
+1. Group items that report the same underlying event into ONE story: a company's own announcement and media coverage of
+   it, English and Turkish reports of it. Products launched together: if each product is significant on its own (a new
+   iPhone and a new Apple Watch; three new Citroën models; a new Sony camera and a new Sony lens) they are SEPARATE stories.
+   If the products are variants or accessories of one launch, or the brand is not a global giant / premium brand, merge the
+   whole launch into ONE story (Honor's phone, watch and tablet unveiled together = one story). Every item id must appear
+   in exactly one story.
 2. on_topic: true only if the story is substantially about technology, AI, consumer tech products, startups/venture funding,
    innovation/science breakthroughs, cars/EVs/mobility, video games/gaming industry, or big-tech business/policy/security.
@@ -76,28 +84,29 @@
    Follow-ups count as the same story: local availability or price of an already covered product, hands-on or review of it,
    reactions, analysis, more details about the same announcement.
-4. importance (integer 1–10). THE TEST: would a person who follows this vertical closely (an AI practitioner, a phone and
-   gadget enthusiast, a car/EV enthusiast, a startup/VC watcher, a gamer) consider this one of TODAY's must-know developments
-   in their field — something they would be annoyed to miss? Most items fail this test.
+4. importance (integer 1–10). THE TEST: would a person who follows this area closely (an AI practitioner, a phone and
+   gadget enthusiast, a photographer, an audio fan, a car/EV enthusiast, a startup/VC watcher, a gamer) want to see this
+   today — something they would be annoyed to miss? Many items fail this test.
    9–10 the day's defining stories: frontier AI model releases or major capability jumps; flagship launches (iPhone, Galaxy S/Z,
         Pixel, new PlayStation/Xbox/Nintendo hardware); landmark regulation or court rulings that change an industry; >$1B
         acquisitions or rounds; genuine first-ever achievements (e.g. a rocket reaching orbit for the first time); the release
         date or reveal of a hugely anticipated game
-   8    clearly significant: a new product or model from a leading company that moves its category; a new AI capability many
-        people will actually use; a major strategic move by a big company; a security incident affecting many users; an
-        important Turkish tech development (TOGG, a large Turkish startup round, a regulation affecting a big platform in
-        Türkiye); a major game announcement or a studio shake-up
-   7    noteworthy for followers but not essential: notable launches outside the top tier, a startup with a sizeable round and a
-        clear, interesting idea, research with a clear path to real products
-   ≤6   everything else, in particular: regional availability or local price of already announced products (except true
-        flagships arriving in Türkiye), mid-range and budget devices, secondary product lines (watches, bands, earbuds, tablets,
-        accessories) unless genuinely novel, launch-date teasers, unboxings, hands-ons, camera samples, benchmarks, spec leaks
-        and rumors, concept cars, design studies and show displays, trims and facelifts, lab or university research without a
-        near-term product, executive opinions and interviews, partnerships and MoUs, recalls, awards and competitions,
-        stock and market moves, deals and discounts, reviews, guides, listicles, podcasts, events and webinars, B2B/enterprise
-        software, developer tools, cloud and data-centre deals, minor model versions
-   Company saturation: if RECENT STORIES already contain a story about the same company or product family from the last
-   24 hours, a new story about it gets importance ≤6 unless it is a separate and clearly bigger development (then ≥8).
-   Be strict and honest; do not inflate scores. Judge each vertical on its own scale so that games and cars are not crowded
-   out by AI, and AI does not crowd out everything else.
+   8    clearly significant: a new product from a global giant or premium brand (phones, computers, watches, earbuds,
+        cameras, lenses, headphones, speakers, TVs, drones, home appliances, consoles); a new car or EV model from a known
+        maker; a new AI capability many people will actually use; a major strategic move by a big company; a security
+        incident affecting many users; an important Turkish tech development (TOGG, a large Turkish startup round, a
+        regulation affecting a big platform in Türkiye); a major game announcement or a studio shake-up
+   7    noteworthy: notable launches from well-known mid-tier brands, credible and detailed leaks about an anticipated
+        flagship (from reputable reporters or leakers such as Mark Gurman, certification filings, official teasers,
+        supply-chain reports with specifics), a startup with a sizeable round and a clear idea, research with a clear path to
+        real products, the Türkiye price and availability of a flagship
+   ≤6   everything else, in particular: very cheap, budget or entry-level products and their regional launches, minor
+        accessories, vague rumors and unsourced leaks, launch-date teasers without details, unboxings, hands-ons, camera
+        samples, benchmarks, concept cars, design studies and show displays, trims and facelifts, lab or university research
+        without a near-term product, executive opinions and interviews, partnerships and MoUs, recalls, awards and
+        competitions, stock and market moves, deals and discounts, reviews, guides, listicles, podcasts, events and webinars,
+        B2B/enterprise software, developer tools, cloud and data-centre deals, minor model or software versions
+   Several stories about the same company on the same day are fine when each is a distinct, newsworthy development.
+   Be strict and honest; do not inflate scores. Judge each area on its own scale so that cameras, audio, cars and games are
+   not crowded out by AI, and AI does not crowd out everything else.
 5. category: one of {CATEGORY_KEYS}. Guide: {CATEGORY_HELP}.
    Stories about Turkey go to their topical category (a Turkish game studio's funding round → girisimcilik or gaming).
@@ -155,7 +164,9 @@
 def edit_system(site_name: str, min_score: int) -> str:
     return f"""You are the editor-in-chief of "{site_name}", a Turkish-language, hand-curated daily briefing about AI, consumer
-tech, cars/EVs, innovation, startups and gaming. Readers follow these fields closely and come back every day to see the
-developments that matter in their field. The site must feel selective and fresh: a small number of must-know stories,
-never two stories about the same thing, never a feed full of one brand.
+tech (phones, computers, cameras, audio, TVs, smart home, wearables, drones), cars/EVs, innovation, startups and gaming.
+Readers follow these fields closely and come back every day to see the developments that matter in their field. We follow
+the global giants and premium brands closely and keep a premium, quality feel: no very cheap or entry-level products,
+never two stories about the same thing. Several stories about the same company are fine when each is a distinct,
+newsworthy development (e.g. Apple's new iPhone and new Apple Watch; three new Citroën models).
 
 You receive COVERED stories (what we already published, what is waiting for approval, and what the editor rejected) and
@@ -166,17 +177,16 @@
   time, a major new fact that changes the story). Put the covered story id in target. We will update that article
   instead of publishing a new one.
-- "skip": not a must-know story; or the same/very similar to a covered story without a substantial new development; or
-  about a company/product family we already covered in the last 24 hours and not clearly one of the day's biggest stories;
-  or a follow-up of a story the editor rejected.
+- "skip": not worth our readers' time (see the ≤6 list); or the same/very similar to a covered story without a substantial
+  new development; or a follow-up of a story the editor rejected.
 - "hold": a good story that does not fit into this round's free slots; it may be reconsidered in a later round.
-must_read (1–10): would a close follower of this vertical consider it one of TODAY's must-know developments?
-9–10 the day's defining stories; 8 clearly significant for the field; 7 noteworthy but not essential; ≤6 routine.
-Most candidates are 6–7. Regional availability or local prices, secondary products (watches, earbuds, tablets, budget
-phones), teasers, unboxings, rumors, concept/design displays, lab research without products, opinions and minor updates
-are ≤6.
+must_read (1–10): would a close follower of this area want to see it today?
+9–10 the day's defining stories; 8 clearly significant (e.g. a new product from a global giant or premium brand — phones,
+cameras, headphones, TVs, watches, consoles —, a new car model from a known maker); 7 noteworthy (notable mid-tier
+launches, credible detailed leaks about an anticipated flagship, a flagship's Türkiye price); ≤6 routine: very cheap or
+entry-level products, minor accessories, vague rumors, teasers, unboxings, concept/design displays, lab research without
+products, opinions and minor updates.
 Rules:
 - At most SLOTS "publish" decisions in this round; if more qualify, publish the strongest and "hold" the rest.
-- Diversity: never publish two candidates about the same company in one round; prefer spreading across verticals.
-- Duplicates among candidates: publish at most one of them.
+- Duplicates among candidates (same product or event): publish at most one of them.
 - target: the covered story id for "update" (e.g. "ab12cd34ef"), the most similar covered id for a duplicate "skip", else "".
 - reason: ≤12 words in Turkish."""
--- a/haberbot/sources.py
+++ b/haberbot/sources.py
@@ -12,8 +12,8 @@
 
 from .config import Config
-from .util import (clip, domain_of, iso, log, normalize_url, now_utc, parse_iso,
+from .util import (clip, domain_of, hours_since, iso, log, normalize_url, now_utc, parse_iso,
                    publisher_name, short_hash, slugify, strip_html)
 
-UA = "Mozilla/5.0 (compatible; SmarityBot/1.0; +https://github.com/)"
+UA = "Mozilla/5.0 (compatible; SmarityBot/1.0; +https://smarity.com.tr)"
 
 NS = {
@@ -156,5 +156,5 @@
 
 
-def _fetch(url: str, timeout: int = 20) -> bytes:
+def _fetch(url: str, timeout: int = 15) -> bytes:
     r = requests.get(url, headers={"User-Agent": UA, "Accept": "*/*"}, timeout=timeout)
     r.raise_for_status()
@@ -177,8 +177,13 @@
 
 
+def _resting(h: dict) -> bool:
+    """Üst üste 6 kez okunamayan kaynak dinlenir: 6 saatte bir yeniden denenir (turlar yavaşlamasın)."""
+    return h.get("fails", 0) >= 6 and hours_since(h.get("last_try")) < 6
+
+
 def fetch_all(cfg: Config, store) -> list[dict]:
     """Tüm kaynakları paralel okur. Kaynak sağlığını store.state'e yazar."""
-    sources = cfg.sources
     health = store.state.setdefault("source_health", {})
+    sources = [s for s in cfg.sources if cfg.fixtures_dir or not _resting(health.get(s["name"], {}))]
     results: list[dict] = []
 
@@ -189,7 +194,8 @@
             return src, [], f"{type(e).__name__}: {e}"[:200]
 
-    with ThreadPoolExecutor(max_workers=8) as ex:
+    with ThreadPoolExecutor(max_workers=16) as ex:
         for src, entries, err in ex.map(work, sources):
             h = health.setdefault(src["name"], {})
+            h["last_try"] = iso(now_utc())
             if err:
                 h["fails"] = h.get("fails", 0) + 1
--- a/tests/test_editor.py
+++ b/tests/test_editor.py
@@ -24,24 +24,27 @@
     with _App() as (cfg, a):
         a.store.save_post(_post(1, 3, tags=["Honor"], entities=["Honor", "Honor Magic9"]))
-        queue = [_q("Honor Watch 6 Pro launched", 8, ["Honor"]),           # aynı şirket bugün var → geç
+        queue = [_q("Honor Watch 6 Pro launched", 8, ["Honor"]),           # aynı şirketten ikinci haber: sorun değil
                  _q("Starship reaches orbit", 9, ["SpaceX", "Starship"]),   # yayınla
-                 _q("Falcon 9 retirement date", 8, ["SpaceX"]),             # aynı turda aynı şirket → beklet
-                 _q("Minor app update", 7, ["Foo"]),                        # eşik altı → geç
-                 _q("Big AI launch", 9, ["Anthropic"]),                     # yer yok → beklet (slots=1)
+                 _q("Falcon 9 retirement date", 8, ["SpaceX"]),             # yer yok → beklet
+                 _q("Minor app update", 6, ["Foo"]),                        # eşik altı → geç
+                 _q("Big AI launch", 9, ["Anthropic"]),                     # yayınla
                  _q("Honor Magic9 price in Europe", 8, ["Honor"], dup="s:p01"),   # yayındaki haberin devamı → güncelle
                  ]
-        dec = {i: {"action": "publish", "target": "", "must_read": q["story"]["importance"], "reason": ""}
-               for i, q in enumerate(queue)}
-        out = a._guard(queue, dec, slots=1, min_score=8, covered=a._covered(48))
+        dec = lambda: {i: {"action": "publish", "target": "", "must_read": q["story"]["importance"], "reason": ""}  # noqa: E731
+                       for i, q in enumerate(queue)}
+        out = a._guard(queue, dec(), slots=3, min_score=7, covered=a._covered(48))
         acts = [out[i]["action"] for i in range(len(queue))]
-        assert acts[1] == "publish"
-        assert acts[0] == "skip" and "24 saat" in out[0]["reason"]
-        assert acts[2] == "hold" and acts[3] == "skip" and acts[4] == "hold"
+        assert acts[1] == "publish" and acts[4] == "publish" and acts[0] == "publish"
+        assert acts[2] == "hold" and acts[3] == "skip"
         assert acts[5] == "update" and out[5]["target"] == "p01"
+        # ayarlardan şirket sınırı açılırsa: aynı şirketten 24 saatte ikinci haber (9 altı) elenir
+        cfg.raw.setdefault("editorial", {})["max_per_company_per_day"] = 1
+        out = a._guard(queue, dec(), slots=3, min_score=7, covered=a._covered(48))
+        assert out[0]["action"] == "skip" and "24 saat" in out[0]["reason"]
 
 
 def test_edit_uses_llm_and_falls_back():
     with _App() as (cfg, a):
-        queue = [_q("Starship reaches orbit", 9, ["SpaceX"]), _q("Vivo unboxing", 7, ["Vivo"])]
+        queue = [_q("Starship reaches orbit", 9, ["SpaceX"]), _q("Vivo unboxing", 6, ["Vivo"])]
         dec = a._edit(queue, slots=2)                                      # test modu yönetmeni: masa puanı ≥8 → yayınla
         assert dec[0]["action"] == "publish" and dec[1]["action"] == "skip"
@@@SM@@@ SHA
cfe7faa24afb3a21acd72360cf7c1d3dd3783b8e80dbc55a1ba40e4801e116b9 config.yaml
0562d09da3290d070e359fe171b6940489940fb35013f55996036bf30102508f haberbot/app.py
46282852f25b36adefa1834fcd3b30e3e7fdadab7f9ac5f74b8622b840a4eb22 haberbot/prompts.py
8bdb965f48d74d7e63289b0e2f211da09b4232815af0ec1cc324adb9456fa084 haberbot/sources.py
7aa8dca626289bcfad42ffdb24eff1c852370e1d304f35a9823ae9fb1992728a tests/test_editor.py
