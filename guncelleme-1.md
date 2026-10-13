SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -62,4 +62,5 @@
   taste_days: 21                 # Yönetmen, son bu kadar günde reddettiğin / kaldırdığın haberlerden zevkini öğrenir
   taste_examples: 40             # ...en fazla bu kadar örnekle
+  confirmed_only: true           # Yalnızca doğrulanmış haber: söylenti, sızıntı, "iddia ediliyor" haberleri yönetmen baştan eler
   fetch_full_text: true          # Haberin tam metnini kaynağından okuyup daha doğru özet çıkar
 
@@ -70,5 +71,5 @@
   #   🟡 sorar          : küçük kitle ve büyük marka değil
   #   🔴 hep sorar      : uyarı işareti, never_auto markaları, güven 'düşük'
-  # Modlar: kural (önerilen) · manuel (her şey sorulur) · tam (yalnızca 🔴 sorulur). Telegram'dan /mod ile değiştirilir.
+  # Modlar: kural · manuel (her şey sorulur) · tam (hiçbir şey sorulmaz; 🔴 olanlar hiç yayınlanmaz). Telegram'dan /mod.
   mode: tam                      # Ekim 2026: sahibin isteğiyle tam otonom (beğenmediklerini Telegram'dan kaldırır)
   min_sources: 3                 # Otomatik yayın için gereken en az farklı kaynak (yayın kuruluşu) sayısı
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -85,5 +85,5 @@
 🔴 <b>Hep sorar</b> — uyarı işaretli (iddia, söylenti) haberler, Vivo / Oppo gibi listedeki markalar.
 Otomatik yayınlanan 2 haberi 3 gün içinde kaldırırsan otomatik yayın kendiliğinden durur; <code>/mod kural</code> ile yeniden açılır. <code>/mod manuel</code>: her şey sorulur.
-<b>Tam otonom</b> (<code>/mod tam</code>): yönetmenin seçtiği her haber yayınlanır ve sana "yayınlandı" diye gelir; yalnızca 🔴 olanlar sorulur. Beğenmediğini 🗑 <b>Kaldır</b>'la çıkar: reddettiğin ve kaldırdığın haberler yönetmene "sahibin istemediği haberler" olarak gösterilir, benzerlerini seçmez.
+<b>Tam otonom</b> (<code>/mod tam</code>): yönetmenin seçtiği her haber sorulmadan yayınlanır ve sana "yayınlandı" diye gelir. Şüpheli içerik (doğrulanmamış iddia, söylenti, çelişen kaynak, eski haber, tanıtım) ve listedeki markalar hiç yayınlanmaz; sana da sorulmaz. Beğenmediğini 🗑 <b>Kaldır</b>'la çıkar: reddettiğin ve kaldırdığın haberler yönetmene "sahibin istemediği haberler" olarak gösterilir, benzerlerini seçmez.
 
 📸 <b>Instagram</b> — yayınlanan her haber birkaç dakika içinde carousel ve hikâye olarak Instagram'da paylaşılır. Sıradaki bir haberi mesajındaki <b>Instagram'a gönderme</b> düğmesiyle durdurabilirsin. Tümünü durdurmak için <code>/instagram kapat</code>.
@@ -260,6 +260,6 @@
             for p in pub[:100] + older:
                 recent.append({"sid": "s:" + p["id"], "status": "published", "title": p["title"]})
-            for a in st.recent_archive(72):   # reddedilen / süresi dolan haberler tekrar önerilmesin
-                if a.get("status") in ("rejected", "expired", "removed"):
+            for a in st.recent_archive(72):   # reddedilen / süresi dolan / şüpheli diye düşen haberler tekrar önerilmesin
+                if a.get("status") in ("rejected", "expired", "removed", "dropped"):
                     recent.append({"sid": "s:" + a["id"], "status": a["status"], "title": a.get("title", "")})
 
@@ -384,5 +384,5 @@
                 add(d, d["status"], d.get("created_at"))
         for a in self.store.recent_archive(hours):
-            if a.get("status") in ("rejected", "expired", "removed"):
+            if a.get("status") in ("rejected", "expired", "removed", "dropped"):
                 add(a, a["status"], a.get("created_at") or a.get("closed_at"))
         out.sort(key=lambda c: c["hours"])
