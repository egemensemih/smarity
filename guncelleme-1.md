SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -45,7 +45,13 @@
 
 editorial:
-  min_importance: 7              # 1-10 arası. Bunun altındaki haberler hiç önüne gelmez (seçici: 7)
+  # Seçki iki aşamalı: haber masası kaynakları ayıklar ve aynı olayı tek habere toplar (min_importance), ardından
+  # yayın yönetmeni o güne kadar yayınlananları görerek karar verir: yeni haber / mevcut haberi güncelle / geç / beklet.
+  # Ölçüt: "Bu alanı yakından takip eden biri bunu bugünün kaçırılmaması gereken gelişmelerinden sayar mı?"
+  min_importance: 7              # 1-10. Haber masasının aday eşiği
+  min_must_read: 8               # 1-10. Yayın yönetmeninin yeni haber eşiği (seçici: 8)
+  max_per_company_per_day: 1     # Aynı şirketten 24 saatte en fazla kaç haber (günün en büyük haberleri, 9+, hariç)
   max_drafts_per_run: 2          # Bir taramada en fazla kaç yeni haber taslağı yazılsın (haberler tek tek, düzenli gelsin)
-  max_drafts_per_day: 0          # Günlük üst sınır (0 = sınır yok; haberler yalnızca önem eşiğine göre seçilir)
+  max_drafts_per_day: 12         # Günlük üst sınır; gün boyuna yayılır (sabah hepsi birden tükenmez)
+  burst: 2                       # Günün başında sınırın önüne geçebilecek taslak sayısı
   active_hours: [7, 24]          # Taslakların yayıldığı saatler (gece en fazla birkaç haber gelir, kalanlar sabaha kalır)
   max_item_age_hours: 36         # Bundan eski haberler atlanır
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -17,9 +17,10 @@
 from .instagram import Instagram, InstagramError, TokenStore, fingerprint, head_ok
 from .llm import LLMError, MockLLM, estimate_cost, make_llm
-from .prompts import (APPEAL_SCHEMA, FLAG_LABELS, FLAGS, SEO_SCHEMA, TRIAGE_SCHEMA, WRITE_SCHEMA, appeal_system,
-                      appeal_user, seo_system, seo_user, triage_system, triage_user, write_system, write_user)
+from .prompts import (APPEAL_SCHEMA, COVERLINE_SCHEMA, EDIT_SCHEMA, FLAG_LABELS, FLAGS, SEO_SCHEMA, TRIAGE_SCHEMA,
+                      WRITE_SCHEMA, appeal_system, appeal_user, coverline_system, coverline_user, edit_system, edit_user,
+                      seo_system, seo_user, triage_system, triage_user, write_system, write_user)
 from .sources import fetch_all
 from .store import Store
-from .textfix import Fixer
+from .textfix import Fixer, entity_keys
 from .telegram import MockTelegram, Telegram, TelegramError
 from .util import (clip, hours_since, iso, local, log, now_utc, short_hash, slugify,
@@ -47,8 +48,9 @@
     ("kaynaklar", "Kaynak güven puanları"),
     ("manset", "Manşeti yönet: haberi manşete al / çıkar"),
+    ("secki", "Yayın yönetmeninin son kararları (neden seçildi / elendi)"),
     ("instagram", "Instagram paylaşımları: durum / kapat / ac"),
     ("yardim", "Nasıl kullanılır"),
 ]
