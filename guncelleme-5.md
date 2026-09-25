SMARITY-BUNDLE v1 part 5/6
-.why { margin: 36px 0; padding: 30px 32px; border-radius: var(--r-md); background: var(--bg-alt); }
-.why strong { display: block; font-size: 14px; font-weight: 600; color: color-mix(in srgb, var(--c) 78%, #000); letter-spacing: .02em; }
-.why p { margin: 8px 0 0; font-size: 21px; line-height: 1.4; letter-spacing: -.02em; font-weight: 600; text-wrap: pretty; }
+.art-body strong { font-weight: 700; color: var(--ink);
+  background: linear-gradient(transparent 64%, color-mix(in srgb, var(--c) 22%, transparent) 0); }
+.art-body h2 { font-size: 26px; line-height: 1.2; letter-spacing: -.03em; margin: 1.7em 0 .55em; padding-top: 1.1em;
+  border-top: 1px solid var(--line); scroll-margin-top: 72px; }
+.art-body h2::before { content: ""; display: block; width: 32px; height: 4px; border-radius: 2px; background: var(--c); margin-bottom: 14px; }
+.art-body ul, .art-body ol { margin: 0 0 1.2em; padding: 0; list-style: none; display: grid; gap: 8px; }
+.art-body ul li { position: relative; padding-left: 22px; }
+.art-body ul li::before { content: ""; position: absolute; left: 4px; top: .62em; width: 7px; height: 7px; border-radius: 50%; background: var(--c); }
+.art-body ol { counter-reset: b; }
+.art-body ol li { counter-increment: b; position: relative; padding-left: 30px; }
+.art-body ol li::before { content: counter(b) "."; position: absolute; left: 0; font-weight: 700; color: color-mix(in srgb, var(--c) 80%, #000); }
+.why { margin: 36px 0 8px; padding: 26px 28px; border-radius: var(--r-md); background: var(--bg-alt); border-left: 4px solid var(--c); }
+.why strong { display: block; font-size: 13px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; background: none;
+  color: color-mix(in srgb, var(--c) 72%, #000); }
+.why p { margin: 8px 0 0; font-size: 21px; line-height: 1.42; letter-spacing: -.02em; font-weight: 600; color: var(--ink); text-wrap: pretty; }
+
+/* yan panel */
+.art-side { display: none; }
+@media (min-width: 1000px) { .art-side { display: block; } }
+.side-in { position: sticky; top: 76px; display: grid; gap: 28px; padding-top: 4px; }
+.side-h { margin: 0 0 8px; font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
+.toc ol { list-style: none; margin: 0; padding: 0; display: grid; border-left: 2px solid var(--line); }
+.toc a { display: block; padding: 7px 0 7px 14px; margin-left: -2px; border-left: 2px solid transparent; font-size: 15px; line-height: 1.35; color: var(--ink-2); }
+.toc a:hover { color: var(--ink); border-left-color: var(--c); }
+.share { display: flex; flex-wrap: wrap; gap: 8px; }
+.share .side-h { flex-basis: 100%; }
+.share a, .share button { font-size: 14px; padding: 8px 14px; border-radius: 999px; background: var(--bg-alt); border: 0; cursor: pointer; transition: background .2s; }
+.share a:hover, .share button:hover { background: #E8E8ED; }
+
 .art-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 32px; font-size: 14px; }
 .art-tags a { padding: 7px 14px; border-radius: 999px; background: var(--bg-alt); font-weight: 500; }
 .art-tags a:hover { background: #E8E8ED; }
 .sources { margin-top: 40px; border-top: 1px solid var(--line); padding-top: 24px; }
-.sources h2 { margin: 0 0 8px; font-size: 14px; font-weight: 600; color: var(--muted); }
+.sources h2 { margin: 0 0 8px; font-size: 13px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
 .sources ol { list-style: none; margin: 0; padding: 0; }
 .sources li a { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 16px 0; border-bottom: 1px solid var(--line); }
 .sources li a:hover .s-title { color: var(--link); }
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -15,7 +15,7 @@
 from .store import Store
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "6"
+ASSET_V = "7"
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
