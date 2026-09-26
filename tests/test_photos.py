"""Gerçek fotoğraf hattı testleri (ağ yok: sayfa ve görseller sahte)."""
import sys
import tempfile
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haberbot import app as appmod  # noqa: E402
from haberbot import photos  # noqa: E402
from haberbot.config import ROOT, Config  # noqa: E402
from haberbot.util import iso, now_utc  # noqa: E402

HTML = """<html><head>
<meta property="og:image" content="https://cdn.site.com/2026/09/car-1200x675.jpg">
<meta name="twitter:image" content="https://cdn.site.com/2026/09/car.jpg?w=800">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"NewsArticle","image":["https://cdn.site.com/2026/09/car-side.jpg"]}</script>
</head><body><header><img src="/logo.png"></header>
<article><h1>T</h1>
<img src="/wp-content/uploads/interior-300x200.jpg" srcset="/wp-content/uploads/interior-300x200.jpg 300w, /wp-content/uploads/interior-1600x900.jpg 1600w" alt="İç mekan">
<img data-src="https://cdn.site.com/rear.webp" width="1200">
<img src="https://cdn.site.com/icon-share.png" width="24">
<img src="https://cdn.site.com/tiny.jpg" width="120">
<div class="author-box"><img src="https://cdn.site.com/me.jpg"></div>
<img src="data:image/gif;base64,xx">
</article><aside><img src="https://cdn.site.com/ad.jpg"></aside></body></html>"""


def test_candidates():
    c = photos.candidates(HTML, "https://site.com/news/x")
    urls = [x["url"] for x in c]
    assert urls[0] == "https://cdn.site.com/2026/09/car-1200x675.jpg"          # paylaşım görseli önce
    assert "https://cdn.site.com/2026/09/car.jpg?w=800" not in urls            # aynı fotoğrafın başka boyutu
    assert "https://cdn.site.com/2026/09/car-side.jpg" in urls                 # yapılandırılmış veri
    assert "https://site.com/wp-content/uploads/interior-1600x900.jpg" in urls  # srcset'in en büyüğü
    assert "https://cdn.site.com/rear.webp" in urls                            # tembel yükleme
    assert not any(k in u for u in urls for k in ("logo", "icon-share", "tiny", "me.jpg", "ad.jpg", "data:"))
    assert next(x for x in c if "interior" in x["url"])["alt"] == "İç mekan"


def _photo(color, size=(1600, 900), seed=0):
    import random
    rnd = random.Random(seed)
    im = Image.new("RGB", size, color)
    d = ImageDraw.Draw(im)
    for _ in range(40):
        x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
        d.ellipse([x, y, x + rnd.randint(80, 500), y + rnd.randint(80, 400)],
                  fill=(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)))
    return im


def test_usable_and_dedupe():
    assert photos.usable(_photo("#335"))
    assert not photos.usable(Image.new("RGB", (1600, 900), "white"))     # düz zemin
    assert not photos.usable(_photo("#335", (400, 300)))                 # küçük
    assert not photos.usable(_photo("#335", (3000, 800)))                # çok geniş şerit
    a, b = _photo("#335", seed=1), _photo("#335", seed=1).resize((800, 450))
    assert photos._similar(photos._dhash(a), photos._dhash(b))


def test_gather_prefers_official_and_feed_image():
    pages = {"https://brand.com/press": HTML, "https://news.com/a": HTML.replace("cdn.site.com", "cdn.news.com")}
    imgs = {}

    def fake_fetch(url, referer="", timeout=20):
        if url not in imgs:
            imgs[url] = _photo("#%02x%02x55" % (len(imgs) * 30 % 255, 90), seed=len(imgs))
        return imgs[url]

    photos.fetch_html, photos.fetch_image = (lambda u: pages.get(u, "")), fake_fetch
    got = photos.gather([
        {"name": "Haber Sitesi", "url": "https://news.com/a", "kind": "media", "image": "https://cdn.news.com/feed-hero.jpg"},
        {"name": "Marka", "url": "https://brand.com/press", "kind": "official"},
    ], limit=6, per_source=3)
    assert got[0]["credit"] == "Marka"                     # resmi kaynak önce
    assert [g["credit"] for g in got].count("Marka") == 3
    news = [g for g in got if g["credit"] == "Haber Sitesi"]
    assert news[0]["src"] == "https://cdn.news.com/feed-hero.jpg"   # beslemedeki görsel o kaynağın ilk adayı


