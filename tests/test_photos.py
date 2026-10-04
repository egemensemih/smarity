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

_REAL_GATHER = photos.gather          # bazı testler gather'ı geçici olarak değiştiriyor

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


def _doc(size=(1600, 900)):
    """Belge / ekran görüntüsü benzeri: beyaz zemin, sık yazı satırları."""
    import random
    rnd = random.Random(3)
    im = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, size[0], 70], fill=(36, 41, 47))                  # üst menü çubuğu
    for y in range(110, size[1] - 40, 34):
        x = 60 + rnd.randrange(0, 40)
        while x < size[0] - 200:
            w = rnd.randrange(30, 110)
            d.rectangle([x, y, x + w, y + 14], fill=(40, 40, 40))       # sözcükler
            x += w + 12
    return im


def test_is_graphic():
    assert photos.is_graphic(_doc())
    assert not photos.is_graphic(_photo("#335"))
    plain = Image.new("RGB", (1600, 900), "white")                   # düz zeminde ürün: fotoğraf sayılır
    ImageDraw.Draw(plain).ellipse([500, 200, 1100, 700], fill=(120, 90, 200))
    assert not photos.is_graphic(plain)


def test_gather_skip_cover_and_graphics_last():
    pages = {"https://tr.com/a": HTML.replace("cdn.site.com", "cdn.tr.com")}
    imgs = {}

    def fake_fetch(url, referer="", timeout=20):
        if url not in imgs:
            imgs[url] = _doc() if "rear" in url else _photo("#553", seed=len(imgs) + 10)
        return imgs[url]

    photos.fetch_html, photos.fetch_image = (lambda u: pages.get(u, "")), fake_fetch
    got = photos.gather([{"name": "TR Site", "url": "https://tr.com/a", "kind": "media",
                          "image": "https://cdn.tr.com/feed-card.jpg"}], limit=6, per_source=6, skip_cover={"TR Site"})
    kinds = [g["kind"] for g in got]
    assert kinds and set(kinds) == {"body"}                            # besleme/og görseli alınmadı
    assert got[-1]["graphic"] and not got[0]["graphic"]                # grafik en sona


class _App:
    """Geçici klasörde uygulama; çıkışta tarayıcıyı kapatır (bir sonraki test yeniden açabilsin)."""
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
        self.cfg = Config(raw=raw, root=Path(self.tmp.name), site_url="https://smarity.com.tr")
        self.app = appmod.App(self.cfg)
        return self.cfg, self.app

    def __exit__(self, *exc):
        if self.app._vis:
            self.app._vis.close()
        self.tmp.cleanup()


def _post(**kw):
    return {"id": "p1", "slug": "ornek", "title": "Örnek araba 15 bin euroya tanıtıldı", "short_title": "Örnek araba tanıtıldı",
            "summary": "Özet", "category": "teknoloji", "tags": ["Dacia Hipster"], "hero_stat": "15 bin €",
            "hero_stat_label": "başlangıç fiyatı",
            "body": "\n\n".join(f"Paragraf {i} metni." for i in range(1, 9)), "published_at": iso(now_utc()),
            "image": {"source": "cover"}, "sources": [{"name": "Marka", "url": "https://brand.com/press", "kind": "official"}], **kw}


