"""Haber görselleri.

1) Kahraman görsel (hero): Claude'un haber için kurguladığı sahne, Google'ın görsel
   modeliyle (Nano Banana) üretilir. Anahtar yoksa ya da üretim başarısız olursa
   habere özgü 3D stüdyo görseli (yedek) üretilir.
2) Kartlar: hero görsel + tipografi → site kapağı (OG), Instagram post ve story.
"""
from __future__ import annotations

import base64
import io
import time
from pathlib import Path

import requests
from PIL import Image

from . import covers
from .config import Config, category_color, category_label
from .render import Renderer
from .util import clip, log, tr_date


def nobr(text: str) -> str:
    """'GPT-6' gibi tireli sözcükler satır sonunda bölünmesin."""
    import re
    return re.sub(r"(?<=\w)-(?=\w)", "\u2011", text or "")

HERO_SIZE = (1280, 960)          # 4:3 — tüm formatlara kırpılabilir

# ── sanat yönetimi ───────────────────────────────────────────
STYLES = {
    "studio": "a minimal studio product photograph of one sculptural hero object on a seamless pastel backdrop",
    "macro": "a macro close-up of premium materials such as brushed aluminium, frosted glass, polished ceramic or a silicon wafer, shallow depth of field",
    "diorama": "a tiny isometric miniature diorama with clay and glass materials and a gentle tilt-shift look",
    "sculpture": "an abstract light sculpture of translucent glass ribbons and soft glowing gradients refracting light",
    "still_life": "a conceptual still-life arrangement of a few everyday objects that symbolise the story",
}
STYLE_KEYS = list(STYLES)

# Kategoriye göre arka plan tonu (açık, Apple tarzı)
BACKDROPS = {
    "super-zeka": "soft lavender white", "teknoloji": "cool silver white", "inovasyon": "pale mint white",
    "girisimcilik": "warm ivory", "gaming": "soft pink-violet white",
}

NEGATIVE = ("Strictly no text, no letters, no numbers, no captions, no logos, no brand marks, no watermarks, "
            "no user-interface screens, no real or recognisable people, no faces.")


def image_prompt(d: dict) -> str:
    style = d.get("visual_style") if d.get("visual_style") in STYLES else "studio"
    scene = (d.get("visual_scene") or "").strip() or f"an elegant abstract object representing {category_label(d.get('category', ''))}"
    accent = category_color(d.get("category", ""))
    backdrop = BACKDROPS.get(d.get("category", ""), "soft neutral white")
    return (
        f"{scene}\n\n"
        f"Render it as {STYLES[style]}. "
        f"Premium, calm, Apple-keynote aesthetic: soft diffused studio lighting, gentle realistic shadows, "
        f"clean {backdrop} background, a restrained palette with one accent colour close to {accent}. "
        f"Single clear focal point, centred, with generous empty space on every side so the image can be cropped "
        f"to square, portrait and landscape. Photorealistic 3D render, high detail, sharp focus on the subject.\n"
        f"{NEGATIVE}"
    )


# ── Google görsel modeli (Nano Banana) ──────────────────────
class ImageError(RuntimeError):
    pass


def _find_image_b64(obj) -> str | None:
    """Yanıt biçimi ne olursa olsun içindeki ilk base64 görseli bul."""
    if isinstance(obj, dict):
        mime = obj.get("mimeType") or obj.get("mime_type") or ""
        data = obj.get("data")
        if isinstance(data, str) and len(data) > 1000 and (not mime or mime.startswith("image")):
            return data
        for k in ("bytesBase64Encoded", "b64_json", "image_bytes"):
            if isinstance(obj.get(k), str) and len(obj[k]) > 1000:
                return obj[k]
        for v in obj.values():
            r = _find_image_b64(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_image_b64(v)
            if r:
                return r
    return None


class GoogleImage:
    BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str, model: str):
        self.key = api_key
        self.model = model

    def _post(self, url: str, body: dict) -> dict:
        for attempt in range(3):
            try:
                r = requests.post(url, json=body, timeout=180,
                                  headers={"x-goog-api-key": self.key, "Content-Type": "application/json"})
            except requests.RequestException as e:
                if attempt < 2:
                    time.sleep(8)
                    continue
                raise ImageError(f"Bağlantı hatası: {e}") from e
            if r.status_code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(10 * (attempt + 1))
                continue
            if r.status_code >= 400:
                raise ImageError(f"HTTP {r.status_code}: {r.text[:300]}")
            return r.json()
        raise ImageError("Tekrar denemeler tükendi")

    def generate(self, prompt: str, aspect: str = "4:3") -> bytes:
        errors = []
        # 1) generateContent
        url = f"{self.BASE}/models/{self.model}:generateContent"
        for image_cfg in ({"aspectRatio": aspect, "imageSize": "1K"}, {"aspectRatio": aspect}):
            body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": image_cfg}}
            try:
                b64 = _find_image_b64(self._post(url, body))
                if b64:
                    return base64.b64decode(b64)
                errors.append("generateContent: görsel dönmedi (güvenlik filtresi olabilir)")
                break
            except ImageError as e:
                errors.append(f"generateContent: {e}")
                if "HTTP 400" not in str(e):
                    break
        # 2) Interactions API
        body = {"model": self.model, "input": [{"type": "text", "text": prompt}],
                "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": aspect,
                                    "image_size": "1K"}}
        try:
            b64 = _find_image_b64(self._post(f"{self.BASE}/interactions", body))
            if b64:
                return base64.b64decode(b64)
            errors.append("interactions: görsel dönmedi")
        except ImageError as e:
            errors.append(f"interactions: {e}")
        raise ImageError(" | ".join(errors)[:600])


