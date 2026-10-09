SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -18,5 +18,5 @@
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "16"
+ASSET_V = "17"
 FOREIGN_PRICE = re.compile(r"(?=.*fiyat)(?=.*(\$|€|£|¥|dolar|euro|avro|sterlin|yuan|yen\b))", re.I)
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
@@ -443,4 +443,7 @@
             "home_description": seo.get("home_description") or cfg.site.get("description", ""),
             "verify": {k: seo.get(k) for k in ("google_site_verification", "bing_site_verification", "yandex_verification")},
+            # arama: dizin yalnızca arama açılınca yüklenir; sürüm en yeni haberle değişir (eski dizin önbellekte kalmasın)
+            "search_url": f"{b}/ara/",
+            "search_index": f"{b}/api/search.json?v={max((p['ts'] for p in posts), default=0)}",
         }
         site["follow"] = follow_links(site)
@@ -548,4 +551,13 @@
             sources=[s for s in cfg.sources]))
         self._write("404.html", self.env.get_template("404.html").render(**ctx, canonical=cfg.site_url + "/", noindex=True))
+        # arama sayfası (/ara/?q=…) ve tarayıcıda aranan haber dizini
+        self._write("ara/index.html", self.env.get_template("search.html").render(
+            **ctx, canonical=f"{cfg.site_url}/ara/", noindex=True, search_page=True))
+        self._write("api/search.json", json.dumps([{
+            "t": p["title"], "u": p["url"], "c": p["cat_label"], "o": p["cat_color"], "d": p["date_short"], "ts": p["ts"],
+            "s": clip(p.get("summary") or "", 200),
+            "g": " ".join(dict.fromkeys([t["label"] for t in p["tag_list"]] + list(p.get("entities") or []))),
+            "i": p["disp"].get("url") if p["disp"].get("kind") in ("photo", "image") else "",
+        } for p in posts], ensure_ascii=False, separators=(",", ":")))
 
         # besleme, site haritaları, robots, IndexNow anahtarı, json
--- a/static/site.js
+++ b/static/site.js
@@ -320,2 +320,150 @@
   });
 })();
