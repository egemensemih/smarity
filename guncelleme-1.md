SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/config.yaml
+++ b/config.yaml
@@ -12,5 +12,5 @@
   url: "https://smarity.com.tr"
   posts_per_page: 18
-  contact_email: "smarityco@gmail.com"   # Hakkında sayfasında görünür
+  contact_email: "smarityco@gmail.com"   # Hakkında, İletişim ve Gizlilik sayfalarında görünür
   # Takip kanalları: yazılanlar sitede "Takip et" bölümünde ve alt bilgide görünür
   instagram: ""            # Instagram kullanıcı adı (boşsa bağlanan hesap kullanılır)
@@ -18,4 +18,18 @@
   whatsapp: ""             # WhatsApp kanalı bağlantısı (https://whatsapp.com/channel/...)
   x: ""                    # X (Twitter) kullanıcı adı
+
+# İletişim ve künye sayfası (/iletisim/) ile gizlilik sayfasında görünür. Boş bırakılan satır sayfada gösterilmez.
+# 5651 sayılı Kanun gereği içerik sağlayıcının tanıtıcı bilgileri (gerçek kişiyse ad soyad ve adres, şirketse unvan ve
+# adres) sitede yer almalıdır.
+legal:
+  owner: ""                # Yayın sahibi (ad soyad ya da şirket unvanı)
+  editor: ""               # Sorumlu yazı işleri müdürü (varsa)
+  address: ""              # Yönetim yeri / tebligat adresi
+  phone: ""                # İsteğe bağlı
+
+# Ziyaretçi istatistiği: Cloudflare Web Analytics (ücretsiz, çerez kullanmaz). Cloudflare → Web Analytics → siteyi ekle →
+# verilen koddaki "token" değerini buraya yaz.
+analytics:
+  cloudflare_token: ""
 
 home:
--- a/haberbot/site.py
+++ b/haberbot/site.py
@@ -18,5 +18,5 @@
 from .util import clip, hours_since, iso, local, log, now_utc, parse_iso, slugify, tr_date
 
-ASSET_V = "18"
+ASSET_V = "19"
 FOREIGN_PRICE = re.compile(r"(?=.*fiyat)(?=.*(\$|€|£|¥|dolar|euro|avro|sterlin|yuan|yen\b))", re.I)
 WHY_RE = re.compile(r"<p><strong>Neden önemli\?</strong>\s*(.*?)</p>", re.S)
@@ -460,7 +460,10 @@
             "search_url": f"{b}/ara/",
             "search_index": f"{b}/api/search.json?v={max((p['ts'] for p in posts), default=0)}",
+            # ziyaretçi istatistiği: Cloudflare Web Analytics (çerezsiz); belirteç Cloudflare panelinden alınır
+            "cf_analytics": str(((cfg.raw.get("analytics") or {}).get("cloudflare_token") or "")).strip(),
         }
         site["follow"] = follow_links(site)
-        ctx = {"site": site}
+        legal = {k: str(v).strip() for k, v in (cfg.raw.get("legal") or {}).items() if v}
+        ctx = {"site": site, "legal": legal}
 
         # statik dosyalar, logo ve görseller
@@ -564,4 +567,8 @@
             **ctx, canonical=f"{cfg.site_url}/hakkinda/",
             sources=[s for s in cfg.sources]))
+        self._write("gizlilik/index.html", self.env.get_template("privacy.html").render(
+            **ctx, canonical=f"{cfg.site_url}/gizlilik/"))
+        self._write("iletisim/index.html", self.env.get_template("contact.html").render(
+            **ctx, canonical=f"{cfg.site_url}/iletisim/"))
         self._write("404.html", self.env.get_template("404.html").render(**ctx, canonical=cfg.site_url + "/", noindex=True))
         # arama sayfası (/ara/?q=…) ve tarayıcıda aranan haber dizini
--- a/static/style.css
+++ b/static/style.css
@@ -457,4 +457,9 @@
 .prose ul { padding-left: 1.2em; }
 .prose li { margin: 8px 0; }
+.prose h3 { font-size: 21px; letter-spacing: -.02em; margin: 28px 0 8px; }
+.kunye { display: grid; grid-template-columns: max-content 1fr; gap: 10px 24px; font-size: 17px; margin: 16px 0; }
+.kunye dt { color: var(--muted); }
+.kunye dd { margin: 0; }
+@media (max-width: 560px) { .kunye { grid-template-columns: 1fr; gap: 2px; } .kunye dd { margin-bottom: 10px; } }
 .prose a { color: var(--link); }
 