# ── yedek 3D görsel paleti ──────────────────────────────────
ACCENTS = {
    "super-zeka": ("#7C5CFF", "#FF8FB1"), "teknoloji": ("#326EF0", "#54D59C"), "inovasyon": ("#10B981", "#0EA5E9"),
    "girisimcilik": ("#F59E0B", "#3B82F6"), "gaming": ("#EC4899", "#8B5CF6"),
}


def _lin(hexc: str) -> list[float]:
    h = hexc.lstrip("#")
    return [round((int(h[i:i + 2], 16) / 255) ** 2.2, 4) for i in (0, 2, 4)]


def _tint(hexc: str, amount: float) -> str:
    h = hexc.lstrip("#")
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    base = (245, 245, 247)
    mixed = [round(base[i] * (1 - amount) + rgb[i] * amount) for i in range(3)]
    return "#" + "".join(f"{v:02X}" for v in mixed)


def fallback_hero(renderer: Renderer, d: dict) -> Image.Image:
    cat = d.get("category", "teknoloji")
    a, b = ACCENTS.get(cat, ("#5B5BF7", "#F59E0B"))
    seed_int = int(d["id"][:6], 16) if d.get("id") else 7
    colors = {"ca": _lin(a), "cb": _lin(b), "cc": _lin("#F3F3F5"), "bg": _lin(_tint(a, .1))}
    img = renderer.studio_art(seed_int % 997 + .5, seed_int % 5, colors, (1024, 768))
    return img.resize(HERO_SIZE, Image.LANCZOS)


def _fit_43(img: Image.Image) -> Image.Image:
    w, h = img.size
    target = 4 / 3
    if abs(w / h - target) > .01:
        if w / h > target:
            nw = int(h * target)
            img = img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = int(w / target)
            img = img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return img.resize(HERO_SIZE, Image.LANCZOS)


