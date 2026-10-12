SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -73,11 +73,10 @@
   global_min_approval: 0.85      # Son kararlarda genel onay oranı bunun altındaysa otomatik yayın durur
   auto_min_importance: 7         # Otomatik yayın için en düşük önem puanı
-  # Doğrudan yayınlanan gruplar: geçmiş kararlarında en çok onayladığın türler. Uyarı işareti olan haber yine sorulur.
+  # Doğrudan yayın (tüm kategoriler): yönetmenin seçtiği haberlerden en az 3 farklı kaynakta çıkanlar onay beklemez.
+  # Uyarı işareti olan haber yine sorulur.
   trusted_groups:
-    - name: "en az 2 kaynaklı otomotiv / süper zeka haberi"
-      categories: [otomotiv, super-zeka]
-      min_sources: 2
     - name: "en az 3 farklı kaynakta çıkan haber"
       min_sources: 3
+  auto_broad_importance: 8       # Puanı bunun altında (küçük kitle) VE büyük bir markaya ait olmayan haber yine sorulur
   # Bu markaların haberleri hiçbir zaman otomatik yayınlanmaz, her zaman onaya gelir
   never_auto: [Vivo, Oppo, Realme, Tecno, Infinix, iQOO, Nubia, ZTE, Meizu, itel, Poco, Redmi]
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -313,4 +313,5 @@
             x = decisions.get(i) or {"action": "hold", "target": "", "must_read": 0, "reason": ""}
             q["story"]["must_read"] = int(x.get("must_read") or 0)
+            q["story"]["big_brand"] = bool(x.get("big_brand"))
             q["story"]["editor_reason"] = x.get("reason", "")
             act = x["action"]
@@ -423,4 +424,5 @@
             x["target"] = (x.get("target") or "").strip().removeprefix("s:")
             x["reason"] = clip(str(x.get("reason") or ""), 120)
+            x["big_brand"] = x.get("big_brand") is True
             if x.get("action") not in ("publish", "update", "skip", "hold"):
                 x["action"] = "hold"
@@ -739,4 +741,5 @@
             "category": w["category"] or story.get("category") or DEFAULT_CATEGORY,
             "importance": int(story.get("must_read") or story.get("importance", 5)),
+            "big_brand": bool(story.get("big_brand")),
             "triage_reason": story.get("editor_reason") or story.get("reason", ""),
             "entities": list(story.get("entities") or []),
@@ -795,4 +798,5 @@
             "category": post.get("category") or w["category"] or DEFAULT_CATEGORY,
             "importance": int(story.get("must_read") or story.get("importance", 5)),
+            "big_brand": bool(story.get("big_brand")),
             "triage_reason": story.get("editor_reason") or story.get("reason", ""),
             "entities": list(story.get("entities") or post.get("entities") or []),
--- a/haberbot/policy.py
+++ b/haberbot/policy.py
@@ -7,6 +7,7 @@
   Bir kaynak güvenilir sayılır: en az X karar + en az %Y onay.
   Otomatik yayınlanan bir haberi 'Kaldır' dersen o kaynak 2 ret puanı alır.
