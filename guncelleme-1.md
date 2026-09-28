SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -92,6 +92,7 @@
   instagram_max_per_day: 0         # günlük üst sınır (0 = sınır yok; Instagram'ın kendi sınırı 100)
   instagram_max_wait_hours: 12     # bundan uzun sırada bekleyen haber artık paylaşılmaz (bayatlamasın)
-  # IG_ACCESS_TOKEN yokken: Instagram post + story görsellerini elle paylaşman için Telegram'a gönder
-  send_to_telegram: true
+  # Instagram post + story görselleri Telegram'a gönderilmez; IG_ACCESS_TOKEN eklenince paylaşım kendiliğinden yapılır.
+  # (true yapılırsa, Instagram bağlı değilken görseller elle paylaşım için Telegram'a gelir.)
+  send_to_telegram: false
   # Instagram görsel tarzı:
   # ozet  : logo, kategori etiketi, vurgulu büyük başlık ve kısa özet; renkler habere göre değişir (önerilen)
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -35,5 +35,4 @@
     "n": ("⏳ Fotoğraflar kaldırılıyor…", "🚫 Fotoğraflar kaldırıldı"),
     "w": ("⏳ Yeniden yazılıyor…", "🔁 Yeniden yazıldı"),
-    "s": ("⏳ Görseller hazırlanıyor…", "📱 Gönderildi"),
 }
 IG_WINDOW_DEFAULT = [8, 24]
@@ -52,5 +51,5 @@
 ]
 COMMANDS_VERSION = 3
-KEYBOARD_VERSION = 3          # yayındaki haber mesajlarının düğmeleri bu sürüme göre bir kez yenilenir
+KEYBOARD_VERSION = 4          # yayındaki haber mesajlarının düğmeleri bu sürüme göre bir kez yenilenir
 HELP = """<b>Nasıl çalışır?</b>
 Kaynaklar düzenli taranır; teknoloji, girişim, yapay zeka, ürün, otomobil ve oyun dünyasından önemli haberler Türkçe yazılıp buraya düşer.
@@ -541,6 +540,5 @@
             return [[{"text": "🔗 Haberi aç", "url": self.cfg.post_url(d["slug"])},
                      {"text": "🗑 Kaldır", "callback_data": f"d:{did}"}],
-                    [{"text": "📄 Tam metin", "callback_data": f"f:{did}"},
-                     {"text": "📱 Instagram", "callback_data": f"s:{did}"}], self._visual_buttons(d),
+                    [{"text": "📄 Tam metin", "callback_data": f"f:{did}"}], self._visual_buttons(d),
                     [{"text": "⭐ Manşetten çıkar" if d.get("home") == "pin" else "⭐ Manşete al", "callback_data": f"m:{did}"},
                      {"text": "🏠 Ana sayfada göster" if d.get("home") == "hide" else "🙈 Ana sayfada gösterme",
@@ -835,9 +833,10 @@
             self._send_preview(d, kind)
             return msg
-        if action == "s":
+        if action == "s":   # eski mesajlardaki "Instagram" düğmesi: görseller artık Telegram'a gelmez
             if where != "post":
                 return "Önce yayınlanmalı."
-            self._send_social(d, force=True)
-            return "📱 Gönderildi"
+            if self.ig_enabled:
+                return "📸 Instagram sırasına eklendi" if self.ig_enqueue(d) else "Zaten sırada ya da paylaşıldı."
+            return "📸 Instagram bağlanınca haberler kendiliğinden paylaşılacak."
         if action == "w":
             if where != "draft" or d.get("status") != "pending":
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -102,4 +102,5 @@
         kb = a._keyboard(a.store.load_post("p01"), "published")
         assert [b["callback_data"][0] for b in kb[-1]] == ["m", "h"]
+        assert not any(b.get("callback_data", "").startswith("s:") for row in kb for b in row)   # Instagram düğmesi yok
         assert a._on_button("m", "p01").startswith("⭐")
         p = a.store.load_post("p01")
@@ -144,4 +145,12 @@
         assert a._on_button("m", "p01").startswith("⭐")
         assert a._manset_keyboard()[1][0]["text"].startswith("📌")
+        # Instagram görselleri Telegram'a gelmez (bağlanınca otomatik paylaşılır)
+        outbox = a.tg.dir / "outbox.jsonl"
+        before = outbox.read_text(encoding="utf-8") if outbox.exists() else ""
+        assert not a.ig_enabled
+        a._send_social(a.store.load_post("p02"))
+        assert "kendiliğinden" in a._on_button("s", "p02")
+        after = outbox.read_text(encoding="utf-8") if outbox.exists() else ""
+        assert "sendMediaGroup" not in after[len(before):] and "sendPhoto" not in after[len(before):]
         # eski mesajların düğmeleri bir kez yenilenir
         a.refresh_keyboards()
@@@SM@@@ SHA
c7fbbaec94a16751832b5d151c6db2f62794b75687ed2e053335a1cdca9ce583 config.yaml
03eb80e8c47ce5a09f9c32a4f10667333ee3fc2320210c4b4301123f23289693 haberbot/app.py
f683a3c35b6b03c9af80a48923355d81795789510abde29a38c6bb258121f8ed tests/test_home.py
