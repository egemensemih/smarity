SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -681,2 +681,13 @@
       need: ["fiyat", "ücret", "zam"]
       need_also: ["türkiye", " tl"]
+
+# ── Haftalık rapor (Telegram) ──────────────────────────────
+# Her hafta bu gün ve saatte (Türkiye saati) son 7 günün raporu gelir; /rapor ile istendiğinde de.
+# Okur verisi Cloudflare Web Analytics'ten okunur: GitHub'da CLOUDFLARE_API_TOKEN sırrı gerekir
+# (Cloudflare → My Profile → API Tokens → yalnızca "Account Analytics: Read" yetkili anahtar).
+report:
+  weekly: true
+  weekday: 0                 # 0 = pazartesi … 6 = pazar
+  hour: 9
+  cf_account_id: "8b50a495bf0914524b1e3d8a5208dc3b"
+  cf_site_tag: "6e2bf0fdd8b84422b162de09fa63eacd"
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -15,4 +15,5 @@
 from . import guides as guidesmod
 from . import photos, policy
+from . import report as reportmod
 from .config import CATEGORIES, DEFAULT_CATEGORY, Config, category_label, indexnow_key
 from .covers import COVER_VERSION, PHOTO_COVER_VERSION, photo_design
@@ -58,7 +59,8 @@
     ("secki", "Yayın yönetmeninin son kararları (neden seçildi / elendi)"),
     ("instagram", "Instagram paylaşımları: durum / kapat / ac / dene"),
+    ("rapor", "Son 7 günün okur ve yayın raporu"),
     ("yardim", "Nasıl kullanılır"),
 ]
-COMMANDS_VERSION = 5
+COMMANDS_VERSION = 6
 COVERLINE_V = 3               # kapak başlığı yazım kuralları değişince eski haberlerin kapak başlıkları yeniden yazılır
 PHOTO_VET_V = 2               # fotoğraf editörü ölçütleri değişince artır: son iki haftanın fotoğrafları yeniden denetlenir
@@ -96,5 +98,7 @@
 📸 <b>Instagram</b> — yayınlanan her haber birkaç dakika içinde carousel ve hikâye olarak Instagram'da paylaşılır. Sıradaki bir haberi mesajındaki <b>Instagram'a gönderme</b> düğmesiyle durdurabilirsin. Tümünü durdurmak için <code>/instagram kapat</code>.
 
-Komutlar: /manset /secki /durum /bekleyen /mod /topla /duraklat /devam /kaynaklar /instagram"""
+📊 <b>Haftalık rapor</b> — her pazartesi sabahı son haftanın okur sayısı, en çok okunanlar, okurların nereden geldiği ve yayın özeti gelir. İstediğin an /rapor.
+
+Komutlar: /manset /secki /durum /bekleyen /mod /topla /duraklat /devam /kaynaklar /instagram /rapor"""
 
 
@@ -1784,4 +1788,6 @@
             if isinstance(res, dict) and res.get("message_id"):
                 self.state["manset_mid"] = res["message_id"]
+        elif cmd == "rapor":
+            self.notify(self.weekly_report_text(), silent=True)
         elif cmd == "instagram":
             if arg in ("kapat", "durdur"):
@@ -2212,4 +2218,76 @@
                 f"Tahmini maliyet: ${self._cost(c):.2f} ({c.get('images', 0)} yapay zeka görseli)\n"
                 f"Mod: {policy.MODES[policy.current_mode(self.cfg, self.state)]}")
