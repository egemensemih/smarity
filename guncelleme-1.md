SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -51,5 +51,5 @@
   # haberleri, yalnızca yurtdışını ilgilendiren araç/fiyat haberleri, B2B, araştırma, söylenti vb. elenir.
   min_importance: 7              # 1-10. Haber masasının aday eşiği
-  min_must_read: 8               # 1-10. Yayın yönetmeninin yeni haber eşiği
+  min_must_read: 7               # 1-10. Yayın yönetmeninin yeni haber eşiği (7: sağlam ve yayına değer, 8: geniş kitle için önemli)
   max_per_company_per_day: 0     # Aynı şirketten 24 saatte en fazla kaç haber (0 = sınır yok)
   max_drafts_per_run: 3          # Bir taramada aynı anda yazılan taslak (fazlası kaybolmaz, bir sonraki taramada gelir)
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -402,5 +402,5 @@
             imp = int(q["story"].get("importance", 0))
             if raw is None:   # yedek: masanın puanı, yönetmen eşiğiyle
-                x = {"action": "publish" if imp >= min_score else "hold", "target": "", "must_read": imp,
+                x = {"action": "publish" if imp >= max(8, min_score) else "hold", "target": "", "must_read": imp,
                      "reason": "masa puanı"}
             else:
@@ -444,5 +444,5 @@
                     x["action"], x["target"] = ("update", dup) if dup in published else ("publish", "")
                 if x["action"] == "update":
-                    if mr < min_score - 1:
+                    if mr < max(7, min_score - 1):
                         x["action"], x["reason"] = "skip", x["reason"] or "yeni gelişme yeterince önemli değil"
                     elif x["target"] in round_targets or (x["target"] in refreshed and mr < 9):
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -187,5 +187,5 @@
 You receive COVERED stories (what we already published, what is waiting for approval, and what the editor rejected) and
 CANDIDATES proposed by the news desk. Decide for EVERY candidate:
-- "publish": a new must-know story for a broad Turkish audience. Allowed only if must_read ≥ {min_score}.
+- "publish": a new story worth a broad Turkish audience's time. Allowed only if must_read ≥ {min_score}.
 - "update": the candidate is the same story or a direct follow-up of a PUBLISHED covered story AND it brings a substantial
   new development (official confirmation, a regulator or court acting, price/date/availability announced for the first
@@ -200,6 +200,12 @@
 premium brand people in Türkiye can buy; a new car model sold in Türkiye or an iconic one; an AI feature many people will
 use; Turkish tech news that touches everyday life — TOGG, BTK/BDDK/KVKK rules, operators, phone prices and taxes —; the
-Turkish startup ecosystem's notable rounds, exits and founders); 7 noteworthy (credible detailed leaks about a hugely
-anticipated flagship, a flagship's Türkiye price); ≤6 routine — in particular: foreign startups' funding rounds and
+Turkish startup ecosystem's notable rounds, exits and founders; major corporate moves of household-name tech companies —
+a merger, a rename, a new CEO, big layoffs at Apple, Google, Meta, Microsoft, OpenAI, xAI, Tesla…); 7 solid and worth
+publishing (a notable launch or refresh from a well-known brand sold in Türkiye — a new Kindle, AirPods, Galaxy Watch,
+mid-tier phones from big brands —; a new feature in an app or service many Turks use daily — WhatsApp, Instagram,
+YouTube, Netflix, Spotify, Google Maps, iOS, Android —; credible, detailed reports about upcoming launches or events of
+household brands — Mark Gurman, Bloomberg, certification filings, official teasers, e.g. the date of Apple's next event —;
+a flagship's Türkiye price; Turkish tech data and reports such as TÜİK or BTK figures; a smaller Turkish startup round
+with a clear, interesting idea); ≤6 routine — in particular: foreign startups' funding rounds and
 acquisitions (unless a household name and a huge deal), games outside the biggest franchises (GTA, Call of Duty, EA Sports
 FC, Minecraft, Fortnite, Pokémon, Mario, Zelda, The Witcher, Elden Ring, Counter-Strike, Valorant, LoL…) and console
@@ -207,5 +213,6 @@
 or tax matters, trucks and fleet orders, trims, concepts), local news from other countries, B2B/enterprise (data centres,
 supercomputers, chip supply, factories, R&D centres, partnerships), niche gadgets from little-known brands, research
-papers and AI safety studies, rumors, teasers, reviews, opinions and minor updates.
+papers and AI safety studies, thin rumors and early leaks from unknown sources (accessory or case leaks, "might" stories),
+reviews, opinions and minor updates.
 Rules:
 - There is NO daily quota: judge every candidate only on its own merits, never by how many stories we already have
@@@SM@@@ SHA
8e9276867ffd1ea13fb6120592a11975c0c3bb985efbc94c75c60f25848d2ec0 config.yaml
9eff50b7739536aa0cbc10914a5aa59c235214e0c835762f34efa369eb05145d haberbot/app.py
300b1be33cc2659b9af1f250a7d029c300c9c9f91a38a0b800e1932dc23d99a2 haberbot/prompts.py
