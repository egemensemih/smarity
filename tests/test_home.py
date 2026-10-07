"""Ana sayfa seçkisi, metin düzeltmeleri ve manşet düğmeleri testleri."""
import re
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haberbot import app as appmod  # noqa: E402
from haberbot.config import ROOT, Config  # noqa: E402
from haberbot.site import SiteBuilder, hot  # noqa: E402
from haberbot.textfix import Fixer, missing_turkish, tag_display  # noqa: E402
from haberbot.util import iso, now_utc  # noqa: E402


def test_textfix():
    fx = Fixer(["Oyunun çıkış tarihi açıklandı. Erişim kararları ve Atatürk.", "Yeni özellikler için güncelleme."])
    assert fx.text("The Witcher 3 cikis tarihi ve yenilikleri aciklandi") == "The Witcher 3 çıkış tarihi ve yenilikleri açıklandı"
    assert fx.text("Steam erisim kararlari ve Ataturk") == "Steam erişim kararları ve Atatürk"
    assert fx.text("Galaxy S27 icin yeni ozellikler") == "Galaxy S27 için yeni özellikler"
    assert fx.text("İPhone 18 Pro tanıtıldı") == "iPhone 18 Pro tanıtıldı"
    assert fx.text("EFootball 2027 duyuruldu") == "eFootball 2027 duyuruldu"
    assert fx.text("Al Gore konuştu, one more thing") == "Al Gore konuştu, one more thing"   # özel ad ve İngilizce dokunulmaz
    assert fx.text("Cikis tarihi belli oldu") == "Çıkış tarihi belli oldu"                        # cümle başı büyük harf
    p = {"title": "Oyun cikis tarihi aciklandi", "tags": ["akilli gozluk", "Apple"], "body": "Metin."}
    assert set(fx.post(p)) == {"title", "tags"} and p["tags"][0] == "akıllı gözlük"
    assert missing_turkish("Bu oyun yarin tum platformlarda cikiyor ve fiyati belli oldu")
    assert not missing_turkish("World of Warcraft Forever duyuruldu")
    assert [tag_display(t) for t in ("elektrikli otomobil", "iPhone 18", "ısı pompası")] == \
        ["Elektrikli otomobil", "iPhone 18", "Isı pompası"]


def _post(i, hours, appeal=6, cat="teknoloji", **kw):
    return {"id": f"p{i:02d}", "slug": f"haber-{i}", "title": f"Haber {i} başlığı", "summary": "Özet cümlesi.",
            "category": cat, "tags": ["Apple"], "body": "Birinci paragraf.\n\nİkinci paragraf.", "appeal": appeal,
            "published_at": iso(now_utc() - timedelta(hours=hours)), "image": {"source": "cover"},
            "sources": [{"name": "Kaynak", "url": "https://k.com/a", "kind": "media"}], **kw}


def test_hot_ranking():
    fresh_low, fresh_high, old_high = _post(1, 1, 5), _post(2, 2, 9), _post(3, 60, 9)
    assert hot(fresh_high) > hot(fresh_low) and hot(fresh_high) > hot(old_high)
    assert hot(_post(4, 1, 6, image={"source": "photo"})) > hot(_post(5, 1, 6))
    assert hot(_post(6, 20, 5, home="pin", home_at=iso(now_utc()))) > hot(fresh_high)
    assert hot(_post(7, 1, 10, home="hide")) < 0


class _App:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
        self.cfg = Config(raw=raw, root=Path(self.tmp.name), site_url="https://smarity.com.tr", mock=True,
                          telegram_chat_id="1")
        self.app = appmod.App(self.cfg)
        return self.cfg, self.app

    def __exit__(self, *exc):
        if self.app._vis:
            self.app._vis.close()
        self.tmp.cleanup()