+        self.notify(text, silent=True)
+
+    # ── haftalık rapor ──────────────────────────────────────
+    def _path_titles(self) -> dict[str, str]:
+        """Sitedeki adres → başlık (raporda en çok okunanlar için)."""
+        out = {"/": "Ana sayfa", "/haberler/": "Tüm haberler", "/rehber/": "Rehberler", "/ara/": "Arama",
+               "/hakkinda/": "Hakkında", "/instagram/": "Instagram sayfası"}
+        for k in CATEGORIES:
+            out[f"/{k}/"] = f"{category_label(k)} (kategori)"
+        for p in self.store.posts():
+            out[f"/{self.cfg.post_path(p)}/"] = p.get("title", "")
+            for old in p.get("old_paths") or []:
+                out.setdefault(f"/{old.strip('/')}/", p.get("title", ""))
+        for g in guidesmod.load_guides(self.cfg):
+            out[f"/rehber/{g['slug']}/"] = f"Rehber: {g.get('h1') or g.get('title')}"
+        return out
+
+    def weekly_report_text(self) -> str:
+        cfg = self.cfg
+        rc = cfg.raw.get("report") or {}
+        a, b = reportmod.week_range(local(now_utc(), cfg.tz).date())
+        lines = [f"📊 <b>Haftalık rapor</b> · {reportmod.span(a, b)}", ""]
+        tok = reportmod.cf_token()
+        if tok and rc.get("cf_account_id") and rc.get("cf_site_tag"):
+            try:
+                cf = reportmod.fetch_cf(tok, str(rc["cf_account_id"]), str(rc["cf_site_tag"]), a, b)
+                host = urlsplit(cfg.site_url).netloc.lower().removeprefix("www.")
+                lines += reportmod.readers_block(cf, self._path_titles(), host, esc) + [""]
+            except reportmod.ReportError as e:
+                lines += [f"👥 Okur verisi alınamadı: {esc(str(e))}", ""]
+        else:
+            lines += ["👥 Okur verisi için Cloudflare anahtarı (CLOUDFLARE_API_TOKEN) tanımlı değil.", ""]
+
+        def in_week(ts) -> bool:
+            d = local(ts, cfg.tz)
+            return bool(d) and a <= d.date() <= b
+        posts = self.store.posts()
+        pub = [p for p in posts if in_week(p.get("published_at"))]
+        dc = self.state.get("day_counts") or {}
+        upd = sum(int((dc.get((a + timedelta(days=i)).isoformat()) or {}).get("updated", 0)) for i in range(7))
+        cats: dict[str, int] = {}
+        for p in pub:
+            cats[category_label(p.get("category", DEFAULT_CATEGORY))] = cats.get(category_label(p.get("category", DEFAULT_CATEGORY)), 0) + 1
+        guides = guidesmod.load_guides(cfg)
+        g_upd = sum(1 for g in guides for h in g.get("history") or [] if in_week(h.get("at")))
+        ig = [x for x in self.state.get("ig_done") or [] if in_week(x.get("at"))]
+        ig_posts = sum(1 for x in ig if x.get("format", "post") == "post")
+        lines += ["<b>📰 Yayın</b>",
+                  f"Yeni haber: <b>{len(pub)}</b>" + (f" ({', '.join(f'{k} {v}' for k, v in sorted(cats.items(), key=lambda t: -t[1])[:5])})"
+                                                      if cats else ""),
+                  f"Güncellenen haber: {upd}",
+                  f"Rehber: {len(guides)} sayfa, bu hafta {g_upd} güncelleme",
+                  f"Instagram: {ig_posts} gönderi, {len(ig)} hikâye"]
+        return "\n".join(lines).strip()
+
+    def maybe_weekly_report(self) -> None:
+        """Her hafta (ayarlardaki gün ve saatte) bir kez rapor gönder."""
+        rc = self.cfg.raw.get("report") or {}
+        if not rc.get("weekly", True) or not self.tg or not self.chat_id:
+            return
+        now_l = local(now_utc(), self.cfg.tz)
+        if now_l.weekday() != int(rc.get("weekday", 0)) or now_l.hour < int(rc.get("hour", 9)):
+            return
+        key = now_l.date().isoformat()
+        if self.state.get("last_weekly") == key:
+            return
+        self.state["last_weekly"] = key
+        try:
+            text = self.weekly_report_text()
+        except Exception as e:  # noqa: BLE001
+            log.exception("Haftalık rapor hazırlanamadı: %s", e)
+            return
         self.notify(text, silent=True)
 
@@ -3275,4 +3353,5 @@
             log.warning("Telegram düğmeleri yenilenemedi: %s", e)
         self.maybe_summary()
+        self.maybe_weekly_report()
         self.listen(int(self.cfg.get("schedule", "listen_seconds", 120) or 0))
         self.store.save()