-COMMANDS_VERSION = 3
+COMMANDS_VERSION = 4
 KEYBOARD_VERSION = 4          # yayındaki haber mesajlarının düğmeleri bu sürüme göre bir kez yenilenir
 HELP = """<b>Nasıl çalışır?</b>
@@ -62,5 +64,5 @@
 🎨 <b>Yazılı kapak / Yeni kapak</b> — kapağı bizim yazılı tasarımımıza çevirir ya da yenisini üretir (fotoğraflar haberde kalır)
 🚫 <b>Fotoğrafsız</b> — haberdeki tüm fotoğrafları kaldırır
-🔤 <b>Kapak yazısı</b> — mesajı yanıtlayıp <code>görsel: Galaxy S27</code> gibi kısa bir ifade yazarsan kapakta o yazar
+🔤 <b>Kapak başlığı</b> — mesajı yanıtlayıp <code>görsel: Starship ilk kez yörüngede</code> gibi kısa bir başlık yazarsan kapakta o yazar
 ✏️ <b>Düzeltme</b> — bir haber mesajını <i>yanıtlayıp</i> talimat yaz: "başlığı kısalt", "ikinci paragrafı çıkar" gibi. Yayınlanmış habere de uygulanır.
 🗑 <b>Kaldır</b> — yayınlanmış haberi siteden kaldırır
@@ -69,4 +71,6 @@
 🙈 <b>Ana sayfada gösterme</b> — haber ana sayfaya çıkmaz, kategoride ve "Tüm haberler"de kalır
 
+<b>Seçki:</b> Sitede aynı gün her şey yer almaz. Haber masası aynı olayı tek habere toplar; yayın yönetmeni o güne kadar yayınlananları görerek karar verir: bu alanı takip eden biri için günün kaçırılmaması gereken gelişmesi mi? Aynı şirketten 24 saatte bir haber (günün en büyük haberleri hariç), yayındaki bir haberin devamı gelirse yeni haber yerine 🔄 <b>güncelleme önerisi</b> gelir; onaylarsan mevcut haber yeni gelişmeyle güncellenir, adresi değişmez. Neyin neden elendiğini /secki gösterir.
+
 <b>Ana sayfa seçkisi:</b> Her haber ana sayfaya çıkmaz. Yapay zeka her habere bir ilgi puanı verir; puan ve tazeliğe göre en dikkat çekiciler manşete ve "Öne çıkanlar"a girer.
 
@@ -75,5 +79,5 @@
 📸 <b>Instagram</b> — yayınlanan her haber birkaç dakika içinde carousel ve hikâye olarak Instagram'da paylaşılır. Sıradaki bir haberi mesajındaki <b>Instagram'a gönderme</b> düğmesiyle durdurabilirsin. Tümünü durdurmak için <code>/instagram kapat</code>.
 
-Komutlar: /manset /durum /bekleyen /mod /topla /duraklat /devam /kaynaklar /instagram"""
+Komutlar: /manset /secki /durum /bekleyen /mod /topla /duraklat /devam /kaynaklar /instagram"""
 
 
@@ -221,15 +225,20 @@
                 by_tid[it["tid"]] = it
 
-            recent = [{"sid": f"q:{i}", "status": "queued", "title": q["story"].get("topic", "")}
-                      for i, q in enumerate(queue)]
+            recent = []
+            for p in st.posts():
+                if hours_since(p.get("published_at")) > 72:
+                    break
+                recent.append({"sid": "s:" + p["id"], "status": "published", "title": p["title"]})
             for d in st.drafts():
                 recent.append({"sid": "s:" + d["id"], "status": d.get("status", "pending"), "title": d["title"]})
-            for p in st.posts():
-                if hours_since(p.get("published_at")) < 72:
-                    recent.append({"sid": "s:" + p["id"], "status": "published", "title": p["title"]})
+            for a in st.recent_archive(72):   # reddedilen / süresi dolan haberler tekrar önerilmesin
+                if a.get("status") in ("rejected", "expired", "removed"):
+                    recent.append({"sid": "s:" + a["id"], "status": a["status"], "title": a.get("title", "")})
+            recent += [{"sid": f"q:{i}", "status": "queued", "title": q["story"].get("topic", "")}
+                       for i, q in enumerate(queue)]
 
             try:
                 tri = self.llm.json(cfg.get("ai", "triage_model", "claude-haiku-4-5-20251001"),
-                                    triage_system(self.brand), triage_user(fresh, recent[:100], today),
+                                    triage_system(self.brand), triage_user(fresh, recent[:150], today),
                                     TRIAGE_SCHEMA, max_tokens=8000)
             except LLMError as e:
@@ -242,8 +251,10 @@
                 tri = {"stories": []}
 
+            posted = {p["id"] for p in st.posts() if hours_since(p.get("published_at")) <= 72}
             for s in tri.get("stories", []):
                 its = [by_tid[t] for t in s.get("item_ids", []) if t in by_tid]
                 if not its:
                     continue
+                s["entities"] = [clip(str(e).strip(), 40) for e in (s.get("entities") or []) if str(e).strip()][:3]
                 dup = (s.get("duplicate_of") or "").strip()
                 if dup.startswith("q:") and dup[2:].isdigit() and int(dup[2:]) < len(queue):
@@ -254,5 +265,12 @@
                     continue
                 if dup:
-                    if self._merge_sources(dup.removeprefix("s:"), its):
+                    did = dup.removeprefix("s:")
+                    if self._merge_sources(did, its):
+                        merged += 1
+                        continue
+                    # yayındaki bir haberin devamı: önemliyse yönetmen "güncelle" ya da "geç" der
+                    if did in posted and int(s.get("importance", 0)) >= min_imp and s.get("on_topic", True):
+                        new_stories.append({"story": s, "items": its, "at": iso(now_utc())})
+                    else:
                         merged += 1
                     continue
@@ -262,12 +280,35 @@
                 new_stories.append({"story": s, "items": its, "at": iso(now_utc())})
 
-        # Sıra: önce önemli olanlar; eşitse önce gelen
-        queue = sorted(queue + new_stories, key=lambda q: (-int(q["story"].get("importance", 0)), q["at"]))
-        limit = min(ed("max_drafts_per_run", 2), remaining)
-        todo, queue = queue[:limit], queue[limit:]
-        self.state["queue"] = queue[:40]
+        # Yayın yönetmeni: adaylar arasından günün seçkisi (yeni haber / mevcut haberi güncelle / geç / beklet)
+        queue = sorted(queue + new_stories, key=lambda q: (-int(q["story"].get("importance", 0)), q["at"]))[:24]
+        slots = min(int(ed("max_drafts_per_run", 2)), remaining)
+        if not new_stories and all(hours_since(q.get("held_at")) < 0.75 for q in queue):
+            self.state["queue"] = queue[:30]   # yeni aday yok, bekleyenlere az önce bakıldı
+            return
+        decisions = self._edit(queue, slots) if queue else {}
+        todo, updates, keep = [], [], []
+        for i, q in enumerate(queue):
+            x = decisions.get(i) or {"action": "hold", "target": "", "must_read": 0, "reason": ""}
+            q["story"]["must_read"] = int(x.get("must_read") or 0)
+            q["story"]["editor_reason"] = x.get("reason", "")
+            act = x["action"]
+            if act == "publish":
+                todo.append(q)
+            elif act == "update":
+                updates.append((q, x["target"]))
+            elif act == "merge":
+                self._merge_sources(x["target"], q["items"])
+            elif act == "hold":
+                q["holds"] = int(q.get("holds", 0)) + 1
+                q["held_at"] = iso(now_utc())
+                if q["holds"] <= 8:
+                    keep.append(q)
+            self._edit_log(q, act, x)
+        todo.sort(key=lambda q: -q["story"]["must_read"])
+        self.state["queue"] = keep[:30]
         if fresh:
-            log.info("Ayıklama: %d yeni hikâye, %d elendi, %d mevcut habere eklendi", len(new_stories), skipped, merged)
-        log.info("Bu tur %d taslak yazılacak, sırada %d haber var", len(todo), len(self.state["queue"]))
+            log.info("Ayıklama: %d aday, %d elendi, %d mevcut habere eklendi", len(new_stories), skipped, merged)
+        log.info("Yönetmen: %d yeni haber, %d güncelleme, %d bekliyor, %d geçildi", len(todo), len(updates), len(keep),
+                 len(queue) - len(todo) - len(updates) - len(keep))
         for n, q in enumerate(todo):
             if n:
@@ -281,8 +322,149 @@
                 else:
                     self.notify_error(f"Yapay zeka (yazım) hatası: {e}")
-                self.state["queue"] = (todo[n:] + self.state["queue"])[:40]  # yazılamayanlar sırada kalsın
+                self.state["queue"] = (todo[n:] + self.state["queue"])[:30]  # yazılamayanlar sırada kalsın
                 break
             except Exception as e:  # noqa: BLE001
                 log.exception("Taslak oluşturulamadı: %s", e)
+        for q, target in updates[:2]:
+            post = st.load_post(target)
+            if not post:
+                continue
+            self.process_updates()
+            try:
+                self.create_update(post, q["story"], q["items"])
+            except LLMError as e:
+                log.warning("Güncelleme yazılamadı (%s): %s", target, str(e)[:160])
+            except Exception as e:  # noqa: BLE001
+                log.exception("Güncelleme oluşturulamadı: %s", e)
+
+    # ── yayın yönetmeni ─────────────────────────────────────
+    def _covered(self, hours: float = 48) -> list[dict]:
+        """Yönetmenin gördüğü 'elimizdekiler': yayındakiler, onay bekleyenler, reddedilen / süresi dolanlar."""
+        out = []
+
+        def add(d: dict, status: str, at: str | None) -> None:
+            h = hours_since(at)
+            if h <= hours:
+                out.append({"id": d["id"], "status": status, "age": f"{h:.0f} sa", "hours": h,
+                            "category": d.get("category", ""), "entities": list(d.get("entities") or (d.get("tags") or [])[:2]),
+                            "title": d.get("title", ""), "keys": entity_keys(d), "updated": bool(d.get("refreshed_at"))})
+        for p in self.store.posts():
+            if hours_since(p.get("published_at")) > hours:
+                break
+            add(p, "published", p.get("refreshed_at") or p.get("published_at"))
+        for d in self.store.drafts():
+            if d.get("status") in ("pending", "rejected"):
+                add(d, d["status"], d.get("created_at"))
+        for a in self.store.recent_archive(hours):
+            if a.get("status") in ("rejected", "expired", "removed"):
+                add(a, a["status"], a.get("created_at") or a.get("closed_at"))
+        out.sort(key=lambda c: c["hours"])
+        return out
+
+    def _edit(self, queue: list[dict], slots: int) -> dict[int, dict]:
+        """Her aday için yönetmen kararı: {sıra: {"action", "target", "must_read", "reason"}}."""
+        cfg = self.cfg
+        ed = lambda k, d: cfg.get("editorial", k, d)  # noqa: E731
+        min_score = int(ed("min_must_read", 8))
+        covered = self._covered(48)
+        cands = []
+        for i, q in enumerate(queue):
+            s = q["story"]
+            cands.append({"cid": f"c{i + 1}", "category": s.get("category", ""), "importance": s.get("importance", 0),
+                          "entities": s.get("entities") or [], "topic": s.get("topic", ""),
+                          "dup": (s.get("duplicate_of") or "").removeprefix("s:"),
+                          "headlines": [f"{it['credit']}: {it['title']}" for it in q["items"]]})
+        now_l = local(now_utc(), cfg.tz)
+        today_n = self.store.count(self.today(), "drafts")
+        target = int(ed("max_drafts_per_day", 0) or 0) or 10
+        raw = None
+        try:
+            out = self.llm.json(cfg.get("ai", "editor_model", None) or cfg.get("ai", "writer_model", "gemini-flash-latest"),
+                                edit_system(self.brand, min_score),
+                                edit_user(now_l.strftime("%Y-%m-%d %H:%M"), slots, today_n, target, covered[:90], cands),
+                                EDIT_SCHEMA, max_tokens=6000)
+            raw = {str(x.get("cid")): x for x in (out.get("decisions") or []) if isinstance(x, dict)}
+        except LLMError as e:
+            log.warning("Yayın yönetmeni yanıt vermedi, masanın puanı kullanılacak: %s", str(e)[:160])
+        decisions = {}
+        for i, q in enumerate(queue):
+            imp = int(q["story"].get("importance", 0))
+            if raw is None:   # yedek: masanın puanı, yönetmen eşiğiyle
+                x = {"action": "publish" if imp >= min_score else "hold", "target": "", "must_read": imp,
+                     "reason": "masa puanı"}
+            else:
+                x = dict(raw.get(f"c{i + 1}") or {"action": "hold", "target": "", "must_read": 0, "reason": ""})
+            try:
+                x["must_read"] = max(0, min(10, int(x.get("must_read") or 0)))
+            except (TypeError, ValueError):
+                x["must_read"] = 0
+            x["target"] = (x.get("target") or "").strip().removeprefix("s:")
+            x["reason"] = clip(str(x.get("reason") or ""), 120)
+            if x.get("action") not in ("publish", "update", "skip", "hold"):
+                x["action"] = "hold"
+            decisions[i] = x
+        return self._guard(queue, decisions, slots, min_score, covered)
+
+    def _guard(self, queue: list[dict], decisions: dict[int, dict], slots: int, min_score: int,
+               covered: list[dict]) -> dict[int, dict]:
+        """Yönetmen kararlarına kurallı emniyet: eşik, günlük şirket sınırı, tur başına yer, aynı turda aynı şirket yok."""
+        cap = int(self.cfg.get("editorial", "max_per_company_per_day", 1) or 1)
+        day_keys: dict[str, int] = {}
+        for c in covered:
+            if c["status"] in ("published", "pending") and c["hours"] <= 24:
+                for k in c["keys"]:
+                    day_keys[k] = day_keys.get(k, 0) + 1
+        published = {c["id"] for c in covered if c["status"] == "published"}
+        published |= {p["id"] for p in self.store.posts()[:200] if hours_since(p.get("published_at")) <= 72}
+        pending = {c["id"] for c in covered if c["status"] == "pending"}
+        refreshed = {c["id"] for c in covered if c["status"] == "published" and c.get("updated") and c["hours"] < 6}
+        used, round_keys, round_targets = 0, set(), set()
+        for i in sorted(decisions, key=lambda i: -decisions[i]["must_read"]):
+            x, s = decisions[i], queue[i]["story"]
+            keys = entity_keys(s)
+            mr = x["must_read"]
+            if x["action"] == "update":
+                if x["target"] in pending:
+                    x["action"] = "merge"
+                    continue
+                if x["target"] not in published:
+                    dup = (s.get("duplicate_of") or "").removeprefix("s:")
+                    x["action"], x["target"] = ("update", dup) if dup in published else ("publish", "")
+                if x["action"] == "update":
+                    if mr < min_score - 1:
+                        x["action"], x["reason"] = "skip", x["reason"] or "yeni gelişme yeterince önemli değil"
+                    elif x["target"] in round_targets or (x["target"] in refreshed and mr < 9):
+                        x["action"], x["reason"] = "skip", "haber az önce güncellendi"
+                    else:
+                        round_targets.add(x["target"])
+                    continue
+            if x["action"] != "publish":
+                continue
+            dup = (s.get("duplicate_of") or "").removeprefix("s:")
+            if dup in published:            # masa "aynı haber" dedi: yeni haber değil, olsa olsa güncelleme
+                ok = mr >= min_score and dup not in round_targets and (dup not in refreshed or mr >= 9)
+                x["action"], x["target"] = ("update", dup) if ok else ("skip", dup)
+                if ok:
+                    round_targets.add(dup)
+                continue
+            if mr < min_score:
+                x["action"], x["reason"] = "skip", f"önem {mr}/10, eşik {min_score}"
+            elif keys & round_keys:
+                x["action"] = "hold"
+            elif mr < 9 and any(day_keys.get(k, 0) >= cap for k in keys):
+                x["action"], x["reason"] = "skip", "aynı şirketten son 24 saatte haber var"
+            elif used >= slots:
+                x["action"] = "hold"
+            else:
+                used += 1
+                round_keys |= keys
+        return decisions
+
+    def _edit_log(self, q: dict, action: str, x: dict) -> None:
+        """Yönetmenin son kararları (/secki komutu ve günlük özet için)."""
+        lg = self.state.setdefault("edit_log", [])
+        lg.append({"t": iso(now_utc()), "topic": clip(q["story"].get("topic", ""), 90), "action": action,
+                   "score": x.get("must_read", 0), "reason": x.get("reason", ""), "target": x.get("target", "")})
+        del lg[:-200]
 
     def _queue(self, max_age: float) -> list[dict]:
@@ -366,4 +548,37 @@
             self.store.save_post(p)
         log.info("İlgi puanı verildi: %d haber", sum(1 for p in todo if p.get("appeal")))
+
+    def backfill_cover_lines(self, batch: int = 25) -> None:
+        """Kapak başlığı olmayan haberlere toplu kapak başlığı yaz (kapaklar ardından bu başlıkla yenilenir)."""
+        if not self.llm:
+            return
+        todo = [p for p in self.store.posts() if not p.get("cover_headline") and not p.get("cover_line_skip")][:batch]
+        if not todo:
+            return
+        try:
+            out = self.llm.json(self.cfg.get("ai", "writer_model", "gemini-flash-latest"),
+                                coverline_system(self.brand), coverline_user(todo), COVERLINE_SCHEMA, max_tokens=5000)
+        except LLMError as e:
+            log.warning("Kapak başlıkları alınamadı: %s", e)
+            return
+        got = {str(x.get("id")): x for x in (out.get("lines") or []) if isinstance(x, dict)}
+        n = 0
+        for p in todo:
+            line = self._cover_line((got.get(p["id"]) or {}).get("cover_headline"), (got.get(p["id"]) or {}).get("cover_highlight"))
+            if line:
+                p.update(line)
+                self.fixer.post(p)
+                n += 1
+            else:
+                p["cover_line_tries"] = int(p.get("cover_line_tries", 0)) + 1
+                if p["cover_line_tries"] >= 3:
+                    p["cover_line_skip"] = True
+            self.store.save_post(p)
+        log.info("Kapak başlığı yazıldı: %d haber", n)
+
+    @staticmethod
+    def _cover_ready(p: dict) -> bool:
+        """Kapak yenilemesi için kapak başlığı hazır mı (ya da artık beklenmiyor mu)."""
+        return bool(p.get("cover_headline") or p.get("cover_line_skip"))
 
     def _write(self, sources: list[dict], previous: dict | None = None, instruction: str | None = None) -> dict:
@@ -398,7 +613,20 @@
             "carousel_points": [clip(x.strip(), 130) for x in (out.get("carousel_points") or []) if x and x.strip()][:4],
             "appeal": self._appeal(out.get("appeal")),
+            "update_note": clip((out.get("update_note") or "").strip(), 160),
+            **self._cover_line(out.get("cover_headline"), out.get("cover_highlight")),
         }
         self.fixer.post(res)          # Türkçe karakter ve marka yazımı düzeltmeleri
         return res
+
+    @staticmethod
+    def _cover_line(head, hl) -> dict:
+        """Kapak başlığını denetle: çok uzunsa ya da boşsa kullanılmaz (kısa başlığa düşülür)."""
+        head = re.sub(r"\s+", " ", str(head or "")).strip().rstrip(".!?…")
+        hl = re.sub(r"\s+", " ", str(hl or "")).strip()
+        if not head or len(head) > 56 or len(head.split()) < 2:
+            return {}
+        if not hl or hl.lower() not in head.lower() or len(hl) >= len(head):
+            hl = ""
+        return {"cover_headline": head, "cover_highlight": hl}
 
     def create_draft(self, story: dict, its: list[dict]) -> dict:
@@ -420,6 +648,8 @@
             **w,
             "category": w["category"] or story.get("category") or DEFAULT_CATEGORY,
-            "importance": int(story.get("importance", 5)),
-            "triage_reason": story.get("reason", ""),
+            "importance": int(story.get("must_read") or story.get("importance", 5)),
+            "triage_reason": story.get("editor_reason") or story.get("reason", ""),
+            "entities": list(story.get("entities") or []),
+            "topic": story.get("topic", ""),
             "sources": [self._source_entry(it) for it in its],
             "source_keys": list(dict.fromkeys(it["source"] for it in its)),
@@ -444,4 +674,93 @@
             self._send_preview(d, "pending")
         return d
+
+    # ── mevcut haberi geliştirme ────────────────────────────
+    UPDATE_FIELDS = ("title", "summary", "body", "tags", "short_title", "kicker", "hero_stat", "hero_stat_label",
+                     "focus_keyword", "seo_title", "meta_description", "image_alt", "cover_text", "carousel_points",
+                     "cover_headline", "cover_highlight", "confidence", "flags", "editor_note")
+
+    def create_update(self, post: dict, story: dict, its: list[dict]) -> dict | None:
+        """Yayındaki habere yeni gelişme geldi: yeni haber yerine güncelleme taslağı (onaylanınca haber yerinde güncellenir)."""
+        cfg, st = self.cfg, self.store
+        known = {x["url"] for x in post.get("sources") or []}
+        its = [it for it in sorted(its, key=lambda x: KIND_ORDER.get(x["kind"], 3)) if it["url"] not in known][:3]
+        if not its:
+            return None
+        texts = []
+        for it in its:
+            txt = ""
+            if cfg.get("editorial", "fetch_full_text", True) and not cfg.mock and not cfg.fixtures_dir:
+                txt = full_text(it["url"])
+            texts.append({"credit": it["credit"], "kind": it["kind"], "title": it["title"], "url": it["url"],
+                          "published": it.get("published"), "summary": it.get("summary", ""), "text": txt})
+        prev = {"_update": True, "title": post["title"], "summary": post["summary"], "body": post["body"]}
+        w = self._write(texts, previous=prev)
+        did = short_hash("u", post["id"], *sorted(it["key"] for it in its))
+        d = {
+            "id": did,
+            "status": "pending",
+            "update_of": post["id"],
+            "created_at": iso(now_utc()),
+            **w,
+            "category": post.get("category") or w["category"] or DEFAULT_CATEGORY,
+            "importance": int(story.get("must_read") or story.get("importance", 5)),
+            "triage_reason": story.get("editor_reason") or story.get("reason", ""),
+            "entities": list(story.get("entities") or post.get("entities") or []),
+            "topic": story.get("topic", ""),
+            "sources": [self._source_entry(it) for it in its],
+            "source_keys": list(dict.fromkeys(it["source"] for it in its)),
+            "source_texts": texts,
+            "rewrites": 0,
+            "telegram": {},
+            "image": dict(post.get("image") or {}),
+        }
+        st.bump(self.today(), "updates")
+        decision, reason = policy.decide(cfg, self.state, self.stats, d)
+        d["policy_reason"] = reason
+        log.info("Güncelleme taslağı %s → %s: %s (%s)", did, post["id"], decision, reason)
+        if decision == "auto" and not self.state.get("paused"):
+            new = self.apply_update(d)
+            if new:
+                self._send_preview({**d, "slug": new["slug"]}, "updated")
+        else:
+            st.save_draft(d)
+            self._send_preview(d, "pending")
+        return d
+
+    def apply_update(self, d: dict) -> dict | None:
+        """Güncelleme taslağını yayındaki habere işle: adres aynı kalır, yeni kaynaklar eklenir, kapak yeni başlıkla yenilenir."""
+        st = self.store
+        post = st.load_post(d.get("update_of") or "")
+        if not post:
+            return None
+        for k in self.UPDATE_FIELDS:
+            if d.get(k) not in (None, "", []):
+                post[k] = d[k]
+        known = {x["url"] for x in post.get("sources") or []}
+        post["sources"] = (post.get("sources") or []) + [x for x in d.get("sources") or [] if x["url"] not in known]
+        post["source_keys"] = list(dict.fromkeys((post.get("source_keys") or []) + (d.get("source_keys") or [])))
+        now = iso(now_utc())
+        post["updated_at"] = post["refreshed_at"] = now
+        post.setdefault("updates", []).append({"at": now, "note": d.get("update_note") or "",
+                                               "sources": list(dict.fromkeys(x["name"] for x in d.get("sources") or []))})
+        post["importance"] = max(int(post.get("importance") or 0), int(d.get("importance") or 0))
+        if d.get("appeal"):
+            post["appeal"] = max(int(post.get("appeal") or 0), int(d["appeal"]))
+        if d.get("entities") and not post.get("entities"):
+            post["entities"] = d["entities"]
+        try:
+            if post.get("photos") and (post.get("image") or {}).get("source") == "photo":
+                self._build_cover(post, draft=False)
+            elif (post.get("image") or {}).get("source") in ("cover", "fallback", None):
+                post["image"] = {**self.vis.make_hero(post, st.post_image(post["id"])), "cover_v": COVER_VERSION}
+            self._make_og(post)
+        except Exception as e:  # noqa: BLE001
+            log.warning("Güncellenen haberin kapağı yenilenemedi (%s): %s", post["id"], e)
+        st.save_post(post)
+        self.queue_indexnow(self.cfg.post_url(post["slug"]))
+        st.draft_path(d["id"]).unlink(missing_ok=True)
+        st.bump(self.today(), "updated")
+        log.info("Haber güncellendi: %s", post["id"])
+        return post
 
     def _credits(self, d: dict) -> list[str]:
@@ -505,8 +824,18 @@
             "removed": "🗑 <b>SİTEDEN KALDIRILDI</b>",
             "rewritten": "🔁 <b>YENİDEN YAZILDI</b> (yeni sürüm aşağıda)",
+            "updated": "🔄 <b>HABER GÜNCELLENDİ</b>",
         }[kind]
+        upd = d.get("update_of")
+        if upd and kind == "pending":
+            head = "🔄 <b>GÜNCELLEME ÖNERİSİ</b> (yeni haber değil, mevcut haber geliştirilir)"
         meta = f"🏷 {esc(category_label(d['category']))} · Önem {d.get('importance', '?')}/10 · Güven {CONF_LABEL.get(d.get('confidence'), '?')}"
-        lines = [head, "", f"<b>{esc(d['title'])}</b>", "", "{SUMMARY}", "",
-                 "📰 " + esc(", ".join(self._credits(d))), meta]
+        lines = [head, "", f"<b>{esc(d['title'])}</b>", "", "{SUMMARY}", ""]
+        if upd and kind in ("pending", "updated", "rejected", "expired"):
+            orig = self.store.load_post(upd) or {}
+            if orig.get("title") and orig.get("title") != d.get("title"):
+                lines.append(f"📌 Mevcut haber: <i>{esc(clip(orig['title'], 110))}</i>")
+            if d.get("update_note"):
+                lines.append(f"🆕 {esc(d['update_note'])}")
+        lines += ["📰 " + esc(", ".join(self._credits(d))), meta]
         if d.get("focus_keyword") and kind in ("pending", "auto"):
             lines.append(f"🔎 Google: <i>{esc(d['focus_keyword'])}</i>")
@@ -519,5 +848,5 @@
         if kind == "pending" and d.get("policy_reason"):
             lines.append(f"<i>Neden sordum: {esc(d['policy_reason'])}</i>")
-        if kind in ("published", "auto"):
+        if kind in ("published", "auto", "updated") and d.get("slug"):
             lines.append(f'🔗 <a href="{esc(self.cfg.post_url(d["slug"]))}">Sitede aç</a>')
         cap = "\n".join(lines)
@@ -528,4 +857,17 @@
         did = d["id"]
         src = d["sources"][0]["url"] if d.get("sources") else None
+        if kind == "pending" and d.get("update_of"):
+            kb = [[{"text": "🔄 Güncelle", "callback_data": f"p:{did}"},
+                   {"text": "❌ Reddet", "callback_data": f"r:{did}"}],
+                  [{"text": "📄 Tam metin", "callback_data": f"f:{did}"},
+                   {"text": "🔁 Yeniden yaz", "callback_data": f"w:{did}"}]]
+            orig = self.store.load_post(d["update_of"])
+            links = ([{"text": "🔗 Mevcut haber", "url": self.cfg.post_url(orig["slug"])}] if orig else []) + \
+                    ([{"text": "🔗 Yeni kaynak", "url": src}] if src else [])
+            if links:
+                kb.append(links)
+            return kb
+        if kind == "updated":
+            return [[{"text": "🔗 Haberi aç", "url": self.cfg.post_url(d["slug"])}]] if d.get("slug") else []
         if kind == "pending":
             kb = [[{"text": "✅ Yayınla", "callback_data": f"p:{did}"},
@@ -553,5 +895,8 @@
         st = self.store
         try:
-            img = self._hero(d) if d.get("photos") and self._hero(d).exists() else self._card(d, "post")
+            if d.get("update_of") and st.post_image(d["update_of"]).exists():
+                img = st.post_image(d["update_of"])       # güncelleme: haberin mevcut kapağı
+            else:
+                img = self._hero(d) if d.get("photos") and self._hero(d).exists() else self._card(d, "post")
         except Exception as e:  # noqa: BLE001
             log.warning("Önizleme kartı üretilemedi: %s", e)
@@ -572,4 +917,6 @@
         except OSError as e:
             log.warning("Önizleme görseli okunamadı: %s", e)
+            return
+        if kind == "updated":
             return
         d.setdefault("telegram", {})["message_id"] = res.get("message_id")
@@ -714,4 +1061,16 @@
         if not d:
             return "Bu haber artık yok."
+        if action in ("p", "P") and where == "draft" and d.get("update_of"):
+            if d.get("status") not in ("pending", "rejected"):
+                return "Bu taslak kapanmış."
+            if d.get("status") == "rejected":
+                self._undo_decision(d)
+            post = self.apply_update(d)
+            if not post:
+                st.archive_draft(d, "expired")
+                return "Asıl haber artık yayında değil."
+            policy.record(self.stats, d, ok=True)
+            self._update_preview({**d, "slug": post["slug"]}, "updated")
+            return "🔄 Haber güncellendi"
         if action == "P":                     # yayınla ve manşete al
             if where == "post":
@@ -892,6 +1251,6 @@
         if new_visual:
             text = visual_only.strip()
-            if text and len(text) <= 24:   # kısa ifade: kapaktaki büyük yazı olsun (fotoğraflı kapakta da)
-                d["cover_text"] = text
+            if text and len(text) <= 56:   # kısa ifade: kapak başlığı olsun (fotoğraflı kapakta da)
+                d["cover_headline"], d["cover_highlight"] = text, ""
                 d["cover_variant"] = int(d.get("cover_variant", 0)) + 1
             elif text:                      # uzun ifade: yapay zeka görseli sahnesi
@@ -970,4 +1329,6 @@
         elif cmd == "kaynaklar":
             self.notify(self.sources_text(), silent=True)
+        elif cmd in ("secki", "seçki"):
+            self.notify(self.edit_text(), silent=True)
         elif cmd in ("manset", "manşet"):
             res = self.tg.send_message(self.chat_id, self._manset_text(), keyboard=self._manset_keyboard(), silent=True)
@@ -988,4 +1349,22 @@
     def _cost(self, c: dict) -> float:
         return c.get("cost_usd", 0) + c.get("images", 0) * float(self.cfg.get("images", "cost_per_image", 0.035))
+
+    def edit_text(self) -> str:
+        """/secki: yayın yönetmeninin son kararları."""
+        lg = self.state.get("edit_log") or []
+        if not lg:
+            return "Henüz karar yok."
+        icon = {"publish": "✅", "update": "🔄", "merge": "➕", "skip": "⏭", "hold": "⏳"}
+        label = {"publish": "yazılıyor", "update": "güncelleme", "merge": "kaynak eklendi", "skip": "elendi", "hold": "bekliyor"}
+        lines = ["🧭 <b>Yayın yönetmeni — son kararlar</b>"]
+        for x in reversed(lg[-20:]):
+            why = f" — {esc(x['reason'])}" if x.get("reason") else ""
+            lines.append(f"{icon.get(x['action'], '•')} <b>{x.get('score', 0)}</b>/10 {esc(clip(x.get('topic', ''), 70))} "
+                         f"<i>({label.get(x['action'], x['action'])}{why})</i>")
+        today = [x for x in lg if (x.get("t") or "")[:10] == iso(now_utc())[:10]]
+        if today:
+            n = {k: sum(1 for x in today if x["action"] == k) for k in ("publish", "update", "skip")}
+            lines.append(f"\nBugün: {n['publish']} seçildi, {n['update']} güncelleme, {n['skip']} elendi")
+        return "\n".join(lines)
 
     def status_text(self) -> str:
@@ -1101,5 +1480,5 @@
         todo = [p for p in self.store.posts()
                 if (p.get("image") or {}).get("source") in ("cover", "fallback", None)
-                and (p.get("image") or {}).get("cover_v") != COVER_VERSION][:limit]
+                and (p.get("image") or {}).get("cover_v") != COVER_VERSION and self._cover_ready(p)][:limit]
         for p in todo:
             try:
@@ -1125,5 +1504,8 @@
         text = (f"🌙 <b>Günün özeti</b>\n"
                 f"Yayın: {c.get('published', 0)} ({c.get('auto', 0)} otomatik, {c.get('approved', 0)} senin onayınla)\n"
+                f"Güncellenen haber: {c.get('updated', 0)}\n"
                 f"Ret: {c.get('rejected', 0)} · Süresi dolan: {c.get('expired', 0)} · Kaldırılan: {c.get('removed', 0)}\n"
+                f"Seçki: {sum(1 for x in self.state.get('edit_log') or [] if (x.get('t') or '')[:10] == iso(now_utc())[:10] and x['action'] == 'skip')} "
+                f"aday elendi (/secki)\n"
                 f"Instagram: {c.get('instagram', 0)} paylaşım\n"
                 f"Tahmini maliyet: ${self._cost(c):.2f} ({c.get('images', 0)} yapay zeka görseli)\n"
@@ -1614,5 +1996,6 @@
                 return False
             img = p.get("image") or {}
-            return p.get("photos_v") != self.PHOTOS_V or (img.get("source") == "photo" and img.get("cover_v") != PHOTO_COVER_VERSION)
+            return p.get("photos_v") != self.PHOTOS_V or (img.get("source") == "photo" and img.get("cover_v") != PHOTO_COVER_VERSION
+                                                          and self._cover_ready(p))
         todo = [p for p in self.store.posts() if due(p)][:limit]
         for p in todo:
@@ -1672,4 +2055,5 @@
                 self.fix_texts()
                 self.backfill_appeal()
+                self.backfill_cover_lines()
             except Exception as e:  # noqa: BLE001
                 log.exception("Metin/ilgi puanı hatası: %s", e)
--- a/haberbot/covers.py
+++ b/haberbot/covers.py
@@ -1,9 +1,10 @@
 """Tipografik haber kapakları: her habere özel renk, düzen ve tek bir güçlü öğe.
 
