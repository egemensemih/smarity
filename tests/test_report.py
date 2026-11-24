"""Haftalık rapor: Cloudflare okur verisi, kaynak adları, yayın özeti ve haftada bir gönderim."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import haberbot.app as appmod  # noqa: E402
from haberbot import report as R  # noqa: E402
from haberbot.util import iso, now_utc  # noqa: E402
from tests.test_home import _App, _post  # noqa: E402


def test_source_names_and_numbers():
    assert R.source_name("", "smarity.com.tr") == "Doğrudan"
    assert R.source_name("www.google.com.tr", "smarity.com.tr") == "Google"
    assert R.source_name("news.google.com", "smarity.com.tr") == "Google Haberler"
    assert R.source_name("l.instagram.com", "smarity.com.tr") == "Instagram"
    assert R.source_name("smarity.com.tr", "smarity.com.tr") is None          # site içi
    assert R.fmt(12345) == "12.345"
    assert R.change(120, 100) == " (önceki hafta 100, +%20)" and R.change(80, 100) == " (önceki hafta 100, -%20)"
    q = R.cf_query("acc", "site", R.date(2026, 11, 16), R.date(2026, 11, 22))
    assert 'date_geq: "2026-11-16"' in q and 'date_geq: "2026-11-09"' in q and "rumPageloadEventsAdaptiveGroups" in q


CF = {"total": [{"count": 900, "sum": {"visits": 400}}], "prev": [{"count": 600, "sum": {"visits": 320}}],
      "days": [{"sum": {"visits": 50}, "dimensions": {"date": "2026-11-19"}},
               {"sum": {"visits": 90}, "dimensions": {"date": "2026-11-20"}}],
      "pages": [{"count": 300, "dimensions": {"requestPath": "/"}},
                {"count": 120, "dimensions": {"requestPath": "/teknoloji/2026/11/haber-1"}},
                {"count": 99, "dimensions": {"requestPath": "/sitemap.xml"}}],
      "refs": [{"sum": {"visits": 200}, "dimensions": {"refererHost": "www.google.com"}},
               {"sum": {"visits": 30}, "dimensions": {"refererHost": "google.com.tr"}},
               {"sum": {"visits": 100}, "dimensions": {"refererHost": ""}},
               {"sum": {"visits": 70}, "dimensions": {"refererHost": "smarity.com.tr"}}]}


def test_weekly_report_text(monkeypatch):
    with _App() as (cfg, a):
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test")
        monkeypatch.setattr(R, "fetch_cf", lambda *_a: CF)
        p = _post(1, 30, title="Togg fiyat listesi açıklandı", cat="otomotiv")
        p["path"] = "teknoloji/2026/11/haber-1"
        a.store.save_post(p)
        a.state["ig_done"] = [{"id": "p01", "at": iso(now_utc() - timedelta(days=2)), "format": "post"},
                              {"id": "p02", "at": "2020-01-01T00:00:00Z", "format": "story"}]
        t = a.weekly_report_text()
        assert "Ziyaret: <b>400</b> (önceki hafta 320, +%25)" in t
        assert "Google 230" in t and "Doğrudan 100" in t and "smarity" not in t.split("Nereden")[1].split("\n")[1]
        assert "1. Ana sayfa — 300" in t and "2. Togg fiyat listesi açıklandı — 120" in t and "sitemap" not in t
        assert "Yeni haber: <b>1</b> (Otomotiv 1)" in t and "Instagram: 1 gönderi, 1 hikâye" in t
        monkeypatch.delenv("CLOUDFLARE_API_TOKEN")
        assert "CLOUDFLARE_API_TOKEN" in a.weekly_report_text()                 # anahtar yoksa yayın özeti yine gelir


def test_weekly_report_sent_once_on_monday(monkeypatch):
    with _App() as (cfg, a):
        from haberbot.telegram import MockTelegram
        a.tg = a.tg or MockTelegram(cfg.root / "tg")
        monday = datetime(2026, 11, 30, 7, 30, tzinfo=timezone.utc)          # Pazartesi 10:30 (İstanbul)
        monkeypatch.setattr(appmod, "now_utc", lambda: monday)
        a.maybe_weekly_report()
        a.maybe_weekly_report()
        out = (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8")
        assert out.count("Haftalık rapor") == 1 and "23–29 Kasım" in json.loads(out.splitlines()[-1])["text"]
        monkeypatch.setattr(appmod, "now_utc", lambda: datetime(2026, 12, 1, 7, 30, tzinfo=timezone.utc))  # salı
        a.maybe_weekly_report()
        assert (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8").count("Haftalık rapor") == 1


def test_rs256_matches_standard_library():
    import pytest
    crypto = pytest.importorskip("cryptography")  # noqa: F841
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for fmt in (serialization.PrivateFormat.PKCS8, serialization.PrivateFormat.TraditionalOpenSSL):
        pem = key.private_bytes(serialization.Encoding.PEM, fmt, serialization.NoEncryption()).decode()
        msg = b"header.claim"
        assert R.rs256(msg, pem) == key.sign(msg, padding.PKCS1v15(), hashes.SHA256())


GSC = {"cur": {"clicks": 12, "impressions": 1500, "position": 11.84}, "prev": {"clicks": 6, "impressions": 3000},
       "queries": [{"keys": ["togg fiyat listesi"], "impressions": 400, "clicks": 5},
                   {"keys": ["imei kayıt ücreti"], "impressions": 900, "clicks": 0}],
       "pages": [{"keys": ["https://smarity.com.tr/rehber/togg-fiyat-listesi/"], "impressions": 300}]}


def test_search_block_in_report(monkeypatch):
    with _App() as (cfg, a):
        monkeypatch.setenv("GSC_SERVICE_ACCOUNT", json.dumps({"client_email": "x@y", "private_key": "-----BEGIN PRIVATE KEY-----"}))
        monkeypatch.setattr(R, "fetch_gsc", lambda *_a: GSC)
        cfg.raw.setdefault("report", {})["gsc_site"] = "https://smarity.com.tr/"
        t = a.weekly_report_text()
        assert "Gösterim: <b>1.500</b> (önceki hafta 3.000, -%50)" in t
        assert "Tıklama: 12 (önceki hafta 6, +%100), ort. sıra 11,8" in t
        assert t.index("imei kayıt ücreti") < t.index("togg fiyat listesi")          # gösterime göre sıralı
        assert "/rehber/togg-fiyat-listesi/ — 300 gösterim" in t
        monkeypatch.setenv("GSC_SERVICE_ACCOUNT", "yanlış")
        assert "Google arama verisi alınamadı" in a.weekly_report_text()
        monkeypatch.delenv("GSC_SERVICE_ACCOUNT")
        assert "Google araması" not in a.weekly_report_text()                       # anahtar yoksa bölüm yok


def test_gsc_token_request_is_valid_jwt(monkeypatch):
    import base64 as b64
    import pytest
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    sent = {}

    class Resp:
        status_code = 200
        headers = {"content-type": "application/json; charset=utf-8"}

        def json(self):
            return {"access_token": "ya29.test"}

    def post(url, data=None, **_k):
        sent.update(url=url, **data)
        return Resp()
    monkeypatch.setattr(R.requests, "post", post)
    assert R.gsc_access_token({"client_email": "rapor@proje.iam.gserviceaccount.com", "private_key": pem}) == "ya29.test"
    head, claim, sig = sent["assertion"].split(".")
    pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
    key.public_key().verify(b64.urlsafe_b64decode(pad(sig)), f"{head}.{claim}".encode(), padding.PKCS1v15(), hashes.SHA256())
    c = json.loads(b64.urlsafe_b64decode(pad(claim)))
    assert c["iss"].startswith("rapor@") and c["scope"].endswith("webmasters.readonly") and c["exp"] - c["iat"] == 3600
    assert sent["url"] == R.GSC_TOKEN_URL and sent["grant_type"].endswith("jwt-bearer")