@@@SM@@@ FILE haberbot/report.py
"""Haftalık Telegram raporu: gerçek okur (Cloudflare Web Analytics), en çok okunanlar, nereden gelindiği, yayın özeti.

Okur verisi için CLOUDFLARE_API_TOKEN gerekir (yalnızca "Account Analytics: Read" yetkili, salt okunur anahtar).
Anahtar yoksa rapor yalnızca yayın özetiyle gider.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import requests

CF_GRAPHQL = "https://api.cloudflare.com/client/v4/graphql"
TR_DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


class ReportError(Exception):
    pass


def cf_token() -> str:
    return (os.environ.get("CLOUDFLARE_API_TOKEN") or "").strip()


def week_range(today: date) -> tuple[date, date]:
    """Son 7 tam gün (dün dahil)."""
    end = today - timedelta(days=1)
    return end - timedelta(days=6), end


def _flt(site: str, a: date, b: date) -> str:
    return f'{{siteTag: "{site}", date_geq: "{a.isoformat()}", date_leq: "{b.isoformat()}"}}'


def cf_query(account: str, site: str, a: date, b: date) -> str:
    cur, prev = _flt(site, a, b), _flt(site, a - timedelta(days=7), a - timedelta(days=1))
    return f"""{{ viewer {{ accounts(filter: {{accountTag: "{account}"}}) {{
  total: rumPageloadEventsAdaptiveGroups(limit: 1, filter: {cur}) {{ count sum {{ visits }} }}
  prev: rumPageloadEventsAdaptiveGroups(limit: 1, filter: {prev}) {{ count sum {{ visits }} }}
  days: rumPageloadEventsAdaptiveGroups(limit: 7, filter: {cur}, orderBy: [date_ASC]) {{ count sum {{ visits }} dimensions {{ date }} }}
  pages: rumPageloadEventsAdaptiveGroups(limit: 25, filter: {cur}, orderBy: [count_DESC]) {{ count dimensions {{ requestPath }} }}
  refs: rumPageloadEventsAdaptiveGroups(limit: 25, filter: {cur}, orderBy: [count_DESC]) {{ count sum {{ visits }} dimensions {{ refererHost }} }}
}} }} }}"""


def fetch_cf(token: str, account: str, site: str, a: date, b: date) -> dict:
    try:
        r = requests.post(CF_GRAPHQL, json={"query": cf_query(account, site, a, b)},
                          headers={"Authorization": f"Bearer {token}"}, timeout=40)
    except requests.RequestException as e:
        raise ReportError(f"Cloudflare'e ulaşılamadı: {e}") from e
    if r.status_code in (401, 403):
        raise ReportError("Cloudflare anahtarı geçersiz ya da yetkisiz (Account Analytics: Read gerekli).")
    try:
        js = r.json()
    except ValueError as e:
        raise ReportError(f"Cloudflare yanıtı okunamadı (HTTP {r.status_code}).") from e
    if js.get("errors"):
        raise ReportError("Cloudflare: " + "; ".join(str(e.get("message", e))[:160] for e in js["errors"][:2]))
    accs = ((js.get("data") or {}).get("viewer") or {}).get("accounts") or []
    if not accs:
        raise ReportError("Cloudflare hesabı bulunamadı (anahtar bu hesaba yetkili mi?).")
    return accs[0]


def _sum(rows: list[dict]) -> tuple[int, int]:
    """(sayfa görüntüleme, ziyaret)"""
    r = (rows or [{}])[0]
    return int(r.get("count") or 0), int((r.get("sum") or {}).get("visits") or 0)


def source_name(host: str, site_host: str) -> str | None:
    h = (host or "").lower().removeprefix("www.")
    if not h:
        return "Doğrudan"
    if site_host and (h == site_host or h.endswith("." + site_host)):
        return None                        # site içi gezinme
    for key, name in (("news.google", "Google Haberler"), ("google", "Google"), ("bing", "Bing"), ("yandex", "Yandex"),
                      ("duckduckgo", "DuckDuckGo"), ("instagram", "Instagram"), ("facebook", "Facebook"),
                      ("t.co", "X"), ("x.com", "X"), ("twitter", "X"), ("t.me", "Telegram"), ("telegram", "Telegram"),
                      ("whatsapp", "WhatsApp"), ("linkedin", "LinkedIn"), ("reddit", "Reddit"), ("chatgpt", "ChatGPT"),
                      ("openai", "ChatGPT"), ("perplexity", "Perplexity"), ("claude.ai", "Claude")):
        if key in h:
            return name
    return h


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def change(cur: int, prev: int) -> str:
    if not prev:
        return ""
    pct = round((cur - prev) * 100 / prev)
    return f" (önceki hafta {fmt(prev)}, {'+' if pct >= 0 else '-'}%{abs(pct)})"


def span(a: date, b: date) -> str:
    if a.month == b.month:
        return f"{a.day}–{b.day} {TR_MONTHS[b.month - 1]}"
    return f"{a.day} {TR_MONTHS[a.month - 1]} – {b.day} {TR_MONTHS[b.month - 1]}"


def readers_block(cf: dict, titles: dict[str, str], site_host: str, esc) -> list[str]:
    pv, visits = _sum(cf.get("total"))
    ppv, pvisits = _sum(cf.get("prev"))
    out = ["<b>👥 Okur</b> <i>(Cloudflare, çerezsiz ölçüm)</i>",
           f"Ziyaret: <b>{fmt(visits)}</b>{change(visits, pvisits)}",
           f"Sayfa görüntüleme: {fmt(pv)}{change(pv, ppv)}"]
    days = [((r.get("dimensions") or {}).get("date"), int((r.get("sum") or {}).get("visits") or 0)) for r in cf.get("days") or []]
    if days:
        top_day = max(days, key=lambda t: t[1])
        if top_day[0] and top_day[1]:
            out.append(f"En yoğun gün: {TR_DAYS[date.fromisoformat(top_day[0]).weekday()]} ({fmt(top_day[1])} ziyaret)")
    srcs: dict[str, int] = {}
    for r in cf.get("refs") or []:
        name = source_name((r.get("dimensions") or {}).get("refererHost", ""), site_host)
        if name:
            srcs[name] = srcs.get(name, 0) + int((r.get("sum") or {}).get("visits") or 0)
    srcs = {k: v for k, v in srcs.items() if v}
    if srcs:
        out += ["", "<b>🧭 Nereden geldiler</b> <i>(ziyaret)</i>",
                " · ".join(f"{esc(k)} {fmt(v)}" for k, v in sorted(srcs.items(), key=lambda t: -t[1])[:7])]
    pages = []
    for r in cf.get("pages") or []:
        path = (r.get("dimensions") or {}).get("requestPath") or ""
        if not path or path.startswith(("/api/", "/static/", "/img/")) or path.endswith((".xml", ".txt", ".json")):
            continue
        key = "/" + path.strip("/") + "/" if path.strip("/") else "/"
        pages.append((titles.get(key) or path, int(r.get("count") or 0)))
    if pages:
        out += ["", "<b>🔥 En çok okunanlar</b> <i>(görüntüleme)</i>"]
        out += [f"{i}. {esc(t[:80])} — {fmt(n)}" for i, (t, n) in enumerate(pages[:6], 1)]
    return out
@@@SM@@@ FILE tests/test_report.py
"""Haftalık rapor: Cloudflare okur verisi, kaynak adları, yayın özeti ve haftada bir gönderim."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import haberbot.app as appmod  # noqa: E402
from haberbot import report as R  # noqa: E402
from haberbot.util import iso, now_utc  # noqa: E402
from tests.test_home import _App, _post  # noqa: E402