@@ -410,5 +410,5 @@
         try:
             out = self.llm.json(cfg.get("ai", "editor_model", None) or cfg.get("ai", "writer_model", "gemini-flash-latest"),
-                                edit_system(self.brand, min_score),
+                                edit_system(self.brand, min_score, self._confirmed_only),
                                 edit_user(now_l.strftime("%Y-%m-%d %H:%M"), slots, covered[:90] + older, cands,
                                           self._owner_rejected()),
@@ -436,4 +436,18 @@
             decisions[i] = x
         return self._guard(queue, decisions, slots, min_score, covered + older)
+
+    @property
+    def _confirmed_only(self) -> bool:
+        """Yalnızca doğrulanmış haber: yönetmen söylenti / sızıntı / doğrulanmamış iddiaları baştan eler."""
+        return bool(self.cfg.get("editorial", "confirmed_only", False))
+
+    def _drop(self, d: dict, reason: str) -> None:
+        """Tam otonomda şüpheli / istenmeyen taslak: yayınlanmaz, sana da sorulmaz (günün özetinde sayısı yazar)."""
+        d["policy_reason"] = reason
+        log.info("Taslak %s yayınlanmadı (%s): %s", d.get("id"), reason, d.get("title"))
+        self.store.bump(self.today(), "dropped")
+        if (d.get("telegram") or {}).get("message_id"):
+            self._update_preview(d, "dropped")      # daha önce sorulmuş bir taslaksa mesajı kapanır
+        self.store.archive_draft(d, "dropped")
 
     def _owner_rejected(self) -> list[dict]:
@@ -782,4 +796,7 @@
         log.info("Taslak %s [%s] önem=%s güven=%s → %s (%s)", did, d["category"], d["importance"],
                  d["confidence"], decision, reason)
+        if decision == "drop":
+            self._drop(d, reason)
+            return d
         if decision == "auto" and not self.state.get("paused"):
             post = self.publish(d, auto=True)
@@ -836,4 +853,7 @@
         d["policy_reason"] = reason
         log.info("Güncelleme taslağı %s → %s: %s (%s)", did, post["id"], decision, reason)
+        if decision == "drop":
+            self._drop(d, reason)
+            return d
         if decision == "auto" and not self.state.get("paused"):
             new = self.apply_update(d)
@@ -945,4 +965,5 @@
             "updated": "🔄 <b>HABER GÜNCELLENDİ</b>",
             "culled": "🧹 <b>SEÇKİ DIŞI</b> (yeni ölçütlere göre elendi)",
+            "dropped": "🚫 <b>YAYINLANMADI</b> (şüpheli ya da istenmeyen içerik)",
         }[kind]
         upd = d.get("update_of")
@@ -970,4 +991,6 @@
         elif d.get("editor_note") and kind == "pending":
             lines.append(f"📝 {esc(d['editor_note'])}")
+        if kind == "dropped" and d.get("policy_reason"):
+            lines.append(f"<i>{esc(d['policy_reason'])}</i>")
         if kind == "pending" and d.get("policy_reason"):
             if d.get("policy_tier") == "wait":
@@ -1457,5 +1480,5 @@
                             f"<code>/mod kural</code> — 3+ kaynakta çıkan geniş kitleli / büyük marka haberleri otomatik\n"
                             f"<code>/mod manuel</code> — her haber sana sorulur\n"
-                            f"<code>/mod tam</code> — yalnızca uyarılı haberler ve listedeki markalar sorulur", silent=True)
+                            f"<code>/mod tam</code> — hiçbir şey sorulmaz; şüpheli haberler yayınlanmaz", silent=True)
         elif cmd == "duraklat":
             self.state["paused"] = True
@@ -1534,6 +1557,7 @@
             f"Onay bekleyen: {pend} ({waiting} tanesi 3. kaynağı bekliyor) · Yazılmak için sırada: "
             f"{len(self.state.get('queue') or [])}",
