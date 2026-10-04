SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -52,7 +52,6 @@
   min_importance: 7              # 1-10. Haber masasının aday eşiği
   min_must_read: 8               # 1-10. Yayın yönetmeninin yeni haber eşiği
-  daily_target: 20               # Günde yaklaşık kaç yeni haber; aşılınca yalnızca çok büyük (önem ≥ 9) haberler gelir
   max_per_company_per_day: 0     # Aynı şirketten 24 saatte en fazla kaç haber (0 = sınır yok)
-  max_drafts_per_run: 2          # Bir taramada en fazla kaç yeni haber taslağı yazılsın (haberler tek tek, düzenli gelsin)
+  max_drafts_per_run: 3          # Bir taramada aynı anda yazılan taslak (fazlası kaybolmaz, bir sonraki taramada gelir)
   max_drafts_per_day: 0          # Günlük üst sınır (0 = sınır yok)
   burst: 2                       # Günlük sınır varsa: günün başında sınırın önüne geçebilecek taslak sayısı
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -388,11 +388,9 @@
                           "headlines": [f"{it['credit']}: {it['title']}" for it in q["items"]]})
         now_l = local(now_utc(), cfg.tz)
-        today_n = self.store.count(self.today(), "drafts")
-        target = self._daily_target()
         raw = None
         try:
             out = self.llm.json(cfg.get("ai", "editor_model", None) or cfg.get("ai", "writer_model", "gemini-flash-latest"),
                                 edit_system(self.brand, min_score),
-                                edit_user(now_l.strftime("%Y-%m-%d %H:%M"), slots, today_n, target, covered[:90], cands),
+                                edit_user(now_l.strftime("%Y-%m-%d %H:%M"), slots, covered[:90], cands),
                                 EDIT_SCHEMA, max_tokens=6000)
             raw = {str(x.get("cid")): x for x in (out.get("decisions") or []) if isinstance(x, dict)}
@@ -418,19 +416,9 @@
         return self._guard(queue, decisions, slots, min_score, covered)
 
-    def _daily_target(self) -> int:
-        """Günlük yeni haber hedefi: aşılınca yalnızca çok büyük (önem ≥ 9) haberler yazılır."""
-        ed = lambda k, d: self.cfg.get("editorial", k, d)  # noqa: E731
-        return int(ed("max_drafts_per_day", 0) or 0) or int(ed("daily_target", 20) or 0) or 10 ** 6
-
     def _guard(self, queue: list[dict], decisions: dict[int, dict], slots: int, min_score: int,
                covered: list[dict]) -> dict[int, dict]:
-        """Yönetmen kararlarına kurallı emniyet: eşik, tur başına yer, aynı habere tek güncelleme, günlük hedef,
-        (isteğe bağlı) şirket sınırı."""
+        """Yönetmen kararlarına kurallı emniyet: eşik, tur başına yer, aynı habere tek güncelleme, (isteğe bağlı) şirket
+        sınırı. Günlük adet sınırı yoktur: eşiği geçen her haber gelir, geçemeyen gelmez."""
         cap = int(self.cfg.get("editorial", "max_per_company_per_day", 0) or 0)   # 0 = sınır yok
-        today_n, target = self.store.count(self.today(), "drafts"), self._daily_target()
-        # Kuraklık kuralı: gündüz 3 saattir hiç haber gelmediyse, eşiğin bir altındaki en iyi aday da yazılır
-        # (seçicilik sürer ama akış tamamen durmaz)
-        last = self.state.get("last_draft_at")
-        drought = not self.quiet() and (last is None or hours_since(last) >= 3) and today_n < target
         day_keys: dict[str, int] = {}
         for c in covered:
@@ -462,7 +450,4 @@
                         round_targets.add(x["target"])
                     continue
-            if (drought and x["action"] in ("skip", "hold") and not x.get("target") and mr >= min_score - 1
-                    and (s.get("duplicate_of") or "").removeprefix("s:") not in published):
-                x["action"] = "publish"          # kuraklık: eşiğin bir altındaki en iyi aday yazılabilir
             if x["action"] != "publish":
                 continue
@@ -474,12 +459,6 @@
                     round_targets.add(dup)
                 continue
-            if mr < min_score and drought and mr >= min_score - 1 and used == 0 and x["action"] == "publish":
-                used += 1
-                drought = False
-                x["reason"] = (x.get("reason") or "") + " (uzun süredir haber yoktu)"
-            elif mr < min_score:
+            if mr < min_score:
                 x["action"], x["reason"] = "skip", f"önem {mr}/10, eşik {min_score}"
-            elif mr < 9 and today_n + used >= target:
-                x["action"], x["reason"] = "skip", f"günlük hedef ({target}) doldu; yalnızca çok büyük haberler"
             elif cap and mr < 9 and any(day_keys.get(k, 0) >= cap for k in keys):
                 x["action"], x["reason"] = "skip", "aynı şirketten son 24 saatte haber var"
@@ -716,5 +695,4 @@
             self._image_feedback(d["image"])
         st.bump(self.today(), "drafts")
