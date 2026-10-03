"""Seçki (yayın yönetmeni), mevcut haberi güncelleme, kapak başlığı ve ana sayfa çeşitliliği testleri."""
import json
import re
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haberbot.site import SiteBuilder  # noqa: E402
from haberbot.telegram import MockTelegram  # noqa: E402
from haberbot.util import iso, now_utc  # noqa: E402
from tests.test_home import _App, _post  # noqa: E402


def _q(topic, imp, ents, dup="", cat="teknoloji"):
    it = {"key": topic, "url": f"https://k.com/{abs(hash(topic))}", "credit": "Kaynak", "title": topic, "kind": "media",
          "source": "Kaynak", "summary": ""}
    return {"story": {"topic": topic, "importance": imp, "entities": ents, "category": cat, "duplicate_of": dup},
            "items": [it], "at": iso(now_utc())}


def test_guard_rules():
    with _App() as (cfg, a):
        a.store.save_post(_post(1, 3, tags=["Honor"], entities=["Honor", "Honor Magic9"]))
        queue = [_q("Honor Watch 6 Pro launched", 8, ["Honor"]),           # aynı şirketten ikinci haber: sorun değil
                 _q("Starship reaches orbit", 9, ["SpaceX", "Starship"]),   # yayınla
                 _q("Falcon 9 retirement date", 8, ["SpaceX"]),             # yer yok → beklet
                 _q("Minor app update", 6, ["Foo"]),                        # eşik altı → geç
                 _q("Big AI launch", 9, ["Anthropic"]),                     # yayınla
                 _q("Honor Magic9 price in Europe", 8, ["Honor"], dup="s:p01"),   # yayındaki haberin devamı → güncelle
                 ]
        dec = lambda: {i: {"action": "publish", "target": "", "must_read": q["story"]["importance"], "reason": ""}  # noqa: E731
                       for i, q in enumerate(queue)}
        out = a._guard(queue, dec(), slots=3, min_score=7, covered=a._covered(48))
        acts = [out[i]["action"] for i in range(len(queue))]
        assert acts[1] == "publish" and acts[4] == "publish" and acts[0] == "publish"
        assert acts[2] == "hold" and acts[3] == "skip"
        assert acts[5] == "update" and out[5]["target"] == "p01"
        # ayarlardan şirket sınırı açılırsa: aynı şirketten 24 saatte ikinci haber (9 altı) elenir
        cfg.raw.setdefault("editorial", {})["max_per_company_per_day"] = 1
        out = a._guard(queue, dec(), slots=3, min_score=7, covered=a._covered(48))
        assert out[0]["action"] == "skip" and "24 saat" in out[0]["reason"]


def test_edit_uses_llm_and_falls_back():
    with _App() as (cfg, a):
        queue = [_q("Starship reaches orbit", 9, ["SpaceX"]), _q("Vivo unboxing", 6, ["Vivo"])]
        dec = a._edit(queue, slots=2)                                      # test modu yönetmeni: masa puanı ≥8 → yayınla
        assert dec[0]["action"] == "publish" and dec[1]["action"] == "skip"
        for i, q in enumerate(queue):
            a._edit_log(q, dec[i]["action"], dec[i])
        txt = a.edit_text()
        assert "Starship" in txt and "elendi" in txt
        from haberbot.llm import LLMError

        def boom(*a_, **k):
            raise LLMError("HTTP 503")
        a.llm.json = boom
        dec = a._edit(queue, slots=2)                                      # yönetmen yoksa masa puanı + eşik
        assert dec[0]["action"] == "publish" and dec[1]["action"] == "hold"


def test_update_story_in_place():
    with _App() as (cfg, a):
        a.tg = a.tg or MockTelegram(cfg.root / "tg")
        post = _post(1, 5, publish_mode="manual", telegram={"message_id": 5}, entities=["OpenAI"])
        a.store.save_post(post)
        it = {"key": "k2", "url": "https://new.com/x", "credit": "The Verge", "title": "Florida asks OpenAI to halt model",
              "kind": "media", "source": "The Verge", "summary": "", "published": iso(now_utc())}
        d = a.create_update(a.store.load_post("p01"), {"must_read": 8, "entities": ["OpenAI"], "topic": "t"}, [it])
        assert d["update_of"] == "p01" and a.store.load_draft(d["id"])["status"] == "pending"
        kb = a._keyboard(d, "pending")
        assert kb[0][0]["text"].startswith("🔄") and "GÜNCELLEME" in a._caption(d, "pending")
        assert a._on_button("p", d["id"]).startswith("🔄")
        p = a.store.load_post("p01")
        assert p["slug"] == "haber-1" and len(p["sources"]) == 2 and p["updates"][0]["sources"] == ["The Verge"]
        assert p.get("refreshed_at") and not a.store.load_draft(d["id"])
        assert p["title"] != post["title"]                                  # metin yeni gelişmeyle yenilendi
        sb = SiteBuilder(cfg)
        sb.build()
        art = (cfg.out_dir / "haber" / "haber-1" / "index.html").read_text(encoding="utf-8")
        assert 'class="upd"' in art and "Güncellendi" in art


