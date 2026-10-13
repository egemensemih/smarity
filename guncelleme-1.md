SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/KURULUM.md
+++ b/KURULUM.md
@@ -87,5 +87,5 @@
 - **Düzeltme:** Haber mesajını yanıtla ve talimat yaz (ör. "başlığı kısalt").
 - Butona bastıktan sonra işlem genellikle birkaç dakikada, en geç ~15 dakikada gerçekleşir; mesaj güncellenir.
-- **Öğrenen mod:** Önce 30 karar vermen gerekir. Ardından en az 10 kararda %90 onay verdiğin kaynaklardan gelen net haberler otomatik yayınlanır. Bunlar sana sessiz bildirim olarak gelir ve **🗑 Kaldır** düğmesiyle geri alınabilir.
+- **Yayın kuralı (`/mod kural`, varsayılan):** Yayın yönetmeninin seçtiği haberlerden en az 3 farklı kaynakta çıkan ve geniş kitleye hitap eden ya da büyük bir markaya ait olanlar doğrudan yayınlanır (sessiz bildirim, **🗑 Kaldır** ile geri alınır). Geniş kitleli ama henüz 1-2 kaynakta olan haber sana sorulur; sen karar vermeden 3. kaynak gelirse kendiliğinden yayınlanır. Küçük kitleye hitap eden ve büyük marka olmayan haber, uyarı işaretli haberler ve Vivo / Oppo gibi listedeki markalar her zaman sorulur. Kısa sürede 2 otomatik haberi kaldırırsan otomatik yayın 3 gün durur (`/mod kural` ile hemen açılır). `/mod manuel`: her haber sorulur.
 - Komutlar: `/durum`, `/bekleyen`, `/mod`, `/topla`, `/duraklat`, `/devam`, `/kaynaklar`.
 
--- a/README.md
+++ b/README.md
@@ -24,5 +24,5 @@
  │    ├─ Kartlar: Instagram post 1080×1350, story 1080×1920, paylaşım kapağı 1200×630
  │    │   (Smarity logosuyla; renk ve düzen habere göre otomatik seçilir)
- │    └─ Karar: sana sor  |  otomatik yayınla (öğrenen mod)
+ │    └─ Karar: 3+ kaynak ve geniş kitle/büyük marka → otomatik  |  diğerleri sana sorulur (3. kaynak gelirse kendiliğinden yayınlanır)
  ├─ Onaylananları siteye ekle, GitHub Pages'e yayınla
  └─ Akşam: günlük özet
@@ -43,5 +43,5 @@
 ## Telegram komutları
 
-`/durum` · `/bekleyen` · `/mod manuel|ogrenen|tam` · `/topla` · `/duraklat` · `/devam` · `/kaynaklar` · `/yardim`
+`/durum` · `/bekleyen` · `/mod kural|manuel|tam` · `/topla` · `/duraklat` · `/devam` · `/kaynaklar` · `/yardim`
 
 Bir haberi düzeltmek için o haberin Telegram mesajını **yanıtla** ve talimatını yaz
--- a/config.yaml
+++ b/config.yaml
@@ -63,23 +63,18 @@
 
 autonomy:
-  # manuel  : her haber onayına gelir
-  # ogrenen : kararlarından öğrenir; güvendiği kaynaklardan gelen net haberleri kendisi yayınlar (önerilen)
-  # tam     : sadece şüpheli/riskli haberleri sorar, gerisini kendisi yayınlar
-  # Telegram'dan /mod komutuyla da değiştirebilirsin.
-  mode: ogrenen
-  source_min_decisions: 10       # Bir kaynağa güvenmek için gereken en az karar sayısı
-  source_min_approval: 0.9       # ...ve o kaynaktaki onay oranı
-  global_window: 30              # Genel başarı için bakılan son karar sayısı
-  global_min_approval: 0.85      # Son kararlarda genel onay oranı bunun altındaysa otomatik yayın durur
-  auto_min_importance: 7         # Otomatik yayın için en düşük önem puanı
-  # Doğrudan yayın (tüm kategoriler): yönetmenin seçtiği haberlerden en az 3 farklı kaynakta çıkanlar onay beklemez.
-  # Uyarı işareti olan haber yine sorulur.
-  trusted_groups:
-    - name: "en az 3 farklı kaynakta çıkan haber"
-      min_sources: 3
-  auto_broad_importance: 8       # Puanı bunun altında (küçük kitle) VE büyük bir markaya ait olmayan haber yine sorulur
+  # Yayın kuralı (yalnızca yayın yönetmeninin seçtiği haberler için):
+  #   🟢 otomatik       : en az min_sources farklı kaynak + (geniş kitle [puan >= broad_importance] ya da büyük marka)
+  #   ⏳ sorar + bekler : geniş kitleli ama kaynak sayısı yetmiyor → sorulur; 3. kaynak gelirse kendiliğinden yayınlanır
+  #   🟡 sorar          : küçük kitle ve büyük marka değil
+  #   🔴 hep sorar      : uyarı işareti, never_auto markaları, güven 'düşük'
+  # Modlar: kural (önerilen) · manuel (her şey sorulur) · tam (yalnızca 🔴 sorulur). Telegram'dan /mod ile değiştirilir.
+  mode: kural
+  min_sources: 3                 # Otomatik yayın için gereken en az farklı kaynak (yayın kuruluşu) sayısı
+  broad_importance: 8            # Yönetmen puanı bu ve üstü = geniş kitle (büyük marka olmasa da otomatik olabilir)
+  auto_min_importance: 7         # Bunun altındaki haber hiçbir zaman otomatik yayınlanmaz
   # Bu markaların haberleri hiçbir zaman otomatik yayınlanmaz, her zaman onaya gelir
   never_auto: [Vivo, Oppo, Realme, Tecno, Infinix, iQOO, Nubia, ZTE, Meizu, itel, Poco, Redmi]
