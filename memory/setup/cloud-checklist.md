# Cloud checklist — заполняет Setup (блок 0)

Ответы yes/no. **Секреты сюда не писать.**

| Пункт | Статус | Комментарий |
|-------|--------|-------------|
| Репозиторий подключён к Cursor Cloud Environment | yes | Форк `yasnosolnce2024/Excalibur-2-Cloud` (тенант Елена Горбачёва). Не пушить в Horosheff. |
| Automation Tools → **Memories = OFF** | yes | First-run prompt: Memories OFF. Automation Memory игнорировать. |
| Secrets: PUBLIC_SITE_URL | no | Живой URL сайта WP неизвестен. Не выдумывать. Вопрос Елене. |
| Secrets: FTP_HOST / FTP_USER / FTP_PASS / FTP_ROOT | no | SFTP не задан. Пароли не выдумывать и не писать в git. |
| MCP Wordstat (если нужен Scout) | no | В брифе не запрошен. Спросить, нужен ли. |
| MCP WordPress blob / image API (если нужны) | no | WP blob не подтверждён. |
| Image API key (Kie / provider) | no | `KIE_API_KEY` добавят позже как Cloud Secret. Не выдумывать ключ. Cover-конфиг пишем без ключа. |
| Yandex Metrika tokens | no | Опционально; не заданы. |
| First-run automation = Setup prompt | yes | Этот прогон — First-run Setup only. Scout / Research / Writer / Publish не запускать. `EXCALIBUR_BLOG_ALLOW_PUBLISH` не ставить. |
| Daily automation = CLOUD-AUTOMATION.md (после setup) | no | Только после `setup_complete=true` и ответов по сайту/FTP. |

First-run vs Daily: сейчас только онбординг тенанта. Daily-пайплайн статей запрещён, пока stamp не закрыт.
