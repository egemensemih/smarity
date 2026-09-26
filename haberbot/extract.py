"""Haberin tam metnini kaynağından okur (robots.txt kurallarına uyarak).

Tam metin yalnızca yapay zekanın daha doğru özet çıkarması için kullanılır;
sitede yayınlanmaz. Okunamazsa RSS özetiyle devam edilir.
"""
from __future__ import annotations

import urllib.robotparser
from urllib.parse import urlsplit

import requests

from .util import log, strip_html

UA_TOKEN = "SmarityBot"
UA = f"Mozilla/5.0 (compatible; {UA_TOKEN}/1.0)"
_robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def _allowed(url: str) -> bool:
    p = urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": UA}, timeout=8)
            if r.status_code >= 400:
                rp = None  # robots.txt yok → serbest
            else:
                rp.parse(r.text.splitlines())
        except requests.RequestException:
            rp = None
        _robots_cache[base] = rp
    rp = _robots_cache[base]
    return True if rp is None else rp.can_fetch(UA_TOKEN, url)


def _fallback_extract(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
        t.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    paras = [strip_html(p.get_text(" ")) for p in root.find_all(["p", "h2", "h3", "li"])]
    paras = [p for p in paras if len(p) > 50]
    return "\n\n".join(paras)


_html_cache: dict[str, str] = {}


def fetch_html(url: str) -> str:
    """Sayfanın HTML'i (robots.txt'e uyarak; aynı çalışmada ikinci kez indirilmez)."""
    if url in _html_cache:
        return _html_cache[url]
    html = ""
    try:
        if not _allowed(url):
            log.info("robots.txt izin vermiyor, sayfa okunmadı: %s", url)
        else:
            r = requests.get(url, headers={"User-Agent": UA, "Accept": "text/html"}, timeout=15)
            if r.status_code < 400 and "html" in r.headers.get("content-type", "html"):
                html = r.text[:3_000_000]
    except requests.RequestException as e:
        log.info("Sayfa okunamadı (%s): %s", type(e).__name__, url)
    _html_cache[url] = html
    return html


def full_text(url: str, max_chars: int = 7000) -> str:
    html = fetch_html(url)
    if not html:
        return ""
    text = ""
    try:
        import trafilatura  # type: ignore

        text = trafilatura.extract(html, include_comments=False, include_tables=False,
                                   favor_precision=True) or ""
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001
        log.debug("trafilatura hata: %s", e)
    if len(text) < 300:
        text = _fallback_extract(html)
    return text[:max_chars]
