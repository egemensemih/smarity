SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -5,4 +5,5 @@ import html
 import os
 import re
+import shutil
 import time
 from urllib.parse import urlsplit
@@ -14,4 +15,5 @@ from .config import CATEGORIES, DEFAULT_CATEGORY, Config, category_label, indexn
 from .covers import COVER_VERSION
 from .extract import full_text
+from .instagram import Instagram, InstagramError, TokenStore, fingerprint, head_ok
 from .llm import LLMError, MockLLM, estimate_cost, make_llm
 from .prompts import (FLAG_LABELS, FLAGS, SEO_SCHEMA, TRIAGE_SCHEMA, WRITE_SCHEMA, seo_system, seo_user,
@@ -31,4 +33,5 @@ SLOW_ACTIONS = {
     "s": ("⏳ Görseller hazırlanıyor…", "📱 Gönderildi"),
 }
+IG_WINDOW_DEFAULT = [8, 24]
 CONF_LABEL = {"yuksek": "yüksek", "orta": "orta", "dusuk": "düşük"}
 COMMANDS = [
@@ -40,6 +43,8 @@ COMMANDS = [
     ("devam", "Yeniden başlat"),
     ("kaynaklar", "Kaynak güven puanları"),
+    ("instagram", "Instagram paylaşımları: durum / kapat / ac"),
     ("yardim", "Nasıl kullanılır"),
 ]
+COMMANDS_VERSION = 2
 HELP = """<b>Nasıl çalışır?</b>
 Kaynaklar düzenli taranır; teknoloji, girişim, yapay zeka, ürün, otomobil ve oyun dünyasından önemli haberler Türkçe yazılıp buraya düşer.
@@ -56,5 +61,7 @@ Kaynaklar düzenli taranır; teknoloji, girişim, yapay zeka, ürün, otomobil v
 <b>Öğrenen mod:</b> Kararların kaynak bazında kaydedilir. Bir kaynak yeterince onay alınca, o kaynaktan gelen net haberler otomatik yayınlanır ve sana sessizce bildirilir. Şüpheli işaretli haberler her zaman sana sorulur.
 
-Komutlar: /durum /bekleyen /mod /topla /duraklat /devam /kaynaklar"""
+📸 <b>Instagram</b> — yayınlanan her haber birkaç dakika içinde carousel ve hikâye olarak Instagram'da paylaşılır. Sıradaki bir haberi mesajındaki <b>Instagram'a gönderme</b> düğmesiyle durdurabilirsin. Tümünü durdurmak için <code>/instagram kapat</code>.
+
+Komutlar: /durum /bekleyen /mod /topla /duraklat /devam /kaynaklar /instagram"""
 
 
@@ -94,4 +101,6 @@ class App:
         self.chat_id = cfg.telegram_chat_id or ("1" if cfg.mock else "")
         self._vis = None
+        self._ig = None
+        self._cb_mid = None
 
     @property
@@ -523,4 +532,7 @@ class App:
         """Instagram için hazır carousel ve hikâyeyi Telegram'a gönder (elle paylaşım için).
         Carousel: kapak + öne çıkanlar + neden önemli. Hikâye: bağlantı çıkartmasıyla siteye yönlendirir."""
+        if not force and self.ig_enabled:
+            self.ig_enqueue(post)
+            return
         if not (self.tg and self.chat_id):
             return
@@ -582,4 +594,5 @@ class App:
             self.state["last_activity"] = iso(now_utc())
             action, _, did = (cq.get("data") or "").partition(":")
+            self._cb_mid = (cq.get("message") or {}).get("message_id")
             slow = SLOW_ACTIONS.get(action)
             if slow:  # uzun süren işlerde düğme hemen yanıt versin
@@ -625,4 +638,11 @@ class App:
     def _on_button(self, action: str, did: str) -> str:
         st = self.store
+        if action == "x":
+            return "🚫 Instagram'a gönderilmeyecek" if self._ig_drop(did, cancelled=True) else "Sırada değil (paylaşılmış olabilir)."
+        if action == "q":
+            post = st.load_post(did)
+            if not post:
+                return "Bu haber artık yayında değil."
+            return "📸 Tekrar sıraya alındı" if self.ig_enqueue(post, mid=self._cb_mid) else "Zaten sırada ya da paylaşıldı."
         where, d = st.find_any(did)
         if not d:
@@ -664,4 +684,5 @@ class App:
                 return "Bu haber yayında değil."
             st.delete_post(did)
+            self._ig_drop(did, "🗑 Haber siteden kaldırıldığı için Instagram'a gönderilmeyecek")
             weight = 2 if d.get("publish_mode") == "auto" else 1
             policy.record(self.stats, d, ok=False, weight=weight)
@@ -816,4 +837,13 @@ class App:
         elif cmd == "kaynaklar":
             self.notify(self.sources_text(), silent=True)
+        elif cmd == "instagram":
+            if arg in ("kapat", "durdur"):
+                self.state["ig_off"] = True
+                self.notify("⏸ Instagram paylaşımları durdu. Sıradakiler bekliyor. Açmak için <code>/instagram ac</code>", silent=True)
+            elif arg in ("ac", "aç", "baslat", "başlat"):
+                self.state["ig_off"] = False
+                self.notify("▶️ Instagram paylaşımları açık.", silent=True)
+            else:
+                self.notify(self.instagram_status(), silent=True)
         else:
             self.notify("Bilinmeyen komut. /yardim", silent=True)
@@ -841,4 +871,8 @@ class App:
             f"Site: {esc(self.cfg.site_url)}",
         ]
+        if self.cfg.instagram_token:
+            q = len(self.state.get("ig_queue") or [])
+            lines.append(f"Instagram: {c.get('instagram', 0)} paylaşım · sırada {q}"
+                         f"{' · ⏸ kapalı' if self.state.get('ig_off') else ''}")
         if bad:
             lines.append("⚠️ Okunamayan kaynaklar: " + esc(", ".join(bad)))
@@ -954,4 +988,5 @@ class App:
                 f"Yayın: {c.get('published', 0)} ({c.get('auto', 0)} otomatik, {c.get('approved', 0)} senin onayınla)\n"
                 f"Ret: {c.get('rejected', 0)} · Süresi dolan: {c.get('expired', 0)} · Kaldırılan: {c.get('removed', 0)}\n"
+                f"Instagram: {c.get('instagram', 0)} paylaşım\n"
                 f"Tahmini maliyet: ${self._cost(c):.2f} ({c.get('images', 0)} yapay zeka görseli)\n"
                 f"Mod: {policy.MODES[policy.current_mode(self.cfg, self.state)]}")
@@ -979,11 +1014,255 @@ class App:
         return bool(self.store.drafts("pending")) and not self.quiet()
 
+    # ── 5) INSTAGRAM ────────────────────────────────────────
+    def _ig_cfg(self, key: str, default):
+        return self.cfg.get("social", key, default)
+
+    @property
+    def ig_enabled(self) -> bool:
+        return self.cfg.instagram_auto and not self.state.get("ig_off")
+
+    def _ig_kinds(self) -> list[str]:
+        return list(self.vis.CAROUSEL) if self.vis.summary_style else ["post"]
+
+    def _ig_urls(self, post: dict) -> dict:
+        base = f"{self.cfg.site_url}/ig/{post['id']}"
+        return {k: f"{base}-{k}.jpg" for k in self._ig_kinds() + ["story"]}
+
+    def _ig_msg(self, it: dict, text: str, keyboard=None) -> None:
+        if not (self.tg and self.chat_id):
+            return
+        if it.get("mid"):
+            self.tg.edit_text(self.chat_id, it["mid"], text, keyboard)
+        else:
+            try:
+                it["mid"] = self.tg.send_message(self.chat_id, text, keyboard, silent=True).get("message_id")
+            except TelegramError as e:
+                log.warning("Instagram bildirimi gönderilemedi: %s", e)
+
+    def ig_enqueue(self, post: dict, mid: int | None = None) -> bool:
+        """Yayınlanan haberi Instagram sırasına ekler (kartlar site yayınlanırken _site/ig/ altına konur)."""
+        q = self.state.setdefault("ig_queue", [])
+        done = {x.get("id") for x in self.state.get("ig_done") or []}
+        if post["id"] in done or any(x["id"] == post["id"] for x in q):
+            return False
+        it = {"id": post["id"], "queued_at": iso(now_utc()), "tries": 0}
+        if mid:
+            it["mid"] = mid
+        q.append(it)
+        self.store.site_dirty = True
+        where = "" if not self.state.get("ig_off") else " (Instagram şu an kapalı: /instagram ac)"
+        self._ig_msg(it, f"📸 <b>Instagram sırasında</b>{where}\n{esc(post['title'])}\n"
+                         f"<i>Carousel ve hikâye birkaç dakika içinde paylaşılacak.</i>",
+                     [[{"text": "🚫 Instagram'a gönderme", "callback_data": f"x:{post['id']}"}]])
+        return True
+
+    def _ig_drop(self, did: str, note: str = "", cancelled: bool = False) -> bool:
+        q = self.state.get("ig_queue") or []
+        it = next((x for x in q if x["id"] == did), None)
+        if not it:
+            return False
+        q.remove(it)
+        if cancelled:
+            post = self.store.load_post(did) or {}
+            self._ig_msg(it, f"🚫 <b>Instagram'a gönderilmeyecek</b>\n{esc(post.get('title', ''))}",
+                         [[{"text": "↩️ Yine de paylaş", "callback_data": f"q:{did}"}]])
+        elif note:
+            self._ig_msg(it, note)
+        return True
+
+    def _ig_problem(self, text: str) -> None:
+        """Aynı uyarıyı en fazla 12 saatte bir gönder."""
+        if hours_since(self.state.get("ig_warned_at")) >= 12:
+            self.state["ig_warned_at"] = iso(now_utc())
+            self.notify("⚠️ <b>Instagram</b>: " + text)
+        log.warning("Instagram: %s", re.sub(r"<[^>]+>", "", text))
+
+    def _ig_client(self):
+        """Anahtarı (gerekirse yenileyip) hazırlar, hesabı tanır. Sorun varsa None."""
+        if self._ig is not None:
+            return self._ig or None
+        self._ig = False
+        secret = self.cfg.instagram_token
+        data = self.store.ig
+        ts = TokenStore(secret, data)
+        if ts.refresh_due():
+            try:
+                tok, exp = Instagram(ts.token).refresh()
+                ts.save(tok, exp)
+                data.pop("refresh_tried_at", None)
+                log.info("Instagram anahtarı yenilendi (%d gün)", exp // 86400)
+            except InstagramError as e:
+                data["refresh_tried_at"] = iso(now_utc())
+                log.info("Instagram anahtarı şimdilik yenilenemedi: %s", e)
+        left = ts.days_left()
+        if left is not None and left < 5:
+            self._ig_problem(f"erişim anahtarının süresi {max(0, left):.0f} gün içinde doluyor ve yenilenemedi. "
+                             "Meta geliştirici panelinden yeni anahtar üretip GitHub'da <b>IG_ACCESS_TOKEN</b> değerini güncelle.")
+        cli = Instagram(ts.token, self._ig_cfg("instagram_api_version", None) or "v25.0")
+        fp = fingerprint(secret)
+        if data.get("me_fp") != fp or not data.get("id"):
+            try:
+                me = cli.me()
+            except InstagramError as e:
+                if e.auth:
+                    self._ig_problem(f"erişim anahtarı çalışmıyor ({esc(e)}). Yeni anahtar üretip GitHub'da "
+                                     "<b>IG_ACCESS_TOKEN</b> değerini güncelle.")
+                else:
+                    log.warning("Instagram hesabı okunamadı: %s", e)
+                return None
+            data.update({"me_fp": fp, "id": str(me.get("id") or ""), "user_id": str(me.get("user_id") or ""),
+                         "username": me.get("username", "")})
+            data.pop("target", None)
+            if self.tg and self.chat_id:
+                self.notify(f"📸 Instagram bağlandı: <b>@{esc(data['username'])}</b>. Yayınlanan haberler buraya "
+                            f"carousel ve hikâye olarak paylaşılacak.", silent=True)
+        self._ig = cli
+        return cli
+
+    def _ig_targets(self) -> list[str]:
+        d = self.store.ig
+        if d.get("target"):
+            return [d["target"]]
+        return [t for t in dict.fromkeys(["me", d.get("user_id"), d.get("id")]) if t]
+
+    def _ig_run(self, fn, *a):
+        """Paylaşım hedefini (me / hesap numarası) dener, çalışanı hatırlar."""
+        last = None
+        for t in self._ig_targets():
+            try:
+                res = fn(t, *a)
+                self.store.ig["target"] = t
+                return res
+            except InstagramError as e:
+                last = e
+                if e.auth or e.transient or e.code not in (100, 3, 803):
+                    raise
+        raise last  # type: ignore[misc]
+
+    def ig_tick(self) -> None:
+        """Sıradaki haberi (kartları sitede yayındaysa) Instagram'da paylaşır. Her turda en fazla bir haber."""
+        if not self.cfg.instagram_auto or self.state.get("paused"):
+            return
+        q = self.state.setdefault("ig_queue", [])
+        max_wait = float(self._ig_cfg("instagram_max_wait_hours", 12) or 12)
+        for it in list(q):
+            post = self.store.load_post(it["id"])
+            if not post:
+                q.remove(it)
+            elif hours_since(it["queued_at"]) > max_wait:
+                self._ig_drop(it["id"], f"⌛ <b>Instagram'a gönderilmedi</b> ({max_wait:.0f} saatten uzun sırada kaldı)\n"
+                                        f"{esc(post['title'])}")
+        if not q or self.state.get("ig_off"):
+            return
+        now_l = local(now_utc(), self.cfg.tz)
+        a, b = (self._ig_cfg("instagram_hours", IG_WINDOW_DEFAULT) or [0, 24])[:2]
+        if not (a <= now_l.hour + now_l.minute / 60 < b):
+            return
+        gap = float(self._ig_cfg("instagram_min_gap_minutes", 15) or 0)
+        if hours_since(self.state.get("ig_last_at")) * 60 < gap:
+            return
+        cap = int(self._ig_cfg("instagram_max_per_day", 0) or 0)
+        if cap and self.store.count(self.today(), "instagram") >= cap:
+            return
+        it = q[0]
+        post = self.store.load_post(it["id"])
+        urls = self._ig_urls(post)
+        code = head_ok(urls["post"])
+        if code != 200:
+            waited = hours_since(it["queued_at"]) * 60
+            if waited > 15 and hours_since(it.get("restaged_at")) * 60 > 30:
+                it["restaged_at"] = iso(now_utc())
+                self.store.site_dirty = True  # site yeniden yayınlansın, kartlar eklensin
+                log.info("Instagram kartı sitede yok (HTTP %s); site yeniden yayınlanacak", code)
+            return
+        cli = self._ig_client()
+        if not cli:
+            return
+        try:
+            if not it.get("media_id"):
+                caption = clip(self.instagram_caption(post), 2150)
+                mid, link = self._ig_run(cli.carousel, [urls[k] for k in self._ig_kinds()], caption)
+                it.update({"media_id": mid, "permalink": link})
+                self.state["ig_last_at"] = iso(now_utc())
+                self.store.bump(self.today(), "instagram")
+        except InstagramError as e:
+            if e.auth:
+                self._ig_problem(f"paylaşım yapılamadı: {esc(e)}. Anahtarın <b>instagram_business_content_publish</b> "
+                                 "izni olduğundan emin ol.")
+                return
+            it["tries"] = it.get("tries", 0) + (0 if e.transient else 1)
+            it["last_error"] = str(e)[:300]
+            log.warning("Instagram paylaşımı başarısız (%s): %s", post["id"], e)
+            if it["tries"] >= 3:
+                self._ig_drop(it["id"], f"⚠️ <b>Instagram'da paylaşılamadı</b>\n{esc(post['title'])}\n<i>{esc(e)}</i>")
+            return
+        if self._ig_cfg("instagram_story", True) and not it.get("story_id"):
+            try:
+                it["story_id"] = self._ig_run(cli.story, urls["story"])
+            except InstagramError as e:  # hikâye olmasa da gönderi paylaşıldı; sırayı tıkama
+                log.warning("Instagram hikâyesi paylaşılamadı (%s): %s", post["id"], e)
+                it["story_error"] = str(e)[:200]
+        q.remove(it)
+        done = self.state.setdefault("ig_done", [])
+        done.append({"id": post["id"], "at": iso(now_utc()), "permalink": it.get("permalink", ""),
+                     "story": bool(it.get("story_id"))})
+        self.state["ig_done"] = done[-200:]
+        story = " + hikâye" if it.get("story_id") else (", hikâye paylaşılamadı" if it.get("story_error") else "")
+        kb = [[{"text": "📸 Instagram'da aç", "url": it["permalink"]}]] if it.get("permalink") else None
+        self._ig_msg(it, f"✅ <b>Instagram'da paylaşıldı</b> (carousel{story})\n{esc(post['title'])}", kb)
+        log.info("Instagram'da paylaşıldı: %s %s", post["id"], it.get("permalink", ""))
+
+    def stage_instagram(self, out) -> int:
+        """Sıradaki haberlerin Instagram kartlarını sitenin ig/ klasörüne koyar (Instagram herkese açık adresten alır)."""
+        q = self.state.get("ig_queue") or []
+        if not (q and self.cfg.instagram_auto):
+            return 0
+        folder = out / "ig"
+        folder.mkdir(parents=True, exist_ok=True)
+        n = 0
+        for it in q[:8]:
+            post = self.store.load_post(it["id"])
+            if not post:
+                continue
+            for k in self._ig_kinds() + ["story"]:
+                try:
+                    shutil.copyfile(self._card(post, k), folder / f"{post['id']}-{k}.jpg")
+                    n += 1
+                except Exception as e:  # noqa: BLE001
+                    log.warning("Instagram kartı hazırlanamadı (%s %s): %s", post["id"], k, e)
+        if self._vis:
+            self._vis.close()
+            self._vis = None
+        log.info("Instagram kartları siteye kondu: %d görsel", n)
+        return n
+
+    def instagram_status(self) -> str:
+        if not self.cfg.instagram_token:
+            return ("📸 <b>Instagram</b> henüz bağlı değil.\nGitHub'da <b>IG_ACCESS_TOKEN</b> gizli anahtarı eklenince "
+                    "yayınlanan her haber otomatik paylaşılır.")
+        d = self.store.ig
+        c = self.state.get("day_counts", {}).get(self.today(), {})
+        left = TokenStore(self.cfg.instagram_token, d).days_left()
+        lines = [f"📸 <b>Instagram</b> {'⏸ kapalı' if self.state.get('ig_off') else '▶️ açık'}"
+                 f"{' · @' + esc(d['username']) if d.get('username') else ''}",
+                 f"Bugün: {c.get('instagram', 0)} paylaşım · Sırada: {len(self.state.get('ig_queue') or [])}"]
+        a, b = (self._ig_cfg("instagram_hours", IG_WINDOW_DEFAULT) or [0, 24])[:2]
+        lines.append(f"Paylaşım saatleri: {a:02d}:00–{b:02d}:00 · en az {self._ig_cfg('instagram_min_gap_minutes', 15)} dk arayla")
+        if left is not None:
+            lines.append(f"Anahtar: {left:.0f} gün geçerli (bot kendisi yeniler)")
+        for x in (self.state.get("ig_done") or [])[-3:][::-1]:
+            p = self.store.load_post(x["id"]) or {}
+            if x.get("permalink"):
+                lines.append(f'• <a href="{esc(x["permalink"])}">{esc(clip(p.get("title", x["id"]), 70))}</a>')
+        lines.append("Durdur: <code>/instagram kapat</code> · Aç: <code>/instagram ac</code>")
+        return "\n".join(lines)
+
     # ── tek çalışma ─────────────────────────────────────────
     def run(self) -> bool:
         """Bir tur: Telegram → süre dolanlar → toplama → özet → dinleme. Site değiştiyse True döner."""
-        if self.tg and self.state.get("commands_version") != 1:
+        if self.tg and self.state.get("commands_version") != COMMANDS_VERSION:
             self.tg.delete_webhook()
             self.tg.set_commands(COMMANDS)
-            self.state["commands_version"] = 1
+            self.state["commands_version"] = COMMANDS_VERSION
         if not self.tg:
             log.warning("TELEGRAM_BOT_TOKEN tanımlı değil; onay mekanizması kapalı.")
@@ -1005,4 +1284,8 @@ class App:
         if not self.state.get("paused"):
             self.backfill_seo()
+        try:
+            self.ig_tick()
+        except Exception as e:  # noqa: BLE001
+            log.exception("Instagram hatası: %s", e)
         self.refresh_covers()
         self.maybe_summary()
--- a/haberbot/config.py
+++ b/haberbot/config.py
@@ -64,4 +64,5 @@ class Config:
     telegram_chat_id: str = ""
     google_key: str = ""
+    instagram_token: str = ""
     mock: bool = False
     fixtures_dir: Path | None = None
@@ -107,4 +108,9 @@ class Config:
         return self.root / "_site"
 
+    @property
+    def instagram_auto(self) -> bool:
+        """IG_ACCESS_TOKEN tanımlı ve ayarlarda kapatılmamışsa haberler Instagram'a kendiliğinden gider."""
+        return bool(self.instagram_token) and bool(self.get("social", "instagram_auto", True))
+
     def post_url(self, slug: str) -> str:
         return f"{self.site_url}/haber/{slug}/"
@@ -143,4 +149,5 @@ def load_config(path: Path | None = None) -> Config:
         telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
         google_key=(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip(),
+        instagram_token=os.environ.get("IG_ACCESS_TOKEN", "").strip(),
         mock=os.environ.get("HABERBOT_MOCK", "") == "1",
         fixtures_dir=Path(fixtures) if fixtures else None,
--- a/haberbot/store.py
+++ b/haberbot/store.py
@@ -58,4 +58,6 @@ class Store:
         self.seen: dict = read_json(cfg.data_dir / "seen.json", {})
         self.stats: dict = {**DEFAULT_STATS, **read_json(cfg.data_dir / "stats.json", {})}
+        self.ig: dict = read_json(cfg.data_dir / "instagram.json", {})
+        self._ig_orig = dict(self.ig)
         self.site_dirty = False
 
@@ -71,4 +73,7 @@ class Store:
         write_json(self.cfg.data_dir / "seen.json", self.seen, compact=True)
         write_json(self.cfg.data_dir / "stats.json", self.stats)
+        if self.ig != self._ig_orig:
+            write_json(self.cfg.data_dir / "instagram.json", self.ig)
+            self._ig_orig = dict(self.ig)
 
     # ── sayaçlar ─────────────────────────────────────────────
--- a/haberbot/telegram.py
+++ b/haberbot/telegram.py
@@ -102,4 +102,15 @@ class Telegram:
                 log.warning("Telegram mesajı güncellenemedi: %s", e)
 
+    def edit_text(self, chat_id, message_id: int, text: str, keyboard=None) -> None:
+        try:
+            self._call("editMessageText", {
+                "chat_id": chat_id, "message_id": message_id, "text": text[:4096], "parse_mode": "HTML",
+                "reply_markup": {"inline_keyboard": keyboard or []},
+                "link_preview_options": {"is_disabled": True},
+            })
+        except TelegramError as e:
+            if "not modified" not in str(e):
+                log.warning("Telegram mesajı güncellenemedi: %s", e)
+
     def set_commands(self, commands: list[tuple[str, str]]) -> None:
         try:
--- a/haberbot/covers.py
+++ b/haberbot/covers.py
@@ -287,5 +287,5 @@ def carousel_points(d: dict) -> list[str]:
 def news_card(d: dict, W: int, H: int, *, brand_name: str = "Smarity", tagline: str = "", label: str = "",
               date: str = "", credits: str = "", mode: str = "cover", page: int = 0, pages: int = 0,
-              site_host: str = "") -> dict:
+              site_host: str = "", story_link: bool = True) -> dict:
     """Özet kartı şablonu için bağlam: habere özel renkler, oluklu cam şeritleri ve vurgulu başlık."""
     seed = _seed(d)
@@ -313,5 +313,5 @@ def news_card(d: dict, W: int, H: int, *, brand_name: str = "Smarity", tagline:
         "headline": _mark(title, d), "summary": (d.get("summary") or "").strip(), "title": title,
         "points": carousel_points(d) if mode == "points" else [], "why": why_text(d) if mode == "why" else "",
-        "mode": mode, "page": page, "pages": pages, "site_host": site_host, "label_plain": label,
+        "mode": mode, "page": page, "pages": pages, "site_host": site_host, "label_plain": label, "story_link": story_link,
         "label": tr_upper(label), "date": date, "credits": credits, "tagline": tagline, "brand_name": brand_name,
     }
--- a/haberbot/visuals.py
+++ b/haberbot/visuals.py
@@ -310,5 +310,6 @@ class Visuals:
                     page=self.CAROUSEL.index(kind) + 1 if kind in self.CAROUSEL else 0,
                     pages=len(self.CAROUSEL) if kind in self.CAROUSEL else 0,
-                    site_host=self.cfg.site_url.split("://", 1)[-1] if "localhost" not in self.cfg.site_url else "")
+                    site_host=self.cfg.site_url.split("://", 1)[-1] if "localhost" not in self.cfg.site_url else "",
+                    story_link=not self.cfg.instagram_auto)
                 return self.renderer.html_to_image("news.html", ctx, size, out)
             except Exception as e:  # noqa: BLE001
