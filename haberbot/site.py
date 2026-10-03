"""Statik web sitesi üretici: content/posts/*.json → _site/"""
from __future__ import annotations

import html as htmlmod
import json
import re
import shutil
from collections import Counter
from email.utils import format_datetime

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import CATEGORIES, DEFAULT_CATEGORY, ROOT, Config, category_color, category_label, category_seo, indexnow_key
from .covers import art_style
from .store import Store
from .textfix import primary_key, tag_display
from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date

ASSET_V = "15"
FOREIGN_PRICE = re.compile(r"(?=.*fiyat)(?=.*(\$|€|£|¥|dolar|euro|avro|sterlin|yuan|yen\b))", re.I)
WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
H2_RE = re.compile(r"<h[1-3]>(.*?)</h[1-3]>", re.S)


def render_body(md: str) -> str:
    safe = htmlmod.escape(md or "", quote=False)
    out = markdown.markdown(safe, extensions=["sane_lists"], output_format="html")
    out = re.sub(r'href="(?!https?://)[^"]*"', 'href="#"', out)
    out = out.replace('<a href="http', '<a rel="noopener" target="_blank" href="http')
    out = WHY_RE.sub(r'<aside class="why"><strong>Neden önemli?</strong><p>\1</p></aside>', out)
    # Metindeki başlıklar sayfanın H1'i ile yarışmasın: hepsi H2, bağlantılanabilir
    out = H2_RE.sub(lambda m: f'<h2 id="{slugify(re.sub("<[^>]+>", "", m.group(1)), 60)}">{m.group(1)}</h2>', out)
    return out


BLOCK_RE = re.compile(r"<(aside|blockquote|ul|ol|table|pre|figure)\b.*?</\1>", re.S)


def figure_html(ph: dict) -> str:
    """Haberin içine yerleşen fotoğraf: kaynağı altında."""
    e = lambda v: htmlmod.escape(str(v or ""), quote=True)  # noqa: E731
    remote = ' referrerpolicy="no-referrer" onerror="this.closest(\'figure\').remove()"' if ph.get("remote") else ""
    cap = (f'<figcaption><a href="{e(ph.get("page"))}" rel="noopener nofollow" target="_blank">Görsel: {e(ph.get("credit"))}</a>'
           f'</figcaption>' if ph.get("credit") else "")
    return (f'<figure class="inl{" graphic" if ph.get("graphic") else ""}"><img src="{e(ph["url"])}" alt="{e(ph.get("alt"))}" '
            f'width="{int(ph.get("w") or 1600)}" height="{int(ph.get("h") or 900)}" loading="lazy" decoding="async"{remote}>'
            f'{cap}</figure>')


def inline_figures(body_html: str, figs: list[dict], first: int = 0, every: int = 1) -> tuple[str, list[dict]]:
    """Fotoğrafları metnin paragrafları arasına yerleştir (ilk paragraftan sonra başlayarak her paragrafın ardına bir
    fotoğraf; haber görsellerle akar).

    Liste, alıntı ve "Neden önemli?" kutularının içine girmez. Yer kalmazsa artanlar geri döner.
    """
    if not figs:
        return body_html, []
    blocked = [m.span() for m in BLOCK_RE.finditer(body_html)]
    ends = [m.end() for m in re.finditer(r"</p>", body_html) if not any(a <= m.start() < b for a, b in blocked)]
    slots = ends[first::every]
    use = figs[:len(slots)]
    out, last = [], 0
    for pos, ph in zip(slots, use):
        out += [body_html[last:pos], "\n", figure_html(ph)]
        last = pos
    out.append(body_html[last:])
    return "".join(out), figs[len(use):]


def follow_links(site: dict) -> list[dict]:
    """Takip kanalları (ayarlarda yazılı olanlar) + RSS."""
    out = []
    ig = (site.get("instagram") or "").lstrip("@").strip()
    if ig:
        out.append({"key": "instagram", "label": "Instagram", "handle": "@" + ig, "url": f"https://www.instagram.com/{ig}/"})
    tg = (site.get("telegram") or "").lstrip("@").strip()
    if tg:
        out.append({"key": "telegram", "label": "Telegram", "handle": "@" + tg, "url": f"https://t.me/{tg}"})
    wa = (site.get("whatsapp") or "").strip()
    if wa:
        out.append({"key": "whatsapp", "label": "WhatsApp", "handle": "Kanal", "url": wa})
    x = (site.get("x") or "").lstrip("@").strip()
    if x:
        out.append({"key": "x", "label": "X", "handle": "@" + x, "url": f"https://x.com/{x}"})
    out.append({"key": "rss", "label": "RSS", "handle": "Besleme", "url": f"{site.get('url', '')}/feed.xml"})
    return out