-  trusted_pause_removals: 2      # Bir gruptan son 7 günde bu kadar otomatik haberi kaldırırsan o grup yeniden onaya döner
+  pause_removals: 2              # Otomatik yayınlanan haberlerden pause_hours içinde bu kadarını kaldırırsan otomatik yayın durur
+  pause_hours: 72                # (/mod kural ile hemen yeniden açılır)
 
 images:
--- a/haberbot/app.py
+++ b/haberbot/app.py
@@ -43,9 +43,9 @@
     ("durum", "Sistem durumu ve istatistikler"),
     ("bekleyen", "Onay bekleyen haberler"),
-    ("mod", "Otonomi modu: manuel / ogrenen / tam"),
+    ("mod", "Yayın modu: manuel / kural / tam"),
     ("topla", "Kaynakları hemen tara"),
     ("duraklat", "Toplama ve otomatik yayını durdur"),
     ("devam", "Yeniden başlat"),
-    ("kaynaklar", "Kaynak güven puanları"),
+    ("kaynaklar", "Kaynaklar ve onay oranları"),
     ("manset", "Manşeti yönet: haberi manşete al / çıkar"),
     ("secki", "Yayın yönetmeninin son kararları (neden seçildi / elendi)"),
@@ -53,5 +53,5 @@
     ("yardim", "Nasıl kullanılır"),
 ]
-COMMANDS_VERSION = 4
+COMMANDS_VERSION = 5
 COVERLINE_V = 3               # kapak başlığı yazım kuralları değişince eski haberlerin kapak başlıkları yeniden yazılır
 PHOTO_VET_V = 2               # fotoğraf editörü ölçütleri değişince artır: son iki haftanın fotoğrafları yeniden denetlenir
@@ -79,5 +79,10 @@
 <b>Ana sayfa seçkisi:</b> Her haber ana sayfaya çıkmaz. Yapay zeka her habere bir ilgi puanı verir; puan ve tazeliğe göre en dikkat çekiciler manşete ve "Öne çıkanlar"a girer.
 
-<b>Öğrenen mod:</b> Kararların kaynak bazında kaydedilir. Bir kaynak yeterince onay alınca, o kaynaktan gelen net haberler otomatik yayınlanır ve sana sessizce bildirilir. Şüpheli işaretli haberler her zaman sana sorulur.
+<b>Yayın kuralı</b> (yönetmenin seçtiği haberler için):
+🟢 <b>Otomatik</b> — en az 3 farklı kaynakta çıkan ve geniş kitleye hitap eden ya da büyük bir markaya ait haber doğrudan yayınlanır, sana sessizce bildirilir.
+⏳ <b>Sorar + bekler</b> — geniş kitleli ama henüz 1-2 kaynakta olan haber sana sorulur; sen karar vermeden 3. kaynak gelirse kendiliğinden yayınlanır.
+🟡 <b>Sorar</b> — küçük kitleye hitap eden ve büyük marka olmayan haber.
+🔴 <b>Hep sorar</b> — uyarı işaretli (iddia, söylenti) haberler, Vivo / Oppo gibi listedeki markalar.
+Otomatik yayınlanan 2 haberi 3 gün içinde kaldırırsan otomatik yayın kendiliğinden durur; <code>/mod kural</code> ile yeniden açılır. <code>/mod manuel</code>: her şey sorulur.
 
 📸 <b>Instagram</b> — yayınlanan her haber birkaç dakika içinde carousel ve hikâye olarak Instagram'da paylaşılır. Sıradaki bir haberi mesajındaki <b>Instagram'a gönderme</b> düğmesiyle durdurabilirsin. Tümünü durdurmak için <code>/instagram kapat</code>.
@@ -937,6 +942,8 @@
         if d.get("focus_keyword") and kind in ("pending", "auto"):
             lines.append(f"🔎 Google: <i>{esc(d['focus_keyword'])}</i>")
-        if kind == "auto" and d.get("auto_group"):
-            lines.append(f"🤖 Otomatik yayın nedeni: {esc(d['auto_group'])}. Beğenmezsen Kaldır'a bas.")
+        if kind == "auto" and (d.get("auto_reason") or d.get("auto_group")):
+            late = " (sonradan gelen kaynaklarla)" if d.get("auto_late") else ""
+            lines.append(f"🤖 Otomatik yayın nedeni: {esc(d.get('auto_reason') or d['auto_group'])}{late}. "
+                         f"Beğenmezsen Kaldır'a bas.")
         if d.get("flags"):
             fl = ", ".join(FLAG_LABELS.get(f, f) for f in d["flags"])
@@ -946,5 +953,9 @@
             lines.append(f"📝 {esc(d['editor_note'])}")
         if kind == "pending" and d.get("policy_reason"):
-            lines.append(f"<i>Neden sordum: {esc(d['policy_reason'])}</i>")
+            if d.get("policy_tier") == "wait":
+                lines.append(f"⏳ <i>{esc(d['policy_reason'])}. Beklemek istemezsen Yayınla'ya bas.</i>")
+            else:
+                icon = policy.TIER_ICON.get(d.get("policy_tier"), "")
+                lines.append(f"{icon} <i>Neden sordum: {esc(d['policy_reason'])}</i>".strip())
         if kind in ("published", "auto", "updated") and d.get("slug"):
             lines.append(f'🔗 <a href="{esc(self.cfg.post_url(d))}">Sitede aç</a>')