--- a/haberbot/__main__.py
+++ b/haberbot/__main__.py
@@ -40,4 +40,8 @@ def main(argv: list[str]) -> int:
         if changed or cfg.force_build or stale or (not in_ci and not (cfg.out_dir / "index.html").exists()):
             SiteBuilder(cfg).build()
+            try:
+                app.stage_instagram(cfg.out_dir)
+            except Exception as e:  # noqa: BLE001
+                log.warning("Instagram kartları siteye konamadı: %s", e)
             app.state["last_build"] = iso(now_utc())
             app.state["build_sig"] = sig
@@ -74,4 +78,13 @@ def check(cfg) -> int:
     print(f"TELEGRAM_BOT_TOKEN: {'VAR' if cfg.telegram_token else 'YOK ✗'}")
     print(f"TELEGRAM_CHAT_ID  : {cfg.telegram_chat_id or 'YOK (bota /start yaz)'}")
+    print(f"IG_ACCESS_TOKEN   : {'VAR' if cfg.instagram_token else 'YOK (Instagram otomatik paylaşım kapalı)'}")
+    if cfg.instagram_token:
+        from .instagram import Instagram, InstagramError
+        try:
+            me = Instagram(cfg.instagram_token).me()
+            print(f"Instagram         : @{me.get('username')} ✓")
+        except InstagramError as e:
+            print(f"Instagram         : HATA ✗ {e}")
+            ok = False
     ok &= bool((cfg.google_key or cfg.anthropic_key) and cfg.telegram_token and cfg.telegram_chat_id)
     if cfg.telegram_token and cfg.telegram_chat_id:
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -245,4 +245,6 @@ class SiteBuilder:
             "url": cfg.site_url,
             "year": now_l.year,
