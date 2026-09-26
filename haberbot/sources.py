"""Kaynakları (RSS/Atom ve basit HTML listeleri) okur, ortak bir biçime çevirir."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import requests
from lxml import etree

from .config import Config
from .util import (clip, domain_of, iso, log, normalize_url, now_utc, parse_iso,
                   publisher_name, short_hash, slugify, strip_html)

UA = "Mozilla/5.0 (compatible; SmarityBot/1.0; +https://github.com/)"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rss1": "http://purl.org/rss/1.0/",
    "media": "http://search.yahoo.com/mrss/",
}
IMG_IN_HTML = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.I)


def _feed_image(el, html_parts: list[str]) -> str:
    """Besleme öğesinin görseli: media:content / media:thumbnail / enclosure ya da içerikteki ilk <img>."""
    best, bw = "", -1
    for m in el.iter("{http://search.yahoo.com/mrss/}content", "{http://search.yahoo.com/mrss/}thumbnail"):
        url = m.get("url") or ""
        typ = (m.get("type") or m.get("medium") or "image").lower()
        if not url or ("image" not in typ and not re.search(r"\.(jpe?g|png|webp|avif)(\?|$)", url, re.I)):
            continue
        try:
            w = int(m.get("width") or 0)
        except ValueError:
            w = 0
        if w > bw:
            best, bw = url, w
    if best:
        return best
    for enc in list(el.iter("enclosure")) + [l for l in el.iter("{http://www.w3.org/2005/Atom}link") if l.get("rel") == "enclosure"]:
        url = enc.get("url") or enc.get("href") or ""
        if url and (enc.get("type") or "").lower().startswith("image"):
            return url
    for h in html_parts:
        m = IMG_IN_HTML.search(h or "")
        if m:
            return m.group(1)
    return ""


def _parse_date(s: str | None):
    if not s:
        return None
    s = s.strip()
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError, IndexError):
        pass
    return parse_iso(s)


def _text(el, path: str) -> str:
    if el is None:
        return ""
    found = el.find(path, NS)
    if found is None:
        return ""
    return "".join(found.itertext()).strip()


def parse_feed(xml_bytes: bytes) -> list[dict]:
    """RSS 2.0 / Atom / RSS 1.0 → [{title, link, summary, published}]"""
    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True, huge_tree=True)
    root = etree.fromstring(xml_bytes, parser=parser)
    if root is None:
        return []
    out = []
    tag = etree.QName(root).localname.lower()

    if tag == "feed":  # Atom
        for e in root.findall("atom:entry", NS):
            link = ""
            for l in e.findall("atom:link", NS):
                if l.get("rel", "alternate") == "alternate" and l.get("href"):
                    link = l.get("href")
                    break
            summary = _text(e, "atom:summary") or _text(e, "atom:content")
            out.append({
                "title": strip_html(_text(e, "atom:title")),
                "link": link,
                "summary": strip_html(summary),
                "published": _parse_date(_text(e, "atom:published") or _text(e, "atom:updated")),
                "image": _feed_image(e, [_text(e, "atom:content"), _text(e, "atom:summary")]),
            })
        return out

    items = root.findall("./channel/item") or root.findall(".//item")
    if not items:
        items = root.findall("rss1:item", NS)
    for it in items:
        link = _text(it, "link") or _text(it, "rss1:link")
        if not link:
            guid = it.find("guid")
            if guid is not None and (guid.text or "").startswith("http"):
                link = guid.text.strip()
        summary = _text(it, "description") or _text(it, "rss1:description")
        if len(strip_html(summary)) < 80:
            summary = _text(it, "content:encoded") or summary
        comments = _text(it, "comments")
        out.append({
            "title": strip_html(_text(it, "title") or _text(it, "rss1:title")),
            "link": link,
            "summary": strip_html(summary),
            "published": _parse_date(_text(it, "pubDate") or _text(it, "dc:date")),
            "comments": comments,
            "image": _feed_image(it, [_text(it, "content:encoded"), _text(it, "description")]),
        })
    return out


def parse_html_listing(html_bytes: bytes, base_url: str, pattern: str) -> list[dict]:
    """RSS'i olmayan sayfalar: desenle eşleşen bağlantıları haber olarak al."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_bytes, "lxml")
    rx = re.compile(pattern)
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].split("#")[0].split("?")[0]
        path = href
        if href.startswith("http"):
            if domain_of(href) != domain_of(base_url):
                continue
            path = "/" + href.split("/", 3)[3] if href.count("/") >= 3 else "/"
        if not rx.search(path):
            continue
        full = urljoin(base_url, href)
        if full in seen:
            continue
        heading = a.find(["h1", "h2", "h3", "h4"])
        title = strip_html(heading.get_text(" ")) if heading else strip_html(a.get_text(" "))
        if len(title) < 12:
            continue
        seen.add(full)
        out.append({"title": clip(title, 200), "link": full, "summary": "", "published": None})
    return out


def _fetch(url: str, timeout: int = 20) -> bytes:
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "*/*"}, timeout=timeout)
    r.raise_for_status()
    return r.content[:5_000_000]


def _load_source(cfg: Config, src: dict) -> list[dict]:
    stype = src.get("type", "rss")
    if cfg.fixtures_dir:
        base = cfg.fixtures_dir / slugify(src["name"])
        path = base.with_suffix(".html" if stype == "html" else ".xml")
        if not path.exists():
            return []
        raw = path.read_bytes()
    else:
        raw = _fetch(src["url"])
    if stype == "html":
        return parse_html_listing(raw, src["url"], src.get("link_pattern", "."))
    return parse_feed(raw)


def fetch_all(cfg: Config, store) -> list[dict]:
    """Tüm kaynakları paralel okur. Kaynak sağlığını store.state'e yazar."""
    sources = cfg.sources
    health = store.state.setdefault("source_health", {})
    results: list[dict] = []

    def work(src):
        try:
            return src, _load_source(cfg, src), None
        except Exception as e:  # noqa: BLE001
            return src, [], f"{type(e).__name__}: {e}"[:200]

    with ThreadPoolExecutor(max_workers=8) as ex:
        for src, entries, err in ex.map(work, sources):
            h = health.setdefault(src["name"], {})
            if err:
                h["fails"] = h.get("fails", 0) + 1
                h["last_error"] = err
                log.warning("Kaynak okunamadı: %s → %s", src["name"], err)
                continue
            h["fails"] = 0
            h["last_ok"] = iso(now_utc())
            h["count"] = len(entries)
            h.pop("last_error", None)
            for e in entries:
                if not e.get("title") or not e.get("link"):
                    continue
                link = e["link"].strip()
                credit, credit_url = src["name"], link
                via = None
                if src.get("credit_linked_site"):
                    credit = publisher_name(link)
                    via = src["name"]
                results.append({
                    "key": short_hash(normalize_url(link), n=16),
                    "source": src["name"],
                    "kind": src.get("kind", "media"),
                    "credit": credit,
                    "url": link,
                    "via": via,
                    "via_url": e.get("comments") or None,
                    "title": clip(e["title"], 220),
                    "summary": clip(e.get("summary") or "", 600),
                    "published": iso(e["published"]) if e.get("published") else None,
                    "html_source": src.get("type") == "html",
                    "image": (e.get("image") or "").strip()[:600] or None,
                })
            log.info("Kaynak %-22s %3d öğe", src["name"], len(entries))
    return results
