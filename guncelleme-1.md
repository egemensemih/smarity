SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -78,4 +78,6 @@
   max_drafts_per_run: 3          # Bir taramada aynı anda yazılan taslak (fazlası kaybolmaz, bir sonraki taramada gelir)
   max_drafts_per_day: 10         # Günlük üst sınır (Kasım 2026: az ama dolu haber; Google çekirdek güncellemesi sonrası)
+  big_news_extra: 3              # Sınır dolsa da yayımlanan büyük haber sayısı (önem 9+, ya da herkesin bildiği bir markada 8+;
+                                 # ör. Apple'ın sürpriz yeni ürünü). Diğer haberler sırada bekler.
   burst: 2                       # Günlük sınır varsa: günün başında sınırın önüne geçebilecek taslak sayısı
   triage_batch: 100              # Bir turda ayıklanan en fazla öğe (fazlası sonraki tura kalır, kaybolmaz)
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -177,4 +177,23 @@
         return max(0, min(cap - used, allowed - used))
 
+    def big_extra_left(self) -> int:
+        """Günlük sınır (ya da günün o saatine düşen pay) dolduğunda bile yayımlanabilecek büyük haber sayısı."""
+        n = int(self.cfg.get("editorial", "big_news_extra", 0) or 0)
+        if n <= 0 or int(self.cfg.get("editorial", "max_drafts_per_day", 0) or 0) <= 0:
+            return 0
+        b = self.state.get("big_extra") or {}
+        return max(0, n - (int(b.get("n", 0)) if b.get("date") == self.today() else 0))
+
+    def _use_big_extra(self) -> None:
+        b = self.state.get("big_extra") or {}
+        n = int(b.get("n", 0)) if b.get("date") == self.today() else 0
+        self.state["big_extra"] = {"date": self.today(), "n": n + 1}
+
+    @staticmethod
+    def is_big_news(x: dict) -> bool:
+        """Sınırı beklemeyen haber: günün öne çıkan haberi (9+) ya da herkesin bildiği bir markanın yeni ürünü/hamlesi (8+)."""
+        mr = int(x.get("must_read") or 0)
+        return mr >= 9 or (mr >= 8 and bool(x.get("big_brand")))
+
     def notify(self, text: str, silent: bool | None = None, keyboard=None) -> None:
         if not (self.tg and self.chat_id):
@@ -209,10 +228,15 @@
         today = self.today()
         remaining = self.draft_budget()
+        big_only = False
         if remaining <= 0:
-            # Haberler "görüldü" sayılmaz; sıra gelince (en geç ertesi sabah) değerlendirilir.
-            self.state["last_collect"] = iso(now_utc())
-            log.info("Taslak sırası dolu (bugün %d taslak); yeni haberler sonraki turda değerlendirilecek.",
-                     st.count(today, "drafts"))
-            return
+            extra = self.big_extra_left()
+            if extra <= 0:
+                # Haberler "görüldü" sayılmaz; sıra gelince (en geç ertesi sabah) değerlendirilir.
+                self.state["last_collect"] = iso(now_utc())
+                log.info("Taslak sırası dolu (bugün %d taslak); yeni haberler sonraki turda değerlendirilecek.",
+                         st.count(today, "drafts"))
+                return
+            # sınır dolu ama büyük haber kaçmasın: tarama sürer, yalnızca büyük haberler yazılır, diğerleri sırada bekler
+            big_only, remaining = True, extra
         items = fetch_all(cfg, st)
         seeded = set(self.state.get("seeded_sources", []))
@@ -336,4 +360,12 @@
             q["story"]["editor_reason"] = x.get("reason", "")
             act = x["action"]
+            if big_only and act == "publish" and not self.is_big_news(x):
+                # günlük sınır dolu: büyük haber değil, sıra açılınca yazılır (bekleme sayısı artmaz)
+                x["action"], x["reason"] = "hold", clip("günlük sınır dolu, sıra bekliyor" +
+                                                        (f": {x['reason']}" if x.get("reason") else ""), 120)
+                q["held_at"] = iso(now_utc())
+                keep.append(q)
+                self._edit_log(q, "hold", x)
+                continue
             if act == "publish":
                 todo.append(q)
@@ -359,4 +391,7 @@
             try:
                 self.create_draft(q["story"], q["items"])
+                if big_only:
+                    self._use_big_extra()
+                    log.info("Günlük sınır dolu, büyük haber yine de yazıldı: %s", clip(q["story"].get("topic", ""), 80))
             except LLMError as e:
                 if self._transient(e):
--- a/tests/test_editor.py
+++ b/tests/test_editor.py
@@ -76,4 +76,40 @@
         assert rel and rel[0]["title"] == "Togg T10F satışa çıktı"
         assert all("Apple" not in r["title"] for r in rel)
+
+
+def test_big_news_passes_full_daily_cap(monkeypatch):
+    """Günlük sınır dolu: Apple'ın sürpriz ürünü yine de yazılır; sıradan haber sırada bekler."""
+    import haberbot.app as appmod
+    with _App() as (cfg, a):
+        ed = cfg.raw.setdefault("editorial", {})
+        ed.update({"max_drafts_per_day": 10, "big_news_extra": 1, "min_outlets": 0})
+        a.store.bump(a.today(), "drafts", 10)
+        assert a.draft_budget() == 0 and a.big_extra_left() == 1
+
+        def item(i, title):
+            return {"key": f"k{i}", "url": f"https://k.com/{i}", "title": title, "kind": "media", "source": "Kaynak",
+                    "credit": "Kaynak", "summary": "", "published": iso(now_utc()), "html_source": False}
+        items = [item(1, "Apple surprise launches new iPad"), item(2, "Minor brand launches cable")]
+        a.state["seeded_sources"] = ["Kaynak"]
+        monkeypatch.setattr(appmod, "fetch_all", lambda *_: items)
+
+        class LLM:
+            def json(self, *_a, **_k):
+                return {"stories": [
+                    {"item_ids": ["i1"], "topic": "Apple new iPad", "importance": 8, "entities": ["Apple"],
+                     "category": "teknoloji", "on_topic": True, "duplicate_of": ""},
+                    {"item_ids": ["i2"], "topic": "Cable launch", "importance": 8, "entities": ["Foo"],
+                     "category": "teknoloji", "on_topic": True, "duplicate_of": ""}]}
+        a.llm = LLM()
+        monkeypatch.setattr(a, "_edit", lambda queue, slots: {
+            i: {"action": "publish", "target": "", "must_read": 8, "reason": "",
+                "big_brand": "Apple" in q["story"]["topic"]} for i, q in enumerate(queue)})
+        made = []
+        monkeypatch.setattr(a, "create_draft", lambda story, its: made.append(story["topic"]))
+        a.collect()
+        assert made == ["Apple new iPad"]
+        assert [q["story"]["topic"] for q in a.state["queue"]] == ["Cable launch"]   # kaybolmaz, sıra bekler
+        assert a.big_extra_left() == 0
+        assert a.is_big_news({"must_read": 9}) and not a.is_big_news({"must_read": 8})
 
 
@@@SM@@@ SHA
c2d83cd962fa3d880feb9e9df256c3d2707496f2c523d33d6429df873dcd2afb config.yaml
882be37e34b01e8570d9a59e6479f50f3cbeb3ec3af33423768722d328f6d7de haberbot/app.py
48172c60fe9f571f0f46ebcf36024bca7d1dcdb1fe735cbde0a72392c882af63 tests/test_editor.py