--- a/templates/about.html
+++ b/templates/about.html
@@ -18,5 +18,5 @@
     <li><strong>Fotoğraflar kaynağıyla.</strong> Haberlerdeki fotoğraflar, öncelikle ilgili şirketin basın için yayımladığı görsellerdir; bunlar yoksa haberin kaynağında yayımlanan görseller kullanılır. Her fotoğrafın altında kaynağı ve bağlantısı yer alır. Fotoğraf bulunamayan haberlerde habere özel tipografik kapak kullanılır.</li>
     <li><strong>Kaldırma talepleri.</strong> Bir fotoğrafın ya da metnin hak sahibiyseniz ve kaldırılmasını istiyorsanız {% if site.contact_email %}<strong>{{ site.contact_email }}</strong> adresine{% else %}bize{% endif %} yazın; talebiniz hızla değerlendirilir.</li>
-    <li><strong>İnsan denetimi.</strong> Haberler editör onayından geçer. Güvenilirliği kanıtlanmış kaynaklardan gelen net haberler otomatik yayımlanabilir; bu durum haberin altında belirtilir.</li>
+    <li><strong>Yapay zeka destekli yayın masası.</strong> Haberler yapay zeka destekli yayın masasında seçilir, yazılır ve yayımlanır; bu durum her haberin altında belirtilir. Doğrulanmamış iddialar, söylentiler ve kaynakları çelişen haberler yayımlanmaz. Editör, yayındaki haberleri denetler; hatalı bulunanları düzeltir ya da kaldırır.</li>
     <li><strong>Düzeltme.</strong> Hatalı bir bilgi fark edersek haberi güncelleriz ya da kaldırırız.</li>
   </ul>
@@ -24,5 +24,5 @@
   <p>{% for s in sources %}{{ s.name }}{{ ', ' if not loop.last }}{% endfor %}.</p>
   <h2>İletişim</h2>
-  <p>{% if site.contact_email %}Hata bildirimi, öneri ve telif talepleri için: <strong>{{ site.contact_email }}</strong>{% else %}İletişim adresi yakında eklenecek.{% endif %}</p>
+  <p>{% if site.contact_email %}Hata bildirimi, öneri ve telif talepleri için: <strong>{{ site.contact_email }}</strong>. {% endif %}Künye ve ayrıntılar: <a href="{{ site.base }}/iletisim/">İletişim ve künye</a> · <a href="{{ site.base }}/gizlilik/">Gizlilik ve çerez politikası</a>.</p>
 </article>
 {% endblock %}
--- a/templates/article.html
+++ b/templates/article.html
@@ -140,8 +140,8 @@
     <p class="disclosure">
       Bu haber, yukarıdaki kaynaklardan yapay zeka yardımıyla Türkçe derlenmiş
-      {%- if post.publish_mode == 'auto' %} ve güvenilir kaynak kuralları çerçevesinde otomatik yayımlanmıştır.{% else %} ve editör onayıyla yayımlanmıştır.{% endif %}
+      {%- if post.publish_mode == 'auto' %} ve yayın masasının doğruluk kuralları çerçevesinde otomatik yayımlanmıştır.{% else %} ve editör onayıyla yayımlanmıştır.{% endif %}
       {% if post.has_photo %}Fotoğraflar, altlarında belirtilen kaynaklara aittir.{% endif %}
       Ayrıntılar ve orijinal ifadeler için kaynaklara başvurun.{% if post.updated_str %} Son güncelleme: {{ post.updated_str }}.{% endif %}
-      Bir hata görürseniz <a href="{{ site.base }}/hakkinda/">bize bildirin</a>.
+      Bir hata görürseniz <a href="{{ site.base }}/iletisim/">bize bildirin</a>.
     </p>
   </section>
--- a/templates/base.html
+++ b/templates/base.html
@@ -92,5 +92,6 @@
       <a href="{{ site.base }}/hakkinda/">Hakkında</a>
       <a href="{{ site.base }}/hakkinda/#ilkeler">Yayın ilkeleri</a>
-      {% if site.contact_email %}<a href="mailto:{{ site.contact_email }}">İletişim</a>{% endif %}
+      <a href="{{ site.base }}/iletisim/">İletişim ve künye</a>
+      <a href="{{ site.base }}/gizlilik/">Gizlilik ve çerezler</a>
     </nav>
     {% if site.top_tags %}
