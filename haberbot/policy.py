"""Kademeli otonomi: hangi haber sana sorulsun, hangisi doğrudan yayınlansın?

Mantık (mod = ogrenen):
  • Şüpheli işaret taşıyan ya da güveni 'yüksek' olmayan haber → HER ZAMAN sorulur.
  • Son N kararındaki genel onay oranın düşükse → sorulur (sistem henüz öğreniyor).
  • Haberdeki TÜM kaynaklar senin kararlarınla 'güvenilir' hale geldiyse → otomatik yayın.
  Bir kaynak güvenilir sayılır: en az X karar + en az %Y onay.
  Otomatik yayınlanan bir haberi 'Kaldır' dersen o kaynak 2 ret puanı alır.
"""
from __future__ import annotations

from .config import Config
from .util import iso, now_utc

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


def decide(cfg: Config, state: dict, stats: dict, draft: dict) -> tuple[str, str]:
    """('auto' | 'ask', gerekçe)"""
    mode = current_mode(cfg, state)
    if mode == "manuel":
        return "ask", "Manuel mod"
    if draft.get("flags"):
        return "ask", "Uyarı işareti var"
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