+
+// ── Arama: haber dizini (api/search.json) yalnızca arama açılınca yüklenir; Türkçe harf duyarsız arar ──
+(function () {
+  var roots = document.querySelectorAll("[data-search]");
+  if (!roots.length) return;
+  var MAP = { "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u", "â": "a", "î": "i", "û": "u" };
+  function fold(s) {
+    return (s || "").toLocaleLowerCase("tr").replace(/[çğıöşüâîû]/g, function (c) { return MAP[c]; })
+      .normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
+  }
+  function esc(s) {
+    return String(s || "").replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; });
+  }
+  var VAR = { c: "[cçÇC]", g: "[gğĞG]", i: "[iıİI]", o: "[oöÖO]", s: "[sşŞS]", u: "[uüÜU]" };
+  function mark(text, toks) {
+    if (!toks.length) return esc(text);
+    var parts = toks.slice().sort(function (a, b) { return b.length - a.length; }).map(function (t) {
+      return t.split("").map(function (ch) { return VAR[ch] || ch.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("");
+    });
+    var re = new RegExp("(" + parts.join("|") + ")", "gi");
+    return text.split(re).map(function (seg, i) { return i % 2 ? "<mark>" + esc(seg) + "</mark>" : esc(seg); }).join("");
+  }
+
+  var data = null, loading = null;
+  function load(url) {
+    if (data) return Promise.resolve(data);
+    if (!loading) {
+      loading = fetch(url).then(function (r) { return r.json(); }).then(function (list) {
+        data = list.map(function (p) {
+          return { p: p, t: " " + fold(p.t) + " ", g: " " + fold(p.g) + " ", s: " " + fold(p.s) + " " };
+        });
+        return data;
+      }).catch(function () { loading = null; return []; });
+    }
+    return loading;
+  }
+  var NOW = Date.now() / 1000;
+  function find(q) {
+    var toks = fold(q).split(" ").filter(Boolean);
+    if (!toks.length || !data) return { toks: toks, list: [] };
+    var phrase = " " + toks.join(" ");
+    var out = [];
+    data.forEach(function (e) {
+      var score = 0;
+      for (var i = 0; i < toks.length; i++) {
+        var t = toks[i], w = " " + t, short = t.length < 2, s = 0;
+        if (e.t.indexOf(w) >= 0) s = 10;
+        else if (!short && e.t.indexOf(t) >= 0) s = 5;
+        else if (e.g.indexOf(w) >= 0) s = 6;
+        else if (!short && e.g.indexOf(t) >= 0) s = 3;
+        else if (e.s.indexOf(w) >= 0) s = 3;
+        else if (!short && t.length > 2 && e.s.indexOf(t) >= 0) s = 1;
+        if (!s) return;                      // her sözcük geçmeli
+        score += s;
+      }
+      if (toks.length > 1 && e.t.indexOf(phrase) >= 0) score += 8;
+      score += Math.max(0, 3 - (NOW - (e.p.ts || 0)) / 864000);   // yeni haberler biraz önde
+      out.push({ e: e, score: score });
+    });
+    out.sort(function (a, b) { return b.score - a.score || (b.e.p.ts || 0) - (a.e.p.ts || 0); });
+    return { toks: toks, list: out.map(function (x) { return x.e.p; }) };
+  }
+  function row(p, toks) {
+    var img = p.i ? '<img src="' + esc(p.i) + '" alt="" loading="lazy" decoding="async">' : '<span class="row-noimg"></span>';
+    return '<li class="row" style="--c:' + esc(p.o) + '"><a href="' + esc(p.u) + '"><time>' + esc(p.d) + "</time>" +
+      '<span class="row-main"><span class="row-cat"><i aria-hidden="true"></i>' + esc(p.c) + "</span>" +
+      '<span class="row-title">' + mark(p.t, toks) + "</span></span>" +
+      '<span class="row-img" aria-hidden="true">' + img + "</span></a></li>";
+  }
+
+  roots.forEach(function (root) {
+    var page = root.hasAttribute("data-search-page");
+    var input = root.querySelector("input[name=q]");
+    var res = root.querySelector("[data-search-results]");
+    var hint = root.querySelector("[data-search-hint]");
+    var count = root.querySelector("[data-search-count]");
+    var all = root.querySelector("[data-search-all]");
+    var url = root.getAttribute("data-url");
+    var max = page ? 100 : 12, timer = null, opener = null;
+
+    function render() {
+      var q = input.value.trim();
+      if (!q) {
+        res.innerHTML = ""; hint.hidden = false; count.hidden = true; if (all) all.hidden = true;
+        if (page) history.replaceState(null, "", url);
+        return;
+      }
+      load(root.getAttribute("data-index")).then(function () {
+        if (input.value.trim() !== q) return;
+        var r = find(q);
+        hint.hidden = true;
+        count.hidden = false;
+        count.textContent = r.list.length ? "“" + q + "” için " + r.list.length + " haber"
+          : "“" + q + "” ile ilgili haber bulunamadı. Başka bir sözcükle dene.";
+        res.innerHTML = r.list.slice(0, max).map(function (p) { return row(p, r.toks); }).join("");
+        if (all) {
+          all.hidden = r.list.length <= max;
+          all.querySelector("a").href = url + "?q=" + encodeURIComponent(q);
+        }
+        if (page) history.replaceState(null, "", url + "?q=" + encodeURIComponent(q));
+      });
+    }
+    input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(render, 90); });
+    input.addEventListener("focus", function () { load(root.getAttribute("data-index")); });
+    // klavye: ↓/↑ sonuçlar arasında gezinir
+    root.addEventListener("keydown", function (ev) {
+      if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
+      var links = [input].concat([].slice.call(res.querySelectorAll("a")));
+      var i = links.indexOf(document.activeElement);
+      if (i < 0) return;
+      ev.preventDefault();
+      var n = links[Math.max(0, Math.min(links.length - 1, i + (ev.key === "ArrowDown" ? 1 : -1)))];
+      if (n) n.focus();
+    });
+
+    if (page) {
+      var q0 = new URLSearchParams(location.search).get("q") || "";
+      input.value = q0;
+      if (q0) render(); else input.focus();
+      document.querySelectorAll("[data-search-open]").forEach(function (b) {
+        b.addEventListener("click", function (ev) { ev.preventDefault(); input.focus(); input.select(); });
+      });
+      return;
+    }
+
+    function open(ev) {
+      if (ev) ev.preventDefault();
+      opener = document.activeElement;
+      root.hidden = false;
+      document.body.classList.add("srch-on");
+      input.focus();
+      input.select();
+      load(root.getAttribute("data-index"));
+    }
+    function close() {
+      root.hidden = true;
+      document.body.classList.remove("srch-on");
+      if (opener && opener.focus) opener.focus();
+    }
+    document.querySelectorAll("[data-search-open]").forEach(function (b) { b.addEventListener("click", open); });
+    root.querySelectorAll("[data-search-close]").forEach(function (b) { b.addEventListener("click", close); });
+    document.addEventListener("keydown", function (ev) {
+      var typing = /^(INPUT|TEXTAREA|SELECT)$/.test((ev.target && ev.target.tagName) || "") || (ev.target && ev.target.isContentEditable);
+      if (ev.key === "Escape" && !root.hidden) { ev.preventDefault(); close(); }
+      else if (root.hidden && ((ev.key === "/" && !typing) || ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k"))) open(ev);
+    });
+  });
+})();
--- a/static/style.css
+++ b/static/style.css
@@ -568,2 +568,38 @@
 @keyframes grow-x { to { transform: scaleX(1); } }
 @media (prefers-reduced-motion: reduce) { .dot { animation: none; } * { transition: none !important; } }
