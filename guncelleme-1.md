SMARITY-BUNDLE v1 part 1/1
@@@SM@@@ PATCH
--- a/haberbot/prompts.py
+++ b/haberbot/prompts.py
@@ -90,6 +90,11 @@
         patch notes, recalls without wider impact, hiring posts
 5. category: one of {CATEGORY_KEYS}. Guide: {CATEGORY_HELP}.
    Stories about Turkey go to their topical category (a Turkish game studio's funding round → girisimcilik or gaming).
+   Category priority rule: if the main subject is an AI model, AI assistant, AI feature or AI company (ChatGPT, Gemini,
+   Copilot, Claude, Meta AI, OpenAI, Anthropic, an AI video tool…), the category is ALWAYS "super-zeka", even when it is a
+   feature inside a product of Google, Microsoft or Apple. A startup's funding round is "girisimcilik" (even an AI startup).
+   A game or gaming platform is "gaming". Military and defence technology is "inovasyon" only if it is a genuine
+   first-of-its-kind technology; otherwise it is usually off topic for our readers.
 6. topic: a short neutral English label for the event. reason: ≤15 words in Turkish explaining the score.
 Be strict and selective: most items are NOT important. Do not inflate scores. Judge each vertical on its own scale so that games and
 cars are not crowded out by AI, and AI does not crowd out everything else."""
@@ -174,7 +179,7 @@
 - title: the H1. ≤90 characters, informative and specific (who did what), starts with or contains the focus_keyword. Sentence case (only first word and proper nouns capitalized). No trailing period, no clickbait.
 - summary: 1–2 plain sentences, ≤180 characters, the core news in everyday language (shown under the headline and on Instagram).
 - body: Markdown, 180–320 words. Structure: a 2–3 sentence lead paragraph that answers who/what/when and contains the focus_keyword; then 2 sections (3 only if really needed), each starting with a "## " subheading (short, informative, natural search-style phrase such as "## iPhone 18 Pro neler sunuyor?", "## Fiyat ve çıkış tarihi" or "## Girişim ne yapıyor?"), each followed by 1–2 short paragraphs. Use a bullet list only for 3+ concrete items from the sources. Bold at most 2 key terms. The LAST paragraph (not under a new heading) must start with "**Neden önemli?** " followed by 1–2 grounded sentences (no speculation beyond what sources support). Do not include a sources list or links; the site adds them. If the sources are thin, write fewer, shorter sections rather than padding — accuracy beats length.
-- category: one of the allowed keys.
+- category: one of the allowed keys. If the main subject is an AI model, assistant, feature or AI company (ChatGPT, Gemini, Copilot, Claude…), always "super-zeka", even inside a Google/Microsoft/Apple product; a startup's funding round → "girisimcilik"; games and gaming platforms → "gaming".
 - tags: 3–6 tags that people search for: companies, products, models, games, car models, technologies, places (e.g. "Apple", "iPhone 18", "TOGG", "elektrikli otomobil", "GTA 6", "OpenAI"). Use the official spelling consistently. If the story is mainly about Turkey or a Turkish company, include the tag "Türkiye". Never use generic words like "teknoloji", "yapay zeka", "oyun", "otomobil", "girişim", "haber", and never use the names of news outlets (TechCrunch, The Verge, Webrazzi…).
 - focus_keyword: as described above.
 - seo_title: ≤58 characters, the title shown in Google results. Starts with the focus_keyword or puts it near the start; specific and compelling but not clickbait; may differ from title. Sentence case. No site name, no trailing period.
@@@SM@@@ SHA
5e15316f694c456c8f5bc4a6019b6c917d3923c037eb0bf16ed6bf747f5add29 haberbot/prompts.py