+Kapakta her zaman habere özel "kapak başlığı" yazar (3–7 sözcük, vurucu kısmı renkli): tek başına bir ad ya da rakam
+okuyucuya bir şey anlatmaz, başlık anlatır.
 Düzenler
-  sayi   : haberin kalbindeki rakam dev boyutta ("311 milyon $", "%40")
-  isim   : öne çıkan ürün / model / şirket adı dev boyutta ("GPT‑6 Astra", "Opus 5.5")
-  manset : açık zeminde afiş gibi büyük başlık, anahtar sözcük renkli
+  manset : afiş gibi büyük kapak başlığı, vurucu kısım renkli (varsayılan)
   isik   : karanlıkta ışık huzmesi ve başlık (regülasyon, güvenlik gibi ciddi konular)
+  sayi / isim : eski düzenler (dev rakam / dev ad); yalnızca sosyal medya "kapak" kart tarzında kalır
 
 Logo ya da marka işareti kullanılmaz; yalnızca metin, renk ve ışık.
@@ -41,5 +42,5 @@
 
 
-COVER_VERSION = 1
+COVER_VERSION = 2
 
 
@@ -80,4 +81,13 @@
 
 
+def cover_line(d: dict) -> tuple[str, str]:
+    """(kapak başlığı, renkli vurgu). Kapak başlığı yoksa kısa başlık; vurgu yoksa kapaktaki ad."""
+    head = (d.get("cover_headline") or "").strip() or (d.get("short_title") or d.get("title") or "").strip()
+    hl = (d.get("cover_highlight") or "").strip()
+    if not hl or hl.lower() not in head.lower():
+        hl = cover_word(d)
+    return head, hl
+
+
 # Her kategori kendi renk ailesinde kalır; aynı aile içinde habere göre ton değişir.
 # Sıra: açık vurgu, ana renk, koyu ton, ara ton, koyu zemin, açık zemin
