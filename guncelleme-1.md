SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -133,4 +133,5 @@
   instagram_max_per_day: 0         # günlük üst sınır (0 = sınır yok; Instagram'ın kendi sınırı 100)
   instagram_max_wait_hours: 12     # bundan uzun sırada bekleyen haber artık paylaşılmaz (bayatlamasın)
+  instagram_blocked_retry_hours: 3 # Meta erişimi reddederse bot bu kadar saat bekleyip yeniden dener (her turda yoklamaz)
   # Instagram post + story görselleri Telegram'a gönderilmez; IG_ACCESS_TOKEN eklenince paylaşım kendiliğinden yapılır.
   # (true yapılırsa, Instagram bağlı değilken görseller elle paylaşım için Telegram'a gelir.)
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -8,4 +8,5 @@
 import shutil
 import time
+from datetime import timedelta
 from urllib.parse import urlsplit
 
@@ -2241,4 +2242,8 @@
         secret = self.cfg.instagram_token
         data = self.store.ig
+        # erişim reddedildiyse Meta'yı her turda (5 dk) yoklama: bekleme süresi dolana ya da anahtar değişene kadar dur
+        pause = self.state.get("ig_pause") or {}
+        if pause.get("fp") == fingerprint(secret) and hours_since(pause.get("until")) < 0:
+            return None
         ts = TokenStore(secret, data)
         fb = is_fb_token(ts.token)                   # yeni Meta kurulumu: süresi dolmayan anahtar, yenileme yok
@@ -2269,10 +2274,20 @@
                         log.warning("Instagram teşhisi yapılamadı: %s", de)
                 if e.auth:
-                    self._ig_problem(f"erişim anahtarı çalışmıyor ({esc(e)}). Yeni anahtar üretip GitHub'da "
-                                     "<b>IG_ACCESS_TOKEN</b> değerini güncelle.")
+                    blocked = "blocked" in str(e).lower()
+                    wait = float(self._ig_cfg("instagram_blocked_retry_hours", 3) or 3)
+                    self.state["ig_pause"] = {"fp": fp, "until": iso(now_utc() + timedelta(hours=wait))}
+                    if blocked:   # Meta işletme hesabını kısıtladı: anahtar değil, hesap sorunu
+                        self._ig_problem(f"Meta uygulamanın erişimini engelledi ({esc(e)}). Bu genellikle işletme "
+                                         "hesabı kısıtlandığında olur: Meta'nın e-postasındaki <b>Sorunu düzelt</b> ile "
+                                         f"inceleme iste. Kısıtlama kalkınca bot kendiliğinden paylaşır (her {wait:.0f} "
+                                         "saatte bir dener).")
+                    else:
+                        self._ig_problem(f"erişim anahtarı çalışmıyor ({esc(e)}). Yeni anahtar üretip GitHub'da "
+                                         f"<b>IG_ACCESS_TOKEN</b> değerini güncelle. (Bot {wait:.0f} saatte bir yeniden dener.)")
                 else:
                     self.state["ig_problem"] = {"at": iso(now_utc()), "text": clip(f"hesap okunamadı: {e}", 400)}
                     log.warning("Instagram hesabı okunamadı: %s", e)
                 return None
+            self.state.pop("ig_pause", None)
             data.update({"me_fp": fp, "id": str(me.get("id") or ""), "user_id": str(me.get("user_id") or ""),
                          "username": me.get("username", "")})
@@ -2521,4 +2536,5 @@
         if not self.cfg.instagram_token:
             return self.instagram_status()
+        self.state.pop("ig_pause", None)          # sahibi denemek istiyor: beklemeyi bırak, hemen yeniden dene
         done = {x.get("id") for x in self.state.get("ig_done") or []}
         queued = {x.get("id") for x in self.state.get("ig_queue") or []}
--- a/tests/test_instagram.py
+++ b/tests/test_instagram.py
@@ -336,4 +336,39 @@
 
 
+class BlockedIG(FakeIG):
+    tries = 0
+
+    def me(self):
+        BlockedIG.tries += 1
+        raise ig.InstagramError("API access blocked.", 200)
+
+
+def test_blocked_access_backs_off():
+    """Meta erişimi engellediğinde bot her turda yoklamaz; bekler, anahtar değişince ya da /instagram dene ile yeniden dener."""
+    BlockedIG.tries = 0
+    appmod.Instagram, appmod.head_ok = BlockedIG, (lambda url: 200)
+    with tempfile.TemporaryDirectory() as t:
+        a = _app(Path(t))
+        a.cfg.instagram_token = "EAA-TOKEN-1"
+        post = _pub(1, 1, 9)
+        a.store.save_post(post)
+        a.ig_enqueue(post)
+        a.ig_tick()
+        assert BlockedIG.tries == 1 and a.state["ig_pause"]["until"]
+        assert "Sorunu düzelt" in a.state["ig_problem"]["text"]
+        for _ in range(3):                     # sonraki turlar: Meta'ya istek gitmez
+            a._ig = None
+            a.ig_tick()
+        assert BlockedIG.tries == 1 and a.state["ig_queue"]
+        a._ig = None
+        a.cfg.instagram_token = "EAA-TOKEN-2"   # yeni anahtar: hemen denenir
+        a.ig_tick()
+        assert BlockedIG.tries == 2
+        a._ig = None
+        a.ig_try_latest()                       # /instagram dene: bekleme biter
+        a.ig_tick()
+        assert BlockedIG.tries == 3
+
+
 def test_missing_card_triggers_rebuild():
     appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 404)
@@@SM@@@ SHA
383d366fdf311244ab0d88d712b3f4eda67b002b284ac41a2ffbe850db2ffbdc config.yaml
ef064066bf0333488cdaac0d314e4163199eac785a0fc2971281bd53359c4cf8 haberbot/app.py
d5334b90ccb6d91f4552655a9bca06891454bcf664514db1a6349dd2f10ffd62 tests/test_instagram.py
