"""Haftalık Telegram raporu: gerçek okur (Cloudflare Web Analytics), en çok okunanlar, nereden gelindiği, yayın özeti.

Okur verisi için CLOUDFLARE_API_TOKEN gerekir (yalnızca "Account Analytics: Read" yetkili, salt okunur anahtar).
Google arama verisi için GSC_SERVICE_ACCOUNT gerekir (Search Console'a "Kısıtlı" kullanıcı olarak eklenmiş bir Google
hizmet hesabının JSON anahtarı; yalnızca okuma kapsamı istenir). Anahtarlar yoksa o bölümler raporda yer almaz.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from datetime import date, timedelta
from urllib.parse import quote

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


# ── Google Search Console ────────────────────────────────────
GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
GSC_TOKEN_URL = "https://oauth2.googleapis.com/token"
GSC_API = "https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")   # PKCS#1 v1.5 DigestInfo (SHA-256)


def gsc_credentials() -> dict | None:
    raw = (os.environ.get("GSC_SERVICE_ACCOUNT") or "").strip()
    if not raw:
        return None
    try:
        sa = json.loads(raw)
    except ValueError as e:
        raise ReportError("GSC_SERVICE_ACCOUNT okunamadı: JSON anahtar dosyasının tamamı yapıştırılmalı.") from e
    if not sa.get("client_email") or "PRIVATE KEY" not in (sa.get("private_key") or ""):
        raise ReportError("GSC_SERVICE_ACCOUNT eksik: client_email ve private_key alanları olmalı.")
    return sa


def _der(b: bytes, i: int) -> tuple[int, int, int]:
    """DER öğesi: (etiket, içerik başı, içerik sonu)."""
    tag, ln = b[i], b[i + 1]
    i += 2
    if ln & 0x80:
        n = ln & 0x7F
        ln = int.from_bytes(b[i:i + n], "big")
        i += n
    return tag, i, i + ln


def _rsa_key(pem: str) -> tuple[int, int]:
    """PEM (PKCS#8 ya da PKCS#1) RSA özel anahtarından (n, d)."""
    body = "".join(ln.strip() for ln in pem.strip().splitlines() if ln.strip() and not ln.startswith("-----"))
    der = base64.b64decode(body)
    _, s, _ = _der(der, 0)                 # SEQUENCE
    _, _, e1 = _der(der, s)                # version
    t2, _, e2 = _der(der, e1)
    if t2 == 0x30:                         # PKCS#8: AlgorithmIdentifier, ardından OCTET STRING içinde PKCS#1
        _, s3, e3 = _der(der, e2)
        der = der[s3:e3]
        _, s, _ = _der(der, 0)
        _, _, e1 = _der(der, s)
    i, vals = e1, []
    for _ in range(3):                     # n, e, d
        _, a, b = _der(der, i)
        vals.append(int.from_bytes(der[a:b], "big"))
        i = b
    return vals[0], vals[2]


def rs256(msg: bytes, pem: str) -> bytes:
    """RSASSA-PKCS1-v1_5 + SHA-256 imzası (Google hizmet hesabı JWT'si için)."""
    n, d = _rsa_key(pem)
    k = (n.bit_length() + 7) // 8
    t = _SHA256_PREFIX + hashlib.sha256(msg).digest()
    em = b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t
    return pow(int.from_bytes(em, "big"), d, n).to_bytes(k, "big")


def _b64(b: bytes) -> bytes:
    return base64.urlsafe_b64encode(b).rstrip(b"=")


def gsc_access_token(sa: dict) -> str:
    now = int(time.time())
    head = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claim = _b64(json.dumps({"iss": sa["client_email"], "scope": GSC_SCOPE, "aud": GSC_TOKEN_URL,
                             "iat": now, "exp": now + 3600}, separators=(",", ":")).encode())
    msg = head + b"." + claim
    try:
        jwt = msg + b"." + _b64(rs256(msg, sa["private_key"]))
    except (ValueError, IndexError) as e:
        raise ReportError("Hizmet hesabı anahtarı çözülemedi.") from e
    try:
        r = requests.post(GSC_TOKEN_URL, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                               "assertion": jwt.decode()}, timeout=30)
    except requests.RequestException as e:
        raise ReportError(f"Google'a ulaşılamadı: {e}") from e
    tok = (r.json() if r.headers.get("content-type", "").startswith("application/json") else {}).get("access_token")
    if not tok:
        raise ReportError(f"Google oturumu açılamadı (HTTP {r.status_code}); hizmet hesabı anahtarı geçerli mi?")
    return tok


def _gsc_rows(token: str, site: str, body: dict) -> list[dict]:
    try:
        r = requests.post(GSC_API.format(site=quote(site, safe="")), json=body,
                          headers={"Authorization": f"Bearer {token}"}, timeout=40)
    except requests.RequestException as e:
        raise ReportError(f"Search Console'a ulaşılamadı: {e}") from e
    if r.status_code == 403:
        raise ReportError("Hizmet hesabı Search Console'da bu siteye kullanıcı olarak eklenmemiş.")
    if r.status_code != 200:
        raise ReportError(f"Search Console hatası (HTTP {r.status_code}).")
    return r.json().get("rows") or []


def fetch_gsc(sa: dict, site: str, a: date, b: date) -> dict:
    tok = gsc_access_token(sa)
    span_ = lambda x, y: {"startDate": x.isoformat(), "endDate": y.isoformat(), "dataState": "all"}  # noqa: E731
    return {"cur": (_gsc_rows(tok, site, span_(a, b)) or [{}])[0],
            "prev": (_gsc_rows(tok, site, span_(a - timedelta(days=7), a - timedelta(days=1))) or [{}])[0],
            "queries": _gsc_rows(tok, site, {**span_(a, b), "dimensions": ["query"], "rowLimit": 8}),
            "pages": _gsc_rows(tok, site, {**span_(a, b), "dimensions": ["page"], "rowLimit": 5})}


def search_block(g: dict, titles: dict[str, str], site_url: str, esc) -> list[str]:
    cur, prev = g.get("cur") or {}, g.get("prev") or {}
    imp, clk = int(cur.get("impressions") or 0), int(cur.get("clicks") or 0)
    pos = (", ort. sıra " + f"{cur['position']:.1f}".replace(".", ",")) if cur.get("position") else ""
    out = ["<b>🔎 Google araması</b> <i>(Search Console)</i>",
           f"Gösterim: <b>{fmt(imp)}</b>{change(imp, int(prev.get('impressions') or 0))}",
           f"Tıklama: {fmt(clk)}{change(clk, int(prev.get('clicks') or 0))}{pos}"]
    qs = sorted(g.get("queries") or [], key=lambda r: -(r.get("impressions") or 0))
    if qs:
        out += ["En çok gösterim alan aramalar:"]
        out += [f"• {esc(str((r.get('keys') or [''])[0])[:60])} — {fmt(int(r.get('impressions') or 0))} gösterim"
                + (f", {fmt(int(r.get('clicks') or 0))} tık" if r.get("clicks") else "") for r in qs[:6]]
    ps = sorted(g.get("pages") or [], key=lambda r: -(r.get("impressions") or 0))
    if ps:
        base = site_url.rstrip("/")
        out += ["Google'da en çok görünen sayfalar:"]
        for r in ps[:3]:
            url = str((r.get("keys") or [""])[0])
            path = url[len(base):] if url.startswith(base) else url
            out.append(f"• {esc((titles.get(path) or path)[:70])} — {fmt(int(r.get('impressions') or 0))} gösterim")
    return out
