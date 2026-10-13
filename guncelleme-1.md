SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -60,4 +60,6 @@
   max_item_age_hours: 36         # Bundan eski haberler atlanır
   pending_expire_hours: 36       # Onaylanmayan taslak bu süre sonunda düşer
+  taste_days: 21                 # Yönetmen, son bu kadar günde reddettiğin / kaldırdığın haberlerden zevkini öğrenir
+  taste_examples: 40             # ...en fazla bu kadar örnekle
   fetch_full_text: true          # Haberin tam metnini kaynağından okuyup daha doğru özet çıkar
 
@@ -69,5 +71,5 @@
   #   🔴 hep sorar      : uyarı işareti, never_auto markaları, güven 'düşük'
   # Modlar: kural (önerilen) · manuel (her şey sorulur) · tam (yalnızca 🔴 sorulur). Telegram'dan /mod ile değiştirilir.
-  mode: kural
+  mode: tam                      # Ekim 2026: sahibin isteğiyle tam otonom (beğenmediklerini Telegram'dan kaldırır)
   min_sources: 3                 # Otomatik yayın için gereken en az farklı kaynak (yayın kuruluşu) sayısı
   broad_importance: 8            # Yönetmen puanı bu ve üstü = geniş kitle (büyük marka olmasa da otomatik olabilir)
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -85,4 +85,5 @@
 🔴 <b>Hep sorar</b> — uyarı işaretli (iddia, söylenti) haberler, Vivo / Oppo gibi listedeki markalar.
 Otomatik yayınlanan 2 haberi 3 gün içinde kaldırırsan otomatik yayın kendiliğinden durur; <code>/mod kural</code> ile yeniden açılır. <code>/mod manuel</code>: her şey sorulur.
+<b>Tam otonom</b> (<code>/mod tam</code>): yönetmenin seçtiği her haber yayınlanır ve sana "yayınlandı" diye gelir; yalnızca 🔴 olanlar sorulur. Beğenmediğini 🗑 <b>Kaldır</b>'la çıkar: reddettiğin ve kaldırdığın haberler yönetmene "sahibin istemediği haberler" olarak gösterilir, benzerlerini seçmez.
 
 📸 <b>Instagram</b> — yayınlanan her haber birkaç dakika içinde carousel ve hikâye olarak Instagram'da paylaşılır. Sıradaki bir haberi mesajındaki <b>Instagram'a gönderme</b> düğmesiyle durdurabilirsin. Tümünü durdurmak için <code>/instagram kapat</code>.
@@ -410,5 +411,6 @@
             out = self.llm.json(cfg.get("ai", "editor_model", None) or cfg.get("ai", "writer_model", "gemini-flash-latest"),
                                 edit_system(self.brand, min_score),
-                                edit_user(now_l.strftime("%Y-%m-%d %H:%M"), slots, covered[:90] + older, cands),
+                                edit_user(now_l.strftime("%Y-%m-%d %H:%M"), slots, covered[:90] + older, cands,
+                                          self._owner_rejected()),
                                 EDIT_SCHEMA, max_tokens=6000)
             raw = {str(x.get("cid")): x for x in (out.get("decisions") or []) if isinstance(x, dict)}
@@ -434,4 +436,20 @@
             decisions[i] = x
         return self._guard(queue, decisions, slots, min_score, covered + older)
