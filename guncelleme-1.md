SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -30,4 +30,5 @@
 SLOW_ACTIONS = {
     "p": ("⏳ Yayınlanıyor…", "✅ Yayınlandı"),
+    "P": ("⏳ Yayınlanıyor…", "⭐ Yayınlandı ve manşete alındı"),
     "v": ("⏳ Yeni görsel hazırlanıyor…", "🎨 Yeni görsel hazır"),
     "g": ("⏳ Fotoğraf değiştiriliyor…", "🖼 Fotoğraf değişti"),
@@ -46,8 +47,10 @@
     ("devam", "Yeniden başlat"),
     ("kaynaklar", "Kaynak güven puanları"),
+    ("manset", "Manşeti yönet: haberi manşete al / çıkar"),
     ("instagram", "Instagram paylaşımları: durum / kapat / ac"),
     ("yardim", "Nasıl kullanılır"),
 ]
-COMMANDS_VERSION = 2
+COMMANDS_VERSION = 3
+KEYBOARD_VERSION = 3          # yayındaki haber mesajlarının düğmeleri bu sürüme göre bir kez yenilenir
 HELP = """<b>Nasıl çalışır?</b>
 Kaynaklar düzenli taranır; teknoloji, girişim, yapay zeka, ürün, otomobil ve oyun dünyasından önemli haberler Türkçe yazılıp buraya düşer.
@@ -63,5 +66,6 @@
 ✏️ <b>Düzeltme</b> — bir haber mesajını <i>yanıtlayıp</i> talimat yaz: "başlığı kısalt", "ikinci paragrafı çıkar" gibi. Yayınlanmış habere de uygulanır.
 🗑 <b>Kaldır</b> — yayınlanmış haberi siteden kaldırır
-⭐ <b>Manşete al</b> — haberi 36 saat ana sayfa manşetinin en başına koyar
+⭐ <b>Yayınla + manşet</b> — onay beklerken tek tuşla yayınlar ve manşete alır
+⭐ <b>Manşete al</b> — haberi 36 saat ana sayfa manşetinin en başına koyar (<code>/manset</code> ile son haberlerden de seçebilirsin)
 🙈 <b>Ana sayfada gösterme</b> — haber ana sayfaya çıkmaz, kategoride ve "Tüm haberler"de kalır
 
@@ -72,5 +76,5 @@
 📸 <b>Instagram</b> — yayınlanan her haber birkaç dakika içinde carousel ve hikâye olarak Instagram'da paylaşılır. Sıradaki bir haberi mesajındaki <b>Instagram'a gönderme</b> düğmesiyle durdurabilirsin. Tümünü durdurmak için <code>/instagram kapat</code>.
 
-Komutlar: /durum /bekleyen /mod /topla /duraklat /devam /kaynaklar /instagram"""
+Komutlar: /manset /durum /bekleyen /mod /topla /duraklat /devam /kaynaklar /instagram"""
 
 
@@ -528,4 +532,5 @@
             kb = [[{"text": "✅ Yayınla", "callback_data": f"p:{did}"},
                    {"text": "❌ Reddet", "callback_data": f"r:{did}"}],
+                  [{"text": "⭐ Yayınla + manşet", "callback_data": f"P:{did}"}],
                   [{"text": "📄 Tam metin", "callback_data": f"f:{did}"},
                    {"text": "🔁 Yeniden yaz", "callback_data": f"w:{did}"}], self._visual_buttons(d)]
@@ -711,4 +716,17 @@
         if not d:
             return "Bu haber artık yok."
+        if action == "P":                     # yayınla ve manşete al
+            if where == "post":
+                return self._on_button("m", did) if d.get("home") != "pin" else "Zaten manşette."
+            if d.get("status") not in ("pending", "rejected"):
+                return "Bu taslak kapanmış."
+            if d.get("status") == "rejected":
+                self._undo_decision(d)
+            d["home"], d["home_at"] = "pin", iso(now_utc())
+            post = self.publish(d, auto=False)
+            policy.record(self.stats, post, ok=True)
+            self._update_preview(post, "published")
+            self._send_social(post)
+            return "⭐ Yayınlandı ve manşete alındı"
         if action == "p":
             if where == "post":
@@ -774,4 +792,6 @@
             st.save_post(d)
             self._update_preview(d, "auto" if d.get("publish_mode") == "auto" else "published")
+            if self._cb_mid and self._cb_mid == self.state.get("manset_mid"):
+                self.tg.edit_text(self.chat_id, self._cb_mid, self._manset_text(), self._manset_keyboard())
             return {"pin": "⭐ Manşete alındı", "hide": "🙈 Ana sayfada gösterilmeyecek (kategoride kalır)",
                     None: "↩️ Ana sayfada normal sıralamaya döndü"}[new]
@@ -951,4 +971,8 @@
         elif cmd == "kaynaklar":
             self.notify(self.sources_text(), silent=True)
+        elif cmd in ("manset", "manşet"):
+            res = self.tg.send_message(self.chat_id, self._manset_text(), keyboard=self._manset_keyboard(), silent=True)
+            if isinstance(res, dict) and res.get("message_id"):
+                self.state["manset_mid"] = res["message_id"]
         elif cmd == "instagram":
             if arg in ("kapat", "durdur"):
@@ -1373,4 +1397,45 @@
         return "\n".join(lines)
 
+    # ── manşet yönetimi (/manset) ───────────────────────────
+    def _manset_posts(self) -> list[dict]:
+        """Son 3 günün yayınları (en fazla 12), en yeni önce."""
+        return [p for p in self.store.posts() if hours_since(p.get("published_at")) <= 72][:12]
+
+    def _manset_text(self) -> str:
+        from .site import hot
+        n = int((self.cfg.raw.get("home") or {}).get("featured_count") or 10)
+        ranked = sorted((p for p in self.store.posts() if hot(p) >= 0), key=lambda p: -hot(p))[:n]
+        lines = [f"⭐ <b>Manşet</b> (sitede şu an ilk {n}):"]
+        for i, p in enumerate(ranked, 1):
+            pin = " 📌" if p.get("home") == "pin" else ""
+            lines.append(f"{i}. {esc(clip(p.get('short_title') or p['title'], 60))}{pin}")
+        lines += ["", "Aşağıdaki son haberlerden birine bas: ⭐ manşete alır (36 saat en başta), 📌 olanı manşetten çıkarır."]
+        return "\n".join(lines)
+
+    def _manset_keyboard(self) -> list[list[dict]]:
+        rows = []
+        for p in self._manset_posts():
+            mark = "📌" if p.get("home") == "pin" else "🙈" if p.get("home") == "hide" else "⭐"
+            rows.append([{"text": f"{mark} {clip(p.get('short_title') or p['title'], 48)}", "callback_data": f"m:{p['id']}"}])
+        return rows
+
+    def refresh_keyboards(self) -> None:
+        """Düğmeler değişince son 3 günün yayın mesajlarına yeni düğmeleri bir kez ekle."""
+        if not (self.tg and self.chat_id) or self.state.get("keyboard_v") == KEYBOARD_VERSION:
+            return
+        self.state["keyboard_v"] = KEYBOARD_VERSION
+        n = 0
+        for p in self.store.posts():
+            if hours_since(p.get("published_at")) > 72:
+                break
+            if (p.get("telegram") or {}).get("message_id"):
+                self._update_preview(p, "auto" if p.get("publish_mode") == "auto" else "published")
+                n += 1
+        for d in self.store.drafts("pending"):
+            if (d.get("telegram") or {}).get("message_id"):
+                self._update_preview(d, "pending")
+                n += 1
+        log.info("Telegram düğmeleri yenilendi: %d mesaj", n)
+
     # ── gerçek fotoğraflar ──────────────────────────────────
     # Düzen: fotoğraflar {id}-g0.webp, {id}-g1.webp … ; {id}.webp her zaman tasarımlı kapaktır:
@@ -1623,4 +1688,8 @@
             log.exception("Instagram hatası: %s", e)
         self.refresh_covers()
+        try:
+            self.refresh_keyboards()
+        except Exception as e:  # noqa: BLE001
+            log.warning("Telegram düğmeleri yenilenemedi: %s", e)
         self.maybe_summary()
         self.listen(int(self.cfg.get("schedule", "listen_seconds", 120) or 0))
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -122,4 +122,31 @@
 
 
+def test_publish_with_pin_and_manset_command():
+    with _App() as (cfg, a):
+        from haberbot.telegram import MockTelegram
+        a.tg = a.tg or MockTelegram(cfg.root / "tg")
+        a.store.save_post(_post(1, 2, publish_mode="manual", telegram={"message_id": 11}))
+        d = {**_post(2, 0), "status": "pending", "created_at": iso(now_utc()), "telegram": {"message_id": 12}}
+        d.pop("published_at")
+        d.pop("slug")
+        a.store.save_draft(d)
+        kb = a._keyboard(a.store.load_draft("p02"), "pending")
+        assert any(b["callback_data"] == "P:p02" for row in kb for b in row)       # onayda "yayınla + manşet"
+        assert a._on_button("P", "p02").startswith("⭐")
+        p = a.store.load_post("p02")
+        assert p["home"] == "pin" and hot(p) >= 100
+        # /manset: son haberler düğmeleriyle; listeden basınca liste yenilenir
+        a._on_command("manset", "")
+        assert a.state.get("manset_mid")
+        rows = a._manset_keyboard()
+        assert [r[0]["callback_data"] for r in rows][:2] == ["m:p02", "m:p01"] and rows[0][0]["text"].startswith("📌")
+        a._cb_mid = a.state["manset_mid"]
+        assert a._on_button("m", "p01").startswith("⭐")
+        assert a._manset_keyboard()[1][0]["text"].startswith("📌")
+        # eski mesajların düğmeleri bir kez yenilenir
+        a.refresh_keyboards()
+        assert a.state["keyboard_v"] == appmod.KEYBOARD_VERSION
+
+
 if __name__ == "__main__":
     for name, fn in list(globals().items()):
@@@SM@@@ SHA
6745243c6c35cfeaa192b25cfd061998954bdd01a70ea9ec2f02638e3a5389de haberbot/app.py
82c33d822a880c5e645139542810ace2d1509cd8d8641e7b6760c5f317b49549 tests/test_home.py
