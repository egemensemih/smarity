SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -47,10 +47,12 @@
   # Seçki iki aşamalı: haber masası kaynakları ayıklar ve aynı olayı tek habere toplar (min_importance), ardından
   # yayın yönetmeni o güne kadar yayınlananları görerek karar verir: yeni haber / mevcut haberi güncelle / geç / beklet.
-  # Ölçüt: "Bu alanı yakından takip eden biri bunu bugün görmek ister mi?" Dünya devleri ve premium markalar yakından
-  # izlenir; çok ucuz / giriş seviyesi ürünler, söylentiler, kutu açılışları vb. elenir.
+  # Ölçüt: "Teknolojiyi seven sıradan Türk okurların çoğu bunu bugün tıklayıp konuşur mu?" Dünya devleri, premium
+  # markalar, Türkiye girişim ekosistemi ve en büyük oyun serileri izlenir; yurtdışındaki girişim yatırımları, niş oyun
+  # haberleri, yalnızca yurtdışını ilgilendiren araç/fiyat haberleri, B2B, araştırma, söylenti vb. elenir.
   min_importance: 7              # 1-10. Haber masasının aday eşiği
-  min_must_read: 7               # 1-10. Yayın yönetmeninin yeni haber eşiği (daha seçici: 8)
+  min_must_read: 8               # 1-10. Yayın yönetmeninin yeni haber eşiği
+  daily_target: 20               # Günde yaklaşık kaç yeni haber; aşılınca yalnızca çok büyük (önem ≥ 9) haberler gelir
   max_per_company_per_day: 0     # Aynı şirketten 24 saatte en fazla kaç haber (0 = sınır yok)
-  max_drafts_per_run: 3          # Bir taramada en fazla kaç yeni haber taslağı yazılsın (haberler tek tek, düzenli gelsin)
+  max_drafts_per_run: 2          # Bir taramada en fazla kaç yeni haber taslağı yazılsın (haberler tek tek, düzenli gelsin)
   max_drafts_per_day: 0          # Günlük üst sınır (0 = sınır yok)
   burst: 2                       # Günlük sınır varsa: günün başında sınırın önüne geçebilecek taslak sayısı
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -54,4 +54,5 @@
 COMMANDS_VERSION = 4
 COVERLINE_V = 3               # kapak başlığı yazım kuralları değişince eski haberlerin kapak başlıkları yeniden yazılır
