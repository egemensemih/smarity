"""Kademeli otonomi: hangi haber sana sorulsun, hangisi doğrudan yayınlansın?

Mantık (mod = ogrenen):
  • Şüpheli işaret taşıyan ya da güveni 'yüksek' olmayan haber → HER ZAMAN sorulur.
  • Son N kararındaki genel onay oranın düşükse → sorulur (sistem henüz öğreniyor).
  • Haberdeki TÜM kaynaklar senin kararlarınla 'güvenilir' hale geldiyse → otomatik yayın.
  Bir kaynak güvenilir sayılır: en az X karar + en az %Y onay.
  Otomatik yayınlanan bir haberi 'Kaldır' dersen o kaynak 2 ret puanı alır.
  Güvenilir gruplar (ayarlarda autonomy.trusted_groups): yönetmenin seçtiği haberlerden çok kaynakta çıkanlar (tüm
  kategorilerde en az 3 farklı kaynak) uyarı işareti yoksa doğrudan yayınlanır. Küçük kitleye hitap eden (yönetmen puanı
  8'in altında) ve büyük bir markaya ait olmayan haber yine sorulur; never_auto listesindeki markalar hep sorulur. Bir gruptan son 7 günde otomatik yayınlanan haberleri
  birkaç kez kaldırırsan o grup kendiliğinden yeniden onayına döner.
"""
from __future__ import annotations

import re

from .config import Config
from .util import hours_since, iso, now_utc

MODES = {"manuel": "Manuel", "ogrenen": "Öğrenen", "tam": "Tam otonom"}


def current_mode(cfg: Config, state: dict) -> str:
    m = state.get("mode_override") or cfg.get("autonomy", "mode", "ogrenen")
    return m if m in MODES else "ogrenen"


def source_trust(cfg: Config, stats: dict, name: str) -> tuple[bool, int, float]:
    s = stats.get("sources", {}).get(name, {})
    a, r = s.get("approved", 0), s.get("rejected", 0)
    n = a + r
    rate = a / n if n else 0.0
    ok = n >= cfg.get("autonomy", "source_min_decisions", 10) and rate >= cfg.get("autonomy", "source_min_approval", 0.9)
    return ok, n, rate


def global_rate(cfg: Config, stats: dict) -> tuple[int, float]:
    window = cfg.get("autonomy", "global_window", 30)
    dec = [d for d in stats.get("decisions", []) if d.get("manual", True)][-window:]
    if not dec:
        return 0, 0.0
    return len(dec), sum(1 for d in dec if d.get("ok")) / len(dec)


def trusted_group(cfg: Config, draft: dict) -> str | None:
    """Haber, doğrudan yayınlanan güvenilir gruplardan birinde mi? (kategori + en az N farklı kaynak)"""
    names = {s.get("name") for s in draft.get("sources") or [] if s.get("name")}
    for g in cfg.get("autonomy", "trusted_groups", None) or []:
        cats = g.get("categories") or []
        if cats and draft.get("category") not in cats:
            continue
        if len(names) < int(g.get("min_sources", 1) or 1):
            continue
        return str(g.get("name") or "güvenilir grup")
    return None


def never_auto_brand(cfg: Config, draft: dict) -> str | None:
    """Otomatik yayınlanmayan markalar (ör. Vivo, Oppo): bu haberler her zaman onaya gelir."""
    names = [str(n).strip() for n in cfg.get("autonomy", "never_auto", None) or [] if str(n).strip()]
    if not names:
        return None
    text = " ".join([draft.get("title") or "", draft.get("summary") or "",
                     *[str(x) for x in (draft.get("entities") or []) + (draft.get("tags") or [])]])
    for n in names:
        if re.search(rf"(?<![\w]){re.escape(n)}(?![\w])", text, re.I):
            return n
    return None


def group_paused(cfg: Config, stats: dict, name: str) -> bool:
    """Bu gruptan son 7 günde otomatik yayınlanıp kaldırdığın haber sayısı sınıra ulaştıysa grup yeniden onaya döner."""
    lim = int(cfg.get("autonomy", "trusted_pause_removals", 2) or 0)
    recent = [t for t in (stats.get("group_removals") or {}).get(name, []) if hours_since(t) <= 24 * 7]
    return bool(lim) and len(recent) >= lim


def record_group_removal(stats: dict, name: str) -> None:
    lst = stats.setdefault("group_removals", {}).setdefault(name, [])
    lst.append(iso(now_utc()))
    del lst[:-20]


def decide(cfg: Config, state: dict, stats: dict, draft: dict) -> tuple[str, str]:
    """('auto' | 'ask', gerekçe)"""
    mode = current_mode(cfg, state)
    if mode == "manuel":
        return "ask", "Manuel mod"
    if draft.get("flags"):
        return "ask", "Uyarı işareti var"
    group = trusted_group(cfg, draft)
    if group and never_auto_brand(cfg, draft):
        group = None                                   # bu marka her zaman onaya gelir
    broad = int(cfg.get("autonomy", "auto_broad_importance", 0) or 0)
    if group and draft.get("importance", 0) < broad and not draft.get("big_brand"):
        group = None                                   # küçük kitleye hitap ediyor ve büyük bir marka değil: sorulur
    if (group and draft.get("confidence") in ("yuksek", "orta")
            and draft.get("importance", 0) >= cfg.get("autonomy", "auto_min_importance", 6)):
        if not group_paused(cfg, stats, group):
            draft["auto_group"] = group
            return "auto", f"Güvenilir grup: {group}"
    if draft.get("confidence") != "yuksek":
        return "ask", "Güven seviyesi yüksek değil"
    if draft.get("importance", 0) < cfg.get("autonomy", "auto_min_importance", 6):
        return "ask", "Önem puanı düşük"
    if mode == "tam":
        return "auto", "Tam otonom mod"

    n, rate = global_rate(cfg, stats)
    need_n = cfg.get("autonomy", "global_window", 30)
    need_rate = cfg.get("autonomy", "global_min_approval", 0.85)
    if n < need_n:
        return "ask", f"Öğreniyor: {n}/{need_n} karar"
    if rate < need_rate:
        return "ask", f"Genel onay oranı %{rate * 100:.0f} (<%{need_rate * 100:.0f})"
    untrusted = [s for s in draft.get("source_keys", []) if not source_trust(cfg, stats, s)[0]]
    if untrusted:
        return "ask", "Henüz güvenilmeyen kaynak: " + ", ".join(untrusted[:3])
    return "auto", "Güvenilir kaynak + net haber"


def record(stats: dict, draft: dict, ok: bool, manual: bool = True, weight: int = 1) -> None:
    for s in draft.get("source_keys", []):
        e = stats.setdefault("sources", {}).setdefault(s, {"approved": 0, "rejected": 0})
        e["approved" if ok else "rejected"] += weight
    stats.setdefault("decisions", []).append(
        {"t": iso(now_utc()), "id": draft.get("id"), "ok": ok, "manual": manual})
