SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -128,4 +128,6 @@
     - ["671d0ac58e", "9976fc4746"]   # OpenAI en gelişmiş modellerinin eğitimini durdurdu (28 Eyl, aynı gün iki haber)
     - ["7f88f8a5fd", "d901a6a000"]   # ChatGPT Pro 500 Türkiye fiyatı (30 Eyl ↔ 27 Eyl)
+  relaunch:                          # ön izleme olarak açılıp asıl gelişmeyle güncellenen haber: yeni haber olarak yeniden yayınla
+    - "248dd99ad3"                   # Tesla Roadster tanıtıldı (14 Eki "tanıtım tarihi" haberi olarak açılmıştı)
   retitle:
     "95a0ae8187": "Uygun fiyatlı elektrikli Dacia Hipster 2027'de geliyor"   # başlıkta yurtdışı fiyatı vardı
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -322,4 +322,6 @@
             q["story"]["must_read"] = int(x.get("must_read") or 0)
             q["story"]["big_brand"] = bool(x.get("big_brand"))
+            q["story"]["preview"] = bool(x.get("preview"))
+            q["story"]["replaces"] = x.get("replaces") or ""
             q["story"]["editor_reason"] = x.get("reason", "")
             act = x["action"]
@@ -434,4 +436,5 @@
             x["reason"] = clip(str(x.get("reason") or ""), 120)
             x["big_brand"] = x.get("big_brand") is True
+            x["preview"] = x.get("preview") is True
             if x.get("action") not in ("publish", "update", "skip", "hold"):
                 x["action"] = "hold"
@@ -483,9 +486,19 @@
         pending = {c["id"] for c in covered if c["status"] == "pending"}
         refreshed = {c["id"] for c in covered if c["status"] == "published" and c.get("updated") and c["hours"] < 6}
-        used, round_targets = 0, set()
+        used, round_targets, retiring = 0, set(), set()
         for i in sorted(decisions, key=lambda i: -decisions[i]["must_read"]):
             x, s = decisions[i], queue[i]["story"]
             keys = entity_keys(s)
             mr = x["must_read"]
+            # asıl olay (tanıtım, çıkış, imza…) ön izleme haberinin (tarih, davet, sızıntı) güncellemesi ya da tekrarı
+            # sayılmaz: yeni haber olarak yayınlanır; ön izleme haberi kalkar, adresi yeni habere yönlenir
+            if not x.get("preview") and mr >= min_score and x["action"] in ("update", "skip", "publish"):
+                dup = (s.get("duplicate_of") or "").removeprefix("s:")
+                tgt = x["target"] if x["action"] in ("update", "skip") and x.get("target") else dup
+                if tgt and tgt in published and tgt not in retiring and self._is_preview(tgt):
+                    x["action"], x["target"], x["replaces"] = "publish", "", tgt
+                    x["reason"] = clip("asıl gelişme, ön izleme haberinin yerini alır" +
+                                       (f": {x['reason']}" if x.get("reason") else ""), 120)
+                    retiring.add(tgt)
             if x["action"] == "update":
                 if x["target"] in pending:
@@ -508,5 +521,5 @@
             # masa "aynı haber" dedi: yeni haber değil, olsa olsa güncelleme. Yönetmen 9+ ile "yeni haber" dediyse
             # (ör. ön izlemesi yayınlanmış bir etkinlikte ürünlerin resmen tanıtılması) yönetmenin kararı geçerli
-            if dup in published and mr < 9:
+            if dup in published and mr < 9 and not x.get("replaces"):
                 ok = mr >= min_score and dup not in round_targets and (dup not in refreshed or mr >= 9)
                 x["action"], x["target"] = ("update", dup) if ok else ("skip", dup)
@@ -720,5 +733,7 @@
         merge_posts: [[yinelenen_id, kalan_id], …] → yinelenen haber silinir, adresi kalan habere yönlenir,
                      kaynakları kalan habere eklenir.
