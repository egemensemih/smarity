"""Yapay zeka istemcileri: Google Gemini (ücretsiz), Claude (isteğe bağlı) + test için sahte mod."""
from __future__ import annotations

import json
import re
import time

import requests

from .util import log

API_URL = "https://api.anthropic.com/v1/messages"

# Tahmini fiyatlar ($ / 1M token): maliyet raporu içindir, faturalamayı etkilemez.
PRICES = {
    "haiku": (1.0, 5.0),
    "sonnet": (2.0, 10.0),
    "opus": (4.0, 20.0),
    "fable": (10.0, 50.0),
}


def estimate_cost(model: str, tok_in: int, tok_out: int) -> float:
    if model.startswith("gemini") or model.startswith("gemma"):
        return 0.0  # ücretsiz katman
    for k, (pi, po) in PRICES.items():
        if k in model:
            return tok_in / 1e6 * pi + tok_out / 1e6 * po
    return tok_in / 1e6 * 3 + tok_out / 1e6 * 15


class LLMError(RuntimeError):
    pass


class LLM:
    def __init__(self, api_key: str, usage_cb=None):
        self.api_key = api_key
        self.usage_cb = usage_cb  # (model, in, out) → None

    def _post(self, body: dict) -> dict:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        delays = [5, 20, 60]
        for attempt in range(len(delays) + 1):
            try:
                r = requests.post(API_URL, headers=headers, json=body, timeout=300)
            except requests.RequestException as e:
                if attempt < len(delays):
                    time.sleep(delays[attempt])
                    continue
                raise LLMError(f"Bağlantı hatası: {e}") from e
            if r.status_code in (429, 500, 502, 503, 504, 529) and attempt < len(delays):
                log.warning("Claude API %s, %ss sonra tekrar denenecek", r.status_code, delays[attempt])
                time.sleep(delays[attempt])
                continue
            if r.status_code >= 400:
                try:
                    msg = r.json().get("error", {}).get("message", r.text)
                except ValueError:
                    msg = r.text
                raise LLMError(f"HTTP {r.status_code}: {msg[:300]}")
            return r.json()
        raise LLMError("Tekrar denemeler tükendi")

    def json(self, model: str, system: str, user: str, schema: dict,
             max_tokens: int = 4000, effort: str | None = None) -> dict:
        """Şemaya uyan JSON döndürür. Model/sürüm farklarına karşı kademeli geri çekilir."""
        use_effort = bool(effort) and "haiku" not in model
        variants = []
        oc = {"format": {"type": "json_schema", "schema": schema}}
        if use_effort:
            variants.append({**oc, "effort": effort})
        variants.append(oc)
        variants.append(None)  # yapılandırılmış çıktı yoksa: şemayı talimata ekle

        last_err: Exception | None = None
        for oc_variant in variants:
            body = {
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
            if oc_variant is not None:
                body["output_config"] = oc_variant
            else:
                body["system"] = system + (
                    "\n\nReturn ONLY a JSON object (no prose, no code fences) matching this JSON schema:\n"
                    + json.dumps(schema, ensure_ascii=False))
            try:
                resp = self._post(body)
            except LLMError as e:
                last_err = e
                if "HTTP 400" in str(e):
                    log.info("Claude isteği bu biçimle kabul edilmedi, sade biçim deneniyor: %s", e)
                    continue
                raise
            usage = resp.get("usage") or {}
            if self.usage_cb:
                self.usage_cb(model, int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)))
            if resp.get("stop_reason") == "max_tokens":
                raise LLMError("Yanıt token sınırına takıldı")
            text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
            try:
                return _parse_json(text)
            except ValueError as e:
                last_err = LLMError(f"JSON çözümlenemedi: {e}; metin: {text[:200]}")
                continue
        raise LLMError(str(last_err))


# ── Google Gemini (ücretsiz katman) ─────────────────────────
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_LIST_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_FALLBACKS = ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
_FLASH_RE = re.compile(r"^gemini-(?P<ver>\d+(?:\.\d+)?)-flash(?P<lite>-lite)?(?P<pre>-preview)?(?P<date>-\d{2}-\d{4})?(?:-\d{3})?$")