-        self.state["last_draft_at"] = iso(now_utc())
         decision, reason = policy.decide(cfg, self.state, self.stats, d)
         d["policy_reason"] = reason
@@ -1555,5 +1533,4 @@
         cfg = self.cfg
         min_score = int(cfg.get("editorial", "min_must_read", 8))
-        keep_max = int(cfg.get("editorial", "daily_target", 20) or 20)
         covered = [c for c in self._covered(48) if c["status"] != "pending"]
         scores: dict[str, tuple[str, int, str]] = {}
@@ -1566,6 +1543,5 @@
                 out = self.llm.json(cfg.get("ai", "editor_model", None) or cfg.get("ai", "writer_model", "gemini-flash-latest"),
                                     edit_system(self.brand, min_score),
-                                    edit_user(local(now_utc(), cfg.tz).strftime("%Y-%m-%d %H:%M"), keep_max, 0, keep_max,
-                                              covered[:90], cands), EDIT_SCHEMA, max_tokens=8000)
+                                    edit_user(local(now_utc(), cfg.tz).strftime("%Y-%m-%d %H:%M"), len(chunk), covered[:90], cands), EDIT_SCHEMA, max_tokens=8000)
             except LLMError as e:
                 log.warning("Bekleyen taslaklar yeniden seçilemedi (sonra denenecek): %s", str(e)[:160])
@@ -1581,5 +1557,5 @@
         good = sorted((d for d in pend if d["id"] in scores and scores[d["id"]][0] in ("publish", "hold")
                        and scores[d["id"]][1] >= min_score), key=lambda d: -scores[d["id"]][1])
-        keep = {d["id"] for d in good[:keep_max]} | {d["id"] for d in pend if d["id"] not in scores}
+        keep = {d["id"] for d in good} | {d["id"] for d in pend if d["id"] not in scores}   # adet sınırı yok: eşiği geçen kalır
         culled = 0
         for d in pend:
@@ -1600,6 +1576,5 @@
         if culled:
             self.notify(f"🧹 <b>Seçki daraltıldı</b>\nOnay bekleyen {len(pend)} haberden geniş okura hitap etmeyen {culled} "
-                        f"tanesi elendi; {len(pend) - culled} haber onayında. Bundan sonra günde yaklaşık "
-                        f"{self._daily_target()} haber gelecek (çok büyük haberler hedefi aşabilir).", silent=True)
+                        f"tanesi elendi; {len(pend) - culled} haber onayında.", silent=True)
 
     # ── ARAMA MOTORLARI ─────────────────────────────────────
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -65,5 +65,6 @@
 Samsung, Google, Microsoft, Sony, Meta, Amazon, NVIDIA, OpenAI, Anthropic, Tesla, SpaceX, BYD, Xiaomi and Huawei flagships,
 Nintendo, Canon, Nikon, Fujifilm, Leica, DJI, Bose, Sonos, Dyson, LG, the big car makers sold in Türkiye, TOGG…). We have a
-premium, quality feel and we publish FEW stories: only what many Turkish readers would actually click and talk about. We
+premium, quality feel and we are highly selective (quality, not quantity — there is no quota): only what many Turkish
+readers would actually click and talk about. We
 never publish the same development twice. You receive a batch of NEW ITEMS fetched from RSS feeds and a list of RECENT
 STORIES (published, pending, queued, and recently rejected or expired ones).
@@ -180,6 +181,6 @@
 TURKISH AUDIENCE: ordinary people in Türkiye who like technology, not industry insiders. We cover AI, consumer tech (phones,
 computers, cameras, audio, TVs, smart home, wearables), cars/EVs, innovation, the Turkish startup ecosystem and the biggest
