"""Türkçe metin düzeltmeleri (yapay zekaya gerek kalmadan, kurallı ve güvenli).

1) Türkçe karakteri düşmüş sözcükler: "cikis tarihi aciklandi" → "çıkış tarihi açıklandı".
   Sözlük, sitedeki haberlerin metinlerinden kendiliğinden öğrenilir (+ sık sözcüklerden oluşan çekirdek liste).
   Yalnızca Türkçe karakterli hâli bilinen ve düz hâli ayrı bir sözcük olmayan kelimeler düzeltilir; cümle ortasında
   büyük harfle başlayan (özel ad olabilecek) sözcüklere, sözlükte de özel ad olarak geçmiyorsa dokunulmaz.
2) Küçük harfle başlayan marka adları: "İPhone" → "iPhone", "EFlyer 2" → "eFlyer 2".
3) Etiketlerin görünen adı: "elektrikli otomobil" → "Elektrikli otomobil" (içinde büyük harf varsa olduğu gibi).
"""
from __future__ import annotations

import re
from collections import Counter

TR_LETTERS = "çğıöşüÇĞİÖŞÜ"
FOLD = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
                      "Ç": "C", "Ğ": "G", "İ": "I", "Ö": "O", "Ş": "S", "Ü": "U", "â": "a", "Â": "A", "î": "i", "û": "u"})
WORD = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşüÂâÎîÛû]+")

SEED = """
açıkladı açıklandı açıklama açıklamada açıklamasına açık açıklığı çıkış çıkışı çıktı çıkıyor çıkacak çıkarıyor çıkardı
erişim erişimi erişimini kararı kararları kararlar karşı karşısında Atatürk Türkiye Türkiye'de Türk Türkçe İstanbul Ankara İzmir
özellik özellikleri özelliği özelliğini özel güncelleme güncellemesi güncellendi şirket şirketi şirketin şirketler şirketleri
üretim üretimi üretti üretiyor üretici kullanıcı kullanıcılar kullanıcıların kullanım kullanılıyor ücretsiz ücret ücreti
oyuncu oyuncular oyuncuların sürüm sürümü sürümünü donanım donanımı yazılım yazılımı öğrenme öğrendi büyük büyüme küçük
çok göre önce sonra dünya dünyanın geliştirdi geliştirme geliştiriyor geliştirici güç gücü gücünü hız hızı hızlı ürün ürünü
ürünleri ürünler satış satışa satışları tanıttı tanıtıldı tanıtım başladı başlıyor başlattı başarı başarılı akıllı gözlük
gözlüğü şarj güvenlik güvenliği düşük düşüş yüksek artış artırdı yatırım yatırımı girişim girişimi işlemci işlemcisi çip çipi
sürücü sürücüsüz aracı araç araçlar çalıştı çalıştırıldı çalışıyor çalışma iş işbirliği ortaklık müşteri müşteriler abonelik
üyelik gösterdi gösteriyor görüntü görüntülü sesli yenilik yenilikleri yeniliği gün günü günü Eylül Ekim Kasım Aralık Şubat
Mayıs Ağustos tarihi tarihinde çıkış tarihi ilgili ilgi dikkat değişiklik değişti dönüşüm döneminde dönem hâlâ şu anda
şimdi şöyle böyle üzere üzerinde içinde için içerik içeriği ağ ağı bağlantı bağlantısı uygulama uygulaması uygulamasının
ülke ülkede ülkeler bölge bölgesinde önemli öne öncelik ödeme ödül ölçek ölçüde örnek örneğin ücretli üst ünlü ünvanı
güncel güney kuzey doğu batı ışık işık süre süreç sürecinde süresi sürdürülebilir sağlık sağlıyor sağladı sağlayacak
Çin Çinli Japonya Güney Kore Avrupa Birliği yapımcı yapımı yönetici yönetim yöntem yöntemi çözüm çözümü çözümler
"""
SHORT_OK = {"cok": "çok", "uc": "üç", "guc": "güç", "hiz": "hız", "ise": None, "ic": "iç", "dis": "dış"}
LOWER_BRANDS = """iPhone iPad iPadOS iOS iMac iCloud iMessage iTunes iPod macOS watchOS visionOS tvOS eSIM eFootball eVTOL eBay
iRobot xAI eFlyer eGolf eMobility iX iQOO""".split()


def fold(s: str) -> str:
    return s.translate(FOLD)


