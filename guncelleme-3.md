SMARITY-BUNDLE v1 part 3/6
   <p class="live" role="status"><span class="dot" aria-hidden="true"></span>Son haber <b><time datetime="{{ latest_iso }}" data-rel data-live>{{ latest_str }}</time></b>{% if site.today_count %} · Bugün <b>{{ site.today_count }}</b> gelişme{% endif %}</p>
   {% endif %}
--- a/static/style.css
+++ b/static/style.css
@@ -46,7 +46,7 @@
 /* ── marka ─────────────────────────────── */
 .brand { display: inline-flex; align-items: center; gap: 5px; font-weight: 700; font-size: 19px; letter-spacing: -.03em; }
 .mark { width: 20px; height: 20px; border-radius: 6px; flex: none; background: var(--grad); }
-.brand .wordmark { display: block; width: auto; height: 25px; transition: opacity .2s var(--ease); }
+.brand .wordmark { display: block; width: auto; height: 32px; transition: opacity .2s var(--ease); }
 .brand:hover .wordmark { opacity: .82; }
 .foot .brand .wordmark { height: 28px; }
 
@@ -54,7 +54,7 @@
 .nav { position: sticky; top: 0; z-index: 50; background: var(--glass);
   -webkit-backdrop-filter: saturate(180%) blur(20px); backdrop-filter: saturate(180%) blur(20px);
   border-bottom: 1px solid rgba(0, 0, 0, .08); }
-.nav-in { height: 52px; display: flex; align-items: center; justify-content: space-between; gap: 20px; }
+.nav-in { height: 60px; display: flex; align-items: center; justify-content: space-between; gap: 20px; }
 .nav-links { display: none; gap: 26px; font-size: 13px; color: var(--ink-2); }
 .nav-links a { padding: 6px 0; position: relative; transition: color .2s; }
 .nav-links a:hover, .nav-links a.on { color: var(--ink); }
@@ -69,14 +69,16 @@
 .menu[open] summary span { background: transparent; }
 .menu[open] summary span::before { transform: translateY(5px) rotate(45deg); }
 .menu[open] summary span::after { transform: translateY(-5px) rotate(-45deg); }
-.menu-panel { position: fixed; left: 0; right: 0; top: 52px; background: rgba(255,255,255,.96);
+.menu-panel { position: fixed; left: 0; right: 0; top: 60px; background: rgba(255,255,255,.96);
   -webkit-backdrop-filter: blur(20px); backdrop-filter: blur(20px); padding: 20px 24px 32px; display: grid; gap: 4px;
   border-bottom: 1px solid var(--line); box-shadow: 0 30px 60px rgba(0,0,0,.08); }
 .menu-panel a { font-size: 26px; font-weight: 600; letter-spacing: -.02em; padding: 6px 0; }
 @media (min-width: 900px) { .nav-links { display: flex; } .menu { display: none; } }
 
 /* ── ana sayfa başlığı ─────────────────── */
-.home-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 6px 20px; padding-block: 28px 18px; }
+.home-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px 20px; padding-block: 22px 16px; }
+.home-date { margin: 0; font-size: 15px; font-weight: 600; color: var(--ink-2); letter-spacing: -.01em; }
+.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
 .home-head h1 { margin: 0; font-size: clamp(28px, 4vw, 44px); letter-spacing: -.04em; line-height: 1.05; font-weight: 700; }
 .live { margin: 0; font-size: 14px; color: var(--muted); }
 .live.stale .dot { display: none; }
@@ -236,35 +238,77 @@
 
 /* ── haber sayfası (Newsroom tarzı) ────── */
 .progress { position: fixed; top: 0; left: 0; right: 0; height: 3px; z-index: 60; background: var(--grad); transform-origin: 0 50%; transform: scaleX(0); }
+/* başlık ve görsel aynı hizada; metin görselin sol kenarından başlar */
 .art-head { padding-block: 28px 0; }
+.art-head > * { max-width: 900px; }
