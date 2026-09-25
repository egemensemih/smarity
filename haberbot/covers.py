"""Tipografik haber kapakları: her habere özel renk, düzen ve tek bir güçlü öğe.

Düzenler
  sayi   : haberin kalbindeki rakam dev boyutta ("311 milyon $", "%40")
  isim   : öne çıkan ürün / model / şirket adı dev boyutta ("GPT‑6 Astra", "Opus 5.5")
  manset : açık zeminde afiş gibi büyük başlık, anahtar sözcük renkli
  isik   : karanlıkta ışık huzmesi ve başlık (regülasyon, güvenlik gibi ciddi konular)

Logo ya da marka işareti kullanılmaz; yalnızca metin, renk ve ışık.
"""
from __future__ import annotations

import hashlib
import html
import random
import re

# c1..c4: vurgu renkleri, sonra koyu zemin ve açık zemin
PALETTES: dict[str, list[str]] = {
    "okyanus":   ["#38BDF8", "#3B82F6", "#6366F1", "#A78BFA", "#050816", "#EAF2FF"],
    "gunbatimi": ["#FDBA74", "#FB7185", "#E879F9", "#A855F7", "#12060F", "#FFF0EA"],
    "nane":      ["#6EE7B7", "#2DD4BF", "#22D3EE", "#A7F3D0", "#03110E", "#E8FAF3"],
    "lav":       ["#FDE047", "#FB923C", "#F43F5E", "#E11D48", "#140605", "#FFF1E8"],
    "lavanta":   ["#C4B5FD", "#A78BFA", "#F0ABFC", "#F9A8D4", "#0C0718", "#F4EEFF"],
    "altin":     ["#FEF08A", "#FACC15", "#F59E0B", "#FB923C", "#120C02", "#FFF7E3"],
    "buz":       ["#BAE6FD", "#7DD3FC", "#93C5FD", "#C7D2FE", "#040A14", "#EEF6FF"],
    "orman":     ["#D9F99D", "#84CC16", "#22C55E", "#10B981", "#040E06", "#EFFAE6"],
    "mercan":    ["#FED7AA", "#FDA4AF", "#FB7185", "#F97316", "#16080A", "#FFF0EC"],
    "elektrik":  ["#22D3EE", "#818CF8", "#C084FC", "#F472B6", "#050314", "#F1EEFF"],
    "grafit":    ["#F4F4F5", "#A1A1AA", "#D4D4D8", "#71717A", "#09090B", "#F2F2F4"],
}

PRODUCT_RE = re.compile(
    r"\b(GPT|ChatGPT|Gemini|Claude|Opus|Sonnet|Haiku|Llama|Grok|Copilot|Sora|Veo|Imagen|Isaac|Jetson|Blackwell|"
    r"Rubin|Mistral|Qwen|DeepSeek|Phi|Muse|Astra|Codex|Siri|Alexa|Nova|Titan|Ray-Ban|Vision Pro|"
    r"iPhone|iPad|MacBook|AirPods|Galaxy|Pixel|PlayStation|PS5|PS6|Xbox|Switch|Steam Deck|Quest|"
    r"Model [3SXY]|Cybertruck|T10X|T10F|GTA|Fortnite|Starship)\b", re.I)
GENERIC = {"yapay zeka", "yapay zekâ", "ai", "teknoloji", "veri merkezleri", "yapay zeka ajanları", "büyük dil modelleri",
           "oyun", "oyunlar", "otomobil", "elektrikli araç", "elektrikli otomobil", "girişim", "girişimler", "yatırım",
           "akıllı telefon", "inovasyon", "bilim"}


COVER_VERSION = 1


def _seed(d: dict) -> int:
    key = f'{d.get("id") or d.get("title", "x")}:{d.get("cover_variant", 0)}'
    return int(hashlib.sha1(key.encode()).hexdigest()[:8], 16)


def cover_word(d: dict) -> str:
    """Kapağa yazılacak ürün / model / şirket adı (yoksa '')."""
    w = (d.get("cover_text") or "").strip()
    if w:
        return w
    cands = [t for t in (d.get("tags") or []) if t and t.lower() not in GENERIC]
    kw = (d.get("focus_keyword") or "").strip()
    if kw:
        cands.append(kw)
    best, score = "", 0
    for c in cands:
        s = 0
        if PRODUCT_RE.search(c):
            s += 3
        if re.search(r"\d", c) and re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]", c):
            s += 2
        if len(c) <= 16:
            s += 1
        if len(c.split()) > 3 or len(c) > 24:
            s -= 3
        if s > score:
            best, score = c, s
    if score >= 3:
        # "Gemini 3.8 Flash TTS" gibi uzun adları kısalt
        words = best.split()
        while len(" ".join(words)) > 16 and len(words) > 2:
            words.pop()
        return " ".join(words)
    return ""


