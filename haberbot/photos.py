"""Haber fotoğrafları: şirketin resmi görselleri ya da kaynak haberin görselleri, kredisiyle.

Sıra: resmi kaynak (şirketin kendi duyurusu) → diğer kaynaklar. Her kaynağın sayfasından
paylaşım görseli (og:image), yapılandırılmış veri görseli ve metin içindeki büyük fotoğraflar alınır.
Küçük/logo/ikon görseller ve aynı fotoğrafın farklı boyutları elenir.

Ana fotoğraf ve galerinin ilk günleri için kopyalar sitede tutulur (hızlı ve güvenilir);
eski galerilerde yer kazanmak için yerel kopya silinip kaynaktaki adres kullanılır.
Hak sahibi talep ederse fotoğraflar Telegram'dan tek tuşla kaldırılır.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from PIL import Image, ImageOps, ImageStat

from .extract import UA, fetch_html
from .util import log

MAX_BYTES = 15_000_000
MIN_W, MIN_H = 600, 320
BAD_URL = re.compile(
    r"(logo|icon|favicon|sprite|avatar|gravatar|/authors?/|profile[-_]?(pic|photo|image)|placeholder|blank\.|"
    r"pixel|spacer|badge|emoji|/ads?/|advert|doubleclick|banner-ad|/share|social[-_]|newsletter|"
    r"default[-_]?(image|og|thumb)|fallback|wp-content/plugins|gstatic\.com/images/branding)", re.I)
BAD_EXT = (".svg", ".gif", ".ico", ".bmp")
SIZE_SUFFIX = re.compile(r"-\d{2,4}x\d{2,4}(?=\.\w{3,4}$)")
RESIZE_KEYS = {"w", "h", "width", "height", "resize", "fit", "quality", "q", "crop", "strip", "ssl", "format", "auto"}
LD_TYPES = {"newsarticle", "article", "blogposting", "reportagenewsarticle", "product", "webpage", "report",
            "techarticle", "analysisnewsarticle"}


# ── adaylar ───────────────────────────────────────────────
def _abs(u: str, base: str) -> str:
    u = (u or "").strip().split(" ")[0]
    if not u or u.startswith("data:"):
        return ""
    u = urljoin(base, u)
    if u.startswith("//"):
        u = "https:" + u
    if u.startswith("http://"):
        u = "https://" + u[7:]
    return u if u.startswith("https://") else ""


def _key(u: str) -> str:
    """Aynı fotoğrafın farklı boyut/parametre sürümlerini birleştirmek için anahtar."""
    p = urlsplit(u)
    path = SIZE_SUFFIX.sub("", p.path.lower())
    q = "&".join(x for x in p.query.split("&") if x and x.split("=")[0].lower() not in RESIZE_KEYS)
    return urlunsplit(("", p.netloc.lower(), path, q, ""))


def _largest_src(srcset: str) -> tuple[str, int]:
    best, bw = "", -1
    for part in (srcset or "").split(","):
        bits = part.strip().split()
        if not bits:
            continue
        w = 0
        if len(bits) > 1:
            m = re.match(r"(\d+(?:\.\d+)?)([wx])", bits[1])
            if m:
                w = int(float(m.group(1)) * (1 if m.group(2) == "w" else 1000))
        if w > bw:
            best, bw = bits[0], w
    return best, max(bw, 0)


def _ld_images(obj, out: list[str]) -> None:
    if isinstance(obj, list):
        for x in obj:
            _ld_images(x, out)
        return
    if not isinstance(obj, dict):
        return
    if "@graph" in obj:
        _ld_images(obj["@graph"], out)
    t = obj.get("@type")
    types = {str(x).lower() for x in (t if isinstance(t, list) else [t])}
    if types & LD_TYPES:
        img = obj.get("image") or obj.get("thumbnailUrl")
        for it in (img if isinstance(img, list) else [img]):
            if isinstance(it, str):
                out.append(it)
            elif isinstance(it, dict):
                out.append(it.get("url") or it.get("contentUrl") or "")


def candidates(html: str, base_url: str, limit: int = 14) -> list[dict]:
    """Sayfadaki fotoğraf adayları: paylaşım görseli, yapılandırılmış veri, metin içi fotoğraflar."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    seen: set[str] = set()

    def add(u: str, kind: str, alt: str = "", w: int = 0) -> None:
        u = _abs(u, base_url)
        if not u:
            return
        low = urlsplit(u).path.lower()
        if low.endswith(BAD_EXT) or BAD_URL.search(u):
            return
        if w and w < 400:
            return
        k = _key(u)
        if k in seen:
            return
        seen.add(k)
        out.append({"url": u, "kind": kind, "alt": (alt or "").strip()[:160]})

    metas = [("property", "og:image:secure_url"), ("property", "og:image"), ("property", "og:image:url"),
             ("name", "twitter:image"), ("name", "twitter:image:src"), ("property", "twitter:image")]
    og_alt = ""
    tag = soup.find("meta", attrs={"property": "og:image:alt"})
    if tag:
        og_alt = tag.get("content") or ""
    for attr, val in metas:
        for tag in soup.find_all("meta", attrs={attr: val}):
            add(tag.get("content") or "", "og", og_alt)
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(s.string or s.get_text() or "")
        except (ValueError, TypeError):
            continue
        found: list[str] = []
        _ld_images(data, found)
        for u in found:
            add(u, "ld")

    root = (soup.find(attrs={"itemprop": "articleBody"}) or soup.find("article")
            or soup.find(class_=re.compile(r"(entry|post|article|story)[-_]?(content|body)", re.I))
            or soup.find("main") or soup.body)
    if root is not None:
        for bad in root.find_all(["header", "footer", "nav", "aside", "form"]):
            bad.decompose()
        for img in root.find_all(["img", "source"]):
            if img.find_parent(class_=re.compile(r"(author|avatar|related|recommend|share|comment|newsletter|promo|sponsor|widget)", re.I)):
                continue
            srcset = img.get("data-srcset") or img.get("srcset") or img.get("data-lazy-srcset") or ""
            u, sw = _largest_src(srcset)
            if not u:
                u = (img.get("data-src") or img.get("data-lazy-src") or img.get("data-original")
                     or img.get("data-full-url") or img.get("src") or "")
            try:
                w = int(str(img.get("width") or "0").rstrip("px") or 0)
            except ValueError:
                w = 0
            add(u, "body", img.get("alt") or "", max(w, sw) if (w or sw) else 0)
            if len(out) >= limit:
                break
    return out[:limit]


