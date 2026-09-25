"""Durum, taslak ve yayın dosyaları (hepsi depoda JSON olarak durur)."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .config import Config
from .util import iso, now_utc, hours_since, log


def read_json(path: Path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as e:
        log.warning("Bozuk JSON dosyası atlandı: %s (%s)", path, e)
        return default


def write_json(path: Path, data, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        if compact:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        else:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")
    os.replace(tmp, path)


DEFAULT_STATE = {
    "telegram_offset": 0,
    "last_collect": None,
    "last_summary_date": None,
    "mode_override": None,
    "paused": False,
    "seeded_sources": [],
    "source_health": {},
    "day_counts": {},
    "last_error_notice": None,
    "chat_id_hint_sent": [],
}

DEFAULT_STATS = {"sources": {}, "decisions": []}


class Store:
    """Tüm kalıcı veriye tek noktadan erişim. `dirty` → site yeniden üretilmeli."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.state: dict = {**DEFAULT_STATE, **read_json(cfg.data_dir / "state.json", {})}
        self.seen: dict = read_json(cfg.data_dir / "seen.json", {})
        self.stats: dict = {**DEFAULT_STATS, **read_json(cfg.data_dir / "stats.json", {})}
        self.site_dirty = False

    # ── kaydet ───────────────────────────────────────────────
    def save(self) -> None:
        # görülen bağlantıları 10 günden sonra unut
        self.seen = {k: v for k, v in self.seen.items() if hours_since(v) < 240}
        # günlük sayaçlar: son 14 gün
        dc = self.state.get("day_counts", {})
        self.state["day_counts"] = {k: dc[k] for k in sorted(dc)[-14:]}
        self.stats["decisions"] = self.stats.get("decisions", [])[-300:]
        write_json(self.cfg.data_dir / "state.json", self.state)
        write_json(self.cfg.data_dir / "seen.json", self.seen, compact=True)
        write_json(self.cfg.data_dir / "stats.json", self.stats)

    # ── sayaçlar ─────────────────────────────────────────────
    def bump(self, day: str, key: str, n: int = 1) -> None:
        d = self.state.setdefault("day_counts", {}).setdefault(day, {})
        d[key] = d.get(key, 0) + n

    def count(self, day: str, key: str) -> int:
        return self.state.get("day_counts", {}).get(day, {}).get(key, 0)

    # ── taslaklar ────────────────────────────────────────────
    def draft_path(self, did: str) -> Path:
        return self.cfg.drafts_dir / f"{did}.json"

    def draft_image(self, did: str) -> Path:
        """Taslağın kahraman görseli (yapay zeka ya da yedek)."""
        return self.cfg.drafts_dir / f"{did}.webp"

    def load_draft(self, did: str) -> dict | None:
        return read_json(self.draft_path(did), None)

    def save_draft(self, d: dict) -> None:
        write_json(self.draft_path(d["id"]), d)

    def drafts(self, status: str | None = None) -> list[dict]:
        out = []
        for p in sorted(self.cfg.drafts_dir.glob("*.json")):
            d = read_json(p, None)
            if d and (status is None or d.get("status") == status):
                out.append(d)
        out.sort(key=lambda d: d.get("created_at") or "")
        return out

    def archive_draft(self, d: dict, status: str) -> None:
        """Taslağı arşive (aylık jsonl) taşı; görseli sil."""
        d = dict(d)
        d["status"] = status
        d["closed_at"] = iso(now_utc())
        d.pop("source_texts", None)
        month = (d["closed_at"] or "")[:7]
        arch = self.cfg.data_dir / "archive" / f"{month}.jsonl"
        arch.parent.mkdir(parents=True, exist_ok=True)
        with open(arch, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
        self.draft_path(d["id"]).unlink(missing_ok=True)
        self.draft_image(d["id"]).unlink(missing_ok=True)

    # ── yayınlar ─────────────────────────────────────────────
    def post_path(self, pid: str) -> Path:
        return self.cfg.posts_dir / f"{pid}.json"

    def post_image(self, pid: str) -> Path:
        return self.cfg.images_dir / f"{pid}.webp"

    def post_og(self, pid: str) -> Path:
        return self.cfg.images_dir / f"{pid}-og.jpg"

    def card_path(self, did: str, kind: str) -> Path:
        """Telegram/Instagram kartları: depoya kaydedilmez (.cache)."""
        return self.cfg.root / ".cache" / "cards" / f"{did}-{kind}.jpg"

    def posts(self) -> list[dict]:
        out = []
        for p in self.cfg.posts_dir.glob("*.json"):
            d = read_json(p, None)
            if d:
                out.append(d)
        out.sort(key=lambda d: d.get("published_at") or "", reverse=True)
        return out

    def load_post(self, pid: str) -> dict | None:
        return read_json(self.post_path(pid), None)

    def save_post(self, d: dict) -> None:
        write_json(self.post_path(d["id"]), d)
        self.site_dirty = True

    def move_image_to_post(self, did: str) -> None:
        src = self.draft_image(did)
        if src.exists():
            self.cfg.images_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), self.post_image(did))

    def delete_post(self, pid: str) -> dict | None:
        d = self.load_post(pid)
        if not d:
            return None
        self.post_path(pid).unlink(missing_ok=True)
        self.post_image(pid).unlink(missing_ok=True)
        self.post_og(pid).unlink(missing_ok=True)
        self.site_dirty = True
        return d

    def find_any(self, did: str) -> tuple[str, dict | None]:
        """('draft'|'post'|'', kayıt)"""
        d = self.load_draft(did)
        if d:
            return "draft", d
        p = self.load_post(did)
        if p:
            return "post", p
        return "", None
