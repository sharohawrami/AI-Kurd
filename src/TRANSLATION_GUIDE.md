# Sorani Kurdish translation guide (Kurdistan AI Safety Hub website)

You are translating one or more page files of an academic website from English into **Central Kurdish (Sorani)**, written in the Arabic-based Kurdish alphabet. The site belongs to an AI safety research and education institute in Erbil. Readers are university students, software developers and researchers in the Kurdistan Region.

## What to produce

For each source file `src/pages/NAME.html`, write `src/pages/ku/NAME.html` (create the `ku` folder if needed) with the **same HTML structure**, translated.

## Rules for the HTML (critical; the site breaks if these change)

1. Keep every tag, class, id, `for`, `name`, `href`, `data-*` attribute, `aria-describedby`, `type`, `required`, `inputmode`, `autocomplete` and `tabindex` exactly as in the source.
2. Keep every `{{token}}` exactly as written (for example `{{cohort_start}}`, `{{root}}`, `{{mail:email_apply}}`, `{{program_name}}`, `{{mark_svg}}`, `{{attention_svg}}`). They are filled in by the build. Put them where they belong grammatically in the Kurdish sentence.
3. Keep the front-matter comment at the top. Keep `out:`, `nav:` and `newsletter:` unchanged. Translate `title:` and `description:` (keep `{{tokens}}` in them as-is; keep "· Kurdistan AI Safety Hub" translated as "· ناوەندی کوردستان بۆ سەلامەتیی زیرەکیی دەستکرد" except on the home page, whose title is just that Kurdish name).
4. Form controls: **never change a `value="…"` attribute**; translate only the visible label text. Where an `<option>` has no `value` attribute, add one containing the original English text, then translate the visible text, e.g. `<option value="Erbil">هەولێر</option>`. Keep `<option value="">` and translate its text.
5. Translate `aria-label`, `placeholder` (except URL placeholders like `https://`, `https://github.com/` which stay), `data-ineligible`, and `alt` text.
6. In form files, immediately after the opening `<form …>` tag, add exactly: `<input type="hidden" name="language" value="Kurdish (Sorani)">`
7. Keep external links (`https://…`) unchanged. Keep `target` and `rel`.
8. Keep paper titles, course titles and resource names in **English** inside their links (they are the real titles of English publications). Keep author names in Latin script. Translate everything around them (summaries, "what it shows", "how to read it", metadata such as "Week 4" → "هەفتەی ٤", "video" → "ڤیدیۆ").
9. Do not add or remove content, sections or list items. Do not add English glosses everywhere; at most add an English technical term in parentheses the first time it appears on a page when the Kurdish term may be unfamiliar, e.g. هاوئاهەنگی (alignment).

## Language rules

- Standard Sorani orthography with Kurdish letters: ە ێ ۆ ڕ ڵ ی ک. Never use Arabic ي ك ة in place of ی ک ە.
- Clear, warm, formal-but-friendly register, as a respected university program would write to students. Short sentences. Natural Kurdish word order; avoid word-for-word calques.
- Numbers in running text use Eastern Arabic digits as used in Sorani: ٠ ١ ٢ ٣ ٤ ٥ ٦ ٧ ٨ ٩ (e.g. ١٢ هەفتە، ٨ بۆ ١٠ کاتژمێر). Keep Western digits only inside attributes, URLs, ids, code-like strings and English titles. "97%" → "٩٧٪".
- Use the Kurdish comma "،" and question mark "؟".
- Times: "23:59 Erbil time" → "کاتژمێر ٢٣:٥٩ بە کاتی هەولێر".

## Glossary (use these consistently)

| English | Sorani |
| --- | --- |
| Kurdistan AI Safety Hub | ناوەندی کوردستان بۆ سەلامەتیی زیرەکیی دەستکرد |
| the Hub | ناوەندەکە |
| AI / artificial intelligence | زیرەکیی دەستکرد |
| AI safety | سەلامەتیی زیرەکیی دەستکرد |
| KAISH Introduction Program | (use the token `{{program_name}}`, it is filled in automatically) |
| program | پرۆگرام |
| Cohort 1 | خولی یەکەم |
| cohort | خول |
| apply / application | پێشکەشکردن / داواکاری |
| Apply for Cohort 1 | داواکاری بۆ خولی یەکەم |
| syllabus | پلانی خوێندن |
| reading library | کتێبخانەی خوێندنەوە |
| reading group | گروپی خوێندنەوە |
| session | دانیشتن |
| week / phase | هەفتە / قۆناغ |
| coding drill | ڕاهێنانی کۆدنووسین |
| readings | خوێندنەوەکان |
| discussion | گفتوگۆ |
| capstone project | پرۆژەی کۆتایی |
| milestone | قۆناغی گرنگ / وادە |
| facilitator | ڕێکخەری دانیشتن |
| teaching assistant | یاریدەدەری وانە |
| reading group lead | سەرپەرشتیاری گروپی خوێندنەوە |
| operations and community manager | بەڕێوەبەری کارگێڕی و کۆمەڵگە |
| field building | بنیاتنانی بوار |
| machine learning | فێربوونی ئامێر |
| deep learning | فێربوونی قووڵ |
| neural network | تۆڕی دەماری |
| transformer | ترانسفۆرمەر |
| language model | مۆدێلی زمان |
| training (a model) | ڕاهێنانی مۆدێل |
| alignment | هاوئاهەنگی (alignment) |
| interpretability | ڕاڤەپێکراوی |
| mechanistic interpretability | ڕاڤەپێکراویی میکانیکی |
| evaluation | هەڵسەنگاندن |
| governance | حوکمڕانی |
| reward hacking | فێڵکردن لە پاداشت (reward hacking) |
| circuit (in a model) | سەرکیت |
| attention head | سەری سەرنج (attention head) |
| induction head | سەری ئیندەکشن (induction head) |
| superposition | لەسەریەکدانان (superposition) |
| sparse autoencoder | ئۆتۆئینکۆدەری کەمچڕ (sparse autoencoder) |
| activation patching | پینەکردنی چالاکی (activation patching) |
| residual stream | ڕەوتی پاشماوە (residual stream) |
| prerequisites | پێشمەرجەکان |
| free (no cost) | بەخۆڕایی |
| deadline | دوا وادە |
| Erbil, Sulaimani, Duhok, Halabja, Kirkuk | هەولێر، سلێمانی، دهۆک، هەڵەبجە، کەرکووک |
| Iraq / Kurdistan Region | عێراق / هەرێمی کوردستان |
| diaspora | تاراوگە |
| AI Kurd | AI Kurd (keep in Latin) |
| required | پێویست |
| optional | ئارەزوومەندانە |
| privacy notice | ڕاگەیەندراوی تایبەتمەندی |
| mailing list | لیستی ئیمەیڵ |
| Join us (page) | پەیوەندی بە تیمەکەمانەوە بکە |
| account | هەژمار |
| member / members | ئەندام / ئەندامان |
| sign in / sign out | چوونەژوورەوە / چوونەدەرەوە |
| register / create an account | خۆتۆمارکردن / دروستکردنی هەژمار |
| profile / my profile | پرۆفایل / پرۆفایلەکەم |
| password | وشەی نهێنی |
| interests (on a profile) | بوارە دڵخوازەکان |
| robustness and security | پتەوی و ئاسایش |

When you finish, reply with only the list of files you wrote and any phrases you were unsure about (English → your Kurdish), at most 10.