# ── indirme ve eleme ───────────────────────────────────────
def _dhash(im: Image.Image) -> int:
    g = im.convert("L").resize((9, 8), Image.BILINEAR)
    px = list(g.tobytes())
    bits = 0
    for r in range(8):
        for c in range(8):
            bits = (bits << 1) | (px[r * 9 + c] > px[r * 9 + c + 1])
    return bits


def _similar(a: int, b: int) -> bool:
    return bin(a ^ b).count("1") <= 8


def fetch_image(url: str, referer: str = "", timeout: int = 20) -> Image.Image | None:
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Referer": referer or url,
                                       "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"},
                         timeout=timeout, stream=True)
        if r.status_code >= 400 or not r.headers.get("content-type", "image").startswith("image"):
            return None
        data = r.raw.read(MAX_BYTES + 1, decode_content=True)
        if len(data) > MAX_BYTES:
            return None
        im = Image.open(io.BytesIO(data))
        im.load()
    except (requests.RequestException, OSError, Image.DecompressionBombError, ValueError):
        return None
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg
    return im.convert("RGB")


def usable(im: Image.Image) -> bool:
    w, h = im.size
    if w < MIN_W or h < MIN_H or not (0.5 <= w / h <= 2.4):
        return False
    st = ImageStat.Stat(im.resize((64, 64)).convert("L"))
    return st.stddev[0] >= 14  # düz/boş görseller (logo zemini, yer tutucu) elenir


def gather(sources: list[dict], limit: int = 6, per_source: int = 4, pages: int = 3) -> list[dict]:
    """Kaynaklardan fotoğraf topla. Dönen her öğe: {'image': PIL, 'src', 'credit', 'page', 'alt', 'kind'}"""
    order = sorted(sources, key=lambda s: 0 if s.get("kind") == "official" else 1)[:pages]
    picked: list[dict] = []
    hashes: list[int] = []
    for s in order:
        url = s.get("url") or ""
        cands: list[dict] = []
        feed_img = _abs(s.get("image") or "", url or "https://x/")
        if feed_img and not BAD_URL.search(feed_img):
            cands.append({"url": feed_img, "kind": "feed", "alt": ""})
        html = fetch_html(url) if url else ""
        if html:
            known = {_key(c["url"]) for c in cands}
            cands += [c for c in candidates(html, url) if _key(c["url"]) not in known]
        n = 0
        for c in cands:
            if len(picked) >= limit or n >= per_source:
                break
            im = fetch_image(c["url"], url)
            if im is None or not usable(im):
                continue
            h = _dhash(im)
            if any(_similar(h, x) for x in hashes):
                continue
            hashes.append(h)
            picked.append({"image": im, "src": c["url"], "credit": s.get("name") or urlsplit(url).netloc,
                           "page": url, "alt": c["alt"], "kind": c["kind"]})
            n += 1
        if len(picked) >= limit:
            break
    log.info("Fotoğraf: %d bulundu (%s)", len(picked), ", ".join(dict.fromkeys(p["credit"] for p in picked)) or "-")
    return picked


# ── kaydetme ──────────────────────────────────────────────
def save_webp(im: Image.Image, out: Path, max_w: int, quality: int) -> tuple[int, int]:
    out.parent.mkdir(parents=True, exist_ok=True)
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    im.save(out, "WEBP", quality=quality, method=6)
    return im.size


def og_crop(im: Image.Image, out: Path, size=(1200, 630)) -> None:
    """Paylaşım görseli: fotoğrafın ortasından (hafif yukarıdan) 1200x630 kırpım."""
    tw, th = size
    w, h = im.size
    scale = max(tw / w, th / h)
    nw, nh = round(w * scale), round(h * scale)
    im = im.resize((nw, nh), Image.LANCZOS)
    x = (nw - tw) // 2
    y = max(0, min(nh - th, round((nh - th) * 0.4)))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.crop((x, y, x + tw, y + th)).save(out, "JPEG", quality=84, optimize=True, progressive=True)
