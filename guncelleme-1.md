SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -17,5 +17,5 @@
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "11"
+ASSET_V = "12"
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
 H2_RE = re.compile(r"<h[1-3]>(.*?)</h[1-3]>", re.S)
--- a/static/style.css
+++ b/static/style.css
@@ -99,6 +99,6 @@
 .slide-in { display: grid; grid-template-columns: minmax(0, 1fr); color: var(--ink); height: 100%; }
 .slide-media { position: relative; order: -1; aspect-ratio: 4 / 3; overflow: hidden; }
+/* Kapak görseli solmaz: üstündeki kapak başlığı her zaman tam okunur */
 .slide-img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover;
-  -webkit-mask-image: linear-gradient(to bottom, #000 70%, transparent); mask-image: linear-gradient(to bottom, #000 70%, transparent);
   transition: transform 1.2s var(--ease); }
 .slide-in:hover .slide-img { transform: scale(1.03); }
@@ -125,5 +125,5 @@
   .slide-in { grid-template-columns: minmax(0, 1fr) auto; height: clamp(400px, 40vw, 520px); }
   .slide-media { order: 0; aspect-ratio: 4 / 3; height: 100%; }
-  .slide-img { -webkit-mask-image: linear-gradient(to right, transparent 0, #000 14%); mask-image: linear-gradient(to right, transparent 0, #000 14%); }
+  .slide-media { margin: 16px 16px 16px 0; height: calc(100% - 32px); border-radius: 20px; }
   .slide-txt { padding: 40px 12px 40px 48px; gap: 12px; }
   .slide h2 { font-size: clamp(26px, 2.7vw, 40px); }
@@@SM@@@ SHA
30c3aacb32d1ced1828627a7fa938fd1a9a14e9a63e5b121350bc93b682a3144 haberbot/site.py
04ea02af13c574027f39a81ea617bda2892f6591847827776f3c51207c674c85 static/style.css
