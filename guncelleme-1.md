SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -73,4 +73,10 @@
   global_min_approval: 0.85      # Son kararlarda genel onay oranı bunun altındaysa otomatik yayın durur
   auto_min_importance: 7         # Otomatik yayın için en düşük önem puanı
+  # Doğrudan yayınlanan gruplar: geçmiş kararlarında en çok onayladığın türler. Uyarı işareti olan haber yine sorulur.
+  trusted_groups:
+    - name: "en az 2 kaynaklı otomotiv / süper zeka haberi"
+      categories: [otomotiv, super-zeka]
+      min_sources: 2
+  trusted_pause_removals: 2      # Bir gruptan son 7 günde bu kadar otomatik haberi kaldırırsan o grup yeniden onaya döner
 
 images:
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -933,4 +933,6 @@
         if d.get("focus_keyword") and kind in ("pending", "auto"):
             lines.append(f"🔎 Google: <i>{esc(d['focus_keyword'])}</i>")
+        if kind == "auto" and d.get("auto_group"):
+            lines.append(f"🤖 Otomatik yayın nedeni: {esc(d['auto_group'])}. Beğenmezsen Kaldır'a bas.")
         if d.get("flags"):
             fl = ", ".join(FLAG_LABELS.get(f, f) for f in d["flags"])
@@ -1223,4 +1225,6 @@
             weight = 2 if d.get("publish_mode") == "auto" else 1
             policy.record(self.stats, d, ok=False, weight=weight)
+            if d.get("publish_mode") == "auto" and d.get("auto_group"):
+                policy.record_group_removal(self.stats, d["auto_group"])   # sık kaldırılırsa grup yeniden onaya döner
             st.bump(self.today(), "removed")
             st.archive_draft(d, "removed")
--- a/haberbot/policy.py
+++ b/haberbot/policy.py
@@ -7,9 +7,12 @@
   Bir kaynak güvenilir sayılır: en az X karar + en az %Y onay.
   Otomatik yayınlanan bir haberi 'Kaldır' dersen o kaynak 2 ret puanı alır.
