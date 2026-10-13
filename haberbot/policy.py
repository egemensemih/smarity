"""Yayın kararı: hangi haber doğrudan yayınlansın, hangisi sana sorulsun?

Önce eleme (değişmedi): kaynaklar → ayıklama → yayın yönetmeni. Buraya yalnızca yönetmenin "yayınlanmalı" dediği haberler gelir.
Sonra tek bir kural (mod = kural):

  🔴 HER ZAMAN SORULUR  uyarı işareti (iddia, söylenti…) · otomatik yayınlanmayan marka (Vivo, Oppo…) · güven 'düşük'
  🟡 SORULUR            küçük kitleye hitap ediyor (yönetmen puanı 8'in altında) VE büyük bir marka değil
  ⏳ SORULUR + BEKLER   geniş kitle ya da büyük marka ama henüz 3 farklı kaynak yok: sana sorulur; sen karar vermeden
                        3. kaynak gelirse kendiliğinden yayınlanır (Telegram mesajı "otomatik yayınlandı" olur)
  🟢 OTOMATİK           geniş kitle ya da büyük marka + en az 3 farklı kaynak

Güvenlik (yalnızca kural modunda): otomatik yayınlanan haberlerden son 3 günde 2'sini kaldırırsan otomatik yayın kendiliğinden
durur (her şey sorulur); /mod kural yazınca hemen yeniden açılır. /mod manuel → her şey sorulur.
/mod tam → yönetmenin seçtiği her haber yayınlanır, yalnızca 🔴 olanlar sorulur; beğenmediğini Kaldır'la çıkarırsın
(kaldırdıkların yönetmene "sahibin istemediği haberler" olarak gösterilir, fren devreye girmez).
"""
from __future__ import annotations

import re
from datetime import timedelta

from .config import Config
from .util import hours_since, iso, now_utc, parse_iso

MODES = {"manuel": "Manuel (her haber sorulur)", "kural": "Kurallı (3+ kaynak otomatik)", "tam": "Tam otonom (yönetmenin seçtiği her haber yayınlanır)"}
ALIASES = {"ogrenen": "kural", "öğrenen": "kural", "otomatik": "kural", "oto": "kural"}
TIER_ICON = {"auto": "🟢", "wait": "⏳", "ask": "🟡", "hard": "🔴", "paused": "⏸"}


def _a(cfg: Config, key: str, default):
    v = cfg.get("autonomy", key, None)
    return default if v is None else v


def normalize_mode(m: str | None) -> str | None:
    m = (m or "").strip().lower()
    m = ALIASES.get(m, m)
    return m if m in MODES else None


def current_mode(cfg: Config, state: dict) -> str:
    return normalize_mode(state.get("mode_override")) or normalize_mode(_a(cfg, "mode", "kural")) or "kural"


def source_count(draft: dict) -> int:
    """Farklı yayın kuruluşu sayısı (aynı siteden iki haber bir sayılır)."""
    return len({s.get("name") for s in draft.get("sources") or [] if s.get("name")})


def min_sources(cfg: Config) -> int:
    return max(1, int(_a(cfg, "min_sources", 3) or 3))


def never_auto_brand(cfg: Config, draft: dict) -> str | None:
    """Otomatik yayınlanmayan markalar (ör. Vivo, Oppo): bu haberler her zaman onaya gelir."""
    names = [str(n).strip() for n in _a(cfg, "never_auto", []) or [] if str(n).strip()]
    if not names:
        return None
    text = " ".join([draft.get("title") or "", draft.get("summary") or "",
                     *[str(x) for x in (draft.get("entities") or []) + (draft.get("tags") or [])]])
    for n in names:
        if re.search(rf"(?<![\w]){re.escape(n)}(?![\w])", text, re.I):
            return n
    return None


def is_broad(cfg: Config, draft: dict) -> bool:
    """Geniş kitleye hitap ediyor mu? (yönetmen puanı yüksek ya da büyük bir marka)"""
    return bool(draft.get("big_brand")) or int(draft.get("importance") or 0) >= int(_a(cfg, "broad_importance", 8))


