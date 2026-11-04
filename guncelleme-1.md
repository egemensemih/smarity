SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -121,5 +121,9 @@
   instagram_auto: true
   instagram_user_id: "17841405730803695"   # @smarityco hesap numarası (Meta panelinde hesabın altında yazar)
-  instagram_every_post: false      # false: yayınlanan her haber otomatik paylaşılmaz (seçim sosyal medya masasında)
+  instagram_every_post: false      # false: her haber paylaşılmaz; sosyal medya masası seçer (gönderi + hikâye / hikâye / hiç)
+  instagram_daily_posts: 4         # günlük en fazla kalıcı gönderi (her gönderinin hikâyesi de atılır)
+  instagram_daily_stories: 7       # günlük en fazla hikâye (gönderilerin hikâyeleri dahil)
+  instagram_post_min: 8            # masanın gönderi için istediği en düşük puan (1–10)
+  instagram_story_min: 6           # hikâye için en düşük puan
   instagram_story: true            # carousel'e ek olarak hikâye de paylaşılsın
   instagram_hours: [8, 24]         # paylaşım saatleri; gece yayınlanan haberler sabah 8'de sırayla paylaşılır
@@ -131,7 +135,8 @@
   send_to_telegram: false
   # Instagram görsel tarzı:
-  # ozet  : logo, kategori etiketi, vurgulu büyük başlık ve kısa özet; renkler habere göre değişir (önerilen)
+  # manset: haberin gerçek fotoğrafı tam ekran, koyu geçiş, beyaz başlık (sitenin mobil manşeti; önerilen)
+  # ozet  : logo, kategori etiketi, vurgulu büyük başlık ve kısa özet; renkli ışık zemini
   # kapak : dev rakam / ürün adı kapağı (sitedeki kapakla aynı)
-  card_style: ozet
+  card_style: manset
 
 # ─────────────────────────────────────────────────────────────
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -19,4 +19,5 @@
 from .llm import LLMError, MockLLM, estimate_cost, make_llm
 from .prompts import (APPEAL_SCHEMA, COVERLINE_SCHEMA, EDIT_SCHEMA, FLAG_LABELS, FLAGS, PHOTO_SCHEMA, SEO_SCHEMA, TRIAGE_SCHEMA,
+                      SOCIAL_SCHEMA, social_system, social_user,
                       photo_system, photo_user,
                       WRITE_SCHEMA, appeal_system, appeal_user, coverline_system, coverline_user, edit_system, edit_user,
@@ -40,4 +41,5 @@
 }
 IG_WINDOW_DEFAULT = [8, 24]
