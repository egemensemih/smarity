// Eski adres sayfası: kanonik adrese hemen geç (#bölüm korunur). Satır içi betik yok: içerik güvenlik politikası.
location.replace(document.querySelector('link[rel="canonical"]').href + location.hash);