def test_attach_backfill_and_buttons():
    with tempfile.TemporaryDirectory() as t:
        raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
        cfg = Config(raw=raw, root=Path(t), site_url="https://smarity.com.tr")
        a = appmod.App(cfg)
        post = {"id": "p1", "slug": "ornek", "title": "Örnek araba tanıtıldı", "summary": "Özet", "category": "teknoloji",
                "tags": [], "body": "Metin.", "published_at": iso(now_utc()), "image": {"source": "cover"},
                "sources": [{"name": "Marka", "url": "https://brand.com/press", "kind": "official"}]}
        a.store.save_post(post)
        shots = [{"image": _photo("#446", seed=i), "src": f"https://x/{i}.jpg", "credit": "Marka",
                  "page": "https://brand.com/press", "alt": "", "kind": "og"} for i in range(4)]
        appmod.photos.gather = lambda *a_, **k: shots
        a.backfill_photos(5)
        p = a.store.load_post("p1")
        assert p["image"]["source"] == "photo" and len(p["photos"]) == 4
        assert (cfg.images_dir / "p1.webp").exists() and (cfg.images_dir / "p1-g3.webp").exists()
        assert (cfg.images_dir / "p1-og.jpg").exists() and Image.open(cfg.images_dir / "p1-og.jpg").size == (1200, 630)
        # başka fotoğraf: sıra döner, ilk fotoğraf galeriye geçer
        first_src = p["photos"][0]["src"]
        a._reorder_photos(p, "post", p["photos"][1:] + p["photos"][:1])
        assert p["photos"][0]["src"] == "https://x/1.jpg" and p["photos"][-1]["src"] == first_src
        # site görünümü: yerel dosyalar, kredi
        from haberbot.site import SiteBuilder
        view = SiteBuilder(cfg)._post_view(p)
        assert view["photos"][0]["url"] == "/img/p1.webp" and view["photos"][0]["credit"] == "Marka"
        # site üretilince galeri dosyaları da yayına kopyalanır
        SiteBuilder(cfg).build()
        assert (cfg.out_dir / "img" / "p1-g2.webp").exists()
        html = (cfg.out_dir / "haber" / "ornek" / "index.html").read_text(encoding="utf-8")
        assert 'class="gal' in html and "Görsel: Marka" in html and "/img/p1-g1.webp" in html
        # eski galeri kopyaları silinir, kaynaktan gösterilir
        p["published_at"] = "2020-01-01T00:00:00+00:00"
        a.store.save_post(p)
        a.prune_gallery()                                   # varsayılan 0: hiçbir şey silinmez
        assert a.store.load_post("p1")["photos"][1]["file"]
        a.cfg.raw["images"]["gallery_keep_days"] = 30
        a.state["last_prune"] = None
        a.prune_gallery()
        p = a.store.load_post("p1")
        assert p["photos"][1]["file"] is None and not (cfg.images_dir / "p1-g1.webp").exists()
        view = SiteBuilder(cfg)._post_view(p)
        assert view["photos"][1]["remote"] and view["photos"][1]["url"].startswith("https://x/")
        assert [b["callback_data"][0] for b in a._visual_buttons(p)] == ["g", "n"]
        # fotoğrafsız
        a._drop_photos(p, "post")
        assert "photos" not in p and a._visual_buttons(p)[0]["callback_data"].startswith("v:")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
