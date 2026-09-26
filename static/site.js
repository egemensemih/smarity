(function () {
  // Göreli zaman: "12 dk önce"
  var now = Date.now();
  document.querySelectorAll("time[data-rel]").forEach(function (t) {
    var d = Date.parse(t.getAttribute("datetime"));
    if (!d) return;
    var m = Math.round((now - d) / 60000);
    var s = m < 1 ? "az önce" : m < 60 ? m + " dk önce" : m < 1440 ? Math.round(m / 60) + " saat önce" : m < 10080 ? Math.round(m / 1440) + " gün önce" : null;
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
    if (!track || slides.length < 2) { if (slides[0]) slides[0].classList.add("on"); return; }
    var dur = +car.getAttribute("data-interval") || 6500;
    car.style.setProperty("--dur", dur + "ms");
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var cur = 0, timer = null, userStopped = reduce, hover = false, visible = true, settleT = null;

    function setCur(i) {
      if (i === cur && slides[i].classList.contains("on")) return;
      cur = i;
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

  // Menü: bir bağlantıya basınca kapansın
  document.querySelectorAll(".menu-panel a").forEach(function (a) {
    a.addEventListener("click", function () { var m = a.closest("details"); if (m) m.open = false; });
  });
})();