-names in gaming. We publish FEW stories — only what many Turkish readers would click and talk about — with a premium,
-quality feel: no very cheap or entry-level products, never two stories about the same thing. Several stories about the
+names in gaming. We are highly selective — we publish only what many Turkish readers would click and talk about — with a
+premium, quality feel: no very cheap or entry-level products, never two stories about the same thing. Several stories about the
 same company are fine when each is a distinct, newsworthy development (e.g. Apple's new iPhone and new Apple Watch).
 
@@ -208,6 +209,8 @@
 papers and AI safety studies, rumors, teasers, reviews, opinions and minor updates.
 Rules:
-- At most SLOTS "publish" decisions in this round; if more qualify, publish the strongest and "hold" the rest.
-- Respect the daily target: once PUBLISHED OR PENDING TODAY reaches it, publish only must_read ≥ 9 stories.
+- There is NO daily quota: judge every candidate only on its own merits, never by how many stories we already have
+  today. On a slow day publish very few (or none); on a big news day publish every story that truly qualifies.
+- At most SLOTS "publish" decisions in this round; if more qualify, publish the strongest and "hold" the rest (they come
+  in the next round — holding is not rejecting).
 - Duplicates among candidates (same product or event): publish at most one of them.
 - target: the covered story id for "update" (e.g. "ab12cd34ef"), the most similar covered id for a duplicate "skip", else "".
@@ -215,8 +218,6 @@
 
 
-def edit_user(now: str, slots: int, today_count: int, daily_target: int, covered: list[dict],
-              candidates: list[dict]) -> str:
-    lines = [f"NOW: {now}", f"SLOTS: {slots}",
-             f"PUBLISHED OR PENDING TODAY: {today_count} (daily target about {daily_target})", "",
+def edit_user(now: str, slots: int, covered: list[dict], candidates: list[dict]) -> str:
+    lines = [f"NOW: {now}", f"SLOTS: {slots}", "",
              "COVERED (id | status | age | category | entities | title):"]
     if covered:
--- a/tests/test_editor.py
+++ b/tests/test_editor.py
@@ -123,28 +123,15 @@
 
 
-def test_drought_lets_best_near_miss_through():
+def test_no_daily_quota_and_backlog_reselection():
     with _App() as (cfg, a):
-        a.quiet = lambda: False
-        queue = [_q("Notable gadget launch", 7, ["Foo"]), _q("Another one", 7, ["Bar"]), _q("Dup story", 7, ["Baz"])]
-        dec = lambda: {0: {"action": "skip", "target": "", "must_read": 7, "reason": ""},  # noqa: E731
-                       1: {"action": "hold", "target": "", "must_read": 7, "reason": ""},
-                       2: {"action": "skip", "target": "p01", "must_read": 7, "reason": ""}}
-        a.state["last_draft_at"] = iso(now_utc())                    # az önce haber geldi: kural devrede değil
-        out = a._guard(queue, dec(), slots=2, min_score=8, covered=a._covered(48))
-        assert [out[i]["action"] for i in range(3)] == ["skip", "hold", "skip"]
-        a.state["last_draft_at"] = iso(now_utc() - timedelta(hours=4))  # 4 saattir haber yok
-        out = a._guard(queue, dec(), slots=2, min_score=8, covered=a._covered(48))
-        assert sum(out[i]["action"] == "publish" for i in range(3)) == 1 and out[2]["action"] == "skip"
-
-
-def test_daily_target_and_backlog_reselection():
-    with _App() as (cfg, a):
-        cfg.raw.setdefault("editorial", {})["daily_target"] = 2
-        a.store.bump(a.today(), "drafts", 2)                               # bugün hedef doldu
-        queue = [_q("Starship reaches orbit", 9, ["SpaceX"]), _q("New Sony camera", 8, ["Sony"])]
+        a.store.bump(a.today(), "drafts", 40)                              # bugün çok haber geldi: adet sınırı yok
+        queue = [_q("Starship reaches orbit", 9, ["SpaceX"]), _q("New Sony camera", 8, ["Sony"]),
+                 _q("Minor app update", 7, ["Foo"]), _q("Big launch", 8, ["Bar"])]
         dec = {i: {"action": "publish", "target": "", "must_read": q["story"]["importance"], "reason": ""}
                for i, q in enumerate(queue)}
-        out = a._guard(queue, dec, slots=3, min_score=8, covered=a._covered(48))
-        assert out[0]["action"] == "publish" and out[1]["action"] == "skip" and "hedef" in out[1]["reason"]
+        out = a._guard(queue, dec, slots=2, min_score=8, covered=a._covered(48))
+        assert out[0]["action"] == "publish" and out[1]["action"] == "publish"   # eşiği geçen gelir
+        assert out[2]["action"] == "skip"                                         # eşiğin altı gelmez
+        assert out[3]["action"] == "hold"                                         # turda yer yoksa sonraki tura kalır
         # onay bekleyen yığın yeni ölçütlerle bir kez elden geçer
         for i in range(8):
@@ -154,10 +141,10 @@
         a.reselect_pending()
         left = a.store.drafts("pending")
-        assert len(left) == 2 and all(d["importance"] == 9 for d in left)   # en iyiler (hedef kadar) kalır
-        assert a.state["reselect_v"] and a.store.count(a.today(), "culled") == 6
+        assert len(left) == 3 and all(d["importance"] == 9 for d in left)   # eşiği geçenlerin hepsi kalır
+        assert a.state["reselect_v"] and a.store.count(a.today(), "culled") == 5
         outbox = (cfg.data_dir / "_mock" / "outbox.jsonl").read_text(encoding="utf-8")
         assert "SEÇKİ DIŞI" in outbox and "Seçki daraltıldı" in outbox
         a.reselect_pending()                                               # ikinci kez çalışmaz
-        assert len(a.store.drafts("pending")) == 2
+        assert len(a.store.drafts("pending")) == 3
 
 
@@@SM@@@ SHA
217db0238f27e96b380f1020f7d4ee639800ba05d804371fe42aac4ebbe7c89e config.yaml
1ab1d83bcf2e6071cf7b3b6d8a7924534a0326ec26942f5da5e07c1d2cceb70d haberbot/app.py
a8301e48b98005e3af336f2379a62a16215e1801f75a59b4fb01e2b84bde5f34 haberbot/prompts.py
7c3486a64243b8df7594dcc43cfe6603637e9ee2c64807501a4b6c2491438acd tests/test_editor.py
