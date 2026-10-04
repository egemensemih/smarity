"""Haber fotoğrafları: şirketin resmi görselleri ya da kaynak haberin görselleri, kredisiyle.

Sıra: resmi kaynak (şirketin kendi duyurusu) → diğer kaynaklar. Her kaynağın sayfasından
paylaşım görseli (og:image), yapılandırılmış veri görseli ve metin içindeki büyük fotoğraflar alınır.
Küçük/logo/ikon görseller ve aynı fotoğrafın farklı boyutları elenir.

Her fotoğraf "fotoğraf" ya da "grafik" (ekran görüntüsü, tablo, belge) diye sınıflanır: kapakta yalnızca
gerçek fotoğraf kullanılır, grafikler haberin içine yerleşir. Paylaşım görsellerine yazı basan kaynaklar
(ayarlarda photo_cover: false) için yalnızca haber metnindeki fotoğraflar alınır.
Hak sahibi talep ederse fotoğraflar Telegram'dan tek tuşla kaldırılır.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import requests
from PIL import Image, ImageChops, ImageOps, ImageStat

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


# reklam / alışveriş / öneri bloklarının sınıf adlarında geçen sözcükler (bu blokların içindeki görseller habere ait değil)
BAD_BLOCK = {"ad", "ads", "advert", "adverts", "advertisement", "adsbygoogle", "reklam", "banner", "sponsor", "sponsored",
             "promo", "promotion", "affiliate", "commerce", "ecommerce", "shop", "shopping", "product", "products", "deal",
             "deals", "kampanya", "campaign", "teaser", "outbrain", "taboola", "related", "recommended", "recommend",
             "popular", "trending", "widget", "newsletter", "author", "avatar", "share", "comments", "subscribe", "firsat",
             "alisveris", "indirim", "partner", "native"}


def _bad_block(el, stop=None) -> bool:
    """Görsel, haber metninin içindeki bir reklam / alışveriş / öneri bloğunda mı? (metin kökünün üstüne bakılmaz)"""
    for anc in [el, *el.parents]:
        if anc is stop or getattr(anc, "name", None) in (None, "[document]", "body", "html"):
            break
        names = " ".join([*(anc.get("class") or []), anc.get("id") or "", anc.get("data-ad") and "ad" or ""]).lower()
        if set(re.split(r"[^a-z0-9]+", names)) & BAD_BLOCK:
            return True
    return False


def _foreign_link(el, base_url: str) -> bool:
    """Görsel başka bir siteye giden bir bağlantının içindeyse (alışveriş / reklam bağlantısı) habere ait değildir."""
    a = el.find_parent("a")
    href = (a.get("href") or "") if a else ""
    if not href.startswith("http") or re.search(r"\.(jpe?g|png|webp|avif)(\?|$)", href, re.I):
        return False
    host = lambda u: ".".join(urlsplit(u).netloc.lower().split(".")[-2:])  # noqa: E731
    return host(href) != host(base_url)


def candidates(html: str, base_url: str, limit: int = 48) -> list[dict]:
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
            if _bad_block(img, root) or _foreign_link(img, base_url):
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


def fetch_image(url: str, referer: str = "", timeout: int = 20, ua: str = "") -> Image.Image | None:
    try:
        r = requests.get(url, headers={"User-Agent": ua or UA, "Referer": referer or url,
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


def _stats(im: Image.Image) -> tuple[float, float]:
    """(düz zemin oranı, ince çizgi yoğunluğu) — 480 px genişlikte ölçülür."""
    w = 480
    small = im.convert("RGB").resize((w, max(2, round(im.height * w / im.width))), Image.BILINEAR)
    px = small.tobytes()
    counts: dict[int, int] = {}
    for i in range(0, len(px), 3):
        k = (px[i] >> 4) << 8 | (px[i + 1] >> 4) << 4 | (px[i + 2] >> 4)
        counts[k] = counts.get(k, 0) + 1
    n = len(px) // 3
    flat = sum(sorted(counts.values(), reverse=True)[:2]) / n
    g = small.convert("L")
    gw, gh = g.size
    base = g.crop((0, 0, gw - 1, gh - 1))
    dx = ImageChops.difference(base, g.crop((1, 0, gw, gh - 1)))
    dy = ImageChops.difference(base, g.crop((0, 1, gw - 1, gh)))
    hist = ImageChops.add(dx, dy).histogram()      # 255'te doyar; eşik 80 olduğu için sorun değil
    return flat, sum(hist[81:]) / n


def classify(im: Image.Image) -> dict:
    """Fotoğrafın türü.

    graphic : ekran görüntüsü, tablo, harita, belge (zeminin çoğu tek renk + yoğun ince çizgi/yazı).
              Kapak ya da kaydırmalı alan yerine haberin içine yerleşir.
    cover_ok: kapak olabilir mi? Düz zeminli tanıtım görsellerinde (üstünde çoğu zaman kendi yazısı olur)
              bizim yazımız kalabalık durur; bunlarda kapak yazılı olur, fotoğraf galeride gösterilir.
    """
    flat, edge = _stats(im)
    graphic = flat >= 0.62 and edge >= 0.025
    return {"graphic": graphic, "cover_ok": not graphic and flat < 0.7}


def is_graphic(im: Image.Image) -> bool:
    return classify(im)["graphic"]


def usable(im: Image.Image) -> bool:
    w, h = im.size
    if w < MIN_W or h < MIN_H or not (0.5 <= w / h <= 2.4):
        return False
    st = ImageStat.Stat(im.resize((64, 64)).convert("L"))
    return st.stddev[0] >= 14  # düz/boş görseller (logo zemini, yer tutucu) elenir


# ── yedek: Wikipedia'daki ürün / şirket / kişi görseli ─────
WIKI_UA = "SmarityBot/1.0 (https://smarity.com.tr; haber sitesi gorsel arama)"
GENERIC_NAMES = {"türkiye", "turkey", "yapay zeka", "ai", "elektrikli otomobil", "abd", "avrupa", "çin"}


def _wiki_names(names: list[str]) -> list[str]:
    """Aranacak adlar: özel adlar (büyük harf içeren), en belirgin olan önce (ürün adı şirket adından önce)."""
    out = []
    for n in names:
        n = (n or "").strip()
        if n and n.lower() not in GENERIC_NAMES and any(c.isupper() for c in n) and n not in out:
            out.append(n)
    return sorted(out[:5], key=lambda n: -len(n.split()))


def wiki_photo(names: list[str]) -> dict | None:
    """Kaynaklarda hiç fotoğraf yoksa: haberin ürününün / şirketinin / kişisinin Wikipedia görseli (kaynağıyla)."""
    for name in _wiki_names(names):
        for lang in ("tr", "en"):
            try:
                r = requests.get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(name.replace(' ', '_'))}",
                                 headers={"User-Agent": WIKI_UA}, timeout=10)
                if r.status_code != 200:
                    continue
                j = r.json()
            except (requests.RequestException, ValueError):
                continue
            if j.get("type") == "disambiguation":
                continue
            org = j.get("originalimage") or {}
            src = org.get("source") or ""
            if not src or src.lower().endswith(".svg") or (org.get("width") or 0) > 2400:
                th = (j.get("thumbnail") or {}).get("source") or ""
                src = re.sub(r"/\d+px-", "/960px-", th) if "/thumb/" in th else src
            if not src or src.lower().endswith(".svg"):
                continue
            im = fetch_image(src, "https://wikipedia.org/", ua=WIKI_UA)
            if im is None or not usable(im):
                continue
            page = ((j.get("content_urls") or {}).get("desktop") or {}).get("page") or f"https://{lang}.wikipedia.org/"
            log.info("Fotoğraf: kaynaklarda yok, Wikipedia görseli kullanıldı (%s)", name)
            return {"image": im, "src": src, "credit": "Wikipedia", "page": page, "alt": j.get("title") or name,
                    "kind": "wiki", **classify(im)}
    return None


def gather(sources: list[dict], limit: int = 16, per_source: int = 12, pages: int = 3,
           skip_cover: set[str] | frozenset = frozenset(), entities: list[str] | None = None) -> list[dict]:
    """Kaynaklardan fotoğraf topla. Dönen her öğe: {'image': PIL, 'src', 'credit', 'page', 'alt', 'kind', 'graphic'}

    skip_cover: paylaşım görseline yazı basan kaynakların adları (bunlarda besleme/og görseli alınmaz).
    Sıra: resmi kaynak önce; aynı sırada gerçek fotoğraflar grafiklerden önce gelir.
    """
    order = sorted(sources, key=lambda s: 0 if s.get("kind") == "official" else 1)[:pages]
    picked: list[dict] = []
    hashes: list[int] = []
    for s in order:
        url = s.get("url") or ""
        no_cover = (s.get("name") or "") in skip_cover
        cands: list[dict] = []
        feed_img = _abs(s.get("image") or "", url or "https://x/")
        if feed_img and not BAD_URL.search(feed_img) and not no_cover:
            cands.append({"url": feed_img, "kind": "feed", "alt": ""})
        html = fetch_html(url) if url else ""
        if html:
            known = {_key(c["url"]) for c in cands}
            cands += [c for c in candidates(html, url) if _key(c["url"]) not in known
                      and not (no_cover and c["kind"] != "body")]
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
                           "page": url, "alt": c["alt"], "kind": c["kind"], **classify(im)})
            n += 1
        if len(picked) >= limit:
            break
    if not picked and entities:
        w = wiki_photo(entities)
        if w:
            picked.append(w)
    picked.sort(key=lambda p: p["graphic"])  # kararlı sıralama: kaynak sırası korunur
    log.info("Fotoğraf: %d bulundu, %d grafik (%s)", len(picked), sum(p["graphic"] for p in picked),
             ", ".join(dict.fromkeys(p["credit"] for p in picked)) or "-")
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


def thumb_jpeg(im: Image.Image, size: int = 384) -> bytes:
    """Yapay zeka fotoğraf editörüne gönderilecek küçük kopya."""
    t = im.convert("RGB").copy()
    t.thumbnail((size, size))
    buf = io.BytesIO()
    t.save(buf, "JPEG", quality=72)
    return buf.getvalue()