def test_recently_rejected_is_remembered():
    with _App() as (cfg, a):
        d = {**_post(3, 1), "status": "rejected", "created_at": iso(now_utc())}
        a.store.save_draft(d)
        a.store.archive_draft(d, "rejected")
        rec = a.store.recent_archive(72)
        assert rec and rec[0]["id"] == "p03"
        cov = a._covered(48)
        assert any(c["id"] == "p03" and c["status"] == "rejected" for c in cov)


def test_cover_lines_backfill_and_gating():
    with _App() as (cfg, a):
        a.store.save_post(_post(1, 2, image={"source": "cover", "cover_v": 1}))
        assert not a._cover_ready(a.store.load_post("p01"))
        a.backfill_cover_lines()
        p = a.store.load_post("p01")
        assert p["cover_headline"] and a._cover_ready(p)
        assert a._cover_line("OpenAI", "") == {}                           # tek sözcük kapak başlığı olmaz
        assert a._cover_line("Apple'a 5,7 milyar dolar ceza", "yok") == {"cover_headline": "Apple'a 5,7 milyar dolar ceza",
                                                                         "cover_highlight": ""}


def test_home_one_story_per_company_in_showcase():
    with _App() as (cfg, a):
        for i, ent in enumerate(["Honor", "Honor", "Honor", "OpenAI", "OpenAI", "Apple", "Tesla", "Sony", "Xbox", "Google",
                                 "Meta", "Nvidia", "BYD", "Samsung", "Nintendo", "Rivian", "Valve", "AMD", "Intel", "Epic",
                                 "Uber", "Spotify"]):
            a.store.save_post(_post(i, hours=i, appeal=8, tags=[ent], entities=[ent]))
        SiteBuilder(cfg).build()
        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
        slider = re.findall(r'class="slide[^"]*"[^>]*data-id="(p\d+)"', home)
        top = re.findall(r'data-id="(p\d+)"', re.search(r'data-top>(.*?)</div>\s*</section>', home, re.S).group(1))
        shown = slider + top
        ents = [json.loads((cfg.posts_dir / f"{pid}.json").read_text())["entities"][0] for pid in shown]
        assert len(ents) == len(set(ents)), ents                          # vitrinde her şirketten tek haber
        assert ents.count("Honor") == 1


def test_daily_target_and_backlog_reselection():
    with _App() as (cfg, a):
        cfg.raw.setdefault("editorial", {})["daily_target"] = 2
        a.store.bump(a.today(), "drafts", 2)                               # bugün hedef doldu
        queue = [_q("Starship reaches orbit", 9, ["SpaceX"]), _q("New Sony camera", 8, ["Sony"])]
        dec = {i: {"action": "publish", "target": "", "must_read": q["story"]["importance"], "reason": ""}
               for i, q in enumerate(queue)}
        out = a._guard(queue, dec, slots=3, min_score=8, covered=a._covered(48))
        assert out[0]["action"] == "publish" and out[1]["action"] == "skip" and "hedef" in out[1]["reason"]
        # onay bekleyen yığın yeni ölçütlerle bir kez elden geçer
        for i in range(8):
            d = {**_post(10 + i, 1, entities=[f"E{i}"]), "status": "pending", "created_at": iso(now_utc()),
                 "importance": 9 if i < 3 else 6, "telegram": {"message_id": 100 + i}}
            a.store.save_draft(d)
        a.reselect_pending()
        left = a.store.drafts("pending")
        assert len(left) == 2 and all(d["importance"] == 9 for d in left)   # en iyiler (hedef kadar) kalır
        assert a.state["reselect_v"] and a.store.count(a.today(), "culled") == 6
        outbox = (cfg.data_dir / "_mock" / "outbox.jsonl").read_text(encoding="utf-8")
        assert "SEÇKİ DIŞI" in outbox and "Seçki daraltıldı" in outbox
        a.reselect_pending()                                               # ikinci kez çalışmaz
        assert len(a.store.drafts("pending")) == 2


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
