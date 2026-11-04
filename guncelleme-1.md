SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -126,4 +126,6 @@
   instagram_post_min: 8            # masanın gönderi için istediği en düşük puan (1–10)
   instagram_story_min: 6           # hikâye için en düşük puan
+  instagram_visual_check: true     # görsel yönetmen her kartı paylaşımdan önce inceler (uygun değilse başka hâli dener ya da paylaşmaz)
+  instagram_visual_min: 7          # görsel kontrolünde geçmek için en düşük puan (1–10)
   instagram_story: true            # carousel'e ek olarak hikâye de paylaşılsın
   instagram_hours: [8, 24]         # paylaşım saatleri; gece yayınlanan haberler sabah 8'de sırayla paylaşılır
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -19,5 +19,5 @@
 from .llm import LLMError, MockLLM, estimate_cost, make_llm
 from .prompts import (APPEAL_SCHEMA, COVERLINE_SCHEMA, EDIT_SCHEMA, FLAG_LABELS, FLAGS, PHOTO_SCHEMA, SEO_SCHEMA, TRIAGE_SCHEMA,
-                      SOCIAL_SCHEMA, social_system, social_user,
+                      SOCIAL_SCHEMA, social_system, social_user, VISUAL_SCHEMA, visual_system, visual_user,
                       photo_system, photo_user,
                       WRITE_SCHEMA, appeal_system, appeal_user, coverline_system, coverline_user, edit_system, edit_user,
@@ -42,4 +42,6 @@
 IG_WINDOW_DEFAULT = [8, 24]
 IG_FORMATS = {"post": "Gönderi + hikâye", "story": "Hikâye"}   # Instagram paylaşım biçimleri (sıradaki haber)
+# görsel yönetmenin onayladığı kart hâli (Telegram'da gösterilir)
+IG_VARIANTS = {"auto": "fotoğraf tam ekran", "contain": "fotoğraf kırpılmadan", "nophoto": "fotoğrafsız, kategori renginde zemin"}
 CONF_LABEL = {"yuksek": "yüksek", "orta": "orta", "dusuk": "düşük"}
 COMMANDS = [
@@ -1016,10 +1018,10 @@
         return st.post_image(d["id"]) if st.post_path(d["id"]).exists() else st.draft_image(d["id"])
 
-    def _card(self, d: dict, kind: str):
-        """Kartı (.cache içine) üret ve yolunu döndür."""
+    def _card(self, d: dict, kind: str, variant: str = "auto"):
+        """Kartı (.cache içine) üret ve yolunu döndür. variant: görsel yönetmenin seçtiği hâl (auto / contain / nophoto)."""
         hero = self._hero(d)
         if not hero.exists():
             d["image"] = self.vis.make_hero(d, hero)
-        return self.vis.render_card(d, kind, hero, self.store.card_path(d["id"], kind))
+        return self.vis.render_card(d, kind, hero, self.store.card_path(d["id"], kind), variant)
 
     # ── 3) YAYIN ────────────────────────────────────────────
@@ -1397,4 +1399,17 @@
             self._ig_msg(it, *self._ig_queue_msg(post, it))
             return f"📸 {IG_FORMATS[it['format']]} olarak paylaşılacak"
+        if action == "k":                 # görsel kontrolünden geçmeyeni sahibinin onayıyla yine de paylaş
+            post = st.load_post(did)
+            if not post:
+                return "Bu haber artık yayında değil."
+            soc = post.get("social") or {}
+            fmt = (soc.get("vfail") or {}).get("format") or soc.get("format")
+            if not self.ig_enqueue(post, mid=self._cb_mid, fmt=fmt if fmt in IG_FORMATS else "story"):
+                return "Zaten sırada ya da paylaşıldı."
+            it = next(x for x in self.state["ig_queue"] if x["id"] == did)
+            it.update({"vok": True, "variant": (soc.get("vfail") or {}).get("variant") or "auto",
+                       "vcheck": {"skipped": True, "at": iso(now_utc())}})
+            self._ig_msg(it, *self._ig_queue_msg(post, it))
+            return "📸 Görsel kontrolü atlanarak sıraya alındı"
         if action == "q":
             post = st.load_post(did)
@@ -2110,6 +2125,16 @@
         fmt = it.get("format", "post")
         where = "" if not self.state.get("ig_off") else " (Instagram şu an kapalı: /instagram ac)"
+        vc = it.get("vcheck") or {}
+        if it.get("vok") and vc.get("skipped"):
+            vline = "\n🖼️ Görsel kontrolü senin onayınla atlandı"
+        elif it.get("vok") and vc:
+            look = f", {IG_VARIANTS[it['variant']]}" if it.get("variant") in IG_VARIANTS and it["variant"] != "auto" else ""
+            vline = f"\n🖼️ Görsel kontrolü geçti ({vc.get('score')}/10{look})"
+        elif self._ig_cfg("instagram_visual_check", True):
+            vline = "\n🖼️ Görseller hazırlanınca görsel yönetmen kontrol edecek"
+        else:
+            vline = ""
         text = (f"📸 <b>Instagram: {IG_FORMATS[fmt]}</b>{where}\n{esc(post['title'])}"
-                f"{chr(10) + '<i>' + esc(it['note']) + '</i>' if it.get('note') else ''}\n"
+                f"{chr(10) + '<i>' + esc(it['note']) + '</i>' if it.get('note') else ''}{vline}\n"
                 f"<i>Birkaç dakika içinde paylaşılacak.</i>")
         switch = ({"text": "Sadece hikâye", "callback_data": f"y:{post['id']}"} if fmt == "post"
@@ -2186,5 +2211,5 @@
         return fmt
 
-    def _ig_drop(self, did: str, note: str = "", cancelled: bool = False) -> bool:
+    def _ig_drop(self, did: str, note: str = "", cancelled: bool = False, keyboard=None) -> bool:
         q = self.state.get("ig_queue") or []
         it = next((x for x in q if x["id"] == did), None)
@@ -2197,13 +2222,15 @@
                          [[{"text": "↩️ Yine de paylaş", "callback_data": f"q:{did}"}]])
         elif note:
-            self._ig_msg(it, note)
+            self._ig_msg(it, note, keyboard)
         return True
 
     def _ig_problem(self, text: str) -> None:
         """Aynı uyarıyı en fazla 12 saatte bir gönder."""
+        plain = re.sub(r"<[^>]+>", "", text)
+        self.state["ig_problem"] = {"at": iso(now_utc()), "text": clip(html.unescape(plain), 400)}  # /instagram'da görünür
         if hours_since(self.state.get("ig_warned_at")) >= 12:
             self.state["ig_warned_at"] = iso(now_utc())
             self.notify("⚠️ <b>Instagram</b>: " + text)
-        log.warning("Instagram: %s", re.sub(r"<[^>]+>", "", text))
+        log.warning("Instagram: %s", plain)
 
     def _ig_client(self):
@@ -2240,4 +2267,5 @@
                                      "<b>IG_ACCESS_TOKEN</b> değerini güncelle.")
                 else:
+                    self.state["ig_problem"] = {"at": iso(now_utc()), "text": clip(f"hesap okunamadı: {e}", 400)}
                     log.warning("Instagram hesabı okunamadı: %s", e)
                 return None
@@ -2301,5 +2329,7 @@
         post = self.store.load_post(it["id"])
         urls = self._ig_urls(post)
-        code = head_ok(urls["post" if fmt == "post" else "story"])
+        # görsel yönetmen kartları onaylamadan paylaşılmaz (onay, kartlar siteye konurken verilir)
+        vetted = it.get("vok") or not self._ig_cfg("instagram_visual_check", True)
+        code = head_ok(urls["post" if fmt == "post" else "story"]) if vetted else 0
         if code != 200:
             waited = hours_since(it["queued_at"]) * 60
@@ -2307,5 +2337,6 @@
                 it["restaged_at"] = iso(now_utc())
                 self.store.site_dirty = True  # site yeniden yayınlansın, kartlar eklensin
-                log.info("Instagram kartı sitede yok (HTTP %s); site yeniden yayınlanacak", code)
+                log.info("Instagram kartı %s; site yeniden yayınlanacak",
+                         f"sitede yok (HTTP {code})" if vetted else "görsel kontrolünü bekliyor")
             return
         cli = self._ig_client()
@@ -2342,4 +2373,5 @@
                 it["story_error"] = str(e)[:200]
         q.remove(it)
+        self.state.pop("ig_problem", None)
         done = self.state.setdefault("ig_done", [])
         done.append({"id": post["id"], "at": iso(now_utc()), "permalink": it.get("permalink", ""),
@@ -2364,13 +2396,27 @@
         folder = out / "ig"
         folder.mkdir(parents=True, exist_ok=True)
-        n = 0
-        for it in q[:8]:
+        n, vets = 0, 0
+        for it in list(q[:8]):
             post = self.store.load_post(it["id"])
             if not post:
                 continue
             kinds = self._ig_kinds() + ["story"] if it.get("format", "post") == "post" else ["story"]
+            if not it.get("vok") and self._ig_cfg("instagram_visual_check", True) and self.llm:
+                if vets >= 4:                      # bir turda en fazla 4 haber kontrol edilir; gerisi sonraki turda
+                    continue
+                vets += 1
+                try:
+                    cards = self.ig_vet(post, it, kinds)
+                except Exception as e:  # noqa: BLE001
+                    log.warning("Görsel kontrolü yapılamadı (%s): %s", post["id"], e)
+                    cards = None
+                if not cards:
+                    continue
+            else:
+                cards = {}
             for k in kinds:
                 try:
-                    shutil.copyfile(self._card(post, k), folder / f"{post['id']}-{k}.jpg")
+                    shutil.copyfile(cards.get(k) or self._card(post, k, it.get("variant", "auto")),
+                                    folder / f"{post['id']}-{k}.jpg")
                     n += 1
                 except Exception as e:  # noqa: BLE001
@@ -2381,4 +2427,87 @@
         log.info("Instagram kartları siteye kondu: %d görsel", n)
         return n
+
+    # ── görsel yönetmen: kartların son kontrolü ─────────────
+    def _ig_variants(self, post: dict) -> list[str]:
+        """Denenecek kart hâlleri, sırayla: fotoğraf tam ekran → kırpılmadan çerçevede → fotoğrafsız renkli zemin."""
+        if self.vis.card_style != "manset":
+            return ["auto"]
+        ph = self.vis.best_photo(post)
+        if not ph:
+            return ["nophoto"]
+        return (["auto"] if ph.get("graphic") else ["auto", "contain"]) + ["nophoto"]
+
+    @staticmethod
+    def _card_jpeg(path, width: int = 720) -> bytes:
+        """Kartın küçültülmüş JPEG'i (yapay zekaya gönderilir; telefonda görülen boyuta yakın)."""
+        import io
+        from PIL import Image
+        im = Image.open(path).convert("RGB")
+        im.thumbnail((width, width * 2))
+        buf = io.BytesIO()
+        im.save(buf, "JPEG", quality=84)
+        return buf.getvalue()
+
+    def ig_vet(self, post: dict, it: dict, kinds: list[str]) -> dict | None:
+        """Görsel yönetmen, kartları Instagram'a gitmeden önce bitmiş hâlleriyle inceler: fotoğraf haberle ilgili mi,
+        başlık okunuyor mu, taşan / kesilen yazı, kötü kırpma, hikâyede güvenli alan, uygunsuz ya da yanıltıcı görsel.
+        Geçmezse önerdiği hâl denenir (fotoğraf kırpılmadan → fotoğrafsız); hiçbiri geçmezse haber Instagram'a gitmez.
+        Onaylanan kartların yollarını döndürür; yapay zeka yanıt vermezse None (sonraki turda yeniden denenir)."""
+        order = self._ig_variants(post)
+        tried = it.setdefault("vtried", [])
+
+        def pick(pref=None):
+            if pref in order and pref not in tried:
+                return pref
+            return next((v for v in order if v not in tried), None)
+
+        variant = pick(it.get("variant"))
+        min_score = int(self._ig_cfg("instagram_visual_min", 7) or 0)
+        model = self.cfg.get("ai", "visual_model", None) or self.cfg.get("ai", "writer_model", "gemini-flash-latest")
+        while variant:
+            cards = {k: self._card(post, k, variant) for k in kinds}
+            ph = self.vis.best_photo(post) if variant != "nophoto" else None
+            try:
+                res = self.llm.json(model, visual_system(self.brand),
+                                    visual_user(post, it.get("format", "post"), variant, kinds,
+                                                (ph or {}).get("credit", "") if ph else ""),
+                                    VISUAL_SCHEMA, max_tokens=900, images=[self._card_jpeg(cards[k]) for k in kinds])
+            except Exception as e:  # noqa: BLE001
+                it["variant"] = variant
+                it["verr"] = it.get("verr", 0) + 1
+                log.warning("Görsel yönetmen yanıt vermedi (%s), sonraki turda yeniden denenecek: %s",
+                            post["id"], str(e)[:160])
+                return None
+            if not isinstance(res, dict):
+                res = {}
+            tried.append(variant)
+            score = int(res.get("score") or 0)
+            ok = bool(res.get("ok")) and score >= min_score
+            issues = [clip(str(x).strip(), 160) for x in res.get("issues") or [] if str(x).strip()][:6]
+            it["vcheck"] = {"variant": variant, "ok": ok, "score": score, "issues": issues,
+                            "reason": clip(str(res.get("reason") or "").strip(), 300), "at": iso(now_utc())}
+            log.info("Görsel yönetmen: %s %s → %s (puan %s) %s", post["id"], variant, "uygun" if ok else "uygun değil",
+                     score, "; ".join(issues))
+            if ok:
+                it.update({"variant": variant, "vok": True})
+                self._ig_msg(it, *self._ig_queue_msg(post, it))
+                return cards
+            fix = res.get("fix")
+            if fix == "skip":
+                break
+            variant = pick({"contain_photo": "contain", "no_photo": "nophoto"}.get(fix))
+        vc = it.get("vcheck") or {}
+        detail = "; ".join(vc.get("issues") or []) or vc.get("reason") or ""
+        post.setdefault("social", {})["vfail"] = {"format": it.get("format", "post"), "variant": vc.get("variant", "auto"),
+                                                  "score": vc.get("score"), "issues": vc.get("issues") or [],
+                                                  "at": iso(now_utc())}
+        self.store.save_post(post)
+        day = self._ig_day()
+        day[:] = [x for x in day if x.get("id") != post["id"]]          # günlük hak geri döner
+        self._ig_drop(post["id"], f"🖼️ <b>Instagram'a gönderilmedi</b>: görseller kontrolden geçmedi\n"
+                                  f"{esc(post['title'])}\n<i>{esc(clip(detail, 400))}</i>",
+                      keyboard=[[{"text": "↩️ Yine de paylaş", "callback_data": f"k:{post['id']}"}]])
+        log.info("Görsel kontrolünden geçmedi, Instagram'a gönderilmeyecek: %s (%s)", post["id"], detail)
+        return None
 
     def ig_try_latest(self) -> str:
@@ -2414,4 +2543,11 @@
         if left is not None:
             lines.append(f"Anahtar: {left:.0f} gün geçerli (bot kendisi yeniler)")
+        prob = self.state.get("ig_problem") or {}
+        if prob and hours_since(prob.get("at")) < 48:
+            when = local(prob["at"], self.cfg.tz).strftime("%d.%m %H:%M")
+            lines.append(f"⚠️ Son sorun ({when}): {esc(prob.get('text', ''))}")
+        waiting = [x for x in self.state.get("ig_queue") or [] if not x.get("vok")]
+        if waiting and self._ig_cfg("instagram_visual_check", True):
+            lines.append(f"🖼️ Görsel kontrolü bekleyen: {len(waiting)}")
         for x in (self.state.get("ig_done") or [])[-3:][::-1]:
             p = self.store.load_post(x["id"]) or {}
--- a/haberbot/instagram.py
+++ b/haberbot/instagram.py
@@ -121,15 +121,36 @@
         return j
 
+    def _discover(self) -> str:
+        """Anahtarın eriştiği Facebook sayfalarına bağlı ilk Instagram işletme hesabının numarası."""
+        pages = self._req("GET", "me/accounts", fields="instagram_business_account{id,username}").get("data") or []
+        return next((str(p["instagram_business_account"]["id"]) for p in pages if p.get("instagram_business_account")), "")
+
     def me(self) -> dict:
         if not self.fb:
             return self._req("GET", "me", fields="user_id,username")
         ig_id = self.ig_id
-        if not ig_id:  # anahtarın eriştiği sayfalara bağlı ilk Instagram hesabı
-            pages = self._req("GET", "me/accounts", fields="instagram_business_account{id,username}").get("data") or []
-            ig_id = next((str(p["instagram_business_account"]["id"]) for p in pages if p.get("instagram_business_account")), "")
+        if ig_id:
+            try:
+                j = self._req("GET", ig_id, fields="id,username")
+            except InstagramError as e:
+                # numara yanlışsa ya da bu anahtara atanmamışsa: anahtarın gördüğü sayfalardan bulmayı dene
+                if e.transient:
+                    raise
+                try:
+                    found = self._discover()
+                except InstagramError:
+                    found = ""
+                if not found or found == ig_id:
+                    raise e
+                log.warning("Instagram hesap numarası %s okunamadı (%s); anahtarın eriştiği hesap %s kullanılacak",
+                            ig_id, e, found)
+                ig_id = found
+                j = self._req("GET", ig_id, fields="id,username")
+        else:  # anahtarın eriştiği sayfalara bağlı ilk Instagram hesabı
+            ig_id = self._discover()
             if not ig_id:
                 raise InstagramError("Anahtarın eriştiği bir Instagram hesabı bulunamadı; config.yaml → "
                                      "social.instagram_user_id alanına hesap numarasını yaz", 100)
-        j = self._req("GET", ig_id, fields="id,username")
+            j = self._req("GET", ig_id, fields="id,username")
         return {"id": str(j.get("id") or ig_id), "user_id": str(j.get("id") or ig_id), "username": j.get("username", "")}
 
--- a/haberbot/llm.py
+++ b/haberbot/llm.py
@@ -329,4 +329,6 @@
         if self.usage_cb:
             self.usage_cb(model, len(user) // 4, 300)
+        if "fix" in schema.get("properties", {}):         # görsel yönetmen: kartlar uygun
+            return {"ok": True, "score": 8, "issues": [], "fix": "none", "reason": "Test modu kontrolü"}
         if "keep" in schema.get("properties", {}):        # fotoğraf editörü: hepsi ilgili
             return {"keep": list(range(len(images or []))), "text": []}
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -628,2 +628,72 @@
     lines += ["", f"REMAINING BUDGET TODAY: posts {posts_left}, stories {stories_left}", f"LOCAL TIME: {local_time}"]
     return "\n".join(lines)
+
+
+# ── görsel yönetmen: Instagram kartlarının son kontrolü ──
+VISUAL_FIXES = ("none", "contain_photo", "no_photo", "skip")
+VISUAL_SCHEMA = {
+    "type": "object",
+    "properties": {
+        "ok": {"type": "boolean"},
+        "score": {"type": "integer"},
+        "issues": {"type": "array", "items": {"type": "string"}},
+        "fix": {"type": "string", "enum": list(VISUAL_FIXES)},
+        "reason": {"type": "string"},
+    },
+    "required": ["ok", "score", "issues", "fix", "reason"],
+    "additionalProperties": False,
+}
+VISUAL_KINDS = {"post": "post page 1/3, cover (1080x1350)", "c2": "post page 2/3, key points (1080x1350)",
+                "c3": "post page 3/3, why it matters (1080x1350)", "story": "story (1080x1920)"}
+VISUAL_LAYOUTS = {"auto": "the news photo full-bleed behind a dark gradient",
+                  "contain": "the news photo shown whole and uncropped in a rounded frame on a blurred copy of itself",
+                  "nophoto": "no photo, a dark background lit in the category color"}
+
+
+def visual_system(site_name: str) -> str:
+    return f"""You are the visual director of "{site_name}", a Turkish technology news site. Before anything is posted to the
+site's Instagram account you inspect the finished images exactly as followers will see them on a phone. Nothing weak,
+broken, misleading or absurd may go out: the account must look like one consistent, premium news brand, in the same
+style as the site (real news photo, dark gradient, bold white headline, a colored category chip, small white logo).
+
+CHECK EVERY IMAGE
+1. Photo fit: the photo clearly belongs to this story (the product, car, game, company, person or scene it is about).
+   Unacceptable: ads, unrelated stock photos, another story's thumbnail, an unrelated person, a logo or icon blown up to
+   fill the frame, memes, low-resolution, pixelated, blurry or heavily watermarked images, screenshots that are mostly text.
+2. Readability: every headline and text block is fully legible at phone size with strong contrast; no text sits on a busy
+   or bright part of the photo; text or logos printed in the photo do not clash with our own headline.
+3. Layout: no cut-off, overlapping or overflowing text, no clipped words, nothing lost at the edges, no empty or broken
+   photo area, no awkward crop (faces cut through the eyes, the product cut in half, the subject hidden behind the text).
+4. Story safe area: in the 1080x1920 story the logo, photo, headline and the white "Haberi oku" button stay out of the
+   top 13% and the bottom 18%, where Instagram draws its own bars.
+5. Taste and accuracy: nothing offensive, graphic, sexual or mocking; the picture matches the headline and does not
+   mislead; the set looks professional and consistent.
+
+DECISION
+- "ok": true only if the whole set can be posted exactly as it is.
+- "score": overall 1-10 (9-10 proud to post, 7-8 good, 6 or less do not post).
+- "issues": short notes in Turkish, one per problem, naming the image (e.g. "Hikâye: başlık fotoğraftaki yazıyla
+  çakışıyor"). Empty when there is nothing to fix.
+- "fix": what would solve the problems:
+  "none": nothing to fix;
+  "contain_photo": the photo is right, but the full-bleed crop or the text over it is the problem; show the whole photo
+  uncropped in a frame instead;
+  "no_photo": the photo itself is wrong, irrelevant, low quality or unsuitable; use the plain category-colored
+  background without a photo;
+  "skip": the story should not go to Instagram in any form.
+- "reason": one sentence in Turkish for the site owner."""
+
+
+def visual_user(post: dict, fmt: str, layout: str, kinds: list[str], photo_credit: str = "") -> str:
+    lines = [
+        f"TITLE: {post.get('title', '')}",
+        f"CATEGORY: {post.get('category', '')}",
+        f"SUMMARY: {post.get('summary', '')}",
+        f"PHOTO CREDIT: {photo_credit or 'none'}",
+        f"FORMAT: {'carousel post + the same story as a story' if fmt == 'post' else 'story only'}",
+        f"CURRENT LAYOUT: {VISUAL_LAYOUTS.get(layout, layout)}",
+        "",
+        "IMAGES, IN ORDER:",
+    ]
+    lines += [f"{i}. {VISUAL_KINDS.get(k, k)}" for i, k in enumerate(kinds, 1)]
+    return "\n".join(lines)
--- a/haberbot/visuals.py
+++ b/haberbot/visuals.py
@@ -286,9 +286,13 @@
         return {**pick, "path": self.cfg.images_dir / pick["file"]} if pick else None
 
-    def manset_context(self, d: dict, kind: str) -> dict:
+    # görsel yönetmenin denediği hâller: fotoğraf tam ekran / fotoğraf kırpılmadan çerçevede / fotoğrafsız renkli zemin
+    VARIANTS = ("auto", "contain", "nophoto")
+
+    def manset_context(self, d: dict, kind: str, variant: str = "auto") -> dict:
         """Manşet tarzı Instagram kartı: haberin gerçek fotoğrafı tam ekran, koyu geçiş, beyaz başlık (sitenin mobil
-        manşeti). Fotoğraf yoksa kategori renginde koyu zemin. Hikâyede fotoğraf kırpılmadan ortada durur."""
+        manşeti). Fotoğraf yoksa kategori renginde koyu zemin. Hikâyede fotoğraf kırpılmadan ortada durur.
+        variant: "contain" fotoğrafı kırpmadan çerçeveye koyar, "nophoto" fotoğrafı hiç kullanmaz."""
         cat = d.get("category", "teknoloji")
-        ph = self.best_photo(d)
+        ph = None if variant == "nophoto" else self.best_photo(d)
         credits = list(dict.fromkeys(s["name"] for s in d.get("sources", [])))
         w, h = ((ph.get("w") or 1600), (ph.get("h") or 900)) if ph else (16, 9)
@@ -298,5 +302,5 @@
             "photo_credit": (ph.get("credit") or "") if ph else "",
             "photo_ratio": max(.5, min(2.2, w / max(1, h))),
-            "fit": bool(ph and ph.get("graphic")),
+            "fit": bool(ph and (ph.get("graphic") or variant == "contain")),
             "accent": category_color(cat),
             "label": category_label(cat),
@@ -357,9 +361,9 @@
         return {**base, "edge": edge, "dark_edge": dark and ctx_layout == "product"}
 
-    def render_card(self, d: dict, kind: str, hero: Path, out: Path) -> Path:
+    def render_card(self, d: dict, kind: str, hero: Path, out: Path, variant: str = "auto") -> Path:
         size = self.SIZES[kind]
         if kind in self.NEWS_MODES and self.card_style == "manset":
             try:
-                return self.renderer.html_to_image("manset.html", self.manset_context(d, kind), size, out)
+                return self.renderer.html_to_image("manset.html", self.manset_context(d, kind, variant), size, out)
             except Exception as e:  # noqa: BLE001
                 log.warning("Manşet kartı üretilemedi (%s), özet kartı kullanılıyor: %s", kind, e)
--- a/templates/cards/manset.html
+++ b/templates/cards/manset.html
@@ -52,11 +52,14 @@
   <div class="abs" style="inset:0;background:linear-gradient(180deg, rgba(0,0,0,.50) 0%, rgba(0,0,0,0) 17%, rgba(0,0,0,0) 30%, rgba(0,0,0,.84) 57%, rgba(0,0,0,.95) 100%)"></div>
   {% elif photo %}
+  {# fotoğraf kırpılmadan: çerçeve, logo ile başlık arasındaki boşluğun ortasında durur #}
   <div class="bg-blur ph"><img src="{{ photo }}" alt=""></div><div class="dim"></div>
-  <div class="ph abs" style="left:64px;right:64px;top:140px;height:520px;border-radius:30px;background:#000"><img src="{{ photo }}" alt="" style="object-fit:contain"></div>
+  <div id="frame-zone" class="abs" style="left:64px;right:64px;top:132px;height:560px;display:flex;align-items:center;justify-content:center">
+    <img id="frame-img" src="{{ photo }}" alt="" style="display:block;width:100%;height:100%;object-fit:contain;border-radius:30px;box-shadow:0 24px 70px rgba(0,0,0,.45)">
+  </div>
   {% else %}
   <div class="bg-art"></div>
   {% endif %}
   <img class="logo" src="{{ logo_light_uri }}" style="top:60px" alt="">
-  <div class="abs" style="left:64px;right:64px;bottom:128px">
+  <div id="cover-text" class="abs" style="left:64px;right:64px;bottom:128px">
     <span class="chip">{{ label }}</span>
     <h1 data-max="{{ 360 if photo else 560 }}" style="font-size:{{ 80 if photo else 96 }}px;margin-top:26px">{{ title }}</h1>
@@ -93,5 +96,7 @@
     {% if photo %}
     {% set ph_h = [[952 / photo_ratio, 420]|max, 640]|min %}
-    <div class="ph" style="position:relative;margin-top:40px;height:{{ ph_h|int }}px;border-radius:32px;background:#000;flex:none">
+    {# kırpılmadan gösterilen fotoğrafta çerçeve fotoğrafın kendi oranında (yanlarda siyah bant kalmaz) #}
+    {% set ph_w = ([952, ph_h * photo_ratio]|min) if fit else 952 %}
+    <div class="ph" style="position:relative;margin-top:40px;height:{{ ph_h|int }}px;width:{{ ph_w|int }}px;align-self:{{ 'center' if fit else 'stretch' }};border-radius:32px;background:#000;flex:none">
       <img src="{{ photo }}" alt=""{% if fit %} style="object-fit:contain"{% endif %}>{% if photo_credit %}<span class="credit">Görsel: {{ photo_credit }}</span>{% endif %}
     </div>
@@ -111,4 +116,15 @@
 <script>
 function fitH(el, max) { let fs = parseFloat(getComputedStyle(el).fontSize); while (el.scrollHeight > max && fs > 20) { fs -= 2; el.style.fontSize = fs + "px"; } }
+function frame() {
+  // kırpılmamış fotoğraf: başlığın üstünde kalan alana, kendi oranıyla, ortalanarak yerleşir
+  var z = document.getElementById("frame-zone"), ct = document.getElementById("cover-text"), im = document.getElementById("frame-img");
+  if (!z || !ct) return;
+  var zh = Math.max(240, ct.getBoundingClientRect().top - 40 - 132);
+  z.style.height = zh + "px";
+  if (im && im.naturalWidth) {
+    var r = im.naturalWidth / im.naturalHeight, w = Math.min(z.clientWidth, zh * r);
+    im.style.width = w + "px"; im.style.height = (w / r) + "px"; im.style.objectFit = "cover";
+  }
+}
 function fitCol() {
   // hikâyede tüm içerik güvenli alana sığmazsa başlık küçülür
@@ -124,5 +140,5 @@
   Promise.all(Array.prototype.slice.call(document.images).map(function (i) {
     return i.complete ? 1 : new Promise(function (r) { i.onload = i.onerror = r; }); }))
-    .then(function () { window.__ready = true; });
+    .then(function () { frame(); window.__ready = true; });
 });
 </script>
--- a/tests/test_instagram.py
+++ b/tests/test_instagram.py
@@ -71,4 +71,5 @@
     raw["social"]["instagram_hours"] = [0, 24]
     raw["social"]["instagram_every_post"] = True
+    raw["social"]["instagram_visual_check"] = False   # görsel kontrolü ayrı testte
     cfg = Config(raw=raw, root=tmp, site_url="https://example.github.io/smarity", mock=True,
                  instagram_token="SECRET-TOKEN", telegram_chat_id="1")
@@ -225,4 +226,100 @@
 
 
+class Director:
+    """Görsel yönetmen yerine sırayla verilen yanıtları döndürür (yanıt kalmazsa hata verir)."""
+    def __init__(self, answers):
+        self.answers, self.seen = list(answers), []
+
+    def json(self, model, system, user, schema, max_tokens=4000, effort=None, images=None):
+        self.seen.append((user, len(images or [])))
+        if not self.answers:
+            raise RuntimeError("yanıt yok")
+        return self.answers.pop(0)
+
+
+def test_visual_check_variants():
+    """Görsel yönetmen: kartlar onaylanmadan paylaşılmaz; önerdiği hâl denenir; hiçbiri geçmezse haber düşer."""
+    from PIL import Image
+    FakeIG.calls = []
+    appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 200)
+    with tempfile.TemporaryDirectory() as t:
+        a = _app(Path(t))
+        a.cfg.raw["social"].update({"card_style": "manset", "instagram_visual_check": True})
+        a.cfg.images_dir.mkdir(parents=True, exist_ok=True)
+        Image.new("RGB", (1600, 900), (40, 90, 160)).save(a.cfg.images_dir / "v-g0.webp")
+        photo = {"image": {"source": "photo", "photo": "v-g0.webp"},
+                 "photos": [{"file": "v-g0.webp", "credit": "Apple", "w": 1600, "h": 900}],
+                 "carousel_points": ["Birinci madde.", "İkinci madde.", "Üçüncü madde."]}
+        posts = []
+        for i in (1, 2, 3):
+            p = {**_pub(i, 1, 9, **photo), "id": f"v{i}"}
+            a.store.save_post(p)
+            posts.append(p)
+        out = Path(t) / "_site"
+        # 1) tam ekran fotoğraf geçmez, yönetmen "kırpmadan göster" der → ikinci hâl geçer
+        a.llm = Director([{"ok": False, "score": 4, "issues": ["Kapak: başlık fotoğraftaki yazıyla çakışıyor"],
+                           "fix": "contain_photo", "reason": "Kırpma kötü"},
+                          {"ok": True, "score": 8, "issues": [], "fix": "none", "reason": "Uygun"}])
+        a.ig_enqueue(posts[0])
+        a.ig_tick()
+        assert FakeIG.calls == [] and a.state["ig_queue"][0].get("vok") is None   # onaysız paylaşılmaz
+        assert a.stage_instagram(out) == 4
+        it = a.state["ig_queue"][0]
+        assert it["vok"] and it["variant"] == "contain" and it["vtried"] == ["auto", "contain"]
+        assert a.llm.seen[0][1] == 4 and "full-bleed" in a.llm.seen[0][0] and "uncropped" in a.llm.seen[1][0]
+        assert sorted(x.name for x in (out / "ig").iterdir()) == ["v1-c2.jpg", "v1-c3.jpg", "v1-post.jpg", "v1-story.jpg"]
+        a.ig_tick()
+        assert a.state["ig_queue"] == [] and FakeIG.calls[0][0] == "carousel"
+        # 2) hikâye: fotoğraf ilgisiz → fotoğrafsız hâl de geçmez → paylaşılmaz, günlük hak geri döner
+        a.llm = Director([{"ok": False, "score": 3, "issues": ["Hikâye: fotoğraf haberle ilgisiz"], "fix": "no_photo",
+                           "reason": "Fotoğraf yanlış"},
+                          {"ok": False, "score": 5, "issues": ["Hikâye: zemin boş duruyor"], "fix": "skip", "reason": "Zayıf"}])
+        a.ig_enqueue(posts[1], fmt="story")
+        a._ig_day().append({"id": "v2", "format": "story", "at": iso(now_utc()), "title": "x"})
+        assert a.stage_instagram(out) == 0
+        assert a.state["ig_queue"] == [] and not any(x["id"] == "v2" for x in a._ig_day())
+        assert a.llm.seen[1][1] == 1 and "no photo" in a.llm.seen[1][0]
+        assert a.store.load_post("v2")["social"]["vfail"]["format"] == "story"
+        outbox = (Path(t) / "data" / "_mock" / "outbox.jsonl").read_text(encoding="utf-8")
+        assert "kontrolden geçmedi" in outbox and "zemin boş duruyor" in outbox
+        # sahibi "Yine de paylaş" derse kontrol atlanır
+        assert "atlanarak" in a._on_button("k", "v2")
+        assert a.state["ig_queue"][0]["vok"] and a.state["ig_queue"][0]["format"] == "story"
+        a._on_button("x", "v2")
+        # 3) yapay zeka yanıt vermezse kart siteye konmaz, haber sırada kalır (sonraki turda yeniden denenir)
+        a.llm = Director([])
+        a.ig_enqueue(posts[2], fmt="story")
+        assert a.stage_instagram(out) == 0
+        it = a.state["ig_queue"][0]
+        assert it["id"] == "v3" and not it.get("vok") and it["verr"] == 1 and it["vtried"] == []
+        assert "Görsel kontrolü bekleyen: 1" in a.instagram_status()
+
+
+def test_fb_me_falls_back_to_pages():
+    """Ayardaki hesap numarası okunamazsa anahtarın eriştiği sayfalardaki Instagram hesabı bulunur."""
+    cli = ig.Instagram("EAAtest", ig_id="999")
+
+    def req(method, path, **params):
+        if path == "999":
+            raise ig.InstagramError("Object does not exist", 100, 33)
+        if path == "me/accounts":
+            return {"data": [{"id": "p1"}, {"id": "p2", "instagram_business_account": {"id": "1784"}}]}
+        return {"id": path, "username": "smarityco"}
+    cli._req = req
+    assert cli.me()["id"] == "1784"
+    cli2 = ig.Instagram("EAAtest", ig_id="999")
+    cli2._req = lambda method, path, **params: (_ for _ in ()).throw(ig.InstagramError("Invalid token", 190))
+    try:
+        cli2.me()
+        raise AssertionError("hata yutulmamalı")
+    except ig.InstagramError as e:
+        assert e.code == 190
+    # sorun /instagram durumunda görünür
+    with tempfile.TemporaryDirectory() as t:
+        a = _app(Path(t))
+        a._ig_problem("erişim anahtarı çalışmıyor (Invalid token)")
+        assert "Son sorun" in a.instagram_status() and "Invalid token" in a.instagram_status()
+
+
 def test_missing_card_triggers_rebuild():
     appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 404)
@@@SM@@@ SHA
92342d460a1aef3301080bdd6b1099dc11ad6283409ee6231d73c9febe3ee59a config.yaml
ef7c66346231dbc4cf01cf9a62382f0427a0b46be208813f65ac3852cc54c5d3 haberbot/app.py
ca5e39ea066cb579e43432c1cc1824d807a420d581ef725d2355b16de3da9da5 haberbot/instagram.py
fa2ebe3460246516d44eaf53bec264b28699e6db4354cc1e7d4a9d0f3bbdd809 haberbot/llm.py
102adb46f1e3a9e441cbd793b319da91e0500759290d0b576080cf648e34e8b7 haberbot/prompts.py
d06ea6b958812476d91e97ab3d354e440b713637429f220a315fefd680b3c9ca haberbot/visuals.py
0ed76bc991d90370e0d9ba116985a20ad4ded46525e97fdbd14461526bea38e0 templates/cards/manset.html
bc9203344ba70a43c7b48dea8b6a42f24bf4cf0db45430383f10e29a62e1862a tests/test_instagram.py