-  Güvenilir gruplar (ayarlarda autonomy.trusted_groups): en çok onayladığın türler (ör. en az 2 kaynaklı otomotiv ve
-  süper zeka haberleri) uyarı işareti yoksa doğrudan yayınlanır. Bir gruptan son 7 günde otomatik yayınlanan haberleri
+  Güvenilir gruplar (ayarlarda autonomy.trusted_groups): yönetmenin seçtiği haberlerden çok kaynakta çıkanlar (tüm
+  kategorilerde en az 3 farklı kaynak) uyarı işareti yoksa doğrudan yayınlanır. Küçük kitleye hitap eden (yönetmen puanı
+  8'in altında) ve büyük bir markaya ait olmayan haber yine sorulur; never_auto listesindeki markalar hep sorulur. Bir gruptan son 7 günde otomatik yayınlanan haberleri
   birkaç kez kaldırırsan o grup kendiliğinden yeniden onayına döner.
 """
@@ -92,4 +93,7 @@
     if group and never_auto_brand(cfg, draft):
         group = None                                   # bu marka her zaman onaya gelir
+    broad = int(cfg.get("autonomy", "auto_broad_importance", 0) or 0)
+    if group and draft.get("importance", 0) < broad and not draft.get("big_brand"):
+        group = None                                   # küçük kitleye hitap ediyor ve büyük bir marka değil: sorulur
     if (group and draft.get("confidence") in ("yuksek", "orta")
             and draft.get("importance", 0) >= cfg.get("autonomy", "auto_min_importance", 6)):
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -165,7 +165,8 @@
                     "target": {"type": "string"},
                     "must_read": {"type": "integer"},
+                    "big_brand": {"type": "boolean"},
                     "reason": {"type": "string"},
                 },
-                "required": ["cid", "action", "target", "must_read", "reason"],
+                "required": ["cid", "action", "target", "must_read", "big_brand", "reason"],
                 "additionalProperties": False,
             },
@@ -222,4 +223,8 @@
 - Duplicates among candidates (same product or event): publish at most one of them.
 - target: the covered story id for "update" (e.g. "ab12cd34ef"), the most similar covered id for a duplicate "skip", else "".
+- big_brand: true if the story is about a household-name company, brand, product or service that most people in Türkiye
+  know (Apple, Samsung, Google, Microsoft, Meta, WhatsApp, Instagram, YouTube, OpenAI/ChatGPT, NVIDIA, Tesla, BYD, Togg,
+  big car makers, Sony/PlayStation, Xbox, Nintendo, GTA, Netflix, Spotify, Turkcell, Türk Telekom, Trendyol…); false for
+  lesser-known or mid-tier brands (Vivo, Oppo, Realme, Tecno, Infinix, small startups, niche gadget makers).
 - reason: ≤12 words in Turkish."""
 
--- a/tests/test_core.py
+++ b/tests/test_core.py
@@ -63,5 +63,5 @@
                                                        "min_sources": 2},
                                                       {"name": "3 kaynak", "min_sources": 3}],
-                                   "never_auto": ["Vivo", "Oppo", "iQOO"]}})
+                                   "never_auto": ["Vivo", "Oppo", "iQOO"], "auto_broad_importance": 8}})
     stats = {"sources": {}, "decisions": [{"ok": False, "manual": True}] * 30}
     three = [{"name": n, "url": n} for n in ("Webtekno", "LOG", "The Verge")]
@@ -76,4 +76,8 @@
     assert policy.decide(cfg, {}, stats, {**phone, "title": "Vivos adlı yeni uygulama çıktı"})[0] == "auto"
     assert policy.decide(cfg, {}, stats, {**vivo, "category": "otomotiv"})[0] == "ask"
+    # küçük kitle (puan 7) + büyük marka değil → sor; büyük markaysa yayınla
+    assert policy.decide(cfg, {}, stats, {**phone, "importance": 7, "title": "Nothing CMF hoparlör tanıttı"})[0] == "ask"
+    assert policy.decide(cfg, {}, stats, {**phone, "importance": 7, "big_brand": True})[0] == "auto"
+    assert policy.decide(cfg, {}, stats, {**phone, "importance": 7, "big_brand": True, "title": "Oppo Find X10"})[0] == "ask"
 
 
@@@SM@@@ SHA
e7ad186f9d8af0fb8c61f2e01ff98cd272771bebdf1f722cb18597aca8715da8 config.yaml
6cb10a8c362c33cae045bcd41ba924234ae44c5814372a5affd08eba2f073eb7 haberbot/app.py
dea3ec5ad46765ae06b6ffd0d96795b495cb00f5937501ffbe4f77f57848ed31 haberbot/policy.py
9a947e6a8b1e85245de7ccd4c4a7eb6a4dc4a84689a96fbec169fb711eee1abe haberbot/prompts.py
e704adf5a34f4d0439e133fcc05312c246e709db4653dd39d2f6bd800784bcdb tests/test_core.py
