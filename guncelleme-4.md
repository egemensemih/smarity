SMARITY-BUNDLE v1 part 4/6
 .art-head .meta-top { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; font-size: 14px; font-weight: 600; }
 .art-head .meta-top .eyebrow { font-size: 14px; text-transform: uppercase; letter-spacing: .04em; }
 .art-head .meta-top time, .art-head .meta-top .muted { color: var(--muted); font-weight: 400; }
-.art-head h1 { margin: 14px 0 0; font-size: clamp(32px, 5vw, 56px); line-height: 1.07; letter-spacing: -.04em; font-weight: 700; text-wrap: balance; }
-.art-head .dek { margin: 18px 0 0; font-size: clamp(19px, 2vw, 24px); line-height: 1.35; color: var(--ink-2); letter-spacing: -.02em; text-wrap: pretty; }
-.share { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 26px; }
-.share a, .share button { font-size: 14px; padding: 9px 16px; border-radius: 999px; background: var(--bg-alt); border: 0; cursor: pointer; transition: background .2s; }
-.share a:hover, .share button:hover { background: #E8E8ED; }
-.art-media { width: min(1200px, 100% - 32px); margin: 40px auto 0; }
+.art-head h1 { margin: 14px 0 0; font-size: clamp(32px, 5vw, 58px); line-height: 1.06; letter-spacing: -.04em; font-weight: 700; text-wrap: balance; }
+.art-head .dek { margin: 18px 0 0; max-width: 760px; font-size: clamp(19px, 2vw, 24px); line-height: 1.38; color: var(--ink-2); letter-spacing: -.02em; text-wrap: pretty; }
+.art-media { margin-top: 36px; }
 .art-media .ph { border-radius: var(--r-lg); overflow: hidden; background: var(--bg-alt); aspect-ratio: 4 / 3; }
 @media (min-width: 700px) { .art-media .ph { aspect-ratio: 16 / 9; } }
 .art-media img { width: 100%; height: 100%; object-fit: cover; }
 .art-media figcaption { margin-top: 10px; font-size: 13px; color: var(--muted); }
-.stat-band { display: grid; gap: 4px; padding: 40px 0 8px; }
-.stat-band .stat { font-size: clamp(56px, 10vw, 120px); }
-.art-body { font-size: 19px; line-height: 1.58; letter-spacing: -.014em; padding-top: 28px; }
-.art-body p { margin: 0 0 1.15em; }
+
+.art-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 40px; padding-top: 40px; }
+@media (min-width: 1000px) { .art-grid { grid-template-columns: minmax(0, 720px) 260px; justify-content: space-between; } }
+.art-main { min-width: 0; }
+
+/* öne çıkanlar kutusu */
+.facts { display: grid; gap: 22px; padding: 26px 28px; border-radius: var(--r-md);
+  background: color-mix(in srgb, var(--c) 7%, #fff); border: 1px solid color-mix(in srgb, var(--c) 18%, #fff); }
+@media (min-width: 700px) { .facts:has(.facts-stat):has(.facts-list) { grid-template-columns: auto minmax(0, 1fr); gap: 32px; align-items: start; } }
+.facts-stat { display: grid; gap: 4px; align-content: start; }
+.facts-stat .stat { font-size: clamp(48px, 7vw, 76px); }
+.facts-stat .stat-label { font-size: 15px; max-width: 16ch; }
+.facts-title { margin: 0 0 10px; font-size: 13px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
+  color: color-mix(in srgb, var(--c) 72%, #000); }
+.facts ol { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; counter-reset: f; }
+.facts li { counter-increment: f; display: grid; grid-template-columns: 26px minmax(0, 1fr); gap: 12px; font-size: 17px; line-height: 1.45; }
+.facts li::before { content: counter(f); width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center;
+  font-size: 13px; font-weight: 700; color: #fff; background: color-mix(in srgb, var(--c) 82%, #000); margin-top: 1px; }
+
+/* metin: ilk paragraf öne çıkar, bölümler ayraçla ayrılır */
+.art-body { font-size: 19px; line-height: 1.62; letter-spacing: -.012em; padding-top: 30px; }
+.art-body > p:first-child { font-size: 21px; line-height: 1.5; color: var(--ink); letter-spacing: -.018em; }
+.art-body p { margin: 0 0 1.1em; color: #2C2C2E; }
 .art-body a { color: var(--link); text-decoration: underline; text-underline-offset: 3px; }
-.art-body h2 { font-size: 26px; line-height: 1.2; letter-spacing: -.03em; margin: 1.6em 0 .5em; }
-.art-body ul, .art-body ol { padding-left: 1.2em; margin: 0 0 1.15em; }
