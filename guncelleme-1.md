SMARITY-BUNDLE v1 part 1/6
@@@SM@@@ PATCH
--- a/templates/article.html
+++ b/templates/article.html
@@ -41,8 +41,8 @@
 
 {% block main %}
 {{ crumbs([("Ana sayfa", site.base ~ "/", site.url ~ "/"), (post.cat_label, post.cat_url, post.abs_cat_url), (post.short_title or post.title, post.url, post.abs_url)]) }}
-<article style="--c:{{ post.cat_color }}">
-  <header class="art-head narrow">
+<article class="art" style="--c:{{ post.cat_color }}">
+  <header class="art-head wrap">
     <div class="meta-top">
       <a class="eyebrow" href="{{ post.cat_url }}">{{ post.cat_label }}</a>
       <time datetime="{{ post.iso }}">{{ post.date_str }}</time>
@@ -50,49 +50,74 @@
     </div>
     <h1>{{ post.title_disp }}</h1>
     <p class="dek">{{ post.summary }}</p>
-    <div class="share">
-      <a href="https://x.com/intent/post?url={{ post.abs_url|urlencode }}&text={{ post.title|urlencode }}" rel="noopener" target="_blank">X'te paylaş</a>
-      <a href="https://www.linkedin.com/sharing/share-offsite/?url={{ post.abs_url|urlencode }}" rel="noopener" target="_blank">LinkedIn</a>
-      <a href="https://wa.me/?text={{ (post.title ~ ' ' ~ post.abs_url)|urlencode }}" rel="noopener" target="_blank">WhatsApp</a>
-      <button type="button" data-copy="{{ post.abs_url }}">Bağlantıyı kopyala</button>
-    </div>
   </header>
 
-  <figure class="art-media">
+  <figure class="art-media wrap">
     <div class="ph">{{ img(post, eager=true, sizes='(min-width: 1232px) 1200px, 100vw', priority=true) }}</div>
     {% if not post.cover_image %}<figcaption>{% if post.ai_image %}Temsili görsel, yapay zeka ile üretilmiştir.{% else %}Temsili görsel.{% endif %}</figcaption>{% endif %}
   </figure>
 
-  <div class="narrow">
-    {% if post.hero_stat and not post.stat_on_cover %}
-    <div class="stat-band"><div class="stat">{{ post.hero_stat }}</div>{% if post.hero_stat_label %}<div class="stat-label">{{ post.hero_stat_label }}</div>{% endif %}</div>
-    {% endif %}
-    <div class="art-body">{{ post.body_html|safe }}</div>
-
-    {% if post.tag_list %}
-    <nav class="art-tags" aria-label="Konular">
-      <span class="muted">Konular</span>
-      {% for t in post.tag_list %}<a href="{{ t.url }}">{{ t.label }}</a>{% endfor %}
-    </nav>
-    {% endif %}
-
-    <section class="sources" aria-labelledby="kaynaklar">
-      <h2 id="kaynaklar">Kaynaklar</h2>
-      <ol>
-        {% for s in post.sources %}
-        <li><a href="{{ s.url }}" rel="noopener" target="_blank">
-          <span><span class="s-name">{{ s.name }}</span>{% if s.via %} <span class="muted">({{ s.via }} üzerinden)</span>{% endif %}<span class="s-title">{{ s.title }}</span></span>
-          <span class="s-go" aria-hidden="true">↗</span>
-        </a></li>
-        {% endfor %}
-      </ol>
-      <p class="disclosure">
-        Bu haber, yukarıdaki kaynaklardan yapay zeka yardımıyla Türkçe derlenmiş
-        {%- if post.publish_mode == 'auto' %} ve güvenilir kaynak kuralları çerçevesinde otomatik yayımlanmıştır.{% else %} ve editör onayıyla yayımlanmıştır.{% endif %}
-        Ayrıntılar ve orijinal ifadeler için kaynaklara başvurun.{% if post.updated_str %} Son güncelleme: {{ post.updated_str }}.{% endif %}
-        Bir hata görürseniz <a href="{{ site.base }}/hakkinda/">bize bildirin</a>.
-      </p>
-    </section>
+  <div class="art-grid wrap">
+    <div class="art-main">
+      {% if post.key_points or (post.hero_stat and not post.stat_on_cover) %}
+      <section class="facts" aria-label="Öne çıkanlar">
+        {% if post.hero_stat and not post.stat_on_cover %}