@@ -124,4 +125,5 @@
 {% endif %}
 <script src="{{ site.base }}/static/site.js?v={{ site.asset_v }}" defer></script>
+{% if site.cf_analytics %}<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{"token": "{{ site.cf_analytics }}"}'></script>{% endif %}
 </body>
 </html>
--- a/templates/sitemap.xml
+++ b/templates/sitemap.xml
@@ -3,4 +3,6 @@
   <url><loc>{{ site.url }}/</loc><lastmod>{{ site.built_iso }}</lastmod></url>
   <url><loc>{{ site.url }}/hakkinda/</loc></url>
+  <url><loc>{{ site.url }}/iletisim/</loc></url>
+  <url><loc>{{ site.url }}/gizlilik/</loc></url>
   <url><loc>{{ site.url }}/haberler/</loc><lastmod>{{ site.built_iso }}</lastmod></url>
   {% for n in range(2, pages + 1) %}
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -403,4 +403,24 @@
         assert a.store.load_post("p03")["photos_filled"]
 
+def test_legal_pages_and_analytics():
+    with _App() as (cfg, a):
+        a.store.save_post(_post(1, 2))
+        SiteBuilder(cfg).build()
+        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
+        assert "cloudflareinsights" not in home                       # belirteç yokken istatistik kodu eklenmez
+        assert "/iletisim/" in home and "/gizlilik/" in home          # alt bilgide bağlantılar
+        priv = (cfg.out_dir / "gizlilik" / "index.html").read_text(encoding="utf-8")
+        cont = (cfg.out_dir / "iletisim" / "index.html").read_text(encoding="utf-8")
+        assert "KVKK" in priv and "çerez" in priv and "Yayın sahibi" not in cont   # boş künye satırı gösterilmez
+        sm = (cfg.out_dir / "sitemap.xml").read_text(encoding="utf-8")
+        assert "/gizlilik/" in sm and "/iletisim/" in sm
+        cfg.raw["analytics"] = {"cloudflare_token": "abc123"}
+        cfg.raw["legal"] = {"owner": "Örnek Medya", "address": "İstanbul"}
+        SiteBuilder(cfg).build()
+        home = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
+        assert '"token": "abc123"' in home and "static.cloudflareinsights.com/beacon.min.js" in home
+        cont = (cfg.out_dir / "iletisim" / "index.html").read_text(encoding="utf-8")
+        assert "Yayın sahibi" in cont and "Örnek Medya" in cont and "İstanbul" in cont
+
 if __name__ == "__main__":
     for name, fn in list(globals().items()):
@@@SM@@@ FILE templates/contact.html
{% extends "base.html" %}
{% block title %}İletişim ve künye | {{ site.name }}{% endblock %}
{% block description %}{{ site.name }} iletişim bilgileri, künye, hata bildirimi, düzeltme ve kaldırma talepleri.{% endblock %}
{% block main %}
<header class="page-head wrap" style="--c:#6E6E73">
  <span class="eyebrow">İletişim</span>
  <h1>İletişim<br>ve künye</h1>
  <p>Hata bildirimi, düzeltme ve cevap talepleri, telif ve kaldırma istekleri ya da önerilerin için bize yaz.</p>