+IG_FORMATS = {"post": "Gönderi + hikâye", "story": "Hikâye"}   # Instagram paylaşım biçimleri (sıradaki haber)
 CONF_LABEL = {"yuksek": "yüksek", "orta": "orta", "dusuk": "düşük"}
 COMMANDS = [
@@ -1262,7 +1264,9 @@
         Carousel: kapak + öne çıkanlar + neden önemli. Hikâye: bağlantı çıkartmasıyla siteye yönlendirir."""
         if not force and self.ig_enabled:
-            # her haber paylaşılmaz: social.instagram_every_post false iken yalnızca seçilenler (/instagram dene, düğmeler)
+            # her haber paylaşılmaz: sosyal medya masası seçer (social.instagram_every_post true ise hepsi gider)
             if self._ig_cfg("instagram_every_post", True):
                 self.ig_enqueue(post)
+            else:
+                self.social_desk(post)
             return
         if not (self.tg and self.chat_id):
@@ -1376,10 +1380,28 @@
         st = self.store
         if action == "x":
+            day = self._ig_day()
+            day[:] = [x for x in day if x.get("id") != did]          # günlük hak geri döner
             return "🚫 Instagram'a gönderilmeyecek" if self._ig_drop(did, cancelled=True) else "Sırada değil (paylaşılmış olabilir)."
+        if action in ("y", "b"):          # Instagram sırası: y = yalnızca hikâye, b = gönderi + hikâye
+            it = next((x for x in self.state.get("ig_queue") or [] if x["id"] == did), None)
+            post = st.load_post(did)
+            if not it or not post:
+                return "Sırada değil (paylaşılmış olabilir)."
+            if it.get("media_id") or it.get("story_id"):
+                return "Paylaşım başladı, artık değiştirilemez."
+            it["format"] = "story" if action == "y" else "post"
+            for x in self._ig_day():
+                if x.get("id") == did:
+                    x["format"] = it["format"]
+            self.store.site_dirty = True                                # gönderi kartları da siteye konsun
+            self._ig_msg(it, *self._ig_queue_msg(post, it))
+            return f"📸 {IG_FORMATS[it['format']]} olarak paylaşılacak"
         if action == "q":
             post = st.load_post(did)
             if not post:
                 return "Bu haber artık yayında değil."
-            return "📸 Tekrar sıraya alındı" if self.ig_enqueue(post, mid=self._cb_mid) else "Zaten sırada ya da paylaşıldı."
+            fmt = (post.get("social") or {}).get("format")
+            fmt = fmt if fmt in IG_FORMATS else "story"
+            return "📸 Tekrar sıraya alındı" if self.ig_enqueue(post, mid=self._cb_mid, fmt=fmt) else "Zaten sırada ya da paylaşıldı."
         where, d = st.find_any(did)
         if not d:
@@ -2067,20 +2089,100 @@
                 log.warning("Instagram bildirimi gönderilemedi: %s", e)
 
-    def ig_enqueue(self, post: dict, mid: int | None = None) -> bool:
-        """Yayınlanan haberi Instagram sırasına ekler (kartlar site yayınlanırken _site/ig/ altına konur)."""
+    def ig_enqueue(self, post: dict, mid: int | None = None, fmt: str = "post", note: str = "") -> bool:
+        """Haberi Instagram sırasına ekler (kartlar site yayınlanırken _site/ig/ altına konur).
+        fmt: "post" (kalıcı gönderi + aynı haberin hikâyesi) ya da "story" (yalnızca hikâye)."""
         q = self.state.setdefault("ig_queue", [])
         done = {x.get("id") for x in self.state.get("ig_done") or []}
         if post["id"] in done or any(x["id"] == post["id"] for x in q):
             return False
-        it = {"id": post["id"], "queued_at": iso(now_utc()), "tries": 0}
+        it = {"id": post["id"], "queued_at": iso(now_utc()), "tries": 0, "format": fmt if fmt in IG_FORMATS else "post"}
+        if note:
+            it["note"] = clip(note, 300)
         if mid:
             it["mid"] = mid
         q.append(it)
         self.store.site_dirty = True
+        self._ig_msg(it, *self._ig_queue_msg(post, it))
+        return True
+
+    def _ig_queue_msg(self, post: dict, it: dict) -> tuple[str, list]:
+        """Sıradaki haberin Telegram mesajı: biçim, masanın gerekçesi, değiştir / paylaşma düğmeleri."""
+        fmt = it.get("format", "post")
         where = "" if not self.state.get("ig_off") else " (Instagram şu an kapalı: /instagram ac)"
-        self._ig_msg(it, f"📸 <b>Instagram sırasında</b>{where}\n{esc(post['title'])}\n"
-                         f"<i>Carousel ve hikâye birkaç dakika içinde paylaşılacak.</i>",
-                     [[{"text": "🚫 Instagram'a gönderme", "callback_data": f"x:{post['id']}"}]])
-        return True
+        text = (f"📸 <b>Instagram: {IG_FORMATS[fmt]}</b>{where}\n{esc(post['title'])}"
+                f"{chr(10) + '<i>' + esc(it['note']) + '</i>' if it.get('note') else ''}\n"
+                f"<i>Birkaç dakika içinde paylaşılacak.</i>")
+        switch = ({"text": "Sadece hikâye", "callback_data": f"y:{post['id']}"} if fmt == "post"
+                  else {"text": "⬆️ Gönderi yap", "callback_data": f"b:{post['id']}"})
+        return text, [[{"text": "🚫 Paylaşma", "callback_data": f"x:{post['id']}"}, switch]]
+
+    # ── sosyal medya masası ─────────────────────────────────
+    def _ig_day(self) -> list[dict]:
+        """Bugün Instagram için seçilen haberler (gönderi / hikâye); günlük sınırlar buna göre hesaplanır."""
+        book = self.state.setdefault("ig_log", {})
+        for k in sorted(book)[:-7]:          # son 7 gün yeter
+            book.pop(k, None)
+        return book.setdefault(self.today(), [])
+
+    def ig_budget(self) -> tuple[int, int]:
+        """Bugün kalan (gönderi, hikâye) hakkı. Her gönderinin hikâyesi de atıldığı için hikâye sayısına dahildir."""
+        day = self._ig_day()
+        posts = sum(1 for x in day if x.get("format") == "post")
+        return (max(0, int(self._ig_cfg("instagram_daily_posts", 4) or 0) - posts),
+                max(0, int(self._ig_cfg("instagram_daily_stories", 7) or 0) - len(day)))
+
+    def _social_fallback(self, post: dict, has_photo: bool) -> dict:
+        """Yapay zeka yanıt vermezse kaba kural: çok büyük haber gönderi, büyük haber hikâye, gerisi paylaşılmaz."""
+        appeal = int(post.get("appeal") or max(1, int(post.get("importance") or 6) - 1))
+        imp = int(post.get("importance") or 0)
+        fmt = "post" if appeal >= 9 and imp >= 9 and has_photo else "story" if appeal >= 8 else "none"
+        return {"format": fmt, "score": appeal, "reason": "Yapay zeka yanıt vermedi; ilgi puanına göre karar verildi.",
+                "votes": []}
+
+    def social_desk(self, post: dict) -> str:
+        """Sosyal medya masası (haber editörü, sosyal medya editörü, görsel yönetmen) yayınlanan haberi değerlendirir:
+        "post" (kalıcı gönderi + hikâye), "story" (yalnızca hikâye) ya da "none". Günlük sınırlar ve alt puanlar kodda da
+        uygulanır; seçilen haber Instagram sırasına girer."""
+        posts_left, stories_left = self.ig_budget()
+        ph = self.vis.best_photo(post)
+        if not stories_left:
+            out = {"format": "none", "score": 0, "reason": "Bugünkü Instagram sınırı doldu.", "votes": []}
+        else:
+            photo = (f"real photo from {ph.get('credit') or 'the source'} ({ph.get('w')}x{ph.get('h')})"
+                     f"{', a screenshot/graphic' if ph.get('graphic') else ''}" if ph else "none (only a colored background)")
+            outlets = len({s.get("name") for s in (post.get("sources") or []) + (post.get("coverage") or []) if s.get("name")})
+            shared = [{"time": local(x.get("at"), self.cfg.tz).strftime("%H:%M") if x.get("at") else "",
+                       "format": x.get("format"), "title": x.get("title", "")} for x in self._ig_day()]
+            now_l = local(now_utc(), self.cfg.tz)
+            out = None
+            if self.llm:
+                try:
+                    out = self.llm.json(self.cfg.get("ai", "writer_model", "gemini-flash-latest"),
+                                        social_system(self.brand, int(self._ig_cfg("instagram_daily_posts", 4) or 0),
+                                                      int(self._ig_cfg("instagram_daily_stories", 7) or 0)),
+                                        social_user(post, photo, outlets, shared, posts_left, stories_left,
+                                                    now_l.strftime("%H:%M")),
+                                        SOCIAL_SCHEMA, max_tokens=1500)
+                except LLMError as e:
+                    log.warning("Sosyal medya masası yanıt vermedi: %s", e)
+            if not isinstance(out, dict) or out.get("format") not in ("post", "story", "none"):
+                out = self._social_fallback(post, bool(ph))
+        fmt, score = out.get("format"), int(out.get("score") or 0)
+        post_min = int(self._ig_cfg("instagram_post_min", 8) or 0)
+        story_min = int(self._ig_cfg("instagram_story_min", 6) or 0)
+        if fmt == "post" and (not posts_left or score < post_min):
+            fmt = "story"
+        if fmt == "story" and (not stories_left or score < story_min):
+            fmt = "none"
+        reason = clip(str(out.get("reason") or "").strip(), 300)
+        votes = [{"role": v.get("role"), "format": v.get("format"), "score": v.get("score"),
+                  "reason": clip(str(v.get("reason") or ""), 200)} for v in out.get("votes") or [] if isinstance(v, dict)]
+        post["social"] = {"format": fmt, "score": score, "reason": reason, "votes": votes, "at": iso(now_utc())}
+        self.store.save_post(post)
+        if fmt in IG_FORMATS:
+            self._ig_day().append({"id": post["id"], "format": fmt, "at": iso(now_utc()), "title": clip(post["title"], 90)})
+            self.ig_enqueue(post, fmt=fmt, note=reason)
+        log.info("Sosyal medya masası: %s → %s (puan %s) %s", post["id"], fmt, score, reason)
+        return fmt
 
     def _ig_drop(self, did: str, note: str = "", cancelled: bool = False) -> bool:
@@ -2196,7 +2298,8 @@
             return
         it = q[0]
+        fmt = it.get("format", "post")
         post = self.store.load_post(it["id"])
         urls = self._ig_urls(post)
-        code = head_ok(urls["post"])
+        code = head_ok(urls["post" if fmt == "post" else "story"])
         if code != 200:
             waited = hours_since(it["queued_at"]) * 60
@@ -2210,5 +2313,5 @@
             return
         try:
-            if not it.get("media_id"):
+            if fmt == "post" and not it.get("media_id"):
                 caption = clip(self.instagram_caption(post), 2150)
                 mid, link = self._ig_run(cli.carousel, [urls[k] for k in self._ig_kinds()], caption)
@@ -2216,4 +2319,8 @@
                 self.state["ig_last_at"] = iso(now_utc())
                 self.store.bump(self.today(), "instagram")
+            elif fmt == "story" and not it.get("story_id"):
+                it["story_id"] = self._ig_run(cli.story, urls["story"])
+                self.state["ig_last_at"] = iso(now_utc())
+                self.store.bump(self.today(), "instagram_story")
         except InstagramError as e:
             if e.auth:
@@ -2227,7 +2334,8 @@
                 self._ig_drop(it["id"], f"⚠️ <b>Instagram'da paylaşılamadı</b>\n{esc(post['title'])}\n<i>{esc(e)}</i>")
             return
-        if self._ig_cfg("instagram_story", True) and not it.get("story_id"):
+        if fmt == "post" and self._ig_cfg("instagram_story", True) and not it.get("story_id"):
             try:
                 it["story_id"] = self._ig_run(cli.story, urls["story"])
+                self.store.bump(self.today(), "instagram_story")
             except InstagramError as e:  # hikâye olmasa da gönderi paylaşıldı; sırayı tıkama
                 log.warning("Instagram hikâyesi paylaşılamadı (%s): %s", post["id"], e)
@@ -2236,9 +2344,15 @@
         done = self.state.setdefault("ig_done", [])
         done.append({"id": post["id"], "at": iso(now_utc()), "permalink": it.get("permalink", ""),
-                     "story": bool(it.get("story_id"))})
+                     "story": bool(it.get("story_id")), "format": fmt})
         self.state["ig_done"] = done[-200:]
-        story = " + hikâye" if it.get("story_id") else (", hikâye paylaşılamadı" if it.get("story_error") else "")
+        # profildeki bağlantı sayfası (/instagram/) Instagram'da paylaşılan haberleri listeler
+        post["ig"] = {"format": fmt, "at": iso(now_utc()), "permalink": it.get("permalink", "")}
+        self.store.save_post(post)
+        if fmt == "post":
+            what = "gönderi" + (" + hikâye" if it.get("story_id") else (", hikâye paylaşılamadı" if it.get("story_error") else ""))
+        else:
+            what = "hikâye"
         kb = [[{"text": "📸 Instagram'da aç", "url": it["permalink"]}]] if it.get("permalink") else None
-        self._ig_msg(it, f"✅ <b>Instagram'da paylaşıldı</b> (carousel{story})\n{esc(post['title'])}", kb)
+        self._ig_msg(it, f"✅ <b>Instagram'da paylaşıldı</b> ({what})\n{esc(post['title'])}", kb)
         log.info("Instagram'da paylaşıldı: %s %s", post["id"], it.get("permalink", ""))
 
@@ -2255,5 +2369,6 @@
             if not post:
                 continue
-            for k in self._ig_kinds() + ["story"]:
+            kinds = self._ig_kinds() + ["story"] if it.get("format", "post") == "post" else ["story"]
+            for k in kinds:
                 try:
                     shutil.copyfile(self._card(post, k), folder / f"{post['id']}-{k}.jpg")
@@ -2290,5 +2405,9 @@
         lines = [f"📸 <b>Instagram</b> {'⏸ kapalı' if self.state.get('ig_off') else '▶️ açık'}"
                  f"{' · @' + esc(d['username']) if d.get('username') else ''}",
-                 f"Bugün: {c.get('instagram', 0)} paylaşım · Sırada: {len(self.state.get('ig_queue') or [])}"]
+                 f"Bugün: {c.get('instagram', 0)} gönderi, {c.get('instagram_story', 0)} hikâye · "
+                 f"Sırada: {len(self.state.get('ig_queue') or [])}"]
+        if not self._ig_cfg("instagram_every_post", True):
+            pl, sl = self.ig_budget()
+            lines.append(f"Sosyal medya masası seçiyor · bugün kalan hak: {pl} gönderi, {sl} hikâye")
         a, b = (self._ig_cfg("instagram_hours", IG_WINDOW_DEFAULT) or [0, 24])[:2]
         lines.append(f"Paylaşım saatleri: {a:02d}:00–{b:02d}:00 · en az {self._ig_cfg('instagram_min_gap_minutes', 15)} dk arayla")
--- a/haberbot/llm.py
+++ b/haberbot/llm.py
@@ -333,4 +333,18 @@
         if "stories" in schema.get("properties", {}):
             return self._triage(user)
+        if "votes" in schema.get("properties", {}):       # sosyal medya masası: ilgi puanı ve fotoğrafa göre
+            m = re.search(r"APPEAL \(homepage, 1–10\): (\d+)", user)
+            appeal = int(m.group(1)) if m else 5
+            photo = "PHOTO: none" not in user
+            left = re.search(r"REMAINING BUDGET TODAY: posts (\d+), stories (\d+)", user)
+            posts_left, stories_left = (int(left.group(1)), int(left.group(2))) if left else (1, 1)
+            fmt, score = ("post", 9) if appeal >= 9 and photo else ("story", 7) if appeal >= 7 else ("none", 4)
+            if fmt == "post" and not posts_left:
+                fmt = "story"
+            if fmt == "story" and not stories_left:
+                fmt = "none"
+            votes = [{"role": r, "format": fmt, "score": score, "reason": "Test modu oyu"}
+                     for r in ("haber_editoru", "sosyal_medya_editoru", "gorsel_yonetmen")]
+            return {"votes": votes, "format": fmt, "score": score, "reason": "Test modu kararı"}
         if "decisions" in schema.get("properties", {}):   # yayın yönetmeni: masanın puanına göre
             out = []
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -555,2 +555,75 @@
 def photo_user(title: str, summary: str, n: int) -> str:
     return f"STORY TITLE: {title}\nSUMMARY: {summary}\nNUMBER OF IMAGES: {n} (numbered 0 to {n - 1} in order)"
+
+
+# ── Sosyal medya masası: yayınlanan haber Instagram'a girer mi, hangi biçimde? ──
+SOCIAL_ROLES = ("haber_editoru", "sosyal_medya_editoru", "gorsel_yonetmen")
+SOCIAL_SCHEMA = {
+    "type": "object",
+    "properties": {
+        "votes": {"type": "array", "items": {"type": "object", "properties": {
+            "role": {"type": "string", "enum": list(SOCIAL_ROLES)},
+            "format": {"type": "string", "enum": ["post", "story", "none"]},
+            "score": {"type": "integer"},
+            "reason": {"type": "string"}},
+            "required": ["role", "format", "score", "reason"], "additionalProperties": False}},
+        "format": {"type": "string", "enum": ["post", "story", "none"]},
+        "score": {"type": "integer"},
+        "reason": {"type": "string"},
+    },
+    "required": ["votes", "format", "score", "reason"],
+    "additionalProperties": False,
+}
+
+
+def social_system(site_name: str, posts_per_day: int, stories_per_day: int) -> str:
+    return f"""You are the social media desk of "{site_name}", a Turkish technology news site (AI, gadgets, cars, games,
+startups). A story was just published on the site. Three editors decide together whether it goes to the site's Instagram
+account and in which format. The account's value depends on ruthless selection: if it shares everything, it becomes
+noise and nobody follows it. Sharing nothing is a perfectly good outcome.
+
+FORMATS
+- "post": a permanent carousel on the profile grid. Only the day's most significant stories with the broadest appeal:
+  big launches and reveals from famous brands (Apple, Samsung, Google, OpenAI, Tesla, Togg, PlayStation, GTA…), news that
+  a broad Turkish audience will talk about, save or send to friends, major Türkiye tech news. Target about
+  {max(1, posts_per_day - 1)}–{posts_per_day} posts on a busy day of ~15 stories; most days fewer is better than weak posts.
+  Every post is also shared as a story.
+- "story": a 24-hour story. Notable, broadly interesting stories that are worth a glance but not worth a permanent spot.
+  Target about {max(1, stories_per_day - 1)}–{stories_per_day} stories per day in total (stories of posts included).
+- "none": do not share. Niche, specialist, B2B or industry-only news, routine software betas and minor updates, price
+  lists and campaigns, small funding rounds, stock and earnings news (unless huge and widely known), rumors and leaks,
+  stories very similar to something already shared today.
+
+THE THREE EDITORS (each votes format, score 1–10 and one short reason in Turkish)
+1. haber_editoru (news editor): news value, significance, timeliness, confirmed facts, relevance for Türkiye.
+2. sosyal_medya_editoru (social media editor): would a broad Turkish Instagram audience (18–40, curious about tech,
+   cars, games and AI but not specialists) stop scrolling, save or share it? Is it too similar to today's earlier posts?
+3. gorsel_yonetmen (visual director): is there a strong real photo (the product, the car, the game, the person, the scene)
+   that works full-screen? Stories without a real photo, with a dull photo (logos, screenshots of text, charts) rarely
+   make a good post; at best a story.
+
+DECISION
+- Final "format": "post" only if at least two editors vote "post" and the desk score is 8 or more and post budget remains;
+  "story" if the desk score is 6 or more and story budget remains; otherwise "none".
+- Respect the remaining budget for today; never lower the bar just because budget is left late in the day.
+- Balance: avoid two posts about the same brand or topic on the same day; vary categories when quality is equal.
+- "score": the desk's overall 1–10 score. "reason": one clear sentence in Turkish explaining the decision for the owner."""
+
+
+def social_user(post: dict, photo: str, outlets: int, shared_today: list[dict], posts_left: int, stories_left: int,
+                local_time: str) -> str:
+    lines = [
+        "STORY:",
+        f"TITLE: {post.get('title', '')}",
+        f"CATEGORY: {post.get('category', '')}",
+        f"SUMMARY: {post.get('summary', '')}",
+        f"KEY POINTS: {' / '.join(post.get('carousel_points') or [])}",
+        f"IMPORTANCE (news desk, 1–10): {post.get('importance', '')} · APPEAL (homepage, 1–10): {post.get('appeal', '')}",
+        f"OUTLETS COVERING IT: {outlets}",
+        f"PHOTO: {photo}",
+        "",
+        "ALREADY SHARED ON INSTAGRAM TODAY:",
+    ]
+    lines += [f"- {x.get('time', '')} {x.get('format')}: {x.get('title', '')}" for x in shared_today] or ["- nothing yet"]
+    lines += ["", f"REMAINING BUDGET TODAY: posts {posts_left}, stories {stories_left}", f"LOCAL TIME: {local_time}"]
+    return "\n".join(lines)
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -627,4 +627,8 @@
         self._write("iletisim/index.html", self.env.get_template("contact.html").render(
             **ctx, canonical=f"{cfg.site_url}/iletisim/"))
+        # Instagram profilindeki bağlantı: Instagram'da paylaşılan haberler (yeniden eskiye)
+        ig_posts = sorted((p for p in posts if (p.get("ig") or {}).get("at")), key=lambda p: p["ig"]["at"], reverse=True)
+        self._write("instagram/index.html", self.env.get_template("instagram.html").render(
+            **ctx, posts=ig_posts[:36], canonical=f"{cfg.site_url}/instagram/", noindex=True))
         self._write("404.html", self.env.get_template("404.html").render(**ctx, canonical=cfg.site_url + "/", noindex=True))
         # arama sayfası (/ara/?q=…) ve tarayıcıda aranan haber dizini
--- a/haberbot/visuals.py
+++ b/haberbot/visuals.py
@@ -265,6 +265,52 @@
 
     @property
+    def card_style(self) -> str:
+        return (self.cfg.get("social", "card_style", "ozet") or "ozet").strip().lower()
+
+    @property
     def summary_style(self) -> bool:
-        return (self.cfg.get("social", "card_style", "ozet") or "ozet") == "ozet"
+        """3 sayfalı carousel (kapak + öne çıkanlar + neden önemli) üreten tarzlar."""
+        return self.card_style in ("ozet", "manset")
+
+    def best_photo(self, d: dict) -> dict | None:
+        """Kartta kullanılacak gerçek fotoğraf: haberin kapak fotoğrafı, yoksa en büyük fotoğrafı (yerel kopyası olan)."""
+        img = d.get("image") or {}
+        recs = [r for r in d.get("photos") or [] if r.get("file") and (self.cfg.images_dir / r["file"]).exists()]
+        pick = None
+        if img.get("source") == "photo" and img.get("photo"):
+            pick = next((r for r in recs if r["file"] == img["photo"]), None)
+        if pick is None:
+            big = sorted((r for r in recs if (r.get("w") or 0) >= 600),
+                         key=lambda r: (bool(r.get("graphic")), -(r.get("w") or 0)))
+            pick = big[0] if big else None
+        return {**pick, "path": self.cfg.images_dir / pick["file"]} if pick else None
+
+    def manset_context(self, d: dict, kind: str) -> dict:
+        """Manşet tarzı Instagram kartı: haberin gerçek fotoğrafı tam ekran, koyu geçiş, beyaz başlık (sitenin mobil
+        manşeti). Fotoğraf yoksa kategori renginde koyu zemin. Hikâyede fotoğraf kırpılmadan ortada durur."""
+        cat = d.get("category", "teknoloji")
+        ph = self.best_photo(d)
+        credits = list(dict.fromkeys(s["name"] for s in d.get("sources", [])))
+        w, h = ((ph.get("w") or 1600), (ph.get("h") or 900)) if ph else (16, 9)
+        return {
+            "mode": self.NEWS_MODES[kind],
+            "photo": ph["path"].resolve().as_uri() if ph else "",
+            "photo_credit": (ph.get("credit") or "") if ph else "",
+            "photo_ratio": max(.5, min(2.2, w / max(1, h))),
+            "fit": bool(ph and ph.get("graphic")),
+            "accent": category_color(cat),
+            "label": category_label(cat),
+            "title": nobr(d.get("title", "")),
+            "short": nobr(d.get("short_title") or d.get("title", "")),
+            "summary": d.get("summary", ""),
+            "points": covers.carousel_points(d),
+            "why": covers.why_text(d),
+            "credits": ", ".join(credits[:3]),
+            "date": tr_date(d.get("published_at") or d.get("created_at"), self.cfg.tz, with_time=False),
+            "page": self.CAROUSEL.index(kind) + 1 if kind in self.CAROUSEL else 0,
+            "pages": len(self.CAROUSEL),
+            "site_host": self.cfg.site_url.split("://", 1)[-1] if "localhost" not in self.cfg.site_url else "",
+            "auto": bool(self.cfg.instagram_auto),
+        }
 
     def layout_for(self, d: dict) -> str:
@@ -313,4 +359,9 @@
     def render_card(self, d: dict, kind: str, hero: Path, out: Path) -> Path:
         size = self.SIZES[kind]
+        if kind in self.NEWS_MODES and self.card_style == "manset":
+            try:
+                return self.renderer.html_to_image("manset.html", self.manset_context(d, kind), size, out)
+            except Exception as e:  # noqa: BLE001
+                log.warning("Manşet kartı üretilemedi (%s), özet kartı kullanılıyor: %s", kind, e)
         if kind in self.NEWS_MODES and self.summary_style:
             try:
--- a/tests/test_instagram.py
+++ b/tests/test_instagram.py
@@ -165,4 +165,64 @@
 
 
+def _pub(i, hours, appeal, photo=True, **kw):
+    return {"id": f"s{i}", "slug": f"sosyal-{i}", "title": f"Sosyal haber {i}", "summary": "Kısa özet.",
+            "category": "teknoloji", "tags": [], "body": "Metin.", "sources": [{"name": "A", "url": "https://a"}],
+            "published_at": iso(now_utc() - timedelta(hours=hours)), "appeal": appeal, "importance": appeal, **kw}
+
+
+def test_social_desk_selects_and_limits():
+    """Sosyal medya masası: her haber paylaşılmaz; gönderi ve hikâye günlük sınırları ve alt puanlar uygulanır."""
+    FakeIG.calls = []
+    appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 200)
+    with tempfile.TemporaryDirectory() as t:
+        a = _app(Path(t))
+        a.cfg.raw["social"].update({"instagram_every_post": False, "instagram_daily_posts": 1, "instagram_daily_stories": 3})
+        a.vis.best_photo = lambda d: {"credit": "Kaynak", "w": 1600, "h": 900} if d.get("photo") else None
+        posts = [_pub(1, 1, 9, photo=True), _pub(2, 1, 9, photo=True), _pub(3, 1, 5), _pub(4, 1, 8), _pub(5, 1, 8)]
+        for p in posts:
+            p["photo"] = True
+            a.store.save_post(p)
+            a._send_social(p)
+        q = {x["id"]: x["format"] for x in a.state["ig_queue"]}
+        assert q == {"s1": "post", "s2": "story", "s4": "story"}            # 1 gönderi hakkı; ilgisiz haber elendi
+        assert a.store.load_post("s5")["social"]["reason"]                   # hikâye hakkı doldu: gerekçe yazıldı
+        assert a.store.load_post("s3")["social"]["format"] == "none"
+        assert a.ig_budget() == (0, 0)
+        # düğmeler: gönderiyi hikâyeye indir, hikâyeyi paylaşma (hak geri döner)
+        assert "Hikâye" in a._on_button("y", "s1")
+        assert a._on_button("x", "s4").startswith("🚫") and a.ig_budget() == (1, 1)
+        # sıradaki hikâye yalnızca hikâye olarak paylaşılır; profil sayfası için haberde işaret kalır
+        a.ig_tick()
+        assert [c[0] for c in FakeIG.calls] == ["story", "story"][:len(FakeIG.calls)] and FakeIG.calls[0][0] == "story"
+        assert a.store.load_post("s1")["ig"]["format"] == "story"
+
+
+def test_manset_cards_and_instagram_page():
+    """Manşet tarzı kartlar doğru boyutta üretilir; /instagram/ sayfası paylaşılan haberleri listeler."""
+    from PIL import Image
+    from haberbot.site import SiteBuilder
+    with tempfile.TemporaryDirectory() as t:
+        a = _app(Path(t))
+        a.cfg.raw["social"]["card_style"] = "manset"
+        a.cfg.images_dir.mkdir(parents=True, exist_ok=True)
+        Image.new("RGB", (1600, 900), (40, 90, 160)).save(a.cfg.images_dir / "m1-g0.webp")
+        post = _pub(1, 1, 9, image={"source": "photo", "photo": "m1-g0.webp"},
+                    photos=[{"file": "m1-g0.webp", "credit": "Apple", "w": 1600, "h": 900}],
+                    carousel_points=["Birinci madde.", "İkinci madde.", "Üçüncü madde."])
+        post["id"] = "m1"
+        a.store.save_post(post)
+        assert a.vis.best_photo(post)["credit"] == "Apple"
+        sizes = {k: Image.open(a._card(post, k)).size for k in ("post", "c2", "c3", "story")}
+        assert sizes == {"post": (1080, 1350), "c2": (1080, 1350), "c3": (1080, 1350), "story": (1080, 1920)}
+        post2 = {**_pub(2, 2, 8), "ig": {"format": "story", "at": iso(now_utc())}}
+        a.store.save_post(post2)
+        if a._vis:
+            a._vis.close()
+            a._vis = None
+        SiteBuilder(a.cfg).build()
+        page = (a.cfg.out_dir / "instagram" / "index.html").read_text(encoding="utf-8")
+        assert "Sosyal haber 2" in page and "Sosyal haber 1" not in page
+
+
 def test_missing_card_triggers_rebuild():
     appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 404)