# Her kategori kendi renk ailesinde kalır; aynı aile içinde habere göre ton değişir.
# Sıra: açık vurgu, ana renk, koyu ton, ara ton, koyu zemin, açık zemin
CATEGORY_SCALES: dict[str, list[list[str]]] = {
    "super-zeka": [   # mor
        ["#C4B5FD", "#8B5CF6", "#6D28D9", "#A78BFA", "#0C0718", "#F3EEFF"],
        ["#E9D5FF", "#A855F7", "#7C3AED", "#C084FC", "#0E0718", "#F7F0FF"],
        ["#DDD6FE", "#7C5CFF", "#5B21B6", "#B4A0FF", "#0A0718", "#F1EEFF"],
    ],
    "teknoloji": [    # mavi
        ["#BFDBFE", "#3B82F6", "#1D4ED8", "#93C5FD", "#030A1A", "#EAF2FF"],
        ["#A5F3FC", "#326EF0", "#1E40AF", "#60A5FA", "#040B1C", "#E8F1FF"],
        ["#C7D2FE", "#4F7DF3", "#2563EB", "#7DD3FC", "#050A1A", "#EDF3FF"],
    ],
    "inovasyon": [    # yeşil / turkuaz
        ["#A7F3D0", "#10B981", "#047857", "#6EE7B7", "#03110E", "#E8FAF3"],
        ["#BBF7D0", "#22C55E", "#15803D", "#86EFAC", "#041008", "#EDFBEF"],
        ["#99F6E4", "#14B8A6", "#0F766E", "#5EEAD4", "#031110", "#E6FAF7"],
    ],
    "girisimcilik": [  # turuncu / kehribar
        ["#FDE68A", "#F59E0B", "#D97706", "#FCD34D", "#140C02", "#FFF7E3"],
        ["#FED7AA", "#FB923C", "#EA580C", "#FDBA74", "#160904", "#FFF3EA"],
        ["#FEF08A", "#FACC15", "#CA8A04", "#FDE047", "#141002", "#FFFBE6"],
    ],
    "gaming": [       # pembe / magenta
        ["#FBCFE8", "#EC4899", "#BE185D", "#F9A8D4", "#16060F", "#FFF0F7"],
        ["#F5D0FE", "#D946EF", "#A21CAF", "#F0ABFC", "#130616", "#FDF0FF"],
        ["#FECDD3", "#F43F5E", "#BE123C", "#FDA4AF", "#16060A", "#FFF0F2"],
    ],
}


def palette_for(d: dict) -> tuple[str, list[str]]:
    """Kategorinin renk ailesinden, habere göre değişen bir ton seç."""
    cat = d.get("category", "")
    scales = CATEGORY_SCALES.get(cat) or CATEGORY_SCALES["teknoloji"]
    i = _seed(d) % len(scales)
    return f"{cat or 'teknoloji'}-{i + 1}", scales[i]


def _highlight(title: str, key: str) -> str:
    """Başlığı güvenli HTML'e çevir; anahtar sözcük renkli vurgulansın."""
    t = html.escape(title)
    k = html.escape(key or "")
    if k and len(k) >= 3:
        m = re.search(re.escape(k), t, re.I)
        if m:
            return t[:m.start()] + f'<em class="grad-text">{t[m.start():m.end()]}</em>' + t[m.end():]
    # anahtar yoksa ilk büyük harfli özel adı vurgula
    m = re.search(r"\b([A-ZÇĞİÖŞÜ][\w'’.-]{2,}(?:\s[A-ZÇĞİÖŞÜ0-9][\w'’.-]*)?)", t)
    if m:
        return t[:m.start()] + f'<em class="grad-text">{m.group(1)}</em>' + t[m.end():]
    return t