def test_attach_cover_slides_inline_and_buttons():
    with _App() as (cfg, a):
        a.store.save_post(_post())
        shots = [{"image": _photo("#446", seed=i), "src": f"https://x/{i}.jpg", "credit": "Marka", "page": "https://brand.com/press",
                  "alt": "", "kind": "og" if i == 0 else "body", "graphic": False} for i in range(4)]
        shots.append({"image": _doc(), "src": "https://x/doc.jpg", "credit": "Marka", "page": "https://brand.com/press",
                      "alt": "", "kind": "body", "graphic": True})
        appmod.photos.gather = lambda *a_, **k: shots
        a.backfill_photos(5)
        p = a.store.load_post("p1")
        assert len(p["photos"]) == 5 and p["photos_v"] == 2
        # ilk 4 fotoğraf siteye kopyalanır, kalanlar kaynaktaki adresinden gösterilir
        assert [r.get("file") for r in p["photos"]] == [f"p1-g{i}.webp" for i in range(4)] + [None]
        assert p["photos"][4]["remote"] and p["photos"][4]["src"] == "https://x/doc.jpg" and p["photos"][4]["w"]
        assert p["image"]["source"] == "photo" and p["image"]["photo"] == "p1-g0.webp"
        hero = cfg.images_dir / "p1.webp"
        assert hero.exists() and Image.open(hero).size == (1280, 960)
        assert Image.open(cfg.images_dir / "p1-og.jpg").size == (1200, 630)
        # kapak fotoğrafın kendisi değil, tasarım: alt kısım (yazı ve karartma) fotoğraftan farklı
        ph = Image.open(cfg.images_dir / "p1-g0.webp").convert("L").resize((64, 48))
        cv = Image.open(hero).convert("L").resize((64, 48))
        from PIL import ImageChops, ImageStat
        assert ImageStat.Stat(ImageChops.difference(ph.crop((0, 36, 64, 48)), cv.crop((0, 36, 64, 48)))).mean[0] > 20
        # site: ana görsel yazısız fotoğrafın kendisi; diğer fotoğraflar ve grafik paragraf paragraf metnin içinde
        from haberbot.site import SiteBuilder
        view = SiteBuilder(cfg)._post_view(p)
        assert view["hero_stat"] == ""                                     # "15 bin €" yurtdışı fiyatı öne çıkarılmaz
        assert view["cover_photo"]["file"] == "p1-g0.webp" and view["disp"]["file"] == "p1-g0.webp"
        assert view["img"] == "/img/p1-g0.webp" and view["slides"] == []
        assert view["body_html"].count('<figure class="inl') == 4 and 'class="inl graphic"' in view["body_html"]
        SiteBuilder(cfg).build()
        assert not (cfg.out_dir / "img" / "p1.webp").exists()            # yazılı kapak sitede kullanılmıyor
        html = (cfg.out_dir / cfg.post_path(p) / "index.html").read_text(encoding="utf-8")
        assert "/img/p1-g3.webp" in html and "Görsel: Marka" in html and "https://x/doc.jpg" in html
        assert html.index("/img/p1-g0.webp") < html.index('class="art-body"') < html.index("/img/p1-g1.webp")
        # düğmeler: başka foto, yazılı kapak, fotoğrafsız
        assert [b["callback_data"][0] for b in a._visual_buttons(p)] == ["g", "v", "n"]
        a._on_button("g", "p1")                                # sonraki fotoğraf kapak olur
        p = a.store.load_post("p1")
        assert p["image"]["photo"] == "p1-g0.webp" and p["photos"][0]["src"] == "https://x/1.jpg"
        assert p["photos"][3]["src"] == "https://x/0.jpg" and p["photos"][4]["graphic"]
        a._on_button("v", "p1")                                # yazılı kapak: fotoğraflar kalır
        p = a.store.load_post("p1")
        assert p["image"]["source"] == "cover" and len(p["photos"]) == 5 and p["cover_mode"] == "type"
        assert a._visual_buttons(p)[0]["text"].endswith("Fotoğraflı kapak")
        view = SiteBuilder(cfg)._post_view(p)
        assert view["cover_photo"]["file"] == "p1-g0.webp" and view["disp"]["kind"] == "photo"   # sitede yine fotoğraf
        assert view["body_html"].count('<figure class="inl') == 4
        a._on_button("g", "p1")                                # fotoğraflı kapağa dönüş
        assert a.store.load_post("p1")["image"]["source"] == "photo"
        a._on_button("n", "p1")                                # fotoğrafsız
        p = a.store.load_post("p1")
        assert "photos" not in p and a._visual_buttons(p)[0]["callback_data"].startswith("v:")
        assert not list(cfg.images_dir.glob("p1-g*.webp"))


def test_small_or_graphic_photos_get_type_cover():
    with _App() as (cfg, a):
        a.store.save_post(_post())
        shots = [{"image": _photo("#446", size=(720, 480), seed=1), "src": "https://x/s.jpg", "credit": "Site", "page": "https://s",
                  "alt": "", "kind": "body", "graphic": False},
                 {"image": _doc(), "src": "https://x/d.jpg", "credit": "Site", "page": "https://s", "alt": "", "kind": "og", "graphic": True}]
        appmod.photos.gather = lambda *a_, **k: shots
        a.backfill_photos(5)
        p = a.store.load_post("p1")
        assert p["image"]["source"] == "cover" and len(p["photos"]) == 2    # küçük fotoğraf ve grafik kapak olmaz
        from haberbot.site import SiteBuilder
        view = SiteBuilder(cfg)._post_view(p)
        # sitede yazı basılmadığı için 720 px'lik fotoğraf da ana görsel olur (boş renk ağı yerine)
        assert view["disp"]["kind"] == "photo" and view["disp"]["file"] == "p1-g0.webp" and view["slides"] == []
        assert view["body_html"].count('<figure class="inl') == 1 and 'class="inl graphic"' in view["body_html"]
        # yalnızca ekran görüntüsü varsa o gösterilir, kırpılmadan
        p["photos"] = [r for r in p["photos"] if r.get("graphic")]
        view = SiteBuilder(cfg)._post_view(p)
        assert view["disp"]["fit"] and view["disp"]["file"] == p["photos"][0]["file"]


