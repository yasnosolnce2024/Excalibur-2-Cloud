# Cover assets — Формула активного долголетия

Фото Елены Горбачёвой **нет**. Лицо не класть и не генерировать.  
`cover_mode=illustrative`, host на обложке не нужен.

## Сейчас

- PNG/JPG moodboard **нет** (visual-inbox — только `notes.md`).
- Style plate для Kie i2i **нет**. `local_reference` пуст.
- **Cover без plate не запускать.** Не подставлять чужой CDN и не выдумывать `reference_url_hosted`.

## Позже (повторный Setup Visual)

Елена пришлёт 2–6 картинок настроения: кухня, свет из окна, стол, еда, руки без лица.

Тогда сюда:

- moodboard / style plate → корень `assets/` и при необходимости `style-refs/`
- обновить `quad-style-kitchen-warmth-ru.json` → `local_reference`
- только после plate + `KIE_API_KEY` в Cloud Secrets можно billed Cover i2i

## Запрещено класть

- чужое лицо, белое худи ведущего, pink-cat коллаж
- сток «счастливая пенсионерка», anti-age до/после
- ключи Kie и live hostname
