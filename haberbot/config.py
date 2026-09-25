"""Ayarların yüklenmesi ve ortam değişkenleri."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Sabit kategori listesi: slug → (etiket, renk)
CATEGORIES: dict[str, tuple[str, str]] = {
    "super-zeka":   ("Süper Zeka",   "#7C5CFF"),
    "teknoloji":    ("Teknoloji",    "#326EF0"),
    "inovasyon":    ("İnovasyon",    "#10B981"),
    "girisimcilik": ("Girişimcilik", "#F59E0B"),
    "gaming":       ("Gaming",       "#EC4899"),
}
DEFAULT_CATEGORY = "teknoloji"

# Kategori sayfaları için arama motoru başlığı ve tanıtım metni
CATEGORY_SEO: dict[str, tuple[str, str]] = {
    "super-zeka": ("Süper Zeka: yapay zeka haberleri",
                   "ChatGPT, Gemini, Claude ve yeni çıkan yapay zeka modelleri; yapay zekanın yeni özellikleri, şirketleri ve hayatımıza giren yeni kullanım alanları."),
    "teknoloji": ("Teknoloji haberleri",
                  "Yeni tanıtılan telefonlar, bilgisayarlar, giyilebilir cihazlar ve otomobiller; Apple, Samsung, Google gibi teknoloji devleri, internet ve siber güvenlik."),
    "inovasyon": ("İnovasyon ve bilim haberleri",
                  "İlk kez denenen teknolojiler, prototipler, robotik, uzay, enerji, batarya, otonom sürüş ve sağlık alanındaki buluşlar."),
    "girisimcilik": ("Girişimcilik ve yatırım haberleri",
                     "Dünyadan ve Türkiye'den girişim hikâyeleri, kurucular, yatırım turları, satın almalar ve yeni iş fikirleri."),
    "gaming": ("Gaming: oyun dünyası haberleri",
               "Yeni oyunlar, konsollar, PC oyunları, e-spor, oyun şirketleri ve Türk oyun stüdyolarından haberler."),
}


def category_seo(slug: str) -> tuple[str, str]:
    return CATEGORY_SEO.get(slug, (category_label(slug), ""))


def indexnow_key(site_url: str) -> str:
    """IndexNow (Bing/Yandex anlık bildirim) anahtarı: site adresinden türetilir, sitede /<anahtar>.txt olarak durur."""
    import hashlib
    return hashlib.sha1(("smarity-indexnow:" + site_url).encode()).hexdigest()[:32]


def category_label(slug: str) -> str:
    return CATEGORIES.get(slug, CATEGORIES[DEFAULT_CATEGORY])[0]


def category_color(slug: str) -> str:
    return CATEGORIES.get(slug, CATEGORIES[DEFAULT_CATEGORY])[1]


@dataclass
class Config:
    raw: dict
    root: Path = ROOT
    site_url: str = ""          # https://kullanici.github.io/depo  (sonda / yok)
    base_path: str = ""         # /depo   ya da ""
    anthropic_key: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""
    google_key: str = ""
    instagram_token: str = ""
    mock: bool = False
    fixtures_dir: Path | None = None
    force_collect: bool = False
    force_build: bool = False
    extras: dict = field(default_factory=dict)

    # kısa yollar
    def get(self, section: str, key: str, default=None):
        return (self.raw.get(section) or {}).get(key, default)

    @property
    def site(self) -> dict:
        return self.raw.get("site") or {}

    @property
    def tz(self) -> str:
        return self.get("schedule", "timezone", "Europe/Istanbul")

    @property
    def sources(self) -> list[dict]:
        return [s for s in (self.raw.get("sources") or []) if s and s.get("url")]

    # dizinler
    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def drafts_dir(self) -> Path:
        return self.root / "data" / "drafts"

    @property
    def posts_dir(self) -> Path:
        return self.root / "content" / "posts"

    @property
    def images_dir(self) -> Path:
        return self.root / "content" / "images"

    @property
    def out_dir(self) -> Path:
        return self.root / "_site"

    @property
    def instagram_auto(self) -> bool:
        """IG_ACCESS_TOKEN tanımlı ve ayarlarda kapatılmamışsa haberler Instagram'a kendiliğinden gider."""
        return bool(self.instagram_token) and bool(self.get("social", "instagram_auto", True))

    def post_url(self, slug: str) -> str:
        return f"{self.site_url}/haber/{slug}/"


def _derive_site_url(cfg_url: str) -> str:
    if cfg_url:
        return cfg_url.rstrip("/")
    env_url = os.environ.get("SITE_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        owner = owner.lower()
        if name.lower() == f"{owner}.github.io":
            return f"https://{owner}.github.io"
        return f"https://{owner}.github.io/{name}"
    return "http://localhost:8000"


def load_config(path: Path | None = None) -> Config:
    path = path or (ROOT / "config.yaml")
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    site_url = _derive_site_url((raw.get("site") or {}).get("url", "") or "")
    base_path = urlsplit(site_url).path.rstrip("/")
    fixtures = os.environ.get("HABERBOT_FIXTURES")
    return Config(
        raw=raw,
        root=Path(os.environ["HABERBOT_ROOT"]) if os.environ.get("HABERBOT_ROOT") else ROOT,
        site_url=site_url,
        base_path=base_path,
        anthropic_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
        telegram_token=os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
        google_key=(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip(),
        instagram_token=os.environ.get("IG_ACCESS_TOKEN", "").strip(),
        mock=os.environ.get("HABERBOT_MOCK", "") == "1",
        fixtures_dir=Path(fixtures) if fixtures else None,
        force_collect=os.environ.get("FORCE_COLLECT", "").lower() == "true",
        force_build=os.environ.get("FORCE_BUILD", "").lower() == "true",
    )