def test_more_photos_only_when_more_found():
    with _App() as (cfg, a):
        a.store.save_post(_post())
        shot = lambda i: {"image": _photo("#446", seed=i), "src": f"https://x/{i}.jpg", "credit": "Marka",  # noqa: E731
                          "page": "https://brand.com/press", "alt": "", "kind": "body", "graphic": False}
        appmod.photos.gather = lambda *a_, **k: [shot(0), shot(1)]
        a.backfill_photos(5)
        assert len(a.store.load_post("p1")["photos"]) == 2
        appmod.photos.gather = lambda *a_, **k: [shot(5)]                 # daha az fotoğraf: dokunma
        a.more_photos()
        assert [r["src"] for r in a.store.load_post("p1")["photos"]] == ["https://x/0.jpg", "https://x/1.jpg"]
        a.state["more_photos"] = []
        appmod.photos.gather = lambda *a_, **k: [shot(i) for i in range(7)]   # daha çok: 4'ü yerel, 3'ü kaynaktan
        a.more_photos()
        ph = a.store.load_post("p1")["photos"]
        assert len(ph) == 7 and sum(1 for r in ph if r.get("file")) == 4 and sum(1 for r in ph if r.get("remote")) == 3


def test_wikipedia_fallback_and_missing_photo_fill():
    assert photos._wiki_names(["Apple", "MacBook Pro", "Türkiye", "yapay zeka"]) == ["MacBook Pro", "Apple"]
    real_gather, real_wiki = _REAL_GATHER, photos.wiki_photo
    photos.gather = _REAL_GATHER
    try:
        photos.wiki_photo = lambda names: {"image": _photo("#335", seed=3), "src": "https://upload.wikimedia.org/x.jpg",
                                           "credit": "Wikipedia", "page": "https://tr.wikipedia.org/wiki/X", "alt": "X",
                                           "kind": "wiki", "graphic": False, "cover_ok": True}
        got = _REAL_GATHER([], entities=["MacBook Pro"])               # kaynaklarda fotoğraf yok → Wikipedia
        assert len(got) == 1 and got[0]["credit"] == "Wikipedia"
        assert _REAL_GATHER([], entities=None) == []
        with _App() as (cfg, a):
            a.store.save_post(_post(photos_tried=iso(now_utc())))        # yakın zamanda denenmiş, yine de doldurulur
            appmod.photos.gather = lambda *a_, **k: [photos.wiki_photo(k.get("entities"))]
            a.fill_missing_photos()
            p = a.store.load_post("p1")
            assert p["photos"][0]["credit"] == "Wikipedia" and p["photos_filled"]
            from haberbot.site import SiteBuilder
            assert SiteBuilder(cfg)._post_view(p)["disp"]["kind"] == "photo"
            a.fill_missing_photos()                                       # artık fotoğraflı: tekrar denenmez
            assert a.store.load_post("p1")["photos"] == p["photos"]
            # konuyla eşleşmeyen Wikipedia görseli (haber X değil başka bir şirketle ilgili) kaldırılır
            a.store.save_post({**a.store.load_post("p1"), "entities": ["Manus"]})
            a.recheck_wiki_photos()
            q = a.store.load_post("p1")
            assert "photos" not in q and not q.get("photos_removed") and q["image"]["source"] == "cover"
            assert a._photo_names({"entities": ["Manus"], "tags": ["Manus", "Tencent"]}) == ["Manus"]
    finally:
        photos.gather, photos.wiki_photo = real_gather, real_wiki
        appmod.photos.gather = real_gather


def test_english_title_is_rewritten():
    from haberbot.textfix import looks_english
    assert looks_english("Microsoft's Copilot reboot pins focus on business customers")
    assert not looks_english("The Last of Us 3. sezon tarihi") and not looks_english("iPhone 18 Pro tanıtıldı")
    with _App() as (cfg, a):
        from haberbot.llm import MockLLM
        a.llm = MockLLM()
        calls = []
        real = a.llm.json

        def fake(model, system, user, schema, **k):
            out = real(model, system, user, schema, **k)
            calls.append(user)
            if "body" in schema.get("properties", {}) and len(calls) == 1:
                out["title"] = "Microsoft's Copilot reboot pins focus on business customers"
            return out
        a.llm.json = fake
        res = a._write([{"credit": "Bloomberg", "kind": "media", "title": "Copilot reboot", "url": "https://b.com/x",
                         "published": iso(now_utc()), "summary": "s", "text": "t"}])
        assert len(calls) == 2 and "Türkçe olmalı" in calls[1] and not looks_english(res["title"])