def hot(p: dict, now=None) -> float:
    """Ana sayfa sıralaması: ilgi puanı (1–10) × tazelik. Fotoğraflı kapak az öne çıkar; manşete sabitlenen haber
    36 saat boyunca en üstte durur; "ana sayfada gösterme" denen haber hiç çıkmaz (kategoride kalır)."""
    home = p.get("home")
    if home == "hide":
        return -1.0
    age = max(0.0, min(hours_since(p.get("published_at")), hours_since(p.get("refreshed_at") or p.get("published_at"))))
    base = float(p.get("appeal") or max(5, int(p.get("importance") or 6) - 1))
    if (p.get("image") or {}).get("source") == "photo":
        base += 1.0
    score = base / (age + 4) ** 0.7
    if home == "pin" and hours_since(p.get("home_at") or p.get("published_at")) < 36:
        score += 100          # editör manşete sabitledi: 36 saat en üstte
    return score


def nobr_hyphen(title: str) -> str:
    """'GPT-6' gibi kısa tireli sözcüklerin satır sonunda bölünmesini engelle."""
    return re.sub(r"(?<=\w)-(?=\w)", "‑", title or "")


def reading_minutes(text: str) -> int:
    return max(1, round(len((text or "").split()) / 180))


def plain(md: str) -> str:
    s = re.sub(r"[*_`#>]+", "", md or "")
    return re.sub(r"\s+", " ", s).strip()


def tag_slug(tag: str) -> str:
    return slugify(tag, 50)


# Her habere uyan genel sözcükler konu sayfası olmaz
GENERIC_TAGS = {"yapay-zeka", "yapay-zek", "ai", "artificial-intelligence", "teknoloji", "technology", "haber", "haberler",
                "gelisme", "duyuru", "yenilik", "yapay-zeka-haberleri", "oyun", "oyunlar", "gaming", "games", "otomobil",
                "araba", "cars", "girisim", "girisimler", "startup", "startups", "inovasyon", "innovation", "urun", "yeni-urun",
                "teknoloji-haberleri", "bilim", "super-zeka", "girisimcilik"}


def edge_color(path) -> tuple[str, bool]:
    """Görselin sol kenar rengi: manşet zemini bu renge boyanır, görsel dikişsiz kaynaşır."""
    from PIL import Image
    try:
        im = Image.open(path).convert("RGB")
    except Exception:  # noqa: BLE001
        return "#F5F5F7", False
    w, h = im.size
    r, g, b = im.crop((0, 0, max(2, int(w * .05)), h)).resize((1, 1), Image.BOX).getpixel((0, 0))
    lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return f"#{r:02X}{g:02X}{b:02X}", lum < .5


GRAD_STOPS = [(0, (43, 89, 255)), (.38, (0, 163, 255)), (.72, (0, 209, 178)), (1, (155, 226, 45))]


def _brand_gradient(size: int):
    """Marka degradesi (sol üstten sağ alta: mavi → turkuaz → yeşil)."""
    from PIL import Image
    n = 256
    g = Image.new("RGB", (n, n))
    px = g.load()
    for x in range(n):
        for y in range(n):
            t = (x + y) / (2 * (n - 1))
            for i in range(len(GRAD_STOPS) - 1):
                a, ca = GRAD_STOPS[i]
                b, cb = GRAD_STOPS[i + 1]
                if a <= t <= b:
                    f = (t - a) / (b - a)
                    px[x, y] = tuple(int(ca[k] + (cb[k] - ca[k]) * f) for k in range(3))
                    break
    return g.resize((size, size), Image.BILINEAR)


