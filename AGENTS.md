# Repository Guidelines

## Project Structure & Module Organization
- `app/` — Flask core: `routes.py` registers the blueprint, `models.py` defines SQLAlchemy entities, `background.py` drives long-running jobs, `templates/` and `static/` build the UI.
- `auto_checker.py` — CLI обработчик архивов Moodle; поддерживает `.pdf`, `.docx`, `.doc`, `onlinetext.html` и агрегирует лучший результат для студента.
- `docs/` хранит операционные гайды (см. `docs/PDF_MULTI_GUIDE_RU.md` для PDF/многодоковой проверки).
- `tests/` содержит сценарии для ручного и автоматизированного тестирования (`archive_upload_demo.py`).
- Ресурсы деплоя лежат в корне: `Dockerfile`, `docker-compose.yml`, `wsgi.py`, `run.sh`, `start.sh`.

## Build, Test, and Development Commands
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt                     # включает PyPDF2 для PDF
flask --app app:create_app run --debug              # UI на http://localhost:5000
python -m tests.archive_upload_demo                 # smoke-тест загрузки архивов
export DUMMY_EVAL=true; python auto_checker.py      # офлайн проверка архивов
docker compose up --build                           # продовый стек с VPN
```
`run.sh` запускает auto_checker с реальными моделями; следите за лимитами Gemini.

## Coding Style & Naming Conventions
- PEP 8, четыре пробела, лимит 100 символов; предпочтительны type hints и явные helper-функции (`_preserve_upload_name`, `_workspace_slug`).
- Названия Flask view/фоновых задач — глаголы с контекстом (`launch_auto_check`, `job_manager`).
- Файлы результатов CLI именуйте `results/<safe_filename>.json`; агрегаты — `result.txt`.
- Новые env-переменные валидируйте и задавайте дефолты в `create_app`.

## Testing Guidelines
- Для CLI используйте режим `DUMMY_EVAL=true` и архив `example/ii.zip` (подробности в `docs/PDF_MULTI_GUIDE_RU.md`).
- При добавлении форматов файлов пишите unit-тесты извлечения текста и обновляйте smoke-сценарии.
- UI и API тестируйте Flask test client’ом; временные хранилища создавайте в `TemporaryDirectory` и направляйте `DATA_STORAGE`.

## Commit & Pull Request Guidelines
- Сообщения как в истории репо: короткое глагольное описание (`support pdf uploads`, `refine room summary`).
- В PR описывайте пользовательский эффект, прикладывайте список тестов (UI, CLI `auto_checker`, dummy/offline режим) и ссылку на сопутствующие гайды.
- Скриншоты или логи при изменении шаблонов и фоновых джоб обязательны.

## Security & Configuration Tips
- Не коммитьте реальные ключи Gemini/VPN; используйте `.env` или секреты CI.
- Для локальной разработки ставьте `DISABLE_VPN=true`; в проде документируйте требуемые `PROXY_*`.
- Вычищайте `instance/data` и распакованные студентские архивы перед коммитами: `rm -rf instance/data/*`.