+
+/* ── arama ─────────────────────────────── */
+.srch-btn { width: 36px; height: 36px; display: grid; place-items: center; border-radius: 50%; color: var(--ink); transition: background .2s; }
+.srch-btn:hover { background: var(--bg-alt); }
+body.srch-on { overflow: hidden; }
+.srch[hidden], .srch-hint[hidden], .srch-count[hidden], .srch-all[hidden] { display: none; }
+.srch:not(.srch-page) { position: fixed; inset: 0; z-index: 100; }
+.srch-back { position: absolute; inset: 0; background: rgba(0, 0, 0, .3); -webkit-backdrop-filter: blur(4px); backdrop-filter: blur(4px); animation: srchfade .2s var(--ease); }
+.srch-panel { position: relative; margin: 72px auto 0; width: min(720px, calc(100% - 32px)); max-height: calc(100vh - 120px); display: flex; flex-direction: column;
+  background: #fff; border-radius: 20px; box-shadow: 0 30px 80px rgba(0, 0, 0, .2); overflow: hidden; animation: srchin .25s var(--ease); }
+.srch-form { display: flex; align-items: center; gap: 12px; padding: 14px 18px; border-bottom: 1px solid #E8E8ED; color: var(--muted); }
+.srch-form svg { flex: none; }
+.srch-form input { flex: 1; min-width: 0; border: 0; outline: 0; padding: 4px 0; font: 500 19px/1.3 var(--font); letter-spacing: -.01em; color: var(--ink); background: transparent; }
+.srch-form input::placeholder { color: #A1A1A6; }
+.srch-x { flex: none; border: 0; background: none; padding: 6px 2px; font: 500 15px var(--font); color: var(--link); cursor: pointer; }
+.srch-body { overflow-y: auto; overscroll-behavior: contain; padding: 4px 20px 18px; }
+.srch-h { margin: 14px 0 10px; font-size: 13px; font-weight: 600; color: var(--muted); }
+.srch-tags { display: flex; flex-wrap: wrap; gap: 8px; }
+.srch-tags a { padding: 7px 14px; border-radius: 999px; background: var(--bg-alt); font-size: 14px; font-weight: 500; transition: background .2s; }
+.srch-tags a:hover { background: #E8E8ED; }
+.srch-count { margin: 14px 0 0; font-size: 14px; color: var(--muted); }
+.rows.srch-res { grid-template-columns: minmax(0, 1fr); }
+.srch-res mark { background: rgba(50, 110, 240, .16); color: inherit; border-radius: 3px; padding: 0 1px; }
+.srch-res .row:last-child a { border-bottom: 0; }
+.srch-all { margin: 12px 0 0; }
+.row-noimg { display: block; aspect-ratio: 4 / 3; background: linear-gradient(135deg, color-mix(in srgb, var(--c) 26%, #fff), color-mix(in srgb, var(--c) 8%, #fff)); }
+.srch-page { max-width: 760px; padding-bottom: 72px; }
+.srch-form.big { border: 1px solid var(--line); border-radius: 16px; background: #fff; transition: border-color .2s, box-shadow .2s; }
+.srch-form.big:focus-within { border-color: var(--link); box-shadow: 0 0 0 4px rgba(36, 88, 214, .12); }
+@media (max-width: 599px) {
+  .srch-panel { margin: 0; width: 100%; height: 100%; height: 100dvh; max-height: none; border-radius: 0; }
+  .srch-body { padding-inline: 16px; }
+}
+@keyframes srchin { from { opacity: 0; transform: translateY(-8px) scale(.99); } to { opacity: 1; transform: none; } }
+@keyframes srchfade { from { opacity: 0; } to { opacity: 1; } }
+@media (prefers-reduced-motion: reduce) { .srch-back, .srch-panel { animation: none; } }
--- a/templates/base.html
+++ b/templates/base.html
@@ -51,4 +51,5 @@
     </div>
     <div class="nav-end">
+      <a class="srch-btn" href="{{ site.search_url }}" data-search-open aria-label="Haberlerde ara" title="Haberlerde ara"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></svg></a>
       <a href="{{ site.base }}/haberler/" class="hide-sm">Tüm haberler</a>
       <a href="{{ site.base }}/hakkinda/" class="hide-sm">Hakkında</a>
@@ -101,4 +102,25 @@
   </div>
 </footer>
+{% if not search_page|default(false) %}
+<div class="srch" data-search data-index="{{ site.search_index }}" data-url="{{ site.search_url }}" hidden>
+  <div class="srch-back" data-search-close></div>
+  <div class="srch-panel" role="dialog" aria-modal="true" aria-label="Haberlerde ara">
+    <form class="srch-form" action="{{ site.search_url }}" method="get" role="search">
+      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></svg>
+      <input type="search" name="q" placeholder="Haberlerde ara" autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="search" aria-label="Aranacak sözcük">
+      <button type="button" class="srch-x" data-search-close>Vazgeç</button>
+    </form>
+    <div class="srch-body">
+      <div class="srch-hint" data-search-hint>
+        {% if site.top_tags %}<p class="srch-h">Popüler konular</p>
+        <div class="srch-tags">{% for t in site.top_tags[:12] %}<a href="{{ t.url }}">{{ t.label }}</a>{% endfor %}</div>{% endif %}
+      </div>
+      <p class="srch-count" data-search-count hidden></p>
+      <ol class="rows srch-res" data-search-results></ol>
+      <p class="srch-all" data-search-all hidden><a class="more" href="{{ site.search_url }}">Tüm sonuçlar</a></p>
+    </div>
+  </div>
+</div>
+{% endif %}
 <script src="{{ site.base }}/static/site.js?v={{ site.asset_v }}" defer></script>
 </body>
--- a/templates/index.html
+++ b/templates/index.html
@@ -15,5 +15,7 @@
     {"@type": "WebSite", "@id": site.url ~ "/#website", "name": site.name, "alternateName": site.name ~ " teknoloji haberleri",
      "url": site.url ~ "/", "inLanguage": "tr-TR", "description": site.home_description,
-     "publisher": {"@id": site.url ~ "/#org"}},
+     "publisher": {"@id": site.url ~ "/#org"},
+     "potentialAction": {"@type": "SearchAction", "target": {"@type": "EntryPoint", "urlTemplate": site.url ~ "/ara/?q={search_term_string}"},
+                         "query-input": "required name=search_term_string"}},
     org
   ]
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -254,4 +254,24 @@
 
 
+
+def test_search_page_and_index():
+    import json as _json
+    with _App() as (cfg, a):
+        a.store.save_post(_post(1, 2, title="Kia Seltos Türkiye'de satışa çıktı", tags=["Kia", "SUV"], entities=["Kia Seltos"]))
+        a.store.save_post(_post(2, 3, title="Yapay zeka destekli ışık sensörü", tags=["Yapay zeka"]))
+        a.migrate_urls()
+        SiteBuilder(cfg).build()
+        idx = _json.loads((cfg.out_dir / "api" / "search.json").read_text(encoding="utf-8"))
+        assert {x["t"] for x in idx} == {"Kia Seltos Türkiye'de satışa çıktı", "Yapay zeka destekli ışık sensörü"}
+        kia = next(x for x in idx if x["t"].startswith("Kia"))
+        assert kia["u"].endswith("/haber-1/") and "Kia Seltos" in kia["g"] and kia["c"] and kia["o"]
+        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
+        assert "data-search-open" in home and 'class="srch"' in home and "/api/search.json?v=" in home
+        assert "SearchAction" in home and "/ara/?q={search_term_string}" in home
+        page = (cfg.out_dir / "ara" / "index.html").read_text(encoding="utf-8")
+        assert 'content="noindex' in page and "data-search-page" in page and 'class="srch"' not in page
+        assert "/ara/" not in (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")
+
+
 if __name__ == "__main__":
     for name, fn in list(globals().items()):
@@@SM@@@ FILE templates/search.html
{% extends "base.html" %}
{% from "_macros.html" import crumbs %}
{% block title %}Haberlerde ara | {{ site.name }}{% endblock %}
{% block description %}Smarity'de yayımlanan teknoloji, yapay zeka, otomotiv, girişimcilik ve gaming haberlerinde ara.{% endblock %}
{% block main %}
{{ crumbs([("Ana sayfa", site.base ~ "/", site.url ~ "/"), ("Ara", site.search_url, site.url ~ "/ara/")]) }}
<header class="page-head wrap"><h1>Haberlerde ara.</h1></header>
<section class="wrap srch-page" data-search data-search-page data-index="{{ site.search_index }}" data-url="{{ site.search_url }}">
  <form class="srch-form big" action="{{ site.search_url }}" method="get" role="search">
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></svg>
    <input type="search" name="q" placeholder="Örneğin: iPhone, TOGG, yapay zeka" autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="search" aria-label="Aranacak sözcük">
  </form>
  <div class="srch-hint" data-search-hint>
    {% if site.top_tags %}<p class="srch-h">Popüler konular</p>
    <div class="srch-tags">{% for t in site.top_tags[:14] %}<a href="{{ t.url }}">{{ t.label }}</a>{% endfor %}</div>{% endif %}
  </div>
  <p class="srch-count" data-search-count aria-live="polite" hidden></p>
  <ol class="rows srch-res" data-search-results></ol>
</section>
{% endblock %}
@@@SM@@@ SHA
593a55e72b2a3b1bef016ebe09993546076e2e0894711348484a146301e9d237 haberbot/site.py
bb4db7132543f8c947ec560fada51d5d4f12d1ed6d159aafcd5623f921b506a7 static/site.js
b80da3c5a6ecc64fbd431a4091133f4b657c40559490e6092cd70ef00a6c1c70 static/style.css
23f483677d30f7e729a027b4d055b3e1c5fae47652c920cf3e7bca6a144f091e templates/base.html
2e5a4c4a6b171fe20d7830dff072c5b0ff9331837940fc402aedd622c3f15628 templates/index.html
c599ec317e8af18290d4774d5b869e1e07c5f6a202c65048a9ccd659f33d33ba tests/test_home.py
cba860b46c00dc5fb11b3100d8182464cd17c68dd4fcf8e1d151b691fdbf17ec templates/search.html