-        retitle: {haber_id: "Yeni başlık"} → başlık düzeltilir (adres değişmez)."""
+        retitle: {haber_id: "Yeni başlık"} → başlık düzeltilir (adres değişmez).
+        relaunch: [haber_id, …] → ön izleme olarak açılıp asıl gelişmeyle güncellenen haber yeni haber olarak yeniden
+                  yayınlanır (yeni adres, eski adres yönlenir); bir kez uygulanır."""
         m = self.cfg.raw.get("maintenance") or {}
         st = self.store
@@ -731,9 +746,5 @@
             if not dup or not keep or dup_id == keep_id:
                 continue
-            olds = list(keep.get("old_paths") or [])
-            for o in (self.cfg.post_path(dup), f"haber/{dup['slug']}", *(dup.get("old_paths") or [])):
-                if o and o not in olds and o != keep.get("path"):
-                    olds.append(o)
-            keep["old_paths"] = olds
+            self._fold_into(dup, keep)
             urls = {s.get("url") for s in keep.get("sources") or []}
             keep["sources"] = (keep.get("sources") or []) + [s for s in dup.get("sources") or [] if s.get("url") not in urls]
@@ -743,4 +754,8 @@
             self.queue_indexnow(self.cfg.post_url(keep))
             log.info("Yinelenen haber birleştirildi: %s → %s", dup_id, keep_id)
+        for pid in m.get("relaunch") or []:
+            p = st.load_post(str(pid))
+            if p and not p.get("relaunched"):
+                self._relaunch(p)
         for pid, title in (m.get("retitle") or {}).items():
             p = st.load_post(str(pid))
@@ -804,4 +819,6 @@
             "importance": int(story.get("must_read") or story.get("importance", 5)),
             "big_brand": bool(story.get("big_brand")),
+            "preview": bool(story.get("preview")),
+            "replaces": story.get("replaces") or "",
             "triage_reason": story.get("editor_reason") or story.get("reason", ""),
             "entities": list(story.get("entities") or []),
@@ -991,5 +1008,70 @@
         st.bump(self.today(), "auto" if auto else "approved")
         log.info("Yayınlandı: %s → %s", post["id"], self.cfg.post_url(post))
+        if post.get("replaces"):
+            try:
+                self._retire_preview(post["replaces"], post)
+            except Exception as e:  # noqa: BLE001
+                log.warning("Ön izleme haberi kaldırılamadı (%s): %s", post.get("replaces"), e)
         return post
