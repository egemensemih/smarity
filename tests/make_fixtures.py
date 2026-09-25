"""Test için örnek kaynak dosyaları üretir (tarihler 'şimdi'ye göre ayarlanır)."""
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).parent / "fixtures"
NOW = datetime.now(timezone.utc)


def rss(title, items):
    body = []
    for t, link, desc, hours_ago in items:
        d = format_datetime(NOW - timedelta(hours=hours_ago))
        body.append(f"<item><title>{escape(t)}</title><link>{escape(link)}</link>"
                    f"<description>{escape(desc)}</description><pubDate>{d}</pubDate></item>")
    return (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{escape(title)}</title>'
            + "".join(body) + "</channel></rss>")


def atom(title, items):
    body = []
    for t, link, desc, hours_ago in items:
        d = (NOW - timedelta(hours=hours_ago)).isoformat()
        body.append(f'<entry><title>{escape(t)}</title><link rel="alternate" href="{escape(link)}"/>'
                    f"<summary>{escape(desc)}</summary><updated>{d}</updated></entry>")
    return (f'<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>{escape(title)}</title>'
            + "".join(body) + "</feed>")


# Başlıklar kaynaklarda gerçekten yayımlanmış haberlerden alınmıştır (25 Eylül 2026); açıklamalar kısaltılmıştır.
FILES = {
    "apple.xml": atom("Apple Newsroom", [
        ("The new Mac mini and Mac Studio are available today", "https://www.apple.com/newsroom/2026/09/the-new-mac-mini-and-mac-studio-are-available-today/",
         "The new Mac mini and Mac Studio are available today.", 10),
    ]),
    "google.xml": rss("The Keyword", [
        ("Anyone can make stunning HD videos with Gemini Omni in Google Vids", "https://blog.google/products/workspace/google-vids-gemini-omni/",
         "Google Vids now uses Gemini Omni to create HD videos.", 14),
    ]),
    "techcrunch.xml": rss("TechCrunch", [
        ("Nexterity wants to automate the hard, dangerous part of pipefitting",
         "https://techcrunch.com/2026/09/24/nexterity-pipefitting-robots/?utm_source=rss",
         "Nexterity builds robots for pipefitting.", 6),
        ("Waymo is scaling fast. Here's what the fleet data shows.",
         "https://techcrunch.com/2026/09/24/waymo-scaling-fleet-data/", "Waymo fleet data analysis.", 8),
    ]),
    "electrek.xml": rss("Electrek", [
        ("Volkswagen delays its electric minibus for the US — again",
         "https://electrek.co/2026/09/24/volkswagen-delays-electric-minibus-us/", "VW delays the ID. Buzz for the US.", 5),
    ]),
    "ign.xml": rss("IGN News", [
        ("PlayStation Reportedly Polling Game Developers After Decision to Kill Discs Sparks Backlash",
         "https://www.ign.com/articles/playstation-polling-developers-discs", "PlayStation polls developers.", 3),
        ("This week's free Epic Games Store titles are Astrea and Mechabellum",
         "https://www.ign.com/articles/free-epic-games-this-week", "Free games of the week.", 4),
    ]),
    "egirisim.xml": rss("Egirisim", [
        ("Yerli oyun stüdyosu Circle Games, Tencent liderliğinde 25 milyon dolar yatırım aldı",
         "https://egirisim.com/2026/09/24/circle-games-25-milyon-dolar-yatirim/", "Circle Games yatırım aldı.", 7),
    ]),
    "new-atlas.xml": rss("New Atlas", [
        ("Z-fold pocket projector levels up to Full HD", "https://newatlas.com/tech/z-fold-pocket-projector-full-hd/",
         "A folding pocket projector now projects Full HD.", 9),
    ]),
    "donanimhaber.xml": rss("DonanımHaber", [
        ("Xiaomi TV S Pro RGB-Mini LED 2027 tanıtıldı: 5.000 nit parlaklık ve 180Hz ekran",
         "https://www.donanimhaber.com/xiaomi-tv-s-pro-rgb-mini-led-2027-tanitildi", "Xiaomi yeni televizyonunu tanıttı.", 11),
    ]),
    "hacker-news.xml": rss("HN", [
        ("Tesla 'FSD' sped in 55% of Brussels 30 km/h zones ahead of EU vote",
         "https://electrek.co/2026/09/24/tesla-fsd-brussels-speeding/", "Comments", 12),
    ]),
    "anthropic.html": """<html><body><main>
      <a href="/news/claude-for-life-sciences"><h3>Introducing the Life Sciences Verification Program</h3><span>Sep 24, 2026</span></a>
      <a href="/careers">Careers</a>
    </main></body></html>""",
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, content in FILES.items():
        (OUT / name).write_text(content, encoding="utf-8")
    print("fixtures:", ", ".join(FILES))
