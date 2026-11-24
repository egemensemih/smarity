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
