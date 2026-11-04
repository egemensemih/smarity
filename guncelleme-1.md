SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -51,5 +51,5 @@
     ("manset", "Manşeti yönet: haberi manşete al / çıkar"),
     ("secki", "Yayın yönetmeninin son kararları (neden seçildi / elendi)"),
-    ("instagram", "Instagram paylaşımları: durum / kapat / ac"),
+    ("instagram", "Instagram paylaşımları: durum / kapat / ac / dene"),
     ("yardim", "Nasıl kullanılır"),
 ]
@@ -1678,4 +1678,6 @@
                 self.state["ig_off"] = False
                 self.notify("▶️ Instagram paylaşımları açık.", silent=True)
+            elif arg in ("dene", "test", "son"):
+                self.notify(self.ig_try_latest(), silent=True)
             else:
                 self.notify(self.instagram_status(), silent=True)
@@ -2263,4 +2265,18 @@
         return n
 
+    def ig_try_latest(self) -> str:
+        """/instagram dene: henüz paylaşılmamış en yeni haberi Instagram sırasına al (bağlantıyı denemek için)."""
+        if not self.cfg.instagram_token:
+            return self.instagram_status()
+        done = {x.get("id") for x in self.state.get("ig_done") or []}
+        queued = {x.get("id") for x in self.state.get("ig_queue") or []}
+        post = next((p for p in self.store.posts() if p["id"] not in done | queued), None)
+        if not post:
+            return "📸 Paylaşılmamış haber yok."
+        self.ig_enqueue(post)
+        note = " Instagram şu an kapalı: <code>/instagram ac</code>" if self.state.get("ig_off") else \
+            " Görseller sitede yayınlanınca (5–10 dk) paylaşılır."
+        return f"📸 Deneme için sıraya alındı: <b>{esc(post['title'])}</b>.{note}"
+
     def instagram_status(self) -> str:
         if not self.cfg.instagram_token:
@@ -2281,5 +2297,6 @@
             if x.get("permalink"):
                 lines.append(f'• <a href="{esc(x["permalink"])}">{esc(clip(p.get("title", x["id"]), 70))}</a>')
-        lines.append("Durdur: <code>/instagram kapat</code> · Aç: <code>/instagram ac</code>")
+        lines.append("Durdur: <code>/instagram kapat</code> · Aç: <code>/instagram ac</code> · "
+                     "Son haberi şimdi paylaş: <code>/instagram dene</code>")
         return "\n".join(lines)
 
--- a/tests/test_instagram.py
+++ b/tests/test_instagram.py
@@ -2,4 +2,5 @@
 import sys
 import tempfile
+from datetime import timedelta
 from pathlib import Path
 
@@ -144,4 +145,20 @@
 
 
+def test_try_latest_command():
+    FakeIG.calls = []
+    appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 200)
+    with tempfile.TemporaryDirectory() as t:
+        a = _app(Path(t))
+        for i, h in ((1, 5), (2, 1)):
+            a.store.save_post({"id": f"p{i}", "slug": f"haber-{i}", "title": f"Haber {i}", "summary": "Özet.",
+                               "category": "teknoloji", "tags": [], "body": "Metin.", "sources": [{"name": "A", "url": "https://a"}],
+                               "published_at": iso(now_utc() - timedelta(hours=h))})
+        assert "Haber 2" in a.ig_try_latest()                       # en yeni haber
+        assert [x["id"] for x in a.state["ig_queue"]] == ["p2"]
+        assert "Haber 1" in a.ig_try_latest()                       # sıradaki atlanır, bir öncekine geçer
+        a.cfg.instagram_token = ""
+        assert "bağlı değil" in a.ig_try_latest()
+
+
 def test_missing_card_triggers_rebuild():
     appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 404)
@@@SM@@@ SHA
ae238321132b36ffac368b0559fc1c380c054cbbcd415f7077856cb144926f4d haberbot/app.py
7d1ab855e564d6c7c48e84f57cc335fc0067c5bbc8256c5534fa581989ffe0cf tests/test_instagram.py
