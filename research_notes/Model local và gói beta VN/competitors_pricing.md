# Manga/comic translation competitors: pricing, limits, features and user sentiment (as of 2026-10-21), globally and in Vietnam

## Q1. Per-tool facts: pricing, free tier, caps, models, BYOK/local, Japanese→Vietnamese support, platforms, users/ratings and recent changes

### Takeaway
The paid market has settled at **about $6/month or $6 for about 2,500 images** at the low end. Examples: Ichigo Tier 1 $5.99/mo; Torii 2,500 credits for $5.99; Scan Translator 2,500 credits for €5.99; Sumi Pro $6.99/mo or $69.99/yr; Comic Translate 2,000 credits for $5.99/mo. "Unlimited" plans always carry a hidden cap (an hourly limit, a fast-quota or fair use). Only a few products document Vietnamese as a target language: IsManga, Sumi, Kites, Immersive Translate (Premium), and Apple-only apps (EasyComix, Mangra, Mangu). The Chrome leaders by users are IsManga (~60k), Transmonkey's Google-Translate-based image translator (~50k, 1.7★), Ichigo (40k) and Scan Translator (~40k). None of them offers a local mode. BYOK and local inference exist only in Torii (BYOK, plus self-hosting through a tunnel), Kites (WebLLM, free), a few tiny extensions, and the desktop open-source tools.

### Cited Findings

#### Method and conventions
- Unless marked otherwise, every price and statistic was seen on **2026-10-21** on a public page. Nothing was installed, bought or logged into. The built-in browser was located in Vietnam: the Google Play footer read "Vietnam (English)", so web prices shown are what a VN visitor sees. Chrome Web Store (CWS) pages were read with WebFetch. The CWS cannot load in the browser pane, and Torii's CWS page loops on redirects, so its CWS figures come from a third-party tracker. Edge Add-ons numbers come from Edge's own product-details endpoint, which the store page uses, called inside the Edge Add-ons page. Reddit could not be reached (blocked in the browser pane, and searches returned no threads); see Q3 Gaps.

#### Summary table (details and sources in the per-tool bullets below)
| Tool | Entry price (seen 2026-10-21) | Free tier | Hidden caps | BYOK / local | Vietnamese target (JA source) | Users / rating |
|---|---|---|---|---|---|---|
| Ichigo (Manga Translator🍓) | $5.99/mo or $59.99/yr web; IAP $8.99 US / 229,000đ VN | 40 extension translations + 20 uploads, total | T1: 300 image uploads/hour; T2: 150 T2 translations/hour; "subject to ToS" | No / No | Not confirmed (VN is a UI language only) | CWS 40,000, 3.9★ (554) |
| Scan Translator | €12.99/mo "Unlimited"; packs €5.99/2,500 | 30 credits once + 3 without account | 20,000 fast/month, then slower; bulk on a low-priority lane | No / No | Not confirmed ("80+ languages", unlisted) | CWS ~40,000, 4.7★ (404) |
| Torii | $5.99/2,500 credits; no subscription | Signup credits (amount unstated; a review says 30) | Per-model credit cost; context +1–2 credits/image | Yes (6 providers) / self-host via LM Studio + tunnel | Not named; users run Vietnamese with custom prompts | CWS 20K, 4.6★ (305) per extscope; Firefox 3.5★ (84) |
| Sumi | $6.99/mo or $69.99/yr (1,500 pages/mo) | 1 page without account; 5 at signup, then 5/day | Page quotas | No / offline on iPhone/iPad only | **Yes** (134 targets incl. Vietnamese) | No CWS figure found |
| IsManga | 229,000đ/mo IAP; credit packs from 199,000đ | 40 translations/week (was 80) | "Unlimited" Premium | No (users ask for it) / No | **Yes** | CWS ~60,000, 3.3★ (387); Play 50K+, 3.2★ |
| Immersive Translate (manga = Premium) | ₫149,000/mo or ₫1,788,000/yr (Pro) | Manga translation not in free tier | Token quotas per tier | n/a for manga / "offline image translation" free | **Yes** (20+ manga languages incl. Vietnamese) | Vendor: 30M+ users |
| Comic Translate | $5.99/mo for 2,000 credits; desktop app open source | 50 one-time credits | Monthly credits, carry-over capped | App: own LLM keys (implied) / No local LLM listed | Not named | ~3.0k GitHub stars |
| Kites | Free (GPL-3.0) | Shared pool 100/day; Google MT "unlimited" | Pool limit | Yes / **WebLLM local + on-device OCR/inpainting** | **Yes** (Vietnamese README, JA→VI demo) | CWS 830, 5.0★ (3) |

