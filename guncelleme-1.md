SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -24,4 +24,5 @@
   # Telegram'daki "⭐ Manşete al" ve "🙈 Ana sayfada gösterme" düğmeleriyle tek tek yönetebilirsin.
   featured_count: 10       # manşetteki (kaydırmalı) haber sayısı
+  max_per_category: 3      # manşette bir kategoriden en fazla bu kadar haber ("Öne çıkanlar"da en fazla 2); 0 = sınırsız
 
 seo:
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -504,5 +504,7 @@
                 continue
             dup = (s.get("duplicate_of") or "").removeprefix("s:")
-            if dup in published:            # masa "aynı haber" dedi: yeni haber değil, olsa olsa güncelleme
+            # masa "aynı haber" dedi: yeni haber değil, olsa olsa güncelleme. Yönetmen 9+ ile "yeni haber" dediyse
+            # (ör. ön izlemesi yayınlanmış bir etkinlikte ürünlerin resmen tanıtılması) yönetmenin kararı geçerli
+            if dup in published and mr < 9:
                 ok = mr >= min_score and dup not in round_targets and (dup not in refreshed or mr >= 9)
                 x["action"], x["target"] = ("update", dup) if ok else ("skip", dup)
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -84,5 +84,7 @@
    its status, including rejected and expired), write that story id (e.g. "s:ab12cd34ef" or "q:3"); otherwise "".
    Follow-ups count as the same story: local availability or price of an already covered product, hands-on or review of it,
-   reactions, analysis, more details about the same announcement.
+   reactions, analysis, more details about the same announcement. But the real thing is never a duplicate of its preview:
+   an official unveiling / launch (products announced at an event, a release, a signed deal) is a NEW story even if a
+   teaser, leak, rumor or "what to expect" story about it is in RECENT STORIES.
 4. importance (integer 1–10). THE TEST: would MANY ordinary Turkish readers who like technology want to click this today
    and tell a friend about it? Not "would a specialist find it interesting" — most items fail this test. Be strict.
@@ -230,4 +232,9 @@
   in the next round — holding is not rejecting).
 - Duplicates among candidates (same product or event): publish at most one of them.
+- The real event beats its preview: a COVERED story that previews, teases or leaks a launch or event never makes the actual
+  announcement a duplicate or an "update". When a household-name company officially unveils products (an Apple event,
+  Samsung Unpacked, a new iPhone, PlayStation or Pixel…), the launch is a NEW story ("publish", must_read 9–10); if several
+  major products are announced, publish the most important ones as separate stories. Live blogs, "how to watch" and
+  "what to expect" pieces are still skipped.
 - target: the covered story id for "update" (e.g. "ab12cd34ef"), the most similar covered id for a duplicate "skip", else "".
 - big_brand: true if the story is about a household-name company, brand, product or service that most people in Türkiye
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -353,7 +353,9 @@
 
     @staticmethod