def _gemini_schema(schema, upper: bool):
    """JSON şemasını Gemini'nin kabul ettiği alt kümeye indir."""
    if isinstance(schema, dict):
        out = {}
        for k, v in schema.items():
            if k == "additionalProperties":
                continue
            if k == "type" and isinstance(v, str):
                out[k] = v.upper() if upper else v
            else:
                out[k] = _gemini_schema(v, upper)
        return out
    if isinstance(schema, list):
        return [_gemini_schema(v, upper) for v in schema]
    return schema


class GeminiLLM:
    """Google Gemini API: ücretsiz katmanda kredi kartı gerektirmez (dakika/gün sınırlıdır)."""

    min_interval = 6.0  # ücretsiz katman: model başına dakikada ~10 istek

    def __init__(self, api_key: str, usage_cb=None):
        self.api_key = api_key
        self.usage_cb = usage_cb
        self._last: dict[str, float] = {}  # model başına son istek zamanı
        self._model_ok: dict[str, str] = {}
        self._variant_ok: dict[str, int] = {}
        self._busy: set[str] = set()  # bu turda yoğunluk/sınır hatası veren modeller
        self._dead: set[str] = set()  # bu hesapta çalışmayan (404) modeller
        self._avail: list[str] | None = None

    def _post(self, model: str, body: dict) -> dict:
        """Tek deneme. Yoğunluk/sınır hatasında beklemeden hata verir; json() hemen sıradaki modele geçer."""
        wait = self.min_interval - (time.time() - self._last.get(model, 0.0))
        if wait > 0:
            time.sleep(wait)
        self._last[model] = time.time()
        try:
            r = requests.post(GEMINI_URL.format(model=model), json=body, timeout=240,
                              headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"})
        except requests.RequestException as e:
            raise LLMError(f"Bağlantı hatası: {e}") from e
        if r.status_code >= 400:
            raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def _available(self) -> list[str]:
        """Hesapta kullanılabilen Gemini metin modellerini bir kez sorgula (yeni modeller kendiliğinden gelir)."""
        if self._avail is None:
            self._avail = []
            try:
                r = requests.get(GEMINI_LIST_URL, params={"pageSize": 1000}, timeout=30,
                                 headers={"x-goog-api-key": self.api_key})
                if r.ok:
                    for m in r.json().get("models", []):
                        if "generateContent" in (m.get("supportedGenerationMethods") or []):
                            self._avail.append(m.get("name", "").removeprefix("models/"))
            except (requests.RequestException, ValueError):
                pass
        return self._avail

    @staticmethod
    def _rank(names: list[str], lite: bool) -> list[str]:
        """Flash modellerini en yeni sürümden eskiye sırala (kararlı sürüm önizlemeden önce)."""
        out = []
        for n in names:
            m = _FLASH_RE.match(n)
            if not m or bool(m.group("lite")) != lite:
                continue
            ver = tuple(int(x) for x in m.group("ver").split("."))
            out.append(((ver, not m.group("pre"), not m.group("date")), n))
        return [n for _, n in sorted(out, reverse=True)]

    def _models(self, model: str) -> list[str]:
        avail = self._available()
        flash, lite = self._rank(avail, False)[:3], self._rank(avail, True)[:2]
        order = [model] + (lite + flash if "lite" in model else flash + lite) + GEMINI_FALLBACKS
        if model in self._model_ok:  # son çalışan model önce denenir, ama diğerleri yedekte kalır
            order.insert(0, self._model_ok[model])
        order = list(dict.fromkeys(order))
        # yoğun olanlar sona
        return [m for m in order if m not in self._busy] + [m for m in order if m in self._busy]

    def json(self, model: str, system: str, user: str, schema: dict,
             max_tokens: int = 4000, effort: str | None = None) -> dict:
        base = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
        }
        gen = {"responseMimeType": "application/json", "maxOutputTokens": max(max_tokens, 8192)}
        variants = [
            {**gen, "responseJsonSchema": _gemini_schema(schema, upper=False)},
            {**gen, "responseSchema": _gemini_schema(schema, upper=True)},
            dict(gen),
        ]
        start = self._variant_ok.get(model, 0)
        variants = variants[start:] + variants[:start]
        last_err: Exception | None = None
        for rnd in range(2):  # tüm modeller meşgulse kısa bir aradan sonra bir tur daha
            if rnd:
                if not self._busy:
                    break
                log.warning("Tüm Gemini modelleri meşgul, 20 sn sonra bir tur daha denenecek")
                time.sleep(20)
            out = self._try_models(model, base, variants, schema, system)
            if isinstance(out, dict):
                return out
            last_err = out
        raise LLMError(("Tüm modeller meşgul: " if self._busy else "") + str(last_err))

    def _try_models(self, model: str, base: dict, variants: list[dict], schema: dict, system: str):
        """Modelleri sırayla dener; başarıda sonuç sözlüğünü, olmazsa son hatayı döndürür."""
        last_err: Exception | None = None
        for m in self._models(model):
            if m in self._dead:
                continue
            for gc in variants:
                body = {**base, "generationConfig": gc}
                if "responseJsonSchema" not in gc and "responseSchema" not in gc:
                    body["systemInstruction"] = {"parts": [{"text": system + (
                        "\n\nReturn ONLY a JSON object matching this JSON schema:\n" + json.dumps(schema, ensure_ascii=False))}]}
                try:
                    resp = self._post(m, body)
                except LLMError as e:
                    last_err = e
                    msg = str(e)
                    if "HTTP 404" in msg:
                        log.info("Gemini modeli bulunamadı (%s), sıradaki deneniyor", m)
                        self._dead.add(m)
                        break
                    if "HTTP 400" in msg:
                        continue
                    if re.search(r"HTTP (429|5\d\d)|Tekrar denemeler|Bağlantı", msg):
                        log.warning("Gemini %s meşgul/sınırda (%s), sıradaki model deneniyor", m, msg[:8])
                        self._busy.add(m)
                        break
                    raise
                usage = resp.get("usageMetadata") or {}
                if self.usage_cb:
                    self.usage_cb(m, int(usage.get("promptTokenCount", 0)), int(usage.get("candidatesTokenCount", 0)))
                cands = resp.get("candidates") or []
                if not cands:
                    reason = (resp.get("promptFeedback") or {}).get("blockReason", "boş yanıt")
                    raise LLMError(f"Gemini yanıt vermedi: {reason}")
                parts = (cands[0].get("content") or {}).get("parts") or []
                text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                if cands[0].get("finishReason") == "MAX_TOKENS":
                    last_err = LLMError("Yanıt token sınırına takıldı")
                    continue
                try:
                    out = _parse_json(text)
                    self._model_ok[model] = m
                    self._busy.discard(m)
                    self._variant_ok[model] = ("responseJsonSchema" not in gc) + ("responseSchema" not in gc and "responseJsonSchema" not in gc)
                    return out
                except ValueError as e:
                    last_err = LLMError(f"JSON çözümlenemedi: {e}; metin: {text[:200]}")
                    continue
        return last_err or LLMError("Uygun model bulunamadı")