def _lum(hexc: str) -> float:
    h = hexc.lstrip("#")[:6]
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _blobs(rnd: random.Random, pal: list[str], layout: str, tone: str, variant: str = "center") -> list[dict]:
    cols = pal[:4]
    if tone == "vivid":  # tüm yüzeyi kaplayan canlı ağ degrade
        return [{"x": x, "y": y, "s": s_, "c": c} for x, y, s_, c in (
            (rnd.randint(0, 30), rnd.randint(0, 35), 85, cols[0]), (rnd.randint(70, 100), rnd.randint(0, 35), 80, cols[2]),
            (rnd.randint(20, 60), rnd.randint(70, 100), 90, cols[1]), (rnd.randint(80, 105), rnd.randint(70, 105), 70, cols[3]))]
    if layout == "sayi" and variant == "left":
        spots = [(rnd.randint(75, 95), rnd.randint(10, 30), 70, cols[1]), (100, 60, 50, cols[2]), (rnd.randint(10, 30), 105, 40, cols[0])]
    elif layout == "sayi" and tone == "dark":  # siyah zemin, rakamın arkasında tek parıltı
        spots = [(50, 62, 62, cols[2]), (rnd.choice((30, 70)), 70, 34, cols[3])]
    elif layout == "sayi":
        spots = [(50, 58, 78, cols[1]), (18, 22, 46, cols[0]), (86, 82, 50, cols[3]), (82, 18, 34, cols[2])]
    elif layout == "isim":
        spots = [(rnd.randint(10, 35), rnd.randint(15, 45), 70, cols[0]), (rnd.randint(60, 90), rnd.randint(10, 40), 64, cols[2]),
                 (rnd.randint(35, 65), rnd.randint(60, 95), 76, cols[1]), (rnd.randint(75, 100), rnd.randint(65, 100), 52, cols[3])]
    elif layout == "manset":
        spots = [(rnd.randint(70, 95), rnd.randint(5, 30), 70, cols[1]), (rnd.randint(85, 110), rnd.randint(40, 70), 55, cols[2]),
                 (rnd.randint(-5, 20), rnd.randint(-10, 15), 36, cols[0])]
    else:  # isik: ışığı şablon çizer
        spots = []
    out = []
    for x, y, s, c in spots:
        if tone == "dark" and layout in ("sayi", "isik"):
            c = c + "B3"  # hafif şeffaf
        out.append({"x": x, "y": y, "s": s, "c": c})
    return out


def design(d: dict, brand: bool = False, caption: bool = False, brand_name: str = "Smarity", kicker: bool = True) -> dict:
    """Kapak şablonu için bağlam sözlüğü. caption=True: sosyal medya için kısa başlık da yazılır."""
    seed = _seed(d)
    rnd = random.Random(seed)
    pal_name, pal = palette_for(d)
    stat = (d.get("hero_stat") or "").strip()
    word = cover_word(d)
    cat = d.get("category", "")
    serious = re.search(r"güvenlik açığı|siber saldırı|ihlal|dava|soruşturma|yasak|geri çağır|kaza|ceza", (d.get("kicker", "") + d.get("title", "")).lower())

    variant = "center"
    pick = seed % 6
    if stat and len(stat) <= 12 and not (word and pick in (1, 4)):
        layout = "sayi"
        tone, variant = [("dark", "center"), ("light", "left"), ("vivid", "center"),
                         ("dark", "center"), ("light", "left"), ("vivid", "left")][pick]
    elif word:
        layout = "isim"
        tone = ["vivid", "light", "dark", "vivid", "light", "vivid"][pick]
    elif serious:
        layout, tone = "isik", "dark"
    else:
        layout, tone = "manset", ["light", "vivid"][pick % 2]

    base = {"dark": "#040405", "light": pal[5], "vivid": pal[1]}[tone]
    if tone == "vivid":
        avg = sum(_lum(c) for c in pal[:4]) / 4
        ink = "#111114" if avg > 0.66 else "#FFFFFF"
    else:
        ink = "#FFFFFF" if tone == "dark" else "#111114"
    kw = d.get("focus_keyword") or ""
    if kw.lower() in GENERIC or len(kw.split()) > 3 or kw.lower().startswith("yapay zeka"):
        kw = ""
    headline = _highlight(d.get("short_title") or d.get("title", ""), word or kw) if not serious else html.escape(d.get("short_title") or d.get("title", ""))
    glyph = (word or re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşü]", "", d.get("short_title") or d.get("title") or "Y") or "Y")[:1].upper()
    return {
        "layout": layout, "tone": tone, "pal": pal[:4] + [base], "palette": pal_name, "seed": seed,
        "kicker": (d.get("kicker") or "") if kicker else "", "stat": stat, "stat_label": (d.get("hero_stat_label") or "").strip(),
        "word": word, "sub": "", "headline": headline, "glyph": glyph,
        "blobs": _blobs(rnd, pal, layout, tone, variant), "brand": brand, "variant": variant, "ink": ink,
        "brand_name": brand_name,
        "caption": (d.get("short_title") or d.get("title", "")) if caption and layout in ("sayi", "isim") else "",
    }


# ── Özet kartı (Instagram post / story) ──────────────────────
def _mark(title: str, d: dict) -> str:
    """Başlığı güvenli HTML'e çevir; öne çıkan ifade siyah kutuyla vurgulansın."""
    t = html.escape(title, quote=False)
    first = [(d.get("cover_text") or "").strip(), cover_word(d)]          # önce kapaktaki ad
    rest = [(d.get("focus_keyword") or "").strip()] + [x for x in (d.get("tags") or []) if x]
    ok = lambda c: c and 3 <= len(c) <= 26 and c.lower() not in GENERIC  # noqa: E731
    ordered = list(dict.fromkeys([c for c in first if ok(c)] + sorted({c for c in rest if ok(c)}, key=len, reverse=True)))
    for c in ordered:
        m = re.search(r"(?<![\wÇĞİÖŞÜçğıöşü])" + re.escape(html.escape(c, quote=False)), t, re.I)
        if m:
            end = m.end()
            # Türkçe ek varsa ("OpenAI'ın", "Xbox'ta") kutu eki de kapsasın
            ext = re.match(r"['’][\wçğıöşü]+", t[end:])
            if ext:
                end += ext.end()
            return t[:m.start()] + f"<mark>{t[m.start():end]}</mark>" + t[end:]
    words = t.split()
    if len(words) >= 4:  # öne çıkan ad yoksa son iki sözcük
        return " ".join(words[:-2]) + " <mark>" + " ".join(words[-2:]) + "</mark>"
    return t


