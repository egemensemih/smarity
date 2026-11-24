SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -665,6 +665,6 @@
 3. Layout: no cut-off, overlapping or overflowing text, no clipped words, nothing lost at the edges, no empty or broken
    photo area, no awkward crop (faces cut through the eyes, the product cut in half, the subject hidden behind the text).
-4. Story safe area: in the 1080x1920 story the logo, photo, headline and the white "Haberi oku" button stay out of the
-   top 13% and the bottom 18%, where Instagram draws its own bars.
+4. Story safe area: in the 1080x1920 story the logo, photo, headline and the "Haberin devamı smarity.com.tr'de" line stay
+   out of the top 13% and the bottom 18%, where Instagram draws its own bars. The story has no button on purpose.
 5. Taste and accuracy: nothing offensive, graphic, sexual or mocking; the picture matches the headline and does not
    mislead; the set looks professional and consistent.
--- a/templates/cards/manset.html
+++ b/templates/cards/manset.html
@@ -3,5 +3,6 @@
          points (gönderi 2/3: öne çıkan 3 madde, fotoğrafın bulanık hâli zeminde)
          why    (gönderi 3/3: neden önemli + haberin tamamı için yönlendirme)
-         story  (hikâye 1080×1920: fotoğraf kırpılmadan ortada, başlık, "Haberi oku" düğmesi; Instagram'ın üst ve alt
+         story  (hikâye 1080×1920: fotoğraf kırpılmadan ortada, başlık, "Haberin devamı smarity.com.tr'de" satırı (düğme yok:
+                 otomatik paylaşımda tıklanabilir bağlantı eklenemiyor); Instagram'ın üst ve alt
                  çubuklarına denk gelen alanlarda yalnızca zemin var — üst 250 px, alt 340 px)
    Fotoğraf yoksa kategori renginde koyu, yumuşak ışıklı zemin. #}
@@ -42,4 +43,7 @@
 .btn { display: inline-flex; align-items: center; gap: 14px; font-weight: 700; font-size: 40px; line-height: 1;
   padding: 28px 46px; border-radius: 999px; background: #fff; color: var(--ink); }
+.more { margin-top: 40px; padding-top: 30px; border-top: 2px solid rgba(255,255,255,.16); font-size: 36px; line-height: 1.2;
+  letter-spacing: -.012em; color: rgba(255,255,255,.80); }
+.more b { color: #fff; font-weight: 700; }
 .col { position: absolute; left: 64px; right: 64px; display: flex; flex-direction: column; justify-content: center; }
 </style></head>
@@ -107,8 +111,5 @@
       <div class="meta" style="margin-top:20px;font-size:26px">Kaynak: {{ credits }}</div>
     </div>
-    <div style="margin-top:44px;display:flex;align-items:center;gap:28px;flex-wrap:wrap">
-      <span class="btn">Haberi oku {{ arrow }}</span>
-      {% if auto %}<span class="meta" style="font-size:28px;line-height:1.3">Bağlantı profilde<br>{{ site_host }}</span>{% endif %}
-    </div>
+    <div class="more">Haberin devamı <b>{{ site_host or "smarity.com.tr" }}</b>'de</div>
   </div>
 {% endif %}
@@@SM@@@ SHA
846aa386b13f75f7b545648e61bfa5cc4606cf62e6a6ec8685b21089b38431ce haberbot/prompts.py
3ebdf67ce017254d03fe4a283dff229a8896869e1d82de882b6af8a2dc20bf62 templates/cards/manset.html