+RESELECT_V = 1                # seçki ölçütleri değişince artır: onay bekleyen yığın bir kez yeniden elden geçer
 KEYBOARD_VERSION = 4          # yayındaki haber mesajlarının düğmeleri bu sürüme göre bir kez yenilenir
 HELP = """<b>Nasıl çalışır?</b>
@@ -387,5 +388,5 @@
         now_l = local(now_utc(), cfg.tz)
         today_n = self.store.count(self.today(), "drafts")
-        target = int(ed("max_drafts_per_day", 0) or 0) or 10
+        target = self._daily_target()
         raw = None
         try:
@@ -416,8 +417,15 @@
         return self._guard(queue, decisions, slots, min_score, covered)
 
+    def _daily_target(self) -> int:
+        """Günlük yeni haber hedefi: aşılınca yalnızca çok büyük (önem ≥ 9) haberler yazılır."""
+        ed = lambda k, d: self.cfg.get("editorial", k, d)  # noqa: E731
+        return int(ed("max_drafts_per_day", 0) or 0) or int(ed("daily_target", 20) or 0) or 10 ** 6
+
     def _guard(self, queue: list[dict], decisions: dict[int, dict], slots: int, min_score: int,
                covered: list[dict]) -> dict[int, dict]:
-        """Yönetmen kararlarına kurallı emniyet: eşik, tur başına yer, aynı habere tek güncelleme, (isteğe bağlı) şirket sınırı."""
+        """Yönetmen kararlarına kurallı emniyet: eşik, tur başına yer, aynı habere tek güncelleme, günlük hedef,
+        (isteğe bağlı) şirket sınırı."""
         cap = int(self.cfg.get("editorial", "max_per_company_per_day", 0) or 0)   # 0 = sınır yok
+        today_n, target = self.store.count(self.today(), "drafts"), self._daily_target()
         day_keys: dict[str, int] = {}
         for c in covered:
@@ -460,4 +468,6 @@
             if mr < min_score:
                 x["action"], x["reason"] = "skip", f"önem {mr}/10, eşik {min_score}"
+            elif mr < 9 and today_n + used >= target:
+                x["action"], x["reason"] = "skip", f"günlük hedef ({target}) doldu; yalnızca çok büyük haberler"
             elif cap and mr < 9 and any(day_keys.get(k, 0) >= cap for k in keys):
                 x["action"], x["reason"] = "skip", "aynı şirketten son 24 saatte haber var"
@@ -839,4 +849,5 @@
             "rewritten": "🔁 <b>YENİDEN YAZILDI</b> (yeni sürüm aşağıda)",
             "updated": "🔄 <b>HABER GÜNCELLENDİ</b>",
+            "culled": "🧹 <b>SEÇKİ DIŞI</b> (yeni ölçütlere göre elendi)",
         }[kind]
         upd = d.get("update_of")
@@ -999,4 +1010,7 @@
                 time.sleep(min(timeout, 10))
             return 0
+        if ups:
+            log.info("Telegram: %d yeni girdi (offset %s → %s)", len(ups), self.state.get("telegram_offset", 0),
+                     ups[-1]["update_id"] + 1)
         for u in ups:
             self.state["telegram_offset"] = u["update_id"] + 1
@@ -1022,4 +1036,5 @@
             action, _, did = (cq.get("data") or "").partition(":")
             self._cb_mid = (cq.get("message") or {}).get("message_id")
+            log.info("Telegram düğmesi: %s %s", action, did)
             slow = SLOW_ACTIONS.get(action)
             if slow:  # uzun süren işlerde düğme hemen yanıt versin
@@ -1049,4 +1064,5 @@
             return
         self.state["last_activity"] = iso(now_utc())
+        log.info("Telegram mesajı: %s", clip(text, 40))
         self.tg.typing(chat)
 
@@ -1439,4 +1455,65 @@
                 st.archive_draft(d, "rejected")
 
+    def reselect_pending(self) -> None:
+        """Seçki ölçütleri değişince (tek seferlik): onay bekleyen yığını yeni ölçütlerle yeniden elden geçir;
+        geniş okur kitlesine hitap etmeyenler "seçki dışı" olarak arşivlenir."""
+        st = self.state
+        if st.get("reselect_v") == RESELECT_V or not self.llm:
+            return
+        pend = [d for d in self.store.drafts("pending") if not d.get("update_of")]
+        if len(pend) <= 5 or int(st.get("reselect_try", 0)) >= 3:
+            st["reselect_v"] = RESELECT_V
+            return
+        st["reselect_try"] = int(st.get("reselect_try", 0)) + 1
+        cfg = self.cfg
+        min_score = int(cfg.get("editorial", "min_must_read", 8))
+        keep_max = int(cfg.get("editorial", "daily_target", 20) or 20)
+        covered = [c for c in self._covered(48) if c["status"] != "pending"]
+        scores: dict[str, tuple[str, int, str]] = {}
+        for i in range(0, len(pend), 45):
+            chunk = pend[i:i + 45]
+            cands = [{"cid": f"c{n + 1}", "category": d.get("category", ""), "importance": d.get("importance", 0),
+                      "entities": list(d.get("entities") or (d.get("tags") or [])[:2]), "topic": d.get("title", ""),
+                      "dup": "", "headlines": [clip(d.get("summary", ""), 200)]} for n, d in enumerate(chunk)]
+            try:
+                out = self.llm.json(cfg.get("ai", "editor_model", None) or cfg.get("ai", "writer_model", "gemini-flash-latest"),
+                                    edit_system(self.brand, min_score),
+                                    edit_user(local(now_utc(), cfg.tz).strftime("%Y-%m-%d %H:%M"), keep_max, 0, keep_max,
+                                              covered[:90], cands), EDIT_SCHEMA, max_tokens=8000)
+            except LLMError as e:
+                log.warning("Bekleyen taslaklar yeniden seçilemedi (sonra denenecek): %s", str(e)[:160])
+                return
+            for x in out.get("decisions") or []:
+                cid = str(x.get("cid") or "")
+                if cid.startswith("c") and cid[1:].isdigit() and 0 < int(cid[1:]) <= len(chunk):
+                    try:
+                        mr = max(0, min(10, int(x.get("must_read") or 0)))
+                    except (TypeError, ValueError):
+                        mr = 0
+                    scores[chunk[int(cid[1:]) - 1]["id"]] = (str(x.get("action") or ""), mr, clip(str(x.get("reason") or ""), 120))
+        good = sorted((d for d in pend if d["id"] in scores and scores[d["id"]][0] in ("publish", "hold")
+                       and scores[d["id"]][1] >= min_score), key=lambda d: -scores[d["id"]][1])
+        keep = {d["id"] for d in good[:keep_max]} | {d["id"] for d in pend if d["id"] not in scores}
+        culled = 0
+        for d in pend:
+            if d["id"] in keep:
+                continue
+            act, mr, why = scores[d["id"]]
+            d["editor_note"] = clip(f"Seçki dışı: {why or f'önem {mr}/10'}", 140)
+            self._update_preview(d, "culled")
+            self.store.bump(self.today(), "culled")
+            self.store.archive_draft(d, "expired")
+            self._edit_log({"story": {"topic": d.get("title", "")}}, "skip",
+                           {"must_read": mr, "reason": "yığın temizliği: " + why})
+            culled += 1
+            if not cfg.mock:
+                time.sleep(0.4)   # Telegram hız sınırı
+        st["reselect_v"] = RESELECT_V
+        log.info("Bekleyen taslaklar yeni ölçütlerle elden geçirildi: %d kaldı, %d seçki dışı", len(pend) - culled, culled)
+        if culled:
+            self.notify(f"🧹 <b>Seçki daraltıldı</b>\nOnay bekleyen {len(pend)} haberden geniş okura hitap etmeyen {culled} "
+                        f"tanesi elendi; {len(pend) - culled} haber onayında. Bundan sonra günde yaklaşık "
+                        f"{self._daily_target()} haber gelecek (çok büyük haberler hedefi aşabilir).", silent=True)
+
     # ── ARAMA MOTORLARI ─────────────────────────────────────
     def queue_indexnow(self, url: str) -> None:
@@ -1544,11 +1621,6 @@
 
     def _should_listen(self) -> bool:
-        """Telegram'ı canlı dinle: son 10 dakikada sen bir şey yaptıysan her zaman;
-        onay bekleyen haber varsa sessiz saatler dışında."""
-        if self.force_collect:
-            return True
-        if hours_since(self.state.get("last_activity")) * 60 < 10:
-            return True
-        return bool(self.store.drafts("pending")) and not self.quiet()
+        """Telegram'ı her turda canlı dinle (gece de): düğmeler beklemeden işlensin."""
+        return True
 
     # ── 5) INSTAGRAM ────────────────────────────────────────