+            # Instagram hesabı: ayarda yazılı değilse bağlanan hesaptan (data/instagram.json) alınır
+            "instagram": cfg.site.get("instagram") or (store.ig.get("username") if cfg.instagram_token else ""),
             "categories": cats,
             "nav_categories": [c for c in cats if c["count"] > 0] or cats[:6],
--- a/templates/cards/news.html
+++ b/templates/cards/news.html
@@ -3,5 +3,6 @@
          points (carousel 2: öne çıkan 3 madde)
          why    (carousel 3: neden önemli + haberin tamamı için yönlendirme)
-         story  (hikâye: başlık, özet ve bağlantı çıkartması için boş alan)
+         story  (hikâye: başlık, özet; elle paylaşımda bağlantı çıkartması için boş alan,
+                 otomatik paylaşımda "profildeki bağlantıda" yönlendirmesi)
    Değişkenler: pal, base, glow, reeds, headline (güvenli HTML), title, summary, points, why, label, date,
    credits, tagline, page, pages, site_host, W, H #}
@@ -81,4 +82,6 @@ h1 mark { background: var(--ink); color: #fff; padding: 0 .14em; margin: 0 -.04e
 .tap .go { width: calc(var(--u) * 8.4); height: calc(var(--u) * 8.4); }
 .sticker-room { height: calc(var(--u) * 17); }
+.tap.bio > span:last-child { display: grid; gap: calc(var(--u) * .6); }
+.tap.bio small { font-size: calc(var(--u) * 3); font-weight: 400; color: var(--ink2); letter-spacing: -.005em; }
 </style></head>
 <body>
@@ -114,7 +117,9 @@ h1 mark { background: var(--ink); color: #fff; padding: 0 .14em; margin: 0 -.04e
   </div>
   <div class="spacer lower"></div>
-  {% if mode == 'story' %}
+  {% if mode == 'story' and story_link %}
   <div class="tap"><span class="go" aria-hidden="true">{{ down|safe }}</span>Haberin tamamı için bağlantıya dokun</div>
   <div class="sticker-room"></div>
+  {% elif mode == 'story' %}
+  <div class="tap bio"><span class="go" aria-hidden="true">{{ arrow|safe }}</span><span>Haberin tamamı profildeki bağlantıda{% if site_host %}<small>{{ site_host }}</small>{% endif %}</span></div>
   {% endif %}
   <div class="bottom">
--- a/config.yaml
+++ b/config.yaml
@@ -14,5 +14,5 @@ site:
   posts_per_page: 18
   contact_email: ""        # Hakkında sayfasında görünür (boş bırakılabilir)
-  instagram: ""            # Örn: "smarity" (2. aşamada kullanılacak)
+  instagram: ""            # Instagram kullanıcı adı (boşsa bağlanan hesap kullanılır; site altında bağlantı çıkar)
 
 seo:
@@ -68,6 +68,14 @@ images:
 
 social:
-  # Yayınlanan her haber için Instagram post + story görsellerini Telegram'a gönder
-  # (Instagram otomasyonu 2. aşamada; o zamana kadar elle paylaşabilirsin).
+  # ── Instagram'a otomatik paylaşım ──
+  # GitHub'da IG_ACCESS_TOKEN gizli anahtarı tanımlıysa yayınlanan her haber, site güncellendikten
+  # birkaç dakika sonra carousel (3 görsel) ve hikâye olarak paylaşılır. Telegram'dan /instagram ile yönetilir.
+  instagram_auto: true
+  instagram_story: true            # carousel'e ek olarak hikâye de paylaşılsın
+  instagram_hours: [8, 24]         # paylaşım saatleri; gece yayınlanan haberler sabah 8'de sırayla paylaşılır
+  instagram_min_gap_minutes: 15    # iki paylaşım arasında en az bu kadar dakika olsun (akış boğulmasın)
+  instagram_max_per_day: 0         # günlük üst sınır (0 = sınır yok; Instagram'ın kendi sınırı 100)
+  instagram_max_wait_hours: 12     # bundan uzun sırada bekleyen haber artık paylaşılmaz (bayatlamasın)
+  # IG_ACCESS_TOKEN yokken: Instagram post + story görsellerini elle paylaşman için Telegram'a gönder
   send_to_telegram: true
   # Instagram görsel tarzı:
@@@SM@@@ FILE haberbot/instagram.py
"""Instagram otomatik paylaşım (Instagram API with Instagram Login).

Akış: haber yayınlanınca sıraya girer → site yayınlanırken kartlar _site/ig/ altına konur →
bir sonraki turda Instagram bu herkese açık JPEG'leri alır ve carousel + hikâye paylaşılır.

Erişim anahtarı (IG_ACCESS_TOKEN) GitHub'da gizli anahtar olarak durur. 60 günlük anahtar bot tarafından
düzenli yenilenir; yenilenen anahtar yalnızca asıl gizli anahtarla açılabilecek şekilde şifrelenip
data/instagram.json dosyasına yazılır (depoda düz metin anahtar yoktur).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from datetime import timedelta

import requests

from .util import iso, log, now_utc, parse_iso

API = "https://graph.instagram.com"
VERSION = "v25.0"


class InstagramError(Exception):
    def __init__(self, msg: str, code: int | None = None, subcode: int | None = None, transient: bool = False):
        super().__init__(msg)
        self.code, self.subcode, self.transient = code, subcode, transient

    @property
    def auth(self) -> bool:
        """Anahtar geçersiz / süresi dolmuş / izin yok."""
        return self.code in (190, 10, 200, 2500) or (self.code == 100 and self.subcode == 33)


# ── anahtarı şifreli saklama (yalnızca standart kütüphane: HMAC-SHA256 CTR + etiket) ──
def _keys(secret: str) -> tuple[bytes, bytes]:
    s = secret.encode()
    return (hmac.new(s, b"smarity-ig-enc-v1", hashlib.sha256).digest(),
            hmac.new(s, b"smarity-ig-mac-v1", hashlib.sha256).digest())


def _stream(key: bytes, nonce: bytes, n: int) -> bytes:
    out, i = bytearray(), 0
    while len(out) < n:
        out += hmac.new(key, nonce + i.to_bytes(8, "big"), hashlib.sha256).digest()
        i += 1
    return bytes(out[:n])


def seal(secret: str, text: str) -> str:
    ek, mk = _keys(secret)
    nonce = os.urandom(16)
    data = text.encode()
    ct = bytes(a ^ b for a, b in zip(data, _stream(ek, nonce, len(data))))
    tag = hmac.new(mk, nonce + ct, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(nonce + ct + tag).decode()


def unseal(secret: str, blob: str) -> str | None:
    try:
        raw = base64.urlsafe_b64decode(blob.encode())
    except (ValueError, TypeError):
        return None
    if len(raw) < 48:
        return None
    ek, mk = _keys(secret)
    nonce, ct, tag = raw[:16], raw[16:-32], raw[-32:]
    if not hmac.compare_digest(tag, hmac.new(mk, nonce + ct, hashlib.sha256).digest()):
        return None
    return bytes(a ^ b for a, b in zip(ct, _stream(ek, nonce, len(ct)))).decode()


def fingerprint(secret: str) -> str:
    return hashlib.sha256(("smarity-ig-fp:" + secret).encode()).hexdigest()[:12]


# ── API istemcisi ──
class Instagram:
    def __init__(self, token: str, version: str = VERSION, timeout: int = 60):
        self.token = token
        self.base = f"{API}/{version}"
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {token}"

    def _clean(self, text: str) -> str:
        return str(text).replace(self.token, "***") if self.token else str(text)

    def _req(self, method: str, path: str, **params) -> dict:
        url = path if path.startswith("http") else f"{self.base}/{path.lstrip('/')}"
        try:
            if method == "GET":
                r = self.s.get(url, params=params, timeout=self.timeout)
            else:
                r = self.s.post(url, data=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise InstagramError(self._clean(f"Bağlantı hatası: {type(e).__name__}"), transient=True) from None
        try:
            j = r.json()
        except ValueError:
            j = {}
        if r.status_code >= 400 or "error" in j:
            err = j.get("error") or {}
            msg = err.get("error_user_msg") or err.get("message") or f"HTTP {r.status_code}"
            raise InstagramError(self._clean(msg), err.get("code"), err.get("error_subcode"),
                                 transient=r.status_code >= 500 or bool(err.get("is_transient")) or err.get("code") in (1, 2, 4, 9007))
        return j

    def me(self) -> dict:
        return self._req("GET", "me", fields="user_id,username")

    def container(self, ig_id: str, **params) -> str:
        return self._req("POST", f"{ig_id}/media", **params)["id"]

    def wait(self, cid: str, tries: int = 30, delay: float = 3) -> None:
        for _ in range(tries):
            st = self._req("GET", cid, fields="status_code,status").get("status_code")
            if st in ("FINISHED", "PUBLISHED"):
                return
            if st in ("ERROR", "EXPIRED"):
                raise InstagramError(f"Instagram görseli işleyemedi ({st})")
            time.sleep(delay)
        raise InstagramError("Instagram görseli zamanında işlemedi", transient=True)

    def publish(self, ig_id: str, cid: str) -> str:
        last = None
        for i in range(4):
            try:
                return self._req("POST", f"{ig_id}/media_publish", creation_id=cid)["id"]
            except InstagramError as e:  # kapsayıcı henüz hazır değilse kısa bekle
                last = e
                if not e.transient and e.code != 9007:
                    raise
                time.sleep(4 * (i + 1))
        raise last  # type: ignore[misc]

    def permalink(self, mid: str) -> str:
        try:
            return self._req("GET", mid, fields="permalink").get("permalink", "")
        except InstagramError:
            return ""

    def carousel(self, ig_id: str, urls: list[str], caption: str) -> tuple[str, str]:
        if len(urls) == 1:
            cid = self.container(ig_id, image_url=urls[0], caption=caption)
        else:
            kids = [self.container(ig_id, image_url=u, is_carousel_item="true") for u in urls]
            for k in kids:
                self.wait(k)
            cid = self.container(ig_id, media_type="CAROUSEL", children=",".join(kids), caption=caption)
        self.wait(cid)
        mid = self.publish(ig_id, cid)
        return mid, self.permalink(mid)

    def story(self, ig_id: str, url: str) -> str:
        cid = self.container(ig_id, media_type="STORIES", image_url=url)
        self.wait(cid)
        return self.publish(ig_id, cid)

    def refresh(self) -> tuple[str, int]:
        """Uzun ömürlü anahtarı 60 gün uzatır (anahtar en az 24 saatlik olmalı)."""
        s = requests.Session()
        try:
            r = s.get(f"{API}/refresh_access_token", params={"grant_type": "ig_refresh_token",
                                                             "access_token": self.token}, timeout=self.timeout)
            j = r.json()
        except (requests.RequestException, ValueError) as e:
            raise InstagramError(self._clean(f"Yenileme bağlantı hatası: {type(e).__name__}"), transient=True) from None
        if "access_token" not in j:
            err = j.get("error") or {}
            raise InstagramError(self._clean(err.get("message") or f"HTTP {r.status_code}"), err.get("code"),
                                 err.get("error_subcode"))
        return j["access_token"], int(j.get("expires_in") or 0)


class TokenStore:
    """Gizli anahtar + (varsa) yenilenmiş anahtarın şifreli kopyası."""

    def __init__(self, secret: str, data: dict):
        self.secret = secret
        self.data = data  # data/instagram.json içeriği (yerinde güncellenir)

    @property
    def token(self) -> str:
        if self.data.get("fp") == fingerprint(self.secret) and self.data.get("token"):
            t = unseal(self.secret, self.data["token"])
            if t:
                return t
        return self.secret

    def save(self, token: str, expires_in: int) -> None:
        fp = fingerprint(self.secret)
        if self.data.get("fp") != fp:  # gizli anahtar değişmiş: eski kayıtları unut
            for k in ("user_id", "username", "expires_at"):
                self.data.pop(k, None)
        self.data.update({"fp": fp, "token": seal(self.secret, token), "refreshed_at": iso(now_utc())})
        if expires_in:
            self.data["expires_at"] = iso(now_utc() + timedelta(seconds=expires_in))

    def days_left(self) -> float | None:
        exp = parse_iso(self.data.get("expires_at")) if self.data.get("fp") == fingerprint(self.secret) else None
        if not exp:
            return None
        return (exp - now_utc()).total_seconds() / 86400

    def refresh_due(self) -> bool:
        fresh = self.data.get("fp") == fingerprint(self.secret)
        last = parse_iso(self.data.get("refreshed_at")) if fresh else None
        tried = parse_iso(self.data.get("refresh_tried_at"))
        if tried and (now_utc() - tried) < timedelta(hours=12):
            return False
        return not last or (now_utc() - last) > timedelta(days=7)


def head_ok(url: str) -> int:
    """Görsel herkese açık mı? HTTP durum kodu (bağlantı hatasında 0)."""
    try:
        r = requests.head(url, timeout=20, allow_redirects=True)
        if r.status_code == 200 and "image" not in r.headers.get("content-type", "image"):
            return 415
        return r.status_code
    except requests.RequestException:
        return 0


def log_error(prefix: str, e: Exception) -> None:
    log.warning("%s: %s", prefix, e)
@@@SM@@@ FILE tests/test_instagram.py
"""Instagram otomatik paylaşım testleri (ağ yok: Instagram istemcisi sahte)."""
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haberbot import app as appmod  # noqa: E402
from haberbot import instagram as ig  # noqa: E402
from haberbot.config import ROOT, Config  # noqa: E402
from haberbot.util import iso, now_utc  # noqa: E402


def test_seal_roundtrip_and_tamper():
    blob = ig.seal("secret-A", "IGAAT-refreshed-token")
    assert ig.unseal("secret-A", blob) == "IGAAT-refreshed-token"
    assert ig.unseal("secret-B", blob) is None           # başka anahtarla açılmaz
    raw = bytearray(ig.base64.urlsafe_b64decode(blob))
    raw[20] ^= 1
    assert ig.unseal("secret-A", ig.base64.urlsafe_b64encode(bytes(raw)).decode()) is None  # değişiklik fark edilir
    assert "IGAAT" not in blob


def test_token_store():
    data = {}
    ts = ig.TokenStore("secret-A", data)
    assert ts.token == "secret-A" and ts.refresh_due()
    ts.save("new-token", 60 * 86400)
    assert ig.TokenStore("secret-A", data).token == "new-token"
    assert 59 < ts.days_left() <= 60 and not ts.refresh_due()
    # kullanıcı gizli anahtarı değiştirdi → yeni anahtar kullanılır
    assert ig.TokenStore("secret-B", data).token == "secret-B"
    assert ig.TokenStore("secret-B", data).days_left() is None


def test_error_classification():
    assert ig.InstagramError("x", 190).auth
    assert not ig.InstagramError("x", 100).auth
    assert ig.InstagramError("x", 100, 33).auth


class FakeIG:
    calls = []

    def __init__(self, token, version="v25.0", timeout=60):
        self.token = token

    def me(self):
        return {"id": "178", "user_id": "178", "username": "smarity"}

    def refresh(self):
        raise ig.InstagramError("too new", 190)

    def carousel(self, target, urls, caption):
        FakeIG.calls.append(("carousel", target, tuple(urls), caption))
        if target == "me":
            raise ig.InstagramError("Unsupported post request", 100)
        return "M1", "https://www.instagram.com/p/abc/"

    def story(self, target, url):
        FakeIG.calls.append(("story", target, url))
        return "S1"


def _app(tmp: Path):
    raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    raw["social"]["instagram_hours"] = [0, 24]
    cfg = Config(raw=raw, root=tmp, site_url="https://example.github.io/smarity", mock=True,
                 instagram_token="SECRET-TOKEN", telegram_chat_id="1")
    return appmod.App(cfg)


def test_queue_and_publish_flow():
    FakeIG.calls = []
    appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 200)
    with tempfile.TemporaryDirectory() as t:
        a = _app(Path(t))
        post = {"id": "p1", "slug": "ornek-haber", "title": "Örnek haber başlığı", "summary": "Kısa özet.",
                "category": "teknoloji", "tags": ["Apple"], "body": "Metin.", "sources": [{"name": "Apple", "url": "https://a"}],
                "published_at": iso(now_utc())}
        a.store.save_post(post)
        assert a.ig_enabled
        a._send_social(post)                          # otomatik modda sıraya girer
        assert [x["id"] for x in a.state["ig_queue"]] == ["p1"]
        assert not a.ig_enqueue(post)                 # iki kez girmez
        a.ig_tick()
        assert a.state["ig_queue"] == []
        assert a.state["ig_done"][-1]["permalink"].endswith("/p/abc/")
        assert a.store.count(a.today(), "instagram") == 1
        assert a.store.ig["target"] == "178"          # "me" desteklenmeyince hesap numarasına geçti
        kinds = [c[0] for c in FakeIG.calls]
        assert kinds == ["carousel", "carousel", "story"]
        assert FakeIG.calls[1][2][0] == "https://example.github.io/smarity/ig/p1-post.jpg"
        assert "profildeki bağlantıda" in FakeIG.calls[1][3]
        # aynı turda ikinci haber boşluk süresi dolmadan paylaşılmaz
        post2 = {**post, "id": "p2", "slug": "ikinci"}
        a.store.save_post(post2)
        a.ig_enqueue(post2)
        a.ig_tick()
        assert [x["id"] for x in a.state["ig_queue"]] == ["p2"]
        # iptal ve geri alma düğmeleri
        assert a._on_button("x", "p2").startswith("🚫")
        assert a.state["ig_queue"] == []
        assert a._on_button("q", "p2").startswith("📸")
        # siteden kaldırılan haber sıradan düşer
        a._on_button("d", "p2")
        assert a.state["ig_queue"] == []
        out = (Path(t) / "data" / "_mock" / "outbox.jsonl").read_text(encoding="utf-8")
        assert "Instagram&#x27;da paylaşıldı" in out or "Instagram'da paylaşıldı" in out
        a.store.save()
        assert "SECRET-TOKEN" not in (Path(t) / "data" / "instagram.json").read_text()


def test_missing_card_triggers_rebuild():
    appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 404)
    with tempfile.TemporaryDirectory() as t:
        a = _app(Path(t))
        post = {"id": "p9", "slug": "x", "title": "T", "summary": "S", "category": "gaming", "tags": [],
                "body": "B", "sources": [], "published_at": iso(now_utc())}
        a.store.save_post(post)
        a.ig_enqueue(post)
        a.store.site_dirty = False
        a.state["ig_queue"][0]["queued_at"] = "2020-01-01T00:00:00+00:00"
        a.cfg.raw["social"]["instagram_max_wait_hours"] = 10 ** 6
        a.ig_tick()
        assert a.store.site_dirty and a.state["ig_queue"][0].get("restaged_at")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
@@@SM@@@ SHA
957763a719dd9762adab8a23ecada990cbe52c429d8c20076793691a78602ef6 haberbot/app.py
4f65f4d30a3befdba46e811da9bca3b5e127620425337bbcf89a86cf24bc7e78 haberbot/config.py
066e08a5e713b2ac48e257539f1a6900ce42fa096e8bc6416e75a83d04487f2c haberbot/store.py
579c96c308fe049fa29847c292bfc3762bf8a1d68b08b23940fae1939b8f585e haberbot/telegram.py
6e122dd2e266f492d9d1df890a77a13706512e5ea5cabcb0ffe7d8872e58ba5e haberbot/covers.py
956d19bd0f16b2dbd8b9266b666f9d9d6eb5f5f65297d6bd4fa35241d2ed53d8 haberbot/visuals.py
ffbf59d1e96cd39cef365d699342780705f8a25b6415edcd8c9a4a6ad6530e0e haberbot/__main__.py
c9f7ae8087c7526926fa4b5d88a4ceccae5366fb4b1c3ee9d1558ea2152af8fa haberbot/site.py
1b6e13b3c2522d676fa35a43e629cc5ed7461275d97cca2dbb94363470e8afdb templates/cards/news.html
4b383ddf973e59d89148e34b7ae13488e89bccf74a3815e4330c0740e5f11d57 config.yaml
25e249d9d9fc6bc9f44069b9c0f4f0e1e4ed1025ca190c9e467789edb64aa7c3 haberbot/instagram.py
9ce01dbc3d63a20237f1450c780fa0466a7221b2c52f8a26c97d037e9d876cb5 tests/test_instagram.py
