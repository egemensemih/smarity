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
from .covers import COVER_VERSION
from .extract import full_text
from .instagram import Instagram, InstagramError, TokenStore, fingerprint, head_ok
from .llm import LLMError, MockLLM, estimate_cost, make_llm
from .prompts import (FLAG_LABELS, FLAGS, SEO_SCHEMA, TRIAGE_SCHEMA, WRITE_SCHEMA, seo_system, seo_user,
                      triage_system, triage_user, write_system, write_user)
from .sources import fetch_all
from .store import Store
from .telegram import MockTelegram, Telegram, TelegramError
from .util import (clip, hours_since, iso, local, log, now_utc, short_hash, slugify,
                   tr_date)

KIND_ORDER = {"official": 0, "media": 1, "community": 2}
# Uzun süren düğmeler: (hemen gösterilen yanıt, işlem bitince beklenen sonuç)
SLOW_ACTIONS = {
    "p": ("⏳ Yayınlanıyor…", "✅ Yayınlandı"),
    "v": ("⏳ Yeni görsel hazırlanıyor…", "🎨 Yeni görsel hazır"),
    "g": ("⏳ Fotoğraf değiştiriliyor…", "🖼 Fotoğraf değişti"),
    "n": ("⏳ Fotoğraflar kaldırılıyor…", "🚫 Fotoğraflar kaldırıldı"),
    "w": ("⏳ Yeniden yazılıyor…", "🔁 Yeniden yazıldı"),
    "s": ("⏳ Görseller hazırlanıyor…", "📱 Gönderildi"),
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
    ("instagram", "Instagram paylaşımları: durum / kapat / ac"),
    ("yardim", "Nasıl kullanılır"),
]
COMMANDS_VERSION = 2
HELP = """<b>Nasıl çalışır?</b>
Kaynaklar düzenli taranır; teknoloji, girişim, yapay zeka, ürün, otomobil ve oyun dünyasından önemli haberler Türkçe yazılıp buraya düşer.

✅ <b>Yayınla</b> — siteye koyar
❌ <b>Reddet</b> — yayınlamaz (Geri al ile dönebilirsin)
📄 <b>Tam metin</b> — haberin tamamını gösterir
🔁 <b>Yeniden yaz</b> — yapay zeka metni yeniden yazar
🎨 <b>Yeni görsel</b> — aynı sahneden yeni bir görsel üretir
🖼 <b>Kendi sahnen</b> — mesajı yanıtlayıp <code>görsel: kırmızı bir satranç tahtası üzerinde cam piyonlar</code> gibi yaz; görsel buna göre yeniden üretilir
✏️ <b>Düzeltme</b> — bir haber mesajını <i>yanıtlayıp</i> talimat yaz: "başlığı kısalt", "ikinci paragrafı çıkar" gibi. Yayınlanmış habere de uygulanır.
🗑 <b>Kaldır</b> — yayınlanmış haberi siteden kaldırır

<b>Öğrenen mod:</b> Kararların kaynak bazında kaydedilir. Bir kaynak yeterince onay alınca, o kaynaktan gelen net haberler otomatik yayınlanır ve sana sessizce bildirilir. Şüpheli işaretli haberler her zaman sana sorulur.

📸 <b>Instagram</b> — yayınlanan her haber birkaç dakika içinde carousel ve hikâye olarak Instagram'da paylaşılır. Sıradaki bir haberi mesajındaki <b>Instagram'a gönderme</b> düğmesiyle durdurabilirsin. Tümünü durdurmak için <code>/instagram kapat</code>.

Komutlar: /durum /bekleyen /mod /topla /duraklat /devam /kaynaklar /instagram"""


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
        fresh = []
        for it in items:
            if it["key"] in st.seen:
                continue
            st.seen[it["key"]] = iso(now_utc())
            if it["source"] not in seeded and (it["html_source"] or not it["published"]):
                continue  # tarihsiz kaynağın ilk taraması: sadece "görüldü" olarak işaretle
            if it["published"] and hours_since(it["published"]) > max_age:
                continue
            fresh.append(it)
        self.state["seeded_sources"] = sorted(seeded | {it["source"] for it in items})
        self.state["last_collect"] = iso(now_utc())
        log.info("Yeni öğe: %d (toplam okunan %d)", len(fresh), len(items))
        queue = self._queue(max_age)
        if not fresh and not queue:
            return

        min_imp = ed("min_importance", 6)
        new_stories, merged, skipped = [], 0, 0
        if fresh:
            fresh.sort(key=lambda x: (KIND_ORDER.get(x["kind"], 3), hours_since(x["published"]) if x["published"] else 0))
            fresh = fresh[:80]
            by_tid = {}
            for i, it in enumerate(fresh, 1):
                it["tid"] = f"i{i}"
                by_tid[it["tid"]] = it

            recent = [{"sid": f"q:{i}", "status": "queued", "title": q["story"].get("topic", "")}
                      for i, q in enumerate(queue)]
            for d in st.drafts():
                recent.append({"sid": "s:" + d["id"], "status": d.get("status", "pending"), "title": d["title"]})
            for p in st.posts():
                if hours_since(p.get("published_at")) < 72:
                    recent.append({"sid": "s:" + p["id"], "status": "published", "title": p["title"]})

            try:
                tri = self.llm.json(cfg.get("ai", "triage_model", "claude-haiku-4-5-20251001"),
                                    triage_system(self.brand), triage_user(fresh, recent[:100], today),
                                    TRIAGE_SCHEMA, max_tokens=8000)
            except LLMError as e:
                if self._transient(e):
                    log.warning("Yapay zeka şu an yoğun (ayıklama), sonraki turda tekrar denenecek: %s", str(e)[:160])
                else:
                    self.notify_error(f"Yapay zeka (ayıklama) hatası: {e}")
                for it in fresh:  # bir sonraki turda tekrar denensin
                    st.seen.pop(it["key"], None)
                tri = {"stories": []}

            for s in tri.get("stories", []):
                its = [by_tid[t] for t in s.get("item_ids", []) if t in by_tid]
                if not its:
                    continue
                dup = (s.get("duplicate_of") or "").strip()
                if dup.startswith("q:") and dup[2:].isdigit() and int(dup[2:]) < len(queue):
                    q = queue[int(dup[2:])]  # sıradaki habere yeni kaynak ekle
                    urls = {it["url"] for it in q["items"]}
                    q["items"] += [it for it in its if it["url"] not in urls]
                    merged += 1
                    continue
                if dup:
                    if self._merge_sources(dup.removeprefix("s:"), its):
                        merged += 1
                    continue
                if not (s.get("on_topic") or s.get("ai_related")) or int(s.get("importance", 0)) < min_imp:
                    skipped += 1
                    continue
                new_stories.append({"story": s, "items": its, "at": iso(now_utc())})

        # Sıra: önce önemli olanlar; eşitse önce gelen
        queue = sorted(queue + new_stories, key=lambda q: (-int(q["story"].get("importance", 0)), q["at"]))
        limit = min(ed("max_drafts_per_run", 2), remaining)
        todo, queue = queue[:limit], queue[limit:]
        self.state["queue"] = queue[:40]
        if fresh:
            log.info("Ayıklama: %d yeni hikâye, %d elendi, %d mevcut habere eklendi", len(new_stories), skipped, merged)
        log.info("Bu tur %d taslak yazılacak, sırada %d haber var", len(todo), len(self.state["queue"]))
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
                self.state["queue"] = (todo[n:] + self.state["queue"])[:40]  # yazılamayanlar sırada kalsın
                break
            except Exception as e:  # noqa: BLE001
                log.exception("Taslak oluşturulamadı: %s", e)

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
    def _write(self, sources: list[dict], previous: dict | None = None, instruction: str | None = None) -> dict:
        cfg = self.cfg
        out = self.llm.json(
            cfg.get("ai", "writer_model", "claude-sonnet-5"),
            write_system(self.brand),
            write_user(sources, self.today(), previous, instruction),
            WRITE_SCHEMA, max_tokens=16000, effort=cfg.get("ai", "writer_effort", "medium"))
        cat = out.get("category") if out.get("category") in CATEGORIES else None
        return {
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
        }

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
            "importance": int(story.get("importance", 5)),
            "triage_reason": story.get("reason", ""),
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
        self.queue_indexnow(self.cfg.post_url(slug))
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
        log.info("Yayınlandı: %s → %s", post["id"], self.cfg.post_url(slug))
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
        }[kind]
        meta = f"🏷 {esc(category_label(d['category']))} · Önem {d.get('importance', '?')}/10 · Güven {CONF_LABEL.get(d.get('confidence'), '?')}"
        lines = [head, "", f"<b>{esc(d['title'])}</b>", "", "{SUMMARY}", "",
                 "📰 " + esc(", ".join(self._credits(d))), meta]
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
        if kind in ("published", "auto"):
            lines.append(f'🔗 <a href="{esc(self.cfg.post_url(d["slug"]))}">Sitede aç</a>')
        cap = "\n".join(lines)
        room = 1024 - len(cap) + len("{SUMMARY}") - 5
        return cap.replace("{SUMMARY}", esc(clip(d.get("summary", ""), max(60, room))))

    def _keyboard(self, d: dict, kind: str):
        did = d["id"]
        src = d["sources"][0]["url"] if d.get("sources") else None
        if kind == "pending":
            kb = [[{"text": "✅ Yayınla", "callback_data": f"p:{did}"},
                   {"text": "❌ Reddet", "callback_data": f"r:{did}"}],
                  [{"text": "📄 Tam metin", "callback_data": f"f:{did}"},
                   {"text": "🔁 Yeniden yaz", "callback_data": f"w:{did}"}] + self._visual_buttons(d)]
            if src:
                kb.append([{"text": "🔗 Kaynağı aç", "url": src}])
            return kb
        if kind in ("published", "auto"):
            return [[{"text": "🔗 Haberi aç", "url": self.cfg.post_url(d["slug"])},
                     {"text": "🗑 Kaldır", "callback_data": f"d:{did}"}],
                    [{"text": "📄 Tam metin", "callback_data": f"f:{did}"}] + self._visual_buttons(d)
                    + [{"text": "📱 Instagram", "callback_data": f"s:{did}"}]]
        if kind == "rejected":
            return [[{"text": "↩️ Geri al", "callback_data": f"u:{did}"}]]
        return []

    def _send_preview(self, d: dict, kind: str) -> None:
        if not (self.tg and self.chat_id):
            return
        st = self.store
        try:
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
        url = self.cfg.post_url(post["slug"])
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
                if len(local) < 2:
                    return "Başka fotoğraf yok."
                self._reorder_photos(d, where, local[1:] + local[:1] + [r for r in d["photos"] if not r.get("file")])
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
        if action == "s":
            if where != "post":
                return "Önce yayınlanmalı."
            self._send_social(d, force=True)
            return "📱 Gönderildi"
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
            if text and len(text) <= 24:   # kısa ifade: kapaktaki büyük yazı olsun
                d["cover_text"] = text
                d["cover_variant"] = int(d.get("cover_variant", 0)) + 1
            elif text:                      # uzun ifade: yapay zeka görseli sahnesi
                d["visual_scene"] = text
            else:                           # "Yeni görsel" düğmesi: yeni renk ve düzen
                d["cover_variant"] = int(d.get("cover_variant", 0)) + 1
            d["rewrites"] = (d.get("rewrites") or 0) + 1
            old_kind = "pending" if where == "draft" else ("auto" if d.get("publish_mode") == "auto" else "published")
            if d.get("photos"):
                self._drop_photos(d, where)
            d["image"] = self.vis.make_hero(d, self._hero(d))
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
        lines = ["🧭 <b>Kaynak güveni</b> (✅ = otomatik yayına uygun)"]
        names = [s["name"] for s in self.cfg.sources]
        for name in names:
            ok, n, rate = policy.source_trust(self.cfg, self.stats, name)
            h = self.state.get("source_health", {}).get(name, {})
            health = " ⚠️ okunamıyor" if h.get("fails", 0) >= 3 else ""
            detail = f"{n} karar, %{rate * 100:.0f} onay" if n else "henüz karar yok"
            lines.append(f"{'✅' if ok else '▫️'} {esc(name)}: {detail}{health}")
        need = self.cfg.get("autonomy", "source_min_decisions", 10)
        pct = self.cfg.get("autonomy", "source_min_approval", 0.9) * 100
        lines.append(f"\nGüven için: en az {need} karar ve %{pct:.0f} onay.")
        return "\n".join(lines)

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
            self.queue_indexnow(self.cfg.post_url(p["slug"]))
            log.info("SEO bilgisi eklendi: %s → %s", p["id"], p["seo_title"])

    def refresh_covers(self, limit: int = 30) -> None:
        """Kapak tasarımı değişince yayındaki haberlerin görsellerini yeniden üret (yapay zeka görsellerine dokunmaz)."""
        if (self.cfg.get("images", "style", "kapak") or "kapak") != "kapak":
            return
        todo = [p for p in self.store.posts()
                if (p.get("image") or {}).get("source") in ("cover", "fallback", None)
                and (p.get("image") or {}).get("cover_v") != COVER_VERSION and not p.get("photos")][:limit]
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
                f"Ret: {c.get('rejected', 0)} · Süresi dolan: {c.get('expired', 0)} · Kaldırılan: {c.get('removed', 0)}\n"
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
        """Telegram'ı canlı dinle: son 10 dakikada sen bir şey yaptıysan her zaman;
        onay bekleyen haber varsa sessiz saatler dışında."""
        if self.force_collect:
            return True
        if hours_since(self.state.get("last_activity")) * 60 < 10:
            return True
        return bool(self.store.drafts("pending")) and not self.quiet()

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

    # ── gerçek fotoğraflar ──────────────────────────────────
    def _visual_buttons(self, d: dict) -> list[dict]:
        did = d["id"]
        if d.get("photos"):
            out = [{"text": "🚫 Fotoğrafsız", "callback_data": f"n:{did}"}]
            if len(d["photos"]) > 1:
                out.insert(0, {"text": "🖼 Başka foto", "callback_data": f"g:{did}"})
            return out
        return [{"text": "🎨 Yeni görsel", "callback_data": f"v:{did}"}]

    def _photo_dir(self, draft: bool):
        return self.cfg.drafts_dir if draft else self.cfg.images_dir

    def _attach_photos(self, d: dict, draft: bool) -> bool:
        """Kaynaklardan gerçek fotoğrafları al: ilki ana görsel, diğerleri galeri. Bulunamazsa False."""
        cfg = self.cfg
        if not cfg.get("images", "photos", True) or cfg.mock or cfg.fixtures_dir:
            return False
        try:
            got = photos.gather(d.get("sources") or [], limit=int(cfg.get("images", "photo_limit", 6) or 6))
        except Exception as e:  # noqa: BLE001
            log.warning("Fotoğraflar alınamadı (%s): %s", d.get("id"), e)
            return False
        if not got:
            return False
        folder = self._photo_dir(draft)
        for f in self.store.gallery_files(d["id"], draft):
            f.unlink(missing_ok=True)
        recs = []
        for i, p in enumerate(got):
            name = f"{d['id']}.webp" if i == 0 else f"{d['id']}-g{i}.webp"
            w, h = photos.save_webp(p["image"], folder / name, 1600 if i == 0 else 1280, 80 if i == 0 else 74)
            recs.append({"file": name, "src": p["src"], "credit": p["credit"], "page": p["page"],
                         "alt": p["alt"], "w": w, "h": h})
        d["photos"] = recs
        d["image"] = {"source": "photo", "credit": recs[0]["credit"], "page": recs[0]["page"], "src": recs[0]["src"]}
        if not draft:
            self._make_og(d)
        return True

    def _reorder_photos(self, d: dict, where: str, order: list[dict]) -> None:
        """Fotoğraf sırasını değiştir (ilk sıradaki ana görsel olur); dosya adları sıraya göre yeniden verilir."""
        from PIL import Image
        draft = where == "draft"
        folder = self._photo_dir(draft)
        loaded = []
        for rec in order:
            f = folder / rec["file"] if rec.get("file") else None
            loaded.append((rec, Image.open(f).convert("RGB") if f and f.exists() else None))
        for f in self.store.gallery_files(d["id"], draft):
            f.unlink(missing_ok=True)
        recs = []
        for i, (rec, im) in enumerate(loaded):
            name = f"{d['id']}.webp" if i == 0 else f"{d['id']}-g{i}.webp"
            rec = dict(rec)
            if im is not None:
                photos.save_webp(im, folder / name, 1600, 82)
                rec["file"] = name
            else:
                rec["file"] = None
            recs.append(rec)
        d["photos"] = [r for r in recs if r.get("file") or r.get("src")]
        first = d["photos"][0]
        d["image"] = {"source": "photo", "credit": first["credit"], "page": first["page"], "src": first["src"]}

    def _drop_photos(self, d: dict, where: str) -> None:
        for f in self.store.gallery_files(d["id"], where == "draft"):
            f.unlink(missing_ok=True)
        d.pop("photos", None)
        d["photos_removed"] = True
        d["image"] = {"source": "cover"}

    def _make_og(self, p: dict) -> None:
        """Paylaşım görseli: fotoğraf varsa fotoğrafın kırpımı, yoksa marka kartı."""
        st = self.store
        hero = st.post_image(p["id"])
        if (p.get("image") or {}).get("source") == "photo" and hero.exists():
            from PIL import Image
            photos.og_crop(Image.open(hero).convert("RGB"), st.post_og(p["id"]))
        else:
            self.vis.render_card(p, "og", hero, st.post_og(p["id"]))

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

    def prune_gallery(self) -> None:
        """Yer kazanmak için eski haberlerin galeri kopyalarını sil (ana görsel kalır, galeri kaynaktan gösterilir)."""
        if self.state.get("last_prune") == self.today():
            return
        self.state["last_prune"] = self.today()
        keep = float(self.cfg.get("images", "gallery_keep_days", 0) or 0)
        if keep <= 0:  # 0 = hiçbir fotoğraf silinmez
            return
        n = 0
        for p in self.store.posts():
            if hours_since(p.get("published_at")) < keep * 24 or not p.get("photos"):
                continue
            changed = False
            for rec in p["photos"][1:]:
                if rec.get("file"):
                    (self.cfg.images_dir / rec["file"]).unlink(missing_ok=True)
                    rec["file"] = None
                    changed = True
                    n += 1
            if changed:
                self.store.save_post(p)
        if n:
            log.info("Eski galeri kopyaları silindi: %d", n)

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
                self.backfill_photos(int(self.cfg.get("images", "photo_backfill_per_run", 5) or 0))
                self.prune_gallery()
            except Exception as e:  # noqa: BLE001
                log.exception("Fotoğraf işlemi hatası: %s", e)
        try:
            self.ig_tick()
        except Exception as e:  # noqa: BLE001
            log.exception("Instagram hatası: %s", e)
        self.refresh_covers()
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
