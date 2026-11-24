SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -120,4 +120,8 @@
   # birkaç dakika sonra carousel (3 görsel) ve hikâye olarak paylaşılır. Telegram'dan /instagram ile yönetilir.
   instagram_auto: true
+  # Paylaşım yolu: auto = IG_ACCESS_TOKEN'daki anahtara bakar (Meta anahtarı "EAA"/"IG" ile başlar; değilse Zernio API anahtarıdır)
+  # Zernio: Meta onaylı uygulaması olan paylaşım servisi; kendi Meta uygulamamız gerekmez, Instagram Zernio panelinde bağlanır.
+  instagram_provider: auto
+  zernio_account_id: ""            # boşsa Zernio'ya bağlı ilk Instagram hesabı kullanılır
   instagram_user_id: "17841405730803695"   # @smarityco hesap numarası (Meta panelinde hesabın altında yazar)
   instagram_every_post: false      # false: her haber paylaşılmaz; sosyal medya masası seçer (gönderi + hikâye / hikâye / hiç)
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -17,5 +17,5 @@
 from .covers import COVER_VERSION, PHOTO_COVER_VERSION, photo_design
 from .extract import full_text
-from .instagram import Instagram, InstagramError, TokenStore, fingerprint, head_ok, is_fb_token
+from .instagram import Instagram, InstagramError, TokenStore, Zernio, fingerprint, head_ok, is_fb_token, is_meta_token
 from .llm import LLMError, MockLLM, estimate_cost, make_llm
 from .prompts import (APPEAL_SCHEMA, COVERLINE_SCHEMA, EDIT_SCHEMA, FLAG_LABELS, FLAGS, PHOTO_SCHEMA, SEO_SCHEMA, TRIAGE_SCHEMA,
@@ -2084,4 +2084,12 @@
 
     @property
+    def ig_provider(self) -> str:
+        """Paylaşım yolu: "zernio" ya da "meta". Ayarda "auto" ise anahtarın biçiminden anlaşılır."""
+        p = str(self._ig_cfg("instagram_provider", "auto") or "auto").strip().lower()
+        if p in ("zernio", "meta"):
+            return p
+        return "meta" if is_meta_token(self.cfg.instagram_token) else "zernio"
+
+    @property
     def ig_enabled(self) -> bool:
         return self.cfg.instagram_auto and not self.state.get("ig_off")
@@ -2246,6 +2254,7 @@
         if pause.get("fp") == fingerprint(secret) and hours_since(pause.get("until")) < 0:
             return None
+        zern = self.ig_provider == "zernio"
         ts = TokenStore(secret, data)
-        fb = is_fb_token(ts.token)                   # yeni Meta kurulumu: süresi dolmayan anahtar, yenileme yok
+        fb = zern or is_fb_token(ts.token)           # Zernio / yeni Meta kurulumu: süresi dolmayan anahtar, yenileme yok
         if not fb and ts.refresh_due():
             try:
@@ -2257,10 +2266,13 @@
                 data["refresh_tried_at"] = iso(now_utc())
                 log.info("Instagram anahtarı şimdilik yenilenemedi: %s", e)
-        left = ts.days_left()
+        left = None if zern else ts.days_left()
         if left is not None and left < 5:
             self._ig_problem(f"erişim anahtarının süresi {max(0, left):.0f} gün içinde doluyor ve yenilenemedi. "
                              "Meta geliştirici panelinden yeni anahtar üretip GitHub'da <b>IG_ACCESS_TOKEN</b> değerini güncelle.")
-        cli = Instagram(ts.token, self._ig_cfg("instagram_api_version", None) or "v25.0",
-                        ig_id=str(self._ig_cfg("instagram_user_id", "") or "").strip())
+        if zern:
+            cli = Zernio(secret, account_id=str(self._ig_cfg("zernio_account_id", "") or "").strip())
+        else:
+            cli = Instagram(ts.token, self._ig_cfg("instagram_api_version", None) or "v25.0",
+                            ig_id=str(self._ig_cfg("instagram_user_id", "") or "").strip())
         fp = fingerprint(secret)
         if data.get("me_fp") != fp or not data.get("id"):
@@ -2277,5 +2289,9 @@
                     wait = float(self._ig_cfg("instagram_blocked_retry_hours", 3) or 3)
                     self.state["ig_pause"] = {"fp": fp, "until": iso(now_utc() + timedelta(hours=wait))}
-                    if blocked:   # Meta işletme hesabını kısıtladı: anahtar değil, hesap sorunu
+                    if zern:
+                        self._ig_problem(f"Zernio bağlantısı çalışmıyor ({esc(e)}). Zernio panelinde Instagram hesabının "
+                                         "bağlı olduğunu ve GitHub'daki <b>IG_ACCESS_TOKEN</b> değerinin Zernio API anahtarı "
+                                         f"olduğunu kontrol et. (Bot {wait:.0f} saatte bir yeniden dener.)")
+                    elif blocked:   # Meta işletme hesabını kısıtladı: anahtar değil, hesap sorunu
                         self._ig_problem(f"Meta uygulamanın erişimini engelledi ({esc(e)}). Bu genellikle işletme "
                                          "hesabı kısıtlandığında olur: Meta'nın e-postasındaki <b>Sorunu düzelt</b> ile "
@@ -2293,7 +2309,9 @@
                          "username": me.get("username", "")})
             data.pop("target", None)