+
+    PREVIEW_TOPIC = re.compile(r"\b(scheduled|upcoming|dates?|invites?|invitation|teasers?|teases?d?|countdown|what to expect|"
+                               r"expected|preview|leaks?|leaked|rumou?rs?|rumou?red|to unveil|will unveil|set to|plans to|"
+                               r"coming soon)\b", re.I)
+
+    def _is_preview(self, pid: str) -> bool:
+        """Yayındaki haber bir ön izleme mi (tarih / davet / teaser / sızıntı)? Eski haberlerde yönetmenin konu notuna bakılır."""
+        p = self.store.load_post(pid)
+        if not p:
+            return False
+        if "preview" in p:
+            return bool(p["preview"])
+        return bool(self.PREVIEW_TOPIC.search(p.get("topic") or ""))
+
+    def _fold_into(self, dup: dict, keep: dict) -> None:
+        """dup haberinin adresleri keep haberine yönlenir (site eski adreslere yönlendirme sayfası yazar)."""
+        olds = list(keep.get("old_paths") or [])
+        for o in (self.cfg.post_path(dup), f"haber/{dup['slug']}", *(dup.get("old_paths") or [])):
+            if o and o not in olds and o != keep.get("path"):
+                olds.append(o)
+        keep["old_paths"] = olds
+
+    def _retire_preview(self, old_id: str, post: dict) -> None:
+        """Asıl gelişme yayınlandı: ön izleme haberi (ör. "Tesla Roadster'ın tanıtım tarihi açıklandı") yayından kalkar,
+        adresi yeni habere yönlenir, Telegram'daki mesajı güncellenir."""
+        st = self.store
+        old = st.load_post(old_id)
+        if not old or old_id == post["id"]:
+            return
+        self._fold_into(old, post)
+        st.save_post(post)
+        st.delete_post(old_id)
+        self._ig_drop(old_id, "↪️ Haber yerini asıl gelişmeye bıraktı; Instagram'a gönderilmeyecek")
+        st.archive_draft(old, "superseded")
+        self._update_preview({**old, "replaced_by": post.get("title")}, "superseded")
+        log.info("Ön izleme haberi yerini asıl habere bıraktı: %s → %s", old_id, post["id"])
+
+    def _relaunch(self, p: dict) -> None:
+        """Ön izleme olarak açılıp asıl gelişmeyle güncellenmiş haberi yeni haber olarak yeniden yayınla: yeni adres
+        (başlıktan), yayın zamanı şimdi, "Güncellendi" geçmişi temizlenir; eski adres yeni adrese yönlenir."""
+        st = self.store
+        old_path, old_slug = self.cfg.post_path(p), p["slug"]
+        used = {q.get("slug") for q in st.posts() if q["id"] != p["id"]}
+        base = slugify(p["title"], 64)
+        slug, n = base, 2
+        while slug in used:
+            slug, n = f"{base}-{n}", n + 1
+        p["slug"] = p["seo_slug"] = slug
+        p["published_at"] = iso(now_utc())
+        for k in ("refreshed_at", "updated_at", "updates", "update_note", "path"):
+            p.pop(k, None)
+        p["path"] = self.cfg.post_path(p)
+        p["old_paths"] = [o for o in dict.fromkeys([*(p.get("old_paths") or []), old_path, f"haber/{old_slug}"])
+                          if o != p["path"]]
+        p["preview"] = False
+        p["relaunched"] = p["published_at"]
+        st.save_post(p)
+        self.queue_indexnow(self.cfg.post_url(p))
+        self._send_preview(p, "auto")
+        log.info("Haber yeni haber olarak yeniden yayınlandı: %s → %s", p["id"], self.cfg.post_url(p))
 
     # ── Telegram önizlemeleri ───────────────────────────────
@@ -1006,4 +1088,5 @@
             "culled": "🧹 <b>SEÇKİ DIŞI</b> (yeni ölçütlere göre elendi)",
             "dropped": "🚫 <b>YAYINLANMADI</b> (şüpheli ya da istenmeyen içerik)",
+            "superseded": "↪️ <b>YERİNİ ASIL HABERE BIRAKTI</b> (ön izleme haberiydi; eski adresi yeni habere yönlenir)",
         }[kind]
         upd = d.get("update_of")
@@ -1031,4 +1114,6 @@
         elif d.get("editor_note") and kind == "pending":
             lines.append(f"📝 {esc(d['editor_note'])}")
+        if kind == "superseded" and d.get("replaced_by"):
+            lines.append(f"🆕 Yeni haber: <i>{esc(clip(d['replaced_by'], 110))}</i>")
         if kind == "dropped" and d.get("policy_reason"):
             lines.append(f"<i>{esc(d['policy_reason'])}</i>")
--- a/haberbot/llm.py
+++ b/haberbot/llm.py
@@ -342,5 +342,5 @@
                     act = ("update" if imp >= 8 else "skip") if same else ("publish" if imp >= 8 else "skip")
                     out.append({"cid": m.group(1), "action": act, "target": same.group(1) if same else "",
-                                "must_read": imp, "reason": "Test modu kararı"})
+                                "must_read": imp, "big_brand": False, "preview": False, "reason": "Test modu kararı"})
             return {"decisions": out}
         if "lines" in schema.get("properties", {}):       # kapak başlıkları
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -168,7 +168,8 @@
                     "must_read": {"type": "integer"},
                     "big_brand": {"type": "boolean"},
+                    "preview": {"type": "boolean"},
                     "reason": {"type": "string"},
                 },
-                "required": ["cid", "action", "target", "must_read", "big_brand", "reason"],
+                "required": ["cid", "action", "target", "must_read", "big_brand", "preview", "reason"],
                 "additionalProperties": False,
             },
