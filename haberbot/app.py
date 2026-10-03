"""Ana akış: topla → ayıkla → yaz → (onay | otomatik) → yayınla.  Telegram etkileşimleri de burada."""
from __future__ import annotations

import html
import os
import re
import shutil
import time
from urllib.parse import urlsplit

import requests

from . import photos, policy
from .config import CATEGORIES, DEFAULT_CATEGORY, Config, category_label, indexnow_key
from .covers import COVER_VERSION, PHOTO_COVER_VERSION, photo_design
from .extract import full_text
from .instagram import Instagram, InstagramError, TokenStore, fingerprint, head_ok
from .llm import LLMError, MockLLM, estimate_cost, make_llm
from .prompts import (APPEAL_SCHEMA, COVERLINE_SCHEMA, EDIT_SCHEMA, FLAG_LABELS, FLAGS, SEO_SCHEMA, TRIAGE_SCHEMA,
                      WRITE_SCHEMA, appeal_system, appeal_user, coverline_system, coverline_user, edit_system, edit_user,
                      seo_system, seo_user, triage_system, triage_user, write_system, write_user)
from .sources import fetch_all
from .store import Store
from .textfix import Fixer, entity_keys, is_car_story
from .telegram import MockTelegram, Telegram, TelegramError
from .util import (clip, hours_since, iso, local, log, now_utc, short_hash, slugify,
                   tr_date)

KIND_ORDER = {"official": 0, "media": 1, "community": 2}
# Uzun süren düğmeler: (hemen gösterilen yanıt, işlem bitince beklenen sonuç)
SLOW_ACTIONS = {
    "p": ("⏳ Yayınlanıyor…", "✅ Yayınlandı"),
    "P": ("⏳ Yayınlanıyor…", "⭐ Yayınlandı ve manşete alındı"),
    "v": ("⏳ Yeni görsel hazırlanıyor…", "🎨 Yeni görsel hazır"),
    "g": ("⏳ Fotoğraf değiştiriliyor…", "🖼 Fotoğraf değişti"),
    "n": ("⏳ Fotoğraflar kaldırılıyor…", "🚫 Fotoğraflar kaldırıldı"),
    "w": ("⏳ Yeniden yazılıyor…", "🔁 Yeniden yazıldı"),
}
IG_WINDOW_DEFAULT = [8, 24]
CONF_LABEL = {"yuksek": "yüksek", "orta": "orta", "dusuk": "düşük"}
COMMANDS = [
    ("durum", "Sistem durumu ve istatistikler"),
    ("bekleyen", "Onay bekleyen haberler"),
    ("mod", "Otonomi modu: manuel / ogrenen / tam"),
    ("topla", "Kaynakları hemen tara"),
    ("duraklat", "Toplama ve otomatik yayını durdur"),
    ("devam", "Yeniden başlat"),
    ("kaynaklar", "Kaynak güven puanları"),
    ("manset", "Manşeti yönet: haberi manşete al / çıkar"),
    ("secki", "Yayın yönetmeninin son kararları (neden seçildi / elendi)"),
    ("instagram", "Instagram paylaşımları: durum / kapat / ac"),
    ("yardim", "Nasıl kullanılır"),
]
COMMANDS_VERSION = 4
COVERLINE_V = 3               # kapak başlığı yazım kuralları değişince eski haberlerin kapak başlıkları yeniden yazılır
RESELECT_V = 1                # seçki ölçütleri değişince artır: onay bekleyen yığın bir kez yeniden elden geçer
KEYBOARD_VERSION = 4          # yayındaki haber mesajlarının düğmeleri bu sürüme göre bir kez yenilenir
HELP = """<b>Nasıl çalışır?</b>
Kaynaklar düzenli taranır; teknoloji, girişim, yapay zeka, ürün, otomobil ve oyun dünyasından önemli haberler Türkçe yazılıp buraya düşer.

✅ <b>Yayınla</b> — siteye koyar
❌ <b>Reddet</b> — yayınlamaz (Geri al ile dönebilirsin)
📄 <b>Tam metin</b> — haberin tamamını gösterir
🔁 <b>Yeniden yaz</b> — yapay zeka metni yeniden yazar
🖼 <b>Başka foto</b> — kapaktaki fotoğrafı sıradaki fotoğrafla değiştirir
🎨 <b>Yazılı kapak / Yeni kapak</b> — kapağı bizim yazılı tasarımımıza çevirir ya da yenisini üretir (fotoğraflar haberde kalır)
🚫 <b>Fotoğrafsız</b> — haberdeki tüm fotoğrafları kaldırır
🔤 <b>Kapak başlığı</b> — mesajı yanıtlayıp <code>görsel: Starship ilk kez yörüngede</code> gibi kısa bir başlık yazarsan kapakta o yazar
✏️ <b>Düzeltme</b> — bir haber mesajını <i>yanıtlayıp</i> talimat yaz: "başlığı kısalt", "ikinci paragrafı çıkar" gibi. Yayınlanmış habere de uygulanır.
🗑 <b>Kaldır</b> — yayınlanmış haberi siteden kaldırır
⭐ <b>Yayınla + manşet</b> — onay beklerken tek tuşla yayınlar ve manşete alır
⭐ <b>Manşete al</b> — haberi 36 saat ana sayfa manşetinin en başına koyar (<code>/manset</code> ile son haberlerden de seçebilirsin)
🙈 <b>Ana sayfada gösterme</b> — haber ana sayfaya çıkmaz, kategoride ve "Tüm haberler"de kalır

<b>Seçki:</b> Sitede aynı gün her şey yer almaz. Haber masası aynı olayı tek habere toplar; yayın yönetmeni o güne kadar yayınlananları görerek karar verir: bu alanı takip eden biri için günün kaçırılmaması gereken gelişmesi mi? Aynı olay tek haber olur; yayındaki bir haberin devamı gelirse yeni haber yerine 🔄 <b>güncelleme önerisi</b> gelir; onaylarsan mevcut haber yeni gelişmeyle güncellenir, adresi değişmez. Neyin neden elendiğini /secki gösterir.

<b>Ana sayfa seçkisi:</b> Her haber ana sayfaya çıkmaz. Yapay zeka her habere bir ilgi puanı verir; puan ve tazeliğe göre en dikkat çekiciler manşete ve "Öne çıkanlar"a girer.

<b>Öğrenen mod:</b> Kararların kaynak bazında kaydedilir. Bir kaynak yeterince onay alınca, o kaynaktan gelen net haberler otomatik yayınlanır ve sana sessizce bildirilir. Şüpheli işaretli haberler her zaman sana sorulur.

📸 <b>Instagram</b> — yayınlanan her haber birkaç dakika içinde carousel ve hikâye olarak Instagram'da paylaşılır. Sıradaki bir haberi mesajındaki <b>Instagram'a gönderme</b> düğmesiyle durdurabilirsin. Tümünü durdurmak için <code>/instagram kapat</code>.

Komutlar: /manset /secki /durum /bekleyen /mod /topla /duraklat /devam /kaynaklar /instagram"""


def esc(s) -> str:
    return html.escape(str(s or ""), quote=False)


def md_to_tg(md: str) -> str:
    """Basit Markdown → Telegram HTML."""
    s = esc(md)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