@@ -1229,6 +1240,10 @@
             weight = 2 if d.get("publish_mode") == "auto" else 1
             policy.record(self.stats, d, ok=False, weight=weight)
-            if d.get("publish_mode") == "auto" and d.get("auto_group"):
-                policy.record_group_removal(self.stats, d["auto_group"])   # sık kaldırılırsa grup yeniden onaya döner
+            if d.get("publish_mode") == "auto" and policy.record_removal(self.cfg, self.stats):
+                until = policy.auto_paused_until(self.cfg, self.stats)
+                self.notify(f"⏸ <b>Otomatik yayın durdu</b>\nKısa sürede otomatik yayınlanan haberlerden "
+                            f"{self.cfg.get('autonomy', 'pause_removals', 2)} tanesini kaldırdın. "
+                            f"{esc(tr_date(until, self.cfg.tz))} tarihine kadar her haber sana sorulacak. "
+                            f"Hemen yeniden açmak için <code>/mod kural</code>", silent=True)
             st.bump(self.today(), "removed")
             st.archive_draft(d, "removed")
@@ -1408,11 +1423,18 @@
             self.notify(self.status_text(), silent=True)
         elif cmd == "mod":
-            if arg in policy.MODES:
-                self.state["mode_override"] = arg
-                self.notify(f"Mod: <b>{policy.MODES[arg]}</b>", silent=True)
+            m = policy.normalize_mode(arg)
+            if m:
+                self.state["mode_override"] = m
+                if m == "kural":
+                    policy.resume(self.stats)      # kaldırma freni sıfırlanır
+                n = self.recheck_pending()
+                self.notify(f"Mod: <b>{policy.MODES[m]}</b>" + (f"\n🤖 Bekleyenlerden {n} haber kurala uyduğu için yayınlandı."
+                                                                 if n else ""), silent=True)
             else:
                 m = policy.current_mode(self.cfg, self.state)
-                self.notify(f"Şu anki mod: <b>{policy.MODES[m]}</b>\nDeğiştirmek için: <code>/mod manuel</code>, "
-                            f"<code>/mod ogrenen</code> ya da <code>/mod tam</code>", silent=True)
+                self.notify(f"Şu anki mod: <b>{policy.MODES[m]}</b>\n"
+                            f"<code>/mod kural</code> — 3+ kaynakta çıkan geniş kitleli / büyük marka haberleri otomatik\n"
+                            f"<code>/mod manuel</code> — her haber sana sorulur\n"
+                            f"<code>/mod tam</code> — yalnızca uyarılı haberler ve listedeki markalar sorulur", silent=True)
         elif cmd == "duraklat":
             self.state["paused"] = True
@@ -1479,5 +1501,8 @@
         n, rate = policy.global_rate(self.cfg, self.stats)
         mode = policy.MODES[policy.current_mode(self.cfg, self.state)]
-        pend = len(self.store.drafts("pending"))
+        drafts = self.store.drafts("pending")
+        pend = len(drafts)
+        waiting = sum(1 for d in drafts if d.get("policy_tier") == "wait")
+        until = policy.auto_paused_until(self.cfg, self.stats)
         bad = [k for k, v in self.state.get("source_health", {}).items() if v.get("fails", 0) >= 3]
         lines = [
@@ -1486,6 +1511,9 @@
             f"Bugün: {c.get('published', 0)} yayın ({c.get('auto', 0)} otomatik, {c.get('approved', 0)} onayla), "
             f"{c.get('rejected', 0)} ret, {c.get('drafts', 0)} taslak",
-            f"Onay bekleyen: {pend} · Yazılmak için sırada: {len(self.state.get('queue') or [])}",
-            f"Son {n} kararda onay oranı: %{rate * 100:.0f}",
+            f"Onay bekleyen: {pend} ({waiting} tanesi 3. kaynağı bekliyor) · Yazılmak için sırada: "
+            f"{len(self.state.get('queue') or [])}",
+            (f"⏸ Otomatik yayın {esc(tr_date(until, self.cfg.tz))} tarihine kadar durdu (/mod kural ile aç)" if until
+             else f"Otomatik yayın kuralı: en az {policy.min_sources(self.cfg)} farklı kaynak + geniş kitle ya da büyük marka"),
+            f"Son {n} kararında onay oranın: %{rate * 100:.0f}",
             f"Toplam yayın: {len(self.store.posts())}",
             f"Bugünkü tahmini maliyet: ${self._cost(c):.2f} ({c.get('images', 0)} görsel)",
@@ -1507,15 +1535,55 @@
         lines = [f"📡 <b>{len(names)} kaynak</b> · {len(names) - len(broken)} okunuyor"
                  + (f" · ⚠️ okunamayan: {esc(', '.join(broken))}" if broken else ""),
-                 "", "🧭 <b>Kaynak güveni</b> (✅ = otomatik yayına uygun; yalnızca karar verdiğin kaynaklar)"]
+                 "", "🧭 <b>Kararların</b> (kaynak başına onay oranı; bilgi amaçlı, otomatik yayını etkilemez)"]
         rows = []
         for name in names:
-            ok, n, rate = policy.source_trust(self.cfg, self.stats, name)
+            n, rate = policy.source_rate(self.stats, name)
             if n:
-                rows.append((not ok, -n, f"{'✅' if ok else '▫️'} {esc(name)}: {n} karar, %{rate * 100:.0f} onay"))
-        lines += [r[2] for r in sorted(rows)[:40]] or ["Henüz karar yok."]
-        need = self.cfg.get("autonomy", "source_min_decisions", 10)
-        pct = self.cfg.get("autonomy", "source_min_approval", 0.9) * 100
-        lines.append(f"\nGüven için: en az {need} karar ve %{pct:.0f} onay.")
+                rows.append((-n, f"▫️ {esc(name)}: {n} karar, %{rate * 100:.0f} onay"))
+        lines += [r[1] for r in sorted(rows)[:40]] or ["Henüz karar yok."]
+        lines.append(f"\nOtomatik yayın kaynağa değil habere bakar: en az {policy.min_sources(self.cfg)} farklı kaynakta "
+                     f"çıkan, geniş kitleli ya da büyük markalı haberler.")
         return "\n".join(lines)[:4000]
+
+    # ── bekleyen taslakları kurala göre yeniden değerlendir ─────────────
+    def recheck_pending(self) -> int:
+        """Onay bekleyen taslaklara yeni kaynak eklendiyse (ya da mod / fren değiştiyse) kuralı yeniden uygula:
+        3. kaynağa ulaşan geniş kitleli haber kendiliğinden yayınlanır; Telegram'daki mesajı güncellenir."""
+        if self.state.get("paused"):
+            return 0
+        done = 0
+        for d in self.store.drafts("pending"):
+            old = (d.get("policy_tier"), d.get("policy_reason"))
+            decision, reason = policy.decide(self.cfg, self.state, self.stats, d)
+            d["policy_reason"] = reason
+            if decision == "auto":
+                try:
+                    if self._auto_promote(d):
+                        done += 1
+                except Exception as e:  # noqa: BLE001
+                    log.exception("Bekleyen taslak otomatik yayınlanamadı (%s): %s", d.get("id"), e)
+                continue
+            if old != (d.get("policy_tier"), reason):
+                self.store.save_draft(d)
+                self._update_preview(d, "pending")
+        if done:
+            log.info("Bekleyen %d taslak kurala uyduğu için otomatik yayınlandı", done)
+        return done
+
+    def _auto_promote(self, d: dict) -> bool:
+        d["auto_late"] = True
+        log.info("Taslak %s sonradan kurala uydu → otomatik (%s)", d["id"], d.get("policy_reason"))
+        if d.get("update_of"):
+            new = self.apply_update(d)
+            if not new:
+                self.store.archive_draft(d, "expired")
+                return False
+            self._update_preview({**d, "slug": new["slug"], "path": self.cfg.post_path(new)}, "updated")
+            return True
+        post = self.publish(d, auto=True)
+        self.store.bump(self.today(), "auto_late")
+        self._update_preview(post, "auto")
+        self._send_social(post)
+        return True
 
     # ── bakım ───────────────────────────────────────────────
