SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -53,4 +53,5 @@
 ]
 COMMANDS_VERSION = 4
+COVERLINE_V = 2               # kapak başlığı yazım kuralları değişince eski haberlerin kapak başlıkları yeniden yazılır
 KEYBOARD_VERSION = 4          # yayındaki haber mesajlarının düğmeleri bu sürüme göre bir kez yenilenir
 HELP = """<b>Nasıl çalışır?</b>
@@ -553,5 +554,6 @@
         if not self.llm:
             return
-        todo = [p for p in self.store.posts() if not p.get("cover_headline") and not p.get("cover_line_skip")][:batch]
+        todo = [p for p in self.store.posts()
+                if p.get("cover_line_v") != COVERLINE_V and not p.get("cover_line_skip")][:batch]
         if not todo:
             return
@@ -567,6 +569,10 @@
             line = self._cover_line((got.get(p["id"]) or {}).get("cover_headline"), (got.get(p["id"]) or {}).get("cover_highlight"))
             if line:
+                changed = line.get("cover_headline") != p.get("cover_headline")
                 p.update(line)
+                p["cover_line_v"] = COVERLINE_V
                 self.fixer.post(p)
+                if changed and p.get("image"):
+                    p["image"]["cover_v"] = 0          # kapak yeni başlıkla yeniden üretilsin
                 n += 1
             else:
@@ -580,5 +586,5 @@
     def _cover_ready(p: dict) -> bool:
         """Kapak yenilemesi için kapak başlığı hazır mı (ya da artık beklenmiyor mu)."""
-        return bool(p.get("cover_headline") or p.get("cover_line_skip"))
+        return bool((p.get("cover_headline") and p.get("cover_line_v") == COVERLINE_V) or p.get("cover_line_skip"))
 
     def _write(self, sources: list[dict], previous: dict | None = None, instruction: str | None = None) -> dict:
@@ -616,4 +622,6 @@
             **self._cover_line(out.get("cover_headline"), out.get("cover_highlight")),
         }
+        if res.get("cover_headline"):
+            res["cover_line_v"] = COVERLINE_V
         self.fixer.post(res)          # Türkçe karakter ve marka yazımı düzeltmeleri
         return res
@@ -678,5 +686,5 @@
     UPDATE_FIELDS = ("title", "summary", "body", "tags", "short_title", "kicker", "hero_stat", "hero_stat_label",
                      "focus_keyword", "seo_title", "meta_description", "image_alt", "cover_text", "carousel_points",
-                     "cover_headline", "cover_highlight", "confidence", "flags", "editor_note")
+                     "cover_headline", "cover_highlight", "cover_line_v", "confidence", "flags", "editor_note")
 
     def create_update(self, post: dict, story: dict, its: list[dict]) -> dict | None:
@@ -1252,5 +1260,5 @@
             text = visual_only.strip()
             if text and len(text) <= 56:   # kısa ifade: kapak başlığı olsun (fotoğraflı kapakta da)
-                d["cover_headline"], d["cover_highlight"] = text, ""
+                d["cover_headline"], d["cover_highlight"], d["cover_line_v"] = text, "", COVERLINE_V
                 d["cover_variant"] = int(d.get("cover_variant", 0)) + 1
             elif text:                      # uzun ifade: yapay zeka görseli sahnesi
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -288,9 +288,12 @@
 a scrolling reader stop and want to read — the cover is our headline):
 - cover_headline: a hook of 3–7 words, ≤42 characters, in Turkish, that makes sense on its own without the title: the key
-  name (company/product/game/car) or the key number plus what is new or surprising. Factual and grounded in the sources;
-  no question marks, no exclamation marks, no ellipsis, no emojis, no clickbait teasing ("şok", "inanılmaz", "herkes
-  bunu konuşuyor"). Word it differently from the title; sentence case. Never just a name or just a number.
-  Examples of the style (do not reuse): "Starship ilk kez yörüngede", "TikTok'ta gençlere 2 saat sınırı",
-  "Apple'a 5,7 milyar dolar ceza", "Honor'dan 11.000 mAh'lik pil", "OpenAI en güçlü modelini durdurdu".
+  name (company/product/game/car) plus the single most striking concrete fact — the number, the first-ever, the standout
+  feature, the consequence — not a shortened copy of the title and not a bare "X tanıtıldı / duyurdu / açıklandı".
+  Keep the certainty of the sources: if something may happen, is claimed or rumoured, the hook says so ("… gelebilir",
+  "… iddiası"). Factual; no question marks, no exclamation marks, no ellipsis, no emojis, no clickbait teasing ("şok",
+  "inanılmaz", "herkes bunu konuşuyor"). Sentence case. Never just a name or just a number.
+  Weak → strong (style only, do not reuse): "Honor Watch 6 Pro tanıtıldı" → "Honor'un yeni saati 35 gün dayanıyor";
+  "ElevenLabs v4 tanıtıldı" → "ElevenLabs sesi 90 dilde konuşturuyor"; "Starship yörüngeye ulaştı" → "Starship ilk kez
+  yörüngede"; "TikTok yeni kural getirdi" → "TikTok'ta gençlere 2 saat sınırı".
 - cover_highlight: 1–3 consecutive words copied exactly from cover_headline that carry the punch (the number, the key
   name or the twist); they are coloured on the cover.
@@ -422,9 +425,13 @@
 For each story write:
 - cover_headline: a hook of 3–7 words, ≤42 characters, in Turkish, that makes sense on its own: the key name
-  (company/product/game/car) or the key number plus what is new or surprising. Use only facts in the given title and
-  summary. No question marks, no exclamation marks, no ellipsis, no emojis, no clickbait teasing. Word it differently from
-  the title; sentence case; correct Turkish characters; keep brand spellings (iPhone, eFootball). Never just a name or just
-  a number. Style examples (do not reuse): "Starship ilk kez yörüngede", "TikTok'ta gençlere 2 saat sınırı",
-  "Apple'a 5,7 milyar dolar ceza", "Honor'dan 11.000 mAh'lik pil".
+  (company/product/game/car) plus the single most striking concrete fact from the title or summary — the number, the
+  first-ever, the standout feature, the consequence — not a shortened copy of the title and not a bare "X tanıtıldı /
+  duyurdu / açıklandı". Use only facts in the given title and summary and keep their certainty: if something may happen,
+  is claimed or rumoured, the hook says so ("… gelebilir", "… iddiası"). No question marks, no exclamation marks, no
+  ellipsis, no emojis, no clickbait teasing. Sentence case; correct Turkish characters; keep brand spellings (iPhone,
+  eFootball). Never just a name or just a number.
+  Weak → strong (style only, do not reuse): "Honor Watch 6 Pro tanıtıldı" → "Honor'un yeni saati 35 gün dayanıyor";
+  "ElevenLabs v4 tanıtıldı" → "ElevenLabs sesi 90 dilde konuşturuyor"; "Starship yörüngeye ulaştı" → "Starship ilk kez
+  yörüngede"; "TikTok yeni kural getirdi" → "TikTok'ta gençlere 2 saat sınırı".
 - cover_highlight: 1–3 consecutive words copied exactly from cover_headline that carry the punch.
 Return one line per id."""
@@ -432,3 +439,4 @@
 
 def coverline_user(posts: list[dict]) -> str:
-    return "\n".join(f"{p['id']} | {p.get('title', '')} | {p.get('summary', '')}" for p in posts)
+    return "\n".join(f"{p['id']} | {p.get('title', '')} | {p.get('summary', '')} "
+                     f"{' '.join((p.get('carousel_points') or [])[:3])}".rstrip() for p in posts)
@@@SM@@@ SHA
6b642f04fb0c448e2cb2bd99005a20c3d1eb04b20d0723dd09a7f1b40b0ce98d haberbot/app.py
dc572a29b55090718492593efa9593cbe41c57091d55d4883ebec69b538c9a3f haberbot/prompts.py