-    def _home(posts: list[dict], n_feat: int) -> dict:
+    def _home(posts: list[dict], n_feat: int, max_per_cat: int = 3) -> dict:
         """Ana sayfa seçkisi. Her onaylanan haber ana sayfaya çıkmaz: en dikkat çekiciler (ilgi × tazelik) seçilir,
-        bir haber sayfada yalnızca bir kez görünür. Tüm haberler kategori ve "Tüm haberler" sayfalarında durur."""
+        bir haber sayfada yalnızca bir kez görünür. Tüm haberler kategori ve "Tüm haberler" sayfalarında durur.
+        Vitrin dengeli olur: manşette bir kategoriden en fazla max_per_cat, "Öne çıkanlar"da en fazla 2 haber
+        (ör. otomobil fuarı günü manşet otomobil haberiyle dolmaz)."""
         visible = [p for p in posts if p["hot"] >= 0]
         ranked = sorted(visible, key=lambda p: -p["hot"])
@@ -362,19 +364,26 @@
         used: set[str] = set()
 
-        def pick(pool: list[dict], n: int, shown: set[str]) -> list[dict]:
-            out = []
-            for strict in (True, False):
+        def pick(pool: list[dict], n: int, shown: set[str], cap: int) -> list[dict]:
+            out: list[dict] = []
+            per_cat: Counter = Counter()
+            # 2: şirket + kategori sınırı · 1: yalnızca şirket sınırı · 0: yer kalırsa sınırsız (az haberli günler)
+            for level in (2, 1, 0):
                 for p in pool:
                     if len(out) >= n:
                         return out
-                    if p["id"] in shown or p in out or (strict and p["ekey"] and p["ekey"] in used):
+                    if p["id"] in shown or p in out:
+                        continue
+                    if level >= 1 and p["ekey"] and p["ekey"] in used:
+                        continue
+                    if level == 2 and cap and p["hot"] < 100 and per_cat[p.get("category")] >= cap:
                         continue
                     out.append(p)
+                    per_cat[p.get("category")] += 1
                     if p["ekey"]:
                         used.add(p["ekey"])
             return out
-        featured = pick(fresh + [p for p in ranked if p not in fresh], n_feat, set())
+        featured = pick(fresh + [p for p in ranked if p not in fresh], n_feat, set(), max_per_cat)
         shown = {p["id"] for p in featured}
-        top = pick(ranked, 6, shown)
+        top = pick(ranked, 6, shown, min(2, max_per_cat) if max_per_cat else 0)
         shown |= {p["id"] for p in top}
         latest = [p for p in visible if p["id"] not in shown and hours_since(p.get("published_at")) <= 48][:6]
@@ -472,5 +481,5 @@
         # ana sayfa: seçki (manşet, öne çıkanlar, son dakika, kaçırmış olabilirsin, kategori şeritleri)
         n_feat = int((cfg.raw.get("home") or {}).get("featured_count") or seo.get("featured_count", 5) or 5)
-        home = self._home(posts, n_feat)
+        home = self._home(posts, n_feat, int((cfg.raw.get("home") or {}).get("max_per_category", 3) or 0))
         featured = home["featured"]
         for p in featured:   # manşette tek, sakin bir zemin: görselden renk alınmaz (her slaytta başka renk olmasın)
--- a/tests/test_editor.py
+++ b/tests/test_editor.py
@@ -38,4 +38,9 @@
         assert acts[2] == "hold" and acts[3] == "skip"
         assert acts[5] == "update" and out[5]["target"] == "p01"
+        # ön izlemesi yayınlanmış etkinlikte ürünler resmen tanıtıldı: yönetmen 9+ "yeni haber" dediyse yeni haber olur
+        launch = [_q("Apple unveils new HomePod at Welcome Home event", 9, ["Apple"], dup="s:p01")]
+        out = a._guard(launch, {0: {"action": "publish", "target": "", "must_read": 9, "reason": ""}}, slots=3,
+                       min_score=7, covered=a._covered(48))
+        assert out[0]["action"] == "publish"
         # ayarlardan şirket sınırı açılırsa: aynı şirketten 24 saatte ikinci haber (9 altı) elenir
         cfg.raw.setdefault("editorial", {})["max_per_company_per_day"] = 1
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -110,4 +110,25 @@
 
 
+def test_showcase_is_balanced_across_categories():
+    with _App() as (cfg, a):
+        # otomobil fuarı günü: en dikkat çekici 8 haber otomotiv, Apple etkinliği haberi daha geride
+        for i in range(8):
+            a.store.save_post(_post(i, hours=i * 0.5, appeal=9, cat="otomotiv", tags=[f"Marka{i}"], entities=[f"Marka{i}"]))
+        a.store.save_post(_post(20, hours=20, appeal=8, cat="teknoloji", tags=["Apple"], entities=["Apple"]))
+        for i, c in enumerate(["super-zeka", "gaming", "inovasyon", "girisimcilik", "teknoloji", "super-zeka"] * 2):
+            a.store.save_post(_post(30 + i, hours=6 + i, appeal=6, cat=c, tags=[f"Firma{i}"], entities=[f"Firma{i}"]))
+        SiteBuilder(cfg).build()
+        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
+        slider = re.findall(r'class="slide[^"]*"[^>]*data-id="(p\d+)"', home)
+        cats = [a.store.load_post(i)["category"] for i in slider]
+        assert len(slider) == 10 and cats.count("otomotiv") == 3 and "p20" in slider
+        top = re.search(r'data-top>(.*?)</div>\s*</section>', home, re.S).group(1)
+        top_cats = [a.store.load_post(i)["category"] for i in re.findall(r'data-id="(p\d+)"', top)]
+        assert all(top_cats.count(c) <= 2 for c in set(top_cats))
+        # az haberli günde boş kalmaz: sınır yalnızca yer varsa uygulanır
+        assert len(SiteBuilder._home([{**p, "hot": 1.0, "ekey": ""} for p in
+                                      [{"id": f"x{i}", "category": "otomotiv", "published_at": iso(now_utc())}
+                                       for i in range(5)]], 10)["featured"]) == 5
+
 def test_pin_and_hide_buttons():
     with _App() as (cfg, a):
@@@SM@@@ SHA
2b18439d84ca3a1ab266481e3e06353f4b0af9eb8fab14e9b065d0b9bc99e96b config.yaml
adbc30a637b3f8f8f41345bb1ced3b13befd30029d7dea28fcec0fde26046ad9 haberbot/app.py
7b1ea4d0d221258979aae73a6c1378b81580d08ffcf2aadf2a210d889de03737 haberbot/prompts.py
f08912fa12ca0ce79159060ee3e989fe28e5c06d72f3cce87399a56bb8d15123 haberbot/site.py
05a13712f7036fb59f422792a83c26930162d796533e4e7cd1937a6113c578b3 tests/test_editor.py
3d5342d26c22356d91bf787c55e96b84097669ae4b4f4e6b3b6c5004fd8c499b tests/test_home.py