@@ -180,15 +190,21 @@
     variant = "center"
     pick = seed % 6
-    if stat and len(stat) <= 12 and not (word and pick in (1, 4)):
-        layout = "sayi"
-        tone, variant = [("dark", "center"), ("light", "left"), ("vivid", "center"),
-                         ("dark", "center"), ("light", "left"), ("vivid", "left")][pick]
-    elif word:
-        layout = "isim"
-        tone = ["vivid", "light", "dark", "vivid", "light", "vivid"][pick]
+    line, hl = cover_line(d)
+    if caption:   # sosyal medya "kapak" kart tarzı: eski düzen (dev rakam / ad + altta kısa başlık)
+        if stat and len(stat) <= 12 and not (word and pick in (1, 4)):
+            layout = "sayi"
+            tone, variant = [("dark", "center"), ("light", "left"), ("vivid", "center"),
+                             ("dark", "center"), ("light", "left"), ("vivid", "left")][pick]
+        elif word:
+            layout = "isim"
+            tone = ["vivid", "light", "dark", "vivid", "light", "vivid"][pick]
+        elif serious:
+            layout, tone = "isik", "dark"
+        else:
+            layout, tone = "manset", ["light", "vivid"][pick % 2]
     elif serious:
         layout, tone = "isik", "dark"
     else:
-        layout, tone = "manset", ["light", "vivid"][pick % 2]
+        layout, tone = "manset", ["light", "vivid", "dark", "vivid", "light", "dark"][pick]
 
     base = {"dark": "#040405", "light": pal[5], "vivid": pal[1]}[tone]
@@ -201,6 +217,9 @@
     if kw.lower() in GENERIC or len(kw.split()) > 3 or kw.lower().startswith("yapay zeka"):
         kw = ""
-    headline = _highlight(d.get("short_title") or d.get("title", ""), word or kw) if not serious else html.escape(d.get("short_title") or d.get("title", ""))
-    glyph = (word or re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşü]", "", d.get("short_title") or d.get("title") or "Y") or "Y")[:1].upper()
+    if caption:
+        headline = _highlight(d.get("short_title") or d.get("title", ""), word or kw) if not serious else html.escape(d.get("short_title") or d.get("title", ""))
+    else:
+        headline = _highlight(line, hl or word or kw)
+    glyph = (hl or word or re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşü]", "", line or "Y") or "Y")[:1].upper()
     return {
         "layout": layout, "tone": tone, "pal": pal[:4] + [base], "palette": pal_name, "seed": seed,
@@ -214,5 +233,5 @@
 
 # ── Fotoğraflı kapak ─────────────────────────────────────────
-PHOTO_COVER_VERSION = 1
+PHOTO_COVER_VERSION = 2
 
 
@@ -222,17 +241,12 @@
     stat = (d.get("hero_stat") or "").strip()
     word = cover_word(d)
-    if stat and len(stat) <= 12:
-        layout = "sayi"
-    elif word:
-        layout = "isim"
-    else:
-        layout = "manset"
+    layout = "manset"
     kw = d.get("focus_keyword") or ""
     if kw.lower() in GENERIC or len(kw.split()) > 3 or kw.lower().startswith("yapay zeka"):
         kw = ""
-    title = d.get("short_title") or d.get("title", "")
+    line, hl = cover_line(d)
     return {
         "layout": layout, "pal": pal[:4], "stat": stat, "stat_label": (d.get("hero_stat_label") or "").strip(),
-        "word": word, "headline": _highlight(title, word or kw), "title": title,
+        "word": word, "headline": _highlight(line, hl or word or kw), "title": line,
         "kicker": kicker, "brand": brand, "brand_name": brand_name, "credit": credit,
         "focus": d.get("photo_focus") or "50% 42%",
--- a/haberbot/llm.py
+++ b/haberbot/llm.py
@@ -326,4 +326,20 @@
         if "stories" in schema.get("properties", {}):
             return self._triage(user)
+        if "decisions" in schema.get("properties", {}):   # yayın yönetmeni: masanın puanına göre
+            out = []
+            for ln in user.split("CANDIDATES:", 1)[-1].splitlines():
+                m = re.match(r"(c\d+) \| [^|]* \| desk importance (\d+)", ln.strip())
+                if m:
+                    imp = int(m.group(2))
+                    same = re.search(r"same as: (\w+)", ln)
+                    act = ("update" if imp >= 8 else "skip") if same else ("publish" if imp >= 8 else "skip")
+                    out.append({"cid": m.group(1), "action": act, "target": same.group(1) if same else "",
+                                "must_read": imp, "reason": "Test modu kararı"})
+            return {"decisions": out}
+        if "lines" in schema.get("properties", {}):       # kapak başlıkları
+            return {"lines": [{"id": ln.split(" | ")[0].strip(),
+                               "cover_headline": " ".join(ln.split(" | ")[1].split()[:5]),
+                               "cover_highlight": ln.split(" | ")[1].split()[0]}
+                              for ln in user.splitlines() if " | " in ln]}
         if "scores" in schema.get("properties", {}):     # ilgi puanı
             return {"scores": [{"id": ln.split(" | ")[0].strip(), "appeal": 6 + len(ln) % 3}
@@ -358,5 +374,5 @@
             stories.append({"item_ids": [tid], "topic": title[:60], "on_topic": True,
                             "duplicate_of": "", "importance": imp, "category": self._cat(title),
-                            "reason": "Test modu puanı"})
+                            "entities": [credit.split(" (")[0]], "reason": "Test modu puanı"})
         return {"stories": stories}
 
@@ -392,4 +408,7 @@
             "image_alt": f"{title[:80]} haberini temsil eden 3D görsel",
             "appeal": 7 if kind == "official" else 6,
+            "cover_headline": " ".join(title.split()[:5]),
+            "cover_highlight": title.split()[0] if title.split() else "",
+            "update_note": "Yeni gelişme eklendi (test)." if "PREVIOUS ARTICLE" in user else "",
             "carousel_points": [f"{credit} bu gelişmeyi duyurdu (test maddesi).",
                                 "Gerçek kurulumda burada kaynaktan alınan somut bir bilgi yer alır.",
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -41,8 +41,9 @@
                     "importance": {"type": "integer"},
                     "category": {"type": "string", "enum": CATEGORY_KEYS},
+                    "entities": {"type": "array", "items": {"type": "string"}},
                     "reason": {"type": "string"},
                 },
                 "required": ["item_ids", "topic", "on_topic", "duplicate_of",
-                             "importance", "category", "reason"],
+                             "importance", "category", "entities", "reason"],
                 "additionalProperties": False,
             },
