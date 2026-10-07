SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -111,4 +111,16 @@
   card_style: ozet
 
+# ─────────────────────────────────────────────────────────────
+#  Bakım (her turda uygulanır, tekrar çalışması zararsızdır)
+#  merge_posts: [yinelenen haber, kalan haber] → yinelenen silinir, adresi kalan habere yönlenir
+#  retitle: haber_id: "Yeni başlık" → başlık düzeltilir, adres değişmez
+maintenance:
+  merge_posts:
+    - ["377564d2b6", "48679f20de"]   # Kia Seltos Türkiye'de satışa çıktı (5 Eki ↔ 2 Eki)
+    - ["671d0ac58e", "9976fc4746"]   # OpenAI en gelişmiş modellerinin eğitimini durdurdu (28 Eyl, aynı gün iki haber)
+    - ["7f88f8a5fd", "d901a6a000"]   # ChatGPT Pro 500 Türkiye fiyatı (30 Eyl ↔ 27 Eyl)
+  retitle:
+    "95a0ae8187": "Uygun fiyatlı elektrikli Dacia Hipster 2027'de geliyor"   # başlıkta yurtdışı fiyatı vardı
+
 ai:
   # gemini: Google Gemini ücretsiz katmanı (kredi kartı gerekmez, günlük sınırlı)
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -23,5 +23,5 @@
 from .sources import fetch_all
 from .store import Store
