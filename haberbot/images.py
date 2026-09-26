"""Acil durum kapağı (Pillow). Normalde kartlar visuals.py + Chrome ile üretilir;
bu dosya yalnızca tarayıcı hiç açılamazsa devreye girer.

Gerçek fotoğraflar photos.py ile kaynaklardan alınır; bu dosya yalnızca fotoğraf
bulunamadığında kullanılan markaya ait tipografik kapağın son yedeğidir.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import ROOT, category_color, category_label
from .util import tr_upper

FONT_DIR = ROOT / "assets" / "fonts"
_BOLD = FONT_DIR / "InstrumentSans-Bold.ttf"
_REG = FONT_DIR / "InstrumentSans-Regular.ttf"
_FALLBACKS_BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_FALLBACKS_REG = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    cands = [_BOLD if bold else _REG] + (_FALLBACKS_BOLD if bold else _FALLBACKS_REG)
    for c in cands:
        try:
            return ImageFont.truetype(str(c), size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _hex(c: str, a: int = 255) -> tuple[int, int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), a


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_cover(title: str, category: str, credits: list[str], date_str: str, brand: str,
               out: Path, size: tuple[int, int] = (1200, 630), chip: str | None = None,
               accent: str | None = None) -> Path:
    W, H = size
    s = W / 1200  # ölçek
    accent = accent or category_color(category)
    pad = int(72 * s)

    # arka plan: koyu gradyan
    img = Image.new("RGB", (W, H), "#0A0F1F")
    grad = Image.new("L", (1, H))
    for y in range(H):
        grad.putpixel((0, y), int(255 * (y / H)))
    top = Image.new("RGB", (W, H), "#0B1022")
    bot = Image.new("RGB", (W, H), "#151B3A")
    img = Image.composite(bot, top, grad.resize((W, H)))

    # kategori renginde parıltı
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = int(W * 0.9), int(H * 0.08)
    r = int(max(W, H) * 0.42)
    gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_hex(accent, 95))
    glow = glow.filter(ImageFilter.GaussianBlur(int(120 * s)))
    img.paste(glow, (0, 0), glow)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # nokta ızgarası
    step = int(30 * s)
    for x in range(step // 2, W, step):
        for y in range(step // 2, H, step):
            d.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(255, 255, 255, 16))
    # radar halkaları + tarama dilimi
    for i, rr in enumerate([90, 180, 270, 360, 450]):
        rr = int(rr * s)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=_hex(accent, 70 - i * 10), width=max(2, int(2 * s)))
    sweep = int(450 * s)
    d.pieslice([cx - sweep, cy - sweep, cx + sweep, cy + sweep], 100, 135, fill=_hex(accent, 26))
    d.line([cx, cy, cx + int(sweep * math.cos(math.radians(135))), cy + int(sweep * math.sin(math.radians(135)))],
           fill=_hex(accent, 120), width=max(2, int(2 * s)))
    img.paste(layer, (0, 0), layer)

    d = ImageDraw.Draw(img)
    # marka
    mark_r = int(15 * s)
    mx, my = pad + mark_r, pad + mark_r
    d.ellipse([mx - mark_r, my - mark_r, mx + mark_r, my + mark_r], outline=accent, width=max(3, int(3 * s)))
    d.ellipse([mx - 4 * s, my - 4 * s, mx + 4 * s, my + 4 * s], fill=accent)
    f_brand = _font(True, int(28 * s))
    d.text((mx + mark_r + int(14 * s), my), tr_upper(brand), font=f_brand, fill="#FFFFFF", anchor="lm")

    # kategori etiketi
    f_chip = _font(True, int(22 * s))
    label = tr_upper(chip or category_label(category))
    tw = d.textlength(label, font=f_chip)
    chip_y = my + mark_r + int(46 * s)
    chip_h = int(40 * s)
    d.rounded_rectangle([pad, chip_y, pad + tw + int(32 * s), chip_y + chip_h], radius=chip_h // 2, fill=accent)
    d.text((pad + int(16 * s), chip_y + chip_h // 2), label, font=f_chip, fill="#FFFFFF", anchor="lm")

    # başlık: sığana kadar küçült
    footer_h = int(90 * s)
    area_top = chip_y + chip_h + int(34 * s)
    area_h = H - footer_h - area_top - int(10 * s)
    max_w = W - pad * 2 - int(40 * s)
    max_lines = 4 if H <= W else 7
    start = int((100 if H > W else 70) * s)
    for fs in range(start, int(34 * s), -2):
        f_title = _font(True, fs)
        lines = _wrap(d, title, f_title, max_w)
        lh = int(fs * 1.12)
        if len(lines) <= max_lines and lh * len(lines) <= area_h:
            break
    else:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .,:;") + "…"
    block_h = lh * len(lines)
    y = area_top + area_h - block_h if H > W else area_top + max(0, (area_h - block_h) // 2)
    for ln in lines:
        d.text((pad, y), ln, font=f_title, fill="#FFFFFF")
        y += lh

    # alt bilgi
    fy = H - pad + int(8 * s)
    d.line([pad, fy - int(40 * s), W - pad, fy - int(40 * s)], fill=(255, 255, 255, 40), width=1)
    f_small = _font(False, int(24 * s))
    src = "Kaynak: " + " · ".join(credits[:3]) if credits else ""
    d.text((pad, fy), src, font=f_small, fill="#AEB6D6", anchor="ls")
    if date_str:
        d.text((W - pad, fy), date_str, font=f_small, fill="#AEB6D6", anchor="rs")

    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, "JPEG", quality=84, optimize=True, progressive=True)
    return out
