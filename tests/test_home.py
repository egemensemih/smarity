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
        raw.setdefault("autonomy", {})["mode"] = "kural"     # testler canlı moddan bağımsız (tam otonom ayrıca sınanır)
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


def test_showcase_is_balanced_across_categories():
    with _App() as (cfg, a):
        # otomobil fuarı günü: en dikkat çekici 8 haber otomotiv, Apple etkinliği haberi daha geride
        for i in range(8):
            a.store.save_post(_post(i, hours=i * 0.5, appeal=9, cat="otomotiv", tags=[f"Marka{i}"], entities=[f"Marka{i}"]))
        a.store.save_post(_post(20, hours=20, appeal=8, cat="teknoloji", tags=["Apple"], entities=["Apple"]))
        for i, c in enumerate(["super-zeka", "gaming", "inovasyon", "girisimcilik", "teknoloji", "super-zeka"] * 2):
            a.store.save_post(_post(30 + i, hours=6 + i, appeal=6, cat=c, tags=[f"Firma{i}"], entities=[f"Firma{i}"]))
        SiteBuilder(cfg).build()
        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
        slider = re.findall(r'class="slide[^"]*"[^>]*data-id="(p\d+)"', home)
        cats = [a.store.load_post(i)["category"] for i in slider]
        assert len(slider) == 10 and cats.count("otomotiv") == 3 and "p20" in slider
        top = re.search(r'data-top>(.*?)</div>\s*</section>', home, re.S).group(1)
        top_cats = [a.store.load_post(i)["category"] for i in re.findall(r'data-id="(p\d+)"', top)]
        assert all(top_cats.count(c) <= 2 for c in set(top_cats))
        # az haberli günde boş kalmaz: sınır yalnızca yer varsa uygulanır
        assert len(SiteBuilder._home([{**p, "hot": 1.0, "ekey": ""} for p in
                                      [{"id": f"x{i}", "category": "otomotiv", "published_at": iso(now_utc())}
                                       for i in range(5)]], 10)["featured"]) == 5

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



