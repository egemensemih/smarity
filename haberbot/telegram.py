"""Telegram Bot API istemcisi + test için sahte (mock) istemci."""
from __future__ import annotations

import json
from pathlib import Path

import requests

from .util import log


class TelegramError(RuntimeError):
    pass


class Telegram:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}"

    def _call(self, method: str, data: dict | None = None, files: dict | None = None, timeout: int = 40):
        payload = {}
        for k, v in (data or {}).items():
            if v is None:
                continue
            if isinstance(v, bool):
                v = "true" if v else "false"
            payload[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
        try:
            r = requests.post(f"{self.base}/{method}", data=payload, files=files, timeout=timeout)
            res = r.json()
        except (requests.RequestException, ValueError) as e:
            raise TelegramError(f"{method}: {e}") from e
        if not res.get("ok"):
            raise TelegramError(f"{method}: {res.get('description')}")
        return res["result"]

    # ── gelen ────────────────────────────────────────────────
    def get_updates(self, offset: int, timeout: int = 0) -> list[dict]:
        return self._call("getUpdates", {
            "offset": offset, "timeout": timeout,
            "allowed_updates": ["message", "callback_query"],
        }, timeout=timeout + 15)

    def typing(self, chat_id) -> None:
        """Sohbetin üstünde "yazıyor…" göster (işlem sürerken)."""
        try:
            self._call("sendChatAction", {"chat_id": chat_id, "action": "typing"}, timeout=10)
        except TelegramError:
            pass

    def answer_callback(self, cb_id: str, text: str = "") -> None:
        try:
            self._call("answerCallbackQuery", {"callback_query_id": cb_id, "text": text[:190]})
        except TelegramError:
            pass  # çok eski sorgular yanıtlanamaz; sorun değil

    # ── giden ────────────────────────────────────────────────
    def send_photo(self, chat_id, photo: Path, caption: str, keyboard=None, silent=False,
                   parse_mode: str | None = "HTML") -> dict:
        with open(photo, "rb") as f:
            return self._call("sendPhoto", {
                "chat_id": chat_id, "caption": caption, "parse_mode": parse_mode,
                "reply_markup": {"inline_keyboard": keyboard} if keyboard else None,
                "disable_notification": silent,
            }, files={"photo": ("kapak.jpg", f, "image/jpeg")})

    def send_media_group(self, chat_id, photos: list[Path], caption: str = "", silent=True) -> None:
        files, media = {}, []
        handles = []
        try:
            for i, ph in enumerate(photos):
                fh = open(ph, "rb")
                handles.append(fh)
                files[f"p{i}"] = (f"p{i}.jpg", fh, "image/jpeg")
                item = {"type": "photo", "media": f"attach://p{i}"}
                if i == 0 and caption:
                    item.update({"caption": caption, "parse_mode": "HTML"})
                media.append(item)
            self._call("sendMediaGroup", {"chat_id": chat_id, "media": media, "disable_notification": silent},
                       files=files, timeout=90)
        finally:
            for fh in handles:
                fh.close()

    def send_message(self, chat_id, text: str, keyboard=None, silent=False, reply_to=None) -> dict:
        return self._call("sendMessage", {
            "chat_id": chat_id, "text": text[:4096], "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": keyboard} if keyboard else None,
            "disable_notification": silent,
            "link_preview_options": {"is_disabled": True},
            "reply_parameters": {"message_id": reply_to, "allow_sending_without_reply": True} if reply_to else None,
        })

    def edit_caption(self, chat_id, message_id: int, caption: str, keyboard=None) -> None:
        try:
            self._call("editMessageCaption", {
                "chat_id": chat_id, "message_id": message_id, "caption": caption, "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard or []},
            })
        except TelegramError as e:
            if "not modified" not in str(e):
                log.warning("Telegram mesajı güncellenemedi: %s", e)

    def edit_text(self, chat_id, message_id: int, text: str, keyboard=None) -> None:
        try:
            self._call("editMessageText", {
                "chat_id": chat_id, "message_id": message_id, "text": text[:4096], "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard or []},
                "link_preview_options": {"is_disabled": True},
            })
        except TelegramError as e:
            if "not modified" not in str(e):
                log.warning("Telegram mesajı güncellenemedi: %s", e)

    def set_commands(self, commands: list[tuple[str, str]]) -> None:
        try:
            self._call("setMyCommands", {"commands": [{"command": c, "description": d} for c, d in commands]})
        except TelegramError as e:
            log.warning("Komut listesi ayarlanamadı: %s", e)

    def delete_webhook(self) -> None:
        try:
            self._call("deleteWebhook", {"drop_pending_updates": False})
        except TelegramError:
            pass


class MockTelegram(Telegram):
    """Giden mesajları data/_mock/outbox.jsonl'a yazar, gelenleri inbox.json'dan okur."""

    def __init__(self, folder: Path):
        self.dir = folder
        self.dir.mkdir(parents=True, exist_ok=True)
        import time as _t
        self._mid = int(_t.time() * 1000) % 1_000_000_000

    def _log(self, method, data):
        with open(self.dir / "outbox.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"method": method, **data}, ensure_ascii=False, default=str) + "\n")

    def _call(self, method, data=None, files=None, timeout=40):
        data = dict(data or {})
        if method == "getUpdates":
            p = self.dir / "inbox.json"
            ups = json.loads(p.read_text()) if p.exists() else []
            p.write_text("[]")
            return [u for u in ups if u["update_id"] >= data.get("offset", 0)]
        if files:
            data["photo"] = "<jpeg>"
        self._log(method, data)
        self._mid += 1
        return {"message_id": self._mid}