+            data["provider"] = "zernio" if zern else "meta"
             if self.tg and self.chat_id:
-                self.notify(f"📸 Instagram bağlandı: <b>@{esc(data['username'])}</b>. Yayınlanan haberler buraya "
-                            f"carousel ve hikâye olarak paylaşılacak.", silent=True)
+                via = " (Zernio üzerinden)" if zern else ""
+                self.notify(f"📸 Instagram bağlandı{via}: <b>@{esc(data['username'])}</b>. Sosyal medya masasının seçtiği "
+                            f"haberler buraya gönderi ve hikâye olarak paylaşılacak.", silent=True)
         self._ig = cli
         return cli
@@ -2303,5 +2321,6 @@
         if d.get("target"):
             return [d["target"]]
-        first = [] if getattr(self._ig, "fb", False) else ["me"]   # Facebook Graph'ta "me" Instagram hesabı değildir
+        # Facebook Graph'ta ve Zernio'da "me" Instagram hesabı değildir
+        first = [] if getattr(self._ig, "fb", False) or getattr(self._ig, "kind", "") == "zernio" else ["me"]
         return [t for t in dict.fromkeys(first + [d.get("user_id"), d.get("id")]) if t]
 
@@ -2363,4 +2382,6 @@
         if not cli:
             return
+        if getattr(cli, "kind", "") == "zernio":   # aynı deneme tekrarlanırsa (zaman aşımı) Zernio ikinci kez paylaşmaz
+            cli.ref = f"{post['id']}-{it.get('tries', 0)}"
         try:
             if fmt == "post" and not it.get("media_id"):
@@ -2553,7 +2574,9 @@
         d = self.store.ig
         c = self.state.get("day_counts", {}).get(self.today(), {})
-        left = TokenStore(self.cfg.instagram_token, d).days_left()
+        zern = self.ig_provider == "zernio"
+        left = None if zern else TokenStore(self.cfg.instagram_token, d).days_left()
         lines = [f"📸 <b>Instagram</b> {'⏸ kapalı' if self.state.get('ig_off') else '▶️ açık'}"
-                 f"{' · @' + esc(d['username']) if d.get('username') else ''}",
+                 f"{' · @' + esc(d['username']) if d.get('username') and d.get('provider', 'meta') == self.ig_provider else ''}"
+                 f"{' · Zernio üzerinden' if zern else ''}",
                  f"Bugün: {c.get('instagram', 0)} gönderi, {c.get('instagram_story', 0)} hikâye · "
                  f"Sırada: {len(self.state.get('ig_queue') or [])}"]
@@ -2570,5 +2593,9 @@
             lines.append(f"⚠️ Son sorun ({when}): {esc(prob.get('text', ''))}")
         dg = self.state.get("ig_diag") or {}
-        if prob and dg:
+        if prob and dg and dg.get("kind") == "zernio":
+            accs = dg.get("accounts")
+            lines.append("🔎 Zernio'daki hesaplar: " + (esc(", ".join(accs)) or "yok" if isinstance(accs, list)
+                                                        else esc(str((accs or {}).get("error", "")))))
+        elif prob and dg:
             me = dg.get("me") or {}
             perms = dg.get("perms")
--- a/haberbot/instagram.py
+++ b/haberbot/instagram.py
@@ -10,4 +10,7 @@
 Meta'nın yeni uygulamalarda verdiği sistem kullanıcısı anahtarı ("EAA…" ile başlar, süresi dolmaz) graph.facebook.com
 üzerinden çalışır: hesap numarası ayarlardan (social.instagram_user_id) alınır ya da anahtarın eriştiği hesaplardan bulunur.