def test_source_names_and_numbers():
    assert R.source_name("", "smarity.com.tr") == "Doğrudan"
    assert R.source_name("www.google.com.tr", "smarity.com.tr") == "Google"
    assert R.source_name("news.google.com", "smarity.com.tr") == "Google Haberler"
    assert R.source_name("l.instagram.com", "smarity.com.tr") == "Instagram"
    assert R.source_name("smarity.com.tr", "smarity.com.tr") is None          # site içi
    assert R.fmt(12345) == "12.345"
    assert R.change(120, 100) == " (önceki hafta 100, +%20)" and R.change(80, 100) == " (önceki hafta 100, -%20)"
    q = R.cf_query("acc", "site", R.date(2026, 11, 16), R.date(2026, 11, 22))
    assert 'date_geq: "2026-11-16"' in q and 'date_geq: "2026-11-09"' in q and "rumPageloadEventsAdaptiveGroups" in q


CF = {"total": [{"count": 900, "sum": {"visits": 400}}], "prev": [{"count": 600, "sum": {"visits": 320}}],
      "days": [{"sum": {"visits": 50}, "dimensions": {"date": "2026-11-19"}},
               {"sum": {"visits": 90}, "dimensions": {"date": "2026-11-20"}}],
      "pages": [{"count": 300, "dimensions": {"requestPath": "/"}},
                {"count": 120, "dimensions": {"requestPath": "/teknoloji/2026/11/haber-1"}},
                {"count": 99, "dimensions": {"requestPath": "/sitemap.xml"}}],
      "refs": [{"sum": {"visits": 200}, "dimensions": {"refererHost": "www.google.com"}},
               {"sum": {"visits": 30}, "dimensions": {"refererHost": "google.com.tr"}},
               {"sum": {"visits": 100}, "dimensions": {"refererHost": ""}},
               {"sum": {"visits": 70}, "dimensions": {"refererHost": "smarity.com.tr"}}]}