+
+    def _owner_rejected(self) -> list[dict]:
+        """Son haftalarda reddettiğin ya da yayından kaldırdığın haberler: yönetmen zevkini bunlardan öğrenir."""
+        ed = lambda k, d: self.cfg.get("editorial", k, d)  # noqa: E731
+        days, n = float(ed("taste_days", 21) or 0), int(ed("taste_examples", 40) or 0)
+        if not days or not n:
+            return []
+        out, seen = [], set()
+        for a in self.store.recent_archive(days * 24):          # en yeniden eskiye
+            t = (a.get("title") or "").strip()
+            if a.get("status") in ("rejected", "removed") and t and t.lower() not in seen:
+                seen.add(t.lower())
+                out.append({"category": a.get("category", ""), "title": clip(t, 110)})
+            if len(out) >= n:
+                break
+        return out
 
     def _guard(self, queue: list[dict], decisions: dict[int, dict], slots: int, min_score: int,
@@ -1012,5 +1030,7 @@
             log.warning("Önizleme kartı üretilemedi: %s", e)
             img = self._hero(d)
-        silent = True if kind == "auto" else self.quiet()
+        # tam otonomda "yayınlandı" mesajları ana akış: gündüz sesli gelir (kural modunda otomatikler sessiz)
+        tam = policy.current_mode(self.cfg, self.state) == "tam"
+        silent = True if kind == "auto" and not tam else self.quiet()
         caption = self._caption(d, kind)
         try:
@@ -1240,5 +1260,6 @@
             weight = 2 if d.get("publish_mode") == "auto" else 1
             policy.record(self.stats, d, ok=False, weight=weight)
-            if d.get("publish_mode") == "auto" and policy.record_removal(self.cfg, self.stats):
+            if (d.get("publish_mode") == "auto" and policy.current_mode(self.cfg, self.state) == "kural"
+                    and policy.record_removal(self.cfg, self.stats)):
                 until = policy.auto_paused_until(self.cfg, self.stats)
                 self.notify(f"⏸ <b>Otomatik yayın durdu</b>\nKısa sürede otomatik yayınlanan haberlerden "
@@ -1513,5 +1534,8 @@
             f"Onay bekleyen: {pend} ({waiting} tanesi 3. kaynağı bekliyor) · Yazılmak için sırada: "
             f"{len(self.state.get('queue') or [])}",
-            (f"⏸ Otomatik yayın {esc(tr_date(until, self.cfg.tz))} tarihine kadar durdu (/mod kural ile aç)" if until
+            ("Tam otonom: yönetmenin seçtiği her haber yayınlanır; uyarılı haberler ve listedeki markalar sorulur. "
+             "Kaldırdıkların yönetmene örnek olur." if policy.current_mode(self.cfg, self.state) == "tam"
+             else "Her haber sana soruluyor." if policy.current_mode(self.cfg, self.state) == "manuel"
+             else f"⏸ Otomatik yayın {esc(tr_date(until, self.cfg.tz))} tarihine kadar durdu (/mod kural ile aç)" if until
              else f"Otomatik yayın kuralı: en az {policy.min_sources(self.cfg)} farklı kaynak + geniş kitle ya da büyük marka"),
             f"Son {n} kararında onay oranın: %{rate * 100:.0f}",
--- a/haberbot/policy.py
+++ b/haberbot/policy.py
@@ -10,6 +10,8 @@
   🟢 OTOMATİK           geniş kitle ya da büyük marka + en az 3 farklı kaynak
 
-Güvenlik: otomatik yayınlanan haberlerden son 3 günde 2'sini kaldırırsan otomatik yayın kendiliğinden durur (her şey sorulur);
-/mod kural yazınca hemen yeniden açılır. /mod manuel → her şey sorulur, /mod tam → yalnızca 🔴 olanlar sorulur.
+Güvenlik (yalnızca kural modunda): otomatik yayınlanan haberlerden son 3 günde 2'sini kaldırırsan otomatik yayın kendiliğinden
+durur (her şey sorulur); /mod kural yazınca hemen yeniden açılır. /mod manuel → her şey sorulur.
+/mod tam → yönetmenin seçtiği her haber yayınlanır, yalnızca 🔴 olanlar sorulur; beğenmediğini Kaldır'la çıkarırsın
+(kaldırdıkların yönetmene "sahibin istemediği haberler" olarak gösterilir, fren devreye girmez).
 """
 from __future__ import annotations
@@ -21,5 +23,5 @@
 from .util import hours_since, iso, now_utc, parse_iso
 
-MODES = {"manuel": "Manuel (her haber sorulur)", "kural": "Kurallı (3+ kaynak otomatik)", "tam": "Tam otonom"}
+MODES = {"manuel": "Manuel (her haber sorulur)", "kural": "Kurallı (3+ kaynak otomatik)", "tam": "Tam otonom (yönetmenin seçtiği her haber yayınlanır)"}
 ALIASES = {"ogrenen": "kural", "öğrenen": "kural", "otomatik": "kural", "oto": "kural"}
 TIER_ICON = {"auto": "🟢", "wait": "⏳", "ask": "🟡", "hard": "🔴", "paused": "⏸"}
@@ -120,5 +122,5 @@
         return out("hard", "Önem puanı düşük")
     if mode == "tam":
-        return out("auto", "Tam otonom mod")
+        return out("auto", "Tam otonom: yayın yönetmeni seçti")
     if not is_broad(cfg, draft):
         return out("ask", "Küçük kitleye hitap ediyor ve büyük bir marka değil")
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -227,10 +227,18 @@
   big car makers, Sony/PlayStation, Xbox, Nintendo, GTA, Netflix, Spotify, Turkcell, Türk Telekom, Trendyol…); false for
   lesser-known or mid-tier brands (Vivo, Oppo, Realme, Tecno, Infinix, small startups, niche gadget makers).
+- OWNER REJECTED (if given): stories the site owner turned down or removed after publishing in recent weeks. Learn his
+  taste from the PATTERNS (kinds of stories rejected again and again, e.g. a type of update, a sector, a kind of report) and
+  give candidates of the same kind a must_read at least 2 points lower — usually a "skip". One rejection alone may have had
+  other reasons (a duplicate, the wording); a clearly bigger development of that kind can still pass.
 - reason: ≤12 words in Turkish."""
 
 
-def edit_user(now: str, slots: int, covered: list[dict], candidates: list[dict]) -> str:
-    lines = [f"NOW: {now}", f"SLOTS: {slots}", "",
-             "COVERED (id | status | age | category | entities | title):"]
+def edit_user(now: str, slots: int, covered: list[dict], candidates: list[dict], rejected: list[dict] | None = None) -> str:
+    lines = [f"NOW: {now}", f"SLOTS: {slots}", ""]
+    if rejected:
+        lines.append("OWNER REJECTED (category | title) — his taste, not coverage:")
+        lines += [f"- {r.get('category', '')} | {r.get('title', '')}" for r in rejected]
+        lines.append("")
+    lines.append("COVERED (id | status | age | category | entities | title):")
     if covered:
         for c in covered:
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -53,4 +53,5 @@
         self.tmp = tempfile.TemporaryDirectory()
         raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
+        raw.setdefault("autonomy", {})["mode"] = "kural"     # testler canlı moddan bağımsız (tam otonom ayrıca sınanır)
         self.cfg = Config(raw=raw, root=Path(self.tmp.name), site_url="https://smarity.com.tr", mock=True,
                           telegram_chat_id="1")
@@ -314,4 +315,41 @@
 
 
+def test_full_autonomy_publishes_and_learns_from_rejections():
+    with _App() as (cfg, a):
+        from haberbot.prompts import edit_user
+        from haberbot.telegram import MockTelegram
+        a.tg = a.tg or MockTelegram(cfg.root / "tg")
+        a._on_command("mod", "tam")
+        d = {**_post(6, 0), "status": "pending", "created_at": iso(now_utc()), "telegram": {"message_id": 61},
+             "importance": 7, "big_brand": False, "confidence": "orta", "flags": [], "source_keys": ["Kaynak"]}
+        d.pop("published_at")
+        d.pop("slug")
+        flagged = {**d, "id": "p07", "flags": ["iddia"], "telegram": {"message_id": 71}, "title": "GTA 6 sızıntısı büyüyor"}
+        a.store.save_draft(d)
+        a.store.save_draft(flagged)
+        assert a.recheck_pending() == 1                      # tek kaynak, küçük kitle: tam otonomda yine yayınlanır
+        p = a.store.load_post("p06")
+        assert p["publish_mode"] == "auto" and "yönetmeni seçti" in a._caption(p, "auto")
+        assert a.store.load_draft("p07")["policy_tier"] == "hard"     # uyarılı haber sorulmaya devam eder
+        # kaldırılanlar freni tetiklemez, yönetmene "sahibin istemediği" örnek olur
+        a.store.save_post({**_post(8, 1), "publish_mode": "auto", "title": "One UI 9 güncellemesi dağıtılıyor"})
+        a._on_button("d", "p06")
+        a._on_button("d", "p08")
+        assert not a.stats.get("auto_removals")
+        assert "Otomatik yayın durdu" not in (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8")
+        assert policy_mode(a) == "tam"
+        a._on_button("r", "p07")
+        a.store.archive_draft(a.store.load_draft("p07"), "rejected")
+        rej = a._owner_rejected()
+        assert {r["title"] for r in rej} == {"GTA 6 sızıntısı büyüyor", "One UI 9 güncellemesi dağıtılıyor", d["title"]}
+        text = edit_user("2026-10-13 15:00", 2, [], [], rej)
+        assert "OWNER REJECTED" in text and "One UI 9 güncellemesi dağıtılıyor" in text
+
+
+def policy_mode(a):
+    from haberbot import policy
+    return policy.current_mode(a.cfg, a.state)
+
+
 if __name__ == "__main__":
     for name, fn in list(globals().items()):
@@@SM@@@ SHA
fddf516e793c901f6f2b9606ca52ade59c7621dd81f5ae3109bd08ef39de316d config.yaml
bbe3738614c6db6f52f6300d84fc9523b302a2077f3c3d9229789ea8b5d238e4 haberbot/app.py
36c381eab0a05402e26127604794e39f7f91a9c55d3df73783b786698c9225bc haberbot/policy.py
a010f8463dc12b1ea74f15d06831b42ba00612b18c3b6e5bdf397112fc9f0db6 haberbot/prompts.py
674e3d6c2d0a121099053b9c1234c354936c104b0ee4439eab8c4299749587d4 tests/test_home.py