def make_llm(cfg, usage_cb=None):
    """Ayarlara göre yapay zeka sağlayıcısını seç. Varsayılan: ücretsiz Gemini."""
    provider = (cfg.get("ai", "provider", "gemini") or "gemini").lower()
    if provider == "claude" and cfg.anthropic_key:
        return LLM(cfg.anthropic_key, usage_cb=usage_cb)
    if cfg.google_key:
        return GeminiLLM(cfg.google_key, usage_cb=usage_cb)
    if cfg.anthropic_key:
        return LLM(cfg.anthropic_key, usage_cb=usage_cb)
    return None


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ValueError("JSON bulunamadı")
        return json.loads(m.group(0))


# ── Sahte mod (yerel test için; gerçek API çağrısı yapmaz) ────────
_KW = [
    ("gaming", ("game", "gaming", "playstation", "xbox", "nintendo", "steam", "oyun", "gta", "esports")),
    ("girisimcilik", ("raises", "funding", "valuation", "series", "yatırım", "startup", "girişim", "seed")),
    ("inovasyon", ("research", "robot", "battery", "space", "first", "prototype", "drone", "study", "waymo", "autonomous")),
    ("super-zeka", ("ai ", "gpt", "gemini", "claude", "model", "openai", "anthropic", "yapay zeka", "llm")),
]