def test_weekly_report_text(monkeypatch):
    with _App() as (cfg, a):
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test")
        monkeypatch.setattr(R, "fetch_cf", lambda *_a: CF)
        p = _post(1, 30, title="Togg fiyat listesi açıklandı", cat="otomotiv")
        p["path"] = "teknoloji/2026/11/haber-1"
        a.store.save_post(p)
        a.state["ig_done"] = [{"id": "p01", "at": iso(now_utc() - timedelta(days=2)), "format": "post"},
                              {"id": "p02", "at": "2020-01-01T00:00:00Z", "format": "story"}]
        t = a.weekly_report_text()
        assert "Ziyaret: <b>400</b> (önceki hafta 320, +%25)" in t
        assert "Google 230" in t and "Doğrudan 100" in t and "smarity" not in t.split("Nereden")[1].split("\n")[1]
        assert "1. Ana sayfa — 300" in t and "2. Togg fiyat listesi açıklandı — 120" in t and "sitemap" not in t
        assert "Yeni haber: <b>1</b> (Otomotiv 1)" in t and "Instagram: 1 gönderi, 1 hikâye" in t
        monkeypatch.delenv("CLOUDFLARE_API_TOKEN")
        assert "CLOUDFLARE_API_TOKEN" in a.weekly_report_text()                 # anahtar yoksa yayın özeti yine gelir


def test_weekly_report_sent_once_on_monday(monkeypatch):
    with _App() as (cfg, a):
        from haberbot.telegram import MockTelegram
        a.tg = a.tg or MockTelegram(cfg.root / "tg")
        monday = datetime(2026, 11, 30, 7, 30, tzinfo=timezone.utc)          # Pazartesi 10:30 (İstanbul)
        monkeypatch.setattr(appmod, "now_utc", lambda: monday)
        a.maybe_weekly_report()
        a.maybe_weekly_report()
        out = (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8")
        assert out.count("Haftalık rapor") == 1 and "23–29 Kasım" in json.loads(out.splitlines()[-1])["text"]
        monkeypatch.setattr(appmod, "now_utc", lambda: datetime(2026, 12, 1, 7, 30, tzinfo=timezone.utc))  # salı
        a.maybe_weekly_report()
        assert (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8").count("Haftalık rapor") == 1
@@@SM@@@ SHA
4fb4d4c5bfa013cab8d024cf129028e44ba752cbf6807082b682c984878350e5 config.yaml
ee2994d56f903ecd97f19e00525551837dcfb21365cd05265bb3ee679ff24bd7 haberbot/app.py
f3d866af77c8c09d66632e10dbf3b18cef8907d44d8761ca988cee17a426814e haberbot/report.py
de4f4ce004db243f642a92864ab9b066eb57eec0f1b5146db177bff42d799f47 tests/test_report.py
