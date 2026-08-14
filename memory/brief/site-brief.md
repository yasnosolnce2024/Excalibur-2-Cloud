# Site brief — Формула активного долголетия

Метаданные сайта и контент-стратегия для Cover / Scout / Publish.
Не источник prose для Writer (Writer = master prompt + research + titles-only).

## Сайт

- **site_name:** Формула активного долголетия
- **site_url:** `{{SITE_BASE}}` (live URL только в Cloud Secrets / PUBLIC_SITE_URL; пока не задан)
- **language:** ru
- **niche:** активное долголетие 55+; живая история; достоинство возраста; кухня и вкус к жизни
- **бренд / leitmotif:** возраст — паспорт, не приговор
- **автор:** Елена Горбачёва (в сети Солнце), 61

## Каналы

- **дом:** VK-сообщество https://vk.ru/formuladolgoletiya
- **витрина:** Дзен https://dzen.ru/formuladolgoletiya — приводит людей в VK
- **личная страница автора (sameAs):** https://vk.ru/yasnosolnyshko60

## Продукт и CTA

Курсы **не продаём**. Название курса **не писать** в статьях.

`cta_required=false`, `cta_links=[]` — ссылка в тексте не обязательна.
Если в материале уместно пригласить в круг — дом это VK, без давления и без «тарифов».

См. `shared/tenant-config.json` → `cta_links`, `cta_required`.

## Редакция

- **ключ контента:** living story (сцена, вопрос-дверь, тепло)
- **рубрика «Формула вкуса»:** путь с нуля, кухня, детская мечта готовить
- **формат:** живая колонка / сцена + смысл / практика без кафедры; how-to только если это жизнь, не чеклист-инфобиз
- **канон:** `shared/pipeline-canon.json`
- **стиль:** `shared/article-style.md` + `shared/SOUL.md` + `shared/dzen-content-rules.md` (`dzen_rf_pack=true`)
- **темы:** Scout → handoff `topic_id` + короткий title; `memory/topics/` запрещена
- **сигналы Scout:** VK-сообщество и канал Дзен (см. `tenant-config.scout_signal_urls`)
- **Wordstat:** не подключён, пока Елена не попросит

## Главный герой визуала

- **cover_mode:** `illustrative` — человека-хозяина нет; лицо Елены не ставить и не генерировать
- **hero:** сцена кухни (`kitchen-warmth-scene`), не портрет, не кот, не белое худи
- **размеры:** VK обложка **1:1** (квадратный кроп cover); Дзен-карточка и quad-панель **16:9** (холст 2048×1152)
- **настроение:** тёплая кухня, жизнь, достоинство. Leitmotif: возраст — паспорт, не приговор
- **рубрика «Формула вкуса»:** стол, еда, руки без лица, свет из окна
- **палитра:** фон `#FFFFFF`; ink `#2A2118` / `#141821`; терракота `#C45C26`; шалфей `#6B8F71`; дерево `#8B5E3C`. Не `#FF1493`
- **preset:** `kitchen-warmth-ru` (`cover_hero_mode=illustrative_scene`, `skip_human_host=true`)
- **reference / lock:** `memory/cover/blog-hero.json` — `prompt_fragment` про кухню без хозяина; `meme_caption_ru=""`
- **style:** `memory/cover/cover-design-code.json` (`kitchen_warmth_dignity`) + `memory/cover/quad-style-kitchen-warmth-ru.json`
- **gap:** нет PNG moodboard / style plate; Cover i2i без plate не запускать; `KIE_API_KEY` и `PUBLIC_SITE_URL` позже

## Запреты

- VPN / обход блокировок (`dzen_rf_pack`)
- Выдуманные цены
- Продажа курсов и имя курса
- Инфоцыганский тон, кафедра, стыд за возраст
- Чужой слоган / чужие статьи / чужое лицо в SOUL и на обложке
- Эмодзи в тексте статей (дефолт Дзена)
- Секреты и live hostname в git-артефактах (только `{{SITE_BASE}}`)
