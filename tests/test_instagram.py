"""Instagram otomatik paylaşım testleri (ağ yok: Instagram istemcisi sahte)."""
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haberbot import app as appmod  # noqa: E402
from haberbot import instagram as ig  # noqa: E402
from haberbot.config import ROOT, Config  # noqa: E402
from haberbot.util import iso, now_utc  # noqa: E402


def test_seal_roundtrip_and_tamper():
    blob = ig.seal("secret-A", "IGAAT-refreshed-token")
    assert ig.unseal("secret-A", blob) == "IGAAT-refreshed-token"
    assert ig.unseal("secret-B", blob) is None           # başka anahtarla açılmaz
    raw = bytearray(ig.base64.urlsafe_b64decode(blob))
    raw[20] ^= 1
    assert ig.unseal("secret-A", ig.base64.urlsafe_b64encode(bytes(raw)).decode()) is None  # değişiklik fark edilir
    assert "IGAAT" not in blob


def test_token_store():
    data = {}
    ts = ig.TokenStore("secret-A", data)
    assert ts.token == "secret-A" and ts.refresh_due()
    ts.save("new-token", 60 * 86400)
    assert ig.TokenStore("secret-A", data).token == "new-token"
    assert 59 < ts.days_left() <= 60 and not ts.refresh_due()
    # kullanıcı gizli anahtarı değiştirdi → yeni anahtar kullanılır
    assert ig.TokenStore("secret-B", data).token == "secret-B"
    assert ig.TokenStore("secret-B", data).days_left() is None


def test_error_classification():
    assert ig.InstagramError("x", 190).auth
    assert not ig.InstagramError("x", 100).auth
    assert ig.InstagramError("x", 100, 33).auth


class FakeIG:
    calls = []

    def __init__(self, token, version="v25.0", timeout=60, ig_id=""):
        self.token = token
        self.fb = ig.is_fb_token(token)

    def me(self):
        return {"id": "178", "user_id": "178", "username": "smarity"}

    def refresh(self):
        raise ig.InstagramError("too new", 190)

    def carousel(self, target, urls, caption):
        FakeIG.calls.append(("carousel", target, tuple(urls), caption))
        if target == "me":
            raise ig.InstagramError("Unsupported post request", 100)
        return "M1", "https://www.instagram.com/p/abc/"

    def story(self, target, url):
        FakeIG.calls.append(("story", target, url))
        return "S1"


def _app(tmp: Path):
    raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    raw["social"]["instagram_hours"] = [0, 24]
    raw["social"]["instagram_every_post"] = True
    cfg = Config(raw=raw, root=tmp, site_url="https://example.github.io/smarity", mock=True,
                 instagram_token="SECRET-TOKEN", telegram_chat_id="1")
    return appmod.App(cfg)


def test_queue_and_publish_flow():
    FakeIG.calls = []
    appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 200)
    with tempfile.TemporaryDirectory() as t:
        a = _app(Path(t))
        post = {"id": "p1", "slug": "ornek-haber", "title": "Örnek haber başlığı", "summary": "Kısa özet.",
                "category": "teknoloji", "tags": ["Apple"], "body": "Metin.", "sources": [{"name": "Apple", "url": "https://a"}],
                "published_at": iso(now_utc())}
        a.store.save_post(post)
        assert a.ig_enabled
        a._send_social(post)                          # otomatik modda sıraya girer
        assert [x["id"] for x in a.state["ig_queue"]] == ["p1"]
        assert not a.ig_enqueue(post)                 # iki kez girmez
        a.ig_tick()
        assert a.state["ig_queue"] == []
        assert a.state["ig_done"][-1]["permalink"].endswith("/p/abc/")
        assert a.store.count(a.today(), "instagram") == 1
        assert a.store.ig["target"] == "178"          # "me" desteklenmeyince hesap numarasına geçti
        kinds = [c[0] for c in FakeIG.calls]
        assert kinds == ["carousel", "carousel", "story"]
        assert FakeIG.calls[1][2][0] == "https://example.github.io/smarity/ig/p1-post.jpg"
        assert "profildeki bağlantıda" in FakeIG.calls[1][3]
        # aynı turda ikinci haber boşluk süresi dolmadan paylaşılmaz
        post2 = {**post, "id": "p2", "slug": "ikinci"}
        a.store.save_post(post2)
        a.ig_enqueue(post2)
        a.ig_tick()
        assert [x["id"] for x in a.state["ig_queue"]] == ["p2"]
        # iptal ve geri alma düğmeleri
        assert a._on_button("x", "p2").startswith("🚫")
        assert a.state["ig_queue"] == []
        assert a._on_button("q", "p2").startswith("📸")
        # siteden kaldırılan haber sıradan düşer
        a._on_button("d", "p2")
        assert a.state["ig_queue"] == []
        out = (Path(t) / "data" / "_mock" / "outbox.jsonl").read_text(encoding="utf-8")
        assert "Instagram&#x27;da paylaşıldı" in out or "Instagram'da paylaşıldı" in out
        a.store.save()
        assert "SECRET-TOKEN" not in (Path(t) / "data" / "instagram.json").read_text()


