SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -692,2 +692,5 @@
   cf_account_id: "8b50a495bf0914524b1e3d8a5208dc3b"
   cf_site_tag: "6e2bf0fdd8b84422b162de09fa63eacd"
+  # Google arama verisi (Search Console): GitHub'da GSC_SERVICE_ACCOUNT sırrı (hizmet hesabının JSON anahtarı) gerekir;
+  # hizmet hesabı Search Console → Ayarlar → Kullanıcılar ve izinler'e "Kısıtlı" olarak eklenir.
+  gsc_site: "https://smarity.com.tr/"
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -2265,4 +2265,12 @@
         else:
             lines += ["👥 Okur verisi için Cloudflare anahtarı (CLOUDFLARE_API_TOKEN) tanımlı değil.", ""]
+        if rc.get("gsc_site"):
+            try:
+                sa = reportmod.gsc_credentials()
+                if sa:
+                    g = reportmod.fetch_gsc(sa, str(rc["gsc_site"]), a, b)
+                    lines += reportmod.search_block(g, self._path_titles(), cfg.site_url, esc) + [""]
+            except reportmod.ReportError as e:
+                lines += [f"🔎 Google arama verisi alınamadı: {esc(str(e))}", ""]
 
         def in_week(ts) -> bool:
--- a/haberbot/report.py
+++ b/haberbot/report.py
@@ -2,10 +2,16 @@
 
 Okur verisi için CLOUDFLARE_API_TOKEN gerekir (yalnızca "Account Analytics: Read" yetkili, salt okunur anahtar).
