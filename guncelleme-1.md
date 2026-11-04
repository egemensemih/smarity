SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -2263,4 +2263,9 @@
                 me = cli.me()
             except InstagramError as e:
+                if hours_since((self.state.get("ig_diag") or {}).get("at")) >= 1:   # anahtarın ne gördüğünü kaydet
+                    try:
+                        self.state["ig_diag"] = {**cli.diagnose(), "at": iso(now_utc())}
+                    except Exception as de:  # noqa: BLE001
+                        log.warning("Instagram teşhisi yapılamadı: %s", de)
                 if e.auth:
                     self._ig_problem(f"erişim anahtarı çalışmıyor ({esc(e)}). Yeni anahtar üretip GitHub'da "
@@ -2374,4 +2379,5 @@
         q.remove(it)
         self.state.pop("ig_problem", None)
+        self.state.pop("ig_diag", None)
         done = self.state.setdefault("ig_done", [])
         done.append({"id": post["id"], "at": iso(now_utc()), "permalink": it.get("permalink", ""),
@@ -2547,4 +2553,16 @@
             when = local(prob["at"], self.cfg.tz).strftime("%d.%m %H:%M")
             lines.append(f"⚠️ Son sorun ({when}): {esc(prob.get('text', ''))}")
+        dg = self.state.get("ig_diag") or {}
+        if prob and dg:
+            me = dg.get("me") or {}
+            perms = dg.get("perms")
+            pages = dg.get("pages")
+            lines.append("🔎 Anahtar: " + ("Facebook" if dg.get("kind") == "facebook" else "Instagram") +
+                         (f" · {esc(me.get('name') or me.get('username') or '')}" if isinstance(me, dict) and not me.get("error") else ""))
+            if isinstance(perms, list):
+                lines.append("İzinler: " + (esc(", ".join(perms)) or "yok"))
+            if isinstance(pages, list):
+                lines.append("Erişilen sayfalar: " + (esc(", ".join(f"{p['name']} → {p['ig'] or 'Instagram bağlı değil'}"
+                                                                   for p in pages)) or "yok"))
         waiting = [x for x in self.state.get("ig_queue") or [] if not x.get("vok")]
         if waiting and self._ig_cfg("instagram_visual_check", True):
--- a/haberbot/instagram.py
+++ b/haberbot/instagram.py
@@ -155,4 +155,28 @@
         return {"id": str(j.get("id") or ig_id), "user_id": str(j.get("id") or ig_id), "username": j.get("username", "")}
 
+    def diagnose(self) -> dict:
+        """Anahtarın ne gördüğü (anahtarın kendisi yazılmaz): kimlik, verilen izinler, erişilen sayfalar ve bağlı
+        Instagram hesapları. Bağlantı kurulamadığında sorunun anahtar mı, izin mi, hesap ataması mı olduğunu gösterir."""
+        out: dict = {"kind": "facebook" if self.fb else "instagram"}
+
+        def safe(key, fn):
+            try:
+                out[key] = fn()
+            except InstagramError as e:
+                out[key] = {"error": str(e)[:200], "code": e.code, "subcode": e.subcode}
+
+        if self.fb:
+            safe("me", lambda: {k: v for k, v in self._req("GET", "me", fields="id,name").items() if k in ("id", "name")})
+            safe("perms", lambda: sorted(x["permission"] for x in self._req("GET", "me/permissions").get("data") or []
+                                         if x.get("status") == "granted"))
+            safe("pages", lambda: [{"name": p.get("name", ""),
+                                    "ig": (p.get("instagram_business_account") or {}).get("username")
+                                    or (p.get("instagram_business_account") or {}).get("id") or ""}
+                                   for p in self._req("GET", "me/accounts",
+                                                      fields="name,instagram_business_account{id,username}").get("data") or []])
+        else:
+            safe("me", lambda: self._req("GET", "me", fields="user_id,username"))
+        return out
+
     def container(self, ig_id: str, **params) -> str:
         return self._req("POST", f"{ig_id}/media", **params)["id"]
--- a/tests/test_instagram.py
+++ b/tests/test_instagram.py
@@ -315,4 +315,15 @@
     except ig.InstagramError as e:
         assert e.code == 190
+    # teşhis: anahtarın kimliği, izinleri ve eriştiği sayfalar (anahtarın kendisi yazılmaz)
+    cli3 = ig.Instagram("EAAsecret", ig_id="999")
+    answers = {"me": {"id": "5", "name": "Smarity Bot"},
+               "me/permissions": {"data": [{"permission": "instagram_basic", "status": "granted"},
+                                           {"permission": "pages_show_list", "status": "declined"}]},
+               "me/accounts": {"data": [{"name": "Smarity", "instagram_business_account": {"id": "1", "username": "smarityco"}},
+                                        {"name": "Boş sayfa"}]}}
+    cli3._req = lambda method, path, **params: answers[path]
+    dg = cli3.diagnose()
+    assert dg["perms"] == ["instagram_basic"] and dg["pages"][0]["ig"] == "smarityco" and dg["pages"][1]["ig"] == ""
+    assert "EAAsecret" not in str(dg)
     # sorun /instagram durumunda görünür
     with tempfile.TemporaryDirectory() as t:
@@ -320,4 +331,7 @@
         a._ig_problem("erişim anahtarı çalışmıyor (Invalid token)")
         assert "Son sorun" in a.instagram_status() and "Invalid token" in a.instagram_status()
+        a.state["ig_diag"] = {**dg, "at": iso(now_utc())}
+        st = a.instagram_status()
+        assert "İzinler: instagram_basic" in st and "Boş sayfa → Instagram bağlı değil" in st
 
 
@@@SM@@@ SHA
a72101d52b3ba868bcdad1475a8b9991674122f94491db83a567cac644b599a0 haberbot/app.py
b563ec1bc7cb770914419b36d3f60d5b140bc8892d6ffb566c7d312c042394c7 haberbot/instagram.py
820ff30e823a36fd9bccf4d23d95a10df7eb0d4ad3f7ac75f196505c3f03dd0c tests/test_instagram.py