def test_fb_system_user_token():
    """Meta'nın yeni "Unified login" kurulumu: EAA… anahtarı graph.facebook.com'da, hesap numarasıyla çalışır."""
    cli = ig.Instagram("EAAtest", ig_id="1784")
    assert cli.fb and cli.base.startswith("https://graph.facebook.com/")
    assert not ig.Instagram("IGAAtest").fb and ig.Instagram("IGAAtest").base.startswith("https://graph.instagram.com/")
    seen = []
    cli._req = lambda method, path, **params: seen.append(path) or {"id": "1784", "username": "smarityco"}
    assert cli.me() == {"id": "1784", "user_id": "1784", "username": "smarityco"} and seen == ["1784"]
    try:
        cli.refresh()
        raise AssertionError("sistem kullanıcısı anahtarı yenilenmemeli")
    except ig.InstagramError:
        pass
    FakeIG.calls = []
    appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 200)
    with tempfile.TemporaryDirectory() as t:
        a = _app(Path(t))
        a.cfg.instagram_token = "EAA-SECRET-TOKEN"
        post = {"id": "p1", "slug": "ornek-haber", "title": "Örnek haber başlığı", "summary": "Kısa özet.",
                "category": "teknoloji", "tags": ["Apple"], "body": "Metin.", "sources": [{"name": "Apple", "url": "https://a"}],
                "published_at": iso(now_utc())}
        a.store.save_post(post)
        a.ig_enqueue(post)
        a.ig_tick()
        assert a.state["ig_queue"] == [] and FakeIG.calls[0][1] == "178"   # "me" denenmeden doğrudan hesap numarası
        a.store.save()
        assert "EAA-SECRET-TOKEN" not in (Path(t) / "data" / "instagram.json").read_text()


def test_try_latest_command():
    FakeIG.calls = []
    appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 200)
    with tempfile.TemporaryDirectory() as t:
        a = _app(Path(t))
        for i, h in ((1, 5), (2, 1)):
            a.store.save_post({"id": f"p{i}", "slug": f"haber-{i}", "title": f"Haber {i}", "summary": "Özet.",
                               "category": "teknoloji", "tags": [], "body": "Metin.", "sources": [{"name": "A", "url": "https://a"}],
                               "published_at": iso(now_utc() - timedelta(hours=h))})
        a.cfg.raw["social"]["instagram_every_post"] = False
        a._send_social(a.store.load_post("p2"))                     # her haber otomatik sıraya girmez
        assert not a.state.get("ig_queue")
        assert "Haber 2" in a.ig_try_latest()                       # en yeni haber
        assert [x["id"] for x in a.state["ig_queue"]] == ["p2"]
        assert "Haber 1" in a.ig_try_latest()                       # sıradaki atlanır, bir öncekine geçer
        a.cfg.instagram_token = ""
        assert "bağlı değil" in a.ig_try_latest()


def _pub(i, hours, appeal, photo=True, **kw):
    return {"id": f"s{i}", "slug": f"sosyal-{i}", "title": f"Sosyal haber {i}", "summary": "Kısa özet.",
            "category": "teknoloji", "tags": [], "body": "Metin.", "sources": [{"name": "A", "url": "https://a"}],
            "published_at": iso(now_utc() - timedelta(hours=hours)), "appeal": appeal, "importance": appeal, **kw}