-Anahtar yoksa rapor yalnızca yayın özetiyle gider.
+Google arama verisi için GSC_SERVICE_ACCOUNT gerekir (Search Console'a "Kısıtlı" kullanıcı olarak eklenmiş bir Google
+hizmet hesabının JSON anahtarı; yalnızca okuma kapsamı istenir). Anahtarlar yoksa o bölümler raporda yer almaz.
 """
 from __future__ import annotations
 
+import base64
+import hashlib
+import json
 import os
+import time
 from datetime import date, timedelta
+from urllib.parse import quote
 
 import requests
@@ -135,2 +141,132 @@
         out += [f"{i}. {esc(t[:80])} — {fmt(n)}" for i, (t, n) in enumerate(pages[:6], 1)]
     return out
+
+
+# ── Google Search Console ────────────────────────────────────
+GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
+GSC_TOKEN_URL = "https://oauth2.googleapis.com/token"
+GSC_API = "https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
+_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")   # PKCS#1 v1.5 DigestInfo (SHA-256)
+
+
+def gsc_credentials() -> dict | None:
+    raw = (os.environ.get("GSC_SERVICE_ACCOUNT") or "").strip()
+    if not raw:
+        return None
+    try:
+        sa = json.loads(raw)
+    except ValueError as e:
+        raise ReportError("GSC_SERVICE_ACCOUNT okunamadı: JSON anahtar dosyasının tamamı yapıştırılmalı.") from e
+    if not sa.get("client_email") or "PRIVATE KEY" not in (sa.get("private_key") or ""):
+        raise ReportError("GSC_SERVICE_ACCOUNT eksik: client_email ve private_key alanları olmalı.")
+    return sa
+
+
+def _der(b: bytes, i: int) -> tuple[int, int, int]:
+    """DER öğesi: (etiket, içerik başı, içerik sonu)."""
+    tag, ln = b[i], b[i + 1]
+    i += 2
+    if ln & 0x80:
+        n = ln & 0x7F
+        ln = int.from_bytes(b[i:i + n], "big")
+        i += n
+    return tag, i, i + ln
+
+
+def _rsa_key(pem: str) -> tuple[int, int]:
+    """PEM (PKCS#8 ya da PKCS#1) RSA özel anahtarından (n, d)."""
+    body = "".join(ln.strip() for ln in pem.strip().splitlines() if ln.strip() and not ln.startswith("-----"))
+    der = base64.b64decode(body)
+    _, s, _ = _der(der, 0)                 # SEQUENCE
+    _, _, e1 = _der(der, s)                # version
+    t2, _, e2 = _der(der, e1)
+    if t2 == 0x30:                         # PKCS#8: AlgorithmIdentifier, ardından OCTET STRING içinde PKCS#1
+        _, s3, e3 = _der(der, e2)
+        der = der[s3:e3]
+        _, s, _ = _der(der, 0)
+        _, _, e1 = _der(der, s)
+    i, vals = e1, []
+    for _ in range(3):                     # n, e, d
+        _, a, b = _der(der, i)
+        vals.append(int.from_bytes(der[a:b], "big"))
+        i = b
+    return vals[0], vals[2]
+
+
+def rs256(msg: bytes, pem: str) -> bytes:
+    """RSASSA-PKCS1-v1_5 + SHA-256 imzası (Google hizmet hesabı JWT'si için)."""
+    n, d = _rsa_key(pem)
+    k = (n.bit_length() + 7) // 8
+    t = _SHA256_PREFIX + hashlib.sha256(msg).digest()
+    em = b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t
+    return pow(int.from_bytes(em, "big"), d, n).to_bytes(k, "big")
+
+
+def _b64(b: bytes) -> bytes:
+    return base64.urlsafe_b64encode(b).rstrip(b"=")
+
+
+def gsc_access_token(sa: dict) -> str:
+    now = int(time.time())
+    head = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
+    claim = _b64(json.dumps({"iss": sa["client_email"], "scope": GSC_SCOPE, "aud": GSC_TOKEN_URL,
+                             "iat": now, "exp": now + 3600}, separators=(",", ":")).encode())
+    msg = head + b"." + claim
+    try:
+        jwt = msg + b"." + _b64(rs256(msg, sa["private_key"]))
+    except (ValueError, IndexError) as e:
+        raise ReportError("Hizmet hesabı anahtarı çözülemedi.") from e
+    try:
+        r = requests.post(GSC_TOKEN_URL, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
+                                               "assertion": jwt.decode()}, timeout=30)
+    except requests.RequestException as e:
+        raise ReportError(f"Google'a ulaşılamadı: {e}") from e
+    tok = (r.json() if r.headers.get("content-type", "").startswith("application/json") else {}).get("access_token")
+    if not tok:
+        raise ReportError(f"Google oturumu açılamadı (HTTP {r.status_code}); hizmet hesabı anahtarı geçerli mi?")
+    return tok
+
+
+def _gsc_rows(token: str, site: str, body: dict) -> list[dict]:
+    try:
+        r = requests.post(GSC_API.format(site=quote(site, safe="")), json=body,
+                          headers={"Authorization": f"Bearer {token}"}, timeout=40)
+    except requests.RequestException as e:
+        raise ReportError(f"Search Console'a ulaşılamadı: {e}") from e
+    if r.status_code == 403:
+        raise ReportError("Hizmet hesabı Search Console'da bu siteye kullanıcı olarak eklenmemiş.")
+    if r.status_code != 200:
+        raise ReportError(f"Search Console hatası (HTTP {r.status_code}).")
+    return r.json().get("rows") or []
+
+
+def fetch_gsc(sa: dict, site: str, a: date, b: date) -> dict:
+    tok = gsc_access_token(sa)
+    span_ = lambda x, y: {"startDate": x.isoformat(), "endDate": y.isoformat(), "dataState": "all"}  # noqa: E731
+    return {"cur": (_gsc_rows(tok, site, span_(a, b)) or [{}])[0],
+            "prev": (_gsc_rows(tok, site, span_(a - timedelta(days=7), a - timedelta(days=1))) or [{}])[0],
+            "queries": _gsc_rows(tok, site, {**span_(a, b), "dimensions": ["query"], "rowLimit": 8}),
+            "pages": _gsc_rows(tok, site, {**span_(a, b), "dimensions": ["page"], "rowLimit": 5})}
+
+
+def search_block(g: dict, titles: dict[str, str], site_url: str, esc) -> list[str]:
+    cur, prev = g.get("cur") or {}, g.get("prev") or {}
+    imp, clk = int(cur.get("impressions") or 0), int(cur.get("clicks") or 0)
+    pos = (", ort. sıra " + f"{cur['position']:.1f}".replace(".", ",")) if cur.get("position") else ""
+    out = ["<b>🔎 Google araması</b> <i>(Search Console)</i>",
+           f"Gösterim: <b>{fmt(imp)}</b>{change(imp, int(prev.get('impressions') or 0))}",
+           f"Tıklama: {fmt(clk)}{change(clk, int(prev.get('clicks') or 0))}{pos}"]
+    qs = sorted(g.get("queries") or [], key=lambda r: -(r.get("impressions") or 0))
+    if qs:
+        out += ["En çok gösterim alan aramalar:"]
+        out += [f"• {esc(str((r.get('keys') or [''])[0])[:60])} — {fmt(int(r.get('impressions') or 0))} gösterim"
+                + (f", {fmt(int(r.get('clicks') or 0))} tık" if r.get("clicks") else "") for r in qs[:6]]
+    ps = sorted(g.get("pages") or [], key=lambda r: -(r.get("impressions") or 0))
+    if ps:
+        base = site_url.rstrip("/")
+        out += ["Google'da en çok görünen sayfalar:"]
+        for r in ps[:3]:
+            url = str((r.get("keys") or [""])[0])
+            path = url[len(base):] if url.startswith(base) else url
+            out.append(f"• {esc((titles.get(path) or path)[:70])} — {fmt(int(r.get('impressions') or 0))} gösterim")
+    return out
--- a/tests/test_report.py
+++ b/tests/test_report.py
@@ -68,2 +68,67 @@
         a.maybe_weekly_report()
         assert (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8").count("Haftalık rapor") == 1
+
+
+def test_rs256_matches_standard_library():
+    import pytest
+    crypto = pytest.importorskip("cryptography")  # noqa: F841
+    from cryptography.hazmat.primitives import hashes, serialization
+    from cryptography.hazmat.primitives.asymmetric import padding, rsa
+    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
+    for fmt in (serialization.PrivateFormat.PKCS8, serialization.PrivateFormat.TraditionalOpenSSL):
+        pem = key.private_bytes(serialization.Encoding.PEM, fmt, serialization.NoEncryption()).decode()
+        msg = b"header.claim"
+        assert R.rs256(msg, pem) == key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
+
+
+GSC = {"cur": {"clicks": 12, "impressions": 1500, "position": 11.84}, "prev": {"clicks": 6, "impressions": 3000},
+       "queries": [{"keys": ["togg fiyat listesi"], "impressions": 400, "clicks": 5},
+                   {"keys": ["imei kayıt ücreti"], "impressions": 900, "clicks": 0}],
+       "pages": [{"keys": ["https://smarity.com.tr/rehber/togg-fiyat-listesi/"], "impressions": 300}]}
+
+
+def test_search_block_in_report(monkeypatch):
+    with _App() as (cfg, a):
+        monkeypatch.setenv("GSC_SERVICE_ACCOUNT", json.dumps({"client_email": "x@y", "private_key": "-----BEGIN PRIVATE KEY-----"}))
+        monkeypatch.setattr(R, "fetch_gsc", lambda *_a: GSC)
+        cfg.raw.setdefault("report", {})["gsc_site"] = "https://smarity.com.tr/"
+        t = a.weekly_report_text()
+        assert "Gösterim: <b>1.500</b> (önceki hafta 3.000, -%50)" in t
+        assert "Tıklama: 12 (önceki hafta 6, +%100), ort. sıra 11,8" in t
+        assert t.index("imei kayıt ücreti") < t.index("togg fiyat listesi")          # gösterime göre sıralı
+        assert "/rehber/togg-fiyat-listesi/ — 300 gösterim" in t
+        monkeypatch.setenv("GSC_SERVICE_ACCOUNT", "yanlış")
+        assert "Google arama verisi alınamadı" in a.weekly_report_text()
+        monkeypatch.delenv("GSC_SERVICE_ACCOUNT")
+        assert "Google araması" not in a.weekly_report_text()                       # anahtar yoksa bölüm yok
+
+
+def test_gsc_token_request_is_valid_jwt(monkeypatch):
+    import base64 as b64
+    import pytest
+    pytest.importorskip("cryptography")
+    from cryptography.hazmat.primitives import hashes, serialization
+    from cryptography.hazmat.primitives.asymmetric import padding, rsa
+    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
+    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
+                            serialization.NoEncryption()).decode()
+    sent = {}
+
+    class Resp:
+        status_code = 200
+        headers = {"content-type": "application/json; charset=utf-8"}
+
+        def json(self):
+            return {"access_token": "ya29.test"}
+
+    def post(url, data=None, **_k):
+        sent.update(url=url, **data)
+        return Resp()
+    monkeypatch.setattr(R.requests, "post", post)
+    assert R.gsc_access_token({"client_email": "rapor@proje.iam.gserviceaccount.com", "private_key": pem}) == "ya29.test"
+    head, claim, sig = sent["assertion"].split(".")
+    pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
+    key.public_key().verify(b64.urlsafe_b64decode(pad(sig)), f"{head}.{claim}".encode(), padding.PKCS1v15(), hashes.SHA256())
+    c = json.loads(b64.urlsafe_b64decode(pad(claim)))
+    assert c["iss"].startswith("rapor@") and c["scope"].endswith("webmasters.readonly") and c["exp"] - c["iat"] == 3600
+    assert sent["url"] == R.GSC_TOKEN_URL and sent["grant_type"].endswith("jwt-bearer")
@@@SM@@@ SHA
a651a0a0fbe745cf8741874e82bbb132cada1680b7d786ed404a071955997a62 config.yaml
3ce023d8d0cea4747ee1f02e66e8b1f4998faadd6ff668c83ad5313dc6f7de36 haberbot/app.py
865b1214cda7a60eada0e3d065b97ce30d9a2975f7d8eb45be9507f8b00c3181 haberbot/report.py
c6a0803002867086e9959382eeeacb7f1ff081c7bbb9e20b4d40954dbaa8d508 tests/test_report.py