@@ -232,9 +233,13 @@
   in the next round — holding is not rejecting).
 - Duplicates among candidates (same product or event): publish at most one of them.
-- The real event beats its preview: a COVERED story that previews, teases or leaks a launch or event never makes the actual
-  announcement a duplicate or an "update". When a household-name company officially unveils products (an Apple event,
-  Samsung Unpacked, a new iPhone, PlayStation or Pixel…), the launch is a NEW story ("publish", must_read 9–10); if several
-  major products are announced, publish the most important ones as separate stories. Live blogs, "how to watch" and
-  "what to expect" pieces are still skipped.
+- The real event beats its preview: a COVERED story that previews, teases or leaks a launch or event (an announced date,
+  an invitation, a teaser, "what to expect", a leak) never makes the actual announcement a duplicate or an "update". When
+  the thing itself happens — products unveiled, a car revealed, a model or game released, a deal signed — it is a NEW
+  story ("publish"); the preview story is retired automatically and its address points to the new story. A household-name
+  launch, and anything spectacular that ordinary people will talk about (a flying car, a humanoid robot, a record), is
+  must_read 9–10; if several major products are announced, publish the most important ones as separate stories. Live blogs,
+  "how to watch" and "what to expect" pieces are still skipped.
+- preview: true if the candidate is only about something that has NOT happened yet — an announced date or invitation, a
+  teaser or countdown, "what to expect", a leak or rumor; false if the thing itself happened.
 - target: the covered story id for "update" (e.g. "ab12cd34ef"), the most similar covered id for a duplicate "skip", else "".
 - big_brand: true if the story is about a household-name company, brand, product or service that most people in Türkiye
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -18,5 +18,5 @@
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "17"
+ASSET_V = "18"
 FOREIGN_PRICE = re.compile(r"(?=.*fiyat)(?=.*(\$|€|£|¥|dolar|euro|avro|sterlin|yuan|yen\b))", re.I)
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
--- a/static/site.js
+++ b/static/site.js
@@ -62,10 +62,11 @@
       });
     }
