"""Küçük yardımcılar: zaman, metin, slug, hash, loglama."""
from __future__ import annotations

import hashlib
import html
import logging
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from zoneinfo import ZoneInfo

log = logging.getLogger("haberbot")


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


# ── zaman ────────────────────────────────────────────────────
def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def hours_since(s: str | None, ref: datetime | None = None) -> float:
    dt = parse_iso(s)
    if dt is None:
        return 1e9
    ref = ref or now_utc()
    return (ref - dt).total_seconds() / 3600


TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
             "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
TR_DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def local(dt: datetime | str | None, tz: str) -> datetime | None:
    if isinstance(dt, str):
        dt = parse_iso(dt)
    if dt is None:
        return None
    return dt.astimezone(ZoneInfo(tz))


def tr_date(dt: datetime | str | None, tz: str, with_time: bool = True) -> str:
    d = local(dt, tz)
    if d is None:
        return ""
    s = f"{d.day} {TR_MONTHS[d.month - 1]} {d.year}"
    if with_time:
        s += f", {d:%H:%M}"
    return s


# ── metin ────────────────────────────────────────────────────
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(s: str | None) -> str:
    if not s:
        return ""
    s = _TAG_RE.sub(" ", s)
    s = html.unescape(s)
    return _WS_RE.sub(" ", s).strip()


def clip(s: str, n: int) -> str:
    s = s.strip()
    if len(s) <= n:
        return s
    cut = s[: n - 1].rsplit(" ", 1)[0]
    return cut.rstrip(" ,.;:-") + "…"


_TR_MAP = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "I": "i", "İ": "i",
    "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u", "â": "a", "î": "i", "û": "u",
})


def slugify(text: str, max_len: int = 72) -> str:
    s = text.translate(_TR_MAP)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > max_len:
        s = s[:max_len].rsplit("-", 1)[0]
    return s or "haber"


def tr_upper(s: str) -> str:
    return s.replace("i", "İ").replace("ı", "I").upper()


def short_hash(*parts: str, n: int = 10) -> str:
    h = hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()
    return h[:n]


_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
             "ref", "ref_src", "fbclid", "gclid", "mc_cid", "mc_eid", "guccounter"}


def normalize_url(url: str) -> str:
    try:
        p = urlsplit(url.strip())
    except ValueError:
        return url.strip()
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in _TRACKING]
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = p.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(q), ""))


def domain_of(url: str) -> str:
    try:
        host = urlsplit(url).netloc.lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


# Bilinen yayıncı alan adları → okunaklı ad (topluluk kaynaklarında kredi için)
PUBLISHERS = {
    "bloomberg.com": "Bloomberg", "reuters.com": "Reuters", "nytimes.com": "The New York Times",
    "wsj.com": "The Wall Street Journal", "ft.com": "Financial Times", "theverge.com": "The Verge",
    "techcrunch.com": "TechCrunch", "arstechnica.com": "Ars Technica", "wired.com": "WIRED",
    "theinformation.com": "The Information", "cnbc.com": "CNBC", "bbc.co.uk": "BBC", "bbc.com": "BBC",
    "theguardian.com": "The Guardian", "washingtonpost.com": "The Washington Post",
    "axios.com": "Axios", "semafor.com": "Semafor", "404media.co": "404 Media",
    "technologyreview.com": "MIT Technology Review", "venturebeat.com": "VentureBeat",
    "github.com": "GitHub", "arxiv.org": "arXiv", "openai.com": "OpenAI", "anthropic.com": "Anthropic",
    "deepmind.google": "Google DeepMind", "blog.google": "Google", "ai.meta.com": "Meta AI",
    "huggingface.co": "Hugging Face", "mistral.ai": "Mistral AI", "x.ai": "xAI",
    "nvidia.com": "NVIDIA", "blogs.nvidia.com": "NVIDIA", "microsoft.com": "Microsoft",
    "apple.com": "Apple", "simonwillison.net": "Simon Willison", "youtube.com": "YouTube",
    "engadget.com": "Engadget", "electrek.co": "Electrek", "ign.com": "IGN", "polygon.com": "Polygon",
    "gsmarena.com": "GSMArena", "newatlas.com": "New Atlas", "spectrum.ieee.org": "IEEE Spectrum",
    "carscoops.com": "Carscoops", "autocar.co.uk": "Autocar", "motor1.com": "Motor1", "insideevs.com": "InsideEVs",
    "gamesindustry.biz": "GamesIndustry.biz", "eurogamer.net": "Eurogamer", "videogameschronicle.com": "VGC",
    "pcgamer.com": "PC Gamer", "kotaku.com": "Kotaku", "9to5mac.com": "9to5Mac", "9to5google.com": "9to5Google",
    "macrumors.com": "MacRumors", "interestingengineering.com": "Interesting Engineering", "nature.com": "Nature",
    "science.org": "Science", "nasa.gov": "NASA", "spacex.com": "SpaceX", "tesla.com": "Tesla", "samsung.com": "Samsung",
    "news.samsung.com": "Samsung", "crunchbase.com": "Crunchbase News", "news.crunchbase.com": "Crunchbase News",
    "sifted.eu": "Sifted", "eu-startups.com": "EU-Startups", "webrazzi.com": "Webrazzi", "egirisim.com": "Egirisim",
    "webtekno.com": "Webtekno", "shiftdelete.net": "ShiftDelete.Net", "donanimhaber.com": "DonanımHaber",
    "log.com.tr": "LOG", "aa.com.tr": "Anadolu Ajansı",
}


def publisher_name(url: str) -> str:
    d = domain_of(url)
    if d in PUBLISHERS:
        return PUBLISHERS[d]
    parts = d.split(".")
    for i in range(1, len(parts) - 1):
        cand = ".".join(parts[i:])
        if cand in PUBLISHERS:
            return PUBLISHERS[cand]
    return d