@@ -55,38 +56,48 @@
 
 def triage_system(site_name: str) -> str:
-    return f"""You are the news-desk editor of "{site_name}", a Turkish-language news site about technology, innovation,
-startups, artificial intelligence, new products, cars and the gaming world, covering both the world and Turkey.
-Readers are curious Turkish people who want to know what is genuinely new: a product that was just unveiled, a startup
-with an interesting story, a technology tried for the first time, a new AI feature, a new car, a big game release.
-You receive a batch of NEW ITEMS fetched from RSS feeds and a list of RECENT STORIES we already have.
+    return f"""You are the news-desk editor of "{site_name}", a Turkish-language, hand-curated daily briefing about AI,
+consumer tech, cars/EVs, innovation, startups and the gaming world, covering both the world and Turkey.
+Our readers follow these fields closely and open the site every day to see the developments that matter in THEIR field.
+We are not a news aggregator: we publish only about 10 carefully chosen stories a day across all verticals, and we never
+publish the same development twice. You receive a batch of NEW ITEMS fetched from RSS feeds and a list of RECENT STORIES
+(published, pending, queued, and recently rejected or expired ones).
 
 Do the following:
-1. Group items that report the same underlying event into ONE story (a company's own announcement and media coverage of it,
-   or an English and a Turkish report of the same event, are the same story). Every item id must appear in exactly one story.
+1. Group items that report the same underlying event into ONE story. Same event includes: a company's own announcement and
+   media coverage of it; English and Turkish reports; and everything announced at the same launch event or in the same
+   announcement wave (a phone, watch and tablet unveiled together by one brand = ONE story). Every item id must appear in
+   exactly one story.
 2. on_topic: true only if the story is substantially about technology, AI, consumer tech products, startups/venture funding,
    innovation/science breakthroughs, cars/EVs/mobility, video games/gaming industry, or big-tech business/policy/security.
-   false for general politics, war, crime, celebrity/entertainment (films, TV, comics) unless the story is about technology or games,
-   traditional sports (esports is on topic), personal finance, lifestyle.
-3. duplicate_of: if the story is the same event as one of the RECENT STORIES, write that story id (e.g. "s:ab12cd34ef" or "q:3"); otherwise "".
-4. importance (integer 1–10) for this audience. First apply the GENERAL-READER TEST: could a curious Turkish reader who is
-   not an engineer, developer or investor understand in one sentence why this matters, and would they tell a friend about it?
-   If not, the score is at most 5 — however "big" it is for insiders. We publish a small, hand-picked selection
-   (about 10–20 stories a day), so favour things people will use, buy, drive, play or talk about, famous names,
-   surprising "first time" moments and stories with a human angle.
-   Always ≤5: B2B/enterprise software, developer tools, APIs and SDKs, cloud/infrastructure deals, chips and data centres
-   (unless it reaches consumers), minor model versions, benchmarks, research papers without a clear everyday impact,
-   funding rounds of little-known B2B startups, earnings details, executive moves, spec-only updates, minor car trims.
-   9–10 events dominating global tech news: flagship launches from Apple/Samsung/Google, frontier AI model releases,
-        >$1B deals or acquisitions, landmark regulation, a new console generation, a hugely anticipated game (e.g. its release date)
-   7–8 notable new consumer products officially unveiled; new AI features ordinary people can use; startups with a
-        genuinely interesting, easy-to-explain idea or a very large round; a technology demonstrated or tried for the
-        first time; new car/EV models people will talk about; big game launches, studio acquisitions or layoffs;
-        policy or security events that affect everyday users;
-        noteworthy news about Turkey (Turkish startup rounds, TOGG, Turkish game studios, big local launches) — Turkish news
-        gets +1 compared with a similar foreign story
-   5–6 incremental updates, smaller funding rounds, niche research, routine partnerships, minor game updates or DLC, facelifts
-   1–4 rumors and leaks without an official source, spy photos, deals/discounts/"free this week", reviews, buying guides,
-        how-tos, listicles, opinion columns, podcasts, event or webinar promotion, sponsored content, trailers without news,
-        patch notes, recalls without wider impact, hiring posts
+   false for general politics, war, defence exercises, crime, celebrity/entertainment (films, TV, comics) unless the story is
+   about technology or games, traditional sports (esports is on topic), personal finance, lifestyle.
+3. duplicate_of: if the story is the same event as, or a follow-up/reaction/re-report of, one of the RECENT STORIES (whatever
+   its status, including rejected and expired), write that story id (e.g. "s:ab12cd34ef" or "q:3"); otherwise "".
+   Follow-ups count as the same story: local availability or price of an already covered product, hands-on or review of it,
+   reactions, analysis, more details about the same announcement.
+4. importance (integer 1–10). THE TEST: would a person who follows this vertical closely (an AI practitioner, a phone and
+   gadget enthusiast, a car/EV enthusiast, a startup/VC watcher, a gamer) consider this one of TODAY's must-know developments
+   in their field — something they would be annoyed to miss? Most items fail this test.
+   9–10 the day's defining stories: frontier AI model releases or major capability jumps; flagship launches (iPhone, Galaxy S/Z,
+        Pixel, new PlayStation/Xbox/Nintendo hardware); landmark regulation or court rulings that change an industry; >$1B
+        acquisitions or rounds; genuine first-ever achievements (e.g. a rocket reaching orbit for the first time); the release
+        date or reveal of a hugely anticipated game
+   8    clearly significant: a new product or model from a leading company that moves its category; a new AI capability many
+        people will actually use; a major strategic move by a big company; a security incident affecting many users; an
+        important Turkish tech development (TOGG, a large Turkish startup round, a regulation affecting a big platform in
+        Türkiye); a major game announcement or a studio shake-up
+   7    noteworthy for followers but not essential: notable launches outside the top tier, a startup with a sizeable round and a
+        clear, interesting idea, research with a clear path to real products
+   ≤6   everything else, in particular: regional availability or local price of already announced products (except true
+        flagships arriving in Türkiye), mid-range and budget devices, secondary product lines (watches, bands, earbuds, tablets,
+        accessories) unless genuinely novel, launch-date teasers, unboxings, hands-ons, camera samples, benchmarks, spec leaks
+        and rumors, concept cars, design studies and show displays, trims and facelifts, lab or university research without a
+        near-term product, executive opinions and interviews, partnerships and MoUs, recalls, awards and competitions,
+        stock and market moves, deals and discounts, reviews, guides, listicles, podcasts, events and webinars, B2B/enterprise
+        software, developer tools, cloud and data-centre deals, minor model versions
+   Company saturation: if RECENT STORIES already contain a story about the same company or product family from the last
+   24 hours, a new story about it gets importance ≤6 unless it is a separate and clearly bigger development (then ≥8).
+   Be strict and honest; do not inflate scores. Judge each vertical on its own scale so that games and cars are not crowded
+   out by AI, and AI does not crowd out everything else.
 5. category: one of {CATEGORY_KEYS}. Guide: {CATEGORY_HELP}.
    Stories about Turkey go to their topical category (a Turkish game studio's funding round → girisimcilik or gaming).
@@ -95,8 +106,9 @@
    feature inside a product of Google, Microsoft or Apple. A startup's funding round is "girisimcilik" (even an AI startup).
    A game or gaming platform is "gaming". Military and defence technology is "inovasyon" only if it is a genuine
-   first-of-its-kind technology; otherwise it is usually off topic for our readers.
-6. topic: a short neutral English label for the event. reason: ≤15 words in Turkish explaining the score.
-Be strict and selective: most items are NOT important. Do not inflate scores. Judge each vertical on its own scale so that games and
-cars are not crowded out by AI, and AI does not crowd out everything else."""
+   first-of-its-kind technology; otherwise it is off topic for our readers.
+6. entities: the 1–3 main companies, brands or products the story is about, most important first, in their official
+   original spelling (e.g. ["Honor", "Honor Magic9"], ["OpenAI"], ["SpaceX", "Starship"]). Not people's names unless the
+   story is about the person.
+7. topic: a short neutral English label for the event. reason: ≤15 words in Turkish explaining the score."""
 
 
@@ -113,4 +125,79 @@
         summ = (it.get("summary") or "")[:260]
         lines.append(f"{it['tid']} | {it['credit']} ({it['kind']}) | {date} | {it['title']} | {summ}")
+    return "\n".join(lines)
+
+
+# ── 1b) Yayın yönetmeni: günün seçkisi ────────────────────────
+EDIT_SCHEMA = {
+    "type": "object",
+    "properties": {
+        "decisions": {
+            "type": "array",
+            "items": {
+                "type": "object",
+                "properties": {
+                    "cid": {"type": "string"},
+                    "action": {"type": "string", "enum": ["publish", "update", "skip", "hold"]},
+                    "target": {"type": "string"},
+                    "must_read": {"type": "integer"},
+                    "reason": {"type": "string"},
+                },
+                "required": ["cid", "action", "target", "must_read", "reason"],
+                "additionalProperties": False,
+            },
+        }
+    },
+    "required": ["decisions"],
+    "additionalProperties": False,
+}
+
+
+def edit_system(site_name: str, min_score: int) -> str:
+    return f"""You are the editor-in-chief of "{site_name}", a Turkish-language, hand-curated daily briefing about AI, consumer
+tech, cars/EVs, innovation, startups and gaming. Readers follow these fields closely and come back every day to see the
+developments that matter in their field. The site must feel selective and fresh: a small number of must-know stories,
+never two stories about the same thing, never a feed full of one brand.
+
+You receive COVERED stories (what we already published, what is waiting for approval, and what the editor rejected) and
+CANDIDATES proposed by the news desk. Decide for EVERY candidate:
+- "publish": a new must-know story for its field. Allowed only if must_read ≥ {min_score}.
+- "update": the candidate is the same story or a direct follow-up of a PUBLISHED covered story AND it brings a substantial
+  new development (official confirmation, a regulator or court acting, price/date/availability announced for the first
+  time, a major new fact that changes the story). Put the covered story id in target. We will update that article
+  instead of publishing a new one.
+- "skip": not a must-know story; or the same/very similar to a covered story without a substantial new development; or
+  about a company/product family we already covered in the last 24 hours and not clearly one of the day's biggest stories;
+  or a follow-up of a story the editor rejected.
+- "hold": a good story that does not fit into this round's free slots; it may be reconsidered in a later round.
+must_read (1–10): would a close follower of this vertical consider it one of TODAY's must-know developments?
+9–10 the day's defining stories; 8 clearly significant for the field; 7 noteworthy but not essential; ≤6 routine.
+Most candidates are 6–7. Regional availability or local prices, secondary products (watches, earbuds, tablets, budget
+phones), teasers, unboxings, rumors, concept/design displays, lab research without products, opinions and minor updates
+are ≤6.
+Rules:
+- At most SLOTS "publish" decisions in this round; if more qualify, publish the strongest and "hold" the rest.
+- Diversity: never publish two candidates about the same company in one round; prefer spreading across verticals.
+- Duplicates among candidates: publish at most one of them.
+- target: the covered story id for "update" (e.g. "ab12cd34ef"), the most similar covered id for a duplicate "skip", else "".
+- reason: ≤12 words in Turkish."""
+
+
+def edit_user(now: str, slots: int, today_count: int, daily_target: int, covered: list[dict],
+              candidates: list[dict]) -> str:
+    lines = [f"NOW: {now}", f"SLOTS: {slots}",
+             f"PUBLISHED OR PENDING TODAY: {today_count} (daily target about {daily_target})", "",
+             "COVERED (id | status | age | category | entities | title):"]
+    if covered:
+        for c in covered:
+            lines.append(f"{c['id']} | {c['status']} | {c['age']} | {c['category']} | {', '.join(c.get('entities') or [])} | {c['title']}")
+    else:
+        lines.append("(none)")
+    lines += ["", "CANDIDATES:"]
+    for c in candidates:
+        same = f" | news desk says same as: {c['dup']}" if c.get("dup") else ""
+        lines.append(f"{c['cid']} | {c['category']} | desk importance {c['importance']} | {', '.join(c.get('entities') or [])} | "
+                     f"{c['topic']}{same}")
+        for h in c["headlines"][:4]:
+            lines.append(f"    - {h}")
     return "\n".join(lines)
 
@@ -142,9 +229,12 @@
         "carousel_points": {"type": "array", "items": {"type": "string"}},
         "appeal": {"type": "integer"},
+        "cover_headline": {"type": "string"},
+        "cover_highlight": {"type": "string"},
+        "update_note": {"type": "string"},
     },
     "required": ["title", "summary", "body", "category", "tags", "confidence", "flags", "editor_note",
                  "short_title", "kicker", "hero_stat", "hero_stat_label", "visual_style", "visual_scene",
                  "focus_keyword", "seo_title", "meta_description", "slug", "image_alt", "cover_text", "carousel_points",
-                 "appeal"],
+                 "appeal", "cover_headline", "cover_highlight", "update_note"],
     "additionalProperties": False,
 }
