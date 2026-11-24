"""Sürekli güncel rehberler: eşleşme, uydurma rakam engeli, yazım turu ve site sayfaları."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haberbot import guides as G  # noqa: E402
from haberbot.site import SiteBuilder  # noqa: E402
from tests.test_home import _App, _post  # noqa: E402

SPEC = {"slug": "imei-kayit-ucreti", "title": "IMEI kayıt ücreti", "h1": "IMEI kayıt ücreti: güncel harç",
        "category": "teknoloji", "match": ["imei"]}


def test_matching_rules():
    p = {"title": "IMEI kayıt ücreti 2027 yılında 69.358 TL olacak", "tags": ["IMEI"], "category": "teknoloji"}
    assert G.matches(SPEC, p)                                                     # IMEI = imei (I/ı farkı yok)
    apple = {"match": ["iphone"], "need": ["fiyat", "zam"], "need_also": ["türkiye"]}
    assert G.matches(apple, {"title": "iPhone 17e Türkiye fiyatı açıklandı"})
    assert not G.matches(apple, {"title": "iPhone Duo tamir ücretleri açıklandı"})   # fiyat/zam yok
    assert not G.matches(apple, {"title": "iPhone 18 fiyatı ABD'de açıklandı"})      # Türkiye yok
    sam = {"match": ["galaxy"], "need": ["fiyat"], "skip": ["geely"]}
    assert not G.matches(sam, {"title": "Geely Galaxy E5 fiyatı", "tags": ["Geely"]})
    car = {"match": ["fiyat listesi"], "categories": ["otomotiv"]}
    assert G.matches(car, {"title": "Fiat Kasım 2026 fiyat listesi", "category": "otomotiv"})
    assert not G.matches(car, {"title": "Apple fiyat listesi", "category": "teknoloji"})
    sub = {"match": ["apple tv"], "match_in": "title", "need": ["ücret"]}
    assert not G.matches(sub, {"title": "HomePod mini ücreti", "tags": ["Apple TV"]})  # yalnızca başlık


def test_unsupported_numbers():
    posts = [{"title": "IMEI kayıt ücreti 69.358 TL", "summary": "", "body": "Ücret 2027'de 69.358 TL; 2026'da 45.614 TL."}]
    assert G.unsupported_numbers("Güncel ücret 69.358 TL, önceki 45.614 TL (2027).", posts) == []
    assert G.unsupported_numbers("Ücret 70.000 TL civarında.", posts) == ["70000"]          # uydurma rakam
    assert G.unsupported_numbers("Artış 23.744 TL oldu.", posts) == ["23744"]                # hesaplanmış rakam


def _imei_posts(a):
    a.store.save_post(_post(1, 30, title="2027 IMEI kayıt ücreti belli oldu: 69.358 TL", tags=["IMEI"],
                            body="## Ücret\n\nYurt dışından getirilen telefonlar için IMEI kayıt ücreti 69.358 TL oldu."))
    a.store.save_post(_post(2, 50, title="IMEI kayıt ücreti 2026 yılında 45.614 TL", tags=["IMEI"],
                            body="## Ücret\n\n2026 yılı IMEI kayıt ücreti 45.614 TL olarak uygulanıyor."))


def test_guide_written_checked_and_published(monkeypatch):
    with _App() as (cfg, a):
        cfg.raw["guides"] = {"enabled": True, "min_posts": 2, "list": [SPEC]}
        _imei_posts(a)
        calls = []
        long = " ".join(["Yurt dışından getirilen telefonlar için kayıt kuralları geçerlidir."] * 20)

        class LLM:
            def __init__(self, fee):
                self.fee = fee

            def json(self, model, system, user, schema, **_k):
                calls.append(user)
                return {"seo_title": "IMEI kayıt ücreti 2027", "meta_description": "Güncel IMEI kayıt ücreti.",
                        "summary": f"IMEI kayıt ücreti {self.fee} TL.",
                        "body": f"IMEI kayıt ücreti {self.fee} TL oldu; 2026'da 45.614 TL idi.\n\n## Kurallar\n\n{long}\n\n"
                                "| Yıl | Ücret |\n|---|---|\n| 2027 | 69.358 TL |\n| 2026 | 45.614 TL |",
                        "faq": [{"q": "IMEI ücreti ne kadar?", "a": f"{self.fee} TL."}],
                        "changes": "İlk sürüm.", "used": ["p01", "p02", "uydurma"]}

        a.llm = LLM("70.000")                                    # haberlerde olmayan rakam → bir kez düzelttirilir
        assert a.guides_tick() is False                          # yine olmuyor → yayımlanmaz
        assert len(calls) == 2 and "CORRECTION" in calls[1] and "70000" in calls[1]
        assert not G.guide_path(cfg, SPEC["slug"]).exists() and a.state["guide_tried"][SPEC["slug"]]
        assert a.guides_tick() is False and len(calls) == 2      # aynı haberlerle tekrar denenmez
        a.store.save_post(_post(3, 1, title="IMEI kayıt ücreti için e-Devlet dönemi", tags=["IMEI"],
                                body="IMEI kaydı için ücret 69.358 TL olarak e-Devlet'ten ödenebilecek."))
        a.llm = LLM("69.358")
        assert a.guides_tick() is True and len(calls) == 3
        g = G.load_guides(cfg)[0]
        assert g["based_on"] == ["p01", "p02"] and g["history"][0]["note"] == "İlk sürüm."
        assert a.guides_tick() is False                          # yeni haber yok: yeniden yazılmaz

        SiteBuilder(cfg).build()
        page = (cfg.out_dir / "rehber" / SPEC["slug"] / "index.html").read_text(encoding="utf-8")
        assert "IMEI kayıt ücreti: güncel harç" in page and "<table>" in page and "Son güncelleme" in page
        assert "noindex" not in page and "Bu rehberin dayandığı haberler" in page
        assert (cfg.out_dir / "rehber" / "index.html").exists()
        sm = (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")
        assert "/rehber/imei-kayit-ucreti/" in sm
        art = max((f.read_text(encoding="utf-8") for f in cfg.out_dir.rglob("haber-2/index.html")), key=len)
        assert 'class="guide-box"' in art and "/rehber/imei-kayit-ucreti/" in art   # eski haberden güncel rehbere
