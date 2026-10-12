SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -78,4 +78,8 @@
       categories: [otomotiv, super-zeka]
       min_sources: 2
+    - name: "en az 3 farklı kaynakta çıkan haber"
+      min_sources: 3
+  # Bu markaların haberleri hiçbir zaman otomatik yayınlanmaz, her zaman onaya gelir
+  never_auto: [Vivo, Oppo, Realme, Tecno, Infinix, iQOO, Nubia, ZTE, Meizu, itel, Poco, Redmi]
   trusted_pause_removals: 2      # Bir gruptan son 7 günde bu kadar otomatik haberi kaldırırsan o grup yeniden onaya döner
 
--- a/haberbot/policy.py
+++ b/haberbot/policy.py
@@ -12,4 +12,6 @@
 """
 from __future__ import annotations
+
+import re
 
 from .config import Config
@@ -54,4 +56,17 @@
 
 
+def never_auto_brand(cfg: Config, draft: dict) -> str | None:
+    """Otomatik yayınlanmayan markalar (ör. Vivo, Oppo): bu haberler her zaman onaya gelir."""
+    names = [str(n).strip() for n in cfg.get("autonomy", "never_auto", None) or [] if str(n).strip()]
+    if not names:
+        return None
+    text = " ".join([draft.get("title") or "", draft.get("summary") or "",
+                     *[str(x) for x in (draft.get("entities") or []) + (draft.get("tags") or [])]])
+    for n in names:
+        if re.search(rf"(?<![\w]){re.escape(n)}(?![\w])", text, re.I):
+            return n
+    return None
+
+
 def group_paused(cfg: Config, stats: dict, name: str) -> bool:
     """Bu gruptan son 7 günde otomatik yayınlanıp kaldırdığın haber sayısı sınıra ulaştıysa grup yeniden onaya döner."""
@@ -75,4 +90,6 @@
         return "ask", "Uyarı işareti var"
     group = trusted_group(cfg, draft)
+    if group and never_auto_brand(cfg, draft):
+        group = None                                   # bu marka her zaman onaya gelir
     if (group and draft.get("confidence") in ("yuksek", "orta")
             and draft.get("importance", 0) >= cfg.get("autonomy", "auto_min_importance", 6)):
--- a/tests/test_core.py
+++ b/tests/test_core.py
@@ -56,4 +56,24 @@
     policy.record_group_removal(stats, "oto/ai")
     assert policy.decide(cfg, {}, stats, {**car})[0] == "ask"                                  # iki kaldırma: onaya döner
+
+
+def test_three_sources_any_category_but_not_some_brands():
+    cfg = Config(raw={"autonomy": {**CFG.raw["autonomy"], "auto_min_importance": 7,
+                                   "trusted_groups": [{"name": "oto/ai", "categories": ["otomotiv", "super-zeka"],
+                                                       "min_sources": 2},
+                                                      {"name": "3 kaynak", "min_sources": 3}],
+                                   "never_auto": ["Vivo", "Oppo", "iQOO"]}})
+    stats = {"sources": {}, "decisions": [{"ok": False, "manual": True}] * 30}
+    three = [{"name": n, "url": n} for n in ("Webtekno", "LOG", "The Verge")]
+    phone = {"id": "p", "flags": [], "confidence": "yuksek", "importance": 8, "category": "teknoloji", "sources": three,
+             "title": "Samsung Galaxy S27 tanıtıldı", "tags": ["Samsung"]}
+    assert policy.decide(cfg, {}, stats, phone) == ("auto", "Güvenilir grup: 3 kaynak")
+    assert policy.decide(cfg, {}, stats, {**phone, "sources": three[:2]})[0] == "ask"           # teknolojide 2 kaynak yetmez
+    assert policy.decide(cfg, {}, stats, {**phone, "category": "gaming"})[0] == "auto"
+    vivo = {**phone, "title": "Vivo'nun yeni telefonu V80 Lite Türkiye'de", "tags": ["akıllı telefon"]}
+    assert policy.decide(cfg, {}, stats, vivo)[0] == "ask"                                     # bu marka onaya gelir
+    assert policy.decide(cfg, {}, stats, {**phone, "tags": ["iQOO"]})[0] == "ask"
+    assert policy.decide(cfg, {}, stats, {**phone, "title": "Vivos adlı yeni uygulama çıktı"})[0] == "auto"
+    assert policy.decide(cfg, {}, stats, {**vivo, "category": "otomotiv"})[0] == "ask"
 
 
@@@SM@@@ SHA
e932a2a72f1748c4951948e5431a4d0d3e631750ab5781df1384a42ddbaf468c config.yaml
882ff702c717ae926e58c2b1331f4b0cf294debd4d9dbd7adbd01adee47ff2e4 haberbot/policy.py
310593d2559e1fd5591b10fe0ef79661105b6f95ae04cbe5e71790273472df6a tests/test_core.py
