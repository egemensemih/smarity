SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -53,5 +53,5 @@
 ]
 COMMANDS_VERSION = 4
-COVERLINE_V = 2               # kapak başlığı yazım kuralları değişince eski haberlerin kapak başlıkları yeniden yazılır
+COVERLINE_V = 3               # kapak başlığı yazım kuralları değişince eski haberlerin kapak başlıkları yeniden yazılır
 KEYBOARD_VERSION = 4          # yayındaki haber mesajlarının düğmeleri bu sürüme göre bir kez yenilenir
 HELP = """<b>Nasıl çalışır?</b>
@@ -284,4 +284,6 @@
         queue = sorted(queue + new_stories, key=lambda q: (-int(q["story"].get("importance", 0)), q["at"]))[:24]
         slots = min(int(ed("max_drafts_per_run", 2)), remaining)
+        if fresh:
+            log.info("Ayıklama: %d aday, %d elendi, %d mevcut habere eklendi", len(new_stories), skipped, merged)
         if not new_stories and all(hours_since(q.get("held_at")) < 0.75 for q in queue):
             self.state["queue"] = queue[:30]   # yeni aday yok, bekleyenlere az önce bakıldı
@@ -308,6 +310,4 @@
         todo.sort(key=lambda q: -q["story"]["must_read"])
         self.state["queue"] = keep[:30]
-        if fresh:
-            log.info("Ayıklama: %d aday, %d elendi, %d mevcut habere eklendi", len(new_stories), skipped, merged)
         log.info("Yönetmen: %d yeni haber, %d güncelleme, %d bekliyor, %d geçildi", len(todo), len(updates), len(keep),
                  len(queue) - len(todo) - len(updates) - len(keep))
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -290,5 +290,6 @@
   name (company/product/game/car) plus the single most striking concrete fact — the number, the first-ever, the standout
   feature, the consequence — not a shortened copy of the title and not a bare "X tanıtıldı / duyurdu / açıklandı".
-  Keep the certainty of the sources: if something may happen, is claimed or rumoured, the hook says so ("… gelebilir",
+  It must be about the MAIN news of the article (what the title says happened), never a side detail; it must read as a
+  complete statement, not a fragment. Keep the certainty of the sources: if something may happen, is claimed or rumoured, the hook says so ("… gelebilir",
   "… iddiası"). Factual; no question marks, no exclamation marks, no ellipsis, no emojis, no clickbait teasing ("şok",
   "inanılmaz", "herkes bunu konuşuyor"). Sentence case. Never just a name or just a number.
@@ -427,5 +428,7 @@
   (company/product/game/car) plus the single most striking concrete fact from the title or summary — the number, the
   first-ever, the standout feature, the consequence — not a shortened copy of the title and not a bare "X tanıtıldı /
-  duyurdu / açıklandı". Use only facts in the given title and summary and keep their certainty: if something may happen,
+  duyurdu / açıklandı". It must be about the MAIN news of the title (what happened), never a side detail from the
+  summary, and it must read as a complete statement, not a fragment. Use only facts in the given title and summary and
+  keep their certainty: if something may happen,
   is claimed or rumoured, the hook says so ("… gelebilir", "… iddiası"). No question marks, no exclamation marks, no
   ellipsis, no emojis, no clickbait teasing. Sentence case; correct Turkish characters; keep brand spellings (iPhone,
@@@SM@@@ SHA
80eebd900c9ae335f22f8736c2cca33033b0ed77d603ad6dad9d429a3f32a2be haberbot/app.py
9c19b191423f463ac7cf2d88e67c7c46e02bfec9076a9da5f489ae9e0b66693b haberbot/prompts.py
