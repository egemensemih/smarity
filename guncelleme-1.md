SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -120,4 +120,5 @@
   # birkaç dakika sonra carousel (3 görsel) ve hikâye olarak paylaşılır. Telegram'dan /instagram ile yönetilir.
   instagram_auto: true
+  instagram_user_id: "17841405730803695"   # @smarityco hesap numarası (Meta panelinde hesabın altında yazar)
   instagram_story: true            # carousel'e ek olarak hikâye de paylaşılsın
   instagram_hours: [8, 24]         # paylaşım saatleri; gece yayınlanan haberler sabah 8'de sırayla paylaşılır
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -16,5 +16,5 @@
 from .covers import COVER_VERSION, PHOTO_COVER_VERSION, photo_design
 from .extract import full_text
-from .instagram import Instagram, InstagramError, TokenStore, fingerprint, head_ok
+from .instagram import Instagram, InstagramError, TokenStore, fingerprint, head_ok, is_fb_token
 from .llm import LLMError, MockLLM, estimate_cost, make_llm
 from .prompts import (APPEAL_SCHEMA, COVERLINE_SCHEMA, EDIT_SCHEMA, FLAG_LABELS, FLAGS, PHOTO_SCHEMA, SEO_SCHEMA, TRIAGE_SCHEMA,
@@ -2109,5 +2109,6 @@
         data = self.store.ig
         ts = TokenStore(secret, data)
-        if ts.refresh_due():
+        fb = is_fb_token(ts.token)                   # yeni Meta kurulumu: süresi dolmayan anahtar, yenileme yok
+        if not fb and ts.refresh_due():
             try:
                 tok, exp = Instagram(ts.token).refresh()
@@ -2122,5 +2123,6 @@
             self._ig_problem(f"erişim anahtarının süresi {max(0, left):.0f} gün içinde doluyor ve yenilenemedi. "
                              "Meta geliştirici panelinden yeni anahtar üretip GitHub'da <b>IG_ACCESS_TOKEN</b> değerini güncelle.")
-        cli = Instagram(ts.token, self._ig_cfg("instagram_api_version", None) or "v25.0")
+        cli = Instagram(ts.token, self._ig_cfg("instagram_api_version", None) or "v25.0",
+                        ig_id=str(self._ig_cfg("instagram_user_id", "") or "").strip())
         fp = fingerprint(secret)
         if data.get("me_fp") != fp or not data.get("id"):
@@ -2147,5 +2149,6 @@
         if d.get("target"):
             return [d["target"]]
-        return [t for t in dict.fromkeys(["me", d.get("user_id"), d.get("id")]) if t]
+        first = [] if getattr(self._ig, "fb", False) else ["me"]   # Facebook Graph'ta "me" Instagram hesabı değildir
+        return [t for t in dict.fromkeys(first + [d.get("user_id"), d.get("id")]) if t]
 
     def _ig_run(self, fn, *a):
--- a/haberbot/instagram.py
+++ b/haberbot/instagram.py
@@ -1,3 +1,3 @@
-"""Instagram otomatik paylaşım (Instagram API with Instagram Login).
+"""Instagram otomatik paylaşım (Instagram API with Instagram Login ya da Meta'nın yeni "Unified login" kurulumu).
 
 Akış: haber yayınlanınca sıraya girer → site yayınlanırken kartlar _site/ig/ altına konur →
@@ -7,4 +7,7 @@
 düzenli yenilenir; yenilenen anahtar yalnızca asıl gizli anahtarla açılabilecek şekilde şifrelenip
 data/instagram.json dosyasına yazılır (depoda düz metin anahtar yoktur).
+
+Meta'nın yeni uygulamalarda verdiği sistem kullanıcısı anahtarı ("EAA…" ile başlar, süresi dolmaz) graph.facebook.com
+üzerinden çalışır: hesap numarası ayarlardan (social.instagram_user_id) alınır ya da anahtarın eriştiği hesaplardan bulunur.
 """
 from __future__ import annotations
@@ -22,5 +25,11 @@
 
 API = "https://graph.instagram.com"
+FB_API = "https://graph.facebook.com"
 VERSION = "v25.0"
+
+
+def is_fb_token(token: str) -> bool:
+    """Facebook Graph anahtarı mı (sistem kullanıcısı / Facebook girişi)? Instagram girişi anahtarları "IG" ile başlar."""
+    return str(token or "").startswith("EAA")
 
 
@@ -80,7 +89,9 @@
 # ── API istemcisi ──
 class Instagram:
-    def __init__(self, token: str, version: str = VERSION, timeout: int = 60):
+    def __init__(self, token: str, version: str = VERSION, timeout: int = 60, ig_id: str = ""):
         self.token = token
-        self.base = f"{API}/{version}"
+        self.fb = is_fb_token(token)
+        self.ig_id = str(ig_id or "")
+        self.base = f"{FB_API if self.fb else API}/{version}"
         self.timeout = timeout
         self.s = requests.Session()
@@ -111,5 +122,15 @@
 
     def me(self) -> dict:
-        return self._req("GET", "me", fields="user_id,username")
+        if not self.fb:
+            return self._req("GET", "me", fields="user_id,username")
+        ig_id = self.ig_id
+        if not ig_id:  # anahtarın eriştiği sayfalara bağlı ilk Instagram hesabı
+            pages = self._req("GET", "me/accounts", fields="instagram_business_account{id,username}").get("data") or []
+            ig_id = next((str(p["instagram_business_account"]["id"]) for p in pages if p.get("instagram_business_account")), "")
+            if not ig_id:
+                raise InstagramError("Anahtarın eriştiği bir Instagram hesabı bulunamadı; config.yaml → "
+                                     "social.instagram_user_id alanına hesap numarasını yaz", 100)
+        j = self._req("GET", ig_id, fields="id,username")
+        return {"id": str(j.get("id") or ig_id), "user_id": str(j.get("id") or ig_id), "username": j.get("username", "")}
 
     def container(self, ig_id: str, **params) -> str:
@@ -163,4 +184,6 @@
     def refresh(self) -> tuple[str, int]:
         """Uzun ömürlü anahtarı 60 gün uzatır (anahtar en az 24 saatlik olmalı)."""
+        if self.fb:
+            raise InstagramError("Sistem kullanıcısı anahtarının süresi dolmaz, yenilenmez")
         s = requests.Session()
         try:
--- a/tests/test_instagram.py
+++ b/tests/test_instagram.py
@@ -45,6 +45,7 @@
     calls = []
 
-    def __init__(self, token, version="v25.0", timeout=60):
+    def __init__(self, token, version="v25.0", timeout=60, ig_id=""):
         self.token = token
+        self.fb = ig.is_fb_token(token)
 
     def me(self):
@@ -114,4 +115,33 @@
 
 
+def test_fb_system_user_token():
+    """Meta'nın yeni "Unified login" kurulumu: EAA… anahtarı graph.facebook.com'da, hesap numarasıyla çalışır."""
+    cli = ig.Instagram("EAAtest", ig_id="1784")
+    assert cli.fb and cli.base.startswith("https://graph.facebook.com/")
+    assert not ig.Instagram("IGAAtest").fb and ig.Instagram("IGAAtest").base.startswith("https://graph.instagram.com/")
+    seen = []
+    cli._req = lambda method, path, **params: seen.append(path) or {"id": "1784", "username": "smarityco"}
+    assert cli.me() == {"id": "1784", "user_id": "1784", "username": "smarityco"} and seen == ["1784"]
+    try:
+        cli.refresh()
+        raise AssertionError("sistem kullanıcısı anahtarı yenilenmemeli")
+    except ig.InstagramError:
+        pass
+    FakeIG.calls = []
+    appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 200)
+    with tempfile.TemporaryDirectory() as t:
+        a = _app(Path(t))
+        a.cfg.instagram_token = "EAA-SECRET-TOKEN"
+        post = {"id": "p1", "slug": "ornek-haber", "title": "Örnek haber başlığı", "summary": "Kısa özet.",
+                "category": "teknoloji", "tags": ["Apple"], "body": "Metin.", "sources": [{"name": "Apple", "url": "https://a"}],
+                "published_at": iso(now_utc())}
+        a.store.save_post(post)
+        a.ig_enqueue(post)
+        a.ig_tick()
+        assert a.state["ig_queue"] == [] and FakeIG.calls[0][1] == "178"   # "me" denenmeden doğrudan hesap numarası
+        a.store.save()
+        assert "EAA-SECRET-TOKEN" not in (Path(t) / "data" / "instagram.json").read_text()
+
+
 def test_missing_card_triggers_rebuild():
     appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 404)
@@@SM@@@ SHA
069645ed0e13132e7773d536fe63fd37f1b05f1c9ae428c9c714c77e5713609e config.yaml
c7b1691209baf98cda42d127f8d9bfa5abef888a3144d2993bf288b9aca0175e haberbot/app.py
64437db87fb40d66e5b0f776b2f9fda274bd18e875ce65770548897b2af638ee haberbot/instagram.py
c1c5af0f8281a01bd9c642fe42dd586facf309137a9f8189cec5d0e013f4d2f7 tests/test_instagram.py