def make_logo(path, size: int = 512, dark: bool = False) -> None:
    """Marka simgesini (degrade 'S' ve kıvılcım noktası) PNG olarak üret: arama motorları ve paylaşım için."""
    from PIL import Image, ImageDraw
    s = size * 4
    u = s * 0.72 / 24                      # 24 birimlik çizim kutusu
    X = lambda x: s / 2 + (x - 12.55) * u  # noqa: E731
    Y = lambda y: s / 2 + (y - 12.2) * u   # noqa: E731
    w = 3.6 * u
    mask = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(mask)

    def arc(cx, cy, r, a0, a1):
        R = r + 3.6 / 2
        d.arc([X(cx - R), Y(cy - R), X(cx + R), Y(cy + R)], a0, a1, fill=255, width=int(w))

    def dot(cx, cy, r):
        d.ellipse([X(cx - r), Y(cy - r), X(cx + r), Y(cy + r)], fill=255)

    arc(10.8, 7.2, 4.8, 90, 360)      # üst yay: alttan sola, yukarı, sağa
    arc(10.8, 16.8, 4.8, -90, 180)    # alt yay: üstten sağa, aşağı, sola
    dot(15.6, 7.2, 1.8)               # yuvarlak uçlar
    dot(6.0, 16.8, 1.8)
    dot(10.8, 12.0, 1.8)
    dot(19.0, 3.2, 1.9)               # kıvılcım
    bg = Image.new("RGB", (s, s), (10, 15, 31) if dark else (255, 255, 255))
    bg.paste(_brand_gradient(s), (0, 0), mask)
    bg.resize((size, size), Image.LANCZOS).save(path, "PNG", optimize=True)