</header>
<article class="narrow prose">
  <h2>Bize ulaş</h2>
  {% if site.contact_email %}
  <p>E-posta: <a href="mailto:{{ site.contact_email }}"><strong>{{ site.contact_email }}</strong></a></p>
  {% else %}
  <p>İletişim adresi yakında eklenecek.</p>
  {% endif %}
  <ul>
    <li><strong>Hata bildirimi ve düzeltme:</strong> Haberin adresini ve hatalı bilgiyi yazman yeterli. Haklı bulunan düzeltmeleri hızla yaparız; haberin altında güncelleme notu yer alır.</li>
    <li><strong>Cevap ve düzeltme hakkı:</strong> Bir haberde adı geçen kişi ya da kurumsan, cevap ve düzeltme metnini bize gönderebilirsin.</li>
    <li><strong>Telif ve kaldırma talepleri:</strong> Bir fotoğrafın ya da metnin hak sahibiysen, ilgili haberin adresini ve hak sahipliğini gösteren bilgiyi ilet; talebin öncelikle değerlendirilir.</li>
  </ul>

  <h2 id="kunye">Künye</h2>
  <dl class="kunye">
    <dt>Yayın adı</dt><dd>{{ site.name }}</dd>
    <dt>İnternet adresi</dt><dd>{{ site.url | replace("https://", "") }}</dd>
    <dt>Yayın türü</dt><dd>Türkçe teknoloji haberleri, internet sitesi</dd>
    {% if legal.owner %}<dt>Yayın sahibi</dt><dd>{{ legal.owner }}</dd>{% endif %}
    {% if legal.editor %}<dt>Sorumlu yazı işleri müdürü</dt><dd>{{ legal.editor }}</dd>{% endif %}
    {% if legal.address %}<dt>Yönetim yeri</dt><dd>{{ legal.address }}</dd>{% endif %}
    {% if legal.phone %}<dt>Telefon</dt><dd>{{ legal.phone }}</dd>{% endif %}
    {% if site.contact_email %}<dt>E-posta</dt><dd><a href="mailto:{{ site.contact_email }}">{{ site.contact_email }}</a></dd>{% endif %}
    <dt>Yer sağlayıcı</dt><dd>GitHub, Inc. (GitHub Pages)</dd>
    <dt>İçerik dağıtımı</dt><dd>Cloudflare, Inc.</dd>
  </dl>

  <h2>Nasıl çalışıyoruz?</h2>
  <p>Haberler, teknoloji şirketlerinin resmi duyuruları ve saygın yayınlar taranarak yapay zeka destekli yayın masasında seçilir ve Türkçe olarak özgün biçimde yazılır. Her haberde kaynaklar adıyla ve bağlantısıyla belirtilir. Ayrıntılar: <a href="{{ site.base }}/hakkinda/#ilkeler">Yayın ilkelerimiz</a> · <a href="{{ site.base }}/gizlilik/">Gizlilik ve çerez politikası</a>.</p>
</article>
{% endblock %}
@@@SM@@@ FILE templates/privacy.html
{% extends "base.html" %}
{% block title %}Gizlilik ve çerez politikası | {{ site.name }}{% endblock %}
{% block description %}{{ site.name }} hangi verileri işler? Çerez kullanmayan ziyaretçi istatistiği, cihazında tutulan okuma bilgisi, hizmet sağlayıcılar ve KVKK kapsamındaki hakların.{% endblock %}
{% block main %}
<header class="page-head wrap" style="--c:#6E6E73">
  <span class="eyebrow">Gizlilik</span>
  <h1>Gizlilik ve<br>çerez politikası</h1>
  <p>Kısaca: üyelik, yorum ya da form yok; adını ve e-postanı istemiyoruz. Reklam ve takip çerezi kullanmıyoruz.</p>