+  Güvenilir gruplar (ayarlarda autonomy.trusted_groups): en çok onayladığın türler (ör. en az 2 kaynaklı otomotiv ve
+  süper zeka haberleri) uyarı işareti yoksa doğrudan yayınlanır. Bir gruptan son 7 günde otomatik yayınlanan haberleri
+  birkaç kez kaldırırsan o grup kendiliğinden yeniden onayına döner.
 """
 from __future__ import annotations
 
 from .config import Config
-from .util import iso, now_utc
+from .util import hours_since, iso, now_utc
 
 MODES = {"manuel": "Manuel", "ogrenen": "Öğrenen", "tam": "Tam otonom"}
@@ -38,4 +41,30 @@
 
 
+def trusted_group(cfg: Config, draft: dict) -> str | None:
+    """Haber, doğrudan yayınlanan güvenilir gruplardan birinde mi? (kategori + en az N farklı kaynak)"""
+    names = {s.get("name") for s in draft.get("sources") or [] if s.get("name")}
+    for g in cfg.get("autonomy", "trusted_groups", None) or []:
+        cats = g.get("categories") or []
+        if cats and draft.get("category") not in cats:
+            continue
+        if len(names) < int(g.get("min_sources", 1) or 1):
+            continue
+        return str(g.get("name") or "güvenilir grup")
+    return None
+
+
+def group_paused(cfg: Config, stats: dict, name: str) -> bool:
+    """Bu gruptan son 7 günde otomatik yayınlanıp kaldırdığın haber sayısı sınıra ulaştıysa grup yeniden onaya döner."""
+    lim = int(cfg.get("autonomy", "trusted_pause_removals", 2) or 0)
+    recent = [t for t in (stats.get("group_removals") or {}).get(name, []) if hours_since(t) <= 24 * 7]
+    return bool(lim) and len(recent) >= lim
+
+
+def record_group_removal(stats: dict, name: str) -> None:
+    lst = stats.setdefault("group_removals", {}).setdefault(name, [])
+    lst.append(iso(now_utc()))
+    del lst[:-20]
+
+
 def decide(cfg: Config, state: dict, stats: dict, draft: dict) -> tuple[str, str]:
     """('auto' | 'ask', gerekçe)"""
@@ -45,4 +74,10 @@
     if draft.get("flags"):
         return "ask", "Uyarı işareti var"
+    group = trusted_group(cfg, draft)
+    if (group and draft.get("confidence") in ("yuksek", "orta")
+            and draft.get("importance", 0) >= cfg.get("autonomy", "auto_min_importance", 6)):
+        if not group_paused(cfg, stats, group):
+            draft["auto_group"] = group
+            return "auto", f"Güvenilir grup: {group}"
     if draft.get("confidence") != "yuksek":
         return "ask", "Güven seviyesi yüksek değil"
--- a/tests/test_core.py
+++ b/tests/test_core.py
@@ -34,4 +34,26 @@
         policy.record(stats, {"id": f"r{i}", "source_keys": ["OpenAI"]}, ok=False)
     assert policy.decide(CFG, {}, stats, GOOD)[0] == "ask"
+
+
+def test_trusted_groups_publish_directly():
+    cfg = Config(raw={"autonomy": {**CFG.raw["autonomy"], "auto_min_importance": 7, "trusted_pause_removals": 2,
+                                   "trusted_groups": [{"name": "oto/ai", "categories": ["otomotiv", "super-zeka"],
+                                                       "min_sources": 2}]}})
+    stats = {"sources": {}, "decisions": [{"ok": False, "manual": True}] * 30}      # genel onay oranı düşük
+    two = [{"name": "Webtekno", "url": "a"}, {"name": "ShiftDelete.Net", "url": "b"}]
+    car = {"id": "c", "flags": [], "confidence": "orta", "importance": 8, "category": "otomotiv", "sources": two}
+    assert policy.decide(cfg, {}, stats, car) == ("auto", "Güvenilir grup: oto/ai") and car["auto_group"] == "oto/ai"
+    assert policy.decide(cfg, {}, stats, {**car, "sources": two[:1]})[0] == "ask"               # tek kaynak
+    assert policy.decide(cfg, {}, stats, {**car, "sources": two * 2})[0] == "auto"              # aynı kaynaklar tekrar sayılmaz
+    assert policy.decide(cfg, {}, stats, {**car, "sources": [two[0], two[0]]})[0] == "ask"
+    assert policy.decide(cfg, {}, stats, {**car, "category": "teknoloji"})[0] == "ask"          # grup dışı kategori
+    assert policy.decide(cfg, {}, stats, {**car, "flags": ["iddia"]})[0] == "ask"               # uyarı işareti
+    assert policy.decide(cfg, {}, stats, {**car, "confidence": "dusuk"})[0] == "ask"
+    assert policy.decide(cfg, {}, stats, {**car, "importance": 6})[0] == "ask"
+    assert policy.decide(cfg, {"mode_override": "manuel"}, stats, car)[0] == "ask"
+    policy.record_group_removal(stats, "oto/ai")
+    assert policy.decide(cfg, {}, stats, {**car})[0] == "auto"                                 # bir kaldırma: sürüyor
+    policy.record_group_removal(stats, "oto/ai")
+    assert policy.decide(cfg, {}, stats, {**car})[0] == "ask"                                  # iki kaldırma: onaya döner
 
 
@@@SM@@@ SHA
82d1b79649fc01bfd619ce139f7c1616cf27acbbadea9d804244d7dff9f94cb1 config.yaml
73283d45b5faee10522556ceb4da57d03f5ea830b1f03c89cc4b31475c60ee35 haberbot/app.py
b41ab1d6bab4c056c65ecdd1a30cdeaca5bb69293e3a99d6495223fe1c3352e9 haberbot/policy.py
d34fd2ba1a19722d32a08b07c7df7c6e53ef3ec92809d5f22645539d58809921 tests/test_core.py