UPPER_EXCEPTIONS = {"gaming": "GAMING"}


def tr_upper(s: str) -> str:
    """Türkçe büyük harf (i → İ, ı → I); İngilizce kategori adları olduğu gibi kalır."""
    if s.lower() in UPPER_EXCEPTIONS:
        return UPPER_EXCEPTIONS[s.lower()]
    return s.replace("i", "İ").replace("ı", "I").upper()


WHY_RE = re.compile(r"\*\*Neden önemli\?\*\*\s*(.+)", re.S)


def _plain(md: str) -> str:
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md or "")
    s = re.sub(r"[*_`#>]+", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _cut(text: str, n: int) -> str:
    text = text.strip()
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


def why_text(d: dict) -> str:
    """Haberin 'Neden önemli?' cümlesi (yoksa özet)."""
    m = WHY_RE.search(d.get("body") or "")
    return _cut(_plain(m.group(1)) if m else (d.get("summary") or ""), 230)


def carousel_points(d: dict) -> list[str]:
    """Carousel'in 2. sayfası için 3 madde: yazarın ürettiği maddeler, yoksa metnin paragraflarından."""
    pts = [_cut(_plain(x), 130) for x in (d.get("carousel_points") or []) if x and x.strip()]
    if len(pts) >= 2:
        return pts[:3]
    paras = []
    for block in re.split(r"\n\s*\n", d.get("body") or ""):
        b = block.strip()
        if not b or b.startswith("#") or b.startswith("**Neden önemli"):
            continue
        sent = re.split(r"(?<=[.!?])\s+", _plain(b))[0]
        if len(sent) > 25:
            paras.append(_cut(sent, 130))
    return (pts + paras)[:3]


def news_card(d: dict, W: int, H: int, *, brand_name: str = "Smarity", tagline: str = "", label: str = "",
              date: str = "", credits: str = "", mode: str = "cover", page: int = 0, pages: int = 0,
              site_host: str = "") -> dict:
    """Özet kartı şablonu için bağlam: habere özel renkler, oluklu cam şeritleri ve vurgulu başlık."""
    seed = _seed(d)
    rnd = random.Random(seed)
    pal_name, pal = palette_for(d)
    base = "#" + "".join(f"{round(int(pal[5][i:i + 2], 16) * .45 + 255 * .55):02X}" for i in (1, 3, 5))
    right = rnd.random() < .7            # ışığın ağırlığı çoğunlukla sağda
    gx = rnd.randint(62, 80) if right else rnd.randint(22, 40)
    glow = [
        {"x": gx, "y": rnd.randint(52, 66), "w": 58, "h": 36, "c": pal[1], "a": 88},
        {"x": min(98, gx + 18) if right else max(2, gx - 18), "y": rnd.randint(34, 48), "w": 34, "h": 30, "c": pal[2], "a": 70},
        {"x": 100 - gx, "y": rnd.randint(78, 92), "w": 46, "h": 26, "c": pal[3], "a": 42},
        {"x": rnd.randint(20, 80), "y": rnd.randint(8, 20), "w": 50, "h": 22, "c": pal[0], "a": 26},
    ]
    n = 22
    w = W / n
    reeds = []
    for i in range(n):
        dx = ((i * 37 + seed) % 9 - 4) * W / 400
        dy = ((i * 53 + seed) % 11 - 5) * H / 160
        reeds.append({"x": round(i * w, 1), "w": round(w + 1, 1), "bx": round(-i * w + dx, 1), "by": round(dy, 1)})
    title = d.get("short_title") or d.get("title", "")
    return {
        "pal": pal[:4], "palette": pal_name, "base": base, "glow": glow, "reeds": reeds,
        "headline": _mark(title, d), "summary": (d.get("summary") or "").strip(), "title": title,
        "points": carousel_points(d) if mode == "points" else [], "why": why_text(d) if mode == "why" else "",
        "mode": mode, "page": page, "pages": pages, "site_host": site_host, "label_plain": label,
        "label": tr_upper(label), "date": date, "credits": credits, "tagline": tagline, "brand_name": brand_name,
    }