#### Ichigo (Manga Translator🍓, ichigo.moe)
- Web pricing, seen 2026-10-21 in USD from a VN-located browser, so no regional price:
  - **Free Trial $0**: "Free models"; 40 extension translations total; 20 image uploads total.
  - **Tier 1 $5.99/month or $59.99/year**: Tier 1 models; unlimited extension translations, asterisked "Subject to terms of service"; Japanese, Chinese and Korean OCR; **300 image uploads/hour**.
  - **Tier 2 $19.99/month or $199.99/year**: everything in Tier 1 plus Tier 2 models; **150 Tier 2 image translations/hour**; English OCR; no watermark.
  - Yearly billing is "Equivalent to 2 months free". [Ichigo subscription page](https://ichigo.moe/subscription)
- **Correction to our COST-PRICING note.** The 300/hour cap applies to *image uploads* on Tier 1, not to extension translations, which are "unlimited". The 150/hour cap applies to *Tier 2-model* translations. [Ichigo subscription page](https://ichigo.moe/subscription)
- App Store, United States: in-app purchases Tier 1 **$8.99** and Tier 2 **$24.99**; 4.6★ from 18 ratings; version 2.6.2 (2.6.1 was dated Oct 7). [App Store US](https://apps.apple.com/us/app/id1641432177)
- App Store, Vietnam: in-app purchases Tier 1 **229,000đ** and Tier 2 **699,000đ**; the rating "was recently reset"; seller Ichigo LLC; privacy label says the developer "does not collect any data"; Vietnamese is among the 38 listing languages. [App Store VN](https://apps.apple.com/vn/app/id1641432177)
- A Gumroad page advertises $8.99/month. This comes from a search snippet; the page was not opened. [Gumroad](https://ichigo.gumroad.com/l/ichigo-reader)
- Chrome Web Store listing:
  - 40,000 users; **3.9★ from 554 ratings**; version 0.0.97; updated **2026-10-08**; "Featured" badge.
  - Described as a translator for Japanese, Korean and Chinese. It works on "every manga site with the Unlocker or Panel Tool" and accepts PDF, ZIP and image uploads, with full context for PDF/ZIP.
  - Tiếng Việt appears **only as a listing UI language**.
  - [CWS listing](https://chromewebstore.google.com/detail/manga-translator%F0%9F%8D%93/lepcfgkehgeiblekejomdmdklmjdmflp)
  - Undated search snippets showed 4.1★ (about 330 and 562 ratings), so the rating has drifted down. [Search-result mirror](https://chrome.google.com/webstore/detail/ichigo-reader%F0%9F%8D%93/lepcfgkehgeiblekejomdmdklmjdmflp?hl=en-US)
- Homepage tagline: "AI powered translations for Japanese, Chinese, and Korean. Every platform supported." No model is named anywhere official. [ichigo.moe](https://ichigo.moe/)
- Third-party claim, unverified, about which models each tier uses: Free = GPT-4o mini; $5.99 = DeepSeek V3 and Gemini Flash; $19.99 = GPT-4o, Gemini Pro, Claude and Grok. [UPDF blog](https://updf.com/chatgpt/japanese-manga-translator/)
- No BYOK and no local mode are advertised. Vietnamese is not confirmed as a translation target on any official Ichigo page. [CWS listing](https://chromewebstore.google.com/detail/manga-translator%F0%9F%8D%93/lepcfgkehgeiblekejomdmdklmjdmflp)
- From earlier notes (2026-10-13), not re-checked today: Ichigo's terms restrict competitive access, scraping and reverse engineering. [Ichigo TOS](https://ichigo.moe/TOS.txt)

#### Scan Translator (scan-translator.com; seller Benoît Lemaire, Paris, a declared EU trader)
- Pricing, seen 2026-10-21 in EUR:
  - **Monthly Unlimited €12.99/month.** It includes 20,000 fast translations per month. After that, translation continues but "may be slower during peak hours". Bulk jobs run on a lower-priority lane.
  - **One-time credit packs that never expire:** 2,500 credits for €5.99; 7,000 for €9.99; 20,000 for €24.99.
  - **30 free credits**, granted once per new account. "1 credit translates 1 image."
  - [Scan Translator homepage](https://scan-translator.com/)
- FAQ details:
  - 3 free translations without an account; fair use applies.
  - Translated images on an account are kept **up to 90 days**; payments go through Stripe.
  - No AI model is named. "80+ target languages" are claimed but not listed.
  - Some sites "block or obfuscate image access"; the suggested fallbacks are Screenshot or uploading the image.
  - [Scan Translator FAQ](https://scan-translator.com/faq)
- Chrome Web Store: ~40,000 users; **4.7★ from 404 ratings**; version 3.2.2; updated **2026-08-27**; Featured. Tiếng Việt appears only among the 12 listing display languages. [CWS listing](https://chromewebstore.google.com/detail/mnngaddpelmhcgkbeajnbjmkdmpkogbo)
  - An older search snippet showed 3.4★ from 101 ratings and "30 requests per week" free. The current listing and site supersede it. [Search snippet source](https://chrome.google.com/webstore/detail/scan-translator/mnngaddpelmhcgkbeajnbjmkdmpkogbo)
- Platforms: Chrome, Brave, Edge, Opera and most Chromium browsers; Firefox; web upload. No mobile app is mentioned. No BYOK or local mode. [Scan Translator homepage](https://scan-translator.com/)

#### Torii (toriitranslate.com)
- Credit packs (USD symbol):
  - **2,500 credits $5.99; 6,000 credits $12.99; 15,000 credits $29.99.** The slider also shows 25K–250K without prices.
  - "No subscription"; credits never expire.
  - An image costs 1 credit for scanning (OCR) plus an AI cost that depends on text length. Fast models (Gemini Flash Lite, DeepSeek) add "a fraction of a credit"; premium models (Claude Opus) cost more.
  - With BYOK the AI charge is skipped.
  - Cached repeat translations are free; the cache auto-deletes after 1 week by default.
  - [Torii pricing](https://toriitranslate.com/pricing)
- Homepage:
  - Models: Claude, Gemini, GPT, DeepSeek, Grok "and more". 140+ languages with auto-detected source. BYOK costs "a flat 1 credit per image".
  - Platforms: Chrome, Edge, Brave, Opera; Firefox on desktop and Android; Safari on Mac, iPad and iPhone; a mobile web app.
  - Marketing claims: "58,000,000+" readers (the metric is unclear), 20,000+ on Discord, "Rated 4.3" on the CWS. Made by one developer with near-weekly updates.
  - [Torii homepage](https://toriitranslate.com/)
- 2026 changelog, newest first ([Torii updates](https://toriitranslate.com/updates)):
  - **2026-10-10 (v2.23.1):** typesetting fitted to each bubble's shape; syllable hyphenation in 40+ languages.
  - **2026-09-13 (v2.22.2):** new models (Gemini 3.8 Flash, Luna, Kimi, OneOCR); BYOK local presets; cached translations show 0 credits; new payment options; full editor in the Mac Safari build.
  - **2026-07-22:** Safari extension for iPhone, iPad and Mac.
  - **2026-05-22:** BYOK for OpenAI, OpenRouter, Google Gemini, Anthropic Claude, DeepSeek and xAI Grok (flat 1 credit/image). **Self-hosted mode with LM Studio plus a tunnel (Cloudflared or Ngrok).**
  - **2026-03-26:** a desktop Visual Novel Translator on the same account and credits.
  - **2026-02-17:** "Context sharing" passes summaries of earlier pages into later translations, at **+1–2 credits per image**.
  - **2026-01-26:** history and caching stored on the device.
  - No glossary or story-memory feature is listed.
- Chrome Web Store figures, from a third-party tracker because the CWS page loops on redirects:
  - 20K users, up 10K in the week to Oct 21; **4.6★ from 305 ratings**; version 2.22.6. [extscope](https://www.extscope.org/extension/gkdekajjngdkocgiealohleibhdjhoed)
  - The tracker's AI summary claims "2,500 free credits", which conflicts with the official pricing page. Treat it as unreliable.
  - The vendor homepage says 4.3★, which also conflicts.
- Firefox: **3.5★ from 84 reviews** (47 five-star, 27 one-star). [AMO reviews](https://addons.mozilla.org/en-US/firefox/addon/torii-image-translator/reviews/)
- Edge Add-ons: 189 installs, no ratings, version 2.20.7, updated 2026-06-30. [Edge listing](https://microsoftedge.microsoft.com/addons/detail/ocfdbdlneckjoennmhilhkkffagmgola)
- Vietnamese is not named on official pages. A Firefox reviewer (2026-09-19, 5★) reports consistent results using **custom prompts for Vietnamese pronouns**. [AMO reviews](https://addons.mozilla.org/en-US/firefox/addon/torii-image-translator/reviews/)

#### Sumi (mangasumi.com)
- Pricing, seen 2026-10-21 in USD via Stripe ([Sumi pricing](https://mangasumi.com/pricing)):
  - **Free:** 1 page without an account; 5 pages at signup, then 5 a day to claim; batch of up to 20 pages.
  - **Pro:** $6.99/month, or $69.99/year ($5.83/month); 1,500 pages/month (about 75 chapters).
  - **Pro+:** $14.99/month, or $149.99/year ($12.50/month); 4,000 pages.
  - **Studio:** $39.99/month, or $399.99/year ($33.33/month); 12,000 pages.
  - Yearly billing shows "Save 17%". Going over the quota falls back to any page balance.
  - One subscription covers web, Chrome, iPhone, iPad, Mac and Android (Google Play open testing).
- **Correction to our earlier notes:** Sumi has monthly plans, not only an annual one. [Sumi pricing](https://mangasumi.com/pricing)
- Homepage ([Sumi homepage](https://mangasumi.com/)):
  - Reads Japanese, Korean and Chinese; **134 target languages including Vietnamese**.
  - Extensions for Chrome, Edge (through the CWS), Firefox and Safari.
  - **Offline translation on iPhone/iPad only**, after downloading a one-time model pack. The page mentions a "one-time offline pack" but shows no price.
  - Claims it "collects no browsing history". No model is named.
- Claims to work on "110+ real manga sites", checked by hand on official publisher platforms such as Shonen Jump+, MANGA Plus, Comic Days and ComicWalker. [Sumi pricing](https://mangasumi.com/pricing)
- Third-party claims, unverified:
  - A one-time **$9.99** unlimited offline purchase on Apple devices; pay-per-page packs from $1.99. [AlternativeTo](https://alternativeto.net/software/sumi--ai-manga-translator/about/)
  - A $0.008/page overage rate. [Stork](https://www.stork.ai/en/sumi-ai-manga-translator)
- The developer's update log reportedly says offline translation in iOS 1.0.7 could crash on low-memory devices, with a fix (1.0.9) submitted. This is a search-result summary only. [Sumi updates](https://mangasumi.userjot.com/updates)
- No Chrome Web Store user or rating figure was found. PeerPush shows a single 5.0 review. [PeerPush](https://peerpush.com/p/sumi)

#### IsManga ("Manga Translator"; Vietnamese CWS title "Dịch Truyện Tranh - IsManga")
- Chrome Web Store ([CWS listing](https://chromewebstore.google.com/detail/oooikipggipaohjibkmoiacmmlilgokn)):
  - **~60,000 users; 3.3★ from 387 ratings**; version 0.2.949; updated 2026-10-14; Featured.
  - Free: "40 premium AI-powered translations per week".
  - Premium: unlimited and faster translation, plus "Screenshot Mode" for more sites.
  - **Vietnamese is listed as a target language**; 55 UI languages.
- The Vietnamese-locale CWS title is "Dịch Truyện Tranh - IsManga", so the listing is localized for Vietnam. This is from the search result title. [CWS (vi)](https://chromewebstore.google.com/detail/manga-translator/oooikipggipaohjibkmoiacmmlilgokn?hl=vi)
- Google Play, VN region: **50K+ downloads; 3.2★ (381 reviews)**; contains ads and in-app purchases; updated 2026-10-15; built-in manga browser. [Google Play](https://play.google.com/store/apps/details?id=com.ismanga.ismanga&hl=en&gl=VN)
- App Store, Vietnam ([App Store VN](https://apps.apple.com/vn/app/id6443648567)):
  - Seller Manga World Inc.; 3.8★ from 12 ratings.
  - In-app purchases: **Premium Monthly 229,000đ; Premium One Day 59,000đ; Premium Annual 2,499,000đ; 2,500 credits 199,000đ; 5,000 credits 399,000đ; 10,000 credits 699,000đ**.

#### Immersive Translate (general translator; "Comic translation" is Premium-only)
- Pricing page as displayed in Vietnam on 2026-10-21 ([Immersive Translate pricing](https://immersivetranslate.com/en/pricing/)):
  - **Pro: ₫149,000/month or ₫1,788,000/year** ("Save 42%").
  - **Max: ₫499,000/month or ₫5,988,000/year.**
  - 3-day free trial; a "Pay with Crypto" option.
  - "Comic translation" and "Image Translation" are listed as **Pro-exclusive**.
  - Pro includes "Advanced translation model 20 million Token/Month": DeepSeek V4.1 Flash, Qwen 3.5 Plus, Gemini 3 Flash, GPT-6 Luna, GLM-4.7 and DeepL Pro.
  - Max adds a top-tier quota of 2M tokens/month (GPT-6.1 Sol, Gemini 3.1 Pro, Kimi K2.6, Claude Sonnet 5.5, GLM-5.2) and raises the advanced quota to 50M.
  - The free tier lists "Offline image translation /Unlimited", subject to fair use.
- Manga page ([Immersive Translate manga](https://immersivetranslate.com/manga)):
  - "Manga Translation is a Premium Feature".
  - Supports 100+ manga platforms: Pixiv, MANGA Plus, Zebrack, Shonen Jump+, Comic Days, ComicWalker, MangaDex and others.
  - **20+ languages including Tiếng Việt**.
  - Extensions for Chrome, Edge, Firefox and Safari.
  - Claims 30M+ downloads and 4.9★.

#### Comic Translate (open-source desktop app ogkalu2/comic-translate, plus the comic-translate.com service)
- Repository:
  - **Apache-2.0**; ~3.0k stars; desktop app for Windows and macOS; a Chromium extension.
  - LLM translation with "GPT-4.1, Claude-4.5, Gemini-2.5".
  - OCR: manga-ocr (JA), Pororo (KO), PPOCRv5; optional Gemini 2.0 Flash or Azure.
  - Inpainting: a manga-finetuned LaMa and AOT-GAN. Detection: RT-DETR-v2.
  - Vietnamese is not named. [GitHub](https://github.com/ogkalu2/comic-translate), [README](https://raw.githubusercontent.com/ogkalu2/comic-translate/main/README.md)
- **New paid service** at comic-translate.com:
  - **Free: 50 one-time credits.**
  - **Individual $5.99/month, 2,000 credits.**
  - **$11.99/month, 4,500 credits.**
  - **Business $24.99/month, 10,000 credits.**
  - 1 credit per image by default; unused credits carry over up to the plan amount; "Translate with GPT, Gemini, and more".
  - BYOK is not mentioned.
  - [Comic Translate pricing](https://www.comic-translate.com/pricing/)

#### Kites (Unheat/Kites, GPL-3.0)
- Chrome Web Store ([CWS listing](https://chromewebstore.google.com/detail/pcaokchkdgnmfgjkljfpghlfohbdjcmj)):
  - **830 users; 5.0★ (3 ratings)**; version 1.2.1; updated **2026-10-19**; 33.19 MiB.
  - Free: "No subscriptions", "No token caps".
  - Engines: a community shared pool (**100 translations/day** with Google sign-in); on-device **WebLLM** (Qwen 3.5, Gemma 3, Llama 3.2); BYOK for OpenAI, Claude, Gemini and DeepSeek.
  - **50+ target languages including Vietnamese.**
  - Other features: glossary, ZIP export, Studio editor, webtoon strips over 14,000 px.
- Repository: 36 stars; 533 commits; PaddleOCR on WebGPU; LaMa-Manga and AOT-GAN inpainting; a **Vietnamese README and a Japanese→Vietnamese demo**; Chrome MV3 only. [GitHub](https://github.com/Unheat/Kites)
- Website: engines fail over automatically; Google Translate is listed as "unlimited"; images "never reach Kites servers"; the IndexedDB cache is pruned after 7 days. [Kites website](https://kites-translator.pages.dev/)
- From earlier notes, not re-checked today: the 2026-09-11 privacy policy says the default Google Translate engine sends text to Google. [PRIVACY.md](https://github.com/Unheat/Kites/blob/main/PRIVACY.md)

#### manga-image-translator and Cotrans
- **GPL-3.0**; 10.5k stars. The repository describes the Cotrans demo (cotrans.touhou.ai) as "**(no longer working)**".
- Online translators: DeepL, ChatGPT, DeepSeek, Groq, Gemini, Papago, Sakura and Custom OpenAI. Google is "Temporarily disabled".
- Offline translators: NLLB, Sugoi, JParaCrawl, M2M100, mBART50 and Qwen2. Custom OpenAI defaults to **Ollama at localhost:11434**.
- The language codes include VIN, but support depends on the translator chosen. `--context-size` applies only to the OpenAI translator.
- The README was last updated 2025-05-10.
- [GitHub](https://github.com/zyddnys/manga-image-translator)

#### BallonsTranslator
- **GPL-3.0**; 5.2k stars; runs on Windows, macOS and Linux.
- Translators: Google, DeepL/DeepLX, **Sugoi (Japanese→English, offline)**, Caiyun, Papago, Sakura-13B (local), m2m100 (local), and an OpenAI-compatible LLM mode with context, glossary, vision and summary features.
- OCR: mit, manga_ocr, PaddleOCRVLManga. Inpainting: AOT, PatchMatch, LaMa.
- It has a Vietnamese README, but Vietnamese is not listed as a translation target.
- [GitHub](https://github.com/dmMaze/BallonsTranslator)
- A commercial "BallonsTranslator Pro" aimed at teams appears on Product Hunt; its relationship to dmMaze was not verified. [Product Hunt](https://www.producthunt.com/products/ballonstranslator-pro)

#### ImageTrans (basiccat.org)
- **One-time licences: Personal $10.99, Commercial $299**, with "Free upgrades for half a year"; discounts for scanlation groups and students.
- Translation with ChatGPT, Gemini and DeepSeek plus vision models. Text removal with LaMa or Gemini "Nano Banana".
- Runs on Windows, macOS and Linux, with a server mode for mobile.
- Vietnamese is not mentioned.
- [ImageTrans](https://www.basiccat.org/imagetrans/)

#### LunaTranslator, for comparison
- GPL-3.0; ~13.8k stars.
- A visual-novel translator that hooks game text. It has OCR and "almost all translation engines", including LLM and offline ones.
- It links to Vietnamese documentation. It is not a manga lettering tool.
- [GitHub](https://github.com/HIllya51/LunaTranslator)

#### Sugoi Translator / Sugoi Toolkit
- Sugoi is an offline **Japanese→English** model. [BallonsTranslator README](https://github.com/dmMaze/BallonsTranslator)
- The offline/batch workflow needs Windows, and an NVIDIA GPU helps (per a third-party tool). [TenshiTranslator on PyPI](https://pypi.org/project/TenshiTranslator)

#### Platform tools (free, generic)
- **Apple:** Live Text, the Translate app and System-Wide Translation all list both Japanese and Vietnamese. Visual Look Up lists Japanese but not Vietnamese. [Apple feature availability](https://www.apple.com/ios/feature-availability/)
- **Papago:** the NAVER Cloud Papago Image Translation API lists **Japanese and Vietnamese as both source and target**. [NAVER Cloud docs](https://guide.ncloud-docs.com/docs/en/papago-image-translation-spec)
- **Google Translate camera:** the help page gives no per-language table. Offline camera translation needs the languages downloaded first. [Google Translate Help](https://support.google.com/translate/answer/6142483?hl=en)
- **Gemini, through a Vietnamese how-to:**
  - Phong Vũ (2025-11-27) shows translating comic pages into Vietnamese with Nano Banana Pro ("Thinking with 3 Pro"). It warns that forms of address, pronouns and punctuation may be wrong and that short exclamations can be dropped. [Phong Vũ](https://phongvu.vn/cong-nghe/dich-truyen-bang-nano-banana-pro/)
  - In late November 2025 Google cut free Nano Banana Pro generations to 2 per day and said limits change often. [ETV Bharat](https://www.etvbharat.com/en/technology/google-reduces-daily-prompt-limits-on-gemini-3-pro-and-nano-banana-pro-free-users-enn25112805726); [Android Authority](https://www.androidauthority.com/gemini-3-pro-high-demand-free-tier-limit-3620382)

#### Other "manga translator" extensions found on Chrome and Edge
- **Transmonkey "Image Translator - Comics Translator | Manga Translator"**
  - Chrome Web Store: ~50,000 users; **1.7★ from 276 ratings**; version 6.8.5; updated 2026-10-12. Uses Google Translate after OCR; in-app purchases; Vietnamese only as a UI language. [CWS listing](https://chromewebstore.google.com/detail/image-translator-comics-t/pbhpcbdjngblklnibanbkgkogjmbjeoe?hl=en)
  - Edge Add-ons: **5,330 installs, 2.4★ (8)**, version 6.8.5; the publisher website is transmonkey.ai. This is the largest manga-specific listing on Edge. [Edge listing](https://microsoftedge.microsoft.com/addons/detail/opimdenmabjbacmheeebgjckapkmedkp)
- **Edge Add-ons search for "manga translator" returns 45 results**, many of them general translators. [Edge search](https://microsoftedge.microsoft.com/addons/search/manga%20translator?hl=en-US) Manga-specific listings by installs:
  - translatemanga.online "Manga Translator - Comics Translator | Manga Tracker": 3,597 installs, 2.0★ (9). [Edge listing](https://microsoftedge.microsoft.com/addons/detail/kapdjmncebofjiccfhckjallpamdhkab)
  - KanFan: 1,590 installs, 5.0★ (7). [Edge listing](https://microsoftedge.microsoft.com/addons/detail/hjdegcejfgbcikdcgafigaoieicofada)
  - MangaLens: 369 installs. [Edge listing](https://microsoftedge.microsoft.com/addons/detail/hnidjffllcjahflggifihkkbicgbhaed)
  - Torii: 189 installs.
  - Manhwa Translator: 173 installs. [Edge listing](https://microsoftedge.microsoft.com/addons/detail/bapobphnkhencllelocmdcecaafofcpc)
  - MangaOT: 52 installs. [Edge listing](https://microsoftedge.microsoft.com/addons/detail/jldmolcgjcpgfkdhiedghnniohmffpgj)
  - An open-source "Manga Translator V3.1.11": 32 installs. [Edge listing](https://microsoftedge.microsoft.com/addons/detail/epjngccjgancjjbpaegmakaemicmjmgh)
  - Ichigo, Scan Translator and Sumi did not appear in the Edge results. Scan and Sumi tell Edge users to install from the Chrome Web Store. [Scan Translator homepage](https://scan-translator.com/), [Sumi homepage](https://mangasumi.com/)
- **KitsuTL:** 162 users, no ratings, account required, version 1.0.1 (2026-03-05). [CWS listing](https://chromewebstore.google.com/detail/kekkedhgbgpbndcdcopjgkkeldnfjpie?hl=en)
- **MangaTrans** ("Mangatrans"): 18 users; BYOK for Claude or OpenAI, **or local Ollama**; outputs English only; version 2.0.0 (2026-06-03). [CWS listing](https://chromewebstore.google.com/detail/hoagaedakmopbokhnbjhoakgpdijahpg?hl=en)
- **MangaTranslate (Firefox):** 25 free credits/month; Pro $5.99/month or $50/year; 9 target languages; images go to its server. This is a search-result summary only. [AMO](https://addons.mozilla.org/addon/mangatranslate/)
- **MochiTranslate (Firefox):** BYOK with a Gemini key; renders the translation back into the bubble. Search-result summary only. [AMO](https://addons.mozilla.org/firefox/addon/mochitranslate/)
- **TranslateManga (translatemanga.net, Vietnamese UI):** 50+ languages; batch of up to 10 images (15 MB each); 5–10 s per request; OCR plus an MT chain plus its own LLM; prices not visible. [TranslateManga (vi)](https://translatemanga.net/vi/translator)
- Smaller CWS listings, from older undated search snippets: "Manga Translator Extension" 409 users, 2.0★ (4); "Manga Page Translator" 218 users, 2.6★ (5). [CWS](https://chromewebstore.google.com/detail/daeemoaijgmgggemjahfhicbccangkom); [CWS](https://chromewebstore.google.com/detail/hckhkkbeppdjomapamojaecjdenjbgcl)

### Inferences
- **Cost per image at list price**, my arithmetic from the cited prices:
  - Scan Unlimited: about €0.00065/fast image (€12.99 / 20,000). Scan packs: €0.0012–0.0024.
  - Torii: $0.0024/credit, so at least about $0.0024/image with fast models and up to about 3× that with context sharing (+1–2 credits).
  - Comic Translate: $0.0025–0.003/image.
  - Sumi: $0.0033–0.0047/page.
  - Ichigo Tier 1 is flat-rate "unlimited" for in-page translations, with a 300/hour upload cap.
  - A Vietnamese beta priced at or below about 150,000đ/month competes with EasyComix (149,000đ) and Immersive Translate Pro (₫149,000). Both anchor that price point for VN users.
- **App Store prices for VN are not discounted.** Ichigo is $8.99 in the US and 229,000đ in VN, which at roughly 26,000 VND/USD (an assumed rate, not checked for October 2026) is about the same. Web prices from Ichigo, Sumi, Scan and Torii are shown in USD or EUR even to a VN visitor. Immersive Translate is the only web vendor seen showing VND.
- "Unlimited" claims always hide caps: Ichigo has hourly caps and ToS fair use; Scan has a 20,000 fast quota; IsManga's "unlimited" sits behind a weekly free cap. A transparent per-chapter cost display would be a differentiator.
- BYOK and local are niche among the big four. Only Torii offers BYOK, and its "local" route still runs through Torii's cloud OCR (1 credit) plus a public tunnel. That is my reading of "LM Studio plus a tunnel"; it is not an offline mode.
- **Sumi is the closest feature competitor in breadth**: Vietnamese target, glossary, offline on iOS, official-site coverage, all platforms. Kites is the closest in architecture (local WebGPU OCR, inpainting and WebLLM, Vietnamese).

### Gaps
- Ichigo's model names per tier and its translation target list are not on any official page; Vietnamese as a target is unverified.
- Scan Translator's and Torii's exact target-language lists, including Vietnamese, are not published on the pages fetched.
- Exact amount of Torii's free signup credits is unconfirmed: a review says 30; a tracker says 2,500, likely wrong.
- Torii's and Sumi's Chrome Web Store figures could not be read directly; Torii's come from extscope.
- Sumi's offline pack price is not on its official page ($9.99 is third-party). Its CWS users and ratings are unknown.
- I could not get a CWS-wide ranking by user count. The CWS search page cannot be loaded in the browser pane. The Chrome list above is built from listings I found, so larger generic "image translator" extensions may exist.
- Google Lens / Translate camera: no official per-language table confirming Japanese→Vietnamese camera or instant translation.
- ChatGPT free-tier image limits: not researched for lack of an official source.
- Gemini app limits: only third-party and news sources, which conflict.
- Sugoi Toolkit: official site and current terms not found.
- ImageTrans Vietnamese OCR/target support: not stated.

## Q2. Vietnamese-specific tools and services; how Vietnamese teams use AI

### Takeaway
No browser extension built specifically for Vietnamese manga translation was found. VN demand is served by global tools that localize for Vietnam: IsManga (Vietnamese CWS title, VND in-app purchases), Immersive Translate (VND web pricing), Scan Translator (many Vietnamese-named reviewers) and Kites (Vietnamese README). The strongest Vietnamese-market app is **EasyComix** (iOS/macOS), from an individual seller with a Vietnamese name. It has **4.8★ from 452 VN ratings**, VND plans (149,000đ/month, 999,000đ/year) and a Pro mode that takes a user-written story summary for names and relationships. Vietnamese text communities (Hako / Cổng Light Novel) openly accept AI translation with Gemini. Their own guides name **pronouns (xưng hô) as the main failure** and fix it manually with glossaries and the previous 2–5 chapters as context.

### Cited Findings
- **EasyComix: Manga Translator** (Vietnamese title "EasyComix: Dịch Manga, Webtoon") ([App Store VN](https://apps.apple.com/vn/app/id6759873531); title from [App Store, vi listing](https://apps.apple.com/us/app/easycomix-d%E1%BB%8Bch-manga-webtoon/id6759873531?l=vi&platform=ipad)):
  - Developer: an individual seller (Nguyen Danh Hao); 4.8★ from 452 ratings on the VN store; version 1.0.40, updated about 2026-10-20.
  - iOS 18+, macOS 15 (M1+) and visionOS.
  - In-app purchases: **Weekly 79,000đ; Monthly 149,000đ; Annual 999,000đ; Live Translation Pack 59,000đ; Novel Translation Pack 29,000đ**.
  - Free tier includes "unlimited offline translation" with on-device OCR. Pro uses an LLM hosted by the developer that receives "a few lines of text". Users can supply a story summary for names, relationships and slang.
  - 26 languages, including Japanese and Vietnamese. Privacy label: "does not collect any data".
- **Mangra** ([App Store VN](https://apps.apple.com/vn/app/id6502868308)):
  - In-app purchases: Weekly 119,000đ; Monthly 249,000đ; Yearly 1,499,000đ. 4.2★ (18) on the VN store; version 4.9.
  - Free: unlimited local translation through Apple's on-device engine, plus on-device Japanese OCR, working offline.
  - Pro: cloud AI with five premium models; claims it sends text only, never images.
  - 50+ languages including Vietnamese.
- **Mangu** ([App Store VN](https://apps.apple.com/vn/app/id6747577465)): Turkish developer; in-app purchases Weekly 129,000đ and Yearly 799,000đ (plus others up to 899,000đ); 4.7★ (7); Vietnamese listed.
- **IsManga** markets in Vietnamese ("Dịch Truyện Tranh - IsManga") and sells VND in-app purchases. App Store: monthly 229,000đ; one-day 59,000đ; annual 2,499,000đ; credits 199,000–699,000đ. [App Store VN](https://apps.apple.com/vn/app/id6443648567); [CWS (vi)](https://chromewebstore.google.com/detail/manga-translator/oooikipggipaohjibkmoiacmmlilgokn?hl=vi)
- **Immersive Translate** shows VND web pricing to VN visitors (Pro ₫149,000/month), offers a crypto payment option, and lists Vietnamese for manga translation. [Pricing](https://immersivetranslate.com/en/pricing/); [Manga](https://immersivetranslate.com/manga)
- **Kites** ships a Vietnamese README and a Japanese→Vietnamese demo. [GitHub](https://github.com/Unheat/Kites)
- **Scan Translator:** of its 10 most recent CWS reviews (Oct 7–20, 2026), at least 4 reviewers have Vietnamese names, all short and positive. [CWS reviews](https://chromewebstore.google.com/detail/mnngaddpelmhcgkbeajnbjmkdmpkogbo/reviews)
- **Vietnamese-language web tools:**
  - MiniWebtool "Dịch truyện tranh bằng AI": places the translation into bubbles, uses earlier-page dialogue for name consistency, free with ads and daily limits. Search-result summary only. [MiniWebtool (vi)](https://miniwebtool.com/vi/dịch-truyện-tranh-bằng-ai/)
  - TranslateManga has a Vietnamese UI and 50+ languages; prices are not visible. [TranslateManga (vi)](https://translatemanga.net/vi/translator)
  - insMind (Vietnamese page) uses image models (GPT Image 2, Nano Banana 2). Search-result summary only. [insMind](https://www.insmind.com/vi-vn/design/manga-translator)
- **Vietnamese tech retailers teach DIY Gemini translation.** Phong Vũ (2025-11-27) gives a step-by-step guide with Nano Banana Pro and warns about pronouns and address. [Phong Vũ](https://phongvu.vn/cong-nghe/dich-truyen-bang-nano-banana-pro/) CellphoneS Sforum ran a similar guide (search result only). [CellphoneS](https://cellphones.com.vn/sforum/dich-truyen-bang-nano-banana-pro)
- **Hako / Cổng Light Novel (docln.net):**
  - On **2025-05-05** an admin renamed the "Máy dịch" section to "**AI dịch**". The section accepts AI-produced translations (suggesting free models such as Gemini 2.5 Flash, DeepSeek, and Llama via Groq), bans "convert" and other low-level machine translation, and admits it cannot check every upload.
  - Commenters discuss buying Gemini Pro/Ultra or ChatGPT Pro cheaply, and note that Gemini sometimes refuses copyrighted text (AI Studio is used as a workaround).
  - [docln announcement](https://docln.net/thao-luan/3097-thong-bao-ve-ai-dich)
- **Hako guide (2025-10-27):**
  - Build a names and terms glossary first.
  - Feed **2–5 previously translated chapters** so the AI learns "xưng hô, ngữ cảnh, cốt truyện".
  - Commenters prefer Gemini 2.5 Pro and say quality drops in long chats.
  - [docln guide](https://docln.net/thao-luan/3268-huong-dan-dich-truyen-bang-ai)
- **VOZ thread "MC-AI Novel Trans"** (a Vietnamese AI tool for comics and novels). The search snippet says it lists pronoun errors ("ta/ngươi" vs "anh/em" mixed up) and offers a character-relationship setting so the AI picks pronouns. The thread returned 403 to WebFetch and "not found" in the browser on 2026-10-21, so it is **unverified**. [VOZ](https://voz.vn/t/mc-ai-novel-trans-cong-cu-dich-truyen-tranh-tieu-thuyet-ho-tro-ai.1190485/)
- **Academic work:** an ICTU student or thesis project (May 2026) on machine-learning text replacement in comic speech bubbles. Search-result summary only. [ICTU PDF](https://repository.ictu.edu.vn/wp-content/uploads/2026/05/22912.pdf)
- **Public debate:** MyTour reports Vietnamese social-media controversy over AI translation of manga, citing *The Ancient Magus' Bride*. Search-result summary only. [MyTour](https://mytour.vn/vi/blog/bai-viet/cong-dong-mang-xa-hoi-roi-ren-truoc-viec-tri-tue-nhan-tao-dam-nhiem-viec-dich-truyen-tranh.html)

### Inferences
- The Vietnamese market already pays VND subscriptions through App Store billing: EasyComix's 452 ratings at 4.8★ are strong for a niche VN app. On the web, payment is the gap. Only Immersive Translate shows VND, and its alternative is crypto rather than MoMo, ZaloPay, VNPay or VietQR bank transfer.
- Vietnamese readers and translators have adopted LLMs (Gemini in particular) and judge output mostly by **xưng hô consistency**. Their fix is manual: glossaries, prior chapters and relationship settings. A product that makes directed pronoun rules (A→B) and a names glossary automatic and evidence-backed addresses the community's own top complaint.
- No Vietnamese Facebook or Discord paid AI-manga service with public VND prices was found. The DIY route (Gemini or ChatGPT plus manual redraw) is the de facto "free competitor" for Vietnamese readers.

### Gaps
- No public data on Vietnamese scanlation teams (manga or manhwa) using BallonsTranslator, manga-image-translator or Comic Translate. Searches in Vietnamese and English returned only generic tool pages.
- Facebook groups and Discord servers could not be searched (login walls). VOZ and Tinhte content was not reachable; the one VOZ thread found was inaccessible.
- EasyComix: no website, Android version or download count was found.
- Whether any competitor accepts MoMo, ZaloPay, VNPay or VietQR is unknown. It was not seen on any pricing page fetched. Torii mentions "new payment options" (2026-09-13) without naming them. [Torii updates](https://toriitranslate.com/updates)

## Q3. User sentiment: recurring praise and complaints

### Takeaway
Praise centres on **text replaced in place, blending into the page** (Scan, Ichigo), **natural or accurate translations** (Torii, Scan), and **inpainting and typography** (Torii). Complaints centre on **free-tier cuts and paywalls** (IsManga's weekly free allowance halved from 80 to 40; one-star Torii reviews after the free credits end), **sites or images that do not work**, uneven accuracy, a lack of BYOK, and occasional billing or caching bugs. The extension that relies only on Google Translate has the worst ratings (1.7★ on Chrome, 2.4★ on Edge). For Vietnamese, **forms of address and pronouns** are the recurring quality complaint.

### Cited Findings
- **IsManga, Chrome Web Store reviews (10 most recent; overall 3.3★):** several reviewers complain the free limit was **cut from 80 to 40** (Apr–May 2026), with one lowering a rating to 2/5 because of it. Others ask for it to be free or for **BYOK** (2026-09-07), call it a waste of money (2026-07-11), or say it doesn't work (2026-01-26). Praise is for ease of use and speed. The developer replies that AI server costs are high. [CWS reviews](https://chromewebstore.google.com/detail/oooikipggipaohjibkmoiacmmlilgokn/reviews)
- **IsManga, Google Play:**
  - "Doesn't work at all", with the words staying Japanese (2026-08-24).
  - Ads run wild in the built-in browser; the developer blames the manga sites (2026-08-09).
  - An older paid review reports outages ("Something went wrong") and limited working hours (2023).
  - [Google Play](https://play.google.com/store/apps/details?id=com.ismanga.ismanga&hl=en&gl=VN)
- **Ichigo, Chrome Web Store reviews:**
  - Accuracy is imperfect but readable and blends into the page (2026-10-12).
  - Works for Korean, Japanese and Mandarin to English but is slower (2026-09-24).
  - English source text was not translated (2026-09-16).
  - A user asks to "untranslate" stray side-text (2026-06-14).
  - A Premium user got identical output from different models (2026-05-11); the developer blamed a caching bug, since fixed.
  - [CWS reviews](https://chromewebstore.google.com/detail/manga-translator%F0%9F%8D%93/lepcfgkehgeiblekejomdmdklmjdmflp/reviews?hl=en)
- **Ichigo, third-party claim:** the UPDF blog claims Ichigo fails to recognize Japanese text in some images and PDFs. This is a single source and unverified. [UPDF](https://updf.com/chatgpt/japanese-manga-translator/)
- **Scan Translator, Chrome Web Store reviews (Oct 7–20, 2026):** short and positive. Reviewers like that it replaces text on the original, call translations "spot on" and "very accurate", and say it is better than other translator extensions. No complaints are visible among the 10 shown. [CWS reviews](https://chromewebstore.google.com/detail/mnngaddpelmhcgkbeajnbjmkdmpkogbo/reviews)
- **Torii, Firefox (3.5★ from 84; 27 one-star):**
  - Praise: translations read naturally, inpainting and typography, cheap (about $6 for 2,500 credits), a responsive developer, and time saved (30 minutes versus 2–3 hours).
  - A **Vietnamese-pronoun custom-prompt** user (2026-09-19) is happy.
  - Complaints: most one-star reviews have no text and appear to object to paying; a login error was reported (2026-07-18); one user wants Safari or iOS support (since shipped).
  - [AMO reviews](https://addons.mozilla.org/en-US/firefox/addon/torii-image-translator/reviews/)
- **Torii, Firefox, older search snippet:** a warning that it costs money after the first 20 image translations; imperfect results on handwriting. [AMO review](https://addons.mozilla.org/en-US/firefox/addon/torii-image-translator/reviews/2491545/)
- **Google-Translate-based extension ratings:** Transmonkey's "Image Translator - Comics Translator" has **1.7★ from 276 ratings** on Chrome and 2.4★ on Edge. [CWS](https://chromewebstore.google.com/detail/image-translator-comics-t/pbhpcbdjngblklnibanbkgkogjmbjeoe?hl=en); [Edge](https://microsoftedge.microsoft.com/addons/detail/opimdenmabjbacmheeebgjckapkmedkp)
- **Site blocking and compatibility:**
  - Scan's FAQ says some sites "block or obfuscate image access"; the workaround is Screenshot or upload. [Scan FAQ](https://scan-translator.com/faq)
  - IsManga Premium sells "Screenshot Mode" for broader site support. [CWS listing](https://chromewebstore.google.com/detail/oooikipggipaohjibkmoiacmmlilgokn)
  - Kites offers an area crop for canvas or WebGL readers. [Kites website](https://kites-translator.pages.dev/)
  - Ichigo uses an "Unlocker or Panel Tool". [CWS listing](https://chromewebstore.google.com/detail/manga-translator%F0%9F%8D%93/lepcfgkehgeiblekejomdmdklmjdmflp)
- **Changes in where raws come from:** Bato.to, once "the world's largest manga piracy website", shut down in late January 2026 after a CODA complaint and a criminal investigation in China. [Wikipedia: Bato](https://en.wikipedia.org/wiki/Bato_(website)) Sumi and Immersive Translate now advertise support for official publisher platforms (MANGA Plus, Shonen Jump+, Comic Days). [Sumi pricing](https://mangasumi.com/pricing); [Immersive Translate manga](https://immersivetranslate.com/manga)
- **Vietnamese pronoun and address complaints:**
  - Phong Vũ warns that AI gets forms of address, pronouns and context wrong and drops exclamations. [Phong Vũ](https://phongvu.vn/cong-nghe/dich-truyen-bang-nano-banana-pro/)
  - The Hako guide treats wrong names as a serious error and uses prior chapters to fix xưng hô. [docln guide](https://docln.net/thao-luan/3268-huong-dan-dich-truyen-bang-ai)
  - The VOZ snippet reports mixed "ta/ngươi" and "anh/em" (unverified). [VOZ](https://voz.vn/t/mc-ai-novel-trans-cong-cu-dich-truyen-tranh-tieu-thuyet-ho-tro-ai.1190485/)
- **Industry backlash, for context:** the Japan Association of Translators said AI has not shown the quality needed for nuance, cultural background or character traits in manga. [AniTrendz](https://anitrendz.net/news/2024/06/04/japan-association-of-translators-expresses-concerns-on-ai-use-for-high-volume-manga-translations/)

### Inferences
- **Free-tier generosity drives ratings.** IsManga's halving of its free allowance produced visible one- and two-star reviews. Torii's one-star reviews cluster around being charged at all. A Vietnamese beta should fix the free allowance up front and never reduce it silently, which also matches our "no silent charges" rule.
- **In-place lettering is the main thing users notice and praise.** Whether translations are accurate gets fewer and shorter comments. Inpainting and typography are where reviewers notice differences between tools (Torii).
- Requests for BYOK appear in IsManga's reviews, and Torii markets BYOK as cheaper. This supports offering BYOK in the beta.
- **Site compatibility is a universal pain point.** Every vendor ships a screenshot or crop fallback, and official Japanese readers often use canvas or scrambled images. Reliable support for official platforms is a selling point (Sumi's "checked by hand" list).

### Gaps
- **Reddit (r/manga, r/LearnJapanese, r/manhwa):** not reached. Old Reddit is blocked in the browser pane, and web searches with and without `site:reddit.com` returned no threads. The report should not claim Reddit sentiment from these notes.
- Chrome Web Store review pages show only about 10 recent reviews each, without stars on some pages. These samples are small and unweighted; no systematic review mining was done.
- No reviews were found that specifically discuss honorific handling (-san, -kun, -chan) in any competitor.
- No measured quality comparison of Japanese→Vietnamese output across tools exists in public sources. Vendor "best of 2026" roundups (for example ai-manga-translator.com, aimangatranslator.app, opentoon.co, kitsutl.com) are vendor-written and were not used as evidence. [Example: aimangatranslator.app](https://aimangatranslator.app/blog/best-ai-manga-translator-2026)

## Q4. Positioning gaps for a Japanese→Vietnamese-focused product

### Takeaway
No competitor documents **directed (A→B) Vietnamese pronoun rules, an honorific policy, evidence-backed per-series memory with a reading-position cutoff, or no-spoiler summaries**. The closest features are a free-text story summary (EasyComix Pro), paid "context sharing" of summaries of earlier pages (Torii, +1–2 credits per image), glossaries (Sumi, Kites, manga-image-translator, BallonsTranslator) and user-written custom prompts (Torii). In the market as seen:
- **Local privacy** is either Apple-only (Mangra, EasyComix, Sumi offline on iPhone/iPad), a tiny open-source extension (Kites, WebLLM), or technical desktop tools.
- **VND pricing** exists only through App Store in-app purchases and Immersive Translate.
- **Local Vietnamese payment methods** (MoMo, ZaloPay, VNPay, VietQR) were not seen anywhere.

### Cited Findings
- **Context and memory features, by product:**
  - Torii "Context sharing" passes summaries of earlier pages forward at **+1–2 credits per image**; no glossary or story memory is listed. [Torii updates](https://toriitranslate.com/updates)
  - EasyComix Pro lets the user paste a story summary covering names, relationships and slang. [App Store VN](https://apps.apple.com/vn/app/id6759873531)
  - Sumi offers a glossary and in-place editing on every plan. [Sumi pricing](https://mangasumi.com/pricing)
  - Kites has a custom glossary for names and terms. [CWS listing](https://chromewebstore.google.com/detail/pcaokchkdgnmfgjkljfpghlfohbdjcmj)
  - Ichigo offers "full-context" only for PDF and ZIP uploads. [CWS listing](https://chromewebstore.google.com/detail/manga-translator%F0%9F%8D%93/lepcfgkehgeiblekejomdmdklmjdmflp)
  - manga-image-translator's `--context-size` is OpenAI-only, and its glossary works only with the OpenAI translator. [GitHub](https://github.com/zyddnys/manga-image-translator)
  - BallonsTranslator's LLM mode has context, glossary and summary features. [GitHub](https://github.com/dmMaze/BallonsTranslator)
- **Vietnamese pronouns are handled only through user prompts or manual workflows:**
  - A Torii user wrote custom prompts for Vietnamese pronouns. [AMO reviews](https://addons.mozilla.org/en-US/firefox/addon/torii-image-translator/reviews/)
  - Hako's guide relies on glossaries and 2–5 prior chapters. [docln guide](https://docln.net/thao-luan/3268-huong-dan-dich-truyen-bang-ai)
  - A VOZ tool sets character relationships (unverified). [VOZ](https://voz.vn/t/mc-ai-novel-trans-cong-cu-dich-truyen-tranh-tieu-thuyet-ho-tro-ai.1190485/)
- **Local or private options:**
  - Kites: OCR, inpainting and WebLLM run on the device, but its default or other engines send text to Google, its pool or BYOK providers. [CWS listing](https://chromewebstore.google.com/detail/pcaokchkdgnmfgjkljfpghlfohbdjcmj); [PRIVACY.md](https://github.com/Unheat/Kites/blob/main/PRIVACY.md)
  - Mangra: offline Apple translation plus a Japanese OCR model on the device. [App Store VN](https://apps.apple.com/vn/app/id6502868308)
  - EasyComix: OCR on the device, but AI translation is online. [App Store VN](https://apps.apple.com/vn/app/id6759873531)
  - Sumi: offline on iPhone/iPad only. [Sumi homepage](https://mangasumi.com/)
  - Torii: "self-hosted" mode works through LM Studio plus a tunnel. [Torii updates](https://toriitranslate.com/updates)
  - MangaTrans: Ollama, English output only. [CWS listing](https://chromewebstore.google.com/detail/hoagaedakmopbokhnbjhoakgpdijahpg?hl=en)
  - manga-image-translator: Ollama by default for custom OpenAI. [GitHub](https://github.com/zyddnys/manga-image-translator)
- **Data retention, for contrast with our in-memory-image rule:**
  - Scan keeps translated account images for up to 90 days. [Scan FAQ](https://scan-translator.com/faq)
  - Torii's cache is stored on the device with 1-day-to-never retention. [Torii updates](https://toriitranslate.com/updates)
  - Kites keeps an IndexedDB cache for 7 days. [Kites website](https://kites-translator.pages.dev/)
- **VND pricing seen:**
  - EasyComix: 79,000đ/week, 149,000đ/month, 999,000đ/year.
  - Immersive Translate Pro: ₫149,000/month, ₫1,788,000/year.
  - IsManga: 229,000đ/month, 59,000đ/day, 2,499,000đ/year.
  - Ichigo: 229,000đ and 699,000đ.
  - Mangra: 249,000đ/month, 1,499,000đ/year.
  - Mangu: 799,000đ/year.
  - [EasyComix](https://apps.apple.com/vn/app/id6759873531); [Immersive Translate](https://immersivetranslate.com/en/pricing/); [IsManga](https://apps.apple.com/vn/app/id6443648567); [Ichigo](https://apps.apple.com/vn/app/id1641432177); [Mangra](https://apps.apple.com/vn/app/id6502868308); [Mangu](https://apps.apple.com/vn/app/id6747577465)
- **Web vendors price in USD or EUR via Stripe:** Sumi ("Prices in USD", Stripe) [Sumi pricing](https://mangasumi.com/pricing); Scan (EUR, Stripe) [Scan FAQ](https://scan-translator.com/faq); Ichigo web (USD) [Ichigo subscription page](https://ichigo.moe/subscription).
- **Chrome Web Store leaders have no Vietnamese focus and no local mode.** IsManga, Ichigo and Scan are cloud-only. Of the three, only IsManga lists Vietnamese as a target. [IsManga CWS](https://chromewebstore.google.com/detail/oooikipggipaohjibkmoiacmmlilgokn); [Ichigo CWS](https://chromewebstore.google.com/detail/manga-translator%F0%9F%8D%93/lepcfgkehgeiblekejomdmdklmjdmflp); [Scan CWS](https://chromewebstore.google.com/detail/mnngaddpelmhcgkbeajnbjmkdmpkogbo)
- **Edge is under-served:** the largest manga-specific Edge add-on has 5,330 installs and 2.4★. [Edge listing](https://microsoftedge.microsoft.com/addons/detail/opimdenmabjbacmheeebgjckapkmedkp)

### Inferences
- **Differentiators competitors do not document**, so we should test them rather than claim they are unique:
  1. Directed address rules (A→B), locked by the reader, with history.
  2. An explicit honorific policy that keeps -san, -kun, -chan, senpai and nee-chan without duplicating a Vietnamese title.
  3. Per-series memory with evidence (page and region) and a reading-position cutoff, so prefetch never leaks spoilers.
  4. Spoiler-free "previously on" summaries.
  5. Unknown speakers kept unknown instead of guessed.
- Today these are done by hand (Hako's glossary plus prior chapters; Torii custom prompts) or charged per image (Torii context sharing). Including memory in the base price is a clear contrast.
- **Price anchor for the VN beta:** about 149,000đ/month is the most common entry point among VN-priced competitors (EasyComix, Immersive Translate Pro). Annual plans run from 799,000đ to 1,788,000đ. A web plan priced in VND that accepts MoMo, ZaloPay, VNPay or VietQR would fill a gap none of the web competitors cover. This needs a check of payment-provider feasibility.
- **Free local mode on desktop Chrome/Edge, with Vietnamese output,** is offered only by Kites (830 users), and Kites' default engine sends text to Google. A free local mode that is truly offline (no cloud fallback, no metadata lookup) and covers Japanese→Vietnamese is an open position. Being honest about limits like cold-start model download is itself a differentiator against vague "unlimited" or "private" claims.
- **BYOK at a flat per-image fee** (Torii: 1 credit) is the market reference. Users of IsManga explicitly ask for BYOK.
- **Positioning risk:** EasyComix already claims a Vietnamese audience, story-summary context and free offline mode on Apple devices. Immersive Translate has huge reach and VND pricing. Sumi has broad platform coverage and lists Vietnamese. The Japanese→Vietnamese-specific quality claims therefore need measured evidence: blind Japanese→Vietnamese scoring on pronoun direction and names. Feature parity alone will not be enough.

### Gaps
- No competitor's Japanese→Vietnamese output quality, pronoun accuracy or honorific handling has been measured. The claims above come only from documentation. "Not documented" does not mean "not supported".
- Whether Immersive Translate's VND price applies to all VN visitors, and which payment methods it accepts apart from cards and crypto, was not verified.
- Whether any competitor plans Vietnamese-specific features (EasyComix's roadmap, Sumi's roadmap) is unknown.
- Whether official Japanese reader sites actively block translator extensions (versus only scrambling images) is undocumented. Only vendor FAQs mention blocking or obfuscation.

## Q5. Immersive Translate manga, multi-engine choices, and sound effects

### Takeaway
- **Immersive Translate** is the biggest translation extension that also does manga: 3,000,000 Chrome users, 4.5★. It sells manga translation as a **Premium feature that works on a list of supported sites** (100+, mostly official Japanese platforms plus MangaDex and Pixiv). The text is erased and relettered inside the bubbles. The "freely switchable" engines are a menu of brand names, and the better models are the paid upsell. Its own pages contradict each other on model names (stale GPT-4o / Claude 3.5 / Gemini 1.5 copy), on the free quota and on prices.
- **Why everyone lists DeepL, GPT, Claude, Gemini, Google and Microsoft:** these are the names users recognise, the keys BYOK users already hold, and simple text APIs that slot in after a separate OCR step. They are **no longer the cheap option per page**. At list prices, Google NMT, Microsoft, DeepL and Google's Translation LLM cost about $0.004–0.014 per manga page. Small LLMs cost about $0.0004–0.002 per page. Classic MT engines also cannot see the image, so they cannot tell who is speaking.
- **Sound effects:** professionals choose between replacing the SFX, adding a small translation next to it, or leaving it. No competitor documents a clear SFX policy. Sumi is the most careful: it flags SFX it is unsure about instead of inventing a line. **The safest default for Vietnamese readers is to keep the original SFX art and add a small, reversible Vietnamese gloss for the SFX that matter.**

### Cited Findings

#### Immersive Translate manga/comic feature (seen 2026-10-21)
- **Two features with different pricing and workflows:**
  - **"Manga Translation"** runs on supported sites. The user clicks the extension button on a supported site. The translation is embedded in the bubbles and the panel layout is kept. The page claims the font style follows the original (handwritten, Mincho, Gothic), that onomatopoeia and cultural references are converted, that translation is real time, and that progress syncs across devices.
    - The page says "Manga Translation is a Premium Feature".
    - The FAQ answer to "Is manga translation free?" says Premium is required.
    - Another FAQ answer says logged-in free users get **100 manga pages per month**. **The page contradicts itself.**
    - [Immersive Translate manga page](https://immersivetranslate.com/manga)
  - **"Image/Comic translator"** handles uploads, clipboard pastes and right-clicked web images, with batch translation of whole chapters. It accepts JPG, PNG and WEBP. OCR finds the text, the original text is erased by inpainting, and the translation is placed inside the image. It offers 16+ engines. The page says full image translation is free and Pro adds better OCR and layout. [Immersive Translate image/manga translator](https://immersivetranslate.com/en/image/manga-translator/) The pricing page, however, lists "Image Translation" and "Comic translation" as Pro-exclusive, and lists "Offline image translation /Unlimited" in the free tier. [Immersive Translate pricing](https://immersivetranslate.com/en/pricing/)
- **Supported sites, languages and platforms:**
  - "Pixiv, MANGA Plus, MangaDex, and 100+ more sites". The page has a site-search box and a form to request a new site. The list also shows Zebrack, MANGA Million, COMIC FUZ, Shonen Jump+, Comic Days, ComicWalker and others. [Manga page](https://immersivetranslate.com/manga)
  - 20+ target languages, including Tiếng Việt.
  - Extensions for Chrome, Edge, Firefox and Safari. The FAQ says the iOS and Android apps also do manga translation. [Manga page](https://immersivetranslate.com/manga)
  - Published by Funstory.ai Limited, Hong Kong (page footer). [Manga page](https://immersivetranslate.com/manga)
- **Engines named on the manga page:** the FAQ lists DeepL, GPT-4o, Claude 3.5, Gemini 1.5 Pro, Google Translate, Microsoft Translator "and more" (10+ engines). Pro "unlock[s] GPT-4o / Claude / Gemini", which the page says gives context-aware handling of onomatopoeia. This model copy is **out of date**: the pricing page lists GPT-6 Luna, Gemini 3 Flash, DeepSeek V4.1 Flash, Qwen 3.5 Plus, GLM-4.7 and DeepL Pro for Pro, and GPT-6.1 Sol, Gemini 3.1 Pro, Claude Sonnet 5.5 and Kimi K2.6 for Max. [Manga page](https://immersivetranslate.com/manga); [Pricing](https://immersivetranslate.com/en/pricing/)
- **Prices shown in two places:**
  - The manga page plan block is labelled "Prices adjusted for your region · United States". Pro is $9.99/month or $119.88/year. Max is $19.99/month or $239.88/year ("50M tokens/mo"). Both have a 3-day free trial. [Manga page](https://immersivetranslate.com/manga)
  - The pricing page, seen from Vietnam, shows Pro at ₫149,000/month or ₫1,788,000/year and Max at ₫499,000/month or ₫5,988,000/year, with token quotas instead of page quotas: Pro gets 20M "advanced model" tokens/month; Max gets 50M advanced plus 2M top-tier tokens. [Pricing](https://immersivetranslate.com/en/pricing/)
  - **No page quota for manga is published for Pro or Max.** The free-tier figure is 100 pages/month according to the FAQ.
- **Quality, latency and privacy statements:**
  - Quality: only marketing claims ("layout preserved", font matching, onomatopoeia conversion). [Manga page](https://immersivetranslate.com/manga)
  - Latency: no figures; the page claims "Real-time translation with no waiting". [Manga page](https://immersivetranslate.com/manga)
  - Privacy: "No retention of translated content", "Never used for training", encryption in transit, and ISO 27001/27701 claims. [Pricing](https://immersivetranslate.com/en/pricing/)
- **Users and ratings:**
  - Chrome Web Store: **3,000,000 users; 4.5★ from 3.2K ratings**; version 1.34.2; updated 2026-10-20; Featured. The listing description itself claims "over 30 million users worldwide". [CWS](https://chromewebstore.google.com/detail/bpoadfkcbjbfhfodiogcnhhhpibjhbnh?hl=en)
  - The manga page claims "Chrome Web Store · 4.9★ · 10,000+ reviews" and 30M+ downloads. This **conflicts** with the store's 4.5★ from 3.2K ratings. [Manga page](https://immersivetranslate.com/manga)

#### Classic MT and LLM API prices (seen 2026-10-21; USD)
- **Google Cloud Translation** ([Google Cloud pricing](https://cloud.google.com/products/translate/pricing)):
  - NMT: **first 500,000 characters/month free** (applied as a $10 monthly credit), then **$20 per 1M characters**.
  - Translation LLM: **$10 per 1M input characters plus $10 per 1M output characters**. Adaptive translation: $25 + $25.
  - Document translation: $0.08 per page.
- **Microsoft Azure Translator** ([Azure pricing](https://azure.microsoft.com/en-us/pricing/details/translator/)):
  - F0: **2M characters/month free**.
  - S1 text translation: **$10 per 1M characters**. Document translation: $15 per 1M characters.
  - **Document Translation (Image): $8 per 1,000 images**, up to 500 characters each.
  - Commitment tier: $2,055 per 250M characters.
- **DeepL API** (plans shown for "Vietnam (USD $)") ([DeepL API plans](https://www.deepl.com/en/pro-api)):
  - **Developer: a one-time credit of 1 million characters** (free); 1 glossary.
  - **Growth: $26/month billed annually**; 12M characters/year included; **$27.50 per 1M extra characters**; usage limit 50M/month; "No data training"; 2,000 glossaries.
  - **Correction to the brief:** the old "API Free 500k characters/month" no longer appears on this page.
- **DeepL Vietnamese support:** the developer languages table lists **Vietnamese (VI)** with Translation, Glossaries, Tag Handling, Translation Memory and Style Rules. Japanese (JA) is also listed. [DeepL supported languages](https://developers.deepl.com/docs/getting-started/supported-languages) DeepL launched Vietnamese on **2025-06-24** in every version of its Translator and in the API. [DeepL blog](https://www.deepl.com/en/blog/vietnamese-thai-hebrew-launch)
- **OpenAI**, per 1M tokens input / output ([OpenAI API pricing](https://developers.openai.com/api/docs/pricing)):

  | Model | Input | Output |
  |---|---|---|
  | gpt-6-luna | $0.10 | $0.50 |
  | gpt-6.1-sol | $2.00 | $10.00 |
  | gpt-6-astra | $10 | $50 |
  | gpt-5-nano | $0.05 | $0.40 |
  | gpt-5-mini | $0.25 | $2.00 |
  | gpt-5.4-mini | $0.75 | $4.50 |
  | gpt-4o-mini | $0.15 | $0.60 |
  | gpt-4.1-nano | $0.10 | $0.40 |
  | gpt-4.1-mini | $0.40 | $1.60 |
  | gpt-4o | $2.50 | $10.00 |
- **Google Gemini API**, standard tier per 1M tokens input / output. Every model listed has a free tier except 3.1 Pro preview. ([Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing))

  | Model | Input | Output | Note |
  |---|---|---|---|
  | gemini-2.5-flash-lite | $0.10 | $0.40 | |
  | gemini-3.1-flash-lite | $0.25 | $1.50 | |
  | gemini-3.5-flash-lite | $0.30 | $2.50 | |
  | gemini-2.5-flash | $0.30 | $2.50 | |
  | gemini-3.6-flash / gemini-3.8-flash | $0.75 | $3.75 | Rises to $1.50 / $7.50 on 2027-01-01 |
  | gemini-2.5-pro | $1.25 | $10 | |
- **Anthropic Claude**, per 1M tokens input / output. The Batch API costs 50% less. ([Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing))

  | Model | Input | Output | Note |
  |---|---|---|---|
  | Claude Haiku 5.5 | $0.10 | $0.50 | Prompts ≤100K tokens |
  | Claude Haiku 4.5 | $1 | $5 | |
  | Claude Sonnet 5 / 5.5 | $2 | $10 | |
  | Claude Sonnet 4.6 | $3 | $15 | |
- **Papago:** the NAVER Cloud Image Translation API lists Japanese and Vietnamese as both source and target. [NAVER Cloud docs](https://guide.ncloud-docs.com/docs/en/papago-image-translation-spec) Prices were not readable from the NAVER Cloud product page. [NAVER Cloud Papago](https://www.ncloud.com/product/aiService/papagoTranslation)

#### Public quality evidence
- **WMT25 General MT findings** (Kocmi et al., 2025): 30 language pairs; 60 systems, including 24 LLMs or online services; human evaluation (ESA/MQM) on half the pairs. The title argues it is time to stop evaluating on easy test sets. The per-pair results for Japanese were not checked here. [ACL Anthology](https://aclanthology.org/2025.wmt-1.22)
- **Intento "State of Translation Automation 2025"** (2025-10-29): 46 engines and LLMs across 11 language pairs. Customised and multi-agent solutions scored best (top in 9 of 11 pairs). Human evaluators often could not tell AI output from human translation. Per-engine scores were not in the public summaries. [Slator](https://slator.com/intento-releases-9th-annual-state-of-translation-automation-2025-industry-report/); [Intento](https://inten.to/the-state-of-translation-automation-2025/)
- A secondary blog says LLMs made up 89% of top performers across pairs (unverified against the report). [machinetranslation.com](https://www.machinetranslation.com/blog/best-mt-engines-per-language-pair)
- **JP-TL-Bench** (Shisa.AI, 2026) evaluates Japanese↔English LLM translation with anchored pairwise LLM judging. It covers neither Japanese→Vietnamese nor manga. [arXiv](https://arxiv.org/abs/2601.00223)
- **No public head-to-head Japanese→Vietnamese benchmark** of DeepL, Google, Microsoft, GPT, Gemini or Claude was found, and none covering manga dialogue. Searches returned only Vietnamese–Chinese/Lao and Japanese–English work. [ViBidirectionMT-Eval](https://arxiv.org/pdf/2501.08621)

#### Sound effects (SFX)
- **Strategies in the research literature:** Sell and Pasfield-Neofitou (2016), as cited in a 2024 ANLP paper, found four main strategies for Japanese SFX: **equivalence, coinage, descriptive, and omission**. [ANLP 2024](https://www.anlp.jp/proceedings/annual_meeting/2024/pdf_dir/D1-5.pdf)
- **Practice guides:** the usual options are to translate or replace with an equivalent, to add an overlay or subtitle (or replace the effect entirely), and to add notes or a glossary where needed. [1stopasia](https://www.1stopasia.com/blog/sound-effects-and-visual-language-translating-the-untranslatable-in-manga/)
- **Translated Korean comics:** SFX outside bubbles were often moved, resized or deleted, and some were kept. [InTRAlinea special issue](https://www.intralinea.org/specials/article/2634)
- **Fan versus official practice** (search-result summaries; the sources were not read in full):
  - Scanlations tended to keep cultural markers and romanise SFX.
  - Some official releases moved toward leaving SFX and honorifics untranslated.
  - A deluxe edition of *Akira* kept the original SFX without translation.
  - [Language Hat](https://languagehat.com/how-manga-was-translated-for-america/); [World Literature Today](https://www.worldliteraturetoday.org/node/2530)
- **Reference glossaries:**
  - The **JADED Network SFX dictionary**, a free Japanese→English SFX dictionary often recommended by learners. [WaniKani community](https://community.wanikani.com/t/translating-sfx-in-manga/48074)
  - J-Ono Search, an open-source searchable list of Japanese onomatopoeia, and the Mangastudies SFX glossary. [yakuaru resources](https://yakuaru.com/resources)
  - Vietnamese material found covers Japanese onomatopoeia vocabulary (giseigo, giongo, gitaigo), not manga lettering conventions. [Mytour](https://mytour.vn/vi/blog/bai-viet/tu-ngu-thanh-am-trong-tieng-nhat.html); [Viblo](https://viblo.asia/p/tu-tuong-thanh-tuong-hinh-trong-tieng-nhat-tiep-tiep-gAm5yXowldb)
- **What competitors say about SFX:**
  - Immersive Translate shows katakana SFX turned into English interjections and pitches "Sound FX & Cultural Context" as a Premium quality point. [Manga page](https://immersivetranslate.com/manga)
  - **Sumi's FAQ calls SFX "the hard cases"** and says it flags uncertain SFX instead of inventing a line. Vertical Japanese stays vertical, and users can flip back to the original. [Sumi homepage](https://mangasumi.com/)
  - **Torii** added a "bubbles-only filter" (2026-02-24), which skips non-bubble text such as SFX. [Torii updates](https://toriitranslate.com/updates)
  - An **Ichigo** user asked to "untranslate" stray side-text. [Ichigo CWS reviews](https://chromewebstore.google.com/detail/manga-translator%F0%9F%8D%93/lepcfgkehgeiblekejomdmdklmjdmflp/reviews?hl=en)
  - **Scan Translator, Comic Translate and manga-image-translator** describe no SFX policy. Their READMEs do not mention SFX or onomatopoeia. [Scan FAQ](https://scan-translator.com/faq); [Comic Translate README](https://raw.githubusercontent.com/ogkalu2/comic-translate/main/README.md); [manga-image-translator README](https://raw.githubusercontent.com/zyddnys/manga-image-translator/main/README.md)

#### Lessons from bigger competitors (cited practices)
- **Letting people try first:**
  - Sumi: 1 page with no signup, then 5 pages at signup plus 5 a day to claim. [Sumi pricing](https://mangasumi.com/pricing)
  - Scan: 3 translations without an account. [Scan FAQ](https://scan-translator.com/faq)
  - Ichigo: a free trial with "no registration required". [CWS](https://chromewebstore.google.com/detail/manga-translator%F0%9F%8D%93/lepcfgkehgeiblekejomdmdklmjdmflp)
- **Site compatibility as a product:**
  - Sumi publishes 110+ sites "checked by hand" and adds that this is never a promise every site works forever. [Sumi pricing](https://mangasumi.com/pricing); [Sumi homepage](https://mangasumi.com/)
  - Immersive has a searchable site list and a request form. [Manga page](https://immersivetranslate.com/manga)
- **Pricing presentation:**
  - Sumi turns pages into chapters ("1,500 pages ≈ 75 chapters"), says cancelling takes two clicks, and shows yearly savings ("Save 17%"). [Sumi pricing](https://mangasumi.com/pricing)
  - Ichigo labels annual billing "2 months free". [Ichigo](https://ichigo.moe/subscription)
  - Immersive shows VND prices and the annual saving percentage. [Pricing](https://immersivetranslate.com/en/pricing/)
  - Torii shows the model, credits used and timing for each translation; cached repeats cost 0 credits. [Torii updates](https://toriitranslate.com/updates)
- **Glossaries and prompts:**
  - Sumi has a glossary and in-place editing on every plan. [Sumi pricing](https://mangasumi.com/pricing)
  - Torii saves custom prompts (up to 1,000 characters). [Torii updates](https://toriitranslate.com/updates)
  - DeepL's API offers glossaries and style rules for Vietnamese. [DeepL supported languages](https://developers.deepl.com/docs/getting-started/supported-languages)
- **Mobile:**
  - Immersive has iOS and Android apps with manga translation. [Manga page](https://immersivetranslate.com/manga)
  - Sumi: one subscription across iPhone, iPad, Mac and Android (open testing). [Sumi pricing](https://mangasumi.com/pricing)
  - Torii: a Safari extension on iPhone and iPad, plus a PWA. [Torii updates](https://toriitranslate.com/updates)
- **Trust copy:**
  - Immersive: no retention, no training. [Pricing](https://immersivetranslate.com/en/pricing/)
  - Sumi: collects no browsing history; offline on iPhone/iPad. [Sumi homepage](https://mangasumi.com/)

### Inferences
- **Cost per manga page**, my arithmetic from the list prices above. Assumptions: about 400 Japanese characters of dialogue per page for classic MT; about 1,500 input and 600 output text tokens for LLMs; Vietnamese output assumed at about 2.5× the source character count where output is billed. OCR is excluded unless noted.

  | Engine | Cost per page | Note |
  |---|---|---|
  | Azure S1 | about $0.004 | F0 free tier covers about 5,000 pages/month |
  | Google NMT | about $0.008 | 500K free ≈ 1,250 pages/month |
  | DeepL Growth overage | about $0.011 | One-time 1M free ≈ 2,500 pages |
  | Google Translation LLM | about $0.014 | Input plus about 1,000 output characters |
  | Azure image document translation (OCR included) | $0.008 per image | |
  | Claude Haiku 5.5 / gpt-6-luna | about $0.00045 | |
  | gemini-2.5-flash-lite | about $0.0004 | |
  | gpt-4o-mini | about $0.0006 | |
  | gemini-3.1-flash-lite | about $0.0013 | |
  | gpt-4.1-mini / gpt-5-mini | about $0.0016 | |
  | gemini-2.5-flash | about $0.002 | |
  | gemini-3.8-flash | about $0.0034 | Doubles on 2027-01-01 |
  | Claude Haiku 4.5 | about $0.0045 | |
  | Sonnet 5.5 / gpt-6.1-sol | about $0.009 | |
  | gpt-4o | about $0.010 | |

  - Sending the page image to a vision model adds image tokens: roughly 1,000–1,600 per page (an assumption, not checked) at the input rate. For a Flash-Lite-class model that is under $0.0005.
  - **Conclusion:** a small multimodal LLM that reads the whole page costs about the same as, or less than, classic MT, and it sees the art and the speakers. The "cheap" reputation of DeepL, Google and Microsoft dates from before small LLMs. Today their advantages are free monthly allowances (Azure 2M; Google 500K) and their brands.
- **Why products converge on these engines (business reasons):**
  1. **Brand recognition.** Users trust the names, and the names fill a marketing feature list ("10+ engines") at no cost.
  2. **BYOK familiarity.** Users already hold OpenAI, Gemini, Claude or DeepL keys. Torii's BYOK list covers exactly these providers plus OpenRouter, DeepSeek and Grok. [Torii updates](https://toriitranslate.com/updates)
  3. **The engine switch is a paid upsell.** Immersive keeps "top" models for Pro or Max and meters them by token tiers. [Pricing](https://immersivetranslate.com/en/pricing/)
  4. **Easy architecture.** OCR is separate, so any text API plugs in with no image understanding needed.
  5. **Cover against outages and price changes** through failover. Kites, for example, fails over between engines automatically. [Kites website](https://kites-translator.pages.dev/)
- **Trade-offs of a text-only engine after OCR, compared with one vision model reading the page:**
  - The text-only engine sees isolated strings. It cannot know who speaks to whom, so Vietnamese pronouns (anh/em, tao/mày, cậu/tớ) and **directed address** become guesses.
  - It may translate or drop honorifics inconsistently.
  - It loses the reading order between bubbles and cannot tell SFX from dialogue.
  - A glossary (DeepL, Google) fixes names but not pronoun direction.
  - A vision LLM given the page plus our story memory can resolve the speaker when the evidence is visible. It still needs our rules: unknown speakers stay unknown, and reader locks win.
  - Classic MT remains useful as a cheap, fast fallback or for the free tier. It should be labelled lower quality for pronouns.
- **Direct Japanese→Vietnamese:** DeepL (since 2025-06-24), Google and Microsoft all support both languages, so the pair is available. None publishes whether it translates directly or pivots through English, and no public Japanese→Vietnamese quality ranking exists. **We must measure it on our own ground-truth pages.**
- **A good SFX default for Vietnamese readers,** consistent with AGENTS.md (never silently drop text; erase art only where it is safe; reversible annotation):
  - (a) Leave SFX art untouched by default.
  - (b) Add a small, removable Vietnamese gloss next to SFX that carry meaning. Use Vietnamese onomatopoeia where a natural one exists (for example a Vietnamese crash or bang word). Otherwise use a short descriptive gloss for mimetic words (gitaigo), such as a state word for "silence" or "glaring".
  - (c) Offer a per-series setting: off / gloss / replace. Replace only where text separation is clean.
  - (d) Never invent an SFX meaning. When unsure, follow Sumi and show "uncertain" or keep the original.
  - This matches the documented professional strategies (equivalence, descriptive, omission) without destroying art. It also turns a weakness of competitors (bubbles-only filters) into a visible feature.
- **Lessons worth copying:**
  - Free trial with no account, plus a small daily allowance that builds a habit (Sumi).
  - A published, honest list of tested sites, with a request form (Sumi, Immersive).
  - Prices shown as chapters, not just pages, and in VND (Sumi; Immersive in VND).
  - A per-translation details panel showing model, cost and cache hits (Torii).
  - Glossary on every plan (Sumi).
  - A one-tap "original" toggle (Sumi).
  - One account across extension, web and mobile (Sumi, Immersive).
  - Avoid what hurts competitors: self-contradicting free quotas and stale model names (Immersive), and silently cutting free allowances (IsManga, Q3).
  - Nobody documents per-series settings (honorific mode, pronoun locks, SFX mode). This is an open differentiator.

### Gaps
- Immersive Translate:
  - The real free manga quota is unclear: "Premium" in one FAQ answer, 100 pages/month in another.
  - Pro/Max manga page quotas, latency figures, and whether an "original" toggle or a side-by-side bilingual mode exists for manga (a search summary mentioned bilingual mode) were not verified on official pages.
  - Which engines actually power manga translation on each tier is unclear, given the stale copy.
  - User growth over time was not found; only the current CWS 3M and the vendor's 30M claim.
- Papago API prices could not be read. Google's Basic table shows a "/1,000,000 byte" unit label that conflicts with "characters" elsewhere on the page; this was not resolved.
- Whether Google, Microsoft and DeepL translate Japanese→Vietnamese directly or pivot through English is not documented publicly.
- Japanese→Vietnamese quality evidence: no public benchmark found. The WMT25 per-pair tables and Intento's per-engine scores were not opened.
- Image-token counts per manga page for each vision model were not checked; the per-page vision cost is an estimate.
- Vietnamese SFX conventions: no public guide from Vietnamese scanlation teams or publishers (for example Kim Đồng) was found. A Vietnamese 2024 university paper on Japanese onomatopoeia could not be text-extracted. [Hue University PDF](https://csdlkhoahoc.hueuni.edu.vn/data/2024/11/20240825202227.pdf)
- Ichigo's and Scan Translator's SFX handling is not documented.
- The JADED Network site's current status was not checked directly.
