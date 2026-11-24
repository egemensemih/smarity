"""Sürekli güncel rehber sayfaları (/rehber/…): Togg fiyat listesi, IMEI kayıt ücreti, şarj ücretleri gibi.

Rehber, sitede yayımlanmış ilgili haberlerden (onların kaynaklarından) derlenir; yeni ilgili bir haber gelince
yeniden yazılır. Uydurma rakam olmasın diye rehberdeki her rakam dayandığı haberlerde birebir geçmek zorundadır;
geçmeyen varsa yeni sürüm yayımlanmaz, eskisi kalır.
"""
from __future__ import annotations

import re
from pathlib import Path

from .store import read_json, write_json
from .util import hours_since, tr_date

GUIDE_SCHEMA = {
    "type": "object",
    "properties": {
        "seo_title": {"type": "string"},
        "meta_description": {"type": "string"},
        "summary": {"type": "string"},
        "body": {"type": "string"},
        "faq": {"type": "array", "items": {"type": "object", "properties": {
            "q": {"type": "string"}, "a": {"type": "string"}}, "required": ["q", "a"]}},
        "changes": {"type": "string"},
        "used": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["seo_title", "meta_description", "summary", "body", "faq", "changes", "used"],
}

_NUM = re.compile(r"\d[\d.,]*\d|\d")


def _low(s: str) -> str:
    """Karşılaştırma için küçük harf; i/ı/İ/I farkı yok sayılır (IMEI = imei, İPHONE = iphone, ışık = isik)."""
    return (s or "").replace("İ", "i").replace("I", "i").lower().replace("ı", "i")


def guide_list(cfg) -> list[dict]:
    g = cfg.raw.get("guides") or {}
    if not g.get("enabled", True):
        return []
    return [x for x in (g.get("list") or []) if x and x.get("slug") and x.get("title") and x.get("match")]


def guide_path(cfg, slug: str) -> Path:
    return cfg.root / "content" / "guides" / f"{slug}.json"


def load_guides(cfg) -> list[dict]:
    """Yayımlanmış rehberler (ayarlardaki sırayla)."""
    out = []
    for spec in guide_list(cfg):
        g = read_json(guide_path(cfg, spec["slug"]), None)
        if g and g.get("body"):
            out.append({**g, "spec": spec})
    return out


def matches(spec: dict, post: dict) -> bool:
    """Haber bu rehbere girer mi: başlıkta ya da etiketlerde `match` sözcüklerinden biri; başlıkta (varsa) `need`
    sözcüklerinden biri ve (varsa) `need_also` sözcüklerinden biri geçmeli; `skip` sözcükleri geçmemeli; `categories`
    verilmişse haber o kategorilerden birinde olmalı. `match_in: title` ise etiketlere bakılmaz."""
    if spec.get("categories") and post.get("category") not in spec["categories"]:
        return False
    title = _low(post.get("title", ""))
    hay = title + " | " + _low(" ".join(list(post.get("tags") or []) + list(post.get("entities") or [])))
    if spec.get("match_in") == "title":
        hay = title
    if not any(_low(m) in hay for m in spec.get("match") or []):
        return False
    for key in ("need", "need_also"):
        if spec.get(key) and not any(_low(n) in title for n in spec[key]):
            return False
    if any(_low(s) in hay for s in spec.get("skip") or []):
        return False
    return True


def related_posts(spec: dict, posts: list[dict], lookback_days: float, limit: int) -> list[dict]:
    out = []
    for p in posts:   # yeniden eskiye
        if hours_since(p.get("published_at")) > lookback_days * 24:
            break
        if matches(spec, p):
            out.append(p)
            if len(out) >= limit:
                break
    return out


def numbers(text: str) -> set[str]:
    """Metindeki 3+ haneli rakamlar (nokta/virgül ayırıcıları atılmış). Yıllar (2000–2039) sayılmaz."""
    out = set()
    for m in _NUM.findall(text or ""):
        d = re.sub(r"\D", "", m)
        if len(d) >= 3 and not (len(d) == 4 and 2000 <= int(d) <= 2039):
            out.add(d)
    return out


def unsupported_numbers(body: str, posts: list[dict]) -> list[str]:
    """Rehberde geçip dayandığı haberlerin hiçbirinde birebir geçmeyen rakamlar (uydurma ya da hesaplanmış)."""
    have = set()
    for p in posts:
        have |= numbers(" ".join([p.get("title", ""), p.get("summary", ""), p.get("body", "")]))
    return sorted(numbers(body) - have)


def signature(posts: list[dict]) -> list[str]:
    return [f"{p['id']}@{p.get('refreshed_at') or p.get('published_at') or ''}" for p in posts]


def guide_system(site_name: str) -> str:
    return f"""You are the senior editor of "{site_name}", a Turkish technology news site. You maintain an evergreen
GUIDE page in Türkiye Türkçesi that people find on Google when they search for the current Türkiye price, fee or
rule of something (for example "Togg fiyat listesi", "IMEI kayıt ücreti", "elektrikli araç şarj ücretleri").
You write the guide ONLY from the RELATED ARTICLES, which our newsroom has already published with sources.

Accuracy rules (most important):
- Every number in the guide (prices, fees, percentages, capacities, dates) must appear in the RELATED ARTICLES and
  must be written with exactly the same digits as there (1.328.000 TL stays 1.328.000 TL). Never compute, convert,
  round, add up, average or estimate numbers, and never use your own memory.
- The newest article wins: when two articles give different values for the same thing, use the newest one and,
  if useful, mention the previous value as "önceki fiyat" with its month.
- Say for which month/date each price or fee is valid ("Kasım 2026 fiyat listesine göre"). If the newest information
  is older than about two months, say clearly that it is the last announced value.
- If the articles do not contain something a reader would expect (a model's price, a campaign), do not invent it;
  leave it out or say in one short sentence that it has not been announced.

Form:
- body: Markdown, 300–900 words. Start with a 2–3 sentence answer paragraph: the current key numbers and the date
  they are valid for (this is what searchers want). Then "## " sections; use Markdown tables for prices and fees
  (columns such as Model / Versiyon / Fiyat / Geçerlilik). Group logically (by model, brand or type). Add a short
  section on what changed recently. Do not add links, a sources list or a "last updated" line; the site adds them.
- summary: 1–2 sentences, ≤180 characters, the current headline numbers with their date.
- seo_title: ≤60 characters, natural search phrase with the current month and year if prices are monthly
  (e.g. "Togg fiyat listesi Kasım 2026: güncel T10X ve T10F fiyatları").
- meta_description: ≤155 characters.
- faq: 3–5 short questions people search for, each answered in 1–2 sentences from the articles (same number rules).
- changes: one short Turkish sentence on what changed compared to the PREVIOUS VERSION ("İlk sürüm." if none).
- used: the ids of the articles you actually used.
Tone: calm, clear, helpful; no hype, no clickbait, no advice on whether to buy."""


def guide_user(spec: dict, posts: list[dict], today: str, tz: str, previous: dict | None) -> str:
    parts = [f"TODAY: {today}", "",
             f"GUIDE: {spec.get('h1') or spec['title']}",
             f"COVERS: {spec.get('about') or spec['title']}", "", "RELATED ARTICLES (newest first):"]
    for p in posts:
        parts += [f"--- id: {p['id']} | published: {tr_date(p.get('published_at'), tz, with_time=False)}"
                  + (f" | updated: {tr_date(p.get('refreshed_at'), tz, with_time=False)}" if p.get("refreshed_at") else ""),
                  f"title: {p.get('title', '')}", f"summary: {p.get('summary', '')}",
                  f"sources: {', '.join(s.get('name', '') for s in p.get('sources') or [])}",
                  (p.get("body") or "")[:5000], ""]
    if previous and previous.get("body"):
        parts += ["PREVIOUS VERSION OF THE GUIDE (keep its useful structure; update the numbers from the articles):",
                  previous["body"][:6000]]
    return "\n".join(parts)


def save_guide(cfg, g: dict) -> None:
    write_json(guide_path(cfg, g["slug"]), g)