class Visuals:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.renderer = Renderer(cfg.root / ".cache" / "render")
        key = cfg.google_key
        model = cfg.get("images", "model", "gemini-3.1-flash-lite-image")
        self.ai = GoogleImage(key, model) if key and not cfg.mock else None
        self.brand = cfg.site.get("name", "Smarity")
        self.enabled_ai = cfg.get("images", "ai", True)

    def close(self):
        self.renderer.close()

    # ── kahraman görsel ─────────────────────────────────────
    def cover_image(self, d: dict, size=HERO_SIZE, brand: bool = False, caption: bool = False) -> Image.Image:
        """Tipografik kapak (dev rakam / isim / manşet) — ücretsiz, habere özel. Sitede etiket zaten yazdığı için kapakta yok."""
        tmp = self.renderer.cache / "_cover.jpg"
        ctx = covers.design(d, brand=brand, caption=caption, brand_name=self.brand, kicker=False)
        self.renderer.html_to_image("cover.html", ctx, size, tmp, quality=95)
        return Image.open(tmp).convert("RGB")

    def make_hero(self, d: dict, out: Path) -> dict:
        """Görseli üretir, out'a WEBP yazar. d['image'] bilgisini döndürür."""
        info = {"source": "fallback"}
        img = None
        if self.ai and self.enabled_ai:
            prompt = image_prompt(d)
            try:
                raw = self.ai.generate(prompt)
                img = _fit_43(Image.open(io.BytesIO(raw)).convert("RGB"))
                info = {"source": "ai", "model": self.ai.model, "prompt": prompt}
            except (ImageError, OSError) as e:
                log.warning("Yapay zeka görseli üretilemedi, yedek görsel kullanılacak: %s", e)
                info = {"source": "fallback", "error": str(e)[:300]}
        if img is None and self.cfg.get("images", "style", "kapak") == "kapak":
            try:
                img = self.cover_image(d)
                c = covers.design(d)
                info = {**info, "source": "cover", "layout": c["layout"], "palette": c["palette"],
                        "cover_v": covers.COVER_VERSION}
            except Exception as e:  # noqa: BLE001
                log.warning("Kapak üretilemedi, 3D görsel denenecek: %s", e)
        if img is None:
            try:
                img = fallback_hero(self.renderer, d)
            except Exception as e:  # noqa: BLE001
                log.warning("Yedek 3D görsel üretilemedi: %s", e)
                a, _ = ACCENTS.get(d.get("category", ""), ("#5B5BF7", ""))
                img = Image.new("RGB", HERO_SIZE, _tint(a, .12))
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out, "WEBP", quality=82, method=6)
        return info

    # ── kartlar ─────────────────────────────────────────────
    SIZES = {"og": (1200, 630), "post": (1080, 1350), "story": (1080, 1920),
             "c2": (1080, 1350), "c3": (1080, 1350)}
    # Instagram carousel sırası (1: kapak, 2: öne çıkanlar, 3: neden önemli) ve hikâye
    CAROUSEL = ["post", "c2", "c3"]
    NEWS_MODES = {"post": "cover", "c2": "points", "c3": "why", "story": "story"}

    @property
    def summary_style(self) -> bool:
        return (self.cfg.get("social", "card_style", "ozet") or "ozet") == "ozet"

    def layout_for(self, d: dict) -> str:
        if (d.get("hero_stat") or "").strip():
            return "stat"
        return ("product", "glass")[int(d["id"][-2:], 16) % 2] if d.get("id") else "product"

    @staticmethod
    def edge_color(hero: Path, side: str) -> tuple[str, bool]:
        """Görselin kenar rengi: kartın zemini bu renge boyanır, geçiş dikişsiz olur."""
        try:
            im = Image.open(hero).convert("RGB")
        except OSError:
            return "#F5F5F7", False
        w, h = im.size
        box = (0, 0, w, max(2, int(h * .06))) if side == "top" else (0, 0, max(2, int(w * .06)), h)
        r, g, b = im.crop(box).resize((1, 1), Image.BOX).getpixel((0, 0))
        lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
        return f"#{r:02X}{g:02X}{b:02X}", lum < .45

    def card_context(self, d: dict, hero: Path, kind: str = "post") -> dict:
        cat = d.get("category", "teknoloji")
        credits = list(dict.fromkeys(s["name"] for s in d.get("sources", [])))
        base = {
            "brand": self.brand,
            "kicker": d.get("kicker") or category_label(cat),
            "title": nobr(d.get("short_title") or d.get("title", "")),
            "summary": clip(d.get("summary", ""), 150),
            "stat": (d.get("hero_stat") or "").strip(),
            "stat_label": (d.get("hero_stat_label") or "").strip(),
            "accent": category_color(cat),
            "cat_label": category_label(cat),
            "credits": " · ".join(credits[:3]),
            "date": tr_date(d.get("published_at") or d.get("created_at"), self.cfg.tz, with_time=False),
            "hero": hero.resolve().as_uri() if hero.exists() else "",
            "site_host": self.cfg.site_url.split("://", 1)[-1],
            "layout": self.layout_for(d),
            "ai_image": (d.get("image") or {}).get("source") == "ai",
        }
        edge, dark = self.edge_color(hero, "left" if kind == "og" else "top")
        layout = ctx_layout = self.layout_for(d)
        if layout == "stat" and kind != "og":
            edge, dark = "#FFFFFF", False
        return {**base, "edge": edge, "dark_edge": dark and ctx_layout == "product"}

    def render_card(self, d: dict, kind: str, hero: Path, out: Path) -> Path:
        size = self.SIZES[kind]
        if kind in self.NEWS_MODES and self.summary_style:
            try:
                credits = list(dict.fromkeys(s["name"] for s in d.get("sources", [])))
                mode = self.NEWS_MODES[kind]
                ctx = covers.news_card(
                    d, *size, brand_name=self.brand, tagline=self.cfg.site.get("tagline", ""),
                    label=category_label(d.get("category", "teknoloji")),
                    date=tr_date(d.get("published_at") or d.get("created_at"), self.cfg.tz, with_time=False),
                    credits=" · ".join(credits[:2]), mode=mode,
                    page=self.CAROUSEL.index(kind) + 1 if kind in self.CAROUSEL else 0,
                    pages=len(self.CAROUSEL) if kind in self.CAROUSEL else 0,
                    site_host=self.cfg.site_url.split("://", 1)[-1] if "localhost" not in self.cfg.site_url else "",
                    story_link=not self.cfg.instagram_auto)
                return self.renderer.html_to_image("news.html", ctx, size, out)
            except Exception as e:  # noqa: BLE001
                log.warning("Özet kartı üretilemedi (%s), kapak kartı kullanılıyor: %s", kind, e)
        if (d.get("image") or {}).get("source") == "cover":
            try:
                ctx = covers.design(d, brand=True, caption=True, brand_name=self.brand)
                return self.renderer.html_to_image("cover.html", ctx, size, out)
            except Exception as e:  # noqa: BLE001
                log.warning("Kapak kartı üretilemedi (%s): %s", kind, e)
        ctx = self.card_context(d, hero, kind)
        try:
            return self.renderer.html_to_image(f"{kind}.html", {**ctx, "kind": kind}, size, out)
        except Exception as e:  # noqa: BLE001
            log.warning("Kart üretilemedi (%s), basit kapak kullanılıyor: %s", kind, e)
            from .images import make_cover
            return make_cover(ctx["title"], d.get("category", ""), ctx["credits"].split(" · "), ctx["date"],
                              self.brand, out, size=size)
