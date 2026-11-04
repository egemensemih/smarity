SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -121,4 +121,5 @@
   instagram_auto: true
   instagram_user_id: "17841405730803695"   # @smarityco hesap numarası (Meta panelinde hesabın altında yazar)
+  instagram_every_post: false      # false: yayınlanan her haber otomatik paylaşılmaz (seçim sosyal medya masasında)
   instagram_story: true            # carousel'e ek olarak hikâye de paylaşılsın
   instagram_hours: [8, 24]         # paylaşım saatleri; gece yayınlanan haberler sabah 8'de sırayla paylaşılır
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -1262,5 +1262,7 @@
         Carousel: kapak + öne çıkanlar + neden önemli. Hikâye: bağlantı çıkartmasıyla siteye yönlendirir."""
         if not force and self.ig_enabled:
-            self.ig_enqueue(post)
+            # her haber paylaşılmaz: social.instagram_every_post false iken yalnızca seçilenler (/instagram dene, düğmeler)
+            if self._ig_cfg("instagram_every_post", True):
+                self.ig_enqueue(post)
             return
         if not (self.tg and self.chat_id):
--- a/tests/test_instagram.py
+++ b/tests/test_instagram.py
@@ -70,4 +70,5 @@
     raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
     raw["social"]["instagram_hours"] = [0, 24]
+    raw["social"]["instagram_every_post"] = True
     cfg = Config(raw=raw, root=tmp, site_url="https://example.github.io/smarity", mock=True,
                  instagram_token="SECRET-TOKEN", telegram_chat_id="1")
@@ -154,4 +155,7 @@
                                "category": "teknoloji", "tags": [], "body": "Metin.", "sources": [{"name": "A", "url": "https://a"}],
                                "published_at": iso(now_utc() - timedelta(hours=h))})
+        a.cfg.raw["social"]["instagram_every_post"] = False
+        a._send_social(a.store.load_post("p2"))                     # her haber otomatik sıraya girmez
+        assert not a.state.get("ig_queue")
         assert "Haber 2" in a.ig_try_latest()                       # en yeni haber
         assert [x["id"] for x in a.state["ig_queue"]] == ["p2"]
@@@SM@@@ SHA
40fbd73c805bd81b940f163396b8ef08f02149a28e13074c8238354a42bb6975 config.yaml
155faa51b8dd1cf6de4779e5db1c310dbff009f032b7301420cca50e99e91101 haberbot/app.py
ec5b2575420e856c3bc29e5bea9756e3cb1129c39996e287eaaade28ec4af46e tests/test_instagram.py