# ── otomatik yayın freni (kaldırılan otomatik haberler) ──────────────
def _recent_removals(cfg: Config, stats: dict) -> list[str]:
    h = float(_a(cfg, "pause_hours", 72) or 72)
    return [t for t in stats.get("auto_removals") or [] if hours_since(t) <= h]


def auto_paused_until(cfg: Config, stats: dict) -> str | None:
    """Otomatik yayın duraklatıldıysa bitiş zamanı (ISO), değilse None."""
    lim = int(_a(cfg, "pause_removals", 2) or 0)
    recent = sorted(_recent_removals(cfg, stats))
    if not lim or len(recent) < lim:
        return None
    end = parse_iso(recent[-lim]) + timedelta(hours=float(_a(cfg, "pause_hours", 72) or 72))
    return iso(end)


def record_removal(cfg: Config, stats: dict) -> bool:
    """Otomatik yayınlanan bir haber kaldırıldı. Bu kaldırma freni devreye soktuysa True döner."""
    before = auto_paused_until(cfg, stats)
    lst = stats.setdefault("auto_removals", [])
    lst.append(iso(now_utc()))
    del lst[:-20]
    return not before and bool(auto_paused_until(cfg, stats))


def resume(stats: dict) -> None:
    """/mod kural: freni sıfırla."""
    stats["auto_removals"] = []


# ── karar ─────────────────────────────────────────────────────────────
def decide(cfg: Config, state: dict, stats: dict, draft: dict) -> tuple[str, str]:
    """('auto' | 'ask', gerekçe). Taslağa policy_tier (auto/wait/ask/hard/paused) ve otomatikse auto_reason yazar."""
    def out(tier: str, reason: str) -> tuple[str, str]:
        draft["policy_tier"] = tier
        if tier == "auto":
            draft["auto_reason"] = reason
        return ("auto" if tier == "auto" else "ask"), reason

    mode = current_mode(cfg, state)
    if mode == "manuel":
        return out("hard", "Manuel mod: her haber sana soruluyor")
    if draft.get("flags"):
        return out("hard", "Uyarı işareti var")
    brand = never_auto_brand(cfg, draft)
    if brand:
        return out("hard", f"{brand}: otomatik yayınlanmayan marka")
    if draft.get("confidence") == "dusuk":
        return out("hard", "Güven seviyesi düşük")
    if int(draft.get("importance") or 0) < int(_a(cfg, "auto_min_importance", 7)):
        return out("hard", "Önem puanı düşük")
    if mode == "tam":
        return out("auto", "Tam otonom: yayın yönetmeni seçti")
    if not is_broad(cfg, draft):
        return out("ask", "Küçük kitleye hitap ediyor ve büyük bir marka değil")
    n, need = source_count(draft), min_sources(cfg)
    if n < need:
        return out("wait", f"Şimdilik {n}/{need} kaynak: {need}. kaynak gelirse kendiliğinden yayınlanacak")
    if auto_paused_until(cfg, stats):
        return out("paused", "Otomatik yayın durdu (son günlerde otomatik haberleri kaldırdın); /mod kural ile açılır")
    why = "büyük marka" if draft.get("big_brand") else "geniş kitle"
    return out("auto", f"{n} farklı kaynak + {why}")


# ── istatistik (bilgi amaçlı; karara etki etmez) ──────────────────────
def source_rate(stats: dict, name: str) -> tuple[int, float]:
    s = stats.get("sources", {}).get(name, {})
    a, r = s.get("approved", 0), s.get("rejected", 0)
    n = a + r
    return n, (a / n if n else 0.0)


def global_rate(cfg: Config, stats: dict, window: int = 30) -> tuple[int, float]:
    dec = [d for d in stats.get("decisions", []) if d.get("manual", True)][-window:]
    if not dec:
        return 0, 0.0
    return len(dec), sum(1 for d in dec if d.get("ok")) / len(dec)


def record(stats: dict, draft: dict, ok: bool, manual: bool = True, weight: int = 1) -> None:
    for s in draft.get("source_keys", []):
        e = stats.setdefault("sources", {}).setdefault(s, {"approved": 0, "rejected": 0})
        e["approved" if ok else "rejected"] += weight
    stats.setdefault("decisions", []).append(
        {"t": iso(now_utc()), "id": draft.get("id"), "ok": ok, "manual": manual})
