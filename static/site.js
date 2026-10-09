(function () {
  // ── Kişisel hafıza (yalnızca bu tarayıcıda): son ziyaret, okunan haberler, görülen manşetler ──
  function load(k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function save(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  var NOW = Math.floor(Date.now() / 1000);
  var read = load("sm_read", {});          // {id: zaman}
  var seen = load("sm_seen", {});          // manşette gösterilenler {id: zaman}
  function prune(o, max) { var ks = Object.keys(o).sort(function (a, b) { return o[b] - o[a]; }); ks.slice(max).forEach(function (k) { delete o[k]; }); return o; }

  // Haber sayfası: okundu olarak işaretle
  var art = document.querySelector("[data-read]");
  if (art) { read[art.getAttribute("data-read")] = NOW; save("sm_read", prune(read, 400)); }

  // Son ziyaret: 30 dakikadan uzun aradan sonra gelinirse "yeni" sayılır
  var visit = load("sm_visit", null), since = 0;
  if (visit && NOW - visit.last > 1800) { since = visit.last; visit = { last: NOW, prev: visit.last }; }
  else if (visit) { since = visit.prev || 0; visit.last = NOW; }
  else { visit = { last: NOW, prev: 0 }; }
  save("sm_visit", visit);

  var isHome = !!document.querySelector(".car");
  var items = document.querySelectorAll("[data-id][data-ts]");
  var newIds = {};
  items.forEach(function (el) {
    var id = el.getAttribute("data-id"), ts = +el.getAttribute("data-ts");
    var top = el.querySelector(".card-top, .row-cat, .slide-top");
    if (read[id]) {
      el.classList.add("is-read");
      if (top) top.insertAdjacentHTML("beforeend", '<span class="badge read">Okundu</span>');
    } else if (since && ts > since) {
      newIds[id] = 1;
      el.classList.add("is-new");
      if (top) top.insertAdjacentHTML("beforeend", '<span class="badge new">Yeni</span>');
    }
  });
  var nNew = Object.keys(newIds).length;
  var banner = document.querySelector("[data-since]");
  if (banner && nNew) {
    banner.querySelector("[data-since-text]").textContent = "Son ziyaretinden beri " + nNew + " yeni haber";
    banner.hidden = false;
  }

  if (isHome) {
    // Öne çıkanlar: okunanlar sona
    var grid = document.querySelector("[data-top]");
    if (grid) Array.prototype.slice.call(grid.children).filter(function (c) { return c.classList.contains("is-read"); })
      .forEach(function (c) { grid.appendChild(c); });
    // Kaçırmış olabilirsin: her ziyarette okunmamışlardan farklı dört haber
    var disc = document.querySelector("[data-discover]");
    if (disc) {
      var all = Array.prototype.slice.call(disc.querySelectorAll(".disc-item"));
      var unread = all.filter(function (d) { return !d.querySelector(".is-read"); });
      var rest = all.filter(function (d) { return unread.indexOf(d) < 0; });
      function shuffle(a) { for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
      var pick = shuffle(unread).concat(shuffle(rest)).slice(0, 4);
      all.forEach(function (d) { d.hidden = pick.indexOf(d) < 0; });
      pick.forEach(function (d) {
        disc.appendChild(d);
        // aynı haber aşağıdaki kategori şeritlerinde tekrar görünmesin
        var id = d.querySelector("[data-id]").getAttribute("data-id");
        document.querySelectorAll('.rail [data-id="' + id + '"]').forEach(function (r) { r.remove(); });
      });
    }
    // Manşet: okunmamış ve son 12 saatte görülmemiş haberler önce (her girişte aynı manşet görünmesin)
    var track = document.getElementById("car-track");
    if (track) {
      var sl = Array.prototype.slice.call(track.querySelectorAll(".slide"));
      function rank(s) { var id = s.getAttribute("data-id"); return read[id] ? 2 : (seen[id] && NOW - seen[id] < 43200) ? 1 : 0; }
      var ordered = sl.map(function (s, i) { return [rank(s), i, s]; }).sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
      if (ordered.some(function (x, k) { return x[1] !== k; })) {
        var dots = document.querySelector(".car-dots"), db = dots ? Array.prototype.slice.call(dots.children) : [];
        ordered.forEach(function (x, k) {
          track.appendChild(x[2]);
          x[2].setAttribute("aria-label", (k + 1) + " / " + sl.length);
          x[2].querySelector(".slide-img") && (x[2].querySelector(".slide-img").loading = k === 0 ? "eager" : "lazy");
          if (db[x[1]]) dots.appendChild(db[x[1]]);
        });
        if (dots) Array.prototype.slice.call(dots.children).forEach(function (b, k) { b.setAttribute("data-go", k); if (k === 0) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current"); });
      }
      window.__smSeen = function (id) { seen[id] = Math.floor(Date.now() / 1000); save("sm_seen", prune(seen, 120)); };
    }
  }

  // Yerel paylaşım (telefonlarda paylaş menüsü)
  document.querySelectorAll("[data-share]").forEach(function (b) {
    if (!navigator.share) return;
    b.hidden = false;
    b.addEventListener("click", function () {
      navigator.share({ title: b.getAttribute("data-title"), url: b.getAttribute("data-url") }).catch(function () {});
    });
  });

  // Ana ekrana ekle (destekleyen tarayıcılarda)
  var installEvt = null;
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault(); installEvt = e;
    document.querySelectorAll("[data-install]").forEach(function (b) { b.hidden = false; });
  });
  document.querySelectorAll("[data-install]").forEach(function (b) {
    b.addEventListener("click", function () { if (installEvt) { installEvt.prompt(); installEvt = null; b.hidden = true; } });
  });

  // Göreli zaman: "12 dk önce"
  var now = Date.now();
  document.querySelectorAll("time[data-rel]").forEach(function (t) {
    var d = Date.parse(t.getAttribute("datetime"));
    if (!d) return;
    var m = Math.round((now - d) / 60000);
    var sh = t.getAttribute("data-rel") === "short";
    var s = m < 1 ? "az önce" : m < 60 ? m + " dk" + (sh ? "" : " önce") : m < 1440 ? Math.round(m / 60) + (sh ? " sa" : " saat önce")
      : m < 10080 ? Math.round(m / 1440) + " gün" + (sh ? "" : " önce") : null;
    if (s) { t.title = t.textContent; t.textContent = s; }
    if (t.hasAttribute("data-live") && m > 180) { var l = t.closest(".live"); if (l) l.classList.add("stale"); }
  });

  // Yatay şerit okları
  document.querySelectorAll(".arrows").forEach(function (box) {
    var rail = document.getElementById(box.getAttribute("data-rail"));
    if (!rail) return;
    var btns = box.querySelectorAll("button");
    function update() {
      btns[0].disabled = rail.scrollLeft < 8;
      btns[1].disabled = rail.scrollLeft + rail.clientWidth > rail.scrollWidth - 8;
    }
    btns.forEach(function (b) {
      b.addEventListener("click", function () {
        var card = rail.firstElementChild;
        var step = card ? card.getBoundingClientRect().width + 20 : 300;
        rail.scrollBy({ left: step * (+b.getAttribute("data-dir")) * 2, behavior: "smooth" });
      });
    });
    rail.addEventListener("scroll", update, { passive: true });
    update();
  });

  // Fotoğraf galerisi: kaydırma, oklar, sayaç, küçük resimler
  document.querySelectorAll("[data-gal]").forEach(function (g) {
    var track = g.querySelector(".gal-track");
    if (!track) return;
    var prev = g.querySelector('.gal-btn[data-dir="-1"]'), next = g.querySelector('.gal-btn[data-dir="1"]');
    var count = g.querySelector(".gal-count b");
    function slides() { return track.querySelectorAll(".gal-slide"); }
    function idx() { return Math.round(track.scrollLeft / Math.max(1, track.clientWidth)); }
    function update() {
      var n = slides().length, i = Math.min(idx(), n - 1);
      if (count) count.textContent = i + 1;
      var tot = g.querySelector(".gal-count"); if (tot) { tot.lastChild.nodeValue = " / " + n; tot.hidden = n < 2; }
      if (prev) prev.disabled = i <= 0;
      if (next) next.disabled = i >= n - 1;
      g.querySelectorAll(".gal-thumbs button").forEach(function (b, k) { b.setAttribute("aria-current", k === i ? "true" : "false"); });
    }
    function go(i) { track.scrollTo({ left: i * track.clientWidth, behavior: "smooth" }); }
    [prev, next].forEach(function (b) { if (b) b.addEventListener("click", function () { go(idx() + (+b.getAttribute("data-dir"))); }); });
    g.querySelectorAll(".gal-thumbs button").forEach(function (b) { b.addEventListener("click", function () { go(+b.getAttribute("data-go")); }); });
    var t; track.addEventListener("scroll", function () { clearTimeout(t); t = setTimeout(update, 60); }, { passive: true });
    track.addEventListener("keydown", function (e) { if (e.key === "ArrowRight") go(idx() + 1); if (e.key === "ArrowLeft") go(idx() - 1); });
    update();
  });

  // Bağlantıyı kopyala
  document.querySelectorAll("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var label = b.textContent;
      try {
        navigator.clipboard.writeText(b.getAttribute("data-copy")).then(function () {
          b.textContent = "Kopyalandı";
          setTimeout(function () { b.textContent = label; }, 1600);
        });
      } catch (e) {}
    });
  });

  // Kaydırmalı manşet: parmakla kaydırılır, kendiliğinden ilerler, üzerine gelince/dokununca durur
  document.querySelectorAll(".car").forEach(function (car) {
    var track = car.querySelector(".car-track");
    var slides = Array.prototype.slice.call(car.querySelectorAll(".slide"));
    var dots = Array.prototype.slice.call(car.querySelectorAll(".car-dots button"));
    var play = car.querySelector(".car-play");
    if (!track || slides.length < 2) { if (slides[0]) { slides[0].classList.add("on"); if (window.__smSeen) window.__smSeen(slides[0].getAttribute("data-id")); } return; }
    var dur = +car.getAttribute("data-interval") || 6500;
    car.style.setProperty("--dur", dur + "ms");
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var cur = 0, timer = null, userStopped = reduce, hover = false, visible = true, settleT = null;

    function setCur(i) {
      if (i === cur && slides[i].classList.contains("on")) return;
      cur = i;
      if (window.__smSeen) { var sid = slides[i].getAttribute("data-id"); clearTimeout(car.__seenT); car.__seenT = setTimeout(function () { window.__smSeen(sid); }, 2500); }
      slides.forEach(function (s, k) { s.classList.toggle("on", k === i); s.setAttribute("aria-hidden", k === i ? "false" : "true");
        s.querySelector("a").tabIndex = k === i ? 0 : -1; });
      dots.forEach(function (d, k) {
        if (k === i) { d.setAttribute("aria-current", "true"); var bar = d.firstElementChild; if (bar) { bar.style.animation = "none"; void bar.offsetWidth; bar.style.animation = ""; } }
        else d.removeAttribute("aria-current");
      });
    }
    function go(i, smooth) {
      i = (i + slides.length) % slides.length;
      var x = slides[i].offsetLeft - slides[0].offsetLeft;
      track.scrollTo({ left: x, behavior: smooth === false || reduce ? "auto" : "smooth" });
      setCur(i);
      schedule();
    }
    function running() { return !userStopped && !hover && visible && !document.hidden; }
    function schedule() {
      clearTimeout(timer);
      car.classList.toggle("playing", !userStopped);
      car.classList.toggle("paused", !running());
      if (running()) timer = setTimeout(function () { go(cur + 1); }, dur);
    }
    // kullanıcı kaydırınca hangi karede olduğumuzu bul
    track.addEventListener("scroll", function () {
      clearTimeout(settleT);
      settleT = setTimeout(function () {
        var mid = track.scrollLeft + track.clientWidth / 2, best = 0, bd = 1e9;
        slides.forEach(function (s, k) { var c = s.offsetLeft - slides[0].offsetLeft + s.clientWidth / 2 + parseFloat(getComputedStyle(track).paddingLeft);
          var d = Math.abs(c - mid); if (d < bd) { bd = d; best = k; } });
        if (best !== cur) { setCur(best); schedule(); }
      }, 90);
    }, { passive: true });
    dots.forEach(function (d, k) { d.addEventListener("click", function () { go(k); }); });
    car.querySelectorAll(".car-arr").forEach(function (b) {
      b.addEventListener("click", function () { go(cur + (+b.getAttribute("data-dir"))); });
    });
    if (play) play.addEventListener("click", function () {
      userStopped = !userStopped;
      play.setAttribute("data-state", userStopped ? "pause" : "play");
      play.setAttribute("aria-label", userStopped ? "Otomatik geçişi başlat" : "Otomatik geçişi durdur");
      schedule();
    });
    if (reduce && play) { play.setAttribute("data-state", "pause"); play.setAttribute("aria-label", "Otomatik geçişi başlat"); }
    car.addEventListener("mouseenter", function () { hover = true; schedule(); });
    car.addEventListener("mouseleave", function () { hover = false; schedule(); });
    car.addEventListener("focusin", function () { hover = true; schedule(); });
    car.addEventListener("focusout", function () { hover = false; schedule(); });
    track.addEventListener("pointerdown", function (e) { if (e.pointerType !== "mouse") { hover = true; schedule(); } }, { passive: true });
    track.addEventListener("touchend", function () { setTimeout(function () { hover = false; schedule(); }, 2500); }, { passive: true });
    car.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight") { e.preventDefault(); go(cur + 1); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); go(cur - 1); }
    });
    document.addEventListener("visibilitychange", schedule);
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (en) { visible = en[0].isIntersecting; schedule(); }, { threshold: 0.35 }).observe(car);
    }
    setCur(0);
    schedule();
  });

  // Bugünün tarihi (sayfa daha önce üretilmiş olabilir; tarih ziyaretçinin saatine göre yazılır)
  var today = document.querySelector("[data-today]");
  if (today && window.Intl) {
    try {
      var dNow = new Date(), tz = { timeZone: "Europe/Istanbul" };
      today.textContent = new Intl.DateTimeFormat("tr-TR", Object.assign({ day: "numeric", month: "long", year: "numeric" }, tz)).format(dNow) +
        ", " + new Intl.DateTimeFormat("tr-TR", Object.assign({ weekday: "long" }, tz)).format(dNow);
    } catch (e) {}
  }

  // Canlı piyasalar: dolar, euro, sterlin, gram altın, BIST 100, bitcoin. Dakikada bir yenilenir;
  // veri gelmeyen kalem gizlenir, hiç veri gelmezse şerit tamamen kaybolur.
  var mkt = document.querySelector("[data-mkt]");
  if (mkt && window.fetch && window.Promise) {
    var nf = function (v, d) { return new Intl.NumberFormat("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d }).format(v); };
    var num = function (x) {
      if (typeof x === "number") return x;
      x = String(x || "").replace(/[^0-9,.-]/g, "");
      return parseFloat(x.indexOf(",") >= 0 ? x.replace(/\./g, "").replace(",", ".") : x);   // "6.542,72" ya da "84812.33"
    };
    var seenK = {};
    var put = function (k, val, ch, dec, pre) {
      var it = mkt.querySelector('[data-k="' + k + '"]');
      if (!it || !isFinite(val) || val <= 0) return false;
      var b = it.querySelector("b"), txt = (pre || "") + nf(val, dec);
      if (b.textContent !== txt) {
        if (seenK[k]) { b.classList.remove("flash"); void b.offsetWidth; b.classList.add("flash"); }
        b.textContent = txt;
      }
      seenK[k] = 1;
      var i = it.querySelector("i");
      if (isFinite(ch)) {
        i.textContent = (ch > 0.004 ? "▲ " : ch < -0.004 ? "▼ " : "") + "%" + nf(Math.abs(ch), 2);
        i.className = ch > 0.004 ? "up" : ch < -0.004 ? "dn" : "eq";
      } else { i.textContent = ""; }
      it.hidden = false;
      return true;
    };
    var get = function (u) {
      var c = window.AbortController ? new AbortController() : null;
      if (c) setTimeout(function () { c.abort(); }, 8000);
      return fetch(u, { cache: "no-store", signal: c ? c.signal : undefined }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
    };
    var loadMkt = function () {
      var fx = get("https://finans.truncgil.com/v4/today.json?t=" + Date.now()).then(function (j) {
        [["USD", 2], ["EUR", 2], ["GBP", 2], ["GRA", 0], ["XU100", 0]].forEach(function (x) {
          var o = j[x[0]];
          if (o) put(x[0], num(o.Selling) || num(o.Buying), num(o.Change), x[1]);
        });
      }).catch(function () {
        return get("https://api.frankfurter.dev/v1/latest?base=TRY&symbols=USD,EUR,GBP").then(function (j) {
          ["USD", "EUR", "GBP"].forEach(function (k) { if (j.rates && j.rates[k]) put(k, 1 / j.rates[k], NaN, 2); });
        }).catch(function () {});
      });
      var btc = get("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT").then(function (j) {
        put("BTC", num(j.lastPrice), num(j.priceChangePercent), 0, "$");
      }).catch(function () {});
      Promise.all([fx, btc]).then(function () {
        if (!mkt.classList.contains("loading")) return;
        mkt.classList.remove("loading");
        mkt.querySelectorAll("[data-k]").forEach(function (it) { if (!seenK[it.getAttribute("data-k")]) it.hidden = true; });
        if (!Object.keys(seenK).length) mkt.classList.add("gone");
      });
    };
    loadMkt();
    setInterval(function () { if (!document.hidden) loadMkt(); }, 60000);
  }

  // Menü: bir bağlantıya basınca kapansın
  document.querySelectorAll(".menu-panel a").forEach(function (a) {
    a.addEventListener("click", function () { var m = a.closest("details"); if (m) m.open = false; });
  });
})();

// ── Arama: haber dizini (api/search.json) yalnızca arama açılınca yüklenir; Türkçe harf duyarsız arar ──
(function () {
  var roots = document.querySelectorAll("[data-search]");
  if (!roots.length) return;
  var MAP = { "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u", "â": "a", "î": "i", "û": "u" };
  function fold(s) {
    return (s || "").toLocaleLowerCase("tr").replace(/[çğıöşüâîû]/g, function (c) { return MAP[c]; })
      .normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
  }
  function esc(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; });
  }
  var VAR = { c: "[cçÇC]", g: "[gğĞG]", i: "[iıİI]", o: "[oöÖO]", s: "[sşŞS]", u: "[uüÜU]" };
  function mark(text, toks) {
    if (!toks.length) return esc(text);
    var parts = toks.slice().sort(function (a, b) { return b.length - a.length; }).map(function (t) {
      return t.split("").map(function (ch) { return VAR[ch] || ch.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("");
    });
    var re = new RegExp("(" + parts.join("|") + ")", "gi");
    return text.split(re).map(function (seg, i) { return i % 2 ? "<mark>" + esc(seg) + "</mark>" : esc(seg); }).join("");
  }

  var data = null, loading = null;
  function load(url) {
    if (data) return Promise.resolve(data);
    if (!loading) {
      loading = fetch(url).then(function (r) { return r.json(); }).then(function (list) {
        data = list.map(function (p) {
          return { p: p, t: " " + fold(p.t) + " ", g: " " + fold(p.g) + " ", s: " " + fold(p.s) + " " };
        });
        return data;
      }).catch(function () { loading = null; return []; });
    }
    return loading;
  }
  var NOW = Date.now() / 1000;
  function find(q) {
    var toks = fold(q).split(" ").filter(Boolean);
    if (!toks.length || !data) return { toks: toks, list: [] };
    var phrase = " " + toks.join(" ");
    var out = [];
    data.forEach(function (e) {
      var score = 0;
      for (var i = 0; i < toks.length; i++) {
        var t = toks[i], w = " " + t, short = t.length < 2, s = 0;
        if (e.t.indexOf(w) >= 0) s = 10;
        else if (!short && e.t.indexOf(t) >= 0) s = 5;
        else if (e.g.indexOf(w) >= 0) s = 6;
        else if (!short && e.g.indexOf(t) >= 0) s = 3;
        else if (e.s.indexOf(w) >= 0) s = 3;
        else if (!short && t.length > 2 && e.s.indexOf(t) >= 0) s = 1;
        if (!s) return;                      // her sözcük geçmeli
        score += s;
      }
      if (toks.length > 1 && e.t.indexOf(phrase) >= 0) score += 8;
      score += Math.max(0, 3 - (NOW - (e.p.ts || 0)) / 864000);   // yeni haberler biraz önde
      out.push({ e: e, score: score });
    });
    out.sort(function (a, b) { return b.score - a.score || (b.e.p.ts || 0) - (a.e.p.ts || 0); });
    return { toks: toks, list: out.map(function (x) { return x.e.p; }) };
  }
  function row(p, toks) {
    var img = p.i ? '<img src="' + esc(p.i) + '" alt="" loading="lazy" decoding="async">' : '<span class="row-noimg"></span>';
    return '<li class="row" style="--c:' + esc(p.o) + '"><a href="' + esc(p.u) + '"><time>' + esc(p.d) + "</time>" +
      '<span class="row-main"><span class="row-cat"><i aria-hidden="true"></i>' + esc(p.c) + "</span>" +
      '<span class="row-title">' + mark(p.t, toks) + "</span></span>" +
      '<span class="row-img" aria-hidden="true">' + img + "</span></a></li>";
  }

  roots.forEach(function (root) {
    var page = root.hasAttribute("data-search-page");
    var input = root.querySelector("input[name=q]");
    var res = root.querySelector("[data-search-results]");
    var hint = root.querySelector("[data-search-hint]");
    var count = root.querySelector("[data-search-count]");
    var all = root.querySelector("[data-search-all]");
    var url = root.getAttribute("data-url");
    var max = page ? 100 : 12, timer = null, opener = null;

    function render() {
      var q = input.value.trim();
      if (!q) {
        res.innerHTML = ""; hint.hidden = false; count.hidden = true; if (all) all.hidden = true;
        if (page) history.replaceState(null, "", url);
        return;
      }
      load(root.getAttribute("data-index")).then(function () {
        if (input.value.trim() !== q) return;
        var r = find(q);
        hint.hidden = true;
        count.hidden = false;
        count.textContent = r.list.length ? "“" + q + "” için " + r.list.length + " haber"
          : "“" + q + "” ile ilgili haber bulunamadı. Başka bir sözcükle dene.";
        res.innerHTML = r.list.slice(0, max).map(function (p) { return row(p, r.toks); }).join("");
        if (all) {
          all.hidden = r.list.length <= max;
          all.querySelector("a").href = url + "?q=" + encodeURIComponent(q);
        }
        if (page) history.replaceState(null, "", url + "?q=" + encodeURIComponent(q));
      });
    }
    input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(render, 90); });
    input.addEventListener("focus", function () { load(root.getAttribute("data-index")); });
    // klavye: ↓/↑ sonuçlar arasında gezinir
    root.addEventListener("keydown", function (ev) {
      if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
      var links = [input].concat([].slice.call(res.querySelectorAll("a")));
      var i = links.indexOf(document.activeElement);
      if (i < 0) return;
      ev.preventDefault();
      var n = links[Math.max(0, Math.min(links.length - 1, i + (ev.key === "ArrowDown" ? 1 : -1)))];
      if (n) n.focus();
    });

    if (page) {
      var q0 = new URLSearchParams(location.search).get("q") || "";
      input.value = q0;
      if (q0) render(); else input.focus();
      document.querySelectorAll("[data-search-open]").forEach(function (b) {
        b.addEventListener("click", function (ev) { ev.preventDefault(); input.focus(); input.select(); });
      });
      return;
    }

    function open(ev) {
      if (ev) ev.preventDefault();
      opener = document.activeElement;
      root.hidden = false;
      document.body.classList.add("srch-on");
      input.focus();
      input.select();
      load(root.getAttribute("data-index"));
    }
    function close() {
      root.hidden = true;
      document.body.classList.remove("srch-on");
      if (opener && opener.focus) opener.focus();
    }
    document.querySelectorAll("[data-search-open]").forEach(function (b) { b.addEventListener("click", open); });
    root.querySelectorAll("[data-search-close]").forEach(function (b) { b.addEventListener("click", close); });
    document.addEventListener("keydown", function (ev) {
      var typing = /^(INPUT|TEXTAREA|SELECT)$/.test((ev.target && ev.target.tagName) || "") || (ev.target && ev.target.isContentEditable);
      if (ev.key === "Escape" && !root.hidden) { ev.preventDefault(); close(); }
      else if (root.hidden && ((ev.key === "/" && !typing) || ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k"))) open(ev);
    });
  });
})();