@@@SM@@@ FILE templates/cards/manset.html
{# Smarity Instagram kartı: "Manşet" tarzı (sitenin mobil manşetiyle aynı dil).
   mode: cover  (gönderi 1/3: tam ekran fotoğraf, koyu geçiş, kategori etiketi, beyaz başlık)
         points (gönderi 2/3: öne çıkan 3 madde, fotoğrafın bulanık hâli zeminde)
         why    (gönderi 3/3: neden önemli + haberin tamamı için yönlendirme)
         story  (hikâye 1080×1920: fotoğraf kırpılmadan ortada, başlık, "Haberi oku" düğmesi; Instagram'ın üst ve alt
                 çubuklarına denk gelen alanlarda yalnızca zemin var — üst 250 px, alt 340 px)
   Fotoğraf yoksa kategori renginde koyu, yumuşak ışıklı zemin. #}
<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<style>
@font-face { font-family: "IS"; src: url("{{ font_dir }}/InstrumentSans-Regular.ttf"); font-weight: 400; }
@font-face { font-family: "IS"; src: url("{{ font_dir }}/InstrumentSans-Bold.ttf"); font-weight: 700; }
:root { --c: {{ accent }}; --ink: #1D1D1F; --soft: rgba(255,255,255,.74); }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: {{ W }}px; height: {{ H }}px; overflow: hidden; }
body { font-family: "IS", system-ui, sans-serif; color: #fff; background: #0B0B10; -webkit-font-smoothing: antialiased;
  position: relative; font-kerning: normal; }
.abs { position: absolute; }
h1, .h { font-weight: 700; letter-spacing: -.035em; line-height: 1.05; text-wrap: balance; }
.logo { position: absolute; left: 64px; height: 42px; display: block; }
.ph { overflow: hidden; } .ph img { width: 100%; height: 100%; object-fit: cover; display: block; }
/* zemin: fotoğraf (ya da fotoğrafın bulanık hâli) veya kategori renginde ışık */
.bg-photo { position: absolute; inset: 0; }
.bg-blur { position: absolute; inset: -80px; }
.bg-blur img { width: 100%; height: 100%; object-fit: cover; filter: blur(46px) saturate(1.25); }
.bg-art { position: absolute; inset: 0;
  background: radial-gradient(110% 70% at 15% 8%, color-mix(in srgb, var(--c) 62%, transparent), transparent 62%),
              radial-gradient(90% 60% at 95% 92%, color-mix(in srgb, var(--c) 45%, #00D1B2 30%), transparent 64%),
              #0B0B10; }
.dim { position: absolute; inset: 0; background: rgba(10, 10, 14, .70); }
.chip { display: inline-block; background: var(--c); color: #fff; font-weight: 700; font-size: 28px; line-height: 1;
  padding: 12px 22px; border-radius: 999px; letter-spacing: -.01em; }
.label { font-size: 30px; font-weight: 700; color: color-mix(in srgb, var(--c) 50%, #fff); letter-spacing: -.01em; }
.meta { font-size: 24px; color: var(--soft); }
.credit { position: absolute; right: 16px; bottom: 16px; font-size: 21px; padding: 7px 14px; border-radius: 999px;
  background: rgba(0,0,0,.55); color: #fff; }
.list { list-style: none; display: grid; gap: 46px; }
.list li { display: grid; grid-template-columns: 56px 1fr; gap: 26px; font-size: 42px; line-height: 1.28; letter-spacing: -.012em; }
.list b { width: 56px; height: 56px; border-radius: 50%; background: var(--c); color: #fff; display: grid; place-items: center;
  font-size: 28px; margin-top: 2px; }
.box { background: rgba(255,255,255,.13); border: 1px solid rgba(255,255,255,.24); border-radius: 28px; padding: 34px 40px; }
.btn { display: inline-flex; align-items: center; gap: 14px; font-weight: 700; font-size: 40px; line-height: 1;
  padding: 28px 46px; border-radius: 999px; background: #fff; color: var(--ink); }
.col { position: absolute; left: 64px; right: 64px; display: flex; flex-direction: column; justify-content: center; }
</style></head>
<body>
{% set arrow %}<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7M9 7h8v8"/></svg>{% endset %}

{% if mode == 'cover' %}
  {% if photo and not fit %}
  <div class="bg-photo ph"><img src="{{ photo }}" alt=""></div>
  <div class="abs" style="inset:0;background:linear-gradient(180deg, rgba(0,0,0,.50) 0%, rgba(0,0,0,0) 17%, rgba(0,0,0,0) 30%, rgba(0,0,0,.84) 57%, rgba(0,0,0,.95) 100%)"></div>
  {% elif photo %}
  <div class="bg-blur ph"><img src="{{ photo }}" alt=""></div><div class="dim"></div>
  <div class="ph abs" style="left:64px;right:64px;top:140px;height:520px;border-radius:30px;background:#000"><img src="{{ photo }}" alt="" style="object-fit:contain"></div>
  {% else %}
  <div class="bg-art"></div>
  {% endif %}
  <img class="logo" src="{{ logo_light_uri }}" style="top:60px" alt="">
  <div class="abs" style="left:64px;right:64px;bottom:128px">
    <span class="chip">{{ label }}</span>
    <h1 data-max="{{ 360 if photo else 560 }}" style="font-size:{{ 80 if photo else 96 }}px;margin-top:26px">{{ title }}</h1>
  </div>
  <div class="abs meta" style="left:64px;right:260px;bottom:56px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">Kaynak: {{ credits }}{% if photo_credit %} · Görsel: {{ photo_credit }}{% endif %}</div>
  <div class="abs meta" style="right:64px;bottom:56px">{{ page }}/{{ pages }} · Kaydır →</div>

{% elif mode in ('points', 'why') %}
  {% if photo %}<div class="bg-blur ph"><img src="{{ photo }}" alt=""></div><div class="dim"></div>{% else %}<div class="bg-art"></div><div class="dim" style="background:rgba(10,10,14,.35)"></div>{% endif %}
  <img class="logo" src="{{ logo_light_uri }}" style="top:60px" alt="">
  {% if mode == 'points' %}
  <div class="col" style="top:150px;bottom:130px"><div>
    <span class="chip">{{ label }}</span>
    <h1 data-max="200" style="font-size:56px;margin-top:24px">{{ short }}</h1>
    <ul class="list" data-max="680" style="margin-top:56px">{% for t in points %}<li><b>{{ loop.index }}</b><span>{{ t }}</span></li>{% endfor %}</ul>
  </div></div>
  {% else %}
  <div class="col" style="top:150px;bottom:340px">
    <span class="label">Neden önemli?</span>
    <p class="h" data-max="640" style="font-size:58px;line-height:1.16;margin-top:24px;letter-spacing:-.025em">{{ why }}</p>
  </div>
  <div class="abs box" style="left:64px;right:64px;bottom:120px">
    <div style="font-size:36px;font-weight:700;letter-spacing:-.02em">Haberin tamamı ve tüm kaynaklar</div>
    <div style="font-size:28px;color:var(--soft);margin-top:8px">Profildeki bağlantıda{% if site_host %} · {{ site_host }}{% endif %}</div>
  </div>
  {% endif %}
  <div class="abs meta" style="right:64px;bottom:56px">{{ page }}/{{ pages }}</div>

{% else %}{# hikâye #}
  {% if photo %}<div class="bg-blur ph"><img src="{{ photo }}" alt=""></div><div class="dim" style="background:rgba(10,10,14,.62)"></div>{% else %}<div class="bg-art"></div>{% endif %}
  {# Instagram'ın üst çubuğu ilk 250 px'i, alt çubuğu son 340 px'i kaplar: içerik arada #}
  <div class="col" style="top:250px;bottom:340px;gap:0">
    <img src="{{ logo_light_uri }}" style="height:42px;align-self:flex-start" alt="">
    {% if photo %}
    {% set ph_h = [[952 / photo_ratio, 420]|max, 640]|min %}
    <div class="ph" style="position:relative;margin-top:40px;height:{{ ph_h|int }}px;border-radius:32px;background:#000;flex:none">
      <img src="{{ photo }}" alt=""{% if fit %} style="object-fit:contain"{% endif %}>{% if photo_credit %}<span class="credit">Görsel: {{ photo_credit }}</span>{% endif %}
    </div>
    {% endif %}
    <div style="margin-top:{{ 44 if photo else 120 }}px">
      <span class="chip">{{ label }}</span>
      <h1 data-max="{{ 330 if photo else 620 }}" style="font-size:{{ 78 if photo else 100 }}px;margin-top:24px">{{ title }}</h1>
      <div class="meta" style="margin-top:20px;font-size:26px">Kaynak: {{ credits }}</div>
    </div>
    <div style="margin-top:44px;display:flex;align-items:center;gap:28px;flex-wrap:wrap">
      <span class="btn">Haberi oku {{ arrow }}</span>
      {% if auto %}<span class="meta" style="font-size:28px;line-height:1.3">Bağlantı profilde<br>{{ site_host }}</span>{% endif %}
    </div>
  </div>
{% endif %}

<script>
function fitH(el, max) { let fs = parseFloat(getComputedStyle(el).fontSize); while (el.scrollHeight > max && fs > 20) { fs -= 2; el.style.fontSize = fs + "px"; } }
function fitCol() {
  // hikâyede tüm içerik güvenli alana sığmazsa başlık küçülür
  document.querySelectorAll(".col").forEach(function (c) {
    var h1 = c.querySelector("h1"); if (!h1) return;
    var fs = parseFloat(getComputedStyle(h1).fontSize);
    while (c.scrollHeight > c.clientHeight + 1 && fs > 40) { fs -= 2; h1.style.fontSize = fs + "px"; }
  });
}
document.fonts.ready.then(function () {
  document.querySelectorAll("[data-max]").forEach(function (e) { fitH(e, +e.dataset.max); });
  fitCol();
  Promise.all(Array.prototype.slice.call(document.images).map(function (i) {
    return i.complete ? 1 : new Promise(function (r) { i.onload = i.onerror = r; }); }))
    .then(function () { window.__ready = true; });
});
</script>
</body></html>
@@@SM@@@ FILE templates/instagram.html
{% extends "base.html" %}
{% from "_macros.html" import card, crumbs %}
{% block title %}Instagram'da paylaştıklarımız | {{ site.name }}{% endblock %}
{% block description %}{{ site.name }} Instagram hesabında paylaşılan haberlerin tamamı: hikâyede ya da gönderide gördüğün haberi burada bul, dokun ve oku.{% endblock %}
{% block main %}
{{ crumbs([("Ana sayfa", site.base ~ "/", site.url ~ "/"), ("Instagram", site.base ~ "/instagram/", site.url ~ "/instagram/")]) }}
<header class="page-head wrap" style="--c:#6E6E73">
  <span class="eyebrow">Instagram</span>
  <h1>Instagram'da<br>paylaştıklarımız.</h1>
  <p>Hikâyede ya da gönderide gördüğün haber burada. Dokun, tamamını kaynağıyla oku.</p>
</header>
<section class="wrap sec-tight">
  {% if posts %}
  <div class="grid">{% for p in posts %}{{ card(p, heading='h2') }}{% endfor %}</div>
  {% else %}
  <p class="muted">Henüz paylaşım yok. <a href="{{ site.base }}/haberler/">Son haberlere göz at</a>.</p>
  {% endif %}
  <p style="margin-top:32px;text-align:center"><a class="more" href="{{ site.base }}/haberler/">Tüm haberler</a></p>
</section>
{% endblock %}
@@@SM@@@ SHA
2edb431bd75915e259a4232243aadce6b1a1e87cdba075286fdaf121e7755f45 config.yaml
e1d3a1f9f794633c6a7e31c2c29e9157746b7fe4a8cf0f449865b281f31d7ac3 haberbot/app.py
dbc2ea84e98766f888cf87cf0d2f8f486db27922be160cda1dc833f5c916812a haberbot/llm.py
19f23c62a384900ccaf8ea690e1caf8b6fdf91f28eddc3f937ce9f35733ed656 haberbot/prompts.py
c94d07e7a7ba8149918f9753fb40078387d272904d37a370a530f09c70e11045 haberbot/site.py
8ad29b98455b96887e6f4b64d411c2a813c5201a099e70628fd4153d7362421e haberbot/visuals.py
27fd6151bff80f818a399cff8647cf8c86406da95c4e8e20deebe1c24c2dd1b1 tests/test_instagram.py
513b73a665dad5445b32f3dc9aaf7bcf8bb94a972fb0e934014e017bf1237771 templates/cards/manset.html
5fb4cb2184e4ed9a8187f19484316470fd9ed536eb7260b03f3f3a16ac3528d1 templates/instagram.html
