"""Instagram otomatik paylaşım (Instagram API with Instagram Login).

Akış: haber yayınlanınca sıraya girer → site yayınlanırken kartlar _site/ig/ altına konur →
bir sonraki turda Instagram bu herkese açık JPEG'leri alır ve carousel + hikâye paylaşılır.

Erişim anahtarı (IG_ACCESS_TOKEN) GitHub'da gizli anahtar olarak durur. 60 günlük anahtar bot tarafından
düzenli yenilenir; yenilenen anahtar yalnızca asıl gizli anahtarla açılabilecek şekilde şifrelenip
data/instagram.json dosyasına yazılır (depoda düz metin anahtar yoktur).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from datetime import timedelta

import requests

from .util import iso, log, now_utc, parse_iso

API = "https://graph.instagram.com"
VERSION = "v25.0"


class InstagramError(Exception):
    def __init__(self, msg: str, code: int | None = None, subcode: int | None = None, transient: bool = False):
        super().__init__(msg)
        self.code, self.subcode, self.transient = code, subcode, transient

    @property
    def auth(self) -> bool:
        """Anahtar geçersiz / süresi dolmuş / izin yok."""
        return self.code in (190, 10, 200, 2500) or (self.code == 100 and self.subcode == 33)


# ── anahtarı şifreli saklama (yalnızca standart kütüphane: HMAC-SHA256 CTR + etiket) ──
def _keys(secret: str) -> tuple[bytes, bytes]:
    s = secret.encode()
    return (hmac.new(s, b"smarity-ig-enc-v1", hashlib.sha256).digest(),
            hmac.new(s, b"smarity-ig-mac-v1", hashlib.sha256).digest())


def _stream(key: bytes, nonce: bytes, n: int) -> bytes:
    out, i = bytearray(), 0
    while len(out) < n:
        out += hmac.new(key, nonce + i.to_bytes(8, "big"), hashlib.sha256).digest()
        i += 1
    return bytes(out[:n])


def seal(secret: str, text: str) -> str:
    ek, mk = _keys(secret)
    nonce = os.urandom(16)
    data = text.encode()
    ct = bytes(a ^ b for a, b in zip(data, _stream(ek, nonce, len(data))))
    tag = hmac.new(mk, nonce + ct, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(nonce + ct + tag).decode()


def unseal(secret: str, blob: str) -> str | None:
    try:
        raw = base64.urlsafe_b64decode(blob.encode())
    except (ValueError, TypeError):
        return None
    if len(raw) < 48:
        return None
    ek, mk = _keys(secret)
    nonce, ct, tag = raw[:16], raw[16:-32], raw[-32:]
    if not hmac.compare_digest(tag, hmac.new(mk, nonce + ct, hashlib.sha256).digest()):
        return None
    return bytes(a ^ b for a, b in zip(ct, _stream(ek, nonce, len(ct)))).decode()


def fingerprint(secret: str) -> str:
    return hashlib.sha256(("smarity-ig-fp:" + secret).encode()).hexdigest()[:12]


# ── API istemcisi ──
class Instagram:
    def __init__(self, token: str, version: str = VERSION, timeout: int = 60):
        self.token = token
        self.base = f"{API}/{version}"
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {token}"

    def _clean(self, text: str) -> str:
        return str(text).replace(self.token, "***") if self.token else str(text)

    def _req(self, method: str, path: str, **params) -> dict:
        url = path if path.startswith("http") else f"{self.base}/{path.lstrip('/')}"
        try:
            if method == "GET":
                r = self.s.get(url, params=params, timeout=self.timeout)
            else:
                r = self.s.post(url, data=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise InstagramError(self._clean(f"Bağlantı hatası: {type(e).__name__}"), transient=True) from None
        try:
            j = r.json()
        except ValueError:
            j = {}
        if r.status_code >= 400 or "error" in j:
            err = j.get("error") or {}
            msg = err.get("error_user_msg") or err.get("message") or f"HTTP {r.status_code}"
            raise InstagramError(self._clean(msg), err.get("code"), err.get("error_subcode"),
                                 transient=r.status_code >= 500 or bool(err.get("is_transient")) or err.get("code") in (1, 2, 4, 9007))
        return j

    def me(self) -> dict:
        return self._req("GET", "me", fields="user_id,username")

    def container(self, ig_id: str, **params) -> str:
        return self._req("POST", f"{ig_id}/media", **params)["id"]

    def wait(self, cid: str, tries: int = 30, delay: float = 3) -> None:
        for _ in range(tries):
            st = self._req("GET", cid, fields="status_code,status").get("status_code")
            if st in ("FINISHED", "PUBLISHED"):
                return
            if st in ("ERROR", "EXPIRED"):
                raise InstagramError(f"Instagram görseli işleyemedi ({st})")
            time.sleep(delay)
        raise InstagramError("Instagram görseli zamanında işlemedi", transient=True)

    def publish(self, ig_id: str, cid: str) -> str:
        last = None
        for i in range(4):
            try:
                return self._req("POST", f"{ig_id}/media_publish", creation_id=cid)["id"]
            except InstagramError as e:  # kapsayıcı henüz hazır değilse kısa bekle
                last = e
                if not e.transient and e.code != 9007:
                    raise
                time.sleep(4 * (i + 1))
        raise last  # type: ignore[misc]

    def permalink(self, mid: str) -> str:
        try:
            return self._req("GET", mid, fields="permalink").get("permalink", "")
        except InstagramError:
            return ""

    def carousel(self, ig_id: str, urls: list[str], caption: str) -> tuple[str, str]:
        if len(urls) == 1:
            cid = self.container(ig_id, image_url=urls[0], caption=caption)
        else:
            kids = [self.container(ig_id, image_url=u, is_carousel_item="true") for u in urls]
            for k in kids:
                self.wait(k)
            cid = self.container(ig_id, media_type="CAROUSEL", children=",".join(kids), caption=caption)
        self.wait(cid)
        mid = self.publish(ig_id, cid)
        return mid, self.permalink(mid)

    def story(self, ig_id: str, url: str) -> str:
        cid = self.container(ig_id, media_type="STORIES", image_url=url)
        self.wait(cid)
        return self.publish(ig_id, cid)

    def refresh(self) -> tuple[str, int]:
        """Uzun ömürlü anahtarı 60 gün uzatır (anahtar en az 24 saatlik olmalı)."""
        s = requests.Session()
        try:
            r = s.get(f"{API}/refresh_access_token", params={"grant_type": "ig_refresh_token",
                                                             "access_token": self.token}, timeout=self.timeout)
            j = r.json()
        except (requests.RequestException, ValueError) as e:
            raise InstagramError(self._clean(f"Yenileme bağlantı hatası: {type(e).__name__}"), transient=True) from None
        if "access_token" not in j:
            err = j.get("error") or {}
            raise InstagramError(self._clean(err.get("message") or f"HTTP {r.status_code}"), err.get("code"),
                                 err.get("error_subcode"))
        return j["access_token"], int(j.get("expires_in") or 0)


class TokenStore:
    """Gizli anahtar + (varsa) yenilenmiş anahtarın şifreli kopyası."""

    def __init__(self, secret: str, data: dict):
        self.secret = secret
        self.data = data  # data/instagram.json içeriği (yerinde güncellenir)

    @property
    def token(self) -> str:
        if self.data.get("fp") == fingerprint(self.secret) and self.data.get("token"):
            t = unseal(self.secret, self.data["token"])
            if t:
                return t
        return self.secret

    def save(self, token: str, expires_in: int) -> None:
        fp = fingerprint(self.secret)
        if self.data.get("fp") != fp:  # gizli anahtar değişmiş: eski kayıtları unut
            for k in ("user_id", "username", "expires_at"):
                self.data.pop(k, None)
        self.data.update({"fp": fp, "token": seal(self.secret, token), "refreshed_at": iso(now_utc())})
        if expires_in:
            self.data["expires_at"] = iso(now_utc() + timedelta(seconds=expires_in))

    def days_left(self) -> float | None:
        exp = parse_iso(self.data.get("expires_at")) if self.data.get("fp") == fingerprint(self.secret) else None
        if not exp:
            return None
        return (exp - now_utc()).total_seconds() / 86400

    def refresh_due(self) -> bool:
        fresh = self.data.get("fp") == fingerprint(self.secret)
        last = parse_iso(self.data.get("refreshed_at")) if fresh else None
        tried = parse_iso(self.data.get("refresh_tried_at"))
        if tried and (now_utc() - tried) < timedelta(hours=12):
            return False
        return not last or (now_utc() - last) > timedelta(days=7)


def head_ok(url: str) -> int:
    """Görsel herkese açık mı? HTTP durum kodu (bağlantı hatasında 0)."""
    try:
        r = requests.head(url, timeout=20, allow_redirects=True)
        if r.status_code == 200 and "image" not in r.headers.get("content-type", "image"):
            return 415
        return r.status_code
    except requests.RequestException:
        return 0


def log_error(prefix: str, e: Exception) -> None:
    log.warning("%s: %s", prefix, e)