@@ -195,8 +285,21 @@
 - appeal: integer 1–10, how strongly a broad Turkish audience (curious about technology, not specialists) would want to click and share this story. 9–10: huge mainstream news everyone talks about (a new iPhone or PlayStation, GTA 6 date, a major AI launch, big Türkiye tech news); 7–8: notable news about well-known brands, products, games, cars or surprising records; 5–6: interesting but niche; 1–4: specialist or industry-only. Be strict and honest; most stories are 5–7.
 
+Cover fields (the big text printed on the article's cover image on the homepage, in feeds and on Instagram; it must make
+a scrolling reader stop and want to read — the cover is our headline):
+- cover_headline: a hook of 3–7 words, ≤42 characters, in Turkish, that makes sense on its own without the title: the key
+  name (company/product/game/car) or the key number plus what is new or surprising. Factual and grounded in the sources;
+  no question marks, no exclamation marks, no ellipsis, no emojis, no clickbait teasing ("şok", "inanılmaz", "herkes
+  bunu konuşuyor"). Word it differently from the title; sentence case. Never just a name or just a number.
+  Examples of the style (do not reuse): "Starship ilk kez yörüngede", "TikTok'ta gençlere 2 saat sınırı",
+  "Apple'a 5,7 milyar dolar ceza", "Honor'dan 11.000 mAh'lik pil", "OpenAI en güçlü modelini durdurdu".
+- cover_highlight: 1–3 consecutive words copied exactly from cover_headline that carry the punch (the number, the key
+  name or the twist); they are coloured on the cover.
+- update_note: "" normally. Only when the input contains a PREVIOUS ARTICLE marked as an update: one Turkish sentence
+  (≤140 characters) saying what is new in this update.
+
 Social/visual fields (used on Instagram cards and the site; the design is bold, colourful and premium, like an Apple product page):
 - short_title: ≤55 characters, punchy Turkish headline for social cards; still factual, no clickbait, no emojis. Sentence case.
 - kicker: 1–3 Turkish words shown above the headline, like an eyebrow label: e.g. "Yeni ürün", "Lansman", "Yatırım turu", "Girişim hikâyesi", "İlk test", "Yeni model", "Elektrikli araç", "Yeni oyun", "Güvenlik", "Regülasyon".
-- hero_stat: if ONE number is the heart of the story and appears in the sources (money, price, range in km, battery, percentage, user or player count, sales), write it compactly in Turkish format, ≤12 characters: "3,5 milyar $", "30 milyar", "%40", "1 milyon". Otherwise "". Never invent or round beyond the source.
+- hero_stat: only if ONE number IS the news itself and appears in the sources (the price of the new product, the funding amount, a fine, a record, a range or battery figure that is the headline feature, a user or player count), write it compactly in Turkish format, ≤12 characters: "3,5 milyar $", "30 milyar", "%40", "1 milyon". Otherwise "" — never a year, a date, a model count, a version number, a scale like "1:1" or a side detail. Never invent or round beyond the source.
 - hero_stat_label: ≤30 Turkish characters explaining the number ("yatırım tutarı", "menzil", "başlangıç fiyatı", "oyuncu sayısı"); "" if no hero_stat.
 - visual_style: pick the style that best fits AND varies from a generic look: studio (one sculptural object), macro (material close-up), diorama (tiny isometric world), sculpture (abstract glass/light forms), still_life (symbolic everyday objects).
@@ -217,5 +320,16 @@
         parts.append("Text:\n" + (text if text else "(only the title is available)"))
         parts.append("")
-    if previous is not None:
+    if previous is not None and previous.get("_update"):
+        parts += [
+            "PREVIOUS ARTICLE (already published on the site; this is an UPDATE):",
+            f"title: {previous.get('title')}",
+            f"summary: {previous.get('summary')}",
+            f"body:\n{previous.get('body')}",
+            "",
+            "EDITOR INSTRUCTION: The SOURCES above bring a new development of this story. Update the article: the title, "
+            "summary, cover_headline and lead must put the new development first; keep the still-valid facts of the previous "
+            "article (it counts as a source) and drop what is outdated. Write update_note. All accuracy rules apply.",
+        ]
+    elif previous is not None:
         parts += [
             "PREVIOUS DRAFT (revise it):",
@@ -288,2 +402,33 @@
 def appeal_user(posts: list[dict]) -> str:
     return "\n".join(f"{p['id']} | {p.get('title', '')} | {p.get('summary', '')}" for p in posts)
+
+
+# ── 5) Kapak başlığı (eski haberler için toplu) ──
+COVERLINE_SCHEMA = {
+    "type": "object",
+    "properties": {
+        "lines": {"type": "array", "items": {"type": "object", "properties": {
+            "id": {"type": "string"}, "cover_headline": {"type": "string"}, "cover_highlight": {"type": "string"}},
+            "required": ["id", "cover_headline", "cover_highlight"], "additionalProperties": False}},
+    },
+    "required": ["lines"],
+    "additionalProperties": False,
+}
+
+
+def coverline_system(site_name: str) -> str:
+    return f"""You write the cover text of "{site_name}", a Turkish technology news site. The cover text is printed big on the
+article's image on the homepage, in feeds and on Instagram; it must make a scrolling reader stop and want to read.
+For each story write:
+- cover_headline: a hook of 3–7 words, ≤42 characters, in Turkish, that makes sense on its own: the key name
+  (company/product/game/car) or the key number plus what is new or surprising. Use only facts in the given title and
+  summary. No question marks, no exclamation marks, no ellipsis, no emojis, no clickbait teasing. Word it differently from
+  the title; sentence case; correct Turkish characters; keep brand spellings (iPhone, eFootball). Never just a name or just
+  a number. Style examples (do not reuse): "Starship ilk kez yörüngede", "TikTok'ta gençlere 2 saat sınırı",
+  "Apple'a 5,7 milyar dolar ceza", "Honor'dan 11.000 mAh'lik pil".
+- cover_highlight: 1–3 consecutive words copied exactly from cover_headline that carry the punch.
+Return one line per id."""
+
+
+def coverline_user(posts: list[dict]) -> str:
+    return "\n".join(f"{p['id']} | {p.get('title', '')} | {p.get('summary', '')}" for p in posts)
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -14,8 +14,8 @@
 from .config import CATEGORIES, DEFAULT_CATEGORY, ROOT, Config, category_color, category_label, category_seo, indexnow_key
 from .store import Store
-from .textfix import tag_display
+from .textfix import primary_key, tag_display
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "10"
+ASSET_V = "11"
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
 H2_RE = re.compile(r"<h[1-3]>(.*?)</h[1-3]>", re.S)
@@ -91,5 +91,5 @@
     if home == "hide":
         return -1.0
-    age = max(0.0, hours_since(p.get("published_at")))
+    age = max(0.0, min(hours_since(p.get("published_at")), hours_since(p.get("refreshed_at") or p.get("published_at"))))
     base = float(p.get("appeal") or max(5, int(p.get("importance") or 6) - 1))
     if (p.get("image") or {}).get("source") == "photo":
@@ -266,4 +266,7 @@
             "has_photo": bool(p.get("photos")),
             "updated_str": tr_date(p.get("updated_at"), cfg.tz) if p.get("updated_at") else "",
+            "ekey": primary_key(p),
+            "update_list": [{"date": tr_date(u.get("at"), cfg.tz), "iso": u.get("at", ""), "note": u.get("note", "")}
+                            for u in reversed(p.get("updates") or []) if u.get("note")],
         }
 
@@ -315,7 +318,22 @@
         ranked = sorted(visible, key=lambda p: -p["hot"])
         fresh = [p for p in ranked if hours_since(p.get("published_at")) <= 72 or p["hot"] >= 100]  # sabitlenen her zaman
-        featured = (fresh + [p for p in ranked if p not in fresh])[:n_feat]
+        # Vitrinde (manşet + öne çıkanlar) her şirketten tek haber: aynı şirketin ikinci haberi aşağıdaki listelerde kalır
+        used: set[str] = set()
+
+        def pick(pool: list[dict], n: int, shown: set[str]) -> list[dict]:
+            out = []
+            for strict in (True, False):
+                for p in pool:
+                    if len(out) >= n:
+                        return out
+                    if p["id"] in shown or p in out or (strict and p["ekey"] and p["ekey"] in used):
+                        continue
+                    out.append(p)
+                    if p["ekey"]:
+                        used.add(p["ekey"])
+            return out
+        featured = pick(fresh + [p for p in ranked if p not in fresh], n_feat, set())
         shown = {p["id"] for p in featured}
-        top = [p for p in ranked if p["id"] not in shown][:6]
+        top = pick(ranked, 6, shown)
         shown |= {p["id"] for p in top}
         latest = [p for p in visible if p["id"] not in shown and hours_since(p.get("published_at")) <= 48][:6]
--- a/haberbot/store.py
+++ b/haberbot/store.py
@@ -129,4 +129,23 @@
             f.unlink(missing_ok=True)
 
+    def recent_archive(self, hours: float) -> list[dict]:
+        """Son saatlerde kapanan taslaklar (reddedilen, süresi dolan, siteden kaldırılan): aynı haber tekrar önerilmesin."""
+        out = []
+        folder = self.cfg.data_dir / "archive"
+        for f in sorted(folder.glob("*.jsonl"))[-2:] if folder.exists() else []:
+            try:
+                lines = f.read_text(encoding="utf-8").splitlines()
+            except OSError:
+                continue
+            for ln in lines:
+                try:
+                    d = json.loads(ln)
+                except json.JSONDecodeError:
+                    continue
+                if hours_since(d.get("closed_at")) <= hours:
+                    out.append(d)
+        out.sort(key=lambda d: d.get("closed_at") or "", reverse=True)
+        return out
+
     # ── yayınlar ─────────────────────────────────────────────
     def post_path(self, pid: str) -> Path:
--- a/haberbot/textfix.py
+++ b/haberbot/textfix.py
@@ -132,5 +132,6 @@
         changed = []
         for k in ("title", "short_title", "summary", "body", "seo_title", "meta_description", "kicker",
-                  "hero_stat_label", "image_alt", "cover_text", "focus_keyword"):
+                  "hero_stat_label", "image_alt", "cover_text", "focus_keyword", "cover_headline", "cover_highlight",
+                  "update_note"):
             v = p.get(k)
             if isinstance(v, str) and v:
@@ -161,2 +162,31 @@
         return t
     return tr_upper_first(t)
+
+
+# Şirket / ürün adından karşılaştırma anahtarı ("HONOR Watch 6" → "honor"): aynı şirketin haberlerini tanımak için
+_EKEY_STOP = {"the", "a", "an", "new", "yeni"}
+_EKEY_GENERIC = {"turkiye", "abd", "cin", "avrupa", "japonya", "kore", "yapay", "elektrikli", "akilli", "otonom", "oyun",
+                 "otomobil", "teknoloji", "girisim", "yatirim", "uzay", "robot", "robotlar", "insansi", "batarya",
+                 "siber", "veri", "bulut", "kripto", "bitcoin", "ai", "ev", "suv", "5g", "6g"}
+
+
+def entity_key(name: str) -> str:
+    words = [w.strip(".'’-") for w in re.split(r"[\s/,:;()]+", fold(name or "").lower().strip())]
+    words = [w for w in words if w and w not in _EKEY_STOP]
+    if not words or len(words[0]) < 2 or words[0] in _EKEY_GENERIC:
+        return ""
+    return words[0]
+
+
+def primary_key(p: dict) -> str:
+    """Haberin ana şirket/ürün anahtarı: önce ayıklamanın verdiği adlar, yoksa ilk etiketler."""
+    for e in list(p.get("entities") or []) + list(p.get("tags") or [])[:2]:
+        k = entity_key(e)
+        if k:
+            return k
+    return ""
+
+
+def entity_keys(p: dict) -> set[str]:
+    names = list(p.get("entities") or []) or list(p.get("tags") or [])[:1]
+    return {k for k in (entity_key(e) for e in names) if k}
--- a/static/style.css
+++ b/static/style.css
@@ -107,5 +107,5 @@
 .chip { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; letter-spacing: .01em; padding: 6px 12px;
   border-radius: 999px; background: color-mix(in srgb, var(--c) 86%, #000); color: #fff; }
-.stat-chip { background: rgba(255,255,255,.72); color: var(--ink); font-weight: 500; }
+.stat-chip, .upd-chip { background: rgba(255,255,255,.72); color: var(--ink); font-weight: 500; }
 .stat-chip b { font-weight: 700; }
 .slide h2 { margin: 0; font-size: clamp(26px, 3.3vw, 46px); line-height: 1.08; letter-spacing: -.03em; font-weight: 700; text-wrap: balance; }
@@ -120,5 +120,5 @@
 .slide.dark .slide-meta { color: rgba(255,255,255,.66); }
 .slide.dark .more { color: #6CB4FF; }
-.slide.dark .stat-chip { background: rgba(255,255,255,.16); color: #fff; }
+.slide.dark .stat-chip, .slide.dark .upd-chip { background: rgba(255,255,255,.16); color: #fff; }
 @media (max-width: 599px) { .slide-dek { display: none; } }
 @media (min-width: 800px) {
@@ -257,4 +257,8 @@
 .art-head .meta-top time, .art-head .meta-top .muted { color: var(--muted); font-weight: 400; }
 .art-head h1 { margin: 12px 0 0; font-size: clamp(30px, 4.4vw, 46px); line-height: 1.1; letter-spacing: -.035em; font-weight: 700; text-wrap: balance; }
+.art-head .upd { margin: 14px 0 0; padding: 10px 14px; border-radius: 12px; font-size: 15px; line-height: 1.45; color: var(--ink-2);
+  background: color-mix(in srgb, var(--c) 8%, transparent); border-left: 3px solid var(--c); text-wrap: pretty; }
+.art-head .upd b { color: var(--ink); font-weight: 700; margin-right: 4px; }
+.art-head .upd time { color: var(--muted); margin-right: 6px; }
 .art-head .dek { margin: 16px 0 0; font-size: clamp(18px, 1.9vw, 21px); line-height: 1.45; color: var(--ink-2); letter-spacing: -.015em; text-wrap: pretty; }
 .art-head .share { margin-top: 20px; }
--- a/templates/_macros.html
+++ b/templates/_macros.html
@@ -45,5 +45,5 @@
       <span class="slide-top">
         <span class="chip">{{ p.cat_label }}</span>
-        {% if p.hero_stat and not p.stat_on_cover %}<span class="chip stat-chip"><b>{{ p.hero_stat }}</b>{% if p.hero_stat_label %} {{ p.hero_stat_label }}{% endif %}</span>{% endif %}
+        {% if p.update_list %}<span class="chip upd-chip">Güncellendi</span>{% endif %}
       </span>
       <h2>{{ p.title_disp }}</h2>
--- a/templates/article.html
+++ b/templates/article.html
@@ -52,4 +52,8 @@
     <h1>{{ post.title_disp }}</h1>
     <p class="dek">{{ post.summary }}</p>
+    {% if post.update_list %}
+    {% set u = post.update_list[0] %}
+    <p class="upd"><b>Güncellendi</b> <time datetime="{{ u.iso }}">{{ u.date }}</time> <span>{{ u.note }}</span></p>
+    {% endif %}
     <div class="share" aria-label="Paylaş">
       <button type="button" class="sh-native" data-share data-title="{{ post.title }}" data-url="{{ post.abs_url }}" hidden>Paylaş</button>
--- a/templates/cards/cover.html
+++ b/templates/cards/cover.html
@@ -75,5 +75,5 @@
 /* ── 3) MANŞET: afiş gibi büyük başlık ── */
 .l-manset .head { position: absolute; left: calc(var(--u) * 6); right: calc(var(--u) * 6); bottom: calc(var(--u) * 12);
-  font-weight: 700; font-size: calc(var(--u) * 11.5); line-height: .98; letter-spacing: -.05em; text-wrap: balance; }
+  font-weight: 700; font-size: calc(var(--u) * 13); line-height: .98; letter-spacing: -.05em; text-wrap: balance; }
 em { font-style: normal; }
 .t-vivid .grad-text { background: none; color: var(--ink); -webkit-text-fill-color: currentColor; }
--- a/templates/cards/photo.html
+++ b/templates/cards/photo.html
@@ -19,5 +19,5 @@
 .scrim { position: absolute; inset: 0; z-index: -3;
   background: linear-gradient(to top, rgba(var(--shade), .95) 0%, rgba(var(--shade), .80) 22%, rgba(var(--shade), .42) 44%, rgba(var(--shade), 0) 64%); }
-.l-manset .scrim { background: linear-gradient(to top, rgba(var(--shade), .96) 0%, rgba(var(--shade), .84) 28%, rgba(var(--shade), .45) 52%, rgba(var(--shade), 0) 72%); }
+.l-manset .scrim { background: linear-gradient(to top, rgba(var(--shade), .96) 0%, rgba(var(--shade), .86) 30%, rgba(var(--shade), .5) 55%, rgba(var(--shade), 0) 76%); }
 .top { position: absolute; inset: 0 0 auto; height: 30%; z-index: -3; background: linear-gradient(to bottom, rgba(var(--shade), .55), rgba(var(--shade), 0)); }
 .tint { position: absolute; z-index: -2; border-radius: 50%; mix-blend-mode: screen; filter: blur(calc(var(--u) * 9)); }
@@ -38,5 +38,5 @@
 .word { font-weight: 700; font-size: calc(var(--u) * 15.5); line-height: .96; letter-spacing: -.055em; text-wrap: balance; max-width: 100%;
   padding-bottom: .04em; }
-.head { font-weight: 700; font-size: calc(var(--u) * 7.4); line-height: 1.03; letter-spacing: -.04em; text-wrap: balance; max-width: 100%;
+.head { font-weight: 700; font-size: calc(var(--u) * 9.4); line-height: 1.02; letter-spacing: -.042em; text-wrap: balance; max-width: 100%;
   text-shadow: 0 calc(var(--u) * .3) calc(var(--u) * 3) rgba(0,0,0,.35); }
 .head em { font-style: normal; }
@@ -71,5 +71,5 @@
     <div class="word grad" data-fitw data-maxh="{{ (H * 0.36)|int }}">{{ word }}</div>
   {% else %}
-    <div class="head" data-maxh="{{ (H * 0.34)|int }}">{{ headline|safe }}</div>
+    <div class="head" data-maxh="{{ (H * 0.42)|int }}">{{ headline|safe }}</div>
   {% endif %}
 </div>
--- a/tests/test_core.py
+++ b/tests/test_core.py
@@ -83,6 +83,14 @@
             assert name.startswith(cat) and len(pal) == 6
     assert cover_word({"tags": ["Apple", "iPhone 18 Pro", "oyun"]}) == "iPhone 18 Pro"
-    d = design({"id": "abc123", "title": "BYD yeni sedanını tanıttı", "hero_stat": "1.000 km", "category": "teknoloji"})
-    assert d["layout"] == "sayi" and d["brand_name"] == "Smarity"
+    d = design({"id": "abc123", "title": "BYD yeni sedanını tanıttı", "hero_stat": "1.000 km", "category": "teknoloji",
+                "cover_headline": "BYD'den 1.000 km menzilli sedan", "cover_highlight": "1.000 km"})
+    assert d["layout"] == "manset" and d["brand_name"] == "Smarity"      # kapakta her zaman vurucu kapak başlığı
+    assert '<em class="grad-text">1.000 km</em>' in d["headline"]
+    assert design({"id": "abc123", "title": "BYD yeni sedanını tanıttı", "hero_stat": "1.000 km",
+                   "category": "teknoloji"}, caption=True)["layout"] == "sayi"   # sosyal "kapak" tarzı eski düzende
+    from haberbot.covers import photo_design
+    pd = photo_design({"id": "x1", "title": "OpenAI modelini durdurdu", "tags": ["OpenAI"], "hero_stat": "5",
+                       "cover_headline": "OpenAI en güçlü modelini durdurdu", "cover_highlight": "durdurdu"})
+    assert pd["layout"] == "manset" and pd["title"] == "OpenAI en güçlü modelini durdurdu"
     from haberbot.covers import _mark, news_card, tr_upper
     assert _mark("Circle Games'e Tencent liderliğinde yatırım", {"tags": ["Circle Games"]}).startswith("<mark>Circle Games'e</mark>")
@@@SM@@@ FILE tests/test_editor.py
"""Seçki (yayın yönetmeni), mevcut haberi güncelleme, kapak başlığı ve ana sayfa çeşitliliği testleri."""
import json
import re
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haberbot.site import SiteBuilder  # noqa: E402
from haberbot.telegram import MockTelegram  # noqa: E402
from haberbot.util import iso, now_utc  # noqa: E402
from tests.test_home import _App, _post  # noqa: E402


def _q(topic, imp, ents, dup="", cat="teknoloji"):
    it = {"key": topic, "url": f"https://k.com/{abs(hash(topic))}", "credit": "Kaynak", "title": topic, "kind": "media",
          "source": "Kaynak", "summary": ""}
    return {"story": {"topic": topic, "importance": imp, "entities": ents, "category": cat, "duplicate_of": dup},
            "items": [it], "at": iso(now_utc())}


def test_guard_rules():
    with _App() as (cfg, a):
        a.store.save_post(_post(1, 3, tags=["Honor"], entities=["Honor", "Honor Magic9"]))
        queue = [_q("Honor Watch 6 Pro launched", 8, ["Honor"]),           # aynı şirket bugün var → geç
                 _q("Starship reaches orbit", 9, ["SpaceX", "Starship"]),   # yayınla
                 _q("Falcon 9 retirement date", 8, ["SpaceX"]),             # aynı turda aynı şirket → beklet
                 _q("Minor app update", 7, ["Foo"]),                        # eşik altı → geç
                 _q("Big AI launch", 9, ["Anthropic"]),                     # yer yok → beklet (slots=1)
                 _q("Honor Magic9 price in Europe", 8, ["Honor"], dup="s:p01"),   # yayındaki haberin devamı → güncelle
                 ]
        dec = {i: {"action": "publish", "target": "", "must_read": q["story"]["importance"], "reason": ""}
               for i, q in enumerate(queue)}
        out = a._guard(queue, dec, slots=1, min_score=8, covered=a._covered(48))
        acts = [out[i]["action"] for i in range(len(queue))]
        assert acts[1] == "publish"
        assert acts[0] == "skip" and "24 saat" in out[0]["reason"]
        assert acts[2] == "hold" and acts[3] == "skip" and acts[4] == "hold"
        assert acts[5] == "update" and out[5]["target"] == "p01"


def test_edit_uses_llm_and_falls_back():
    with _App() as (cfg, a):
        queue = [_q("Starship reaches orbit", 9, ["SpaceX"]), _q("Vivo unboxing", 7, ["Vivo"])]
        dec = a._edit(queue, slots=2)                                      # test modu yönetmeni: masa puanı ≥8 → yayınla
        assert dec[0]["action"] == "publish" and dec[1]["action"] == "skip"
        for i, q in enumerate(queue):
            a._edit_log(q, dec[i]["action"], dec[i])
        txt = a.edit_text()
        assert "Starship" in txt and "elendi" in txt
        from haberbot.llm import LLMError

        def boom(*a_, **k):
            raise LLMError("HTTP 503")
        a.llm.json = boom
        dec = a._edit(queue, slots=2)                                      # yönetmen yoksa masa puanı + eşik
        assert dec[0]["action"] == "publish" and dec[1]["action"] == "hold"


def test_update_story_in_place():
    with _App() as (cfg, a):
        a.tg = a.tg or MockTelegram(cfg.root / "tg")
        post = _post(1, 5, publish_mode="manual", telegram={"message_id": 5}, entities=["OpenAI"])
        a.store.save_post(post)
        it = {"key": "k2", "url": "https://new.com/x", "credit": "The Verge", "title": "Florida asks OpenAI to halt model",
              "kind": "media", "source": "The Verge", "summary": "", "published": iso(now_utc())}
        d = a.create_update(a.store.load_post("p01"), {"must_read": 8, "entities": ["OpenAI"], "topic": "t"}, [it])
        assert d["update_of"] == "p01" and a.store.load_draft(d["id"])["status"] == "pending"
        kb = a._keyboard(d, "pending")
        assert kb[0][0]["text"].startswith("🔄") and "GÜNCELLEME" in a._caption(d, "pending")
        assert a._on_button("p", d["id"]).startswith("🔄")
        p = a.store.load_post("p01")
        assert p["slug"] == "haber-1" and len(p["sources"]) == 2 and p["updates"][0]["sources"] == ["The Verge"]
        assert p.get("refreshed_at") and not a.store.load_draft(d["id"])
        assert p["title"] != post["title"]                                  # metin yeni gelişmeyle yenilendi
        sb = SiteBuilder(cfg)
        sb.build()
        art = (cfg.out_dir / "haber" / "haber-1" / "index.html").read_text(encoding="utf-8")
        assert 'class="upd"' in art and "Güncellendi" in art


def test_recently_rejected_is_remembered():
    with _App() as (cfg, a):
        d = {**_post(3, 1), "status": "rejected", "created_at": iso(now_utc())}
        a.store.save_draft(d)
        a.store.archive_draft(d, "rejected")
        rec = a.store.recent_archive(72)
        assert rec and rec[0]["id"] == "p03"
        cov = a._covered(48)
        assert any(c["id"] == "p03" and c["status"] == "rejected" for c in cov)


def test_cover_lines_backfill_and_gating():
    with _App() as (cfg, a):
        a.store.save_post(_post(1, 2, image={"source": "cover", "cover_v": 1}))
        assert not a._cover_ready(a.store.load_post("p01"))
        a.backfill_cover_lines()
        p = a.store.load_post("p01")
        assert p["cover_headline"] and a._cover_ready(p)
        assert a._cover_line("OpenAI", "") == {}                           # tek sözcük kapak başlığı olmaz
        assert a._cover_line("Apple'a 5,7 milyar dolar ceza", "yok") == {"cover_headline": "Apple'a 5,7 milyar dolar ceza",
                                                                         "cover_highlight": ""}


def test_home_one_story_per_company_in_showcase():
    with _App() as (cfg, a):
        for i, ent in enumerate(["Honor", "Honor", "Honor", "OpenAI", "OpenAI", "Apple", "Tesla", "Sony", "Xbox", "Google",
                                 "Meta", "Nvidia", "BYD", "Samsung", "Nintendo", "Rivian", "Valve", "AMD", "Intel", "Epic",
                                 "Uber", "Spotify"]):
            a.store.save_post(_post(i, hours=i, appeal=8, tags=[ent], entities=[ent]))
        SiteBuilder(cfg).build()
        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
        slider = re.findall(r'class="slide[^"]*"[^>]*data-id="(p\d+)"', home)
        top = re.findall(r'data-id="(p\d+)"', re.search(r'data-top>(.*?)</div>\s*</section>', home, re.S).group(1))
        shown = slider + top
        ents = [json.loads((cfg.posts_dir / f"{pid}.json").read_text())["entities"][0] for pid in shown]
        assert len(ents) == len(set(ents)), ents                          # vitrinde her şirketten tek haber
        assert ents.count("Honor") == 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
@@@SM@@@ SHA
19268751b2140e12816cf24d196743ecfb29d3e14baeafe178b6da6be985823d config.yaml
59efa98c1bc95755945017e88be87b3b9b0ddc7763e0bd9a888d2426e4b93292 haberbot/app.py
79932163db604b30de5e8fcfd465f470971898c6fc30a4c86fd0c43f07150f04 haberbot/covers.py
b93c25005f478eb66e181cf1af0c14bc646471c4e850f75af26608d6ccc1db12 haberbot/llm.py
de2bf0d5bcb3986dd2d1e125eef0ed4fed83749cb692b57967e089f58c725d4b haberbot/prompts.py
ded1e834d0e28a3c756b7d3ed880791182e67dc430399600885ae355cdc3eebf haberbot/site.py
a56003afa08ee28f31b04fcad20e66b4fed30a3dd179bc882917f59a0d4f3728 haberbot/store.py
4f729f95bf24c37c8ad1e595237372e2d39ea548089689858cf22b5f2873aaab haberbot/textfix.py
7581d88bdba455441a4294f3961d8dcf0b6b95b25ed01a15bada367e64960b6c static/style.css
bf3ef1461e4c8c57bcd0d9c899c5919de80be54aa00c1e5ad39b934cffe2b178 templates/_macros.html
5828394adaa50a4a73e5d3ebcabf42e84f77abaa79de3ed08b15852129ff9451 templates/article.html
6749b199720e447623b2931d823c4f5d6949f27d37a2c93c956c54f82f68792b templates/cards/cover.html
92ea4c0a68bf7b7a64554be0d3a2c262c7a6b2a55bbfd736f042184e069aa66c templates/cards/photo.html
bc89661de18988e539754d1b01f9b7f9796d4ef015745c075c9017a2fff6e1a1 tests/test_core.py
d1c11df29ef29d39f12730695f83ee0fa237ac7bf085e0ba04b5173ea5bf0897 tests/test_editor.py