+
+IG_ACCESS_TOKEN'da Meta anahtarı yerine Zernio API anahtarı varsa paylaşım Zernio üzerinden yapılır (Zernio sınıfı):
+kendi Meta uygulamamız gerekmez, Instagram hesabı Zernio panelinde bağlanır.
 """
 from __future__ import annotations
@@ -284,4 +287,128 @@
 
 
+# ── Zernio: Meta onaylı uygulaması olan paylaşım servisi (kendi Meta uygulamamız gerekmez) ──
+ZERNIO_API = "https://zernio.com/api/v1"
+
+
+def is_meta_token(token: str) -> bool:
+    """Meta'nın kendi anahtarları "EAA" (Facebook) ya da "IG" (Instagram girişi) ile başlar; diğerleri Zernio anahtarıdır."""
+    return str(token or "").startswith(("EAA", "IG"))
+
+
+class Zernio:
+    """Zernio REST API üzerinden Instagram'a gönderi (carousel) ve hikâye. Görseller herkese açık adresten alınır.
+    Arayüz Instagram sınıfıyla aynıdır (me / carousel / story / diagnose); hedef, Zernio'daki hesap numarasıdır."""
+    kind = "zernio"
+    fb = False
+    ref = ""   # paylaşılan haberin kimliği + deneme sayısı (bot her paylaşımdan önce koyar): çift paylaşımı önler
+
+    def __init__(self, key: str, account_id: str = "", timeout: int = 90):
+        self.key = key
+        self.ig_id = str(account_id or "")
+        self.timeout = timeout
+        self.s = requests.Session()
+        self.s.headers.update({"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
+
+    def _clean(self, text: str) -> str:
+        return str(text).replace(self.key, "***") if self.key else str(text)
+
+    def _req(self, method: str, path: str, body: dict | None = None, params: dict | None = None,
+             idem: str = "") -> dict:
+        headers = {"Idempotency-Key": idem} if idem else {}
+        try:
+            r = self.s.request(method, f"{ZERNIO_API}/{path.lstrip('/')}", json=body, params=params,
+                               headers=headers, timeout=self.timeout)
+        except requests.RequestException as e:
+            raise InstagramError(self._clean(f"Zernio bağlantı hatası: {type(e).__name__}"), transient=True) from None
+        try:
+            j = r.json()
+        except ValueError:
+            j = {}
+        if r.status_code >= 400:
+            err = j.get("error") if isinstance(j.get("error"), dict) else j
+            msg = (err.get("message") if isinstance(err, dict) else None) or j.get("error") or f"HTTP {r.status_code}"
+            perr = (err.get("platformError") if isinstance(err, dict) else None) or j.get("platformError")
+            if perr:
+                msg = f"{msg} ({perr if isinstance(perr, str) else perr.get('message', perr)})"
+            code = {401: 190, 403: 200, 422: 200}.get(r.status_code)     # yetki sorunları: anahtar / hesap bağlantısı
+            raise InstagramError(self._clean(f"Zernio: {msg}"), code,
+                                 transient=r.status_code in (429, 500, 502, 503, 504))
+        return j if isinstance(j, dict) else {"data": j}
+
+    @staticmethod
+    def _items(j) -> list[dict]:
+        if isinstance(j, list):
+            return j
+        for k in ("accounts", "data", "items", "results"):
+            if isinstance(j.get(k), list):
+                return j[k]
+        return []
+
+    def accounts(self) -> list[dict]:
+        out = []
+        for a in self._items(self._req("GET", "accounts")):
+            if not isinstance(a, dict):
+                continue
+            out.append({"id": str(a.get("_id") or a.get("id") or a.get("accountId") or ""),
+                        "platform": str(a.get("platform") or "").lower(),
+                        "username": a.get("username") or a.get("handle") or a.get("name") or a.get("displayName") or "",
+                        "active": a.get("isActive", a.get("active", True)) is not False})
+        return out
+
+    def me(self) -> dict:
+        igs = [a for a in self.accounts() if a["platform"] == "instagram" and a["id"]]
+        if self.ig_id:
+            igs = [a for a in igs if a["id"] == self.ig_id] or igs
+        if not igs:
+            raise InstagramError("Zernio'da bağlı Instagram hesabı yok: Zernio panelinde Instagram'ı bağla", 200)
+        a = igs[0]
+        return {"id": a["id"], "user_id": a["id"], "username": a["username"]}
+
+    def _publish(self, body: dict, idem: str) -> tuple[str, str]:
+        j = self._req("POST", "posts", body, idem=idem)
+        post = j.get("post") if isinstance(j.get("post"), dict) else j
+        pid = str(post.get("_id") or post.get("id") or "")
+        plats = [p for p in post.get("platforms") or [] if isinstance(p, dict)] or [post]
+        p = plats[0]
+        st = str(p.get("status") or post.get("status") or "").lower()
+        if st in ("failed", "cancelled"):
+            perr = p.get("platformError") or p.get("error") or post.get("error") or st
+            raise InstagramError(self._clean(f"Zernio: Instagram paylaşımı başarısız ({perr})"))
+        return pid, str(p.get("platformPostUrl") or "")
+
+    def carousel(self, account_id: str, urls: list[str], caption: str) -> tuple[str, str]:
+        body = {"content": caption, "mediaItems": [{"type": "image", "url": u} for u in urls],
+                "platforms": [{"platform": "instagram", "accountId": account_id}], "publishNow": True}
+        if self.ref:
+            body["externalId"] = f"{self.ref}-post"
+        return self._publish(body, self._idem(self.ref or urls[0], "post"))
+
+    def story(self, account_id: str, url: str) -> str:
+        body = {"mediaItems": [{"type": "image", "url": url}],
+                "platforms": [{"platform": "instagram", "accountId": account_id,
+                               "platformSpecificData": {"contentType": "story"}}],
+                "publishNow": True}
+        if self.ref:
+            body["externalId"] = f"{self.ref}-story"
+        return self._publish(body, self._idem(self.ref or url, "story"))[0]
+
+    @staticmethod
+    def _idem(ref: str, kind: str) -> str:
+        """Aynı haberin aynı biçimi iki kez gönderilmesin (zaman aşımı sonrası yeniden denemede çift paylaşım olmaz)."""
+        import uuid
+        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"smarity:{ref}:{kind}"))
+
+    def diagnose(self) -> dict:
+        out: dict = {"kind": "zernio"}
+        try:
+            out["accounts"] = [f"{a['platform']}:{a['username'] or a['id']}" for a in self.accounts()]
+        except InstagramError as e:
+            out["accounts"] = {"error": str(e)[:200], "code": e.code}
+        return out
+
+    def refresh(self) -> tuple[str, int]:
+        raise InstagramError("Zernio anahtarı yenilenmez")
+
+
 def head_ok(url: str) -> int:
     """Görsel herkese açık mı? HTTP durum kodu (bağlantı hatasında 0)."""