def test_photo_editor_drops_unrelated_images():
    # sayfadaki reklam / alışveriş bloğu ve başka siteye giden bağlantıdaki görseller aday olmaz
    html = """<html><body><article class="post-content">
      <p><img src="https://site.com/byd-seal-07.jpg" width="1200"></p>
      <div class="wt-shopping-box"><img src="https://site.com/anahtarlik-mouse.jpg" width="1200"></div>
      <a href="https://www.hepsiburada.com/x"><img src="https://site.com/kampanya.jpg" width="1200"></a>
      <a href="https://site.com/byd-big.jpg"><img src="https://site.com/byd-2.jpg" width="1200"></a>
    </article></body></html>"""
    urls = [c["url"] for c in photos.candidates(html, "https://site.com/haber")]
    assert urls == ["https://site.com/byd-seal-07.jpg", "https://site.com/byd-2.jpg"]
    with _App() as (cfg, a):
        class Editor:
            seen = []

            def json(self, model, system, user, schema, max_tokens=0, effort=None, images=None):
                Editor.seen.append(len(images or []))
                return {"keep": [2, 0, 9]}                    # 1 numara ilgisiz; 9 yok sayılır
        a.llm = Editor()
        got = [{"image": _photo("#446", seed=i), "src": f"https://x/{i}.jpg"} for i in range(3)]
        kept = a._vet_photos({"id": "d1", "title": "BYD Seal 07", "summary": "s"}, got)
        assert [g["src"] for g in kept] == ["https://x/2.jpg", "https://x/0.jpg"] and Editor.seen == [3]
        # yayındaki haberin fotoğrafları da bir kez denetlenir; ilgisiz olan silinir
        a.store.save_post(_post())
        appmod.photos.gather = lambda *a_, **k: [{"image": _photo("#446", seed=i), "src": f"https://x/{i}.jpg", "credit": "M",
                                                  "page": "https://p", "alt": "", "kind": "body", "graphic": False}
                                                 for i in range(3)]
        a.llm = None
        a.backfill_photos(5)
        assert len(a.store.load_post("p1")["photos"]) == 3
        a.llm = Editor()
        a.vet_existing_photos()
        p = a.store.load_post("p1")
        assert [r["src"] for r in p["photos"]] == ["https://x/0.jpg", "https://x/2.jpg"] and p["photos_vetted"]
        assert not (cfg.images_dir / "p1-g1.webp").exists()
        a.vet_existing_photos()                                    # ikinci kez denetlenmez
        assert Editor.seen == [3, 3]
        appmod.photos.gather = _REAL_GATHER


def test_migrate_old_layout():
    with _App() as (cfg, a):
        cfg.images_dir.mkdir(parents=True, exist_ok=True)
        # eski düzen: ilk fotoğraf {id}.webp; DonanımHaber'in ilk fotoğrafı yazılı paylaşım görseli
        _photo("#a55", seed=1).save(cfg.images_dir / "p1.webp", "WEBP")
        _doc().save(cfg.images_dir / "p1-g1.webp", "WEBP")
        _photo("#5a5", seed=2).save(cfg.images_dir / "p1-g2.webp", "WEBP")
        _photo("#55a", seed=3).save(cfg.images_dir / "p1-g3.webp", "WEBP")
        recs = [{"file": "p1.webp", "src": "https://log/og.jpg", "credit": "LOG", "page": "https://log", "w": 1600, "h": 900},
                {"file": "p1-g1.webp", "src": "https://log/doc.jpg", "credit": "LOG", "page": "https://log", "w": 1600, "h": 900},
                {"file": "p1-g2.webp", "src": "https://dh/card.jpg", "credit": "DonanımHaber", "page": "https://dh", "w": 1600, "h": 900},
                {"file": "p1-g3.webp", "src": "https://dh/body.jpg", "credit": "DonanımHaber", "page": "https://dh", "w": 1600, "h": 900}]
        a.store.save_post(_post(photos=recs, image={"source": "photo", "credit": "LOG"}))
        a.upgrade_photos()
        p = a.store.load_post("p1")
        assert p["photos_v"] == 2
        assert [r["src"] for r in p["photos"]] == ["https://log/og.jpg", "https://dh/body.jpg", "https://log/doc.jpg"]
        assert [r["graphic"] for r in p["photos"]] == [False, False, True]
        assert sorted(f.name for f in cfg.images_dir.glob("p1-g*.webp")) == ["p1-g0.webp", "p1-g1.webp", "p1-g2.webp"]
        assert p["image"]["source"] == "photo" and p["image"]["photo"] == "p1-g0.webp"
        assert (cfg.images_dir / "p1.webp").exists() and (cfg.images_dir / "p1-og.jpg").exists()
        a.upgrade_photos()                                    # ikinci kez: dokunmaz
        assert a.store.load_post("p1")["photos"] == p["photos"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