@@ -2059,4 +2131,8 @@
         self.process_updates()
         self.expire()
+        try:
+            self.reselect_pending()
+        except Exception as e:  # noqa: BLE001
+            log.exception("Bekleyen taslak seçkisi hatası: %s", e)
         every = self.cfg.get("schedule", "collect_every_minutes", 60)
         due = hours_since(self.state.get("last_collect")) * 60 >= every - 2
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -57,15 +57,13 @@
 
 def triage_system(site_name: str) -> str:
-    return f"""You are the news-desk editor of "{site_name}", a Turkish-language, hand-curated daily briefing about AI,
-consumer tech, cars/EVs, innovation, startups and the gaming world, covering both the world and Turkey.
-Our readers follow these fields closely and open the site every day to see the developments that matter in THEIR field.
-We cover the whole world of technology people use — phones and computers, but also cameras and lenses, headphones and
-audio systems, TVs, smart home and home appliances, wearables, drones, e-mobility, cars, consoles and games, AI and
-startups. We follow the global giants and premium brands closely (Apple, Samsung, Google, Microsoft, Sony, Meta, Amazon,
-NVIDIA, OpenAI, Anthropic, Tesla, SpaceX, BYD, Xiaomi and Huawei flagships, Nintendo, Canon, Nikon, Fujifilm, Leica, DJI,
-GoPro, Bose, Sonos, Bang & Olufsen, Sennheiser, Dyson, LG, Garmin, the big car makers, TOGG…). We have a premium, quality
-feel: we do not cover very cheap or entry-level products. We never publish the same development twice. You receive a batch
-of NEW ITEMS fetched from RSS feeds and a list of RECENT STORIES (published, pending, queued, and recently rejected or
-expired ones).
+    return f"""You are the news-desk editor of "{site_name}", a Turkish-language, hand-curated daily tech briefing for a BROAD
+TURKISH AUDIENCE: ordinary people in Türkiye who are curious about technology — not industry insiders, not specialists.
+We cover AI, consumer tech (phones, computers, cameras, audio, TVs, smart home, wearables), cars/EVs, innovation, the
+Turkish startup ecosystem and the biggest names in gaming. We follow the global giants and premium brands closely (Apple,
+Samsung, Google, Microsoft, Sony, Meta, Amazon, NVIDIA, OpenAI, Anthropic, Tesla, SpaceX, BYD, Xiaomi and Huawei flagships,
+Nintendo, Canon, Nikon, Fujifilm, Leica, DJI, Bose, Sonos, Dyson, LG, the big car makers sold in Türkiye, TOGG…). We have a
+premium, quality feel and we publish FEW stories: only what many Turkish readers would actually click and talk about. We
+never publish the same development twice. You receive a batch of NEW ITEMS fetched from RSS feeds and a list of RECENT
+STORIES (published, pending, queued, and recently rejected or expired ones).
 
 Do the following:
@@ -84,29 +82,42 @@
    Follow-ups count as the same story: local availability or price of an already covered product, hands-on or review of it,
    reactions, analysis, more details about the same announcement.
-4. importance (integer 1–10). THE TEST: would a person who follows this area closely (an AI practitioner, a phone and
-   gadget enthusiast, a photographer, an audio fan, a car/EV enthusiast, a startup/VC watcher, a gamer) want to see this
-   today — something they would be annoyed to miss? Many items fail this test.
-   9–10 the day's defining stories: frontier AI model releases or major capability jumps; flagship launches (iPhone, Galaxy S/Z,
-        Pixel, new PlayStation/Xbox/Nintendo hardware); landmark regulation or court rulings that change an industry; >$1B
-        acquisitions or rounds; genuine first-ever achievements (e.g. a rocket reaching orbit for the first time); the release
-        date or reveal of a hugely anticipated game
-   8    clearly significant: a new product from a global giant or premium brand (phones, computers, watches, earbuds,
-        cameras, lenses, headphones, speakers, TVs, drones, home appliances, consoles); a new car or EV model from a known
-        maker; a new AI capability many people will actually use; a major strategic move by a big company; a security
-        incident affecting many users; an important Turkish tech development (TOGG, a large Turkish startup round, a
-        regulation affecting a big platform in Türkiye); a major game announcement or a studio shake-up
-   7    noteworthy: notable launches from well-known mid-tier brands, credible and detailed leaks about an anticipated
-        flagship (from reputable reporters or leakers such as Mark Gurman, certification filings, official teasers,
-        supply-chain reports with specifics), a startup with a sizeable round and a clear idea, research with a clear path to
-        real products, the Türkiye price and availability of a flagship
-   ≤6   everything else, in particular: very cheap, budget or entry-level products and their regional launches, minor
-        accessories, vague rumors and unsourced leaks, launch-date teasers without details, unboxings, hands-ons, camera
-        samples, benchmarks, concept cars, design studies and show displays, trims and facelifts, lab or university research
-        without a near-term product, executive opinions and interviews, partnerships and MoUs, recalls, awards and
-        competitions, stock and market moves, deals and discounts, reviews, guides, listicles, podcasts, events and webinars,
-        B2B/enterprise software, developer tools, cloud and data-centre deals, minor model or software versions
+4. importance (integer 1–10). THE TEST: would MANY ordinary Turkish readers who like technology want to click this today
+   and tell a friend about it? Not "would a specialist find it interesting" — most items fail this test. Be strict.
+   9–10 the day's defining stories: frontier AI model releases or major ChatGPT/Gemini/Claude capability jumps; flagship
+        launches (iPhone, Galaxy S/Z, Pixel, new PlayStation/Xbox/Nintendo hardware); landmark regulation or court rulings
+        that change an industry (EU vs Apple/Google/Meta); acquisitions or rounds above $1B by household names; genuine
+        first-ever achievements (a rocket reaching orbit for the first time); GTA 6-level game news
+   8    clearly significant for a broad audience: a new product from a global giant or premium brand that people in Türkiye
+        can buy or have heard of (phones, computers, watches, earbuds, cameras, headphones, TVs, consoles); a new car or EV
+        model from a big maker sold in Türkiye, or an iconic one; a new AI feature many people will actually use; a major
+        move by a household-name company; a security incident or outage affecting many users; Turkish tech news that
+        touches everyday life (TOGG, BTK/BDDK/KVKK rules, phone taxes and installments, e-Devlet, Turkcell/Türk Telekom/
+        Vodafone moves, internet restrictions); the Turkish startup ecosystem (a Turkish startup's notable round, exit or
+        acquisition — Dream Games, Insider, Getir, Peak, Papara, Trendyol… — Turkish founders abroad, big Turkish VC funds)
+   7    noteworthy: notable launches from well-known mid-tier brands sold in Türkiye; credible and detailed leaks about a
+        hugely anticipated flagship (Mark Gurman, certification filings, official teasers); the Türkiye price and
+        availability of a flagship; a smaller Turkish startup round with a clear, interesting idea
+   ≤6   everything else, in particular:
+        - startups and funding OUTSIDE Türkiye: rounds, valuations and acquisitions of foreign startups are ≤5, unless the
+          company is a household name (OpenAI, Anthropic, xAI, Mistral, SpaceX, Stripe, Revolut…) AND the deal is huge
+        - gaming beyond the biggest names: we only cover franchises and platforms almost everyone knows (GTA, Call of Duty,
+          EA Sports FC, Battlefield, Minecraft, Fortnite, Pokémon, Mario, Zelda, God of War, The Witcher, Elden Ring,
+          Assassin's Creed, Counter-Strike, Valorant, League of Legends, PUBG, Red Dead, The Last of Us), console hardware,
+          big Steam / Game Pass / PlayStation Plus changes, giant studio deals and Turkish studios. Every other game
+          announcement, season update, DLC, expansion, preview, interview, remaster, port, patch, accessory (wheels,
+          controllers) or sales figure is ≤5
+        - car news that only matters abroad: a foreign-market price announcement (US/EU price of a car not yet sold in
+          Türkiye) ≤6; US-only matters (NACS ports, US charging networks, US tax credits, dealer news), trucks, vans, fleet
+          orders and commercial vehicles ≤5; trims, facelifts, special editions, concept cars and reviews ≤5
+        - local news from other countries (a US state's law, a California subpoena, a UK grid problem) unless it changes
+          products Turkish users use
+        - B2B and enterprise: data centres, supercomputers, chip supply and smuggling cases, factories, R&D centres,
+          corporate partnerships and MoUs, enterprise software, developer tools, cloud deals
+        - niche gadgets from little-known brands, very cheap or entry-level products, minor accessories
+        - research papers, lab and university research, AI safety studies, robotics demos without a product
+        - vague rumors and unsourced leaks, teasers without details, unboxings, hands-ons, reviews, benchmarks
+        - executive opinions and interviews, recalls, awards, events, stock and market moves, deals and discounts, guides
    Several stories about the same company on the same day are fine when each is a distinct, newsworthy development.
-   Be strict and honest; do not inflate scores. Judge each area on its own scale so that cameras, audio, cars and games are
-   not crowded out by AI, and AI does not crowd out everything else.
+   Be strict and honest; do not inflate scores. Most items should score ≤6.
 5. category: one of {CATEGORY_KEYS}. Guide: {CATEGORY_HELP}.
    Stories about Turkey go to their topical category (a Turkish game studio's funding round → girisimcilik or gaming).
@@ -163,29 +174,37 @@
 
 def edit_system(site_name: str, min_score: int) -> str:
-    return f"""You are the editor-in-chief of "{site_name}", a Turkish-language, hand-curated daily briefing about AI, consumer
-tech (phones, computers, cameras, audio, TVs, smart home, wearables, drones), cars/EVs, innovation, startups and gaming.
-Readers follow these fields closely and come back every day to see the developments that matter in their field. We follow
-the global giants and premium brands closely and keep a premium, quality feel: no very cheap or entry-level products,
-never two stories about the same thing. Several stories about the same company are fine when each is a distinct,
-newsworthy development (e.g. Apple's new iPhone and new Apple Watch; three new Citroën models).
+    return f"""You are the editor-in-chief of "{site_name}", a Turkish-language, hand-curated daily tech briefing for a BROAD
+TURKISH AUDIENCE: ordinary people in Türkiye who like technology, not industry insiders. We cover AI, consumer tech (phones,
+computers, cameras, audio, TVs, smart home, wearables), cars/EVs, innovation, the Turkish startup ecosystem and the biggest
+names in gaming. We publish FEW stories — only what many Turkish readers would click and talk about — with a premium,
+quality feel: no very cheap or entry-level products, never two stories about the same thing. Several stories about the
+same company are fine when each is a distinct, newsworthy development (e.g. Apple's new iPhone and new Apple Watch).
 
 You receive COVERED stories (what we already published, what is waiting for approval, and what the editor rejected) and
 CANDIDATES proposed by the news desk. Decide for EVERY candidate:
-- "publish": a new must-know story for its field. Allowed only if must_read ≥ {min_score}.
+- "publish": a new must-know story for a broad Turkish audience. Allowed only if must_read ≥ {min_score}.
 - "update": the candidate is the same story or a direct follow-up of a PUBLISHED covered story AND it brings a substantial
   new development (official confirmation, a regulator or court acting, price/date/availability announced for the first
-  time, a major new fact that changes the story). Put the covered story id in target. We will update that article
-  instead of publishing a new one.
+  time — above all for Türkiye —, a major new fact that changes the story). Put the covered story id in target. We will
+  update that article instead of publishing a new one.
 - "skip": not worth our readers' time (see the ≤6 list); or the same/very similar to a covered story without a substantial
   new development; or a follow-up of a story the editor rejected.
 - "hold": a good story that does not fit into this round's free slots; it may be reconsidered in a later round.
-must_read (1–10): would a close follower of this area want to see it today?
-9–10 the day's defining stories; 8 clearly significant (e.g. a new product from a global giant or premium brand — phones,
-cameras, headphones, TVs, watches, consoles —, a new car model from a known maker); 7 noteworthy (notable mid-tier
-launches, credible detailed leaks about an anticipated flagship, a flagship's Türkiye price); ≤6 routine: very cheap or
-entry-level products, minor accessories, vague rumors, teasers, unboxings, concept/design displays, lab research without
-products, opinions and minor updates.
+must_read (1–10): would MANY ordinary Turkish readers who like technology want to see it today?
+9–10 the day's defining stories (a new iPhone or PlayStation, a frontier AI model, GTA 6 news, landmark rulings against
+big tech, huge deals by household names); 8 clearly significant for a broad audience (a new product from a global giant or
+premium brand people in Türkiye can buy; a new car model sold in Türkiye or an iconic one; an AI feature many people will
+use; Turkish tech news that touches everyday life — TOGG, BTK/BDDK/KVKK rules, operators, phone prices and taxes —; the
+Turkish startup ecosystem's notable rounds, exits and founders); 7 noteworthy (credible detailed leaks about a hugely
+anticipated flagship, a flagship's Türkiye price); ≤6 routine — in particular: foreign startups' funding rounds and
+acquisitions (unless a household name and a huge deal), games outside the biggest franchises (GTA, Call of Duty, EA Sports
+FC, Minecraft, Fortnite, Pokémon, Mario, Zelda, The Witcher, Elden Ring, Counter-Strike, Valorant, LoL…) and console
+hardware, season updates/DLC/previews/remasters, car news that only matters abroad (foreign-market prices, US-only charging
+or tax matters, trucks and fleet orders, trims, concepts), local news from other countries, B2B/enterprise (data centres,
+supercomputers, chip supply, factories, R&D centres, partnerships), niche gadgets from little-known brands, research
+papers and AI safety studies, rumors, teasers, reviews, opinions and minor updates.
 Rules:
 - At most SLOTS "publish" decisions in this round; if more qualify, publish the strongest and "hold" the rest.
+- Respect the daily target: once PUBLISHED OR PENDING TODAY reaches it, publish only must_read ≥ 9 stories.
 - Duplicates among candidates (same product or event): publish at most one of them.
 - target: the covered story id for "update" (e.g. "ab12cd34ef"), the most similar covered id for a duplicate "skip", else "".
@@ -271,5 +290,10 @@
 - Always write with correct Turkish characters (ç, ğ, ı, ö, ş, ü, İ) in every field except slug; never write Turkish words in ASCII ("çıkış", not "cikis").
 - Keep product, model, game, car and company names in their original form, including lowercase-first names even at the start of a title or sentence ("iPhone 18 tanıtıldı", never "İPhone"; "eFootball", "iOS"). Briefly explain technical terms on first use if a general reader would not know them.
-- For startup stories, explain in one or two sentences what the company actually does and what problem it solves. For products and cars, include price, availability and the key specs when the sources give them. For games, include platforms and release date when given.
+- For startup stories, explain in one or two sentences what the company actually does and what problem it solves. For products and cars, include availability and the key specs when the sources give them. For games, include platforms and release date when given.
+- We write for readers in Türkiye. Prices: if the sources give a Türkiye price or Türkiye availability, lead with it. A
+  price for another market (US, Europe, China…) is NEVER the headline: keep it out of title, short_title, seo_title,
+  cover_headline and hero_stat, and mention it only in the body with its market and context ("ABD'de 64 bin dolardan
+  başlayan fiyatla satışa çıkacak; Türkiye fiyatı henüz açıklanmadı" — the last part only if the sources do not mention
+  Türkiye). Prefer the product itself, its key feature or its Türkiye relevance for the headline.
 - Money: "350 milyon dolar". Avoid "bugün/dün"; use explicit dates like "22 Eylül'de" when the sources give them.
 
@@ -315,5 +339,5 @@
 - short_title: ≤55 characters, punchy Turkish headline for social cards; still factual, no clickbait, no emojis. Sentence case.
 - kicker: 1–3 Turkish words shown above the headline, like an eyebrow label: e.g. "Yeni ürün", "Lansman", "Yatırım turu", "Girişim hikâyesi", "İlk test", "Yeni model", "Elektrikli araç", "Yeni oyun", "Güvenlik", "Regülasyon".
-- hero_stat: only if ONE number IS the news itself and appears in the sources (the price of the new product, the funding amount, a fine, a record, a range or battery figure that is the headline feature, a user or player count), write it compactly in Turkish format, ≤12 characters: "3,5 milyar $", "30 milyar", "%40", "1 milyon". Otherwise "" — never a year, a date, a model count, a version number, a scale like "1:1" or a side detail. Never invent or round beyond the source.
+- hero_stat: only if ONE number IS the news itself and appears in the sources (the Türkiye price of the new product — never a foreign-market price —, the funding amount, a fine, a record, a range or battery figure that is the headline feature, a user or player count), write it compactly in Turkish format, ≤12 characters: "3,5 milyar $", "30 milyar", "%40", "1 milyon". Otherwise "" — never a year, a date, a model count, a version number, a scale like "1:1" or a side detail. Never invent or round beyond the source.
 - hero_stat_label: ≤30 Turkish characters explaining the number ("yatırım tutarı", "menzil", "başlangıç fiyatı", "oyuncu sayısı"); "" if no hero_stat.
 - visual_style: pick the style that best fits AND varies from a generic look: studio (one sculptural object), macro (material close-up), diorama (tiny isometric world), sculpture (abstract glass/light forms), still_life (symbolic everyday objects).
--- a/haberbot/sources.py
+++ b/haberbot/sources.py
@@ -186,4 +186,7 @@
 
 
+MAX_ITEMS = 60   # bir kaynaktan bir turda bakılan en fazla öğe
+
+
 def _resting(h: dict) -> bool:
     """Üst üste 6 kez okunamayan kaynak dinlenir: 6 saatte bir yeniden denenir (turlar yavaşlamasın)."""
@@ -216,4 +219,7 @@
             h["count"] = len(entries)
             h.pop("last_error", None)
+            if len(entries) > MAX_ITEMS:   # bazı akışlar tüm arşivi verir (ör. 1500 öğe): en yenileri yeter
+                entries = sorted(entries, key=lambda e: iso(e["published"]) if e.get("published") else "",
+                                 reverse=True)[:MAX_ITEMS]
             for e in entries:
                 if not e.get("title") or not e.get("link"):
--- a/templates/archive.html
+++ b/templates/archive.html
@@ -11,5 +11,5 @@
 <header class="page-head wrap"><span class="eyebrow" style="--c:#6E6E73">Arşiv</span><h1>Tüm haberler.</h1><p>En yeniden eskiye, {{ total }} haber{% if pages > 1 %} · Sayfa {{ page }} / {{ pages }}{% endif %}</p></header>
 <nav class="chips wrap center" aria-label="Kategoriler">
-  {% for c in site.categories if c.count %}<a class="chip-link" href="{{ c.url }}" style="--c:{{ c.color }}"><i aria-hidden="true"></i>{{ c.label }}<span>{{ c.count }}</span></a>{% endfor %}
+  {% for c in site.categories if c.count %}<a class="chip-link" href="{{ c.url }}" style="--c:{{ c.color }}"><i aria-hidden="true"></i>{{ c.label }}</a>{% endfor %}
 </nav>
 <section class="wrap sec-tight"><div class="grid">{% for p in posts %}{{ card(p, heading='h2') }}{% endfor %}</div></section>
--- a/templates/category.html
+++ b/templates/category.html
@@ -9,5 +9,5 @@
   <h1>{{ cat.seo_title }}.</h1>
   <p>{{ cat.intro }}</p>
-  <p class="muted small">{% if cat.count %}{{ cat.count }} haber{% else %}Bu kategoride henüz haber yok.{% endif %}</p>
+  {% if not cat.count %}<p class="muted small">Bu kategoride henüz haber yok.</p>{% endif %}
 </header>
 {% if posts %}
--- a/templates/index.html
+++ b/templates/index.html
@@ -61,5 +61,5 @@
   <nav class="chips wrap" aria-label="Kategoriler">
     {% for c in site.categories if c.count %}
-    <a class="chip-link" href="{{ c.url }}" style="--c:{{ c.color }}"><i aria-hidden="true"></i>{{ c.label }}<span>{{ c.count }}</span></a>
+    <a class="chip-link" href="{{ c.url }}" style="--c:{{ c.color }}"><i aria-hidden="true"></i>{{ c.label }}</a>
     {% endfor %}
     <a class="chip-link all" href="{{ all_url }}">Tüm haberler<span>›</span></a>
@@ -101,5 +101,5 @@
   <section class="sec wrap" aria-labelledby="h-konu">
     <div class="sec-head"><h2 id="h-konu">Popüler konular.</h2></div>
-    <div class="tags">{% for t in tags %}<a href="{{ t.url }}">{{ t.label }}<span>{{ t.count }}</span></a>{% endfor %}</div>
+    <div class="tags">{% for t in tags %}<a href="{{ t.url }}">{{ t.label }}</a>{% endfor %}</div>
   </section>
   {% endif %}
--- a/templates/tag.html
+++ b/templates/tag.html
@@ -2,5 +2,5 @@
 {% from "_macros.html" import card, crumbs %}
 {% block title %}{{ tag.label }} haberleri: son gelişmeler | {{ site.name }}{% endblock %}
-{% block description %}{{ tag.label }} ile ilgili en son haberler ve gelişmeler. {{ tag.count }} haber, her biri kaynağıyla ve Türkçe.{% endblock %}
+{% block description %}{{ tag.label }} ile ilgili en son haberler ve gelişmeler. Her haber kaynağıyla ve Türkçe.{% endblock %}
 {% block main %}
 {{ crumbs([("Ana sayfa", site.base ~ "/", site.url ~ "/"), (tag.label, tag.url, site.url ~ "/etiket/" ~ tag.slug ~ "/")]) }}
@@ -9,5 +9,4 @@
   <h1>{{ tag.label }} haberleri.</h1>
   <p>{{ tag.label }} hakkındaki son gelişmeler, kaynağıyla.</p>
-  <p class="muted small">{{ tag.count }} haber</p>
 </header>
 <section class="wrap"><div class="grid">{% for p in posts %}{{ card(p, heading='h2') }}{% endfor %}</div></section>
--- a/tests/test_editor.py
+++ b/tests/test_editor.py
@@ -123,4 +123,28 @@
 
 
+def test_daily_target_and_backlog_reselection():
+    with _App() as (cfg, a):
+        cfg.raw.setdefault("editorial", {})["daily_target"] = 2
+        a.store.bump(a.today(), "drafts", 2)                               # bugün hedef doldu
+        queue = [_q("Starship reaches orbit", 9, ["SpaceX"]), _q("New Sony camera", 8, ["Sony"])]
+        dec = {i: {"action": "publish", "target": "", "must_read": q["story"]["importance"], "reason": ""}
+               for i, q in enumerate(queue)}
+        out = a._guard(queue, dec, slots=3, min_score=8, covered=a._covered(48))
+        assert out[0]["action"] == "publish" and out[1]["action"] == "skip" and "hedef" in out[1]["reason"]
+        # onay bekleyen yığın yeni ölçütlerle bir kez elden geçer
+        for i in range(8):
+            d = {**_post(10 + i, 1, entities=[f"E{i}"]), "status": "pending", "created_at": iso(now_utc()),
+                 "importance": 9 if i < 3 else 6, "telegram": {"message_id": 100 + i}}
+            a.store.save_draft(d)
+        a.reselect_pending()
+        left = a.store.drafts("pending")
+        assert len(left) == 2 and all(d["importance"] == 9 for d in left)   # en iyiler (hedef kadar) kalır
+        assert a.state["reselect_v"] and a.store.count(a.today(), "culled") == 6
+        outbox = (cfg.data_dir / "_mock" / "outbox.jsonl").read_text(encoding="utf-8")
+        assert "SEÇKİ DIŞI" in outbox and "Seçki daraltıldı" in outbox
+        a.reselect_pending()                                               # ikinci kez çalışmaz
+        assert len(a.store.drafts("pending")) == 2
+
+
 if __name__ == "__main__":
     for name, fn in list(globals().items()):
@@@SM@@@ SHA
54e52c0dff87809c37de51ca0f32c14258523655455e47381e59b349ac063b62 config.yaml
30cbaef75d91d789805a7b66cab32187aa370fcd70ec49d99d4d33c21e4b39ad haberbot/app.py
2d0562417932a0ab544387b5f15eaa3fa3252ce48754ce79210c028574a48674 haberbot/prompts.py
6c0a096e1674de866f9736970ab29448d7c04475c65b20b50f4e4787e46241d1 haberbot/sources.py
bf1622f5bb8910199c9eccc22f31110b2acff6657a9c79fc3698b31e6d0b584d templates/archive.html
ab1f92234b70e88e0f0f4ef16e5ad8c25c3c7fdc4d9f14c6e3be402b31d45f13 templates/category.html
e6dbcc3c7a5a225d3971b3bba5f7106f2aff5122605e9814be2f9fea61fe02ad templates/index.html
7ae2659939fd757d043c91bde2d4b7cf346d49305b4b285f610b0143ae8a2ff6 templates/tag.html
583a41545a50fd367121fafe5099901b260f123a15e321a8bbaa1695b97bbc1a tests/test_editor.py