class App:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.store = Store(cfg)
        self.state = self.store.state
        self.stats = self.store.stats
        self.force_collect = cfg.force_collect
        self.brand = cfg.site.get("name", "Smarity")

        if cfg.mock:
            self.llm = MockLLM(usage_cb=self._usage)
        else:
            self.llm = make_llm(cfg, usage_cb=self._usage)

        if cfg.mock:
            self.tg = MockTelegram(cfg.data_dir / "_mock")
        elif cfg.telegram_token:
            self.tg = Telegram(cfg.telegram_token)
        else:
            self.tg = None
        self.chat_id = cfg.telegram_chat_id or ("1" if cfg.mock else "")
        self._vis = None
        self._ig = None
        self._cb_mid = None

    @property
    def vis(self):
        if self._vis is None:
            from .visuals import Visuals
            self._vis = Visuals(self.cfg)
        return self._vis

    # ── yardımcılar ─────────────────────────────────────────
    def today(self) -> str:
        return local(now_utc(), self.cfg.tz).strftime("%Y-%m-%d")

    def _usage(self, model: str, tin: int, tout: int) -> None:
        d = self.state.setdefault("day_counts", {}).setdefault(self.today(), {})
        d["tok_in"] = d.get("tok_in", 0) + tin
        d["tok_out"] = d.get("tok_out", 0) + tout
        d["cost_usd"] = round(d.get("cost_usd", 0.0) + estimate_cost(model, tin, tout), 4)

    def quiet(self) -> bool:
        a, b = (self.cfg.get("schedule", "quiet_hours", [0, 8]) or [0, 0])[:2]
        h = local(now_utc(), self.cfg.tz).hour
        return (a <= h < b) if a <= b else (h >= a or h < b)

    def draft_budget(self) -> int:
        """Şu an yazılabilecek taslak sayısı. Günlük sınır güne yayılır: sabah hepsi birden tükenmez,
        akşam da haber gelmeye devam eder."""
        ed = lambda k, d: self.cfg.get("editorial", k, d)  # noqa: E731
        cap = int(ed("max_drafts_per_day", 0) or 0)
        used = self.store.count(self.today(), "drafts")
        if cap <= 0:  # günlük sınır yok: seçim yalnızca önem eşiğine göre yapılır
            return 10 ** 6
        a, b = (ed("active_hours", [7, 24]) or [0, 24])[:2]
        now_l = local(now_utc(), self.cfg.tz)
        h = now_l.hour + now_l.minute / 60
        frac = min(1.0, max(0.0, (h - a) / max(1, b - a)))
        allowed = int(cap * frac + 0.999) + int(ed("burst", 3))
        return max(0, min(cap - used, allowed - used))

    def notify(self, text: str, silent: bool | None = None, keyboard=None) -> None:
        if not (self.tg and self.chat_id):
            log.info("[bildirim] %s", re.sub(r"<[^>]+>", "", text)[:200])
            return
        try:
            self.tg.send_message(self.chat_id, text, keyboard=keyboard,
                                 silent=self.quiet() if silent is None else silent)
        except TelegramError as e:
            log.warning("Telegram bildirimi gönderilemedi: %s", e)

    @staticmethod
    def _transient(e: Exception) -> bool:
        """Google tarafındaki geçici yoğunluk/sınır: kullanıcıyı rahatsız etmeye gerek yok, sonraki turda tekrar denenir."""
        return bool(re.search(r"HTTP (429|5\d\d)|meşgul|Tekrar denemeler|Bağlantı hatası|high demand|UNAVAILABLE", str(e)))

    def notify_error(self, text: str) -> None:
        """Aynı tür hata için en fazla 6 saatte bir uyar."""
        if hours_since(self.state.get("last_error_notice")) < 6:
            log.error(text)
            return
        self.state["last_error_notice"] = iso(now_utc())
        self.notify("⚠️ <b>Sorun</b>\n" + esc(text), silent=False)

    # ── 1) TOPLAMA ──────────────────────────────────────────
    def collect(self) -> None:
        if not self.llm:
            log.warning("GEMINI_API_KEY tanımlı değil; haber toplama atlandı.")
            return
        cfg, st = self.cfg, self.store
        ed = lambda k, d: cfg.get("editorial", k, d)  # noqa: E731
        today = self.today()
        remaining = self.draft_budget()
        if remaining <= 0:
            # Haberler "görüldü" sayılmaz; sıra gelince (en geç ertesi sabah) değerlendirilir.
            self.state["last_collect"] = iso(now_utc())
            log.info("Taslak sırası dolu (bugün %d taslak); yeni haberler sonraki turda değerlendirilecek.",
                     st.count(today, "drafts"))
            return
        items = fetch_all(cfg, st)
        seeded = set(self.state.get("seeded_sources", []))
        max_age = ed("max_item_age_hours", 36)
        fresh, keys = [], set()
        for it in items:
            if it["key"] in st.seen or it["key"] in keys:
                continue
            keys.add(it["key"])
            if it["source"] not in seeded and (it["html_source"] or not it["published"]
                                               or hours_since(it["published"]) > 6):
                st.seen[it["key"]] = iso(now_utc())   # yeni eklenen kaynağın ilk taraması: eski haberleri yığma
                continue
            if it["published"] and hours_since(it["published"]) > max_age:
                st.seen[it["key"]] = iso(now_utc())
                continue
            fresh.append(it)
        self.state["seeded_sources"] = sorted(seeded | {it["source"] for it in items})
        self.state["last_collect"] = iso(now_utc())
        # Bir turda en fazla N öğe ayıklanır; kalanlar "görülmedi" sayılır ve sonraki turda sıraya girer (kaybolmaz)
        batch = int(ed("triage_batch", 100) or 100)
        fresh.sort(key=lambda x: (KIND_ORDER.get(x["kind"], 3), hours_since(x["published"]) if x["published"] else 0))
        later = len(fresh) - batch
        fresh = fresh[:batch]
        for it in fresh:
            st.seen[it["key"]] = iso(now_utc())
        log.info("Yeni öğe: %d (toplam okunan %d%s)", len(fresh), len(items),
                 f", {later} tanesi sonraki tura kaldı" if later > 0 else "")
        queue = self._queue(max_age)
        if not fresh and not queue:
            return

        min_imp = ed("min_importance", 6)
        new_stories, merged, skipped = [], 0, 0
        if fresh:
            by_tid = {}
            for i, it in enumerate(fresh, 1):
                it["tid"] = f"i{i}"
                by_tid[it["tid"]] = it

            recent = []
            for p in st.posts():
                if hours_since(p.get("published_at")) > 72:
                    break
                recent.append({"sid": "s:" + p["id"], "status": "published", "title": p["title"]})
            for d in st.drafts():
                recent.append({"sid": "s:" + d["id"], "status": d.get("status", "pending"), "title": d["title"]})
            for a in st.recent_archive(72):   # reddedilen / süresi dolan haberler tekrar önerilmesin
                if a.get("status") in ("rejected", "expired", "removed"):
                    recent.append({"sid": "s:" + a["id"], "status": a["status"], "title": a.get("title", "")})
            recent += [{"sid": f"q:{i}", "status": "queued", "title": q["story"].get("topic", "")}
                       for i, q in enumerate(queue)]

            try:
                tri = self.llm.json(cfg.get("ai", "triage_model", "claude-haiku-4-5-20251001"),
                                    triage_system(self.brand), triage_user(fresh, recent[:150], today),
                                    TRIAGE_SCHEMA, max_tokens=12000)
            except LLMError as e:
                if self._transient(e):
                    log.warning("Yapay zeka şu an yoğun (ayıklama), sonraki turda tekrar denenecek: %s", str(e)[:160])
                else:
                    self.notify_error(f"Yapay zeka (ayıklama) hatası: {e}")
                for it in fresh:  # bir sonraki turda tekrar denensin
                    st.seen.pop(it["key"], None)
                tri = {"stories": []}

            posted = {p["id"] for p in st.posts() if hours_since(p.get("published_at")) <= 72}
            for s in tri.get("stories", []):
                its = [by_tid[t] for t in s.get("item_ids", []) if t in by_tid]
                if not its:
                    continue
                s["entities"] = [clip(str(e).strip(), 40) for e in (s.get("entities") or []) if str(e).strip()][:3]
                dup = (s.get("duplicate_of") or "").strip()
                if dup.startswith("q:") and dup[2:].isdigit() and int(dup[2:]) < len(queue):
                    q = queue[int(dup[2:])]  # sıradaki habere yeni kaynak ekle
                    urls = {it["url"] for it in q["items"]}
                    q["items"] += [it for it in its if it["url"] not in urls]
                    merged += 1
                    continue
                if dup:
                    did = dup.removeprefix("s:")
                    if self._merge_sources(did, its):
                        merged += 1
                        continue
                    # yayındaki bir haberin devamı: önemliyse yönetmen "güncelle" ya da "geç" der
                    if did in posted and int(s.get("importance", 0)) >= min_imp and s.get("on_topic", True):
                        new_stories.append({"story": s, "items": its, "at": iso(now_utc())})
                    else:
                        merged += 1
                    continue
                if not (s.get("on_topic") or s.get("ai_related")) or int(s.get("importance", 0)) < min_imp:
                    skipped += 1
                    continue
                new_stories.append({"story": s, "items": its, "at": iso(now_utc())})

        # Yayın yönetmeni: adaylar arasından günün seçkisi (yeni haber / mevcut haberi güncelle / geç / beklet)
        queue = sorted(queue + new_stories, key=lambda q: (-int(q["story"].get("importance", 0)), q["at"]))[:24]
        slots = min(int(ed("max_drafts_per_run", 2)), remaining)
        if fresh:
            log.info("Ayıklama: %d aday, %d elendi, %d mevcut habere eklendi", len(new_stories), skipped, merged)
        if not new_stories and all(hours_since(q.get("held_at")) < 0.75 for q in queue):
            self.state["queue"] = queue[:30]   # yeni aday yok, bekleyenlere az önce bakıldı
            return
        decisions = self._edit(queue, slots) if queue else {}
        todo, updates, keep = [], [], []
        for i, q in enumerate(queue):
            x = decisions.get(i) or {"action": "hold", "target": "", "must_read": 0, "reason": ""}
            q["story"]["must_read"] = int(x.get("must_read") or 0)
            q["story"]["editor_reason"] = x.get("reason", "")
            act = x["action"]
            if act == "publish":
                todo.append(q)
            elif act == "update":
                updates.append((q, x["target"]))
            elif act == "merge":
                self._merge_sources(x["target"], q["items"])
            elif act == "hold":
                q["holds"] = int(q.get("holds", 0)) + 1
                q["held_at"] = iso(now_utc())
                if q["holds"] <= 8:
                    keep.append(q)
            self._edit_log(q, act, x)
        todo.sort(key=lambda q: -q["story"]["must_read"])
        self.state["queue"] = keep[:30]
        log.info("Yönetmen: %d yeni haber, %d güncelleme, %d bekliyor, %d geçildi", len(todo), len(updates), len(keep),
                 len(queue) - len(todo) - len(updates) - len(keep))
        for n, q in enumerate(todo):
            if n:
                self.process_updates()  # yazım sürerken basılan düğmeler beklemesin
            try:
                self.create_draft(q["story"], q["items"])
            except LLMError as e:
                if self._transient(e):
                    log.warning("Yapay zeka şu an yoğun (yazım), kalan %d haber sonraki turda yazılacak: %s",
                                len(todo) - n, str(e)[:160])
                else:
                    self.notify_error(f"Yapay zeka (yazım) hatası: {e}")
                self.state["queue"] = (todo[n:] + self.state["queue"])[:30]  # yazılamayanlar sırada kalsın
                break
            except Exception as e:  # noqa: BLE001
                log.exception("Taslak oluşturulamadı: %s", e)
        for q, target in updates[:2]:
            post = st.load_post(target)
            if not post:
                continue
            self.process_updates()
            try:
                self.create_update(post, q["story"], q["items"])
            except LLMError as e:
                log.warning("Güncelleme yazılamadı (%s): %s", target, str(e)[:160])
            except Exception as e:  # noqa: BLE001
                log.exception("Güncelleme oluşturulamadı: %s", e)

    # ── yayın yönetmeni ─────────────────────────────────────
    def _covered(self, hours: float = 48) -> list[dict]:
        """Yönetmenin gördüğü 'elimizdekiler': yayındakiler, onay bekleyenler, reddedilen / süresi dolanlar."""
        out = []

        def add(d: dict, status: str, at: str | None) -> None:
            h = hours_since(at)
            if h <= hours:
                out.append({"id": d["id"], "status": status, "age": f"{h:.0f} sa", "hours": h,
                            "category": d.get("category", ""), "entities": list(d.get("entities") or (d.get("tags") or [])[:2]),
                            "title": d.get("title", ""), "keys": entity_keys(d), "updated": bool(d.get("refreshed_at"))})
        for p in self.store.posts():
            if hours_since(p.get("published_at")) > hours:
                break
            add(p, "published", p.get("refreshed_at") or p.get("published_at"))
        for d in self.store.drafts():
            if d.get("status") in ("pending", "rejected"):
                add(d, d["status"], d.get("created_at"))
        for a in self.store.recent_archive(hours):
            if a.get("status") in ("rejected", "expired", "removed"):
                add(a, a["status"], a.get("created_at") or a.get("closed_at"))
        out.sort(key=lambda c: c["hours"])
        return out

    def _edit(self, queue: list[dict], slots: int) -> dict[int, dict]:
        """Her aday için yönetmen kararı: {sıra: {"action", "target", "must_read", "reason"}}."""
        cfg = self.cfg
        ed = lambda k, d: cfg.get("editorial", k, d)  # noqa: E731
        min_score = int(ed("min_must_read", 8))
        covered = self._covered(48)
        cands = []
        for i, q in enumerate(queue):
            s = q["story"]
            cands.append({"cid": f"c{i + 1}", "category": s.get("category", ""), "importance": s.get("importance", 0),
                          "entities": s.get("entities") or [], "topic": s.get("topic", ""),
                          "dup": (s.get("duplicate_of") or "").removeprefix("s:"),
                          "headlines": [f"{it['credit']}: {it['title']}" for it in q["items"]]})
        now_l = local(now_utc(), cfg.tz)
        today_n = self.store.count(self.today(), "drafts")
        target = self._daily_target()
        raw = None
        try:
            out = self.llm.json(cfg.get("ai", "editor_model", None) or cfg.get("ai", "writer_model", "gemini-flash-latest"),
                                edit_system(self.brand, min_score),
                                edit_user(now_l.strftime("%Y-%m-%d %H:%M"), slots, today_n, target, covered[:90], cands),
                                EDIT_SCHEMA, max_tokens=6000)
            raw = {str(x.get("cid")): x for x in (out.get("decisions") or []) if isinstance(x, dict)}
        except LLMError as e:
            log.warning("Yayın yönetmeni yanıt vermedi, masanın puanı kullanılacak: %s", str(e)[:160])
        decisions = {}
        for i, q in enumerate(queue):
            imp = int(q["story"].get("importance", 0))
            if raw is None:   # yedek: masanın puanı, yönetmen eşiğiyle
                x = {"action": "publish" if imp >= min_score else "hold", "target": "", "must_read": imp,
                     "reason": "masa puanı"}
            else:
                x = dict(raw.get(f"c{i + 1}") or {"action": "hold", "target": "", "must_read": 0, "reason": ""})
            try:
                x["must_read"] = max(0, min(10, int(x.get("must_read") or 0)))
            except (TypeError, ValueError):
                x["must_read"] = 0
            x["target"] = (x.get("target") or "").strip().removeprefix("s:")
            x["reason"] = clip(str(x.get("reason") or ""), 120)
            if x.get("action") not in ("publish", "update", "skip", "hold"):
                x["action"] = "hold"
            decisions[i] = x
        return self._guard(queue, decisions, slots, min_score, covered)

    def _daily_target(self) -> int:
        """Günlük yeni haber hedefi: aşılınca yalnızca çok büyük (önem ≥ 9) haberler yazılır."""
        ed = lambda k, d: self.cfg.get("editorial", k, d)  # noqa: E731
        return int(ed("max_drafts_per_day", 0) or 0) or int(ed("daily_target", 20) or 0) or 10 ** 6

    def _guard(self, queue: list[dict], decisions: dict[int, dict], slots: int, min_score: int,
               covered: list[dict]) -> dict[int, dict]:
        """Yönetmen kararlarına kurallı emniyet: eşik, tur başına yer, aynı habere tek güncelleme, günlük hedef,
        (isteğe bağlı) şirket sınırı."""
        cap = int(self.cfg.get("editorial", "max_per_company_per_day", 0) or 0)   # 0 = sınır yok
        today_n, target = self.store.count(self.today(), "drafts"), self._daily_target()
        day_keys: dict[str, int] = {}
        for c in covered:
            if c["status"] in ("published", "pending") and c["hours"] <= 24:
                for k in c["keys"]:
                    day_keys[k] = day_keys.get(k, 0) + 1
        published = {c["id"] for c in covered if c["status"] == "published"}
        published |= {p["id"] for p in self.store.posts()[:200] if hours_since(p.get("published_at")) <= 72}
        pending = {c["id"] for c in covered if c["status"] == "pending"}
        refreshed = {c["id"] for c in covered if c["status"] == "published" and c.get("updated") and c["hours"] < 6}
        used, round_targets = 0, set()
        for i in sorted(decisions, key=lambda i: -decisions[i]["must_read"]):
            x, s = decisions[i], queue[i]["story"]
            keys = entity_keys(s)
            mr = x["must_read"]
            if x["action"] == "update":
                if x["target"] in pending:
                    x["action"] = "merge"
                    continue
                if x["target"] not in published:
                    dup = (s.get("duplicate_of") or "").removeprefix("s:")
                    x["action"], x["target"] = ("update", dup) if dup in published else ("publish", "")
                if x["action"] == "update":
                    if mr < min_score - 1:
                        x["action"], x["reason"] = "skip", x["reason"] or "yeni gelişme yeterince önemli değil"
                    elif x["target"] in round_targets or (x["target"] in refreshed and mr < 9):
                        x["action"], x["reason"] = "skip", "haber az önce güncellendi"
                    else:
                        round_targets.add(x["target"])
                    continue
            if x["action"] != "publish":
                continue
            dup = (s.get("duplicate_of") or "").removeprefix("s:")
            if dup in published:            # masa "aynı haber" dedi: yeni haber değil, olsa olsa güncelleme
                ok = mr >= min_score and dup not in round_targets and (dup not in refreshed or mr >= 9)
                x["action"], x["target"] = ("update", dup) if ok else ("skip", dup)
                if ok:
                    round_targets.add(dup)
                continue
            if mr < min_score:
                x["action"], x["reason"] = "skip", f"önem {mr}/10, eşik {min_score}"
            elif mr < 9 and today_n + used >= target:
                x["action"], x["reason"] = "skip", f"günlük hedef ({target}) doldu; yalnızca çok büyük haberler"
            elif cap and mr < 9 and any(day_keys.get(k, 0) >= cap for k in keys):
                x["action"], x["reason"] = "skip", "aynı şirketten son 24 saatte haber var"
            elif used >= slots:
                x["action"] = "hold"
            else:
                used += 1
        return decisions

    def _edit_log(self, q: dict, action: str, x: dict) -> None:
        """Yönetmenin son kararları (/secki komutu ve günlük özet için)."""
        lg = self.state.setdefault("edit_log", [])
        lg.append({"t": iso(now_utc()), "topic": clip(q["story"].get("topic", ""), 90), "action": action,
                   "score": x.get("must_read", 0), "reason": x.get("reason", ""), "target": x.get("target", "")})
        del lg[:-200]

    def _queue(self, max_age: float) -> list[dict]:
        """Seçilmiş ama henüz yazılmamış haberler (eskiyenler düşer)."""
        out = []
        for q in self.state.get("queue") or []:
            pubs = [it.get("published") for it in q.get("items", []) if it.get("published")]
            newest = max(pubs) if pubs else q.get("at")
            if hours_since(newest) <= max_age and hours_since(q.get("at")) <= max_age:
                out.append(q)
        return out

    def _merge_sources(self, did: str, its: list[dict]) -> bool:
        d = self.store.load_draft(did)
        if not d or d.get("status") != "pending":
            return False
        urls = {s["url"] for s in d["sources"]}
        added = False
        for it in its:
            if it["url"] not in urls:
                d["sources"].append(self._source_entry(it))
                if it["source"] not in d["source_keys"]:
                    d["source_keys"].append(it["source"])
                added = True
        if added:
            self.store.save_draft(d)
        return added

    @staticmethod
    def _source_entry(it: dict) -> dict:
        return {"name": it["credit"], "url": it["url"], "title": it["title"], "kind": it["kind"],
                "via": it.get("via"), "via_url": it.get("via_url"), "published": it.get("published"),
                "image": it.get("image")}

    # ── 2) YAZIM ────────────────────────────────────────────
    @property
    def fixer(self) -> Fixer:
        """Türkçe metin düzeltici; sözlüğünü yayındaki haberlerin metinlerinden öğrenir (tur başına bir kez)."""
        if getattr(self, "_fixer", None) is None:
            self._fixer = Fixer([f"{p.get('summary', '')}\n{p.get('body', '')}" for p in self.store.posts()])
        return self._fixer

    @staticmethod
    def _appeal(v) -> int | None:
        try:
            return max(1, min(10, int(v)))
        except (TypeError, ValueError):
            return None

    def fix_texts(self) -> None:
        """Yayındaki haberlerde Türkçe karakteri düşmüş sözcükleri ve marka yazımlarını düzelt."""
        for p in self.store.posts():
            changed = self.fixer.post(p)
            if changed:
                p["updated_at"] = p.get("updated_at") or p.get("published_at")
                self.store.save_post(p)
                self.queue_indexnow(self.cfg.post_url(p))
                log.info("Metin düzeltildi: %s (%s)", p["id"], ", ".join(changed))

    def backfill_appeal(self, batch: int = 25) -> None:
        """İlgi puanı olmayan eski haberleri toplu puanla (ana sayfa seçkisi için)."""
        if not self.llm:
            return
        todo = [p for p in self.store.posts() if p.get("appeal") is None and not p.get("appeal_skip")][:batch]
        if not todo:
            return
        try:
            out = self.llm.json(self.cfg.get("ai", "triage_model", "gemini-flash-lite-latest"),
                                appeal_system(self.brand), appeal_user(todo), APPEAL_SCHEMA, max_tokens=3000)
        except LLMError as e:
            log.warning("İlgi puanları alınamadı: %s", e)
            return
        got = {str(x.get("id")): self._appeal(x.get("appeal")) for x in (out.get("scores") or []) if isinstance(x, dict)}
        for p in todo:
            if got.get(p["id"]):
                p["appeal"] = got[p["id"]]
            else:
                p["appeal_tries"] = int(p.get("appeal_tries", 0)) + 1
                if p["appeal_tries"] >= 3:
                    p["appeal_skip"] = True
            self.store.save_post(p)
        log.info("İlgi puanı verildi: %d haber", sum(1 for p in todo if p.get("appeal")))

    def backfill_cover_lines(self, batch: int = 25) -> None:
        """Kapak başlığı olmayan haberlere toplu kapak başlığı yaz (kapaklar ardından bu başlıkla yenilenir)."""
        if not self.llm:
            return
        todo = [p for p in self.store.posts()
                if p.get("cover_line_v") != COVERLINE_V and not p.get("cover_line_skip")][:batch]
        if not todo:
            return
        try:
            out = self.llm.json(self.cfg.get("ai", "writer_model", "gemini-flash-latest"),
                                coverline_system(self.brand), coverline_user(todo), COVERLINE_SCHEMA, max_tokens=5000)
        except LLMError as e:
            log.warning("Kapak başlıkları alınamadı: %s", e)
            return
        got = {str(x.get("id")): x for x in (out.get("lines") or []) if isinstance(x, dict)}
        n = 0
        for p in todo:
            line = self._cover_line((got.get(p["id"]) or {}).get("cover_headline"), (got.get(p["id"]) or {}).get("cover_highlight"))
            if line:
                changed = line.get("cover_headline") != p.get("cover_headline")
                p.update(line)
                p["cover_line_v"] = COVERLINE_V
                self.fixer.post(p)
                if changed and p.get("image"):
                    p["image"]["cover_v"] = 0          # kapak yeni başlıkla yeniden üretilsin
                n += 1
            else:
                p["cover_line_tries"] = int(p.get("cover_line_tries", 0)) + 1
                if p["cover_line_tries"] >= 3:
                    p["cover_line_skip"] = True
            self.store.save_post(p)
        log.info("Kapak başlığı yazıldı: %d haber", n)

    @staticmethod
    def _cover_ready(p: dict) -> bool:
        """Kapak yenilemesi için kapak başlığı hazır mı (ya da artık beklenmiyor mu)."""
        return bool((p.get("cover_headline") and p.get("cover_line_v") == COVERLINE_V) or p.get("cover_line_skip"))

    def _write(self, sources: list[dict], previous: dict | None = None, instruction: str | None = None) -> dict:
        cfg = self.cfg
        out = self.llm.json(
            cfg.get("ai", "writer_model", "claude-sonnet-5"),
            write_system(self.brand),
            write_user(sources, self.today(), previous, instruction),
            WRITE_SCHEMA, max_tokens=16000, effort=cfg.get("ai", "writer_effort", "medium"))
        cat = out.get("category") if out.get("category") in CATEGORIES else None
        res = {
            "title": clip((out.get("title") or "").strip().rstrip("."), 120),
            "summary": clip((out.get("summary") or "").strip(), 280),
            "body": (out.get("body") or "").strip(),
            "category": cat,
            "tags": [clip(t, 30) for t in (out.get("tags") or [])][:6],
            "confidence": out.get("confidence") if out.get("confidence") in CONF_LABEL else "orta",
            "flags": [f for f in (out.get("flags") or []) if f in FLAGS],
            "editor_note": clip(out.get("editor_note") or "", 200),
            "short_title": clip((out.get("short_title") or "").strip().rstrip("."), 70),
            "kicker": clip((out.get("kicker") or "").strip(), 28),
            "hero_stat": clip((out.get("hero_stat") or "").strip(), 16),
            "hero_stat_label": clip((out.get("hero_stat_label") or "").strip(), 36),
            "visual_style": out.get("visual_style") or "studio",
            "visual_scene": clip((out.get("visual_scene") or "").strip(), 600),
            "focus_keyword": clip((out.get("focus_keyword") or "").strip(), 60),
            "seo_title": clip((out.get("seo_title") or "").strip().rstrip("."), 62),
            "meta_description": clip((out.get("meta_description") or "").strip(), 170),
            "seo_slug": slugify(out["slug"], 64) if (out.get("slug") or "").strip() else "",
            "image_alt": clip((out.get("image_alt") or "").strip(), 125),
            "cover_text": clip((out.get("cover_text") or "").strip(), 24),
            "carousel_points": [clip(x.strip(), 130) for x in (out.get("carousel_points") or []) if x and x.strip()][:4],
            "appeal": self._appeal(out.get("appeal")),
            "update_note": clip((out.get("update_note") or "").strip(), 160),
            **self._cover_line(out.get("cover_headline"), out.get("cover_highlight")),
        }
        if res.get("cover_headline"):
            res["cover_line_v"] = COVERLINE_V
        self.fixer.post(res)          # Türkçe karakter ve marka yazımı düzeltmeleri
        return res

    @staticmethod
    def _cover_line(head, hl) -> dict:
        """Kapak başlığını denetle: çok uzunsa ya da boşsa kullanılmaz (kısa başlığa düşülür)."""
        head = re.sub(r"\s+", " ", str(head or "")).strip().rstrip(".!?…")
        hl = re.sub(r"\s+", " ", str(hl or "")).strip()
        if not head or len(head) > 56 or len(head.split()) < 2:
            return {}
        if not hl or hl.lower() not in head.lower() or len(hl) >= len(head):
            hl = ""
        return {"cover_headline": head, "cover_highlight": hl}

    def create_draft(self, story: dict, its: list[dict]) -> dict:
        cfg, st = self.cfg, self.store
        its = sorted(its, key=lambda x: KIND_ORDER.get(x["kind"], 3))[:4]
        texts = []
        for i, it in enumerate(its):
            txt = ""
            if i < 3 and cfg.get("editorial", "fetch_full_text", True) and not cfg.mock and not cfg.fixtures_dir:
                txt = full_text(it["url"])
            texts.append({"credit": it["credit"], "kind": it["kind"], "title": it["title"], "url": it["url"],
                          "published": it.get("published"), "summary": it.get("summary", ""), "text": txt})
        w = self._write(texts)
        did = short_hash(*sorted(it["key"] for it in its))
        d = {
            "id": did,
            "status": "pending",
            "created_at": iso(now_utc()),
            **w,
            "category": w["category"] or story.get("category") or DEFAULT_CATEGORY,
            "importance": int(story.get("must_read") or story.get("importance", 5)),
            "triage_reason": story.get("editor_reason") or story.get("reason", ""),
            "entities": list(story.get("entities") or []),
            "topic": story.get("topic", ""),
            "sources": [self._source_entry(it) for it in its],
            "source_keys": list(dict.fromkeys(it["source"] for it in its)),
            "source_texts": texts,
            "rewrites": 0,
            "telegram": {},
        }
        if not self._attach_photos(d, draft=True):
            d["image"] = self.vis.make_hero(d, st.draft_image(did))
            self._image_feedback(d["image"])
        st.bump(self.today(), "drafts")
        decision, reason = policy.decide(cfg, self.state, self.stats, d)
        d["policy_reason"] = reason
        log.info("Taslak %s [%s] önem=%s güven=%s → %s (%s)", did, d["category"], d["importance"],
                 d["confidence"], decision, reason)
        if decision == "auto" and not self.state.get("paused"):
            post = self.publish(d, auto=True)
            self._send_preview(post, "auto")
            self._send_social(post)
        else:
            st.save_draft(d)
            self._send_preview(d, "pending")
        return d

    # ── mevcut haberi geliştirme ────────────────────────────
    UPDATE_FIELDS = ("title", "summary", "body", "tags", "short_title", "kicker", "hero_stat", "hero_stat_label",
                     "focus_keyword", "seo_title", "meta_description", "image_alt", "cover_text", "carousel_points",
                     "cover_headline", "cover_highlight", "cover_line_v", "confidence", "flags", "editor_note")

    def create_update(self, post: dict, story: dict, its: list[dict]) -> dict | None:
        """Yayındaki habere yeni gelişme geldi: yeni haber yerine güncelleme taslağı (onaylanınca haber yerinde güncellenir)."""
        cfg, st = self.cfg, self.store
        known = {x["url"] for x in post.get("sources") or []}
        its = [it for it in sorted(its, key=lambda x: KIND_ORDER.get(x["kind"], 3)) if it["url"] not in known][:3]
        if not its:
            return None
        texts = []
        for it in its:
            txt = ""
            if cfg.get("editorial", "fetch_full_text", True) and not cfg.mock and not cfg.fixtures_dir:
                txt = full_text(it["url"])
            texts.append({"credit": it["credit"], "kind": it["kind"], "title": it["title"], "url": it["url"],
                          "published": it.get("published"), "summary": it.get("summary", ""), "text": txt})
        prev = {"_update": True, "title": post["title"], "summary": post["summary"], "body": post["body"]}
        w = self._write(texts, previous=prev)
        did = short_hash("u", post["id"], *sorted(it["key"] for it in its))
        d = {
            "id": did,
            "status": "pending",
            "update_of": post["id"],
            "created_at": iso(now_utc()),
            **w,
            "category": post.get("category") or w["category"] or DEFAULT_CATEGORY,
            "importance": int(story.get("must_read") or story.get("importance", 5)),
            "triage_reason": story.get("editor_reason") or story.get("reason", ""),
            "entities": list(story.get("entities") or post.get("entities") or []),
            "topic": story.get("topic", ""),
            "sources": [self._source_entry(it) for it in its],
            "source_keys": list(dict.fromkeys(it["source"] for it in its)),
            "source_texts": texts,
            "rewrites": 0,
            "telegram": {},
            "image": dict(post.get("image") or {}),
        }
        st.bump(self.today(), "updates")
        decision, reason = policy.decide(cfg, self.state, self.stats, d)
        d["policy_reason"] = reason
        log.info("Güncelleme taslağı %s → %s: %s (%s)", did, post["id"], decision, reason)
        if decision == "auto" and not self.state.get("paused"):
            new = self.apply_update(d)
            if new:
                self._send_preview({**d, "slug": new["slug"], "path": self.cfg.post_path(new)}, "updated")
        else:
            st.save_draft(d)
            self._send_preview(d, "pending")
        return d

    def apply_update(self, d: dict) -> dict | None:
        """Güncelleme taslağını yayındaki habere işle: adres aynı kalır, yeni kaynaklar eklenir, kapak yeni başlıkla yenilenir."""
        st = self.store
        post = st.load_post(d.get("update_of") or "")
        if not post:
            return None
        for k in self.UPDATE_FIELDS:
            if d.get(k) not in (None, "", []):
                post[k] = d[k]
        known = {x["url"] for x in post.get("sources") or []}
        post["sources"] = (post.get("sources") or []) + [x for x in d.get("sources") or [] if x["url"] not in known]
        post["source_keys"] = list(dict.fromkeys((post.get("source_keys") or []) + (d.get("source_keys") or [])))
        now = iso(now_utc())
        post["updated_at"] = post["refreshed_at"] = now
        post.setdefault("updates", []).append({"at": now, "note": d.get("update_note") or "",
                                               "sources": list(dict.fromkeys(x["name"] for x in d.get("sources") or []))})
        post["importance"] = max(int(post.get("importance") or 0), int(d.get("importance") or 0))
        if d.get("appeal"):
            post["appeal"] = max(int(post.get("appeal") or 0), int(d["appeal"]))
        if d.get("entities") and not post.get("entities"):
            post["entities"] = d["entities"]
        try:
            if post.get("photos") and (post.get("image") or {}).get("source") == "photo":
                self._build_cover(post, draft=False)
            elif (post.get("image") or {}).get("source") in ("cover", "fallback", None):
                post["image"] = {**self.vis.make_hero(post, st.post_image(post["id"])), "cover_v": COVER_VERSION}
            self._make_og(post)
        except Exception as e:  # noqa: BLE001
            log.warning("Güncellenen haberin kapağı yenilenemedi (%s): %s", post["id"], e)
        st.save_post(post)
        self.queue_indexnow(self.cfg.post_url(post))
        st.draft_path(d["id"]).unlink(missing_ok=True)
        st.bump(self.today(), "updated")
        log.info("Haber güncellendi: %s", post["id"])
        return post

    def _credits(self, d: dict) -> list[str]:
        return list(dict.fromkeys(s["name"] for s in d.get("sources", [])))

    def _image_feedback(self, info: dict) -> None:
        if info.get("source") == "ai":
            self.store.bump(self.today(), "images")
        elif info.get("error"):
            self.notify_error("Yapay zeka görseli üretilemedi, yedek 3D görsel kullanıldı. "
                              "Google hesabında ödeme bağlı mı ve GEMINI_API_KEY doğru mu? Ayrıntı: " + info["error"][:200])
        elif not self.cfg.google_key and not self.cfg.mock and not self.state.get("gemini_hint_sent"):
            self.state["gemini_hint_sent"] = True
            self.notify("ℹ️ <b>GEMINI_API_KEY</b> tanımlı olmadığı için haber görselleri ücretsiz 3D görsellerle üretiliyor. "
                        "Her habere özel yapay zeka görseli için kurulum rehberindeki 3. adımı tamamla.", silent=True)

    def _hero(self, d: dict):
        st = self.store
        return st.post_image(d["id"]) if st.post_path(d["id"]).exists() else st.draft_image(d["id"])

    def _card(self, d: dict, kind: str):
        """Kartı (.cache içine) üret ve yolunu döndür."""
        hero = self._hero(d)
        if not hero.exists():
            d["image"] = self.vis.make_hero(d, hero)
        return self.vis.render_card(d, kind, hero, self.store.card_path(d["id"], kind))

    # ── 3) YAYIN ────────────────────────────────────────────
    def publish(self, d: dict, auto: bool) -> dict:
        st = self.store
        used = {p.get("slug") for p in st.posts()}
        base = d.get("seo_slug") if len(d.get("seo_slug") or "") >= 12 else slugify(d["title"], 64)
        slug, n = base, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        post = {k: v for k, v in d.items() if k not in ("source_texts", "status", "policy_reason")}
        post.update({"slug": slug, "published_at": iso(now_utc()), "publish_mode": "auto" if auto else "manual"})
        post.pop("path", None)
        post["path"] = self.cfg.post_path(post)        # kalıcı adres: kategori/yıl/ay/slug
        self.queue_indexnow(self.cfg.post_url(post))
        st.move_image_to_post(d["id"])
        img = post.get("image") or {}
        if img.get("source") in ("cover", "fallback") and img.get("cover_v") != COVER_VERSION:
            post["image"] = self.vis.make_hero(post, st.post_image(d["id"]))
        elif not st.post_image(d["id"]).exists():
            post["image"] = self.vis.make_hero(post, st.post_image(d["id"]))
        self._make_og(post)
        st.save_post(post)
        st.draft_path(d["id"]).unlink(missing_ok=True)
        st.bump(self.today(), "published")
        st.bump(self.today(), "auto" if auto else "approved")
        log.info("Yayınlandı: %s → %s", post["id"], self.cfg.post_url(post))
        return post

    # ── Telegram önizlemeleri ───────────────────────────────
    def _caption(self, d: dict, kind: str) -> str:
        head = {
            "pending": "🟡 <b>ONAY BEKLİYOR</b>",
            "published": "✅ <b>YAYINLANDI</b>",
            "auto": "🤖 <b>OTOMATİK YAYINLANDI</b>",
            "rejected": "❌ <b>REDDEDİLDİ</b>",
            "expired": "⌛ <b>SÜRESİ DOLDU</b>",
            "removed": "🗑 <b>SİTEDEN KALDIRILDI</b>",
            "rewritten": "🔁 <b>YENİDEN YAZILDI</b> (yeni sürüm aşağıda)",
            "updated": "🔄 <b>HABER GÜNCELLENDİ</b>",
            "culled": "🧹 <b>SEÇKİ DIŞI</b> (yeni ölçütlere göre elendi)",
        }[kind]
        upd = d.get("update_of")
        if upd and kind == "pending":
            head = "🔄 <b>GÜNCELLEME ÖNERİSİ</b> (yeni haber değil, mevcut haber geliştirilir)"
        meta = f"🏷 {esc(category_label(d['category']))} · Önem {d.get('importance', '?')}/10 · Güven {CONF_LABEL.get(d.get('confidence'), '?')}"
        lines = [head, "", f"<b>{esc(d['title'])}</b>", "", "{SUMMARY}", ""]
        if upd and kind in ("pending", "updated", "rejected", "expired"):
            orig = self.store.load_post(upd) or {}
            if orig.get("title") and orig.get("title") != d.get("title"):
                lines.append(f"📌 Mevcut haber: <i>{esc(clip(orig['title'], 110))}</i>")
            if d.get("update_note"):
                lines.append(f"🆕 {esc(d['update_note'])}")
        lines += ["📰 " + esc(", ".join(self._credits(d))), meta]
        if d.get("focus_keyword") and kind in ("pending", "auto"):
            lines.append(f"🔎 Google: <i>{esc(d['focus_keyword'])}</i>")
        if d.get("flags"):
            fl = ", ".join(FLAG_LABELS.get(f, f) for f in d["flags"])
            note = f" — {esc(d['editor_note'])}" if d.get("editor_note") else ""
            lines.append(f"⚠️ {esc(fl)}{note}")
        elif d.get("editor_note") and kind == "pending":
            lines.append(f"📝 {esc(d['editor_note'])}")
        if kind == "pending" and d.get("policy_reason"):
            lines.append(f"<i>Neden sordum: {esc(d['policy_reason'])}</i>")
        if kind in ("published", "auto", "updated") and d.get("slug"):
            lines.append(f'🔗 <a href="{esc(self.cfg.post_url(d))}">Sitede aç</a>')
        cap = "\n".join(lines)
        room = 1024 - len(cap) + len("{SUMMARY}") - 5
        return cap.replace("{SUMMARY}", esc(clip(d.get("summary", ""), max(60, room))))

    def _keyboard(self, d: dict, kind: str):
        did = d["id"]
        src = d["sources"][0]["url"] if d.get("sources") else None
        if kind == "pending" and d.get("update_of"):
            kb = [[{"text": "🔄 Güncelle", "callback_data": f"p:{did}"},
                   {"text": "❌ Reddet", "callback_data": f"r:{did}"}],
                  [{"text": "📄 Tam metin", "callback_data": f"f:{did}"},
                   {"text": "🔁 Yeniden yaz", "callback_data": f"w:{did}"}]]
            orig = self.store.load_post(d["update_of"])
            links = ([{"text": "🔗 Mevcut haber", "url": self.cfg.post_url(orig)}] if orig else []) + \
                    ([{"text": "🔗 Yeni kaynak", "url": src}] if src else [])
            if links:
                kb.append(links)
            return kb
        if kind == "updated":
            return [[{"text": "🔗 Haberi aç", "url": self.cfg.post_url(d)}]] if d.get("slug") else []
        if kind == "pending":
            kb = [[{"text": "✅ Yayınla", "callback_data": f"p:{did}"},
                   {"text": "❌ Reddet", "callback_data": f"r:{did}"}],
                  [{"text": "⭐ Yayınla + manşet", "callback_data": f"P:{did}"}],
                  [{"text": "📄 Tam metin", "callback_data": f"f:{did}"},
                   {"text": "🔁 Yeniden yaz", "callback_data": f"w:{did}"}], self._visual_buttons(d)]
            if src:
                kb.append([{"text": "🔗 Kaynağı aç", "url": src}])
            return kb
        if kind in ("published", "auto"):
            return [[{"text": "🔗 Haberi aç", "url": self.cfg.post_url(d)},
                     {"text": "🗑 Kaldır", "callback_data": f"d:{did}"}],
                    [{"text": "📄 Tam metin", "callback_data": f"f:{did}"}], self._visual_buttons(d),
                    [{"text": "⭐ Manşetten çıkar" if d.get("home") == "pin" else "⭐ Manşete al", "callback_data": f"m:{did}"},
                     {"text": "🏠 Ana sayfada göster" if d.get("home") == "hide" else "🙈 Ana sayfada gösterme",
                      "callback_data": f"h:{did}"}]]
        if kind == "rejected":
            return [[{"text": "↩️ Geri al", "callback_data": f"u:{did}"}]]
        return []

    def _send_preview(self, d: dict, kind: str) -> None:
        if not (self.tg and self.chat_id):
            return
        st = self.store
        try:
            if d.get("update_of") and st.post_image(d["update_of"]).exists():
                img = st.post_image(d["update_of"])       # güncelleme: haberin mevcut kapağı
            else:
                img = self._hero(d) if d.get("photos") and self._hero(d).exists() else self._card(d, "post")
        except Exception as e:  # noqa: BLE001
            log.warning("Önizleme kartı üretilemedi: %s", e)
            img = self._hero(d)
        silent = True if kind == "auto" else self.quiet()
        caption = self._caption(d, kind)
        try:
            res = self.tg.send_photo(self.chat_id, img, caption, self._keyboard(d, kind), silent=silent)
        except TelegramError as e:
            log.warning("Önizleme HTML ile gönderilemedi (%s); düz metin deneniyor", e)
            plain = html.unescape(re.sub(r"<[^>]+>", "", caption))[:1024]
            try:
                res = self.tg.send_photo(self.chat_id, img, plain, self._keyboard(d, kind), silent=silent,
                                         parse_mode=None)
            except (TelegramError, OSError) as e2:
                log.warning("Önizleme gönderilemedi: %s", e2)
                return
        except OSError as e:
            log.warning("Önizleme görseli okunamadı: %s", e)
            return
        if kind == "updated":
            return
        d.setdefault("telegram", {})["message_id"] = res.get("message_id")
        if kind in ("published", "auto"):
            st.save_post(d)
        else:
            st.save_draft(d)

    def instagram_caption(self, post: dict) -> str:
        """Instagram gönderi açıklaması: başlık, özet, neden önemli, kaynak, yönlendirme ve etiketler."""
        from .covers import why_text
        tags = []
        for t in (post.get("tags") or []) + [category_label(post.get("category", "")), self.brand]:
            h = re.sub(r"[^0-9A-Za-zÇĞİÖŞÜçğıöşü]", "", t or "")
            if h and h.lower() not in {x.lower() for x in tags}:
                tags.append(h)
        why = why_text(post)
        parts = [post["title"], "", post.get("summary", "")]
        if why and why != post.get("summary"):
            parts += ["", f"Neden önemli? {why}"]
        parts += ["", f"Kaynak: {', '.join(self._credits(post))}", "Haberin tamamı profildeki bağlantıda.", "",
                  " ".join("#" + t for t in tags[:8])]
        return "\n".join(parts)

    def _send_social(self, post: dict, force: bool = False) -> None:
        """Instagram için hazır carousel ve hikâyeyi Telegram'a gönder (elle paylaşım için).
        Carousel: kapak + öne çıkanlar + neden önemli. Hikâye: bağlantı çıkartmasıyla siteye yönlendirir."""
        if not force and self.ig_enabled:
            self.ig_enqueue(post)
            return
        if not (self.tg and self.chat_id):
            return
        if not force and not self.cfg.get("social", "send_to_telegram", True):
            return
        url = self.cfg.post_url(post)
        try:
            kinds = self.vis.CAROUSEL if self.vis.summary_style else ["post"]
            files = [self._card(post, k) for k in kinds]
            cap = (f"📱 <b>Instagram gönderisi</b> ({len(files)} görsel, bu sırayla)\n"
                   f"Açıklama metni (dokunup kopyala):\n<code>{esc(clip(self.instagram_caption(post), 850))}</code>")
            self.tg.send_media_group(self.chat_id, files, caption=cap, silent=True)
        except Exception as e:  # noqa: BLE001
            log.warning("Instagram gönderisi hazırlanamadı: %s", e)
        try:
            story = self._card(post, "story")
            cap = (f"📲 <b>Instagram hikâyesi</b>\nHikâyeye <b>Bağlantı</b> çıkartması ekle, bu adresi yapıştır ve "
                   f"çıkartmayı okun altındaki boşluğa yerleştir:\n<code>{esc(url)}</code>")
            self.tg.send_photo(self.chat_id, story, cap, [[{"text": "🔗 Haberi aç", "url": url}]], silent=True)
        except Exception as e:  # noqa: BLE001
            log.warning("Instagram hikâyesi hazırlanamadı: %s", e)

    def _update_preview(self, d: dict, kind: str) -> None:
        mid = (d.get("telegram") or {}).get("message_id")
        if self.tg and self.chat_id and mid:
            self.tg.edit_caption(self.chat_id, mid, self._caption(d, kind), self._keyboard(d, kind))

    # ── 4) TELEGRAM GİRDİLERİ ───────────────────────────────
    def process_updates(self, timeout: int = 0) -> int:
        if not self.tg:
            return 0
        try:
            ups = self.tg.get_updates(self.state.get("telegram_offset", 0), timeout=timeout)
        except TelegramError as e:
            log.warning("Telegram güncellemeleri alınamadı: %s", e)
            if timeout:
                time.sleep(min(timeout, 10))
            return 0
        if ups:
            log.info("Telegram: %d yeni girdi (offset %s → %s)", len(ups), self.state.get("telegram_offset", 0),
                     ups[-1]["update_id"] + 1)
        for u in ups:
            self.state["telegram_offset"] = u["update_id"] + 1
            try:
                self._handle(u)
            except LLMError as e:
                self.notify(f"⚠️ Yapay zeka hatası: {esc(e)}")
            except Exception as e:  # noqa: BLE001
                log.exception("Güncelleme işlenemedi: %s", e)
        return len(ups)

    def _authorized(self, chat_id) -> bool:
        return bool(self.chat_id) and str(chat_id) == str(self.chat_id)

    def _handle(self, u: dict) -> None:
        if "callback_query" in u:
            cq = u["callback_query"]
            chat = (cq.get("message") or {}).get("chat", {}).get("id")
            if not self._authorized(chat):
                self.tg.answer_callback(cq["id"], "Yetkin yok.")
                return
            self.state["last_activity"] = iso(now_utc())
            action, _, did = (cq.get("data") or "").partition(":")
            self._cb_mid = (cq.get("message") or {}).get("message_id")
            log.info("Telegram düğmesi: %s %s", action, did)
            slow = SLOW_ACTIONS.get(action)
            if slow:  # uzun süren işlerde düğme hemen yanıt versin
                self.tg.answer_callback(cq["id"], slow[0])
                msg = self._on_button(action, did)
                if msg and msg != slow[1]:
                    self.notify(esc(msg), silent=True)
                return
            msg = self._on_button(action, did)
            self.tg.answer_callback(cq["id"], msg)
            return

        msg = u.get("message") or {}
        chat = msg.get("chat", {}).get("id")
        text = (msg.get("text") or "").strip()
        if not chat:
            return
        if not self.chat_id:
            # Kurulum yardımcısı: sohbet numarasını söyle
            if str(chat) not in self.state.setdefault("chat_id_hint_sent", []):
                self.state["chat_id_hint_sent"].append(str(chat))
                self.tg.send_message(chat, f"👋 Merhaba! Senin sohbet numaran: <code>{chat}</code>\n\n"
                                           f"Bunu GitHub'da <b>TELEGRAM_CHAT_ID</b> adıyla gizli anahtar olarak kaydet. "
                                           f"Sonra bot sadece sana çalışır.")
            return
        if not self._authorized(chat):
            return
        self.state["last_activity"] = iso(now_utc())
        log.info("Telegram mesajı: %s", clip(text, 40))
        self.tg.typing(chat)

        reply_to = (msg.get("reply_to_message") or {}).get("message_id")
        if reply_to and text and not text.startswith("/"):
            self._on_reply_edit(reply_to, text, msg.get("message_id"))
            return
        if not text.startswith("/"):
            self.tg.send_message(chat, "Komutlar için /yardim yazabilirsin. Bir haberi düzeltmek için o haberin mesajını yanıtla.")
            return
        cmd, _, arg = text[1:].partition(" ")
        cmd = cmd.split("@")[0].lower()
        self._on_command(cmd, arg.strip().lower())

    # ── butonlar ────────────────────────────────────────────
    def _on_button(self, action: str, did: str) -> str:
        st = self.store
        if action == "x":
            return "🚫 Instagram'a gönderilmeyecek" if self._ig_drop(did, cancelled=True) else "Sırada değil (paylaşılmış olabilir)."
        if action == "q":
            post = st.load_post(did)
            if not post:
                return "Bu haber artık yayında değil."
            return "📸 Tekrar sıraya alındı" if self.ig_enqueue(post, mid=self._cb_mid) else "Zaten sırada ya da paylaşıldı."
        where, d = st.find_any(did)
        if not d:
            return "Bu haber artık yok."
        if action in ("p", "P") and where == "draft" and d.get("update_of"):
            if d.get("status") not in ("pending", "rejected"):
                return "Bu taslak kapanmış."
            if d.get("status") == "rejected":
                self._undo_decision(d)
            post = self.apply_update(d)
            if not post:
                st.archive_draft(d, "expired")
                return "Asıl haber artık yayında değil."
            policy.record(self.stats, d, ok=True)
            self._update_preview({**d, "slug": post["slug"], "path": self.cfg.post_path(post)}, "updated")
            return "🔄 Haber güncellendi"
        if action == "P":                     # yayınla ve manşete al
            if where == "post":
                return self._on_button("m", did) if d.get("home") != "pin" else "Zaten manşette."
            if d.get("status") not in ("pending", "rejected"):
                return "Bu taslak kapanmış."
            if d.get("status") == "rejected":
                self._undo_decision(d)
            d["home"], d["home_at"] = "pin", iso(now_utc())
            post = self.publish(d, auto=False)
            policy.record(self.stats, post, ok=True)
            self._update_preview(post, "published")
            self._send_social(post)
            return "⭐ Yayınlandı ve manşete alındı"
        if action == "p":
            if where == "post":
                return "Zaten yayında."
            if d.get("status") not in ("pending", "rejected"):
                return "Bu taslak kapanmış."
            if d.get("status") == "rejected":
                self._undo_decision(d)
            post = self.publish(d, auto=False)
            policy.record(self.stats, post, ok=True)
            self._update_preview(post, "published")
            self._send_social(post)
            return "✅ Yayınlandı"
        if action == "r":
            if where != "draft" or d.get("status") != "pending":
                return "Bu haber beklemede değil."
            d["status"] = "rejected"
            d["rejected_at"] = iso(now_utc())
            st.save_draft(d)
            st.bump(self.today(), "rejected")
            policy.record(self.stats, d, ok=False)
            self._update_preview(d, "rejected")
            return "❌ Reddedildi"
        if action == "u":
            if where != "draft" or d.get("status") != "rejected":
                return "Geri alınacak bir şey yok."
            self._undo_decision(d)
            st.bump(self.today(), "rejected", -1)
            d["status"] = "pending"
            d.pop("rejected_at", None)
            st.save_draft(d)
            self._update_preview(d, "pending")
            return "↩️ Tekrar beklemede"
        if action == "d":
            if where != "post":
                return "Bu haber yayında değil."
            st.delete_post(did)
            self._ig_drop(did, "🗑 Haber siteden kaldırıldığı için Instagram'a gönderilmeyecek")
            weight = 2 if d.get("publish_mode") == "auto" else 1
            policy.record(self.stats, d, ok=False, weight=weight)
            st.bump(self.today(), "removed")
            st.archive_draft(d, "removed")
            self._update_preview(d, "removed")
            return "🗑 Siteden kaldırılıyor (birkaç dakika sürebilir)"
        if action == "f":
            mid = (d.get("telegram") or {}).get("message_id")
            body = f"<b>{esc(d['title'])}</b>\n\n{md_to_tg(d.get('body', ''))}\n\n" + "\n".join(
                f'• <a href="{esc(s["url"])}">{esc(s["name"])}</a>: {esc(clip(s.get("title", ""), 90))}'
                for s in d.get("sources", []))
            self.tg.send_message(self.chat_id, body, reply_to=mid, silent=True)
            return ""
        if action in ("m", "h"):
            # ana sayfa seçkisi: manşete sabitle (36 saat) ya da ana sayfada hiç gösterme (kategoride kalır)
            if where != "post":
                return "Önce yayınlanmalı."
            cur = d.get("home")
            new = ("pin" if cur != "pin" else None) if action == "m" else ("hide" if cur != "hide" else None)
            if new:
                d["home"], d["home_at"] = new, iso(now_utc())
            else:
                d.pop("home", None)
                d.pop("home_at", None)
            st.save_post(d)
            self._update_preview(d, "auto" if d.get("publish_mode") == "auto" else "published")
            if self._cb_mid and self._cb_mid == self.state.get("manset_mid"):
                self.tg.edit_text(self.chat_id, self._cb_mid, self._manset_text(), self._manset_keyboard())
            return {"pin": "⭐ Manşete alındı", "hide": "🙈 Ana sayfada gösterilmeyecek (kategoride kalır)",
                    None: "↩️ Ana sayfada normal sıralamaya döndü"}[new]
        if action == "v":
            if where == "draft" and d.get("status") != "pending":
                return "Bu taslak kapanmış."
            self._rewrite(d, None, where, visual_only="")
            return "🎨 Yeni görsel hazır"
        if action in ("g", "n"):
            if where == "draft" and d.get("status") != "pending":
                return "Bu taslak kapanmış."
            if not d.get("photos"):
                return "Bu haberde fotoğraf yok."
            if action == "g":
                local = [r for r in d["photos"] if r.get("file")]
                good = [r for r in local if not r.get("graphic")]
                if d.get("cover_mode") == "type" and any(self._coverable(r) for r in good):
                    d.pop("cover_mode", None)            # yazılı kapaktan fotoğraflı kapağa dön
                    self._build_cover(d, where == "draft")
                    msg = "🖼 Fotoğraflı kapak"
                else:
                    coverable = [r for r in good if self._coverable(r)]
                    if len(coverable) < 2:
                        return "Kapak olabilecek başka fotoğraf yok."
                    cur = next((r for r in coverable if r["file"] == (d.get("image") or {}).get("photo")), coverable[0])
                    rest = [r for r in good if r is not cur]      # grafikler sonda kalır
                    self._reorder_photos(d, where, rest + [cur] + [r for r in local if r.get("graphic")])
                    msg = "🖼 Fotoğraf değişti"
            else:
                self._drop_photos(d, where)
                d["image"] = self.vis.make_hero(d, self._hero(d))
                msg = "🚫 Fotoğraflar kaldırıldı"
            kind = "pending" if where == "draft" else ("auto" if d.get("publish_mode") == "auto" else "published")
            if where == "draft":
                st.save_draft(d)
            else:
                d["updated_at"] = iso(now_utc())
                self._make_og(d)
                st.save_post(d)
            self._update_preview(d, "rewritten")
            self._send_preview(d, kind)
            return msg
        if action == "s":   # eski mesajlardaki "Instagram" düğmesi: görseller artık Telegram'a gelmez
            if where != "post":
                return "Önce yayınlanmalı."
            if self.ig_enabled:
                return "📸 Instagram sırasına eklendi" if self.ig_enqueue(d) else "Zaten sırada ya da paylaşıldı."
            return "📸 Instagram bağlanınca haberler kendiliğinden paylaşılacak."
        if action == "w":
            if where != "draft" or d.get("status") != "pending":
                return "Sadece bekleyen haberler yeniden yazılabilir. Yayındakini düzeltmek için mesajı yanıtla."
            self._rewrite(d, None, where)
            return "🔁 Yeniden yazıldı"
        return ""

    def _undo_decision(self, d: dict) -> None:
        """Son reddi istatistiklerden düş."""
        for s in d.get("source_keys", []):
            e = self.stats.get("sources", {}).get(s)
            if e and e.get("rejected", 0) > 0:
                e["rejected"] -= 1
        decs = self.stats.get("decisions", [])
        for i in range(len(decs) - 1, -1, -1):
            if decs[i].get("id") == d["id"] and not decs[i].get("ok"):
                decs.pop(i)
                break

    def _on_reply_edit(self, reply_to: int, instruction: str, user_mid: int | None) -> None:
        st = self.store
        target, where = None, ""
        for d in st.drafts("pending"):
            if (d.get("telegram") or {}).get("message_id") == reply_to:
                target, where = d, "draft"
                break
        if not target:
            for p in st.posts()[:200]:
                if (p.get("telegram") or {}).get("message_id") == reply_to:
                    target, where = p, "post"
                    break
        if not target:
            self.tg.send_message(self.chat_id, "Bu mesaja bağlı bekleyen ya da yayında olan bir haber bulamadım.",
                                 reply_to=user_mid)
            return
        m = re.match(r"^\s*g[öo]rsel\s*[:：]\s*(.*)$", instruction, re.I | re.S)
        if m:
            self._rewrite(target, None, where, visual_only=m.group(1))
            return
        if not self.llm:
            self.tg.send_message(self.chat_id, "Yapay zeka anahtarı (GEMINI_API_KEY) tanımlı değil.", reply_to=user_mid)
            return
        self._rewrite(target, instruction, where)

    def _rewrite(self, d: dict, instruction: str | None, where: str, visual_only: str | None = None) -> None:
        """Metni yeniden yaz; visual_only verilirse sadece görseli yenile (boş dize = aynı sahne, yeni deneme)."""
        if (d.get("rewrites") or 0) >= 8:
            self.tg.send_message(self.chat_id, "Bu haber 8 kez düzenlendi; lütfen yayınla ya da reddet.")
            return
        st = self.store
        new_visual = visual_only is not None
        if new_visual:
            text = visual_only.strip()
            if text and len(text) <= 56:   # kısa ifade: kapak başlığı olsun (fotoğraflı kapakta da)
                d["cover_headline"], d["cover_highlight"], d["cover_line_v"] = text, "", COVERLINE_V
                d["cover_variant"] = int(d.get("cover_variant", 0)) + 1
            elif text:                      # uzun ifade: yapay zeka görseli sahnesi
                d["visual_scene"] = text
                d["cover_mode"] = "type"
            else:                           # "Yeni kapak" düğmesi: yazılı kapak, yeni renk ve düzen
                d["cover_variant"] = int(d.get("cover_variant", 0)) + 1
                d["cover_mode"] = "type"
            d["rewrites"] = (d.get("rewrites") or 0) + 1
            old_kind = "pending" if where == "draft" else ("auto" if d.get("publish_mode") == "auto" else "published")
            self._build_cover(d, where == "draft")   # fotoğraflar galeride kalır
            self._image_feedback(d["image"])
            if where == "draft":
                self._update_preview(d, "rewritten")
                st.save_draft(d)
                self._send_preview(d, "pending")
            else:
                d["updated_at"] = iso(now_utc())
                self._make_og(d)
                st.save_post(d)
                self._update_preview(d, "rewritten")
                self._send_preview(d, old_kind)
            return
        sources = d.get("source_texts") or [
            {"credit": s["name"], "kind": s["kind"], "title": s["title"], "url": s["url"],
             "published": s.get("published"), "summary": "", "text": ""} for s in d["sources"]]
        prev = {"title": d["title"], "summary": d["summary"], "body": d["body"]}
        w = self._write(sources, previous=prev, instruction=instruction)
        old_kind = "pending" if where == "draft" else d.get("publish_mode") == "auto" and "auto" or "published"
        d.update({k: v for k, v in w.items() if v not in (None, "", [])})
        d["rewrites"] = (d.get("rewrites") or 0) + 1
        st = self.store
        if where == "draft":
            self._update_preview(d, "rewritten")
            st.save_draft(d)
            self._send_preview(d, "pending")
        else:  # yayındaki haber: yerinde güncelle (adres değişmez)
            d["updated_at"] = iso(now_utc())
            self._make_og(d)
            st.save_post(d)
            self._update_preview(d, "rewritten")
            self._send_preview(d, old_kind if old_kind in ("published", "auto") else "published")

    # ── komutlar ────────────────────────────────────────────
    def _on_command(self, cmd: str, arg: str) -> None:
        if cmd in ("start", "yardim", "help"):
            self.notify(HELP, silent=True)
        elif cmd == "durum":
            self.notify(self.status_text(), silent=True)
        elif cmd == "mod":
            if arg in policy.MODES:
                self.state["mode_override"] = arg
                self.notify(f"Mod: <b>{policy.MODES[arg]}</b>", silent=True)
            else:
                m = policy.current_mode(self.cfg, self.state)
                self.notify(f"Şu anki mod: <b>{policy.MODES[m]}</b>\nDeğiştirmek için: <code>/mod manuel</code>, "
                            f"<code>/mod ogrenen</code> ya da <code>/mod tam</code>", silent=True)
        elif cmd == "duraklat":
            self.state["paused"] = True
            self.notify("⏸ Duraklatıldı. Toplama ve otomatik yayın durdu. Devam için /devam", silent=True)
        elif cmd == "devam":
            self.state["paused"] = False
            self.notify("▶️ Devam ediyor.", silent=True)
        elif cmd == "topla":
            self.force_collect = True
            self.notify("🔎 Kaynaklar taranıyor…", silent=True)
        elif cmd == "bekleyen":
            pend = self.store.drafts("pending")
            if not pend:
                self.notify("Bekleyen haber yok. 🎉", silent=True)
            else:
                lines = [f"🟡 <b>{len(pend)} haber onay bekliyor</b>"]
                for d in pend[:20]:
                    lines.append(f"• {esc(clip(d['title'], 90))} <i>({hours_since(d['created_at']):.0f} sa)</i>")
                self.notify("\n".join(lines), silent=True)
        elif cmd == "kaynaklar":
            self.notify(self.sources_text(), silent=True)
        elif cmd in ("secki", "seçki"):
            self.notify(self.edit_text(), silent=True)
        elif cmd in ("manset", "manşet"):
            res = self.tg.send_message(self.chat_id, self._manset_text(), keyboard=self._manset_keyboard(), silent=True)
            if isinstance(res, dict) and res.get("message_id"):
                self.state["manset_mid"] = res["message_id"]
        elif cmd == "instagram":
            if arg in ("kapat", "durdur"):
                self.state["ig_off"] = True
                self.notify("⏸ Instagram paylaşımları durdu. Sıradakiler bekliyor. Açmak için <code>/instagram ac</code>", silent=True)
            elif arg in ("ac", "aç", "baslat", "başlat"):
                self.state["ig_off"] = False
                self.notify("▶️ Instagram paylaşımları açık.", silent=True)
            else:
                self.notify(self.instagram_status(), silent=True)
        else:
            self.notify("Bilinmeyen komut. /yardim", silent=True)

    def _cost(self, c: dict) -> float:
        return c.get("cost_usd", 0) + c.get("images", 0) * float(self.cfg.get("images", "cost_per_image", 0.035))

    def edit_text(self) -> str:
        """/secki: yayın yönetmeninin son kararları."""
        lg = self.state.get("edit_log") or []
        if not lg:
            return "Henüz karar yok."
        icon = {"publish": "✅", "update": "🔄", "merge": "➕", "skip": "⏭", "hold": "⏳"}
        label = {"publish": "yazılıyor", "update": "güncelleme", "merge": "kaynak eklendi", "skip": "elendi", "hold": "bekliyor"}
        lines = ["🧭 <b>Yayın yönetmeni — son kararlar</b>"]
        for x in reversed(lg[-20:]):
            why = f" — {esc(x['reason'])}" if x.get("reason") else ""
            lines.append(f"{icon.get(x['action'], '•')} <b>{x.get('score', 0)}</b>/10 {esc(clip(x.get('topic', ''), 70))} "
                         f"<i>({label.get(x['action'], x['action'])}{why})</i>")
        today = [x for x in lg if (x.get("t") or "")[:10] == iso(now_utc())[:10]]
        if today:
            n = {k: sum(1 for x in today if x["action"] == k) for k in ("publish", "update", "skip")}
            lines.append(f"\nBugün: {n['publish']} seçildi, {n['update']} güncelleme, {n['skip']} elendi")
        return "\n".join(lines)

    def status_text(self) -> str:
        t = self.today()
        c = self.state.get("day_counts", {}).get(t, {})
        n, rate = policy.global_rate(self.cfg, self.stats)
        mode = policy.MODES[policy.current_mode(self.cfg, self.state)]
        pend = len(self.store.drafts("pending"))
        bad = [k for k, v in self.state.get("source_health", {}).items() if v.get("fails", 0) >= 3]
        lines = [
            f"📊 <b>Durum</b> — {esc(tr_date(now_utc(), self.cfg.tz))}",
            f"Mod: <b>{mode}</b>{' · ⏸ DURAKLATILDI' if self.state.get('paused') else ''}",
            f"Bugün: {c.get('published', 0)} yayın ({c.get('auto', 0)} otomatik, {c.get('approved', 0)} onayla), "
            f"{c.get('rejected', 0)} ret, {c.get('drafts', 0)} taslak",
            f"Onay bekleyen: {pend} · Yazılmak için sırada: {len(self.state.get('queue') or [])}",
            f"Son {n} kararda onay oranı: %{rate * 100:.0f}",
            f"Toplam yayın: {len(self.store.posts())}",
            f"Bugünkü tahmini maliyet: ${self._cost(c):.2f} ({c.get('images', 0)} görsel)",
            f"Son tarama: {esc(tr_date(self.state.get('last_collect'), self.cfg.tz)) or '—'}",
            f"Site: {esc(self.cfg.site_url)}",
        ]
        if self.cfg.instagram_token:
            q = len(self.state.get("ig_queue") or [])
            lines.append(f"Instagram: {c.get('instagram', 0)} paylaşım · sırada {q}"
                         f"{' · ⏸ kapalı' if self.state.get('ig_off') else ''}")
        if bad:
            lines.append("⚠️ Okunamayan kaynaklar: " + esc(", ".join(bad)))
        return "\n".join(lines)

    def sources_text(self) -> str:
        names = [s["name"] for s in self.cfg.sources]
        health = self.state.get("source_health", {})
        broken = [n for n in names if health.get(n, {}).get("fails", 0) >= 3]
        lines = [f"📡 <b>{len(names)} kaynak</b> · {len(names) - len(broken)} okunuyor"
                 + (f" · ⚠️ okunamayan: {esc(', '.join(broken))}" if broken else ""),
                 "", "🧭 <b>Kaynak güveni</b> (✅ = otomatik yayına uygun; yalnızca karar verdiğin kaynaklar)"]
        rows = []
        for name in names:
            ok, n, rate = policy.source_trust(self.cfg, self.stats, name)
            if n:
                rows.append((not ok, -n, f"{'✅' if ok else '▫️'} {esc(name)}: {n} karar, %{rate * 100:.0f} onay"))
        lines += [r[2] for r in sorted(rows)[:40]] or ["Henüz karar yok."]
        need = self.cfg.get("autonomy", "source_min_decisions", 10)
        pct = self.cfg.get("autonomy", "source_min_approval", 0.9) * 100
        lines.append(f"\nGüven için: en az {need} karar ve %{pct:.0f} onay.")
        return "\n".join(lines)[:4000]

    # ── bakım ───────────────────────────────────────────────
    def expire(self) -> None:
        st = self.store
        limit = self.cfg.get("editorial", "pending_expire_hours", 36)
        for d in st.drafts():
            if d.get("status") == "pending" and hours_since(d.get("created_at")) > limit:
                self._update_preview(d, "expired")
                st.bump(self.today(), "expired")
                st.archive_draft(d, "expired")
            elif d.get("status") == "rejected" and hours_since(d.get("rejected_at")) > 24:
                st.archive_draft(d, "rejected")

    URL_V = 1

    def migrate_urls(self) -> None:
        """Tek seferlik: otomotiv kategorisi ve yeni adres yapısı (kategori/yıl/ay/slug).

        Araba haberleri otomotive taşınır; her habere kalıcı adres yazılır, eski /haber/slug/ adresi yeni adrese yönlenir."""
        st = self.state
        if st.get("url_v") == self.URL_V:
            return
        moved = 0
        for p in self.store.posts():
            if p.get("category") in ("teknoloji", "inovasyon") and is_car_story(p):
                p["category"] = "otomotiv"
                moved += 1
            if not p.get("path"):
                p["path"] = self.cfg.post_path(p)
                self.queue_indexnow(self.cfg.post_url(p))
            self.store.save_post(p)
        for d in self.store.drafts("pending"):
            if d.get("category") in ("teknoloji", "inovasyon") and is_car_story(d):
                d["category"] = "otomotiv"
                self.store.save_draft(d)
        st["url_v"] = self.URL_V
        self.store.site_dirty = True
        log.info("Yeni adres yapısı: tüm haberlere kalıcı adres yazıldı, %d haber otomotive taşındı", moved)

    def more_photos(self, per_run: int = 3) -> None:
        """Tek seferlik: son 6 habere daha çok fotoğraf (haberin içine paragraf paragraf yerleşir)."""
        if self.cfg.mock or self.cfg.fixtures_dir or not self.cfg.get("images", "photos", True):
            return
        done = self.state.setdefault("more_photos", [])
        if len(done) >= 6:
            return
        for p in self.store.posts()[:6]:
            if p["id"] in done or per_run <= 0:
                continue
            done.append(p["id"])
            per_run -= 1
            if p.get("photos_removed") or (p.get("image") or {}).get("source") == "ai":
                continue
            if self._attach_photos(p, draft=False):
                log.info("Daha çok fotoğraf: %s (%d)", p["id"], len(p["photos"]))
                self.store.save_post(p)

    def reselect_pending(self) -> None:
        """Seçki ölçütleri değişince (tek seferlik): onay bekleyen yığını yeni ölçütlerle yeniden elden geçir;
        geniş okur kitlesine hitap etmeyenler "seçki dışı" olarak arşivlenir."""
        st = self.state
        if st.get("reselect_v") == RESELECT_V or not self.llm:
            return
        pend = [d for d in self.store.drafts("pending") if not d.get("update_of")]
        if len(pend) <= 5 or int(st.get("reselect_try", 0)) >= 3:
            st["reselect_v"] = RESELECT_V
            return
        st["reselect_try"] = int(st.get("reselect_try", 0)) + 1
        cfg = self.cfg
        min_score = int(cfg.get("editorial", "min_must_read", 8))
        keep_max = int(cfg.get("editorial", "daily_target", 20) or 20)
        covered = [c for c in self._covered(48) if c["status"] != "pending"]
        scores: dict[str, tuple[str, int, str]] = {}
        for i in range(0, len(pend), 45):
            chunk = pend[i:i + 45]
            cands = [{"cid": f"c{n + 1}", "category": d.get("category", ""), "importance": d.get("importance", 0),
                      "entities": list(d.get("entities") or (d.get("tags") or [])[:2]), "topic": d.get("title", ""),
                      "dup": "", "headlines": [clip(d.get("summary", ""), 200)]} for n, d in enumerate(chunk)]
            try:
                out = self.llm.json(cfg.get("ai", "editor_model", None) or cfg.get("ai", "writer_model", "gemini-flash-latest"),
                                    edit_system(self.brand, min_score),
                                    edit_user(local(now_utc(), cfg.tz).strftime("%Y-%m-%d %H:%M"), keep_max, 0, keep_max,
                                              covered[:90], cands), EDIT_SCHEMA, max_tokens=8000)
            except LLMError as e:
                log.warning("Bekleyen taslaklar yeniden seçilemedi (sonra denenecek): %s", str(e)[:160])
                return
            for x in out.get("decisions") or []:
                cid = str(x.get("cid") or "")
                if cid.startswith("c") and cid[1:].isdigit() and 0 < int(cid[1:]) <= len(chunk):
                    try:
                        mr = max(0, min(10, int(x.get("must_read") or 0)))
                    except (TypeError, ValueError):
                        mr = 0
                    scores[chunk[int(cid[1:]) - 1]["id"]] = (str(x.get("action") or ""), mr, clip(str(x.get("reason") or ""), 120))
        good = sorted((d for d in pend if d["id"] in scores and scores[d["id"]][0] in ("publish", "hold")
                       and scores[d["id"]][1] >= min_score), key=lambda d: -scores[d["id"]][1])
        keep = {d["id"] for d in good[:keep_max]} | {d["id"] for d in pend if d["id"] not in scores}
        culled = 0
        for d in pend:
            if d["id"] in keep:
                continue
            act, mr, why = scores[d["id"]]
            d["editor_note"] = clip(f"Seçki dışı: {why or f'önem {mr}/10'}", 140)
            self._update_preview(d, "culled")
            self.store.bump(self.today(), "culled")
            self.store.archive_draft(d, "expired")
            self._edit_log({"story": {"topic": d.get("title", "")}}, "skip",
                           {"must_read": mr, "reason": "yığın temizliği: " + why})
            culled += 1
            if not cfg.mock:
                time.sleep(0.4)   # Telegram hız sınırı
        st["reselect_v"] = RESELECT_V
        log.info("Bekleyen taslaklar yeni ölçütlerle elden geçirildi: %d kaldı, %d seçki dışı", len(pend) - culled, culled)
        if culled:
            self.notify(f"🧹 <b>Seçki daraltıldı</b>\nOnay bekleyen {len(pend)} haberden geniş okura hitap etmeyen {culled} "
                        f"tanesi elendi; {len(pend) - culled} haber onayında. Bundan sonra günde yaklaşık "
                        f"{self._daily_target()} haber gelecek (çok büyük haberler hedefi aşabilir).", silent=True)

    # ── ARAMA MOTORLARI ─────────────────────────────────────
    def queue_indexnow(self, url: str) -> None:
        q = self.state.setdefault("indexnow_queue", [])
        if url not in q:
            q.append(url)

    def flush_indexnow(self) -> None:
        """Önceki turda yayınlanan adresleri Bing/Yandex'e bildir (IndexNow). Site o arada yayına girmiş olur."""
        q = self.state.get("indexnow_queue") or []
        if not q or self.cfg.mock or not (self.cfg.raw.get("seo") or {}).get("indexnow", True):
            return
        site = self.cfg.site_url
        if "localhost" in site:
            return
        key = indexnow_key(site)
        urls = list(dict.fromkeys(q + [site + "/"]))[:500]
        try:
            r = requests.post("https://api.indexnow.org/indexnow", timeout=20, json={
                "host": urlsplit(site).netloc, "key": key, "keyLocation": f"{site}/{key}.txt", "urlList": urls})
            log.info("IndexNow: %d adres bildirildi (HTTP %s)", len(urls), r.status_code)
            if r.status_code < 300 or r.status_code in (400, 403, 422):
                self.state["indexnow_queue"] = []
        except requests.RequestException as e:
            log.warning("IndexNow bildirimi başarısız: %s", e)

    def backfill_seo(self, limit: int = 3) -> None:
        """SEO bilgisi olmayan eski haberlere (metnine dokunmadan) arama başlığı ve açıklaması ekle."""
        if not self.llm:
            return
        todo = [p for p in self.store.posts() if not p.get("seo_title") and not p.get("seo_skip")][:limit]
        for p in todo:
            try:
                out = self.llm.json(self.cfg.get("ai", "triage_model", "gemini-flash-lite-latest"),
                                    seo_system(self.brand), seo_user(p), SEO_SCHEMA, max_tokens=2000)
            except LLMError as e:
                log.warning("SEO bilgisi üretilemedi (%s): %s", p["id"], e)
                p["seo_tries"] = int(p.get("seo_tries", 0)) + 1
                if p["seo_tries"] >= 3:
                    p["seo_skip"] = True
                self.store.save_post(p)
                return
            p["focus_keyword"] = clip((out.get("focus_keyword") or "").strip(), 60)
            p["seo_title"] = clip((out.get("seo_title") or "").strip().rstrip("."), 62) or p.get("short_title") or p["title"]
            p["meta_description"] = clip((out.get("meta_description") or "").strip(), 170)
            p["image_alt"] = clip((out.get("image_alt") or "").strip(), 125)
            tags = [clip(t, 30) for t in (out.get("tags") or []) if t and t.strip()][:6]
            if len(tags) >= 2:
                p["tags"] = tags
            self.store.save_post(p)
            self.store.site_dirty = True
            self.queue_indexnow(self.cfg.post_url(p))
            log.info("SEO bilgisi eklendi: %s → %s", p["id"], p["seo_title"])

    def refresh_covers(self, limit: int = 30) -> None:
        """Kapak tasarımı değişince yayındaki haberlerin görsellerini yeniden üret (yapay zeka görsellerine dokunmaz)."""
        if (self.cfg.get("images", "style", "kapak") or "kapak") != "kapak":
            return
        todo = [p for p in self.store.posts()
                if (p.get("image") or {}).get("source") in ("cover", "fallback", None)
                and (p.get("image") or {}).get("cover_v") != COVER_VERSION and self._cover_ready(p)][:limit]
        for p in todo:
            try:
                p["image"] = {**self.vis.make_hero(p, self.store.post_image(p["id"])), "cover_v": COVER_VERSION}
                self._make_og(p)
                self.store.save_post(p)
            except Exception as e:  # noqa: BLE001
                log.warning("Kapak yenilenemedi (%s): %s", p["id"], e)
                return
        if todo:
            log.info("Kapak yenilendi: %d haber", len(todo))

    def maybe_summary(self) -> None:
        now_l = local(now_utc(), self.cfg.tz)
        hour = self.cfg.get("schedule", "daily_summary_hour", 21)
        t = self.today()
        if hour is None or now_l.hour < hour or self.state.get("last_summary_date") == t:
            return
        self.state["last_summary_date"] = t
        c = self.state.get("day_counts", {}).get(t, {})
        if not any(c.get(k) for k in ("drafts", "published")):
            return
        text = (f"🌙 <b>Günün özeti</b>\n"
                f"Yayın: {c.get('published', 0)} ({c.get('auto', 0)} otomatik, {c.get('approved', 0)} senin onayınla)\n"
                f"Güncellenen haber: {c.get('updated', 0)}\n"
                f"Ret: {c.get('rejected', 0)} · Süresi dolan: {c.get('expired', 0)} · Kaldırılan: {c.get('removed', 0)}\n"
                f"Seçki: {sum(1 for x in self.state.get('edit_log') or [] if (x.get('t') or '')[:10] == iso(now_utc())[:10] and x['action'] == 'skip')} "
                f"aday elendi (/secki)\n"
                f"Instagram: {c.get('instagram', 0)} paylaşım\n"
                f"Tahmini maliyet: ${self._cost(c):.2f} ({c.get('images', 0)} yapay zeka görseli)\n"
                f"Mod: {policy.MODES[policy.current_mode(self.cfg, self.state)]}")
        self.notify(text, silent=True)

    def listen(self, seconds: int) -> None:
        if not self.tg or seconds <= 0 or self.cfg.mock:
            return
        deadline = time.time() + seconds
        while time.time() < deadline - 3:
            if not self._should_listen():
                break
            self.process_updates(timeout=int(min(25, deadline - time.time())))
            if self.force_collect and not self.state.get("paused"):
                self.force_collect = False
                self.collect()

    def _should_listen(self) -> bool:
        """Telegram'ı her turda canlı dinle (gece de): düğmeler beklemeden işlensin."""
        return True

    # ── 5) INSTAGRAM ────────────────────────────────────────
    def _ig_cfg(self, key: str, default):
        return self.cfg.get("social", key, default)

    @property
    def ig_enabled(self) -> bool:
        return self.cfg.instagram_auto and not self.state.get("ig_off")

    def _ig_kinds(self) -> list[str]:
        return list(self.vis.CAROUSEL) if self.vis.summary_style else ["post"]

    def _ig_urls(self, post: dict) -> dict:
        base = f"{self.cfg.site_url}/ig/{post['id']}"
        return {k: f"{base}-{k}.jpg" for k in self._ig_kinds() + ["story"]}

    def _ig_msg(self, it: dict, text: str, keyboard=None) -> None:
        if not (self.tg and self.chat_id):
            return
        if it.get("mid"):
            self.tg.edit_text(self.chat_id, it["mid"], text, keyboard)
        else:
            try:
                it["mid"] = self.tg.send_message(self.chat_id, text, keyboard, silent=True).get("message_id")
            except TelegramError as e:
                log.warning("Instagram bildirimi gönderilemedi: %s", e)

    def ig_enqueue(self, post: dict, mid: int | None = None) -> bool:
        """Yayınlanan haberi Instagram sırasına ekler (kartlar site yayınlanırken _site/ig/ altına konur)."""
        q = self.state.setdefault("ig_queue", [])
        done = {x.get("id") for x in self.state.get("ig_done") or []}
        if post["id"] in done or any(x["id"] == post["id"] for x in q):
            return False
        it = {"id": post["id"], "queued_at": iso(now_utc()), "tries": 0}
        if mid:
            it["mid"] = mid
        q.append(it)
        self.store.site_dirty = True
        where = "" if not self.state.get("ig_off") else " (Instagram şu an kapalı: /instagram ac)"
        self._ig_msg(it, f"📸 <b>Instagram sırasında</b>{where}\n{esc(post['title'])}\n"
                         f"<i>Carousel ve hikâye birkaç dakika içinde paylaşılacak.</i>",
                     [[{"text": "🚫 Instagram'a gönderme", "callback_data": f"x:{post['id']}"}]])
        return True

    def _ig_drop(self, did: str, note: str = "", cancelled: bool = False) -> bool:
        q = self.state.get("ig_queue") or []
        it = next((x for x in q if x["id"] == did), None)
        if not it:
            return False
        q.remove(it)
        if cancelled:
            post = self.store.load_post(did) or {}
            self._ig_msg(it, f"🚫 <b>Instagram'a gönderilmeyecek</b>\n{esc(post.get('title', ''))}",
                         [[{"text": "↩️ Yine de paylaş", "callback_data": f"q:{did}"}]])
        elif note:
            self._ig_msg(it, note)
        return True

    def _ig_problem(self, text: str) -> None:
        """Aynı uyarıyı en fazla 12 saatte bir gönder."""
        if hours_since(self.state.get("ig_warned_at")) >= 12:
            self.state["ig_warned_at"] = iso(now_utc())
            self.notify("⚠️ <b>Instagram</b>: " + text)
        log.warning("Instagram: %s", re.sub(r"<[^>]+>", "", text))

    def _ig_client(self):
        """Anahtarı (gerekirse yenileyip) hazırlar, hesabı tanır. Sorun varsa None."""
        if self._ig is not None:
            return self._ig or None
        self._ig = False
        secret = self.cfg.instagram_token
        data = self.store.ig
        ts = TokenStore(secret, data)
        if ts.refresh_due():
            try:
                tok, exp = Instagram(ts.token).refresh()
                ts.save(tok, exp)
                data.pop("refresh_tried_at", None)
                log.info("Instagram anahtarı yenilendi (%d gün)", exp // 86400)
            except InstagramError as e:
                data["refresh_tried_at"] = iso(now_utc())
                log.info("Instagram anahtarı şimdilik yenilenemedi: %s", e)
        left = ts.days_left()
        if left is not None and left < 5:
            self._ig_problem(f"erişim anahtarının süresi {max(0, left):.0f} gün içinde doluyor ve yenilenemedi. "
                             "Meta geliştirici panelinden yeni anahtar üretip GitHub'da <b>IG_ACCESS_TOKEN</b> değerini güncelle.")
        cli = Instagram(ts.token, self._ig_cfg("instagram_api_version", None) or "v25.0")
        fp = fingerprint(secret)
        if data.get("me_fp") != fp or not data.get("id"):
            try:
                me = cli.me()
            except InstagramError as e:
                if e.auth:
                    self._ig_problem(f"erişim anahtarı çalışmıyor ({esc(e)}). Yeni anahtar üretip GitHub'da "
                                     "<b>IG_ACCESS_TOKEN</b> değerini güncelle.")
                else:
                    log.warning("Instagram hesabı okunamadı: %s", e)
                return None
            data.update({"me_fp": fp, "id": str(me.get("id") or ""), "user_id": str(me.get("user_id") or ""),
                         "username": me.get("username", "")})
            data.pop("target", None)
            if self.tg and self.chat_id:
                self.notify(f"📸 Instagram bağlandı: <b>@{esc(data['username'])}</b>. Yayınlanan haberler buraya "
                            f"carousel ve hikâye olarak paylaşılacak.", silent=True)
        self._ig = cli
        return cli

    def _ig_targets(self) -> list[str]:
        d = self.store.ig
        if d.get("target"):
            return [d["target"]]
        return [t for t in dict.fromkeys(["me", d.get("user_id"), d.get("id")]) if t]

    def _ig_run(self, fn, *a):
        """Paylaşım hedefini (me / hesap numarası) dener, çalışanı hatırlar."""
        last = None
        for t in self._ig_targets():
            try:
                res = fn(t, *a)
                self.store.ig["target"] = t
                return res
            except InstagramError as e:
                last = e
                if e.auth or e.transient or e.code not in (100, 3, 803):
                    raise
        raise last  # type: ignore[misc]

    def ig_tick(self) -> None:
        """Sıradaki haberi (kartları sitede yayındaysa) Instagram'da paylaşır. Her turda en fazla bir haber."""
        if not self.cfg.instagram_auto or self.state.get("paused"):
            return
        q = self.state.setdefault("ig_queue", [])
        max_wait = float(self._ig_cfg("instagram_max_wait_hours", 12) or 12)
        for it in list(q):
            post = self.store.load_post(it["id"])
            if not post:
                q.remove(it)
            elif hours_since(it["queued_at"]) > max_wait:
                self._ig_drop(it["id"], f"⌛ <b>Instagram'a gönderilmedi</b> ({max_wait:.0f} saatten uzun sırada kaldı)\n"
                                        f"{esc(post['title'])}")
        if not q or self.state.get("ig_off"):
            return
        now_l = local(now_utc(), self.cfg.tz)
        a, b = (self._ig_cfg("instagram_hours", IG_WINDOW_DEFAULT) or [0, 24])[:2]
        if not (a <= now_l.hour + now_l.minute / 60 < b):
            return
        gap = float(self._ig_cfg("instagram_min_gap_minutes", 15) or 0)
        if hours_since(self.state.get("ig_last_at")) * 60 < gap:
            return
        cap = int(self._ig_cfg("instagram_max_per_day", 0) or 0)
        if cap and self.store.count(self.today(), "instagram") >= cap:
            return
        it = q[0]
        post = self.store.load_post(it["id"])
        urls = self._ig_urls(post)
        code = head_ok(urls["post"])
        if code != 200:
            waited = hours_since(it["queued_at"]) * 60
            if waited > 15 and hours_since(it.get("restaged_at")) * 60 > 30:
                it["restaged_at"] = iso(now_utc())
                self.store.site_dirty = True  # site yeniden yayınlansın, kartlar eklensin
                log.info("Instagram kartı sitede yok (HTTP %s); site yeniden yayınlanacak", code)
            return
        cli = self._ig_client()
        if not cli:
            return
        try:
            if not it.get("media_id"):
                caption = clip(self.instagram_caption(post), 2150)
                mid, link = self._ig_run(cli.carousel, [urls[k] for k in self._ig_kinds()], caption)
                it.update({"media_id": mid, "permalink": link})
                self.state["ig_last_at"] = iso(now_utc())
                self.store.bump(self.today(), "instagram")
        except InstagramError as e:
            if e.auth:
                self._ig_problem(f"paylaşım yapılamadı: {esc(e)}. Anahtarın <b>instagram_business_content_publish</b> "
                                 "izni olduğundan emin ol.")
                return
            it["tries"] = it.get("tries", 0) + (0 if e.transient else 1)
            it["last_error"] = str(e)[:300]
            log.warning("Instagram paylaşımı başarısız (%s): %s", post["id"], e)
            if it["tries"] >= 3:
                self._ig_drop(it["id"], f"⚠️ <b>Instagram'da paylaşılamadı</b>\n{esc(post['title'])}\n<i>{esc(e)}</i>")
            return
        if self._ig_cfg("instagram_story", True) and not it.get("story_id"):
            try:
                it["story_id"] = self._ig_run(cli.story, urls["story"])
            except InstagramError as e:  # hikâye olmasa da gönderi paylaşıldı; sırayı tıkama
                log.warning("Instagram hikâyesi paylaşılamadı (%s): %s", post["id"], e)
                it["story_error"] = str(e)[:200]
        q.remove(it)
        done = self.state.setdefault("ig_done", [])
        done.append({"id": post["id"], "at": iso(now_utc()), "permalink": it.get("permalink", ""),
                     "story": bool(it.get("story_id"))})
        self.state["ig_done"] = done[-200:]
        story = " + hikâye" if it.get("story_id") else (", hikâye paylaşılamadı" if it.get("story_error") else "")
        kb = [[{"text": "📸 Instagram'da aç", "url": it["permalink"]}]] if it.get("permalink") else None
        self._ig_msg(it, f"✅ <b>Instagram'da paylaşıldı</b> (carousel{story})\n{esc(post['title'])}", kb)
        log.info("Instagram'da paylaşıldı: %s %s", post["id"], it.get("permalink", ""))

    def stage_instagram(self, out) -> int:
        """Sıradaki haberlerin Instagram kartlarını sitenin ig/ klasörüne koyar (Instagram herkese açık adresten alır)."""
        q = self.state.get("ig_queue") or []
        if not (q and self.cfg.instagram_auto):
            return 0
        folder = out / "ig"
        folder.mkdir(parents=True, exist_ok=True)
        n = 0
        for it in q[:8]:
            post = self.store.load_post(it["id"])
            if not post:
                continue
            for k in self._ig_kinds() + ["story"]:
                try:
                    shutil.copyfile(self._card(post, k), folder / f"{post['id']}-{k}.jpg")
                    n += 1
                except Exception as e:  # noqa: BLE001
                    log.warning("Instagram kartı hazırlanamadı (%s %s): %s", post["id"], k, e)
        if self._vis:
            self._vis.close()
            self._vis = None
        log.info("Instagram kartları siteye kondu: %d görsel", n)
        return n

    def instagram_status(self) -> str:
        if not self.cfg.instagram_token:
            return ("📸 <b>Instagram</b> henüz bağlı değil.\nGitHub'da <b>IG_ACCESS_TOKEN</b> gizli anahtarı eklenince "
                    "yayınlanan her haber otomatik paylaşılır.")
        d = self.store.ig
        c = self.state.get("day_counts", {}).get(self.today(), {})
        left = TokenStore(self.cfg.instagram_token, d).days_left()
        lines = [f"📸 <b>Instagram</b> {'⏸ kapalı' if self.state.get('ig_off') else '▶️ açık'}"
                 f"{' · @' + esc(d['username']) if d.get('username') else ''}",
                 f"Bugün: {c.get('instagram', 0)} paylaşım · Sırada: {len(self.state.get('ig_queue') or [])}"]
        a, b = (self._ig_cfg("instagram_hours", IG_WINDOW_DEFAULT) or [0, 24])[:2]
        lines.append(f"Paylaşım saatleri: {a:02d}:00–{b:02d}:00 · en az {self._ig_cfg('instagram_min_gap_minutes', 15)} dk arayla")
        if left is not None:
            lines.append(f"Anahtar: {left:.0f} gün geçerli (bot kendisi yeniler)")
        for x in (self.state.get("ig_done") or [])[-3:][::-1]:
            p = self.store.load_post(x["id"]) or {}
            if x.get("permalink"):
                lines.append(f'• <a href="{esc(x["permalink"])}">{esc(clip(p.get("title", x["id"]), 70))}</a>')
        lines.append("Durdur: <code>/instagram kapat</code> · Aç: <code>/instagram ac</code>")
        return "\n".join(lines)

    # ── manşet yönetimi (/manset) ───────────────────────────
    def _manset_posts(self) -> list[dict]:
        """Son 3 günün yayınları (en fazla 12), en yeni önce."""
        return [p for p in self.store.posts() if hours_since(p.get("published_at")) <= 72][:12]

    def _manset_text(self) -> str:
        from .site import hot
        n = int((self.cfg.raw.get("home") or {}).get("featured_count") or 10)
        ranked = sorted((p for p in self.store.posts() if hot(p) >= 0), key=lambda p: -hot(p))[:n]
        lines = [f"⭐ <b>Manşet</b> (sitede şu an ilk {n}):"]
        for i, p in enumerate(ranked, 1):
            pin = " 📌" if p.get("home") == "pin" else ""
            lines.append(f"{i}. {esc(clip(p.get('short_title') or p['title'], 60))}{pin}")
        lines += ["", "Aşağıdaki son haberlerden birine bas: ⭐ manşete alır (36 saat en başta), 📌 olanı manşetten çıkarır."]
        return "\n".join(lines)

    def _manset_keyboard(self) -> list[list[dict]]:
        rows = []
        for p in self._manset_posts():
            mark = "📌" if p.get("home") == "pin" else "🙈" if p.get("home") == "hide" else "⭐"
            rows.append([{"text": f"{mark} {clip(p.get('short_title') or p['title'], 48)}", "callback_data": f"m:{p['id']}"}])
        return rows

    def refresh_keyboards(self) -> None:
        """Düğmeler değişince son 3 günün yayın mesajlarına yeni düğmeleri bir kez ekle."""
        if not (self.tg and self.chat_id) or self.state.get("keyboard_v") == KEYBOARD_VERSION:
            return
        self.state["keyboard_v"] = KEYBOARD_VERSION
        n = 0
        for p in self.store.posts():
            if hours_since(p.get("published_at")) > 72:
                break
            if (p.get("telegram") or {}).get("message_id"):
                self._update_preview(p, "auto" if p.get("publish_mode") == "auto" else "published")
                n += 1
        for d in self.store.drafts("pending"):
            if (d.get("telegram") or {}).get("message_id"):
                self._update_preview(d, "pending")
                n += 1
        log.info("Telegram düğmeleri yenilendi: %d mesaj", n)

    # ── gerçek fotoğraflar ──────────────────────────────────
    # Düzen: fotoğraflar {id}-g0.webp, {id}-g1.webp … ; {id}.webp her zaman tasarımlı kapaktır:
    # anlamlı bir fotoğraf varsa fotoğraflı kapak, yoksa (ya da cover_mode "type" ise) tipografik kapak.
    PHOTOS_V = 2
    COVER_MIN_W = 900          # kapak için en az bu genişlikte gerçek fotoğraf gerekir

    def _visual_buttons(self, d: dict) -> list[dict]:
        did = d["id"]
        if not d.get("photos"):
            return [{"text": "🎨 Yeni görsel", "callback_data": f"v:{did}"}]
        good = [r for r in d["photos"] if r.get("file") and not r.get("graphic")]
        out = []
        if d.get("cover_mode") == "type" and any(self._coverable(r) for r in good):
            out.append({"text": "🖼 Fotoğraflı kapak", "callback_data": f"g:{did}"})
        elif sum(self._coverable(r) for r in good) > 1:
            out.append({"text": "🖼 Başka foto", "callback_data": f"g:{did}"})
        photo_cover = (d.get("image") or {}).get("source") == "photo"
        out.append({"text": "🎨 Yazılı kapak" if photo_cover else "🎨 Yeni kapak", "callback_data": f"v:{did}"})
        out.append({"text": "🚫 Fotoğrafsız", "callback_data": f"n:{did}"})
        return out

    def _photo_dir(self, draft: bool):
        return self.cfg.drafts_dir if draft else self.cfg.images_dir

    def _no_cover_sources(self) -> set[str]:
        """Paylaşım görseline yazı basan kaynaklar (ayarlarda photo_cover: false)."""
        return {x.get("name") for x in self.cfg.sources if x.get("photo_cover") is False}

    def _coverable(self, r: dict) -> bool:
        """Kapak olabilecek fotoğraf: gerçek fotoğraf, düz zeminli tanıtım görseli değil, yeterince büyük."""
        return bool(r.get("file")) and not r.get("graphic") and r.get("cover_ok", True) and (r.get("w") or 0) >= self.COVER_MIN_W

    def _cover_photo(self, d: dict, folder) -> dict | None:
        if d.get("cover_mode") == "type":
            return None
        return next((r for r in d.get("photos") or [] if self._coverable(r) and (folder / r["file"]).exists()), None)

    def _build_cover(self, d: dict, draft: bool) -> None:
        """Kapağı ({id}.webp) üret: fotoğraflı kapak ya da tipografik kapak."""
        folder = self._photo_dir(draft)
        hero = folder / f"{d['id']}.webp"
        r = self._cover_photo(d, folder)
        if r:
            try:
                self.vis.photo_cover(d, folder / r["file"], hero)
                d["image"] = {"source": "photo", "photo": r["file"], "credit": r.get("credit", ""),
                              "page": r.get("page", ""), "src": r.get("src", ""), "layout": photo_design(d)["layout"],
                              "cover_v": PHOTO_COVER_VERSION}
                return
            except Exception as e:  # noqa: BLE001
                log.warning("Fotoğraflı kapak üretilemedi (%s), yazılı kapak kullanılacak: %s", d.get("id"), e)
        d["image"] = self.vis.make_hero(d, hero)

    def _attach_photos(self, d: dict, draft: bool) -> bool:
        """Kaynaklardan gerçek fotoğrafları al ve kapağı üret. Bulunamazsa False."""
        cfg = self.cfg
        if not cfg.get("images", "photos", True) or cfg.mock or cfg.fixtures_dir:
            return False
        try:
            got = photos.gather(d.get("sources") or [], limit=int(cfg.get("images", "photo_limit", 16) or 16),
                                per_source=int(cfg.get("images", "photos_per_source", 12) or 12),
                                skip_cover=self._no_cover_sources())
        except Exception as e:  # noqa: BLE001
            log.warning("Fotoğraflar alınamadı (%s): %s", d.get("id"), e)
            return False
        if not got:
            return False
        folder = self._photo_dir(draft)
        for f in self.store.gallery_files(d["id"], draft):
            f.unlink(missing_ok=True)
        # İlk birkaç fotoğraf siteye kopyalanır (kapak, Telegram, Instagram bunlardan); kalanlar haberin içinde
        # kaynaktaki adresinden gösterilir (depo ve site boyutu şişmesin).
        keep = int(cfg.get("images", "photo_local", 4) or 4)
        recs = []
        for i, p in enumerate(got):
            rec = {"src": p["src"], "credit": p["credit"], "page": p["page"], "alt": p["alt"], "kind": p.get("kind", ""),
                   "graphic": bool(p.get("graphic")), "cover_ok": bool(p.get("cover_ok", not p.get("graphic")))}
            if len([r for r in recs if r.get("file")]) < keep:
                name = f"{d['id']}-g{len([r for r in recs if r.get('file')])}.webp"
                w, h = photos.save_webp(p["image"], folder / name, 1600, 80 if p.get("graphic") else 78)
                rec["file"] = name
            else:
                w, h = p["image"].size
                rec["remote"] = True
            rec.update({"w": w, "h": h})
            recs.append(rec)
        d["photos"] = recs
        d["photos_v"] = self.PHOTOS_V
        d.pop("cover_mode", None)
        self._build_cover(d, draft)
        if not draft:
            self._make_og(d)
        return True

    def _reorder_photos(self, d: dict, where: str, order: list[dict]) -> None:
        """Fotoğraf sırasını değiştir (dosyalar yeniden adlandırılır, yeniden sıkıştırılmaz) ve kapağı yenile."""
        draft = where == "draft"
        folder = self._photo_dir(draft)
        remote = [r for r in d.get("photos") or [] if not r.get("file")]
        moved = []
        for i, rec in enumerate(order):
            f = folder / rec["file"] if rec.get("file") else None
            if f and f.exists():
                t = folder / f"{d['id']}-t{i}.webp"
                f.rename(t)
                moved.append((dict(rec), t))
        for f in self.store.gallery_files(d["id"], draft):
            f.unlink(missing_ok=True)
        recs = []
        for rec, t in moved:
            rec["file"] = f"{d['id']}-g{len(recs)}.webp"
            t.rename(folder / rec["file"])
            recs.append(rec)
        d["photos"] = recs + remote
        d["photos_v"] = self.PHOTOS_V
        self._build_cover(d, draft)

    def _drop_photos(self, d: dict, where: str) -> None:
        for f in self.store.gallery_files(d["id"], where == "draft"):
            f.unlink(missing_ok=True)
        d.pop("photos", None)
        d.pop("cover_mode", None)
        d["photos_removed"] = True
        d["image"] = {"source": "cover"}

    def _make_og(self, p: dict) -> None:
        """Paylaşım görseli: fotoğraflı kapak (logo, kategori ve fotoğraf kredisiyle) ya da özet kartı."""
        st = self.store
        img = p.get("image") or {}
        photo = self.cfg.images_dir / img["photo"] if img.get("source") == "photo" and img.get("photo") else None
        if photo is not None and photo.exists():
            try:
                self.vis.photo_cover(p, photo, st.post_og(p["id"]), size=(1200, 630), brand=True, kicker=True,
                                     credit=img.get("credit", ""))
                return
            except Exception as e:  # noqa: BLE001
                log.warning("Fotoğraflı paylaşım görseli üretilemedi (%s): %s", p["id"], e)
                from PIL import Image
                photos.og_crop(Image.open(photo).convert("RGB"), st.post_og(p["id"]))
                return
        self.vis.render_card(p, "og", st.post_image(p["id"]), st.post_og(p["id"]))

    def _migrate_photos(self, p: dict) -> None:
        """Eski düzen (ilk fotoğraf {id}.webp) → yeni düzen ({id}-gN.webp, grafik/fotoğraf ayrımı).

        Paylaşım görseline yazı basan kaynakların (photo_cover: false) ilk fotoğrafı o kaynağın paylaşım
        görseliydi; o fotoğraf atılır.
        """
        from PIL import Image
        folder, pid = self.cfg.images_dir, p["id"]
        no_cover, seen, keep = self._no_cover_sources(), set(), []
        for r in p.get("photos") or []:
            c = r.get("credit")
            if c in no_cover and c not in seen:
                seen.add(c)
                continue
            seen.add(c)
            keep.append(dict(r))
        tmp = []
        for i, r in enumerate(keep):
            f = folder / r["file"] if r.get("file") else None
            if f and f.exists():
                t = folder / f"{pid}-t{i}.webp"
                f.rename(t)
                with Image.open(t) as im:
                    r.update(photos.classify(im.convert("RGB")))
                    r["w"], r["h"] = im.size
                tmp.append((r, t))
        for f in self.store.gallery_files(pid, draft=False):
            f.unlink(missing_ok=True)
        tmp.sort(key=lambda x: bool(x[0]["graphic"]))
        recs = []
        for r, t in tmp:
            r["file"] = f"{pid}-g{len(recs)}.webp"
            t.rename(folder / r["file"])
            recs.append(r)
        if recs:
            p["photos"] = recs
        else:
            p.pop("photos", None)
        p["photos_v"] = self.PHOTOS_V

    def upgrade_photos(self, limit: int = 30) -> None:
        """Fotoğraflı haberleri yeni düzene geçir; fotoğraflı kapak tasarımı değişince kapakları yenile."""
        def due(p: dict) -> bool:
            if not p.get("photos"):
                return False
            img = p.get("image") or {}
            return p.get("photos_v") != self.PHOTOS_V or (img.get("source") == "photo" and img.get("cover_v") != PHOTO_COVER_VERSION
                                                          and self._cover_ready(p))
        todo = [p for p in self.store.posts() if due(p)][:limit]
        for p in todo:
            try:
                if p.get("photos_v") != self.PHOTOS_V:
                    self._migrate_photos(p)
                self._build_cover(p, draft=False)
                self._make_og(p)
                self.store.save_post(p)
            except Exception as e:  # noqa: BLE001
                log.warning("Fotoğraflı kapak yenilenemedi (%s): %s", p["id"], e)
                return
        if todo:
            log.info("Fotoğraflı kapaklar yenilendi: %d", len(todo))

    def backfill_photos(self, limit: int = 5) -> None:
        """Eski haberlere gerçek fotoğraf ekle (her turda birkaç tane; bulunamayanlar 3 gün sonra tekrar denenir)."""
        if not self.cfg.get("images", "photos", True) or self.cfg.mock or self.cfg.fixtures_dir:
            return
        todo = [p for p in self.store.posts()
                if not p.get("photos") and not p.get("photos_removed") and (p.get("image") or {}).get("source") != "ai"
                and hours_since(p.get("photos_tried")) > 72][:limit]
        for p in todo:
            p["photos_tried"] = iso(now_utc())
            if self._attach_photos(p, draft=False):
                p["updated_at"] = p.get("updated_at") or p.get("published_at")
                log.info("Fotoğraf eklendi: %s (%d)", p["id"], len(p["photos"]))
            self.store.save_post(p)

    # ── tek çalışma ─────────────────────────────────────────
    def run(self) -> bool:
        """Bir tur: Telegram → süre dolanlar → toplama → özet → dinleme. Site değiştiyse True döner."""
        if self.tg and self.state.get("commands_version") != COMMANDS_VERSION:
            self.tg.delete_webhook()
            self.tg.set_commands(COMMANDS)
            self.state["commands_version"] = COMMANDS_VERSION
        if not self.tg:
            log.warning("TELEGRAM_BOT_TOKEN tanımlı değil; onay mekanizması kapalı.")
        elif not self.chat_id:
            log.warning("TELEGRAM_CHAT_ID tanımlı değil; bota /start yaz, numaranı söyleyecek.")

        self.flush_indexnow()
        self.process_updates()
        self.expire()
        try:
            self.migrate_urls()
        except Exception as e:  # noqa: BLE001
            log.exception("Adres geçişi hatası: %s", e)
        try:
            self.reselect_pending()
        except Exception as e:  # noqa: BLE001
            log.exception("Bekleyen taslak seçkisi hatası: %s", e)
        every = self.cfg.get("schedule", "collect_every_minutes", 60)
        due = hours_since(self.state.get("last_collect")) * 60 >= every - 2
        if not self.state.get("paused") and (due or self.force_collect):
            self.force_collect = False
            try:
                self.collect()
            except Exception as e:  # noqa: BLE001
                log.exception("Toplama hatası: %s", e)
                self.notify_error(f"Toplama sırasında hata: {type(e).__name__}: {e}")
        if not self.state.get("paused"):
            self.backfill_seo()
            try:
                self.fix_texts()
                self.backfill_appeal()
                self.backfill_cover_lines()
            except Exception as e:  # noqa: BLE001
                log.exception("Metin/ilgi puanı hatası: %s", e)
            try:
                self.more_photos()
                self.backfill_photos(int(self.cfg.get("images", "photo_backfill_per_run", 5) or 0))
            except Exception as e:  # noqa: BLE001
                log.exception("Fotoğraf işlemi hatası: %s", e)
        try:
            self.upgrade_photos()
        except Exception as e:  # noqa: BLE001
            log.exception("Fotoğraflı kapak hatası: %s", e)
        try:
            self.ig_tick()
        except Exception as e:  # noqa: BLE001
            log.exception("Instagram hatası: %s", e)
        self.refresh_covers()
        try:
            self.refresh_keyboards()
        except Exception as e:  # noqa: BLE001
            log.warning("Telegram düğmeleri yenilenemedi: %s", e)
        self.maybe_summary()
        self.listen(int(self.cfg.get("schedule", "listen_seconds", 120) or 0))
        self.store.save()
        if self._vis:
            self._vis.close()
        return self.store.site_dirty


def write_github_output(key: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