</header>
<article class="narrow prose">
  <p><em>Yürürlük tarihi: {{ legal.updated or "1 Kasım 2026" }}.</em> Bu metin, 6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK) kapsamında aydınlatma amacıyla hazırlanmıştır.</p>

  <h2>Veri sorumlusu</h2>
  <p>{{ legal.owner or site.name }}{% if legal.address %}, {{ legal.address }}{% endif %}.
  {% if site.contact_email %}Bu metinle ilgili her konuda <a href="mailto:{{ site.contact_email }}">{{ site.contact_email }}</a> adresinden bize ulaşabilirsin.{% endif %}
  Künye bilgileri için <a href="{{ site.base }}/iletisim/">İletişim ve künye</a> sayfasına bakabilirsin.</p>

  <h2>Hangi veriler, neden işleniyor?</h2>
  <h3>1. Teknik kayıtlar</h3>
  <p>Site, barındırma hizmeti (GitHub Pages) ve içerik dağıtım ile güvenlik hizmeti (Cloudflare) üzerinden sunulur. Bu sağlayıcılar, sayfayı sana ulaştırabilmek ve siteyi saldırılara karşı korumak için IP adresi, tarayıcı ve cihaz bilgisi, istenen sayfa ve zaman gibi teknik kayıtları işler. Hukuki sebep: hizmetin sunulması ve güvenliği için meşru menfaat (KVKK m. 5/2-f). Bu kayıtları biz ayrıca toplamıyor ve saklamıyoruz; sağlayıcılar kendi politikalarına göre saklar.</p>
  <h3>2. Ziyaretçi istatistikleri</h3>
  <p>Hangi haberlerin okunduğunu görmek için Cloudflare Web Analytics kullanıyoruz. Bu hizmet çerez kullanmaz, cihazında bilgi saklamaz ve ziyaretçileri tek tek tanımlamaz; yalnızca toplam sayıları (sayfa görüntüleme, ülke, cihaz türü, siteye nereden gelindiği, sayfa hızı) gösterir.</p>
  <h3>3. Cihazında tutulan bilgiler</h3>
  <p>Okuduğun haberleri "Okundu" diye işaretlemek, son ziyaretinden beri kaç yeni haber çıktığını göstermek ve manşette daha önce gördüğün haberleri geriye almak için tarayıcının yerel depolama alanında haber kimlikleri ve son ziyaret zamanın tutulur. Bu bilgiler cihazından çıkmaz, bize ya da başka birine gönderilmez. Tarayıcının site verilerini silerek istediğin zaman kaldırabilirsin.</p>
  <h3>4. Başka sitelerden yüklenen içerikler</h3>
  <ul>
    <li><strong>Yazı tipi:</strong> Sitenin yazı tipi Google Fonts'tan yüklenir; bu sırada IP adresin Google'a iletilir.</li>
    <li><strong>Fotoğraflar:</strong> Haberlerdeki bazı fotoğraflar, haberin kaynağı olan sitelerden doğrudan gösterilir; bu sitelere IP adresin iletilebilir.</li>
    <li><strong>Paylaşım:</strong> Paylaş bağlantıları yalnızca tıklarsan ilgili platforma (Telegram, WhatsApp, X vb.) gider.</li>
  </ul>

  <h2>Çerezler</h2>
  <p>{{ site.name }} kendisi çerez kullanmaz; reklam, pazarlama ya da takip çerezi yoktur. Cloudflare, siteyi kötü amaçlı trafiğe karşı korumak için gerektiğinde zorunlu güvenlik çerezleri kullanabilir. Bu çerezler seni tanımlamak ya da reklam göstermek için kullanılmaz.</p>

  <h2>Yurt dışındaki hizmet sağlayıcılar</h2>
  <p>Yukarıda adı geçen hizmet sağlayıcıların (GitHub, Cloudflare, Google) sunucuları Türkiye dışında bulunabilir. Teknik kayıtlar bu sağlayıcılar tarafından, hizmetin sunulması amacıyla ve kendi gizlilik politikaları çerçevesinde işlenir.</p>

  <h2>Hakların</h2>
  <p>KVKK'nın 11. maddesi uyarınca kişisel verilerinin işlenip işlenmediğini öğrenme, işlenmişse bilgi isteme, amacını ve kimlere aktarıldığını öğrenme, eksik ya da yanlış işlenmişse düzeltilmesini, şartları oluşmuşsa silinmesini isteme ve zarara uğraman hâlinde zararın giderilmesini talep etme haklarına sahipsin.{% if site.contact_email %} Taleplerini <a href="mailto:{{ site.contact_email }}">{{ site.contact_email }}</a> adresine iletebilirsin.{% endif %}</p>

  <h2>Değişiklikler</h2>
  <p>Bu politikayı güncellediğimizde yürürlük tarihi de değişir. Önemli bir değişiklik olursa bu sayfada belirtilir.</p>
</article>
{% endblock %}
@@@SM@@@ SHA
6fcde4a4ba03562b96eb3244356e77b23917afcfbd1bf19cf565176eaa7639f2 config.yaml
7ec28055b7303987805c22f211d18a3837d1af6837049742baec75c907e2f6af haberbot/site.py
e5bff38a8ceca6986ec9c54eb27e1e5405da1541f28fc7c816528fc18ae9cb27 static/style.css
e3de36bf3e233b8e8fe739224be5bccbbcc275e88d24b2c85a944fb0e4dfdec2 templates/about.html
1686a2ec185a8de1536a48cd3198f0662520a7f47ed18ff5330425c901f06375 templates/article.html
f50f52ca9ab05de1cb7cbf0b8c556dd4486ca0a0a2de8259b88015007dec6339 templates/base.html
8d95aeaeadbdae9c0d1018c4cb023789a6d34d013d5cb014d68145a5f3c3e33c templates/sitemap.xml
94760af3643afddc99b8825db0a3e50968c4f10f1b1f400637d1b75d44c1b214 tests/test_home.py
eac50624b32621dc5417e99d04fa5632d09ab4190c67d3fc801e1ee15da076b7 templates/contact.html
91f9870b71bc9b77dcb3ecb03c77b00c94656e82636a66205accbf1a565fed29 templates/privacy.html
