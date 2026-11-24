SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/guides.py
+++ b/haberbot/guides.py
@@ -125,4 +125,7 @@
 - Say for which month/date each price or fee is valid ("Kasım 2026 fiyat listesine göre"). If the newest information
   is older than about two months, say clearly that it is the last announced value.
+- Date every number by the article that actually contains it, also in the summary. Never present an older price as
+  part of a newer list: if the newest list or article did not restate a price, write that the last announced price is
+  from the older month (e.g. "Kasım listesinde model fiyatları yer almadı; son açıklanan fiyatlar Ekim 2026'ya ait").
 - If the articles do not contain something a reader would expect (a model's price, a campaign), do not invent it;
   leave it out or say in one short sentence that it has not been announced.
@@@SM@@@ SHA
1ff7a974917f2e59d29acd2da777bcc6c1b3ba64646c5eb1432beed9dff7def6 haberbot/guides.py
