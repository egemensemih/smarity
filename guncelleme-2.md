SMARITY-BUNDLE v1 part 2/6
+        <div class="facts-stat"><span class="stat">{{ post.hero_stat }}</span>{% if post.hero_stat_label %}<span class="stat-label">{{ post.hero_stat_label }}</span>{% endif %}</div>
+        {% endif %}
+        {% if post.key_points %}
+        <div class="facts-list">
+          <h2 class="facts-title">Öne çıkanlar</h2>
+          <ol>{% for t in post.key_points %}<li>{{ t }}</li>{% endfor %}</ol>
+        </div>
+        {% endif %}
+      </section>
+      {% endif %}
+
+      <div class="art-body">{{ post.body_html|safe }}</div>
+
+      {% if post.tag_list %}
+      <nav class="art-tags" aria-label="Konular">
+        <span class="muted">Konular</span>
+        {% for t in post.tag_list %}<a href="{{ t.url }}">{{ t.label }}</a>{% endfor %}
+      </nav>
+      {% endif %}
+
+      <section class="sources" aria-labelledby="kaynaklar">
+        <h2 id="kaynaklar">Kaynaklar</h2>
+        <ol>
+          {% for s in post.sources %}
+          <li><a href="{{ s.url }}" rel="noopener" target="_blank">
+            <span><span class="s-name">{{ s.name }}</span>{% if s.via %} <span class="muted">({{ s.via }} üzerinden)</span>{% endif %}<span class="s-title">{{ s.title }}</span></span>
+            <span class="s-go" aria-hidden="true">↗</span>
+          </a></li>
+          {% endfor %}
+        </ol>
+        <p class="disclosure">
+          Bu haber, yukarıdaki kaynaklardan yapay zeka yardımıyla Türkçe derlenmiş
+          {%- if post.publish_mode == 'auto' %} ve güvenilir kaynak kuralları çerçevesinde otomatik yayımlanmıştır.{% else %} ve editör onayıyla yayımlanmıştır.{% endif %}
+          Ayrıntılar ve orijinal ifadeler için kaynaklara başvurun.{% if post.updated_str %} Son güncelleme: {{ post.updated_str }}.{% endif %}
+          Bir hata görürseniz <a href="{{ site.base }}/hakkinda/">bize bildirin</a>.
+        </p>
+      </section>
+    </div>
+
+    <aside class="art-side" aria-label="Haber bilgileri">
+      <div class="side-in">
+        {% if post.toc|length > 1 %}
+        <nav class="toc" aria-label="Bu haberde">
+          <p class="side-h">Bu haberde</p>
+          <ol>{% for h in post.toc %}<li><a href="#{{ h.id }}">{{ h.text }}</a></li>{% endfor %}<li><a href="#kaynaklar">Kaynaklar</a></li></ol>
+        </nav>
+        {% endif %}
+        <div class="share">
+          <p class="side-h">Paylaş</p>
+          <a href="https://x.com/intent/post?url={{ post.abs_url|urlencode }}&text={{ post.title|urlencode }}" rel="noopener" target="_blank">X</a>
+          <a href="https://www.linkedin.com/sharing/share-offsite/?url={{ post.abs_url|urlencode }}" rel="noopener" target="_blank">LinkedIn</a>
+          <a href="https://wa.me/?text={{ (post.title ~ ' ' ~ post.abs_url)|urlencode }}" rel="noopener" target="_blank">WhatsApp</a>
+          <button type="button" data-copy="{{ post.abs_url }}">Bağlantıyı kopyala</button>
+        </div>
+      </div>
+    </aside>
   </div>
 </article>
 
--- a/templates/index.html
+++ b/templates/index.html
@@ -18,7 +18,8 @@
 
 {% block main %}
 <header class="home-head wrap">
-  <h1>{{ site.home_h1 }}</h1>
+  <h1 class="sr-only">{{ site.home_h1 }}</h1>
+  <p class="home-date"><time datetime="{{ site.built_iso[:10] }}">{{ site.today_str }}</time></p>
   {% if featured %}