-from .textfix import Fixer, entity_keys, is_car_story, looks_english
+from .textfix import Fixer, entity_keys, is_car_story, looks_english, title_words
 from .telegram import MockTelegram, Telegram, TelegramError
 from .util import (clip, hours_since, iso, local, log, now_utc, short_hash, slugify,
@@ -238,20 +238,27 @@
                 by_tid[it["tid"]] = it
 
-            recent = []
+            pub, older = [], []
             for p in st.posts():
-                if hours_since(p.get("published_at")) > 72:
+                h = hours_since(p.get("published_at"))
+                if h > 24 * 7:
                     break
-                recent.append({"sid": "s:" + p["id"], "status": "published", "title": p["title"]})
+                (pub if h <= 72 else older).append(p)
+            # 3-7 gün önce yayınlanmış ve yeni öğelerle aynı ürünü / şirketi anan haberler de gösterilir:
+            # aynı haber günler sonra başka bir siteden yeniden geldiğinde tekrar yazılmasın (ör. iki ayrı Kia Seltos haberi)
+            words = title_words(" ".join(it["title"] for it in fresh))
+            older = [p for p in older if len(title_words(p["title"]) & words) >= 2][:30]
+            recent = [{"sid": f"q:{i}", "status": "queued", "title": q["story"].get("topic", "")}
+                      for i, q in enumerate(queue)]
             for d in st.drafts():
                 recent.append({"sid": "s:" + d["id"], "status": d.get("status", "pending"), "title": d["title"]})
+            for p in pub[:100] + older:
+                recent.append({"sid": "s:" + p["id"], "status": "published", "title": p["title"]})
             for a in st.recent_archive(72):   # reddedilen / süresi dolan haberler tekrar önerilmesin
                 if a.get("status") in ("rejected", "expired", "removed"):
                     recent.append({"sid": "s:" + a["id"], "status": a["status"], "title": a.get("title", "")})
-            recent += [{"sid": f"q:{i}", "status": "queued", "title": q["story"].get("topic", "")}
-                       for i, q in enumerate(queue)]
 
             try:
                 tri = self.llm.json(cfg.get("ai", "triage_model", "claude-haiku-4-5-20251001"),
-                                    triage_system(self.brand), triage_user(fresh, recent[:150], today),
+                                    triage_system(self.brand), triage_user(fresh, recent[:260], today),
                                     TRIAGE_SCHEMA, max_tokens=12000)
             except LLMError as e:
@@ -381,4 +388,8 @@
         min_score = int(ed("min_must_read", 8))
         covered = self._covered(48)
+        cand_keys = set().union(*(entity_keys(q["story"]) for q in queue)) if queue else set()
+        have = {c["id"] for c in covered}
+        older = [c for c in self._covered(24 * 7) if c["status"] == "published" and c["id"] not in have
+                 and c["keys"] & cand_keys][:30]
         cands = []
         for i, q in enumerate(queue):
@@ -393,5 +404,5 @@
             out = self.llm.json(cfg.get("ai", "editor_model", None) or cfg.get("ai", "writer_model", "gemini-flash-latest"),
                                 edit_system(self.brand, min_score),
-                                edit_user(now_l.strftime("%Y-%m-%d %H:%M"), slots, covered[:90], cands),
+                                edit_user(now_l.strftime("%Y-%m-%d %H:%M"), slots, covered[:90] + older, cands),
                                 EDIT_SCHEMA, max_tokens=6000)
             raw = {str(x.get("cid")): x for x in (out.get("decisions") or []) if isinstance(x, dict)}
@@ -415,5 +426,5 @@
                 x["action"] = "hold"
             decisions[i] = x
-        return self._guard(queue, decisions, slots, min_score, covered)
+        return self._guard(queue, decisions, slots, min_score, covered + older)
 
     def _guard(self, queue: list[dict], decisions: dict[int, dict], slots: int, min_score: int,
@@ -428,5 +439,5 @@
                     day_keys[k] = day_keys.get(k, 0) + 1
         published = {c["id"] for c in covered if c["status"] == "published"}
-        published |= {p["id"] for p in self.store.posts()[:200] if hours_since(p.get("published_at")) <= 72}
+        published |= {p["id"] for p in self.store.posts()[:300] if hours_since(p.get("published_at")) <= 24 * 7}
         pending = {c["id"] for c in covered if c["status"] == "pending"}
         refreshed = {c["id"] for c in covered if c["status"] == "published" and c.get("updated") and c["hours"] < 6}
@@ -639,4 +650,49 @@
         self.fixer.post(res)          # Türkçe karakter ve marka yazımı düzeltmeleri
         return res
+
+    def apply_maintenance(self) -> None:
+        """Ayarlardaki bakım listesi (config.yaml → maintenance). Tekrar çalışması zararsızdır.
+
+        merge_posts: [[yinelenen_id, kalan_id], …] → yinelenen haber silinir, adresi kalan habere yönlenir,
+                     kaynakları kalan habere eklenir.
+        retitle: {haber_id: "Yeni başlık"} → başlık düzeltilir (adres değişmez)."""
+        m = self.cfg.raw.get("maintenance") or {}
+        st = self.store
+        for pair in m.get("merge_posts") or []:
+            try:
+                dup_id, keep_id = str(pair[0]), str(pair[1])
+            except (TypeError, IndexError, KeyError):
+                continue
+            dup, keep = st.load_post(dup_id), st.load_post(keep_id)
+            if not dup or not keep or dup_id == keep_id:
+                continue
+            olds = list(keep.get("old_paths") or [])
+            for o in (self.cfg.post_path(dup), f"haber/{dup['slug']}", *(dup.get("old_paths") or [])):
+                if o and o not in olds and o != keep.get("path"):
+                    olds.append(o)
+            keep["old_paths"] = olds
+            urls = {s.get("url") for s in keep.get("sources") or []}
+            keep["sources"] = (keep.get("sources") or []) + [s for s in dup.get("sources") or [] if s.get("url") not in urls]
+            keep["updated_at"] = iso(now_utc())
+            st.save_post(keep)
+            st.delete_post(dup_id)
+            self.queue_indexnow(self.cfg.post_url(keep))
+            log.info("Yinelenen haber birleştirildi: %s → %s", dup_id, keep_id)
+        for pid, title in (m.get("retitle") or {}).items():
+            p = st.load_post(str(pid))
+            title = clip(str(title or "").strip(), 120)
+            if not p or not title or p.get("title") == title:
+                continue
+            p["title"] = title
+            p["short_title"] = clip(title, 70)
+            p["seo_title"] = clip(title, 62)
+            p.pop("cover_line_v", None)                # kapak başlığı da yeni başlıkla yeniden yazılsın
+            p["updated_at"] = iso(now_utc())
+            try:
+                self._make_og(p)                       # paylaşım görselindeki başlık da yenilensin
+            except Exception as e:  # noqa: BLE001
+                log.warning("Paylaşım görseli yenilenemedi (%s): %s", p["id"], e)
+            st.save_post(p)
+            log.info("Başlık düzeltildi: %s → %s", p["id"], title)
 
     def fix_english_titles(self) -> None:
@@ -2353,4 +2409,8 @@
             log.exception("Adres geçişi hatası: %s", e)
         try:
+            self.apply_maintenance()
+        except Exception as e:  # noqa: BLE001
+            log.exception("Bakım listesi hatası: %s", e)
+        try:
             self.reselect_pending()
             self.fix_english_titles()
--- a/haberbot/llm.py
+++ b/haberbot/llm.py
@@ -164,5 +164,5 @@
         self._last[model] = time.time()
         try:
-            r = requests.post(GEMINI_URL.format(model=model), json=body, timeout=240,
+            r = requests.post(GEMINI_URL.format(model=model), json=body, timeout=120,
                               headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"})
         except requests.RequestException as e:
--- a/haberbot/textfix.py
+++ b/haberbot/textfix.py
@@ -188,4 +188,23 @@
 
 
+TITLE_STOP = {"the", "a", "an", "new", "yeni", "ve", "ile", "için", "bu", "how", "why", "what", "this", "is", "to", "in",
+              "on", "of", "for", "and", "with", "türkiye", "turkey", "türkiye'de", "here's", "here", "it", "its", "you",
+              "işte", "ilk", "resmi", "artık"}
+
+
+def title_words(text: str) -> set[str]:
+    """Başlıktaki ayırt edici sözcükler (özel adlar ve sayılar): farklı dillerdeki aynı haberi eşleştirmek için."""
+    out = set()
+    for w in re.findall(r"[\wÇĞİÖŞÜçğıöşü][\w'’.\-ÇĞİÖŞÜçğıöşü]*", text or ""):
+        w = w.strip(".-'’")
+        base = re.split(r"['’]", w)[0]
+        if len(base) < 2 or not (base[0].isupper() or any(c.isdigit() for c in base)):
+            continue
+        k = base.replace("İ", "i").replace("I", "ı").lower() if base[0] in "İI" else base.lower()
+        if k not in TITLE_STOP:
+            out.add(k)
+    return out
+
+
 def entity_keys(p: dict) -> set[str]:
     names = list(p.get("entities") or []) or list(p.get("tags") or [])[:1]
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -209,4 +209,49 @@
 
 
+
+def test_maintenance_merges_duplicates_and_fixes_titles():
+    with _App() as (cfg, a):
+        a.store.save_post(_post(1, 80, title="Kia Seltos Türkiye'de satışa çıktı: İşte resmi fiyatları", tags=["Kia"],
+                                sources=[{"name": "DonanımHaber", "url": "https://dh.com/kia", "kind": "media"}]))
+        a.store.save_post(_post(2, 2, title="Yeni Kia Seltos Türkiye'de satışa çıktı", tags=["Kia"],
+                                sources=[{"name": "ShiftDelete.Net", "url": "https://sd.net/kia", "kind": "media"}]))
+        a.store.save_post(_post(3, 5, title="Dacia Hipster 15 bin euronun altında fiyatla geliyor", tags=["Dacia"]))
+        a.migrate_urls()
+        dup_path = a.store.load_post("p02")["path"]
+        cfg.raw["maintenance"] = {"merge_posts": [["p02", "p01"], ["yok", "p01"]],
+                                  "retitle": {"p03": "Uygun fiyatlı elektrikli Dacia Hipster geliyor"}}
+        a.apply_maintenance()
+        a.apply_maintenance()                                              # ikinci kez çalışması zararsız
+        keep = a.store.load_post("p01")
+        assert a.store.load_post("p02") is None and dup_path in keep["old_paths"] and "haber/haber-2" in keep["old_paths"]
+        assert [s_["name"] for s_ in keep["sources"]] == ["DonanımHaber", "ShiftDelete.Net"]
+        assert a.store.load_post("p03")["title"] == "Uygun fiyatlı elektrikli Dacia Hipster geliyor"
+        SiteBuilder(cfg).build()
+        stub = (cfg.out_dir / dup_path / "index.html").read_text(encoding="utf-8")
+        assert cfg.post_url(keep) in stub and "refresh" in stub              # eski adres kalan habere yönlenir
+        assert dup_path not in (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")
+
+
+def test_older_duplicates_are_shown_to_desk_and_editor():
+    from haberbot.textfix import title_words
+    assert title_words("Kia Seltos Türkiye'de satışa çıktı: İşte resmi fiyatları") == {"kia", "seltos"}
+    assert {"chatgpt", "pro", "500"} <= title_words("OpenAI's ChatGPT Pro 500 now costs 26,499 lira")
+    with _App() as (cfg, a):
+        a.store.save_post(_post(1, 80, title="Kia Seltos Türkiye'de satışa çıktı", tags=["Kia Seltos"],
+                                entities=["Kia Seltos"]))
+        a.store.save_post(_post(2, 100, title="Sony yeni kulaklık tanıttı", tags=["Sony"], entities=["Sony"]))
+        seen = {}
+
+        class Ed:
+            def json(self, model, system, user, schema, max_tokens=0, effort=None, images=None):
+                seen["user"] = user
+                return {"decisions": [{"cid": "c1", "action": "skip", "target": "p01", "must_read": 8, "reason": "aynı haber"}]}
+        a.llm = Ed()
+        q = {"story": {"topic": "Kia Seltos on sale in Turkey", "importance": 8, "entities": ["Kia Seltos"],
+                       "category": "otomotiv", "duplicate_of": ""}, "items": [], "at": iso(now_utc())}
+        dec = a._edit([q], slots=2)
+        assert "p01" in seen["user"] and "p02" not in seen["user"] and dec[0]["action"] == "skip"
+
+
 if __name__ == "__main__":
     for name, fn in list(globals().items()):
@@@SM@@@ SHA
a6c3ac4e9f4873e1d22b208bc0b5834e67a8acd6e137f3250772aeda83bfb274 config.yaml
253efce5060db8b3a29dd713bff23403cae4162f23153ba13cc40da796fdf756 haberbot/app.py
49b1bb18b9b581a405bc497d1e9eaee095775baf92df26cbdbd74ec5fa653c18 haberbot/llm.py
47f8b04aaade0038f691cb6f61bad4d258a404152cb9d1b3ed4ccc1c45740de1 haberbot/textfix.py
dc81aa1cb8b88386f8d5e0dde1ed52fbf52155c9031bc4bbe05e9e189a9f4f76 tests/test_home.py