-            ("Tam otonom: yönetmenin seçtiği her haber yayınlanır; uyarılı haberler ve listedeki markalar sorulur. "
-             "Kaldırdıkların yönetmene örnek olur." if policy.current_mode(self.cfg, self.state) == "tam"
+            (f"Tam otonom: yönetmenin seçtiği haberler sorulmadan yayınlanır; şüpheli olanlar yayınlanmaz "
+             f"(bugün {c.get('dropped', 0)}). Kaldırdıkların yönetmene örnek olur."
+             if policy.current_mode(self.cfg, self.state) == "tam"
              else "Her haber sana soruluyor." if policy.current_mode(self.cfg, self.state) == "manuel"
              else f"⏸ Otomatik yayın {esc(tr_date(until, self.cfg.tz))} tarihine kadar durdu (/mod kural ile aç)" if until
@@ -1581,4 +1605,7 @@
             decision, reason = policy.decide(self.cfg, self.state, self.stats, d)
             d["policy_reason"] = reason
+            if decision == "drop":
+                self._drop(d, reason)
+                continue
             if decision == "auto":
                 try:
@@ -1699,5 +1726,5 @@
             try:
                 out = self.llm.json(cfg.get("ai", "editor_model", None) or cfg.get("ai", "writer_model", "gemini-flash-latest"),
-                                    edit_system(self.brand, min_score),
+                                    edit_system(self.brand, min_score, self._confirmed_only),
                                     edit_user(local(now_utc(), cfg.tz).strftime("%Y-%m-%d %H:%M"), len(chunk), covered[:90], cands), EDIT_SCHEMA, max_tokens=8000)
             except LLMError as e:
@@ -1822,4 +1849,5 @@
                 f"Güncellenen haber: {c.get('updated', 0)}\n"
                 f"Ret: {c.get('rejected', 0)} · Süresi dolan: {c.get('expired', 0)} · Kaldırılan: {c.get('removed', 0)}\n"
+                + (f"Şüpheli olduğu için yayınlanmayan: {c['dropped']}\n" if c.get("dropped") else "") +
                 f"Seçki: {sum(1 for x in self.state.get('edit_log') or [] if (x.get('t') or '')[:10] == iso(now_utc())[:10] and x['action'] == 'skip')} "
                 f"aday elendi (/secki)\n"
--- a/haberbot/policy.py
+++ b/haberbot/policy.py
@@ -12,6 +12,7 @@
 Güvenlik (yalnızca kural modunda): otomatik yayınlanan haberlerden son 3 günde 2'sini kaldırırsan otomatik yayın kendiliğinden
 durur (her şey sorulur); /mod kural yazınca hemen yeniden açılır. /mod manuel → her şey sorulur.
-/mod tam → yönetmenin seçtiği her haber yayınlanır, yalnızca 🔴 olanlar sorulur; beğenmediğini Kaldır'la çıkarırsın
-(kaldırdıkların yönetmene "sahibin istemediği haberler" olarak gösterilir, fren devreye girmez).
+/mod tam → yönetmenin seçtiği her haber sorulmadan yayınlanır; 🔴 olanlar (şüpheli: doğrulanmamış iddia, çelişen kaynak,
+yetersiz bilgi, eski, tanıtım, hassas konu · listedeki markalar · güveni düşük) hiç yayınlanmaz ve sana da sorulmaz.
+Beğenmediğini Kaldır'la çıkarırsın (kaldırdıkların yönetmene "sahibin istemediği haberler" olarak gösterilir).
 """
 from __future__ import annotations
@@ -21,4 +22,5 @@
 
 from .config import Config
+from .prompts import FLAG_LABELS
 from .util import hours_since, iso, now_utc, parse_iso
 
@@ -101,24 +103,33 @@
 
 # ── karar ─────────────────────────────────────────────────────────────
+def hard_reason(cfg: Config, draft: dict) -> str | None:
+    """Otomatik yayınlanamayacak haber: şüpheli (uyarı işareti), listedeki marka, güveni düşük ya da önemsiz."""
+    if draft.get("flags"):
+        return "Şüpheli içerik: " + ", ".join(FLAG_LABELS.get(f, f) for f in draft["flags"])
+    brand = never_auto_brand(cfg, draft)
+    if brand:
+        return f"{brand}: otomatik yayınlanmayan marka"
+    if draft.get("confidence") == "dusuk":
+        return "Güven seviyesi düşük"
+    if int(draft.get("importance") or 0) < int(_a(cfg, "auto_min_importance", 7)):
+        return "Önem puanı düşük"
+    return None
+
+
 def decide(cfg: Config, state: dict, stats: dict, draft: dict) -> tuple[str, str]:
-    """('auto' | 'ask', gerekçe). Taslağa policy_tier (auto/wait/ask/hard/paused) ve otomatikse auto_reason yazar."""
+    """('auto' | 'ask' | 'drop', gerekçe). Taslağa policy_tier (auto/wait/ask/hard/paused/drop) ve otomatikse auto_reason
+    yazar. 'drop': tam otonomda şüpheli / istenmeyen haber — yayınlanmaz, sorulmaz."""
     def out(tier: str, reason: str) -> tuple[str, str]:
         draft["policy_tier"] = tier
         if tier == "auto":
             draft["auto_reason"] = reason
-        return ("auto" if tier == "auto" else "ask"), reason
+        return ("auto" if tier == "auto" else "drop" if tier == "drop" else "ask"), reason
 
     mode = current_mode(cfg, state)
     if mode == "manuel":
         return out("hard", "Manuel mod: her haber sana soruluyor")
-    if draft.get("flags"):
-        return out("hard", "Uyarı işareti var")
-    brand = never_auto_brand(cfg, draft)
-    if brand:
-        return out("hard", f"{brand}: otomatik yayınlanmayan marka")
-    if draft.get("confidence") == "dusuk":
-        return out("hard", "Güven seviyesi düşük")
-    if int(draft.get("importance") or 0) < int(_a(cfg, "auto_min_importance", 7)):
-        return out("hard", "Önem puanı düşük")
+    why = hard_reason(cfg, draft)
+    if why:
+        return out("drop" if mode == "tam" else "hard", why)
     if mode == "tam":
         return out("auto", "Tam otonom: yayın yönetmeni seçti")
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -178,5 +178,13 @@
 
 
-def edit_system(site_name: str, min_score: int) -> str:
+CONFIRMED_ONLY_RULE = """
+- CONFIRMED NEWS ONLY: we publish only confirmed facts (official announcements, launches, filings, on-record statements,
+  verified data). Skip rumors, leaks, unconfirmed or anonymous-source reports and "may / is expected to / reportedly /
+  claims" stories — even from Mark Gurman or Bloomberg —, stories whose sources conflict, old news presented as new and
+  promotional content. Status "dropped" in COVERED means we did not publish it because it was unconfirmed: it may run
+  later only as a new story when an official confirmation arrives."""
+
+
+def edit_system(site_name: str, min_score: int, confirmed_only: bool = False) -> str:
     return f"""You are the editor-in-chief of "{site_name}", a Turkish-language, hand-curated daily tech briefing for a BROAD
 TURKISH AUDIENCE: ordinary people in Türkiye who like technology, not industry insiders. We cover AI, consumer tech (phones,
@@ -230,5 +238,5 @@
   taste from the PATTERNS (kinds of stories rejected again and again, e.g. a type of update, a sector, a kind of report) and
   give candidates of the same kind a must_read at least 2 points lower — usually a "skip". One rejection alone may have had
-  other reasons (a duplicate, the wording); a clearly bigger development of that kind can still pass.
+  other reasons (a duplicate, the wording); a clearly bigger development of that kind can still pass.{CONFIRMED_ONLY_RULE if confirmed_only else ""}
 - reason: ≤12 words in Turkish."""
 
--- a/tests/test_core.py
+++ b/tests/test_core.py
@@ -52,5 +52,9 @@
     one = {**GOOD, "sources": THREE[:1], "importance": 7, "title": "Küçük bir uygulama", "tags": []}
     assert policy.decide(CFG, {"mode_override": "tam"}, stats, one)[0] == "auto"
-    assert policy.decide(CFG, {"mode_override": "tam"}, stats, {**one, "flags": ["iddia"]})[0] == "ask"
+    # tam otonomda şüpheli / listedeki marka: yayınlanmaz, sorulmaz
+    for bad in ({"flags": ["iddia"]}, {"flags": ["celiski"]}, {"confidence": "dusuk"}, {"title": "Oppo Find X10"}):
+        x = {**one, **bad}
+        assert policy.decide(CFG, {"mode_override": "tam"}, stats, x)[0] == "drop" and x["policy_tier"] == "drop", bad
+    assert "Doğrulanmamış iddia" in policy.decide(CFG, {"mode_override": "tam"}, stats, {**one, "flags": ["iddia"]})[1]
     # 2 otomatik haber kaldırılınca fren
     assert policy.record_removal(CFG, stats) is False
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -317,5 +317,6 @@
 def test_full_autonomy_publishes_and_learns_from_rejections():
     with _App() as (cfg, a):
-        from haberbot.prompts import edit_user
+        from haberbot import policy
+        from haberbot.prompts import edit_system, edit_user
         from haberbot.telegram import MockTelegram
         a.tg = a.tg or MockTelegram(cfg.root / "tg")
@@ -331,5 +332,10 @@
         p = a.store.load_post("p06")
         assert p["publish_mode"] == "auto" and "yönetmeni seçti" in a._caption(p, "auto")
-        assert a.store.load_draft("p07")["policy_tier"] == "hard"     # uyarılı haber sorulmaya devam eder
+        # şüpheli (uyarılı) haber: yayınlanmaz, sorulmaz; daha önce sorulmuşsa mesajı "yayınlanmadı" olur
+        assert not a.store.load_draft("p07") and not a.store.load_post("p07")
+        out = (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8")
+        assert "YAYINLANMADI" in out and "Doğrulanmamış iddia" in out and "ONAY BEKLİYOR" not in out
+        assert any(x["status"] == "dropped" for x in a.store.recent_archive(1))
+        assert policy.decide(cfg, a.state, a.stats, {**d, "title": "Vivo X300 tanıtıldı"})[0] == "drop"
         # kaldırılanlar freni tetiklemez, yönetmene "sahibin istemediği" örnek olur
         a.store.save_post({**_post(8, 1), "publish_mode": "auto", "title": "One UI 9 güncellemesi dağıtılıyor"})
@@ -339,10 +345,10 @@
         assert "Otomatik yayın durdu" not in (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8")
         assert policy_mode(a) == "tam"
-        a._on_button("r", "p07")
-        a.store.archive_draft(a.store.load_draft("p07"), "rejected")
-        rej = a._owner_rejected()
-        assert {r["title"] for r in rej} == {"GTA 6 sızıntısı büyüyor", "One UI 9 güncellemesi dağıtılıyor", d["title"]}
+        rej = a._owner_rejected()                              # düşenler sahibin zevki sayılmaz, kaldırılanlar sayılır
+        assert {r["title"] for r in rej} == {"One UI 9 güncellemesi dağıtılıyor", d["title"]}
         text = edit_user("2026-10-13 15:00", 2, [], [], rej)
         assert "OWNER REJECTED" in text and "One UI 9 güncellemesi dağıtılıyor" in text
+        assert "CONFIRMED NEWS ONLY" in edit_system("Smarity", 7, True) and "CONFIRMED" not in edit_system("Smarity", 7)
+        assert a._confirmed_only is bool(cfg.get("editorial", "confirmed_only", False))
 
 
@@@SM@@@ SHA
ff985aed9afb1e2efe3467c3b196e59612166db5e0704d85e9fee5e20a530d6e config.yaml
1ad00f1491b51ed8e5189f8eac67874d1c57179fdf0a0593fca415c9c6f65707 haberbot/app.py
1d0a07ae489efcfc7c38f5ba1a6171828a9f75847993adcde0ab0dccb8fdf242 haberbot/policy.py
9c97f16e73508a462f0be99f4113f31e2d188ed5efa44d6e65e428d60e228079 haberbot/prompts.py
6e5a9c2a20ce605749e284f405e49817e9218efabfa0ca58b68ade3ed9dc3c96 tests/test_core.py
9d35d08b0b17b4c5e61ce7a5dc6647d97c90bdb6aa2ce2a53239954a07366391 tests/test_home.py
