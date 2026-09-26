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
from .store import Store
from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date

ASSET_V = "8"
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
        ext = "webp" if (cfg.images_dir / f"{p['id']}.webp").exists() else "jpg"
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
                tags.append({"label": t, "slug": ts, "url": f"{b}/etiket/{ts}/"})
        cat = p.get("category", DEFAULT_CATEGORY)
        return {
            **p,
            "url": f"{b}/haber/{p['slug']}/",
            "title_disp": nobr_hyphen(title),
            "short_disp": nobr_hyphen(short),
            "kicker_disp": p.get("kicker") or category_label(cat),
            "hero_stat": (p.get("hero_stat") or "").strip(),
            "hero_stat_label": (p.get("hero_stat_label") or "").strip(),
            "ai_image": (p.get("image") or {}).get("source") == "ai",
            "cover_image": (p.get("image") or {}).get("source") == "cover",
            "stat_on_cover": (p.get("image") or {}).get("source") == "cover" and (p.get("image") or {}).get("layout") == "sayi",
            "img_alt": clip(p.get("image_alt") or f"{short}: habere ait görsel", 125),
            "seo_title": seo_title,
            "meta_description": clip(meta, 158),
            "focus_keyword": p.get("focus_keyword", ""),
            "tag_list": tags,
            "abs_url": cfg.post_url(p["slug"]),
            "img": f"{b}/img/{p['id']}.{ext}",
            "abs_img": f"{cfg.site_url}/img/{p['id']}.{ext}",
            "abs_og": f"{cfg.site_url}/img/{p['id']}-og.jpg" if has_og else f"{cfg.site_url}/static/og-default.jpg",
            "date_str": tr_date(pub, cfg.tz),
            "date_short": tr_date(pub, cfg.tz, with_time=False),
            "iso": iso(dt),
            "mod_iso": iso(max(mod, dt)),
            "rfc822": format_datetime(dt),
            "cat_label": category_label(cat),
            "cat_seo": category_seo(cat)[0],
            "cat_color": category_color(cat),
            "cat_url": f"{b}/kategori/{cat}/",
            "abs_cat_url": f"{cfg.site_url}/kategori/{cat}/",
            "credits": list(dict.fromkeys(s["name"] for s in p.get("sources", []))),
            "minutes": reading_minutes(p.get("body", "")),
            "words": len(plain(p.get("body", "")).split()),
            "body_html": (body_html := render_body(p.get("body", ""))),
            "toc": [{"id": m.group(1), "text": re.sub("<[^>]+>", "", m.group(2))}
                    for m in re.finditer(r'<h2 id="([^"]+)">(.*?)</h2>', body_html)],
            "key_points": [x for x in (p.get("carousel_points") or []) if x][:4],
            "photos": self._photos(p, short),
            "has_photo": (p.get("image") or {}).get("source") == "photo",
            "updated_str": tr_date(p.get("updated_at"), cfg.tz) if p.get("updated_at") else "",
        }

    def _photos(self, p: dict, short: str) -> list[dict]:
        """Haberin gerçek fotoğrafları (ilki ana görsel). Yerel kopyası silinmiş galeri fotoğrafı kaynaktan gösterilir."""
        cfg, b = self.cfg, self.base
        out = []
        for i, r in enumerate(p.get("photos") or []):
            local = bool(r.get("file")) and (cfg.images_dir / r["file"]).exists()
            if not local and (i == 0 or not r.get("src")):
                continue
            out.append({
                "url": f"{b}/img/{r['file']}" if local else r["src"],
                "remote": not local,
                "credit": r.get("credit") or "",
                "page": r.get("page") or "",
                "alt": clip(r.get("alt") or (p.get("image_alt") if i == 0 else "") or f"{short} ({i + 1})", 125),
                "w": r.get("w") or 1600, "h": r.get("h") or 900,
            })
        return out

    def _write(self, rel: str, content: str) -> None:
        path = self.cfg.out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def _featured(posts: list[dict], n: int) -> list[dict]:
        """Manşet: son 3 günün en önemli haberleri (eşitlikte en yenisi); yetmezse en yeniler."""
        fresh = [p for p in posts if hours_since(p.get("published_at")) <= 72]
        pick = sorted(fresh, key=lambda p: (-int(p.get("importance") or 5), -(parse_iso(p.get("published_at")) or now_utc()).timestamp()))[:n]
        for p in posts:
            if len(pick) >= n:
                break
            if p not in pick:
                pick.append(p)
        return pick

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
                 "url": f"{b}/kategori/{k}/", "lastmod": latest_by_cat.get(k)} for k, v in CATEGORIES.items()]

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
            names = [f"{p['id']}.webp", f"{p['id']}.jpg", f"{p['id']}-og.jpg"]
            names += [ph["url"].rsplit("/", 1)[-1] for ph in p.get("photos") or [] if not ph.get("remote")]
            for name in dict.fromkeys(names):
                src = cfg.images_dir / name
                if src.exists():
                    shutil.copy2(src, out / "img" / name)

        # ana sayfa: manşet + son haberler; devamı arşiv sayfalarında
        n_feat = int(seo.get("featured_count", 5) or 5)
        featured = self._featured(posts, n_feat)
        for p in featured:
            src = cfg.images_dir / p["img"].rsplit("/", 1)[-1]
            p["slide_bg"], p["slide_dark"] = edge_color(src)
        rest = [p for p in posts if p not in featured]
        latest = rest[:12] if len(rest) >= 3 else posts[:6]
        if len(latest) > 3:
            latest = latest[:len(latest) - len(latest) % 3]
        shown = {p["id"] for p in featured} | {p["id"] for p in latest}
        archive = [p for p in posts if p["id"] not in shown]
        per = int(cfg.site.get("posts_per_page", 18))
        pages = 1 + (len(archive) + per - 1) // per
        rails = []
        for c in sorted(cats, key=lambda c: -c["count"]):
            cp = [p for p in posts if p["category"] == c["slug"]]
            if len(cp) >= 4 and len(rails) < 3:
                rails.append({"cat": c, "posts": cp[:10]})
        self._write("index.html", self.env.get_template("index.html").render(
            **ctx, featured=featured, latest=latest, rails=rails, tags=site["top_tags"],
            latest_iso=max((q["iso"] for q in posts), default=site["built_iso"]),
            latest_str=tr_date(max((q.get("published_at") or "" for q in posts), default=None), cfg.tz),
            page=1, pages=pages, next_url=f"{b}/sayfa/2/" if pages > 1 else None,
            canonical=cfg.site_url + "/"))
        for n in range(2, pages + 1):
            chunk = archive[(n - 2) * per:(n - 1) * per]
            self._write(f"sayfa/{n}/index.html", self.env.get_template("archive.html").render(
                **ctx, posts=chunk, page=n, pages=pages,
                prev_url=f"{b}/" if n == 2 else f"{b}/sayfa/{n - 1}/",
                next_url=f"{b}/sayfa/{n + 1}/" if n < pages else None,
                canonical=f"{cfg.site_url}/sayfa/{n}/"))

        # haber sayfaları
        for p in posts:
            same_tag = {t["slug"] for t in p["tag_list"]}
            related = sorted((q for q in posts if q["id"] != p["id"]),
                             key=lambda q: (-(len(same_tag & {t["slug"] for t in q["tag_list"]}) * 2
                                              + (q["category"] == p["category"])), posts.index(q)))[:8]
            self._write(f"haber/{p['slug']}/index.html", self.env.get_template("article.html").render(
                **ctx, post=p, related=related, canonical=p["abs_url"]))

        # kategoriler
        for c in cats:
            cp = [p for p in posts if p["category"] == c["slug"]][:120]
            self._write(f"kategori/{c['slug']}/index.html", self.env.get_template("category.html").render(
                **ctx, cat=c, posts=cp, active_cat=c["slug"], canonical=f"{cfg.site_url}/kategori/{c['slug']}/",
                noindex=not cp))

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
