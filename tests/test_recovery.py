"""Google toparlanma planı: zayıf eski sayfalara noindex, basın görseli kuralı."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haberbot import site as sitemod  # noqa: E402
from haberbot.photos import press_ok  # noqa: E402
from haberbot.site import SiteBuilder, is_thin  # noqa: E402
from tests.test_home import _App, _post  # noqa: E402

SEO = {"prune_thin": True, "prune_before": "2026-11-25", "thin_words": 250}


def test_is_thin_rules():
    old = {"slug": "eski", "published_at": "2026-10-01T10:00:00+00:00",
           "sources": [{"name": "A", "url": "https://a.com/1"}]}
    assert is_thin(old, 180, SEO, set())
    assert not is_thin(old, 180, SEO, {"eski"})                                       # Google'da gösterim almış
    assert not is_thin(old, 400, SEO, set())                                          # dolu haber
    two = {**old, "sources": old["sources"] + [{"name": "B", "url": "https://b.com/1"}]}
    assert not is_thin(two, 180, SEO, set())                                          # iki ayrı yayın
    assert not is_thin({**old, "published_at": "2026-11-26T08:00:00+00:00"}, 180, SEO, set())   # yeni dönem
    assert not is_thin(old, 180, {**SEO, "prune_thin": False}, set())


def test_thin_pages_get_noindex_and_leave_sitemap(monkeypatch):
    with _App() as (cfg, a):
        cfg.raw.setdefault("seo", {}).update(SEO)
        monkeypatch.setattr(sitemod, "load_keep", lambda: {"haber-2"})
        # _post: 2 kısa paragraf, tek kaynak → zayıf; haber-2 Google'da gösterim almış, haber-3 yeni dönemde
        for i in (1, 2, 3):
            a.store.save_post(_post(i, 24 * 90 if i < 3 else 1, tags=["Apple"]))
        sb = SiteBuilder(cfg)
        sb.build()
        page = lambda slug: max((f.read_text(encoding="utf-8") for f in cfg.out_dir.rglob(f"{slug}/index.html")),  # noqa: E731
                                key=len)   # eski adreslerdeki yönlendirme sayfaları değil, haberin kendisi
        thin, kept = page("haber-1"), page("haber-2")
        assert 'content="noindex, follow"' in thin
        assert "noindex" not in kept
        sm = (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")
        assert "haber-1" not in sm and "haber-2" in sm


def test_press_photo_rule():
    hosts = ["apple.com", "togg.com.tr"]
    assert press_ok({"src_kind": "official", "src": "https://cdn.x.com/a.jpg"}, hosts)
    assert press_ok({"kind": "wiki", "src": "https://upload.wikimedia.org/a.jpg"}, hosts)
    assert press_ok({"src_kind": "media", "src": "https://www.apple.com/newsroom/images/a.jpg"}, hosts)
    assert press_ok({"src_kind": "media", "src": "https://newsroom.example.com/a.jpg"}, hosts)
    assert not press_ok({"src_kind": "media", "src": "https://www.theverge.com/a.jpg"}, hosts)
    assert not press_ok({"src_kind": "media", "src": "https://notapple.com/a.jpg"}, hosts)
    assert not press_ok({"src_kind": "media", "src": ""}, hosts)
