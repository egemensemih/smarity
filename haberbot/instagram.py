"""Instagram otomatik paylaşım (Instagram API with Instagram Login ya da Meta'nın yeni "Unified login" kurulumu).

Akış: haber yayınlanınca sıraya girer → site yayınlanırken kartlar _site/ig/ altına konur →
bir sonraki turda Instagram bu herkese açık JPEG'leri alır ve carousel + hikâye paylaşılır.

Erişim anahtarı (IG_ACCESS_TOKEN) GitHub'da gizli anahtar olarak durur. 60 günlük anahtar bot tarafından
düzenli yenilenir; yenilenen anahtar yalnızca asıl gizli anahtarla açılabilecek şekilde şifrelenip
data/instagram.json dosyasına yazılır (depoda düz metin anahtar yoktur).

Meta'nın yeni uygulamalarda verdiği sistem kullanıcısı anahtarı ("EAA…" ile başlar, süresi dolmaz) graph.facebook.com
üzerinden çalışır: hesap numarası ayarlardan (social.instagram_user_id) alınır ya da anahtarın eriştiği hesaplardan bulunur.

IG_ACCESS_TOKEN'da Meta anahtarı yerine Zernio API anahtarı varsa paylaşım Zernio üzerinden yapılır (Zernio sınıfı):
kendi Meta uygulamamız gerekmez, Instagram hesabı Zernio panelinde bağlanır.
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
FB_API = "https://graph.facebook.com"
VERSION = "v25.0"


def is_fb_token(token: str) -> bool:
    """Facebook Graph anahtarı mı (sistem kullanıcısı / Facebook girişi)? Instagram girişi anahtarları "IG" ile başlar."""
    return str(token or "").startswith("EAA")


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
    def __init__(self, token: str, version: str = VERSION, timeout: int = 60, ig_id: str = ""):
        self.token = token
        self.fb = is_fb_token(token)
        self.ig_id = str(ig_id or "")
        self.base = f"{FB_API if self.fb else API}/{version}"
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

    def _discover(self) -> str:
        """Anahtarın eriştiği Facebook sayfalarına bağlı ilk Instagram işletme hesabının numarası."""
        pages = self._req("GET", "me/accounts", fields="instagram_business_account{id,username}").get("data") or []
        return next((str(p["instagram_business_account"]["id"]) for p in pages if p.get("instagram_business_account")), "")

    def me(self) -> dict:
        if not self.fb:
            return self._req("GET", "me", fields="user_id,username")
        ig_id = self.ig_id
        if ig_id:
            try:
                j = self._req("GET", ig_id, fields="id,username")
            except InstagramError as e:
                # numara yanlışsa ya da bu anahtara atanmamışsa: anahtarın gördüğü sayfalardan bulmayı dene
                if e.transient:
                    raise
                try:
                    found = self._discover()
                except InstagramError:
                    found = ""
                if not found or found == ig_id:
                    raise e
                log.warning("Instagram hesap numarası %s okunamadı (%s); anahtarın eriştiği hesap %s kullanılacak",
                            ig_id, e, found)
                ig_id = found
                j = self._req("GET", ig_id, fields="id,username")
        else:  # anahtarın eriştiği sayfalara bağlı ilk Instagram hesabı
            ig_id = self._discover()
            if not ig_id:
                raise InstagramError("Anahtarın eriştiği bir Instagram hesabı bulunamadı; config.yaml → "
                                     "social.instagram_user_id alanına hesap numarasını yaz", 100)
            j = self._req("GET", ig_id, fields="id,username")
        return {"id": str(j.get("id") or ig_id), "user_id": str(j.get("id") or ig_id), "username": j.get("username", "")}

    def diagnose(self) -> dict:
        """Anahtarın ne gördüğü (anahtarın kendisi yazılmaz): kimlik, verilen izinler, erişilen sayfalar ve bağlı
        Instagram hesapları. Bağlantı kurulamadığında sorunun anahtar mı, izin mi, hesap ataması mı olduğunu gösterir."""
        out: dict = {"kind": "facebook" if self.fb else "instagram"}

        def safe(key, fn):
            try:
                out[key] = fn()
            except InstagramError as e:
                out[key] = {"error": str(e)[:200], "code": e.code, "subcode": e.subcode}

        if self.fb:
            safe("me", lambda: {k: v for k, v in self._req("GET", "me", fields="id,name").items() if k in ("id", "name")})
            safe("perms", lambda: sorted(x["permission"] for x in self._req("GET", "me/permissions").get("data") or []
                                         if x.get("status") == "granted"))
            safe("pages", lambda: [{"name": p.get("name", ""),
                                    "ig": (p.get("instagram_business_account") or {}).get("username")
                                    or (p.get("instagram_business_account") or {}).get("id") or ""}
                                   for p in self._req("GET", "me/accounts",
                                                      fields="name,instagram_business_account{id,username}").get("data") or []])
        else:
            safe("me", lambda: self._req("GET", "me", fields="user_id,username"))
        return out

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
        if self.fb:
            raise InstagramError("Sistem kullanıcısı anahtarının süresi dolmaz, yenilenmez")
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


# ── Zernio: Meta onaylı uygulaması olan paylaşım servisi (kendi Meta uygulamamız gerekmez) ──
ZERNIO_API = "https://zernio.com/api/v1"


def is_meta_token(token: str) -> bool:
    """Meta'nın kendi anahtarları "EAA" (Facebook) ya da "IG" (Instagram girişi) ile başlar; diğerleri Zernio anahtarıdır."""
    return str(token or "").startswith(("EAA", "IG"))