def tr_lower(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


def tr_upper_first(s: str) -> str:
    if not s:
        return s
    c = s[0]
    c = "İ" if c == "i" else "I" if c == "ı" else c.upper()
    return c + s[1:]


class Fixer:
    """Sözlüğü haber metinlerinden öğrenen düzeltici."""

    def __init__(self, texts: list[str] | None = None):
        orig: dict[str, Counter] = {}
        plain: set[str] = set()
        for text in [SEED] + list(texts or []):
            for w in WORD.findall(text or ""):
                if any(ch in TR_LETTERS for ch in w):
                    key = tr_lower(fold(w)) if w[0].isupper() else fold(w).lower()
                    orig.setdefault(key, Counter())[w] += 1
                else:
                    plain.add(w.lower())
        self.map: dict[str, str] = {}
        for key, c in orig.items():
            if key in plain or (len(key) < 4 and key not in SHORT_OK):
                continue
            # en sık görülen yazım; küçük harfli hâli varsa o esas alınır (cümle başı büyük harfi sayılmaz)
            lows = Counter({w: n for w, n in c.items() if not w[0].isupper()})
            best = (lows or c).most_common(1)[0][0]
            self.map[key] = best
        for k, v in SHORT_OK.items():
            if v:
                self.map.setdefault(k, v)
        self.brands = {b.lower(): b for b in LOWER_BRANDS}
        for text in texts or []:
            for w in re.findall(r"\b[a-z]{1,2}[A-Z][A-Za-z0-9]*\b", text or ""):
                self.brands.setdefault(w.lower(), w)

    # ── sözcük düzeltme ──
    def _word(self, w: str, sentence_start: bool) -> str:
        if any(ch in TR_LETTERS for ch in w):
            return w
        lw = w.lower()
        rep = self.map.get(lw)
        if not rep:
            return w
        if w.isupper() and len(w) > 1:
            return rep.replace("i", "İ").replace("ı", "I").upper()
        if w[0].isupper():
            if rep[0].isupper():          # sözlükte de özel ad: Ataturk → Atatürk
                return rep
            return tr_upper_first(rep) if sentence_start else w   # cümle ortasında büyük harf: özel ad olabilir
        return rep if not rep[0].isupper() else w

    def diacritics(self, text: str) -> str:
        if not text:
            return text
        out, last, start = [], 0, True
        for m in WORD.finditer(text):
            gap = text[last:m.start()]
            if re.search(r"[.!?:\n]\s*$", gap) or (last == 0 and not gap.strip()):
                start = True
            out.append(gap)
            out.append(self._word(m.group(), start))
            start = False
            last = m.end()
        out.append(text[last:])
        return "".join(out)

    def brands_case(self, text: str) -> str:
        """İPhone / IPhone / EFlyer → iPhone / eFlyer (cümle başında büyütülmüş küçük harfli markalar)."""
        def fix(m):
            w = m.group(0)
            key = tr_lower(w[0]) + w[1:].lower() if w[0] in "İI" else w.lower()
            b = self.brands.get(key)
            return b if b and w != b and w[1:] == b[1:] else w
        return re.sub(r"\b[A-ZİÇĞÖŞÜ][A-Z][A-Za-z0-9]*\b", fix, text or "")

    def text(self, s: str) -> str:
        return self.brands_case(self.diacritics(s)) if s else s

    def post(self, p: dict) -> list[str]:
        """Bir haberin metin alanlarını düzelt; değişen alan adlarını döndür."""
        changed = []
        for k in ("title", "short_title", "summary", "body", "seo_title", "meta_description", "kicker",
                  "hero_stat_label", "image_alt", "cover_text", "focus_keyword", "cover_headline", "cover_highlight",
                  "update_note"):
            v = p.get(k)
            if isinstance(v, str) and v:
                nv = self.text(v)
                if nv != v:
                    p[k] = nv
                    changed.append(k)
        for k in ("tags", "carousel_points"):
            v = p.get(k)
            if isinstance(v, list):
                nv = [self.text(x) if isinstance(x, str) else x for x in v]
                if nv != v:
                    p[k] = nv
                    changed.append(k)
        return changed


def missing_turkish(text: str) -> bool:
    """Uzun bir Türkçe metinde hiç Türkçe karakter yoksa (büyük olasılıkla karakterler düşmüş)."""
    words = [w for w in WORD.findall(text or "") if w[0].islower()]
    return len(words) >= 6 and not any(ch in TR_LETTERS for ch in text)


def tag_display(tag: str) -> str:
    """Etiketin görünen adı: tamamı küçük harfse ilk harf büyür (Türkçe kurallarıyla)."""
    t = (tag or "").strip()
    if not t or any(ch.isupper() for ch in t):
        return t
    return tr_upper_first(t)


# Şirket / ürün adından karşılaştırma anahtarı ("HONOR Watch 6" → "honor"): aynı şirketin haberlerini tanımak için
_EKEY_STOP = {"the", "a", "an", "new", "yeni"}
_EKEY_GENERIC = {"turkiye", "abd", "cin", "avrupa", "japonya", "kore", "yapay", "elektrikli", "akilli", "otonom", "oyun",
                 "otomobil", "teknoloji", "girisim", "yatirim", "uzay", "robot", "robotlar", "insansi", "batarya",
                 "siber", "veri", "bulut", "kripto", "bitcoin", "ai", "ev", "suv", "5g", "6g"}


def entity_key(name: str) -> str:
    words = [w.strip(".'’-") for w in re.split(r"[\s/,:;()]+", fold(name or "").lower().strip())]
    words = [w for w in words if w and w not in _EKEY_STOP]
    if not words or len(words[0]) < 2 or words[0] in _EKEY_GENERIC:
        return ""
    return words[0]


def primary_key(p: dict) -> str:
    """Haberin ana şirket/ürün anahtarı: önce ayıklamanın verdiği adlar, yoksa ilk etiketler."""
    for e in list(p.get("entities") or []) + list(p.get("tags") or [])[:2]:
        k = entity_key(e)
        if k:
            return k
    return ""


def entity_keys(p: dict) -> set[str]:
    names = list(p.get("entities") or []) or list(p.get("tags") or [])[:1]
    return {k for k in (entity_key(e) for e in names) if k}


# ── Otomotiv: araba haberini tanı (kategori geçişi için) ─────
CAR_BRANDS = {
    "toyota", "lexus", "honda", "acura", "nissan", "infiniti", "mazda", "subaru", "mitsubishi", "suzuki", "hyundai", "kia",
    "genesis", "bmw", "mini cooper", "rolls-royce", "mercedes", "mercedes-benz", "mercedes-amg", "maybach", "audi", "volkswagen",
    "vw", "porsche", "lamborghini", "bentley", "bugatti", "skoda", "škoda", "seat", "cupra", "ferrari", "maserati",
    "alfa romeo", "fiat", "lancia", "jeep", "chrysler", "dodge", "chevrolet", "cadillac", "gmc", "buick",
    "general motors", "ford", "lincoln", "tesla", "rivian", "lucid", "lucid motors", "polestar", "volvo", "renault",
    "dacia", "peugeot", "citroën", "citroen", "opel", "ds automobiles", "stellantis", "jaguar", "land rover",
    "range rover", "aston martin", "mclaren", "lotus", "byd", "nio", "xpeng", "li auto", "zeekr", "geely", "chery",
    "omoda", "jaecoo", "mg motor", "togg", "waymo", "zoox", "leapmotor", "lynk & co", "denza", "yangwang",
    "aito", "rimac", "koenigsegg", "pagani", "alpine", "abarth", "isuzu", "scout", "fisker", "vinfast",
}
CAR_WORDS = re.compile(r"\b(otomobil|elektrikli araç|elektrikli otomobil|elektrikli suv|suv\b|sedan|hatchback|pikap|"
                       r"motosiklet|robotaksi|şarj istasyon|menzilli|beygir|model y\b|model 3\b|cybertruck|su7|yu7)", re.I)
NOT_CAR = re.compile(r"optimus|insansı robot|humanoid|starlink|spacex|carplay|android auto", re.I)


def is_car_story(d: dict) -> bool:
    """Haber bir araba / elektrikli araç / araç üreticisi haberi mi? (Tesla'nın robotu, CarPlay vb. hariç)"""
    text = f"{d.get('title', '')} {d.get('summary', '')}"
    if NOT_CAR.search(text):
        return False
    names = {str(x).strip().lower() for x in (d.get("entities") or []) + (d.get("tags") or [])}
    first = {n.split()[0] for n in names if n}
    if names & CAR_BRANDS or first & (CAR_BRANDS - {"seat", "scout", "alpine", "genesis", "lotus", "smart"}):
        return True
    return bool(CAR_WORDS.search(d.get("title", "")))


# ── Dil denetimi: başlık İngilizce mi kalmış? ─────────────────
EN_WORDS = {"the", "of", "for", "on", "in", "to", "with", "and", "its", "is", "are", "a", "an", "from", "by", "at", "as",
            "after", "says", "gets", "launches", "announces", "reveals", "adds", "pins", "focus", "reboot", "new", "will",
            "could", "over", "into", "how", "why", "what", "customers", "business", "about", "this", "that", "now"}


def looks_english(text: str) -> bool:
    """Türkçe harf hiç yok ve en az iki İngilizce bağlaç/sözcük var → İngilizce."""
    if not text or re.search(r"[çğıöşüÇĞİÖŞÜ]", text):
        return False
    words = re.findall(r"[a-z']+", text.lower().replace("’", "'"))
    if set(words) & TR_WORDS:
        return False
    hits = [w for w in words if w in EN_WORDS or w.endswith("'s")]
    strong = [w for w in hits if w not in {"the", "of", "a", "an"}]   # "The Last of Us" gibi adlar sayılmaz
    return len(hits) >= 3 or (len(hits) >= 2 and bool(strong))


TR_WORDS = {"ve", "ile", "bir", "yeni", "icin", "oldu", "geliyor", "tanitildi", "aciklandi", "sezon", "tarihi", "fiyati",
            "fiyat", "satis", "ozellikleri", "cikti", "duyurdu", "geldi", "artik"}