@@ -1725,5 +1793,7 @@
             return
         text = (f"🌙 <b>Günün özeti</b>\n"
-                f"Yayın: {c.get('published', 0)} ({c.get('auto', 0)} otomatik, {c.get('approved', 0)} senin onayınla)\n"
+                f"Yayın: {c.get('published', 0)} ({c.get('auto', 0)} otomatik"
+                f"{f', {x} tanesi sonradan 3. kaynak gelince' if (x := c.get('auto_late', 0)) else ''}, "
+                f"{c.get('approved', 0)} senin onayınla)\n"
                 f"Güncellenen haber: {c.get('updated', 0)}\n"
                 f"Ret: {c.get('rejected', 0)} · Süresi dolan: {c.get('expired', 0)} · Kaldırılan: {c.get('removed', 0)}\n"
@@ -2435,4 +2505,8 @@
                 self.notify_error(f"Toplama sırasında hata: {type(e).__name__}: {e}")
         if not self.state.get("paused"):
+            try:
+                self.recheck_pending()
+            except Exception as e:  # noqa: BLE001
+                log.exception("Bekleyen taslak kontrolü hatası: %s", e)
             self.backfill_seo()
             try:
--- a/tests/test_core.py
+++ b/tests/test_core.py
@@ -12,72 +12,56 @@
 from haberbot.util import normalize_url, slugify, publisher_name  # noqa: E402
 
-CFG = Config(raw={"autonomy": {"mode": "ogrenen", "source_min_decisions": 10, "source_min_approval": 0.9,
-                               "global_window": 30, "global_min_approval": 0.85, "auto_min_importance": 6}})
-GOOD = {"id": "x", "flags": [], "confidence": "yuksek", "importance": 8, "source_keys": ["OpenAI"]}
+CFG = Config(raw={"autonomy": {"mode": "kural", "min_sources": 3, "broad_importance": 8, "auto_min_importance": 7,
+                               "never_auto": ["Vivo", "Oppo", "iQOO"], "pause_removals": 2, "pause_hours": 72}})
+THREE = [{"name": n, "url": n} for n in ("Webtekno", "LOG", "The Verge")]
+GOOD = {"id": "x", "flags": [], "confidence": "yuksek", "importance": 8, "category": "teknoloji", "sources": THREE,
+        "title": "Samsung Galaxy S27 tanıtıldı", "tags": ["Samsung"], "source_keys": ["Webtekno", "LOG", "The Verge"]}
 
 
-def test_policy_learning_path():
-    stats = {"sources": {}, "decisions": []}
-    assert policy.decide(CFG, {}, stats, GOOD)[0] == "ask"  # henüz karar yok
-    for i in range(30):
-        policy.record(stats, {"id": str(i), "source_keys": ["OpenAI"]}, ok=True)
-    assert policy.decide(CFG, {}, stats, GOOD)[0] == "auto"
-    # başka, güvenilmeyen kaynak → sor
-    assert policy.decide(CFG, {}, stats, {**GOOD, "source_keys": ["OpenAI", "Yeni"]})[0] == "ask"
-    # uyarı işareti → her zaman sor
-    assert policy.decide(CFG, {}, stats, {**GOOD, "flags": ["iddia"]})[0] == "ask"
-    assert policy.decide(CFG, {}, stats, {**GOOD, "confidence": "orta"})[0] == "ask"
-    # manuel mod
-    assert policy.decide(CFG, {"mode_override": "manuel"}, stats, GOOD)[0] == "ask"
-    # çok ret → genel oran düşer → sor
-    for i in range(10):
-        policy.record(stats, {"id": f"r{i}", "source_keys": ["OpenAI"]}, ok=False)
-    assert policy.decide(CFG, {}, stats, GOOD)[0] == "ask"
+def test_rule_three_sources_broad_or_big_brand():
+    stats = {"sources": {}, "decisions": [{"ok": False, "manual": True}] * 30}   # onay oranı artık karara etki etmez
+    d = dict(GOOD)
+    assert policy.decide(CFG, {}, stats, d) == ("auto", "3 farklı kaynak + geniş kitle")
+    assert d["policy_tier"] == "auto" and d["auto_reason"]
+    for cat in ("gaming", "otomotiv", "super-zeka", "girisimcilik", "inovasyon"):       # tüm kategoriler
+        assert policy.decide(CFG, {}, stats, {**GOOD, "category": cat})[0] == "auto"
+    # aynı kaynak iki kez sayılmaz
+    assert policy.decide(CFG, {}, stats, {**GOOD, "sources": [THREE[0], THREE[0], THREE[1]]})[0] == "ask"
+    # geniş kitleli ama 2 kaynak → sorar + bekler
+    w = {**GOOD, "sources": THREE[:2]}
+    assert policy.decide(CFG, {}, stats, w)[0] == "ask" and w["policy_tier"] == "wait"
+    # küçük kitle (puan 7) + büyük marka değil → sorar, kaynak artsa da beklemez
+    small = {**GOOD, "importance": 7, "title": "Nothing CMF hoparlör tanıttı", "tags": []}
+    assert policy.decide(CFG, {}, stats, small)[0] == "ask" and small["policy_tier"] == "ask"
+    # küçük puan ama büyük marka → otomatik
+    assert policy.decide(CFG, {}, stats, {**small, "big_brand": True}) == ("auto", "3 farklı kaynak + büyük marka")
+    # her zaman sorulanlar
+    for bad in ({"flags": ["iddia"]}, {"confidence": "dusuk"}, {"importance": 6},
+                {"title": "Vivo'nun yeni telefonu V80 Lite Türkiye'de"}, {"tags": ["iQOO"]},
+                {"title": "Oppo Find X10", "big_brand": True}):
+        x = {**GOOD, **bad}
+        assert policy.decide(CFG, {}, stats, x)[0] == "ask" and x["policy_tier"] == "hard", bad
+    assert policy.decide(CFG, {}, stats, {**GOOD, "confidence": "orta"})[0] == "auto"
+    assert policy.decide(CFG, {}, stats, {**GOOD, "title": "Vivos adlı yeni uygulama çıktı"})[0] == "auto"
 
 
-def test_trusted_groups_publish_directly():
-    cfg = Config(raw={"autonomy": {**CFG.raw["autonomy"], "auto_min_importance": 7, "trusted_pause_removals": 2,
-                                   "trusted_groups": [{"name": "oto/ai", "categories": ["otomotiv", "super-zeka"],
-                                                       "min_sources": 2}]}})
-    stats = {"sources": {}, "decisions": [{"ok": False, "manual": True}] * 30}      # genel onay oranı düşük
-    two = [{"name": "Webtekno", "url": "a"}, {"name": "ShiftDelete.Net", "url": "b"}]
-    car = {"id": "c", "flags": [], "confidence": "orta", "importance": 8, "category": "otomotiv", "sources": two}
-    assert policy.decide(cfg, {}, stats, car) == ("auto", "Güvenilir grup: oto/ai") and car["auto_group"] == "oto/ai"
-    assert policy.decide(cfg, {}, stats, {**car, "sources": two[:1]})[0] == "ask"               # tek kaynak
-    assert policy.decide(cfg, {}, stats, {**car, "sources": two * 2})[0] == "auto"              # aynı kaynaklar tekrar sayılmaz
-    assert policy.decide(cfg, {}, stats, {**car, "sources": [two[0], two[0]]})[0] == "ask"
-    assert policy.decide(cfg, {}, stats, {**car, "category": "teknoloji"})[0] == "ask"          # grup dışı kategori
-    assert policy.decide(cfg, {}, stats, {**car, "flags": ["iddia"]})[0] == "ask"               # uyarı işareti
-    assert policy.decide(cfg, {}, stats, {**car, "confidence": "dusuk"})[0] == "ask"
-    assert policy.decide(cfg, {}, stats, {**car, "importance": 6})[0] == "ask"
-    assert policy.decide(cfg, {"mode_override": "manuel"}, stats, car)[0] == "ask"
-    policy.record_group_removal(stats, "oto/ai")
-    assert policy.decide(cfg, {}, stats, {**car})[0] == "auto"                                 # bir kaldırma: sürüyor
-    policy.record_group_removal(stats, "oto/ai")
-    assert policy.decide(cfg, {}, stats, {**car})[0] == "ask"                                  # iki kaldırma: onaya döner
-
-
-def test_three_sources_any_category_but_not_some_brands():
-    cfg = Config(raw={"autonomy": {**CFG.raw["autonomy"], "auto_min_importance": 7,
-                                   "trusted_groups": [{"name": "oto/ai", "categories": ["otomotiv", "super-zeka"],
-                                                       "min_sources": 2},
-                                                      {"name": "3 kaynak", "min_sources": 3}],
-                                   "never_auto": ["Vivo", "Oppo", "iQOO"], "auto_broad_importance": 8}})
-    stats = {"sources": {}, "decisions": [{"ok": False, "manual": True}] * 30}
-    three = [{"name": n, "url": n} for n in ("Webtekno", "LOG", "The Verge")]
-    phone = {"id": "p", "flags": [], "confidence": "yuksek", "importance": 8, "category": "teknoloji", "sources": three,
-             "title": "Samsung Galaxy S27 tanıtıldı", "tags": ["Samsung"]}
-    assert policy.decide(cfg, {}, stats, phone) == ("auto", "Güvenilir grup: 3 kaynak")
-    assert policy.decide(cfg, {}, stats, {**phone, "sources": three[:2]})[0] == "ask"           # teknolojide 2 kaynak yetmez
-    assert policy.decide(cfg, {}, stats, {**phone, "category": "gaming"})[0] == "auto"
-    vivo = {**phone, "title": "Vivo'nun yeni telefonu V80 Lite Türkiye'de", "tags": ["akıllı telefon"]}
-    assert policy.decide(cfg, {}, stats, vivo)[0] == "ask"                                     # bu marka onaya gelir
-    assert policy.decide(cfg, {}, stats, {**phone, "tags": ["iQOO"]})[0] == "ask"
-    assert policy.decide(cfg, {}, stats, {**phone, "title": "Vivos adlı yeni uygulama çıktı"})[0] == "auto"
-    assert policy.decide(cfg, {}, stats, {**vivo, "category": "otomotiv"})[0] == "ask"
-    # küçük kitle (puan 7) + büyük marka değil → sor; büyük markaysa yayınla
-    assert policy.decide(cfg, {}, stats, {**phone, "importance": 7, "title": "Nothing CMF hoparlör tanıttı"})[0] == "ask"
-    assert policy.decide(cfg, {}, stats, {**phone, "importance": 7, "big_brand": True})[0] == "auto"
-    assert policy.decide(cfg, {}, stats, {**phone, "importance": 7, "big_brand": True, "title": "Oppo Find X10"})[0] == "ask"
+def test_modes_and_removal_brake():
+    stats = {"sources": {}, "decisions": []}
+    assert policy.decide(CFG, {"mode_override": "manuel"}, stats, dict(GOOD))[0] == "ask"
+    assert policy.current_mode(CFG, {"mode_override": "ogrenen"}) == "kural"            # eski mod adı
+    one = {**GOOD, "sources": THREE[:1], "importance": 7, "title": "Küçük bir uygulama", "tags": []}
+    assert policy.decide(CFG, {"mode_override": "tam"}, stats, one)[0] == "auto"
+    assert policy.decide(CFG, {"mode_override": "tam"}, stats, {**one, "flags": ["iddia"]})[0] == "ask"
+    # 2 otomatik haber kaldırılınca fren
+    assert policy.record_removal(CFG, stats) is False
+    assert policy.decide(CFG, {}, stats, dict(GOOD))[0] == "auto"
+    assert policy.record_removal(CFG, stats) is True and policy.auto_paused_until(CFG, stats)
+    x = dict(GOOD)
+    assert policy.decide(CFG, {}, stats, x)[0] == "ask" and x["policy_tier"] == "paused"
+    policy.resume(stats)
+    assert policy.decide(CFG, {}, stats, dict(GOOD))[0] == "auto"
+    # eski kaldırmalar (3 günden eski) freni tetiklemez
+    stats["auto_removals"] = ["2020-01-01T00:00:00Z", "2020-01-02T00:00:00Z"]
+    assert policy.auto_paused_until(CFG, stats) is None
 
 
--- a/tests/test_home.py
+++ b/tests/test_home.py
@@ -274,4 +274,44 @@
 
 
+def test_pending_draft_publishes_itself_when_third_source_arrives():
+    with _App() as (cfg, a):
+        from haberbot.telegram import MockTelegram
+        a.tg = a.tg or MockTelegram(cfg.root / "tg")
+        src = lambda n: {"name": n, "url": f"https://{n.lower()}.com/x", "title": "t", "kind": "media"}  # noqa: E731
+        d = {**_post(3, 0), "status": "pending", "created_at": iso(now_utc()), "telegram": {"message_id": 31},
+             "importance": 8, "big_brand": True, "confidence": "yuksek", "flags": [],
+             "sources": [src("Webtekno"), src("LOG")], "source_keys": ["Webtekno", "LOG"]}
+        d.pop("published_at")
+        d.pop("slug")
+        small = {**d, "id": "p04", "importance": 7, "big_brand": False, "telegram": {"message_id": 41},
+                 "sources": [src("Webtekno"), src("LOG"), src("Verge")]}
+        a.store.save_draft(d)
+        a.store.save_draft(small)
+        assert a.recheck_pending() == 0                                   # 2 kaynak: bekler (mesajda 2/3 yazar)
+        w = a.store.load_draft("p03")
+        assert w["policy_tier"] == "wait" and "2/3" in a._caption(w, "pending")
+        assert a.store.load_draft("p04")["policy_tier"] == "ask"         # küçük kitle + büyük marka değil: hep sorar
+        it = {"credit": "The Verge", "url": "https://verge.com/x", "title": "t", "kind": "media", "source": "The Verge"}
+        assert a._merge_sources("p03", [it])                              # 3. kaynak geldi
+        assert a.recheck_pending() == 1
+        p = a.store.load_post("p03")
+        assert p and p["publish_mode"] == "auto" and p["auto_late"] and not a.store.load_draft("p03")
+        out = (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8")
+        assert "OTOMATİK YAYINLANDI" in out and "sonradan gelen kaynaklarla" in out and '"message_id": 31' in out
+        assert a.store.load_draft("p04")["status"] == "pending"
+        # /mod manuel: hiçbir şey otomatik yayınlanmaz; iki otomatik haber kaldırılınca fren + bildirim
+        a._on_command("mod", "manuel")
+        assert a.state["mode_override"] == "manuel"
+        a._on_command("mod", "ogrenen")
+        assert a.state["mode_override"] == "kural"
+        a.store.save_post({**_post(5, 1), "publish_mode": "auto"})
+        a._on_button("d", "p03")
+        a._on_button("d", "p05")
+        out = (a.tg.dir / "outbox.jsonl").read_text(encoding="utf-8")
+        assert "Otomatik yayın durdu" in out and a.stats.get("auto_removals")
+        a._on_command("mod", "kural")
+        assert not a.stats.get("auto_removals")
+
+
 if __name__ == "__main__":
     for name, fn in list(globals().items()):
@@@SM@@@ FILE haberbot/policy.py
"""Yayın kararı: hangi haber doğrudan yayınlansın, hangisi sana sorulsun?

Önce eleme (değişmedi): kaynaklar → ayıklama → yayın yönetmeni. Buraya yalnızca yönetmenin "yayınlanmalı" dediği haberler gelir.
Sonra tek bir kural (mod = kural):

  🔴 HER ZAMAN SORULUR  uyarı işareti (iddia, söylenti…) · otomatik yayınlanmayan marka (Vivo, Oppo…) · güven 'düşük'
  🟡 SORULUR            küçük kitleye hitap ediyor (yönetmen puanı 8'in altında) VE büyük bir marka değil
  ⏳ SORULUR + BEKLER   geniş kitle ya da büyük marka ama henüz 3 farklı kaynak yok: sana sorulur; sen karar vermeden
                        3. kaynak gelirse kendiliğinden yayınlanır (Telegram mesajı "otomatik yayınlandı" olur)
  🟢 OTOMATİK           geniş kitle ya da büyük marka + en az 3 farklı kaynak

Güvenlik: otomatik yayınlanan haberlerden son 3 günde 2'sini kaldırırsan otomatik yayın kendiliğinden durur (her şey sorulur);
/mod kural yazınca hemen yeniden açılır. /mod manuel → her şey sorulur, /mod tam → yalnızca 🔴 olanlar sorulur.
"""
from __future__ import annotations

import re
from datetime import timedelta

from .config import Config
from .util import hours_since, iso, now_utc, parse_iso

MODES = {"manuel": "Manuel (her haber sorulur)", "kural": "Kurallı (3+ kaynak otomatik)", "tam": "Tam otonom"}
ALIASES = {"ogrenen": "kural", "öğrenen": "kural", "otomatik": "kural", "oto": "kural"}
TIER_ICON = {"auto": "🟢", "wait": "⏳", "ask": "🟡", "hard": "🔴", "paused": "⏸"}


def _a(cfg: Config, key: str, default):
    v = cfg.get("autonomy", key, None)
    return default if v is None else v


def normalize_mode(m: str | None) -> str | None:
    m = (m or "").strip().lower()
    m = ALIASES.get(m, m)
    return m if m in MODES else None


def current_mode(cfg: Config, state: dict) -> str:
    return normalize_mode(state.get("mode_override")) or normalize_mode(_a(cfg, "mode", "kural")) or "kural"


def source_count(draft: dict) -> int:
    """Farklı yayın kuruluşu sayısı (aynı siteden iki haber bir sayılır)."""
    return len({s.get("name") for s in draft.get("sources") or [] if s.get("name")})


def min_sources(cfg: Config) -> int:
    return max(1, int(_a(cfg, "min_sources", 3) or 3))


def never_auto_brand(cfg: Config, draft: dict) -> str | None:
    """Otomatik yayınlanmayan markalar (ör. Vivo, Oppo): bu haberler her zaman onaya gelir."""
    names = [str(n).strip() for n in _a(cfg, "never_auto", []) or [] if str(n).strip()]
    if not names:
        return None
    text = " ".join([draft.get("title") or "", draft.get("summary") or "",
                     *[str(x) for x in (draft.get("entities") or []) + (draft.get("tags") or [])]])
    for n in names:
        if re.search(rf"(?<![\w]){re.escape(n)}(?![\w])", text, re.I):
            return n
    return None


def is_broad(cfg: Config, draft: dict) -> bool:
    """Geniş kitleye hitap ediyor mu? (yönetmen puanı yüksek ya da büyük bir marka)"""
    return bool(draft.get("big_brand")) or int(draft.get("importance") or 0) >= int(_a(cfg, "broad_importance", 8))


# ── otomatik yayın freni (kaldırılan otomatik haberler) ──────────────
def _recent_removals(cfg: Config, stats: dict) -> list[str]:
    h = float(_a(cfg, "pause_hours", 72) or 72)
    return [t for t in stats.get("auto_removals") or [] if hours_since(t) <= h]


def auto_paused_until(cfg: Config, stats: dict) -> str | None:
    """Otomatik yayın duraklatıldıysa bitiş zamanı (ISO), değilse None."""
    lim = int(_a(cfg, "pause_removals", 2) or 0)
    recent = sorted(_recent_removals(cfg, stats))
    if not lim or len(recent) < lim:
        return None
    end = parse_iso(recent[-lim]) + timedelta(hours=float(_a(cfg, "pause_hours", 72) or 72))
    return iso(end)


def record_removal(cfg: Config, stats: dict) -> bool:
    """Otomatik yayınlanan bir haber kaldırıldı. Bu kaldırma freni devreye soktuysa True döner."""
    before = auto_paused_until(cfg, stats)
    lst = stats.setdefault("auto_removals", [])
    lst.append(iso(now_utc()))
    del lst[:-20]
    return not before and bool(auto_paused_until(cfg, stats))


def resume(stats: dict) -> None:
    """/mod kural: freni sıfırla."""
    stats["auto_removals"] = []


# ── karar ─────────────────────────────────────────────────────────────
def decide(cfg: Config, state: dict, stats: dict, draft: dict) -> tuple[str, str]:
    """('auto' | 'ask', gerekçe). Taslağa policy_tier (auto/wait/ask/hard/paused) ve otomatikse auto_reason yazar."""
    def out(tier: str, reason: str) -> tuple[str, str]:
        draft["policy_tier"] = tier
        if tier == "auto":
            draft["auto_reason"] = reason
        return ("auto" if tier == "auto" else "ask"), reason

    mode = current_mode(cfg, state)
    if mode == "manuel":
        return out("hard", "Manuel mod: her haber sana soruluyor")
    if draft.get("flags"):
        return out("hard", "Uyarı işareti var")
    brand = never_auto_brand(cfg, draft)
    if brand:
        return out("hard", f"{brand}: otomatik yayınlanmayan marka")
    if draft.get("confidence") == "dusuk":
        return out("hard", "Güven seviyesi düşük")
    if int(draft.get("importance") or 0) < int(_a(cfg, "auto_min_importance", 7)):
        return out("hard", "Önem puanı düşük")
    if mode == "tam":
        return out("auto", "Tam otonom mod")
    if not is_broad(cfg, draft):
        return out("ask", "Küçük kitleye hitap ediyor ve büyük bir marka değil")
    n, need = source_count(draft), min_sources(cfg)
    if n < need:
        return out("wait", f"Şimdilik {n}/{need} kaynak: {need}. kaynak gelirse kendiliğinden yayınlanacak")
    if auto_paused_until(cfg, stats):
        return out("paused", "Otomatik yayın durdu (son günlerde otomatik haberleri kaldırdın); /mod kural ile açılır")
    why = "büyük marka" if draft.get("big_brand") else "geniş kitle"
    return out("auto", f"{n} farklı kaynak + {why}")


# ── istatistik (bilgi amaçlı; karara etki etmez) ──────────────────────
def source_rate(stats: dict, name: str) -> tuple[int, float]:
    s = stats.get("sources", {}).get(name, {})
    a, r = s.get("approved", 0), s.get("rejected", 0)
    n = a + r
    return n, (a / n if n else 0.0)


def global_rate(cfg: Config, stats: dict, window: int = 30) -> tuple[int, float]:
    dec = [d for d in stats.get("decisions", []) if d.get("manual", True)][-window:]
    if not dec:
        return 0, 0.0
    return len(dec), sum(1 for d in dec if d.get("ok")) / len(dec)


def record(stats: dict, draft: dict, ok: bool, manual: bool = True, weight: int = 1) -> None:
    for s in draft.get("source_keys", []):
        e = stats.setdefault("sources", {}).setdefault(s, {"approved": 0, "rejected": 0})
        e["approved" if ok else "rejected"] += weight
    stats.setdefault("decisions", []).append(
        {"t": iso(now_utc()), "id": draft.get("id"), "ok": ok, "manual": manual})
@@@SM@@@ SHA
f56944b48fe7e1e2033f23149011fa60e9f62324a30ecb397187edeb76e9b386 KURULUM.md
6024df8ae7d9b5e294846b81c24fed36e35f1029ee5c9cb983b5008db62e3000 README.md
404c6d7b0686f8b306db4741afa05f3b1b6fb31855c4e30eff8d1185bffef7c4 config.yaml
06ec4235e80606e43e390a6054fdc227aa2c8bd4841bed89af1c82b2a406e5c2 haberbot/app.py
099efc0ec79269bc8b3e0da3de59cb763fbd59f4b280cc7ceb38a44c8a465695 haberbot/policy.py
5d3a33015fc520b8fb1df9de45c747ff2134956d6927b81de85235d2e674c20f tests/test_core.py
fd2246d9613c47ae06beff15247d7ae4cc90ca77152fac56a6f3cef3e9663c85 tests/test_home.py