class Zernio:
    """Zernio REST API üzerinden Instagram'a gönderi (carousel) ve hikâye. Görseller herkese açık adresten alınır.
    Arayüz Instagram sınıfıyla aynıdır (me / carousel / story / diagnose); hedef, Zernio'daki hesap numarasıdır."""
    kind = "zernio"
    fb = False
    ref = ""   # paylaşılan haberin kimliği + deneme sayısı (bot her paylaşımdan önce koyar): çift paylaşımı önler

    def __init__(self, key: str, account_id: str = "", timeout: int = 90):
        self.key = key
        self.ig_id = str(account_id or "")
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {key}", "Content-Type": "application/json"})

    def _clean(self, text: str) -> str:
        return str(text).replace(self.key, "***") if self.key else str(text)

    def _req(self, method: str, path: str, body: dict | None = None, params: dict | None = None,
             idem: str = "") -> dict:
        headers = {"Idempotency-Key": idem} if idem else {}
        try:
            r = self.s.request(method, f"{ZERNIO_API}/{path.lstrip('/')}", json=body, params=params,
                               headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            raise InstagramError(self._clean(f"Zernio bağlantı hatası: {type(e).__name__}"), transient=True) from None
        try:
            j = r.json()
        except ValueError:
            j = {}
        if r.status_code >= 400:
            err = j.get("error") if isinstance(j.get("error"), dict) else j
            msg = (err.get("message") if isinstance(err, dict) else None) or j.get("error") or f"HTTP {r.status_code}"
            perr = (err.get("platformError") if isinstance(err, dict) else None) or j.get("platformError")
            if perr:
                msg = f"{msg} ({perr if isinstance(perr, str) else perr.get('message', perr)})"
            code = {401: 190, 403: 200, 422: 200}.get(r.status_code)     # yetki sorunları: anahtar / hesap bağlantısı
            raise InstagramError(self._clean(f"Zernio: {msg}"), code,
                                 transient=r.status_code in (429, 500, 502, 503, 504))
        return j if isinstance(j, dict) else {"data": j}

    @staticmethod
    def _items(j) -> list[dict]:
        if isinstance(j, list):
            return j
        for k in ("accounts", "data", "items", "results"):
            if isinstance(j.get(k), list):
                return j[k]
        return []

    def accounts(self) -> list[dict]:
        out = []
        for a in self._items(self._req("GET", "accounts")):
            if not isinstance(a, dict):
                continue
            out.append({"id": str(a.get("_id") or a.get("id") or a.get("accountId") or ""),
                        "platform": str(a.get("platform") or "").lower(),
                        "username": a.get("username") or a.get("handle") or a.get("name") or a.get("displayName") or "",
                        "active": a.get("isActive", a.get("active", True)) is not False})
        return out

    def me(self) -> dict:
        igs = [a for a in self.accounts() if a["platform"] == "instagram" and a["id"]]
        if self.ig_id:
            igs = [a for a in igs if a["id"] == self.ig_id] or igs
        if not igs:
            raise InstagramError("Zernio'da bağlı Instagram hesabı yok: Zernio panelinde Instagram'ı bağla", 200)
        a = igs[0]
        return {"id": a["id"], "user_id": a["id"], "username": a["username"]}

    def _publish(self, body: dict, idem: str) -> tuple[str, str]:
        j = self._req("POST", "posts", body, idem=idem)
        post = j.get("post") if isinstance(j.get("post"), dict) else j
        pid = str(post.get("_id") or post.get("id") or "")
        plats = [p for p in post.get("platforms") or [] if isinstance(p, dict)] or [post]
        p = plats[0]
        st = str(p.get("status") or post.get("status") or "").lower()
        if st in ("failed", "cancelled"):
            perr = p.get("platformError") or p.get("error") or post.get("error") or st
            raise InstagramError(self._clean(f"Zernio: Instagram paylaşımı başarısız ({perr})"))
        return pid, str(p.get("platformPostUrl") or "")

    def carousel(self, account_id: str, urls: list[str], caption: str) -> tuple[str, str]:
        body = {"content": caption, "mediaItems": [{"type": "image", "url": u} for u in urls],
                "platforms": [{"platform": "instagram", "accountId": account_id}], "publishNow": True}
        if self.ref:
            body["externalId"] = f"{self.ref}-post"
        return self._publish(body, self._idem(self.ref or urls[0], "post"))

    def story(self, account_id: str, url: str) -> str:
        body = {"mediaItems": [{"type": "image", "url": url}],
                "platforms": [{"platform": "instagram", "accountId": account_id,
                               "platformSpecificData": {"contentType": "story"}}],
                "publishNow": True}
        if self.ref:
            body["externalId"] = f"{self.ref}-story"
        return self._publish(body, self._idem(self.ref or url, "story"))[0]

    @staticmethod
    def _idem(ref: str, kind: str) -> str:
        """Aynı haberin aynı biçimi iki kez gönderilmesin (zaman aşımı sonrası yeniden denemede çift paylaşım olmaz)."""
        import uuid
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"smarity:{ref}:{kind}"))

    def diagnose(self) -> dict:
        out: dict = {"kind": "zernio"}
        try:
            out["accounts"] = [f"{a['platform']}:{a['username'] or a['id']}" for a in self.accounts()]
        except InstagramError as e:
            out["accounts"] = {"error": str(e)[:200], "code": e.code}
        return out

    def refresh(self) -> tuple[str, int]:
        raise InstagramError("Zernio anahtarı yenilenmez")


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
