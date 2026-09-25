"""Instagram otomatik paylaşım testleri (ağ yok: Instagram istemcisi sahte)."""
import sys
import tempfile
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

    def __init__(self, token, version="v25.0", timeout=60):
        self.token = token

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