def test_maintenance_merges_duplicates_and_fixes_titles():
    with _App() as (cfg, a):
        a.store.save_post(_post(1, 80, title="Kia Seltos Türkiye'de satışa çıktı: İşte resmi fiyatları", tags=["Kia"],
                                sources=[{"name": "DonanımHaber", "url": "https://dh.com/kia", "kind": "media"}]))
        a.store.save_post(_post(2, 2, title="Yeni Kia Seltos Türkiye'de satışa çıktı", tags=["Kia"],
                                sources=[{"name": "ShiftDelete.Net", "url": "https://sd.net/kia", "kind": "media"}]))
        a.store.save_post(_post(3, 5, title="Dacia Hipster 15 bin euronun altında fiyatla geliyor", tags=["Dacia"]))
        a.migrate_urls()
        dup_path = a.store.load_post("p02")["path"]
        cfg.raw["maintenance"] = {"merge_posts": [["p02", "p01"], ["yok", "p01"]],
                                  "retitle": {"p03": "Uygun fiyatlı elektrikli Dacia Hipster geliyor"}}
        a.apply_maintenance()
        a.apply_maintenance()                                              # ikinci kez çalışması zararsız
        keep = a.store.load_post("p01")
        assert a.store.load_post("p02") is None and dup_path in keep["old_paths"] and "haber/haber-2" in keep["old_paths"]
        assert [s_["name"] for s_ in keep["sources"]] == ["DonanımHaber", "ShiftDelete.Net"]
        assert a.store.load_post("p03")["title"] == "Uygun fiyatlı elektrikli Dacia Hipster geliyor"
        SiteBuilder(cfg).build()
        stub = (cfg.out_dir / dup_path / "index.html").read_text(encoding="utf-8")
        assert cfg.post_url(keep) in stub and "refresh" in stub              # eski adres kalan habere yönlenir
        assert dup_path not in (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")


def test_older_duplicates_are_shown_to_desk_and_editor():
    from haberbot.textfix import title_words
    assert title_words("Kia Seltos Türkiye'de satışa çıktı: İşte resmi fiyatları") == {"kia", "seltos"}
    assert {"chatgpt", "pro", "500"} <= title_words("OpenAI's ChatGPT Pro 500 now costs 26,499 lira")
    with _App() as (cfg, a):
        a.store.save_post(_post(1, 80, title="Kia Seltos Türkiye'de satışa çıktı", tags=["Kia Seltos"],
                                entities=["Kia Seltos"]))
        a.store.save_post(_post(2, 100, title="Sony yeni kulaklık tanıttı", tags=["Sony"], entities=["Sony"]))
        seen = {}

        class Ed:
            def json(self, model, system, user, schema, max_tokens=0, effort=None, images=None):
                seen["user"] = user
                return {"decisions": [{"cid": "c1", "action": "skip", "target": "p01", "must_read": 8, "reason": "aynı haber"}]}
        a.llm = Ed()
        q = {"story": {"topic": "Kia Seltos on sale in Turkey", "importance": 8, "entities": ["Kia Seltos"],
                       "category": "otomotiv", "duplicate_of": ""}, "items": [], "at": iso(now_utc())}
        dec = a._edit([q], slots=2)
        assert "p01" in seen["user"] and "p02" not in seen["user"] and dec[0]["action"] == "skip"



def test_search_page_and_index():
    import json as _json
    with _App() as (cfg, a):
        a.store.save_post(_post(1, 2, title="Kia Seltos Türkiye'de satışa çıktı", tags=["Kia", "SUV"], entities=["Kia Seltos"]))
        a.store.save_post(_post(2, 3, title="Yapay zeka destekli ışık sensörü", tags=["Yapay zeka"]))
        a.migrate_urls()
        SiteBuilder(cfg).build()
        idx = _json.loads((cfg.out_dir / "api" / "search.json").read_text(encoding="utf-8"))
        assert {x["t"] for x in idx} == {"Kia Seltos Türkiye'de satışa çıktı", "Yapay zeka destekli ışık sensörü"}
        kia = next(x for x in idx if x["t"].startswith("Kia"))
        assert kia["u"].endswith("/haber-1/") and "Kia Seltos" in kia["g"] and kia["c"] and kia["o"]
        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
        assert "data-search-open" in home and 'class="srch"' in home and "/api/search.json?v=" in home
        assert "SearchAction" in home and "/ara/?q={search_term_string}" in home
        page = (cfg.out_dir / "ara" / "index.html").read_text(encoding="utf-8")
        assert 'content="noindex' in page and "data-search-page" in page and 'class="srch"' not in page
        assert "/ara/" not in (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")


def test_pending_draft_publishes_itself_when_third_source_arrives():
    with _App() as (cfg, a):
        from haberbot.telegram import MockTelegram
        a.tg = a.tg or MockTelegram(cfg.root / "tg")
        src = lambda n: {"name": n, "url": f"https://{n.lower()}.com/x", "title": "t", "kind": "media"}  # noqa: E731
        d = {**_post(3, 0), "status": "pending", "created_at": iso(now_utc()), "telegram": {"message_id": 31},
             "importance": 8, "big_brand": True, "confidence": "yuksek", "flags": [],
             "sources": [src("Webtekno"), src("LOG")], "source_keys": ["Webtekno", "LOG"]}
        d.pop("published_at")
        d.pop("slug")
        small = {**d, "id": "p04", "importance": 7, "big_brand": False, "telegram": {"message_id": 41},
                 "sources": [src("Webtekno"), src("LOG"), src("Verge")]}
        a.store.save_draft(d)
        a.store.save_draft(small)
        assert a.recheck_pending() == 0                                   # 2 kaynak: bekler (mesajda 2/3 yazar)
        w = a.store.load_draft("p03")
        assert w["policy_tier"] == "wait" and "2/3" in a._caption(w, "pending")
        assert a.store.load_draft("p04")["policy_tier"] == "ask"         # küçük kitle + büyük marka değil: hep sorar
        it = {"credit": "The Verge", "url": "https://verge.com/x", "title": "t", "kind": "media", "source": "The Verge"}
        assert a._merge_sources("p03", [it])                              # 3. kaynak geldi
        assert a.recheck_pending() == 1
        p = a.store.load_post("p03")
        assert p and p["publish_mode"] == "auto" and p["auto_late"] and not a.store.load_draft("p03")
        out = (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8")
        assert "OTOMATİK YAYINLANDI" in out and "sonradan gelen kaynaklarla" in out and '"message_id": 31' in out
        assert a.store.load_draft("p04")["status"] == "pending"
        # /mod manuel: hiçbir şey otomatik yayınlanmaz; iki otomatik haber kaldırılınca fren + bildirim
        a._on_command("mod", "manuel")
        assert a.state["mode_override"] == "manuel"
        a._on_command("mod", "ogrenen")
        assert a.state["mode_override"] == "kural"
        a.store.save_post({**_post(5, 1), "publish_mode": "auto"})
        a._on_button("d", "p03")
        a._on_button("d", "p05")
        out = (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8")
        assert "Otomatik yayın durdu" in out and a.stats.get("auto_removals")
        a._on_command("mod", "kural")
        assert not a.stats.get("auto_removals")


def test_full_autonomy_publishes_and_learns_from_rejections():
    with _App() as (cfg, a):
        from haberbot import policy
        from haberbot.prompts import edit_system, edit_user
        from haberbot.telegram import MockTelegram
        a.tg = a.tg or MockTelegram(cfg.root / "tg")
        a._on_command("mod", "tam")
        d = {**_post(6, 0), "status": "pending", "created_at": iso(now_utc()), "telegram": {"message_id": 61},
             "importance": 7, "big_brand": False, "confidence": "orta", "flags": [], "source_keys": ["Kaynak"]}
        d.pop("published_at")
        d.pop("slug")
        flagged = {**d, "id": "p07", "flags": ["iddia"], "telegram": {"message_id": 71}, "title": "GTA 6 sızıntısı büyüyor"}
        a.store.save_draft(d)
        a.store.save_draft(flagged)
        assert a.recheck_pending() == 1                      # tek kaynak, küçük kitle: tam otonomda yine yayınlanır
        p = a.store.load_post("p06")
        assert p["publish_mode"] == "auto" and "yönetmeni seçti" in a._caption(p, "auto")
        # şüpheli (uyarılı) haber: yayınlanmaz, sorulmaz; daha önce sorulmuşsa mesajı "yayınlanmadı" olur
        assert not a.store.load_draft("p07") and not a.store.load_post("p07")
        out = (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8")
        assert "YAYINLANMADI" in out and "Doğrulanmamış iddia" in out and "ONAY BEKLİYOR" not in out
        assert any(x["status"] == "dropped" for x in a.store.recent_archive(1))
        assert policy.decide(cfg, a.state, a.stats, {**d, "title": "Vivo X300 tanıtıldı"})[0] == "drop"
        # kaldırılanlar freni tetiklemez, yönetmene "sahibin istemediği" örnek olur
        a.store.save_post({**_post(8, 1), "publish_mode": "auto", "title": "One UI 9 güncellemesi dağıtılıyor"})
        a._on_button("d", "p06")
        a._on_button("d", "p08")
        assert not a.stats.get("auto_removals")
        assert "Otomatik yayın durdu" not in (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8")
        assert policy_mode(a) == "tam"
        rej = a._owner_rejected()                              # düşenler sahibin zevki sayılmaz, kaldırılanlar sayılır
        assert {r["title"] for r in rej} == {"One UI 9 güncellemesi dağıtılıyor", d["title"]}
        text = edit_user("2026-10-13 15:00", 2, [], [], rej)
        assert "OWNER REJECTED" in text and "One UI 9 güncellemesi dağıtılıyor" in text
        assert "CONFIRMED NEWS ONLY" in edit_system("Smarity", 7, True) and "CONFIRMED" not in edit_system("Smarity", 7)
        assert a._confirmed_only is bool(cfg.get("editorial", "confirmed_only", False))


def policy_mode(a):
    from haberbot import policy
    return policy.current_mode(a.cfg, a.state)


def test_big_stories_rank_higher_and_get_photos_from_later_sources():
    src = lambda n: {"name": n, "url": f"https://{n.lower()}.com/x", "kind": "media", "image": f"https://{n}.com/a.jpg"}  # noqa: E731
    one = _post(1, 3, appeal=9)
    many = {**_post(2, 3, appeal=9), "sources": [src("Electrek")], "coverage": [src(n) for n in ("Verge", "NYT", "Engadget", "InsideEVs")]}
    assert hot(many) > hot(one) * 1.15                                 # 5 ayrı site haberi verdi: büyük haber
    with _App() as (cfg, a):
        post = {**_post(3, 30), "sources": [src("Electrek")], "importance": 9, "telegram": {"message_id": 9}}
        a.store.save_post(post)
        a.store.site_dirty = False
        it = lambda n: {"credit": n, "url": f"https://{n.lower()}.com/y", "title": "Roadster", "kind": "media",  # noqa: E731
                        "image": f"https://{n}.com/b.jpg", "source": n}
        assert a._note_coverage("p03", [it("Verge"), it("Verge"), it("NYT")])
        assert not a._note_coverage("p03", [it("NYT")])                 # aynı adres iki kez eklenmez
        p = a.store.load_post("p03")
        assert [c["name"] for c in p["coverage"]] == ["Verge", "NYT"] and not a.store.site_dirty
        assert [x["name"] for x in a._photo_sources(p, draft=False)] == ["Electrek", "NYT", "Verge"]
        # güncelleme gelince fotoğrafsız habere yeni kaynaklarla fotoğraf aranır
        tried = []
        a._attach_photos = lambda d, draft, got=None: tried.append(d["id"]) or False
        upd = {"id": "u1", "update_of": "p03", "title": "Tesla Roadster tanıtıldı", "summary": "s", "body": "b",
               "sources": [src("Engadget")], "source_keys": ["Engadget"], "importance": 9}
        assert a.apply_update(upd) and tried == ["p03"]
        assert a.store.load_post("p03")["photos_filled"]

def test_legal_pages_and_analytics():
    with _App() as (cfg, a):
        cfg.raw["analytics"], cfg.raw["legal"] = {"cloudflare_token": ""}, {}
        a.store.save_post(_post(1, 2))
        SiteBuilder(cfg).build()
        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
        assert "cloudflareinsights" not in home                       # belirteç yokken istatistik kodu eklenmez
        assert "/iletisim/" in home and "/gizlilik/" in home          # alt bilgide bağlantılar
        priv = (cfg.out_dir / "gizlilik" / "index.html").read_text(encoding="utf-8")
        cont = (cfg.out_dir / "iletisim" / "index.html").read_text(encoding="utf-8")
        assert "KVKK" in priv and "çerez" in priv and "Yayın sahibi" not in cont   # boş künye satırı gösterilmez
        sm = (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")
        assert "/gizlilik/" in sm and "/iletisim/" in sm
        red = (cfg.out_dir / "api" / "redirects.csv").read_text(encoding="utf-8").splitlines()
        p01 = a.store.load_post("p01")
        assert f"smarity.com.tr/haber/{p01['slug']}/,https://smarity.com.tr/{cfg.post_path(p01)}/,301,TRUE,FALSE,FALSE,FALSE" in red
        cfg.raw["analytics"] = {"cloudflare_token": "abc123"}
        cfg.raw["legal"] = {"owner": "Örnek Medya", "address": "İstanbul"}
        SiteBuilder(cfg).build()
        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
        assert '"token": "abc123"' in home and "static.cloudflareinsights.com/beacon.min.js" in home
        cont = (cfg.out_dir / "iletisim" / "index.html").read_text(encoding="utf-8")
        assert "Yayın sahibi" in cont and "Örnek Medya" in cont and "İstanbul" in cont

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