def test_social_desk_selects_and_limits():
    """Sosyal medya masası: her haber paylaşılmaz; gönderi ve hikâye günlük sınırları ve alt puanlar uygulanır."""
    FakeIG.calls = []
    appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 200)
    with tempfile.TemporaryDirectory() as t:
        a = _app(Path(t))
        a.cfg.raw["social"].update({"instagram_every_post": False, "instagram_daily_posts": 1, "instagram_daily_stories": 3})
        a.vis.best_photo = lambda d: {"credit": "Kaynak", "w": 1600, "h": 900} if d.get("photo") else None
        posts = [_pub(1, 1, 9, photo=True), _pub(2, 1, 9, photo=True), _pub(3, 1, 5), _pub(4, 1, 8), _pub(5, 1, 8)]
        for p in posts:
            p["photo"] = True
            a.store.save_post(p)
            a._send_social(p)
        q = {x["id"]: x["format"] for x in a.state["ig_queue"]}
        assert q == {"s1": "post", "s2": "story", "s4": "story"}            # 1 gönderi hakkı; ilgisiz haber elendi
        assert a.store.load_post("s5")["social"]["reason"]                   # hikâye hakkı doldu: gerekçe yazıldı
        assert a.store.load_post("s3")["social"]["format"] == "none"
        assert a.ig_budget() == (0, 0)
        # düğmeler: gönderiyi hikâyeye indir, hikâyeyi paylaşma (hak geri döner)
        assert "Hikâye" in a._on_button("y", "s1")
        assert a._on_button("x", "s4").startswith("🚫") and a.ig_budget() == (1, 1)
        # sıradaki hikâye yalnızca hikâye olarak paylaşılır; profil sayfası için haberde işaret kalır
        a.ig_tick()
        assert [c[0] for c in FakeIG.calls] == ["story", "story"][:len(FakeIG.calls)] and FakeIG.calls[0][0] == "story"
        assert a.store.load_post("s1")["ig"]["format"] == "story"


def test_manset_cards_and_instagram_page():
    """Manşet tarzı kartlar doğru boyutta üretilir; /instagram/ sayfası paylaşılan haberleri listeler."""
    from PIL import Image
    from haberbot.site import SiteBuilder
    with tempfile.TemporaryDirectory() as t:
        a = _app(Path(t))
        a.cfg.raw["social"]["card_style"] = "manset"
        a.cfg.images_dir.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1600, 900), (40, 90, 160)).save(a.cfg.images_dir / "m1-g0.webp")
        post = _pub(1, 1, 9, image={"source": "photo", "photo": "m1-g0.webp"},
                    photos=[{"file": "m1-g0.webp", "credit": "Apple", "w": 1600, "h": 900}],
                    carousel_points=["Birinci madde.", "İkinci madde.", "Üçüncü madde."])
        post["id"] = "m1"
        a.store.save_post(post)
        assert a.vis.best_photo(post)["credit"] == "Apple"
        sizes = {k: Image.open(a._card(post, k)).size for k in ("post", "c2", "c3", "story")}
        assert sizes == {"post": (1080, 1350), "c2": (1080, 1350), "c3": (1080, 1350), "story": (1080, 1920)}
        post2 = {**_pub(2, 2, 8), "ig": {"format": "story", "at": iso(now_utc())}}
        a.store.save_post(post2)
        if a._vis:
            a._vis.close()
            a._vis = None
        SiteBuilder(a.cfg).build()
        page = (a.cfg.out_dir / "instagram" / "index.html").read_text(encoding="utf-8")
        assert "Sosyal haber 2" in page and "Sosyal haber 1" not in page


def test_missing_card_triggers_rebuild():
    appmod.Instagram, appmod.head_ok = FakeIG, (lambda url: 404)
    with tempfile.TemporaryDirectory() as t:
        a = _app(Path(t))
        post = {"id": "p9", "slug": "x", "title": "T", "summary": "S", "category": "gaming", "tags": [],
                "body": "B", "sources": [], "published_at": iso(now_utc())}
        a.store.save_post(post)
        a.ig_enqueue(post)
        a.store.site_dirty = False
        a.state["ig_queue"][0]["queued_at"] = "2020-01-01T00:00:00+00:00"
        a.cfg.raw["social"]["instagram_max_wait_hours"] = 10 ** 6
        a.ig_tick()
        assert a.store.site_dirty and a.state["ig_queue"][0].get("restaged_at")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