def test_home_is_curated_and_everything_stays_reachable():
    with _App() as (cfg, a):
        cats = ["teknoloji", "gaming", "super-zeka", "inovasyon"]
        for i in range(40):
            extra = {"home": "hide"} if i == 3 else {"home": "pin", "home_at": iso(now_utc())} if i == 30 else {}
            a.store.save_post(_post(i, hours=i * 3, appeal=[5, 6, 7, 9][i % 4], cat=cats[i % 4], **extra))
        sb = SiteBuilder(cfg)
        sb.build()
        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
        ids = re.findall(r'data-id="(p\d+)"', home)
        slider = re.findall(r'class="slide[^"]*"[^>]*data-id="(p\d+)"', home)
        assert slider[0] == "p30"                                     # manşete sabitlenen en üstte
        assert "p03" not in ids                                       # "ana sayfada gösterme"
        assert len(set(ids)) < 40                                     # her haber ana sayfaya çıkmaz
        top = re.search(r'data-top>(.*?)</div>\s*</section>', home, re.S).group(1)
        top_ids = re.findall(r'data-id="(p\d+)"', top)
        assert len(top_ids) == 6 and not set(top_ids) & set(slider)   # bölümler arasında tekrar yok
        for sec in ("Öne çıkanlar.", "Son haberler.", "Kaçırmış olabilirsin."):
            assert sec in home
        # tüm haberler sayfalarında her şey var (gizlenen dahil), eski adresler yönlenir
        pages = [cfg.out_dir / "haberler" / "index.html"] + sorted((cfg.out_dir / "haberler" / "sayfa").glob("*/index.html"))
        all_ids = set()
        for pg in pages:
            all_ids |= set(re.findall(r'data-id="(p\d+)"', pg.read_text(encoding="utf-8")))
        assert len(all_ids) == 40
        assert "haberler/" in (cfg.out_dir / "sayfa" / "2" / "index.html").read_text(encoding="utf-8")
        assert (cfg.out_dir / "manifest.webmanifest").exists()
        p5 = a.store.load_post("p05")
        path = cfg.post_path(p5)                                      # kategori/yıl/ay/slug
        assert re.fullmatch(r"[a-z-]+/20\d\d/\d\d/haber-5", path) and path.startswith(p5["category"] + "/")
        art = (cfg.out_dir / path / "index.html").read_text(encoding="utf-8")
        assert "Sıradaki haber" in art and 'data-read="p05"' in art and "t.me/share" in art
        assert f'<link rel="canonical" href="https://smarity.com.tr/{path}/">' in art
        assert f'href="/{p5["category"]}/"' in art                    # kategori sayfası /teknoloji/
        old = (cfg.out_dir / "haber" / "haber-5" / "index.html").read_text(encoding="utf-8")
        assert f"url=https://smarity.com.tr/{path}/" in old and 'rel="canonical"' in old   # eski adres yönlenir
        assert "teknoloji/" in (cfg.out_dir / "kategori" / "teknoloji" / "index.html").read_text(encoding="utf-8")
        assert (cfg.out_dir / "teknoloji" / "index.html").exists()
        ym = "/".join(path.split("/")[:3])
        assert "url=https://smarity.com.tr/" in (cfg.out_dir / ym / "index.html").read_text(encoding="utf-8")
        sm = (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")
        assert "/haberler/" in sm and "smarity.com.tr/sayfa/" not in sm and f"/{path}/" in sm and "/kategori/" not in sm
        assert ">Süper Zeka<" in home and not re.search(r"Süper Zeka<span>\d", home)   # kategori çiplerinde sayı yok


def test_pin_and_hide_buttons():
    with _App() as (cfg, a):
        a.store.save_post(_post(1, 2, publish_mode="manual"))
        kb = a._keyboard(a.store.load_post("p01"), "published")
        assert [b["callback_data"][0] for b in kb[-1]] == ["m", "h"]
        assert not any(b.get("callback_data", "").startswith("s:") for row in kb for b in row)   # Instagram düğmesi yok
        assert a._on_button("m", "p01").startswith("⭐")
        p = a.store.load_post("p01")
        assert p["home"] == "pin" and a._keyboard(p, "published")[-1][0]["text"].endswith("Manşetten çıkar")
        assert a._on_button("h", "p01").startswith("🙈")
        assert a.store.load_post("p01")["home"] == "hide" and hot(a.store.load_post("p01")) < 0
        assert a._on_button("h", "p01").startswith("↩️")
        assert "home" not in a.store.load_post("p01")


def test_write_fixes_text_and_scores_appeal():
    with _App() as (cfg, a):
        a.store.save_post(_post(1, 2, body="Oyunun çıkış tarihi açıklandı."))
        w = a._write([{"credit": "IGN", "kind": "media", "title": "GTA 6 cikis tarihi aciklandi", "url": "https://ign.com/x",
                       "summary": "", "text": ""}])
        assert "çıkış tarihi açıklandı" in w["title"] and 1 <= w["appeal"] <= 10
        a.store.save_post(_post(2, 3, appeal=None))
        a.backfill_appeal()
        assert a.store.load_post("p02")["appeal"]


def test_publish_with_pin_and_manset_command():
    with _App() as (cfg, a):
        from haberbot.telegram import MockTelegram
        a.tg = a.tg or MockTelegram(cfg.root / "tg")
        a.store.save_post(_post(1, 2, publish_mode="manual", telegram={"message_id": 11}))
        d = {**_post(2, 0), "status": "pending", "created_at": iso(now_utc()), "telegram": {"message_id": 12}}
        d.pop("published_at")
        d.pop("slug")
        a.store.save_draft(d)
        kb = a._keyboard(a.store.load_draft("p02"), "pending")
        assert any(b["callback_data"] == "P:p02" for row in kb for b in row)       # onayda "yayınla + manşet"
        assert a._on_button("P", "p02").startswith("⭐")
        p = a.store.load_post("p02")
        assert p["home"] == "pin" and hot(p) >= 100
        assert p["path"].startswith("teknoloji/") and p["path"].endswith("/" + p["slug"])   # kalıcı adres yayında yazılır
        assert cfg.post_url(p) in a._caption(p, "published") and cfg.post_url(p) in str(a._keyboard(p, "published"))
        # /manset: son haberler düğmeleriyle; listeden basınca liste yenilenir
        a._on_command("manset", "")
        assert a.state.get("manset_mid")
        rows = a._manset_keyboard()
        assert [r[0]["callback_data"] for r in rows][:2] == ["m:p02", "m:p01"] and rows[0][0]["text"].startswith("📌")
        a._cb_mid = a.state["manset_mid"]
        assert a._on_button("m", "p01").startswith("⭐")
        assert a._manset_keyboard()[1][0]["text"].startswith("📌")
        # Instagram görselleri Telegram'a gelmez (bağlanınca otomatik paylaşılır)
        outbox = a.tg.dir / "outbox.jsonl"
        before = outbox.read_text(encoding="utf-8") if outbox.exists() else ""
        assert not a.ig_enabled
        a._send_social(a.store.load_post("p02"))
        assert "kendiliğinden" in a._on_button("s", "p02")
        after = outbox.read_text(encoding="utf-8") if outbox.exists() else ""
        assert "sendMediaGroup" not in after[len(before):] and "sendPhoto" not in after[len(before):]
        # eski mesajların düğmeleri bir kez yenilenir
        a.refresh_keyboards()
        assert a.state["keyboard_v"] == appmod.KEYBOARD_VERSION


def test_url_migration_and_otomotiv():
    with _App() as (cfg, a):
        a.store.save_post(_post(1, 2, title="2027 Lexus TZ menzili açıklandı", tags=["Lexus", "Lexus TZ"]))
        a.store.save_post(_post(2, 3, tags=["Apple"]))
        a.store.save_post(_post(3, 4, cat="inovasyon", title="Tesla Optimus yürüdü", tags=["Tesla", "Optimus"]))
        d = {**_post(4, 0, title="TOGG T10F Almanya'da", tags=["TOGG"]), "status": "pending", "created_at": iso(now_utc())}
        a.store.save_draft(d)
        a.migrate_urls()
        p1, p2, p3 = (a.store.load_post(f"p0{i}") for i in (1, 2, 3))
        assert p1["category"] == "otomotiv" and p1["path"].startswith("otomotiv/") and p2["category"] == "teknoloji"
        assert p3["category"] == "inovasyon"                                # robot haberi otomotive gitmez
        assert a.store.load_draft("p04")["category"] == "otomotiv"
        assert cfg.post_url(p1) in a.state["indexnow_queue"]
        a.store.save_post({**p2, "category": "gaming"})                      # kategori sonradan değişse de adres sabit
        a.migrate_urls()
        assert cfg.post_url(a.store.load_post("p02")) == cfg.post_url(p2)
        SiteBuilder(cfg).build()
        assert (cfg.out_dir / p1["path"] / "index.html").exists() and (cfg.out_dir / "otomotiv" / "index.html").exists()
        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
        assert 'class="ph-art' in home and 'data-mkt' in home                  # fotoğrafsız haber: yazısız renk ağı; piyasa şeridi



def test_single_post_tags_are_not_linked():
    # tek haberlik konu sayfası noindex; haberden ona bağlantı verilmez (Search Console'da "noindex" uyarısı birikmesin)
    with _App() as (cfg, a):
        a.store.save_post(_post(1, 2, tags=["Apple", "Grok Bot"]))
        a.store.save_post(_post(2, 3, tags=["Apple"]))
        a.migrate_urls()
        SiteBuilder(cfg).build()
        art = (cfg.out_dir / a.store.load_post("p01")["path"] / "index.html").read_text(encoding="utf-8")
        assert "/etiket/apple/" in art and "/etiket/grok-bot/" not in art
        lone = (cfg.out_dir / "etiket" / "grok-bot" / "index.html").read_text(encoding="utf-8")
        assert 'content="noindex' in lone                                  # eski bağlantılar için sayfa durur, dizine eklenmez
        assert "/etiket/grok-bot/" not in (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