-    // Manşet: okunmamış ve son 12 saatte görülmemiş haberler önce (her girişte aynı manşet görünmesin)
+    // Manşet: günün en büyük haberi (ilk slayt) herkes için ve her zaman ilk sırada kalır; diğerlerinde okunmamış ve
+    // son 12 saatte görülmemiş haberler öne alınır (her girişte aynı manşet görünmesin)
     var track = document.getElementById("car-track");
     if (track) {
       var sl = Array.prototype.slice.call(track.querySelectorAll(".slide"));
-      function rank(s) { var id = s.getAttribute("data-id"); return read[id] ? 2 : (seen[id] && NOW - seen[id] < 43200) ? 1 : 0; }
-      var ordered = sl.map(function (s, i) { return [rank(s), i, s]; }).sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
+      function rank(s, i) { if (i === 0) return -1; var id = s.getAttribute("data-id"); return read[id] ? 2 : (seen[id] && NOW - seen[id] < 43200) ? 1 : 0; }
+      var ordered = sl.map(function (s, i) { return [rank(s, i), i, s]; }).sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
       if (ordered.some(function (x, k) { return x[1] !== k; })) {
         var dots = document.querySelector(".car-dots"), db = dots ? Array.prototype.slice.call(dots.children) : [];
--- a/tests/test_editor.py
+++ b/tests/test_editor.py
@@ -10,5 +10,5 @@
 from haberbot.site import SiteBuilder  # noqa: E402
 from haberbot.telegram import MockTelegram  # noqa: E402
-from haberbot.util import iso, now_utc  # noqa: E402
+from haberbot.util import hours_since, iso, now_utc  # noqa: E402
 from tests.test_home import _App, _post  # noqa: E402
 
@@ -49,4 +49,44 @@
 
 
+def test_launch_replaces_its_preview_story():
+    with _App() as (cfg, a):
+        from haberbot.telegram import MockTelegram
+        a.tg = a.tg or MockTelegram(cfg.root / "tg")
+        prev = _post(1, 20, entities=["Tesla", "Tesla Roadster"], topic="Tesla Roadster unveiling event scheduled",
+                     telegram={"message_id": 77}, title="Tesla Roadster'ın tanıtım tarihi açıklandı")
+        a.store.save_post(prev)
+        a.store.save_post(_post(2, 20, entities=["Apple"], topic="Apple launches iPhone Duo", preview=False))
+        launch = [_q("Tesla unveils Roadster with SpaceX thrusters", 9, ["Tesla", "Tesla Roadster"], dup="s:p01"),
+                  _q("Tesla Roadster event moved to Friday", 8, ["Tesla"], dup="s:p01"),
+                  _q("iPhone Duo Türkiye fiyatı", 8, ["Apple"], dup="s:p02")]
+        dec = {0: {"action": "update", "target": "p01", "must_read": 8, "reason": "", "preview": False},
+               1: {"action": "update", "target": "p01", "must_read": 8, "reason": "", "preview": True},
+               2: {"action": "update", "target": "p02", "must_read": 8, "reason": "", "preview": False}}
+        out = a._guard(launch, dec, slots=3, min_score=7, covered=a._covered(48))
+        assert out[0]["action"] == "publish" and out[0]["replaces"] == "p01"          # asıl tanıtım: yeni haber
+        assert out[1]["action"] == "update"                                            # yine ön izleme: güncelleme
+        assert out[2]["action"] == "update" and not out[2].get("replaces")             # ön izleme olmayan haber
+        # yayınlanınca ön izleme haberi kalkar, adresi yeni habere yönlenir, Telegram mesajı güncellenir
+        d = {**_post(3, 0), "status": "pending", "replaces": "p01", "preview": False, "title": "Tesla Roadster tanıtıldı"}
+        d.pop("published_at")
+        d.pop("slug")
+        post = a.publish(d, auto=True)
+        assert not a.store.load_post("p01") and cfg.post_path(prev) in post["old_paths"]
+        out = (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8")
+        assert "YERİNİ ASIL HABERE BIRAKTI" in out and "Tesla Roadster tanıtıldı" in out
+        assert not a._is_preview(post["id"])
+        # ön izleme olarak açılıp güncellenmiş eski haber: yeni haber olarak yeniden yayınlanır (bir kez)
+        old = {**_post(4, 50, title="Tesla Roadster roket iticileriyle tanıtıldı"), "updates": [{"at": "x", "note": "n"}],
+               "refreshed_at": iso(now_utc()), "telegram": {"message_id": 5}}
+        a.store.save_post(old)
+        old_path = cfg.post_path(old)
+        cfg.raw["maintenance"] = {"relaunch": ["p04"]}
+        a.apply_maintenance()
+        p = a.store.load_post("p04")
+        assert p["slug"].startswith("tesla-roadster-roket") and old_path in p["old_paths"] and "updates" not in p
+        assert hours_since(p["published_at"]) < 0.1 and p["relaunched"] and p["telegram"]["message_id"] != 5
+        a.apply_maintenance()
+        assert a.store.load_post("p04")["slug"] == p["slug"]
+
 def test_edit_uses_llm_and_falls_back():
     with _App() as (cfg, a):
@@@SM@@@ SHA
05260ab08cc13bc3c796310eb6fad7937bb235c1da843142414815be5c7255dc config.yaml
d38427d6ee0948b975b54628d9be5b04b50e72af8a6701c9cc81cf6d4f441615 haberbot/app.py
b6604c2a17eb4bcb2e1e233ca2191d5b8dc45c41dbad5ca269e2b5351f12fd20 haberbot/llm.py
fde5ab40f45cf37f735506b852af3c3a21f165e4a76b5ac4066654fb70a967e5 haberbot/prompts.py
95753098e0f1bb87164020084062e8c59886fc2abaaf8a09f193e389fccecf69 haberbot/site.py
fa2cb250cdef6dc73a546a2c747e3dd53c2d01e6ca2bcc6dbdfb0924252ac1a5 static/site.js
3f5b8bb43f181e0aa2a5e45d37f5885c63d5164bf61946fc11e3d4531a4f2119 tests/test_editor.py