--- a/tests/test_instagram.py
+++ b/tests/test_instagram.py
@@ -72,4 +72,5 @@
     raw["social"]["instagram_every_post"] = True
     raw["social"]["instagram_visual_check"] = False   # görsel kontrolü ayrı testte
+    raw["social"]["instagram_provider"] = "meta"      # test anahtarı Meta biçiminde değil; Zernio ayrı testte
     cfg = Config(raw=raw, root=tmp, site_url="https://example.github.io/smarity", mock=True,
                  instagram_token="SECRET-TOKEN", telegram_chat_id="1")
@@ -371,4 +372,106 @@
 
 
+class _Resp:
+    def __init__(self, code, body):
+        self.status_code, self._b = code, body
+
+    def json(self):
+        return self._b
+
+
+def test_zernio_client():
+    """Zernio: hesap bulunur; carousel ve hikâye doğru gövdeyle, tekrar anahtarıyla gönderilir; hatalar sınıflandırılır."""
+    cli = ig.Zernio("zk_SECRET", account_id="")
+    sent = []
+
+    def fake(method, url, json=None, params=None, headers=None, timeout=None):
+        sent.append((method, url, json, headers or {}))
+        if url.endswith("/accounts"):
+            return _Resp(200, {"accounts": [{"_id": "a1", "platform": "twitter", "username": "x"},
+                                            {"_id": "a2", "platform": "instagram", "username": "smarityco"}]})
+        if json and json["platforms"][0].get("platformSpecificData"):
+            return _Resp(201, {"post": {"_id": "p2", "status": "published",
+                                        "platforms": [{"platform": "instagram", "status": "published"}]}})
+        return _Resp(201, {"post": {"_id": "p1", "status": "published",
+                                    "platforms": [{"platform": "instagram", "status": "published",
+                                                   "platformPostUrl": "https://www.instagram.com/p/X/"}]}})
+    cli.s.request = fake
+    assert cli.me() == {"id": "a2", "user_id": "a2", "username": "smarityco"}
+    cli.ref = "h1-0"
+    assert cli.carousel("a2", ["https://s/1.jpg", "https://s/2.jpg", "https://s/3.jpg"], "Başlık") == \
+        ("p1", "https://www.instagram.com/p/X/")
+    body, hdr = sent[-1][2], sent[-1][3]
+    assert sent[-1][1].endswith("/api/v1/posts") and body["publishNow"] and body["content"] == "Başlık"
+    assert [m["url"] for m in body["mediaItems"]] == ["https://s/1.jpg", "https://s/2.jpg", "https://s/3.jpg"]
+    assert body["platforms"] == [{"platform": "instagram", "accountId": "a2"}] and hdr["Idempotency-Key"]
+    key1 = hdr["Idempotency-Key"]
+    assert cli.story("a2", "https://s/st.jpg") == "p2"
+    sb = sent[-1][2]
+    assert sb["platforms"][0]["platformSpecificData"] == {"contentType": "story"} and "content" not in sb
+    cli.ref = "h1-1"                                     # yeni deneme: yeni tekrar anahtarı
+    cli.carousel("a2", ["https://s/1.jpg"], "x")
+    assert sent[-1][3]["Idempotency-Key"] != key1
+    # hatalar: başarısız paylaşım, yetki, geçici
+    cli.s.request = lambda *a, **k: _Resp(207, {"post": {"_id": "p3", "platforms": [
+        {"status": "failed", "platformError": "Media download failed"}]}})
+    try:
+        cli.carousel("a2", ["https://s/1.jpg"], "x")
+        raise AssertionError("başarısız paylaşım hata vermeli")
+    except ig.InstagramError as e:
+        assert "Media download failed" in str(e) and not e.auth
+    cli.s.request = lambda *a, **k: _Resp(401, {"error": {"message": "Invalid API key zk_SECRET", "type": "authentication_error"}})
+    try:
+        cli.me()
+        raise AssertionError
+    except ig.InstagramError as e:
+        assert e.auth and "zk_SECRET" not in str(e)
+    cli.s.request = lambda *a, **k: _Resp(429, {"error": {"message": "Too many"}})
+    try:
+        cli.story("a2", "https://s/st.jpg")
+        raise AssertionError
+    except ig.InstagramError as e:
+        assert e.transient and not e.auth
+
+
+class FakeZernio(FakeIG):
+    kind, fb, ref = "zernio", False, ""
+    refs = []
+
+    def __init__(self, key, account_id="", timeout=90):
+        self.key = key
+
+    def me(self):
+        return {"id": "z9", "user_id": "z9", "username": "smarityco"}
+
+    def carousel(self, target, urls, caption):
+        FakeZernio.refs.append(self.ref)
+        FakeIG.calls.append(("carousel", target, tuple(urls), caption))
+        return "ZP1", "https://www.instagram.com/p/z/"
+
+
+def test_zernio_provider_in_app():
+    """IG_ACCESS_TOKEN'da Zernio anahtarı varsa bot paylaşımı Zernio üzerinden yapar; Meta anahtarıysa Meta'dan."""
+    FakeIG.calls, FakeZernio.refs = [], []
+    appmod.Instagram, appmod.Zernio, appmod.head_ok = FakeIG, FakeZernio, (lambda url: 200)
+    with tempfile.TemporaryDirectory() as t:
+        a = _app(Path(t))
+        a.cfg.raw["social"]["instagram_provider"] = "auto"
+        a.cfg.instagram_token = "EAA-meta"
+        assert a.ig_provider == "meta"
+        a.cfg.instagram_token = "zk_live_123"
+        assert a.ig_provider == "zernio"
+        post = _pub(1, 1, 9)
+        a.store.save_post(post)
+        a.ig_enqueue(post)
+        a.ig_tick()
+        assert a.state["ig_queue"] == [] and a.state["ig_done"][-1]["permalink"] == "https://www.instagram.com/p/z/"
+        assert [c[0] for c in FakeIG.calls] == ["carousel", "story"] and FakeIG.calls[0][1] == "z9"
+        assert FakeZernio.refs == ["s1-0"] and a.store.ig["provider"] == "zernio"
+        st = a.instagram_status()
+        assert "Zernio üzerinden" in st and "@smarityco" in st
+        out = (Path(t) / "data" / "_mock" / "outbox.jsonl").read_text(encoding="utf-8")
+        assert "Zernio üzerinden" in out
+
+
 def test_missing_card_triggers_rebuild():
     appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 404)
@@@SM@@@ SHA
be789ad66f19b966910b46c5d1b7a7ee5d45632f73f8def026d15f711ad74ef7 config.yaml
e8882b8c8527122bea55225a4466c5ee5e0d7a1788dfd58cc9e08ade0a379544 haberbot/app.py
cdc7b1460cf8f6db6dec389bcb60e22757825028fb5d4c0a2fcc77850fba3ec8 haberbot/instagram.py
ff7ed6606d61c63e29f6491bbfabd6c774af80e2f04d5ea76cc64c84f01aa207 tests/test_instagram.py