class SiteBuilder:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.base = cfg.base_path
        self.skip_tags = GENERIC_TAGS | {slugify(x.get("name", ""), 50) for x in cfg.sources
                                         if x.get("kind") in ("media", "community")}
        self.env = Environment(
            loader=FileSystemLoader(str(ROOT / "templates")),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True, lstrip_blocks=True,
        )

    def _post_view(self, p: dict) -> dict:
        cfg, b = self.cfg, self.base
        pub = p.get("published_at")
        dt = parse_iso(pub) or now_utc()
        mod = parse_iso(p.get("updated_at")) or dt
        has_og = (cfg.images_dir / f"{p['id']}-og.jpg").exists()
        title = p.get("title", "")
        short = p.get("short_title") or title
        summary = p.get("summary", "")
        seo_title = clip(p.get("seo_title") or short or title, 62)
        meta = p.get("meta_description") or ""
        if len(meta) < 70:  # yedek: özet + ilk paragraf
            meta = summary if len(summary) >= 110 else f"{summary} {plain(p.get('body', ''))}"
        tags = []
        for t in dict.fromkeys(t.strip() for t in (p.get("tags") or []) if t and t.strip()):
            ts = tag_slug(t)
            if ts and ts not in self.skip_tags and len(tags) < 6:
                tags.append({"label": tag_display(t), "slug": ts, "url": f"{b}/etiket/{ts}/"})
        cat = p.get("category", DEFAULT_CATEGORY)
        disp = self._display(p)
        disp_url = disp.get("url") or ""
        return {
            **p,
            "url": f"{b}/{cfg.post_path(p)}/",
            "path": cfg.post_path(p),
            "disp": disp,
            "ts": int(dt.timestamp()),
            "hot": hot(p),
            "photo_cover": (p.get("image") or {}).get("source") == "photo",
            "title_disp": nobr_hyphen(title),
            "short_disp": nobr_hyphen(short),
            "kicker_disp": p.get("kicker") or category_label(cat),
            # yurtdışı fiyatı öne çıkarılmaz (Türkiye'ye haber yapıyoruz): "64.050 $" gibi rakamlar kutuda gösterilmez
            "hero_stat": "" if FOREIGN_PRICE.search(f"{p.get('hero_stat') or ''} {p.get('hero_stat_label') or ''}")
            else (p.get("hero_stat") or "").strip(),
            "hero_stat_label": (p.get("hero_stat_label") or "").strip(),
            "ai_image": (p.get("image") or {}).get("source") == "ai",
            "cover_image": (p.get("image") or {}).get("source") == "cover",
            # rakam kapakta yazıyorsa "öne çıkanlar" kutusunda tekrar edilmez
            "stat_on_cover": False,   # sitede görsellerin üstünde yazı yok: rakam "öne çıkanlar" kutusunda görünür
            "img_alt": clip(p.get("image_alt") or f"{short}: habere ait görsel", 125),
            "seo_title": seo_title,
            "meta_description": clip(meta, 158),
            "focus_keyword": p.get("focus_keyword", ""),
            "tag_list": tags,
            "abs_url": cfg.post_url(p),
            "img": disp_url,
            "abs_og": (og := f"{cfg.site_url}/img/{p['id']}-og.jpg" if has_og else f"{cfg.site_url}/static/og-default.jpg"),
            "abs_img": f"{cfg.site_url}{disp_url[len(b):]}" if disp_url else og,
            "date_str": tr_date(pub, cfg.tz),
            "date_short": tr_date(pub, cfg.tz, with_time=False),
            "iso": iso(dt),
            "mod_iso": iso(max(mod, dt)),
            "rfc822": format_datetime(dt),
            "cat_label": category_label(cat),
            "cat_seo": category_seo(cat)[0],
            "cat_color": category_color(cat),
            "cat_url": f"{b}/{cat}/",
            "abs_cat_url": f"{cfg.site_url}/{cat}/",
            "credits": list(dict.fromkeys(s["name"] for s in p.get("sources", []))),
            "minutes": reading_minutes(p.get("body", "")),
            "words": len(plain(p.get("body", "")).split()),
            **(media := self._media(p, short, render_body(p.get("body", "")))),
            "toc": [{"id": m.group(1), "text": re.sub("<[^>]+>", "", m.group(2))}
                    for m in re.finditer(r'<h2 id="([^"]+)">(.*?)</h2>', media["body_html"])],
            "key_points": [x for x in (p.get("carousel_points") or []) if x][:4],
            "photos": self._photos(p, short),
            "has_photo": bool(p.get("photos")),
            "updated_str": tr_date(p.get("updated_at"), cfg.tz) if p.get("updated_at") else "",
            "ekey": primary_key(p),
            "update_list": [{"date": tr_date(u.get("at"), cfg.tz), "iso": u.get("at", ""), "note": u.get("note", "")}
                            for u in reversed(p.get("updates") or []) if u.get("note")],
        }

    def _photos(self, p: dict, short: str) -> list[dict]:
        """Haberin gerçek fotoğrafları. Yerel kopyası olmayan fotoğraf kaynaktaki adresinden gösterilir."""
        cfg, b = self.cfg, self.base
        out = []
        for i, r in enumerate(p.get("photos") or []):
            local = bool(r.get("file")) and (cfg.images_dir / r["file"]).exists()
            if not local and not r.get("src"):
                continue
            out.append({
                "file": r.get("file") or "",
                "url": f"{b}/img/{r['file']}" if local else r["src"],
                "remote": not local,
                "graphic": bool(r.get("graphic")),
                "credit": r.get("credit") or "",
                "page": r.get("page") or "",
                "alt": clip(r.get("alt") or f"{short}: {r.get('credit') or 'habere ait'} fotoğrafı ({i + 1})", 125),
                "w": r.get("w") or 1600, "h": r.get("h") or 900,
            })
        return out

    def _display(self, p: dict) -> dict:
        """Sitede görünen görsel — üstünde yazı yok, başlık sayfada HTML olarak durur (tek parça görünüm):
        haberin gerçek fotoğrafı; yoksa yapay zeka görseli; o da yoksa habere özel renk ağı (CSS)."""
        cfg, b = self.cfg, self.base
        img = p.get("image") or {}
        recs = [r for r in p.get("photos") or [] if r.get("file") and (cfg.images_dir / r["file"]).exists()]
        pick = None
        if img.get("source") == "photo" and img.get("photo"):
            pick = next((r for r in recs if r["file"] == img["photo"]), None)
        # Yazı basılmayacağı için düz zeminli tanıtım görselleri ve 720 px'lik fotoğraflar da olur; boş renk ağı son çare.
        # Önce gerçek fotoğraflar (en büyüğü), yoksa ekran görüntüsü / grafik (kırpılmadan, sığdırılarak).
        if pick is None:
            big = sorted((r for r in recs if (r.get("w") or 0) >= 600), key=lambda r: (bool(r.get("graphic")), -(r.get("w") or 0)))
            pick = big[0] if big else None
        if pick:
            return {"kind": "photo", "file": pick["file"], "url": f"{b}/img/{pick['file']}", "w": pick.get("w") or 1600,
                    "h": pick.get("h") or 900, "credit": pick.get("credit") or "", "page": pick.get("page") or "",
                    "focus": p.get("photo_focus") or "50% 40%", "fit": bool(pick.get("graphic"))}
        if img.get("source") in ("ai", "fallback") and (cfg.images_dir / f"{p['id']}.webp").exists():
            return {"kind": "image", "file": f"{p['id']}.webp", "url": f"{b}/img/{p['id']}.webp", "w": 1280, "h": 960,
                    "credit": "", "page": "", "focus": "50% 50%"}
        style, base = art_style(p)
        return {"kind": "art", "style": style, "base": base, "url": ""}

    def _media(self, p: dict, short: str, body_html: str) -> dict:
        """Ana görsel (yazısız) + metnin içine paragraf paragraf yerleşen fotoğraflar + sona kalanlar için galeri.

        Ana görselde kullanılan fotoğraf tekrar gösterilmez."""
        ph = self._photos(p, short)
        disp = self._display(p)
        cover = next((x for x in ph if x["file"] and x["file"] == disp.get("file")), None)
        rest = [x for x in ph if x is not cover]
        good = [x for x in rest if not x["graphic"]]
        graphics = [x for x in rest if x["graphic"]]
        body_html, left = inline_figures(body_html, good + graphics)
        return {"body_html": body_html, "cover_photo": cover, "slides": left}

    def _redirect(self, rel: str, target: str, title: str) -> None:
        """GitHub Pages'te sunucu yönlendirmesi yok: anında yenileme + kanonik adres (Google bunu kalıcı yönlendirme sayar)."""
        if (self.cfg.out_dir / rel).exists():
            return
        t = htmlmod.escape(target, quote=True)
        name = htmlmod.escape(title or "Smarity")
        self._write(rel, f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>{name}</title>'
                         f'<link rel="canonical" href="{t}"><meta http-equiv="refresh" content="0; url={t}">'
                         f'<script>location.replace({json.dumps(target)} + location.hash)</script></head>'
                         f'<body><a href="{t}">{name}</a></body></html>')

    def _write(self, rel: str, content: str) -> None:
        path = self.cfg.out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def _home(posts: list[dict], n_feat: int) -> dict:
        """Ana sayfa seçkisi. Her onaylanan haber ana sayfaya çıkmaz: en dikkat çekiciler (ilgi × tazelik) seçilir,
        bir haber sayfada yalnızca bir kez görünür. Tüm haberler kategori ve "Tüm haberler" sayfalarında durur."""
        visible = [p for p in posts if p["hot"] >= 0]
        ranked = sorted(visible, key=lambda p: -p["hot"])
        fresh = [p for p in ranked if hours_since(p.get("published_at")) <= 72 or p["hot"] >= 100]  # sabitlenen her zaman
        # Vitrinde (manşet + öne çıkanlar) her şirketten tek haber: aynı şirketin ikinci haberi aşağıdaki listelerde kalır
        used: set[str] = set()

        def pick(pool: list[dict], n: int, shown: set[str]) -> list[dict]:
            out = []
            for strict in (True, False):
                for p in pool:
                    if len(out) >= n:
                        return out
                    if p["id"] in shown or p in out or (strict and p["ekey"] and p["ekey"] in used):
                        continue
                    out.append(p)
                    if p["ekey"]:
                        used.add(p["ekey"])
            return out
        featured = pick(fresh + [p for p in ranked if p not in fresh], n_feat, set())
        shown = {p["id"] for p in featured}
        top = pick(ranked, 6, shown)
        shown |= {p["id"] for p in top}
        latest = [p for p in visible if p["id"] not in shown and hours_since(p.get("published_at")) <= 48][:6]
        shown |= {p["id"] for p in latest}
        # "Kaçırmış olabilirsin": son iki haftanın ilgi çekici haberlerinden her ziyarette farklı dördü (tarayıcıda seçilir)
        pool = sorted((p for p in visible if p["id"] not in shown and hours_since(p.get("published_at")) <= 24 * 14),
                      key=lambda p: (-(p.get("appeal") or 5), -p["ts"]))[:16]
        return {"featured": featured, "top": top, "latest": latest, "discover": pool, "shown": shown,
                "ranked": ranked}

    def build(self) -> int:
        cfg, b = self.cfg, self.base
        seo = cfg.raw.get("seo") or {}
        out = cfg.out_dir
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        store = Store(cfg)
        posts = [self._post_view(p) for p in store.posts()]
        counts = Counter(p["category"] for p in posts)
        latest_by_cat: dict[str, str] = {}
        for p in posts:
            latest_by_cat.setdefault(p["category"], p["mod_iso"])
        cats = [{"slug": k, "label": v[0], "color": v[1], "count": counts.get(k, 0),
                 "seo_title": category_seo(k)[0], "intro": category_seo(k)[1],
                 "url": f"{b}/{k}/", "abs_url": f"{cfg.site_url}/{k}/", "lastmod": latest_by_cat.get(k)}
                for k, v in CATEGORIES.items()]

        # etiketler (konular)
        tag_posts: dict[str, list[dict]] = {}
        tag_label: dict[str, Counter] = {}
        for p in posts:
            for t in p["tag_list"]:
                tag_posts.setdefault(t["slug"], []).append(p)
                tag_label.setdefault(t["slug"], Counter())[t["label"]] += 1
        tags = sorted(({"slug": s, "label": tag_label[s].most_common(1)[0][0], "count": len(ps),
                        "url": f"{b}/etiket/{s}/", "lastmod": ps[0]["mod_iso"]}
                       for s, ps in tag_posts.items()), key=lambda t: (-t["count"], t["label"].lower()))

        now_l = local(now_utc(), cfg.tz)
        key = indexnow_key(cfg.site_url)
        site = {
            **cfg.site,
            "base": b,
            "url": cfg.site_url,
            "year": now_l.year,
            # Instagram hesabı: ayarda yazılı değilse bağlanan hesaptan (data/instagram.json) alınır
            "instagram": cfg.site.get("instagram") or (store.ig.get("username") if cfg.instagram_token else ""),
            "categories": cats,
            "nav_categories": [c for c in cats if c["count"] > 0] or cats[:6],
            "top_tags": [t for t in tags if t["count"] >= 2][:14],
            "built": tr_date(now_utc(), cfg.tz),
            "built_iso": iso(now_utc()),
            "today_count": sum(1 for p in posts if (local(p["published_at"], cfg.tz) or now_l).date() == now_l.date()),
            "og_image": f"{cfg.site_url}/static/og-default.jpg",
            "logo": f"{cfg.site_url}/static/logo.png",
            "logo_svg": f"{b}/static/logo.svg" if (ROOT / "static" / "logo.svg").exists() else "",
            "asset_v": ASSET_V,
            "home_h1": seo.get("home_h1") or "Teknoloji haberleri",
            "today_str": f"{tr_date(now_utc(), cfg.tz, with_time=False)}, "
                         f"{['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar'][now_l.weekday()]}",
            "home_title": seo.get("home_title") or f"{cfg.site.get('name')}: {cfg.site.get('tagline')}",
            "home_description": seo.get("home_description") or cfg.site.get("description", ""),
            "verify": {k: seo.get(k) for k in ("google_site_verification", "bing_site_verification", "yandex_verification")},
        }
        site["follow"] = follow_links(site)
        ctx = {"site": site}

        # statik dosyalar, logo ve görseller
        shutil.copytree(ROOT / "static", out / "static")
        # Marka görselleri static/ klasöründe hazır gelir; yoksa basit bir simge üretilir.
        for name, size, dark in (("logo.png", 512, False), ("apple-touch-icon.png", 180, True)):
            if not (ROOT / "static" / name).exists():
                try:
                    make_logo(out / "static" / name, size, dark=dark)
                except Exception as e:  # noqa: BLE001
                    log.warning("Logo üretilemedi: %s", e)
        (out / "img").mkdir()
        for p in posts:
            # yazılı kapak ({id}.webp) sitede kullanılmaz (paylaşım görseli -og.jpg ayrı); yalnızca görünen görsel kopyalanır
            names = [p["disp"]["file"]] if p["disp"].get("file") else []
            names += [f"{p['id']}-og.jpg"]
            names += [ph["file"] for ph in p.get("photos") or [] if ph.get("file") and not ph.get("remote")]
            for name in dict.fromkeys(names):
                src = cfg.images_dir / name
                if src.exists():
                    shutil.copy2(src, out / "img" / name)

        # ana sayfa: seçki (manşet, öne çıkanlar, son dakika, kaçırmış olabilirsin, kategori şeritleri)
        n_feat = int((cfg.raw.get("home") or {}).get("featured_count") or seo.get("featured_count", 5) or 5)
        home = self._home(posts, n_feat)
        featured = home["featured"]
        for p in featured:
            if p["disp"].get("file"):
                p["slide_bg"], p["slide_dark"] = edge_color(cfg.images_dir / p["disp"]["file"])
            else:
                p["slide_bg"], p["slide_dark"] = p["disp"]["base"], True
        shown = set(home["shown"])
        rails = []
        for c in sorted(cats, key=lambda c: -c["count"]):
            cp = [p for p in home["ranked"] if p["category"] == c["slug"] and p["id"] not in shown][:8]
            if len(cp) >= 3 and len(rails) < 3:
                rails.append({"cat": c, "posts": cp})
        per = int(cfg.site.get("posts_per_page", 18))
        pages = max(1, (len(posts) + per - 1) // per)
        self._write("index.html", self.env.get_template("index.html").render(
            **ctx, featured=featured, top=home["top"], latest=home["latest"], discover=home["discover"],
            rails=rails, tags=site["top_tags"],
            latest_iso=max((q["iso"] for q in posts), default=site["built_iso"]),
            latest_str=tr_date(max((q.get("published_at") or "" for q in posts), default=None), cfg.tz),
            all_url=f"{b}/haberler/", canonical=cfg.site_url + "/"))
        # tüm haberler (kronolojik, sayfalı): /haberler/, /haberler/sayfa/2/ …
        for n in range(1, pages + 1):
            chunk = posts[(n - 1) * per:n * per]
            url = lambda k: f"{b}/haberler/" if k == 1 else f"{b}/haberler/sayfa/{k}/"  # noqa: E731
            rel = "haberler/index.html" if n == 1 else f"haberler/sayfa/{n}/index.html"
            self._write(rel, self.env.get_template("archive.html").render(
                **ctx, posts=chunk, page=n, pages=pages, total=len(posts),
                prev_url=url(n - 1) if n > 1 else None, next_url=url(n + 1) if n < pages else None,
                canonical=cfg.site_url + url(n)[len(b):]))
        # eski arşiv adresleri (/sayfa/N/) yeni sayfalara yönlenir
        for n in range(2, pages + 2):
            target = f"{cfg.site_url}/haberler/" if n - 1 <= 1 else f"{cfg.site_url}/haberler/sayfa/{n - 1}/"
            self._write(f"sayfa/{n}/index.html",
                        f'<!doctype html><meta charset="utf-8"><title>Tüm haberler</title><meta name="robots" content="noindex">'
                        f'<link rel="canonical" href="{target}"><meta http-equiv="refresh" content="0; url={target}">'
                        f'<a href="{target}">Tüm haberler</a>')

        # haber sayfaları
        for p in posts:
            same_tag = {t["slug"] for t in p["tag_list"]}
            related = sorted((q for q in posts if q["id"] != p["id"]),
                             key=lambda q: (-(len(same_tag & {t["slug"] for t in q["tag_list"]}) * 2
                                              + (q["category"] == p["category"])), posts.index(q)))[:8]
            # sıradaki haber: aynı kategoriden en dikkat çekici güncel haber, yoksa genel seçkiden
            pool = [q for q in home["ranked"][:24] if q["id"] != p["id"]]
            nxt = next((q for q in pool if q["category"] == p["category"]), pool[0] if pool else None)
            related = [q for q in related if not nxt or q["id"] != nxt["id"]]
            self._write(f"{p['path']}/index.html", self.env.get_template("article.html").render(
                **ctx, post=p, related=related, next_post=nxt, canonical=p["abs_url"]))
            # eski adres (/haber/slug/) yeni adrese yönlenir
            self._redirect(f"haber/{p['slug']}/index.html", p["abs_url"], p["title"])
            for old in p.get("old_paths") or []:
                if old != p["path"]:
                    self._redirect(f"{old}/index.html", p["abs_url"], p["title"])

        # kategoriler: /teknoloji/ ; yıl ve ay adresleri (/teknoloji/2026/10/) kategori sayfasına yönlenir
        months: set[str] = set()
        for p in posts:
            parts = p["path"].split("/")
            if len(parts) == 4:
                months |= {"/".join(parts[:2]), "/".join(parts[:3])}
        for c in cats:
            cp = [p for p in posts if p["category"] == c["slug"]][:120]
            self._write(f"{c['slug']}/index.html", self.env.get_template("category.html").render(
                **ctx, cat=c, posts=cp, active_cat=c["slug"], canonical=c["abs_url"], noindex=not cp))
            self._redirect(f"kategori/{c['slug']}/index.html", c["abs_url"], c["seo_title"])
        for m in sorted(months):
            cat = m.split("/")[0]
            if cat in CATEGORIES:
                self._redirect(f"{m}/index.html", f"{cfg.site_url}/{cat}/", category_seo(cat)[0])

        # konu (etiket) sayfaları: tek haberlik konular dizine eklenmez (ince içerik)
        for t in tags:
            self._write(f"etiket/{t['slug']}/index.html", self.env.get_template("tag.html").render(
                **ctx, tag=t, posts=tag_posts[t["slug"]][:120], canonical=f"{cfg.site_url}/etiket/{t['slug']}/",
                noindex=t["count"] < 2))

        self._write("hakkinda/index.html", self.env.get_template("about.html").render(
            **ctx, canonical=f"{cfg.site_url}/hakkinda/",
            sources=[s for s in cfg.sources]))
        self._write("404.html", self.env.get_template("404.html").render(**ctx, canonical=cfg.site_url + "/", noindex=True))

        # besleme, site haritaları, robots, IndexNow anahtarı, json
        self._write("feed.xml", self.env.get_template("feed.xml").render(
            **ctx, posts=posts[:40], now_rfc=format_datetime(now_utc())))
        self._write("sitemap.xml", self.env.get_template("sitemap.xml").render(
            **ctx, posts=posts, cats=[c for c in cats if c["count"]], tags=[t for t in tags if t["count"] >= 2],
            pages=pages))
        # ana ekrana eklenebilir site (PWA bildirimi)
        self._write("manifest.webmanifest", json.dumps({
            "name": cfg.site.get("name", "Smarity"), "short_name": cfg.site.get("name", "Smarity"),
            "description": cfg.site.get("tagline", ""), "lang": "tr", "start_url": f"{b}/?kaynak=uygulama",
            "scope": f"{b}/", "display": "standalone", "background_color": "#FFFFFF", "theme_color": "#FFFFFF",
            "icons": [{"src": f"{b}/static/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
                      {"src": f"{b}/static/logo.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}]},
            ensure_ascii=False, indent=1))
        news = [p for p in posts if hours_since(p.get("published_at")) <= 48][:1000]
        self._write("news-sitemap.xml", self.env.get_template("news-sitemap.xml").render(**ctx, posts=news))
        self._write("robots.txt", "User-agent: *\nAllow: /\nDisallow: /api/\n\n"
                                  f"Sitemap: {cfg.site_url}/sitemap.xml\nSitemap: {cfg.site_url}/news-sitemap.xml\n")
        self._write(f"{key}.txt", key)
        latest_json = [{"id": p["id"], "title": p["title"], "summary": p["summary"], "url": p["abs_url"],
                        "image": p["abs_img"], "og_image": p["abs_og"], "category": p["category"],
                        "published_at": p["published_at"],
                        "sources": [{"name": s["name"], "url": s["url"]} for s in p.get("sources", [])]}
                       for p in posts[:50]]
        self._write("api/latest.json", json.dumps(latest_json, ensure_ascii=False, indent=1))
        (out / ".nojekyll").write_text("")
        log.info("Site üretildi: %d haber, %d sayfa, %d konu → %s", len(posts), pages, len(tags), out)
        return len(posts)