class MockLLM:
    def __init__(self, *a, **k):
        self.usage_cb = k.get("usage_cb")

    def json(self, model, system, user, schema, max_tokens=4000, effort=None) -> dict:
        if self.usage_cb:
            self.usage_cb(model, len(user) // 4, 300)
        if "stories" in schema.get("properties", {}):
            return self._triage(user)
        if "body" not in schema.get("properties", {}):  # yalnızca SEO bilgisi
            t = re.search(r"TITLE: (.+)", user)
            t = t.group(1) if t else "Haber"
            return {"focus_keyword": " ".join(t.split()[:3]), "seo_title": t[:58],
                    "meta_description": (t + ". Gelişmenin ayrıntıları, kaynağıyla ve Türkçe olarak Smarity'de.")[:156],
                    "image_alt": f"{t[:80]} haberini temsil eden 3D görsel", "tags": ["OpenAI", "Test"]}
        return self._write(user)

    @staticmethod
    def _cat(text: str) -> str:
        t = text.lower()
        for cat, kws in _KW:
            if any(k in t for k in kws):
                return cat
        return "teknoloji"

    def _triage(self, user: str) -> dict:
        stories = []
        section = user.split("NEW ITEMS:", 1)[-1]
        for line in section.strip().splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 4:
                continue
            tid, credit, _, title = parts[0], parts[1], parts[2], parts[3]
            imp = 8 if "(official)" in credit else 6
            if any(k in title.lower() for k in ("summit", "agenda", "podcast", "webinar")):
                imp = 3
            stories.append({"item_ids": [tid], "topic": title[:60], "on_topic": True,
                            "duplicate_of": "", "importance": imp, "category": self._cat(title),
                            "reason": "Test modu puanı"})
        return {"stories": stories}

    def _write(self, user: str) -> dict:
        m = re.search(r"\[1\] (.+?) \((\w+)\) — (.+)", user)
        credit, kind, title = (m.group(1), m.group(2), m.group(3)) if m else ("Kaynak", "media", "Haber")
        instr = re.search(r"EDITOR INSTRUCTION[^:]*: (.+)", user)
        t = f"{title[:80]}"
        if instr:
            t = f"{t} (düzeltildi)"
        body = (
            f"Bu metin **test modunda** üretildi; gerçek kurulumda burada yapay zekanın {credit} kaynağından "
            f"yazdığı özgün Türkçe haber metni yer alır.\n\n"
            f"Kaynak başlığı: _{title}_.\n\n"
            f"**Neden önemli?** Test modunda örnek bir değerlendirme cümlesi."
        )
        return {
            "title": t, "summary": f"{credit} kaynaklı gelişme (test özeti): {title[:120]}",
            "body": body, "category": self._cat(title), "tags": [credit, "Test"],
            "confidence": "yuksek" if kind == "official" else "orta",
            "flags": [] if kind == "official" else ["iddia"] if "report" in title.lower() else [],
            "editor_note": "",
            "short_title": t[:55],
            "kicker": {"official": "Duyuru", "media": "Gündem"}.get(kind, "Gündem"),
            "hero_stat": (m2.group(1) if (m2 := re.search(r"\$(\d+(?:\.\d+)?)\s?(B|M)\b", title)) else ""),
            "hero_stat_label": "",
            "visual_style": "studio",
            "visual_scene": "a smooth sculptural object on a pastel backdrop",
            "focus_keyword": " ".join(title.split()[:3]),
            "seo_title": title[:58],
            "meta_description": (f"{title}. {credit} kaynaklı gelişmenin ayrıntıları, kaynağıyla ve Türkçe olarak.")[:156],
            "slug": "",
            "image_alt": f"{title[:80]} haberini temsil eden 3D görsel",
            "carousel_points": [f"{credit} bu gelişmeyi duyurdu (test maddesi).",
                                "Gerçek kurulumda burada kaynaktan alınan somut bir bilgi yer alır.",
                                "Üçüncü madde: fiyat, tarih ya da kullanıcı sayısı gibi bir ayrıntı."],
        }
